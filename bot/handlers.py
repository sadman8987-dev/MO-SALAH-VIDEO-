"""المنطق الأساسي: التحليل، التحميل، الأزرار، الترجمات، القص، قوائم التشغيل..."""
import asyncio
import html
import logging
import os
import re
import secrets
import shutil
import time
import uuid
from typing import Optional

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message, User
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .common import (
    ACTIVE, PENDING, PLAYLISTS, SESSIONS, STOP,
    check_sub, extract_url, fmt_duration, get_sem, get_session, get_username,
    human_size, limit_text, parse_ts, precheck, quota_ok, render_progress,
    safe_edit, safe_name,
)
from .config import Config
from .db import DB
from .downloader import (
    AUDIO_FORMATS, GALLERY_OK, IMG_EXTS, VID_EXTS,
    DownloadError, DownloadResult, MediaInfo, TooBigError,
    compress_video, convert_to_mp3, download_direct, download_media,
    download_subtitle, extract_info, fetch_gallery, fetch_thumb,
    is_direct_url, is_public_url, make_gif, make_video_note, pick_fit,
    probe_duration, search_youtube, split_file_raw, split_media,
)
from .texts import t

log = logging.getLogger(__name__)
router = Router()

YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
CLIP_RE = re.compile(
    r"^\s*(\d+(?::\d+){0,2})\s*(?:-|–|—|to|إلى)\s*(\d+(?::\d+){0,2})\s*(mp3|audio|صوت)?\s*$",
    re.I,
)
KIND_ICON = {"a": "🎵", "v": "🎬", "n": "⭕", "g": "🎞"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024


# ------------------------------------------------------------- keyboards
def build_card(info: MediaInfo, sid: str, lang: str, cfg: Config):
    meta_parts = []
    if info.uploader:
        meta_parts.append("👤 " + html.escape(info.uploader))
    if info.duration:
        meta_parts.append("⏱ " + fmt_duration(info.duration, lang))
    text = t(lang, "card", title=html.escape(info.title), meta="  •  ".join(meta_parts))

    b = InlineKeyboardBuilder()
    height_buttons = 0
    if info.has_video:
        b.button(text=t(lang, "btn_auto"), callback_data=f"dl:{sid}:v:auto")
        for h in info.heights:
            sz = info.sizes.get(h)
            label = f"🎬 {h}p"
            if sz:
                label += f" · {human_size(sz)}"
                if sz > cfg.max_upload_bytes:
                    label += " ✂️"
            b.button(text=label, callback_data=f"dl:{sid}:v:{h}")
            height_buttons += 1
    for br in ("mp3_128", "mp3_192", "mp3_320"):
        b.button(text=f"🎵 MP3 {br.split('_')[1]}k", callback_data=f"dl:{sid}:a:{br}")
    b.button(text="🎵 M4A", callback_data=f"dl:{sid}:a:m4a")
    b.button(text="🎵 OPUS", callback_data=f"dl:{sid}:a:opus")
    b.button(text="🎼 FLAC", callback_data=f"dl:{sid}:a:flac")
    b.button(text="🎼 WAV", callback_data=f"dl:{sid}:a:wav")
    b.button(text=t(lang, "btn_voice"), callback_data=f"dl:{sid}:a:voice")
    if info.has_video:
        b.button(text=t(lang, "btn_note"), callback_data=f"dl:{sid}:n:0")
        b.button(text=t(lang, "btn_gif"), callback_data=f"dl:{sid}:g:0")
    if info.thumbnail:
        b.button(text=t(lang, "btn_thumb"), callback_data=f"dl:{sid}:t:0")
    extra = 0
    if info.subs:
        b.button(text=t(lang, "btn_subs"), callback_data=f"sbm:{sid}")
        extra += 1
    b.button(text=t(lang, "btn_clip"), callback_data=f"cl:{sid}")
    extra += 1
    b.button(text=t(lang, "btn_cancel"), callback_data=f"x:{sid}")

    layout = []
    if info.has_video:
        layout.append(1)
        n = height_buttons
        while n > 0:
            layout.append(min(2, n))
            n -= 2
    layout += [3, 3, 2]
    if info.has_video:
        layout.append(2)
    if info.thumbnail:
        layout.append(1)
    layout.append(extra)
    layout.append(1)
    b.adjust(*layout)
    return text, b.as_markup()


def build_subs_menu(info: MediaInfo, sid: str, lang: str):
    b = InlineKeyboardBuilder()
    for i, s in enumerate(info.subs):
        label = f"📝 {s['code']}" + (" (auto)" if s["auto"] else "")
        b.button(text=label, callback_data=f"sb:{sid}:{i}")
    b.button(text=t(lang, "btn_back"), callback_data=f"bk:{sid}")
    b.adjust(2)
    return t(lang, "subs_title"), b.as_markup()


def build_playlist_card(info: MediaInfo, sid: str, lang: str):
    text = t(lang, "pl_card", title=html.escape(info.title), n=len(info.playlist))
    b = InlineKeyboardBuilder()
    b.button(text=t(lang, "btn_pl_video"), callback_data=f"pl:{sid}:v")
    b.button(text=t(lang, "btn_pl_audio"), callback_data=f"pl:{sid}:a")
    b.button(text=t(lang, "btn_cancel"), callback_data=f"x:{sid}")
    b.adjust(1)
    return text, b.as_markup()


def settings_kb(user: dict):
    lang = user["lang"]
    b = InlineKeyboardBuilder()
    for code, name in (("ar", "🇪🇬 العربية"), ("en", "🇬🇧 English")):
        b.button(
            text=("✅ " if user["lang"] == code else "") + name,
            callback_data=f"set:lang:{code}",
        )
    for code in ("ask", "best", "720", "480", "audio"):
        b.button(
            text=("✅ " if user["pref"] == code else "") + t(lang, f"pref_{code}"),
            callback_data=f"set:pref:{code}",
        )
    b.button(
        text=("✅ " if user["big"] == "split" else "") + t(lang, "big_split"),
        callback_data="set:big:split",
    )
    b.button(
        text=("✅ " if user["big"] == "compress" else "") + t(lang, "big_compress"),
        callback_data="set:big:compress",
    )
    b.button(
        text=t(lang, "doc_on" if user["doc"] else "doc_off"),
        callback_data=f"set:doc:{0 if user['doc'] else 1}",
    )
    b.adjust(2, 1, 1, 1, 1, 1, 2, 1)
    return b.as_markup()


# ------------------------------------------------------------- sending
async def send_result(
    bot: Bot,
    chat_id: int,
    kind: str,
    file,
    caption: str,
    info: MediaInfo,
    res=None,
    is_part: bool = False,
    q: str = "",
    thumb: Optional[str] = None,
    as_doc: bool = False,
):
    th = FSInputFile(thumb) if thumb else None
    dur = None
    if not is_part:
        dur = (res.duration if res is not None and res.duration else None) or info.duration or None
    if kind == "a":
        if q == "voice":
            return await bot.send_voice(chat_id, file, caption=caption, duration=dur)
        if as_doc:
            return await bot.send_document(chat_id, file, caption=caption, thumbnail=th)
        return await bot.send_audio(
            chat_id, file, caption=caption, title=info.title[:64],
            performer=(info.uploader or None), duration=dur, thumbnail=th,
        )
    if as_doc:
        return await bot.send_document(chat_id, file, caption=caption, thumbnail=th)
    kw = {}
    if res is not None:
        kw = dict(width=res.width, height=res.height)
    if dur:
        kw["duration"] = dur
    return await bot.send_video(
        chat_id, file, caption=caption, supports_streaming=True, thumbnail=th, **kw
    )


def _file_id(sent) -> Optional[str]:
    for attr in ("audio", "voice", "video", "document"):
        obj = getattr(sent, attr, None)
        if obj:
            return obj.file_id
    return None


def _input(path: str, kind: str, q: str):
    if kind == "a" and q == "voice":
        return FSInputFile(path, filename="voice.ogg")
    return FSInputFile(path)


async def deliver(
    bot: Bot, cfg: Config, db: DB, chat_id: int, status: Message, lang: str,
    kind: str, q: str, res: DownloadResult, caption: str, info: MediaInfo,
    cache_key: Optional[str], prefs: dict, thumb: Optional[str],
) -> None:
    """يرفع الملف: عادي / مضغوط / مقسّم لأجزاء، أو فيديو دائري / GIF."""
    if kind in ("n", "g"):
        dst = os.path.join(res.outdir, "special.mp4")
        if kind == "n":
            await make_video_note(res.path, dst)
        else:
            await make_gif(res.path, dst)
        if os.path.getsize(dst) > cfg.max_upload_bytes:
            raise TooBigError("special too big")
        dur = int(await probe_duration(dst)) or None
        await safe_edit(status, t(lang, "uploading"))
        if kind == "n":
            await bot.send_video_note(chat_id, FSInputFile(dst), duration=dur, length=384)
        else:
            await bot.send_animation(chat_id, FSInputFile(dst), caption=caption, duration=dur)
        return

    as_doc = bool(prefs.get("doc"))
    path = res.path
    cur = res
    size = os.path.getsize(path)

    if size > cfg.max_upload_bytes:
        if (
            prefs.get("big") == "compress"
            and kind == "v"
            and not as_doc
            and res.duration
            and res.duration <= 3600
        ):
            try:
                await safe_edit(status, t(lang, "compressing"))
                dst = os.path.join(res.outdir, "compressed.mp4")
                await compress_video(path, dst, cfg.max_upload_bytes, res.duration)
                if os.path.getsize(dst) <= cfg.max_upload_bytes:
                    path = dst
                    cur = DownloadResult(dst, res.outdir, None, None, res.duration)
                    size = os.path.getsize(dst)
            except Exception as e:  # noqa
                log.warning("compress failed, falling back to split: %s", e)

    if size > cfg.max_upload_bytes:
        if not cfg.split_large:
            raise TooBigError(str(size))
        await safe_edit(status, t(lang, "splitting"))
        parts = await split_media(path, cfg.max_upload_bytes)
        await safe_edit(status, t(lang, "uploading"))
        for i, part in enumerate(parts, 1):
            pcap = f"{caption}\n\n📦 {t(lang, 'part')} {i}/{len(parts)}"
            await send_result(
                bot, chat_id, kind, _input(part, kind, q), pcap, info, cur,
                is_part=True, q=q, thumb=thumb, as_doc=as_doc,
            )
        return

    await safe_edit(status, t(lang, "uploading"))
    sent = await send_result(
        bot, chat_id, kind, _input(path, kind, q), caption, info, cur,
        q=q, thumb=thumb, as_doc=as_doc,
    )
    fid = _file_id(sent)
    if fid and cache_key:
        await db.cache_set(cache_key, fid)


async def run_download(
    bot: Bot, cfg: Config, db: DB, chat_id: int, status: Message, uid: int,
    lang: str, info: MediaInfo, kind: str, q: str, clip=None,
) -> bool:
    """ينزّل ويرسل الملف. يرجع True لو نجح."""
    if not await quota_ok(db, cfg, uid):
        await safe_edit(status, t(lang, "err_quota", limit=cfg.daily_limit))
        return False

    ACTIVE[uid] = ACTIVE.get(uid, 0) + 1
    outdir = None
    try:
        prefs = await db.get_prefs(uid)
        special = kind in ("n", "g")
        if special and not info.has_video:
            raise DownloadError("this link has no video")
        if kind == "v" and not info.has_video:
            kind, q = "a", "mp3_192"
        dl_kind = "v" if special else kind
        if special:
            q = pick_fit(info, cfg, 480)
            secs = 60 if kind == "n" else 30
            clip = (0, min(info.duration or secs, secs))
        elif kind == "v" and q == "auto":
            q = pick_fit(info, cfg)

        username = await get_username(bot)
        caption = f"{KIND_ICON[kind]} {html.escape(info.title[:200])}"
        if clip and not special:
            caption += f"\n✂️ {fmt_duration(clip[0])} – {fmt_duration(clip[1])}"
        if username:
            caption += f"\n\n🤖 @{username}"

        cache_key = None
        if not clip and not special:
            cache_key = f"{info.extractor}:{info.id}:{kind}:{q}" + (":d" if prefs["doc"] else "")
            cached = await db.cache_get(cache_key)
            if cached:
                try:
                    await safe_edit(status, t(lang, "uploading"))
                    await send_result(
                        bot, chat_id, kind, cached, caption, info, q=q, as_doc=prefs["doc"]
                    )
                    await db.record(uid, info.url, info.title, info.extractor)
                    return True
                except TelegramBadRequest:
                    await db.cache_delete(cache_key)

        sem = get_sem(cfg)
        if sem.locked():
            await safe_edit(status, t(lang, "queue"))

        state = {"stage": "downloading", "pct": 0.0, "speed": None, "eta": None}
        async with sem:
            await safe_edit(status, t(lang, "starting"))
            task = asyncio.create_task(
                download_media(info.url, dl_kind, q, cfg, state, clip)
            )
            last = ""
            while True:
                done, _ = await asyncio.wait({task}, timeout=2.5)
                if done:
                    break
                txt = render_progress(lang, state)
                if txt != last:
                    await safe_edit(status, txt)
                    last = txt
            res = await task  # قد يرفع DownloadError
        outdir = res.outdir

        real_dur = await probe_duration(res.path)
        if real_dur:
            res.duration = int(real_dur)
        thumb = None
        if kind in ("v", "a"):
            thumb = await fetch_thumb(info.thumbnail, res.outdir, cfg)

        await deliver(
            bot, cfg, db, chat_id, status, lang, kind, q, res, caption, info,
            cache_key, prefs, thumb,
        )
        await db.record(uid, info.url, info.title, info.extractor)
        return True

    except TooBigError:
        await safe_edit(status, t(lang, "err_toobig", limit=limit_text(cfg)))
    except DownloadError as e:
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
    except TelegramBadRequest as e:
        msg = str(e)
        if "too large" in msg.lower():
            await safe_edit(status, t(lang, "err_toobig", limit=limit_text(cfg)))
        else:
            log.exception("telegram error")
            await safe_edit(status, t(lang, "err_generic", reason=html.escape(msg[:200])))
    except Exception as e:  # noqa
        log.exception("unexpected download error")
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e)[:200])))
    finally:
        ACTIVE[uid] = max(0, ACTIVE.get(uid, 1) - 1)
        if outdir:
            shutil.rmtree(outdir, ignore_errors=True)
    return False


# ----------------------------------------------- direct files + galleries
async def run_direct(
    bot: Bot, cfg: Config, db: DB, chat_id: int, status: Message,
    uid: int, lang: str, url: str,
) -> bool:
    """تحميل ملف مباشر (PDF/ZIP/APK/صورة...) وإرساله كمستند، أو تقسيمه لو كبير."""
    if not await quota_ok(db, cfg, uid):
        await safe_edit(status, t(lang, "err_quota", limit=cfg.daily_limit))
        return False
    ACTIVE[uid] = ACTIVE.get(uid, 0) + 1
    outdir = os.path.join(cfg.download_dir, uuid.uuid4().hex)
    os.makedirs(outdir, exist_ok=True)
    try:
        sem = get_sem(cfg)
        if sem.locked():
            await safe_edit(status, t(lang, "queue"))
        state = {"stage": "downloading", "pct": 0.0, "speed": None, "eta": None}
        async with sem:
            await safe_edit(status, t(lang, "starting"))
            task = asyncio.create_task(
                download_direct(url, outdir, cfg, state, cfg.max_upload_bytes * 20)
            )
            last = ""
            while True:
                done, _ = await asyncio.wait({task}, timeout=2.5)
                if done:
                    break
                txt = render_progress(lang, state)
                if txt != last:
                    await safe_edit(status, txt)
                    last = txt
            path = await task

        name = os.path.basename(path)
        ext = os.path.splitext(name)[1].lower()
        size = os.path.getsize(path)
        username = await get_username(bot)
        caption = f"📎 {html.escape(name[:200])}" + (f"\n\n🤖 @{username}" if username else "")
        await safe_edit(status, t(lang, "uploading"))

        if size > cfg.max_upload_bytes:
            if not cfg.split_large:
                raise TooBigError(str(size))
            await safe_edit(status, t(lang, "splitting"))
            parts = await asyncio.to_thread(split_file_raw, path, cfg.max_upload_bytes)
            await safe_edit(status, t(lang, "uploading"))
            for i, part in enumerate(parts, 1):
                await bot.send_document(
                    chat_id, FSInputFile(part),
                    caption=f"{caption}\n\n📦 {t(lang, 'part')} {i}/{len(parts)}",
                )
            await bot.send_message(chat_id, t(lang, "join_parts"))
        else:
            sent = False
            if ext in IMG_EXTS and size <= MAX_PHOTO_BYTES:
                try:
                    await bot.send_photo(chat_id, FSInputFile(path), caption=caption)
                    sent = True
                except TelegramBadRequest:
                    sent = False
            if not sent:
                await bot.send_document(chat_id, FSInputFile(path), caption=caption)
        await db.record(uid, url, name, "direct")
        return True
    except TooBigError:
        await safe_edit(status, t(lang, "err_toobig", limit=limit_text(cfg)))
    except DownloadError as e:
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
    except Exception as e:  # noqa
        log.exception("direct download failed")
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e)[:200])))
    finally:
        ACTIVE[uid] = max(0, ACTIVE.get(uid, 1) - 1)
        shutil.rmtree(outdir, ignore_errors=True)
    return False


async def send_gallery(bot: Bot, cfg: Config, chat_id: int, files: list) -> None:
    imgs = [
        f for f in files
        if os.path.splitext(f)[1].lower() in IMG_EXTS and os.path.getsize(f) <= MAX_PHOTO_BYTES
    ]
    others = [f for f in files if f not in imgs]
    for i in range(0, len(imgs), 10):
        chunk = imgs[i:i + 10]
        try:
            if len(chunk) == 1:
                await bot.send_photo(chat_id, FSInputFile(chunk[0]))
            else:
                await bot.send_media_group(
                    chat_id, [InputMediaPhoto(media=FSInputFile(p)) for p in chunk]
                )
        except TelegramBadRequest:
            for p in chunk:  # أبعاد غير مدعومة كصورة → ابعتها كملف
                await bot.send_document(chat_id, FSInputFile(p))
    for p in others:
        if os.path.getsize(p) > cfg.max_upload_bytes:
            continue
        ext = os.path.splitext(p)[1].lower()
        if ext in VID_EXTS:
            await bot.send_video(chat_id, FSInputFile(p), supports_streaming=True)
        elif ext == ".gif":
            await bot.send_animation(chat_id, FSInputFile(p))
        else:
            await bot.send_document(chat_id, FSInputFile(p))


async def try_gallery(
    bot: Bot, cfg: Config, db: DB, chat_id: int, status: Message,
    uid: int, lang: str, url: str,
) -> bool:
    """بديل لـ yt-dlp: صور/ألبومات انستجرام وبنترست وتويتر وغيرها عبر gallery-dl."""
    if not GALLERY_OK or not await quota_ok(db, cfg, uid):
        return False
    await safe_edit(status, t(lang, "gallery_try"))
    files, outdir = await fetch_gallery(url, cfg)
    if not files:
        return False
    try:
        await safe_edit(status, t(lang, "uploading"))
        await send_gallery(bot, cfg, chat_id, files)
        await db.record(uid, url, "gallery", "gallery")
        try:
            await status.delete()
        except Exception:  # noqa
            pass
        return True
    except Exception:  # noqa
        log.exception("gallery send failed")
        return False
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


# ------------------------------------------------------------- main flow
def resolve_pref(pref: str, info: MediaInfo, cfg: Config):
    if pref == "audio" or not info.has_video:
        return "a", "mp3_192"
    if pref == "720":
        return "v", pick_fit(info, cfg, 720)
    if pref == "480":
        return "v", pick_fit(info, cfg, 480)
    return "v", "auto"


async def process_url(
    message: Message, url: str, cfg: Config, db: DB, bot: Bot,
    user: Optional[User] = None, status: Optional[Message] = None,
) -> None:
    u = user or message.from_user
    usr = await precheck(message, u, cfg, db, bot)
    if not usr:
        return
    lang = usr["lang"]
    PENDING.pop(u.id, None)
    if ACTIVE.get(u.id, 0) >= cfg.max_user_jobs:
        await message.answer(t(lang, "busy"))
        return
    if not await is_public_url(url):
        if status:
            await safe_edit(status, t(lang, "invalid_url"))
        else:
            await message.answer(t(lang, "invalid_url"))
        return

    if is_direct_url(url):
        if status:
            await safe_edit(status, t(lang, "starting"))
        else:
            status = await message.answer(t(lang, "starting"))
        if await run_direct(bot, cfg, db, message.chat.id, status, u.id, lang, url):
            try:
                await status.delete()
            except Exception:  # noqa
                pass
        return

    if status:
        await safe_edit(status, t(lang, "analyzing"))
    else:
        status = await message.answer(t(lang, "analyzing"))
    try:
        info = await extract_info(url, cfg)
    except DownloadError as e:
        if await try_gallery(bot, cfg, db, message.chat.id, status, u.id, lang, url):
            return
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
        return
    except Exception as e:  # noqa
        log.exception("extract failed")
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e)[:200])))
        return

    sid = secrets.token_urlsafe(5)
    SESSIONS[sid] = {"uid": u.id, "info": info, "ts": time.time()}

    if info.playlist:
        text, kb = build_playlist_card(info, sid, lang)
        await safe_edit(status, text, kb)
        return
    if info.is_live:
        await safe_edit(status, t(lang, "err_live"))
        return
    if cfg.max_duration and info.duration and info.duration > cfg.max_duration:
        await safe_edit(status, t(lang, "err_long", limit=fmt_duration(cfg.max_duration, lang)))
        return

    if usr["pref"] != "ask":
        kind, q = resolve_pref(usr["pref"], info, cfg)
        ok = await run_download(bot, cfg, db, message.chat.id, status, u.id, lang, info, kind, q)
        SESSIONS.pop(sid, None)
        if ok:
            try:
                await status.delete()
            except Exception:  # noqa
                pass
        return

    text, kb = build_card(info, sid, lang, cfg)
    await safe_edit(status, text, kb)


async def do_search(
    message: Message, query: str, cfg: Config, db: DB, bot: Bot, user: Optional[User] = None
) -> None:
    u = user or message.from_user
    usr = await precheck(message, u, cfg, db, bot)
    if not usr:
        return
    lang = usr["lang"]
    PENDING.pop(u.id, None)
    status = await message.answer(t(lang, "searching"))
    try:
        results = await search_youtube(query, cfg)
    except DownloadError as e:
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
        return
    if not results:
        await safe_edit(status, t(lang, "no_results"))
        return
    sid = secrets.token_urlsafe(5)
    SESSIONS[sid] = {"uid": u.id, "results": results, "ts": time.time()}
    b = InlineKeyboardBuilder()
    for i, r in enumerate(results):
        dur = fmt_duration(r["duration"], lang)
        label = "🎵 " + r["title"][:48] + (f" · {dur}" if dur else "")
        b.button(text=label, callback_data=f"s:{sid}:{i}")
    b.button(text=t(lang, "btn_cancel"), callback_data=f"x:{sid}")
    b.adjust(1)
    await safe_edit(
        status, t(lang, "search_title", q=html.escape(query[:60])), b.as_markup()
    )


# ---------------------------------------------------------------- commands
@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, db: DB, cfg: Config, bot: Bot):
    u = message.from_user
    args = (command.args or "").strip()
    ref = 0
    if args.startswith("ref_") and args[4:].isdigit():
        ref = int(args[4:])
    if ref == u.id:
        ref = 0
    user = await db.ensure_user(u.id, u.full_name, u.language_code, referrer=ref)
    lang = user["lang"]

    if user["new"] and ref and cfg.ref_bonus_days and await db.user_exists(ref):
        await db.set_premium(ref, cfg.ref_bonus_days)
        try:
            rlang = (await db.ensure_user(ref, "", None))["lang"]
            await bot.send_message(
                ref,
                t(rlang, "ref_bonus", name=html.escape(u.first_name or ""), days=cfg.ref_bonus_days),
            )
        except Exception:  # noqa
            pass

    if args.startswith("yt_") and YT_ID_RE.match(args[3:]):
        await process_url(message, f"https://www.youtube.com/watch?v={args[3:]}", cfg, db, bot)
        return
    await message.answer(t(lang, "start", name=html.escape(u.first_name or "")))


@router.message(Command("help"))
async def cmd_help(message: Message, db: DB, cfg: Config):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    await message.answer(t(user["lang"], "help", limit=limit_text(cfg), links=cfg.max_links))


@router.message(Command("settings"))
async def cmd_settings(message: Message, db: DB):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    await message.answer(t(user["lang"], "settings"), reply_markup=settings_kb(user))


@router.message(Command("me"))
async def cmd_me(message: Message, db: DB, cfg: Config):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    info = await db.user_info(u.id)
    today = await db.usage_today(u.id)
    if info["premium_until"] > time.time():
        premium = "💎 " + time.strftime("%Y-%m-%d", time.localtime(info["premium_until"]))
    else:
        premium = t(lang, "no")
    await message.answer(
        t(
            lang, "me",
            total=info["downloads"], today=today,
            limit=cfg.daily_limit or "∞", premium=premium,
        )
    )


@router.message(Command("history"))
async def cmd_history(message: Message, db: DB):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    rows = await db.get_history(u.id, 8)
    if not rows:
        await message.answer(t(lang, "history_empty"))
        return
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text="🔁 " + (r["title"] or r["url"])[:52], callback_data=f"h:{r['id']}")
    b.adjust(1)
    await message.answer(t(lang, "history_title"), reply_markup=b.as_markup())


@router.message(Command("search"))
async def cmd_search(message: Message, command: CommandObject, cfg: Config, db: DB, bot: Bot):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    q = (command.args or "").strip()
    if len(q) < 2:
        await message.answer(t(user["lang"], "search_usage"))
        return
    await do_search(message, q[:100], cfg, db, bot)


@router.message(Command("dl"))
async def cmd_dl(message: Message, command: CommandObject, db: DB, cfg: Config, bot: Bot):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    src = command.args or ""
    if not extract_url(src) and message.reply_to_message:
        src = message.reply_to_message.text or message.reply_to_message.caption or ""
    url = extract_url(src)
    if not url:
        await message.answer(t(user["lang"], "dl_usage"))
        return
    await process_url(message, url, cfg, db, bot)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, db: DB):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    PENDING.pop(u.id, None)
    await message.answer(t(user["lang"], "cancelled"))


@router.message(Command("stop"))
async def cmd_stop(message: Message, db: DB):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    if u.id in PLAYLISTS:
        STOP.add(u.id)
    await message.answer(t(user["lang"], "cancelled"))


# --------------------------------------------------------------- callbacks
@router.callback_query(F.data == "chk")
async def cb_check(cb: CallbackQuery, bot: Bot, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    if await check_sub(bot, u.id, cfg):
        await cb.answer("✅")
        try:
            await cb.message.delete()
        except Exception:  # noqa
            pass
    else:
        await cb.answer(t(user["lang"], "not_joined"), show_alert=True)


@router.callback_query(F.data.startswith("set:"))
async def cb_settings(cb: CallbackQuery, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    parts = cb.data.split(":")
    if len(parts) == 3:
        _, what, val = parts
        if what == "lang" and val in ("ar", "en"):
            await db.set_lang(u.id, val)
            user["lang"] = val
        elif what == "pref" and val in ("ask", "best", "720", "480", "audio"):
            await db.set_pref(u.id, val)
            user["pref"] = val
        elif what == "big" and val in ("split", "compress"):
            await db.set_big(u.id, val)
            user["big"] = val
        elif what == "doc" and val in ("0", "1"):
            await db.set_doc(u.id, val == "1")
            user["doc"] = val == "1"
    await cb.answer(t(user["lang"], "saved"))
    await safe_edit(cb.message, t(user["lang"], "settings"), settings_kb(user))


@router.callback_query(F.data.startswith("x:"))
async def cb_cancel(cb: CallbackQuery):
    SESSIONS.pop(cb.data.split(":", 1)[1], None)
    await cb.answer()
    try:
        await cb.message.delete()
    except Exception:  # noqa
        pass


@router.callback_query(F.data.startswith("s:"))
async def cb_search_pick(cb: CallbackQuery, bot: Bot, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    try:
        _, sid, idx = cb.data.split(":")
        idx = int(idx)
    except ValueError:
        await cb.answer(t(lang, "unknown_kind"), show_alert=True)
        return
    s, err = get_session(cb, sid, lang)
    results = (s or {}).get("results") or []
    if err or idx >= len(results):
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    await cb.answer()
    SESSIONS.pop(sid, None)
    await process_url(cb.message, results[idx]["url"], cfg, db, bot, user=u, status=cb.message)


@router.callback_query(F.data.startswith("h:"))
async def cb_history(cb: CallbackQuery, bot: Bot, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    try:
        hid = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        await cb.answer()
        return
    item = await db.get_history_item(u.id, hid)
    if not item:
        await cb.answer(t(user["lang"], "expired"), show_alert=True)
        return
    await cb.answer()
    await process_url(cb.message, item["url"], cfg, db, bot, user=u)


@router.callback_query(F.data.startswith("dl:"))
async def cb_download(cb: CallbackQuery, bot: Bot, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    if user["banned"]:
        await cb.answer()
        return
    try:
        _, sid, kind, q = cb.data.split(":", 3)
    except ValueError:
        await cb.answer(t(lang, "unknown_kind"), show_alert=True)
        return

    s, err = get_session(cb, sid, lang)
    info: Optional[MediaInfo] = (s or {}).get("info")
    if err or info is None:
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    if ACTIVE.get(u.id, 0) >= cfg.max_user_jobs:
        await cb.answer(t(lang, "busy"), show_alert=True)
        return
    valid = (
        (kind == "v" and (q == "auto" or q.isdigit()))
        or (kind == "a" and q in AUDIO_FORMATS)
        or (kind in ("n", "g", "t") and q == "0")
    )
    if not valid:
        await cb.answer(t(lang, "unknown_kind"), show_alert=True)
        return

    await cb.answer()
    status = cb.message

    if kind == "t":
        if not info.thumbnail:
            await cb.message.answer(t(lang, "no_thumb"))
            return
        try:
            await bot.send_photo(status.chat.id, info.thumbnail, caption=html.escape(info.title[:200]))
        except Exception:  # noqa
            await cb.message.answer(t(lang, "no_thumb"))
        return

    ok = await run_download(bot, cfg, db, status.chat.id, status, u.id, lang, info, kind, q)
    if ok:
        # رجّع الكارت عشان المستخدم يقدر ينزّل صيغة تانية
        text, kb = build_card(info, sid, lang, cfg)
        await safe_edit(status, text, kb)


@router.callback_query(F.data.startswith("sbm:"))
async def cb_subs_menu(cb: CallbackQuery, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    sid = cb.data.split(":", 1)[1]
    s, err = get_session(cb, sid, lang)
    info = (s or {}).get("info")
    if err or info is None or not info.subs:
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    await cb.answer()
    text, kb = build_subs_menu(info, sid, lang)
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data.startswith("bk:"))
async def cb_back(cb: CallbackQuery, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    sid = cb.data.split(":", 1)[1]
    s, err = get_session(cb, sid, lang)
    info = (s or {}).get("info")
    if err or info is None:
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    await cb.answer()
    text, kb = build_card(info, sid, lang, cfg)
    await safe_edit(cb.message, text, kb)


@router.callback_query(F.data.startswith("sb:"))
async def cb_subtitle(cb: CallbackQuery, bot: Bot, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    try:
        _, sid, idx = cb.data.split(":")
        idx = int(idx)
    except ValueError:
        await cb.answer(t(lang, "unknown_kind"), show_alert=True)
        return
    s, err = get_session(cb, sid, lang)
    info = (s or {}).get("info")
    if err or info is None or idx >= len(info.subs):
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    await cb.answer()
    sub = info.subs[idx]
    status = await cb.message.answer(t(lang, "subs_sending"))
    outdir = None
    try:
        path, outdir = await download_subtitle(info.url, sub["code"], sub["auto"], cfg)
        ext = os.path.splitext(path)[1] or ".srt"
        fname = f"{safe_name(info.title)}.{sub['code']}{ext}"
        await bot.send_document(
            cb.message.chat.id,
            FSInputFile(path, filename=fname),
            caption=f"📝 {html.escape(info.title[:150])}  [{sub['code']}]",
        )
        await status.delete()
    except DownloadError as e:
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
    except Exception as e:  # noqa
        log.exception("subtitle failed")
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e)[:200])))
    finally:
        if outdir:
            shutil.rmtree(outdir, ignore_errors=True)


@router.callback_query(F.data.startswith("cl:"))
async def cb_clip(cb: CallbackQuery, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    sid = cb.data.split(":", 1)[1]
    s, err = get_session(cb, sid, lang)
    info = (s or {}).get("info")
    if err or info is None:
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    await cb.answer()
    PENDING[u.id] = {"sid": sid, "ts": time.time()}
    await cb.message.answer(t(lang, "clip_prompt", max=fmt_duration(cfg.max_clip, lang)))


async def handle_clip_text(
    message: Message, text: str, pend: dict, cfg: Config, db: DB, bot: Bot
) -> None:
    u = message.from_user
    usr = await precheck(message, u, cfg, db, bot)
    if not usr:
        return
    lang = usr["lang"]
    m = CLIP_RE.match(text)
    if not m:
        await message.answer(t(lang, "clip_invalid"))
        return
    s = SESSIONS.get(pend["sid"])
    info: Optional[MediaInfo] = (s or {}).get("info")
    if not s or info is None or s["uid"] != u.id:
        PENDING.pop(u.id, None)
        await message.answer(t(lang, "expired"))
        return
    start, end = parse_ts(m.group(1)), parse_ts(m.group(2))
    if info.duration and end > info.duration:
        end = info.duration
    if end <= start:
        await message.answer(t(lang, "clip_invalid"))
        return
    if end - start > cfg.max_clip:
        await message.answer(t(lang, "clip_toolong", max=fmt_duration(cfg.max_clip, lang)))
        return
    if ACTIVE.get(u.id, 0) >= cfg.max_user_jobs:
        await message.answer(t(lang, "busy"))
        return

    PENDING.pop(u.id, None)
    if m.group(3) or not info.has_video:
        kind, q = "a", "mp3_192"
    else:
        hs = [h for h in info.heights if h <= 1080]
        kind, q = "v", (str(max(hs)) if hs else "best")
    status = await message.answer(t(lang, "starting"))
    ok = await run_download(
        bot, cfg, db, message.chat.id, status, u.id, lang, info, kind, q, clip=(start, end)
    )
    if ok:
        try:
            await status.delete()
        except Exception:  # noqa
            pass


@router.callback_query(F.data.startswith("pl:"))
async def cb_playlist(cb: CallbackQuery, bot: Bot, cfg: Config, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    if user["banned"]:
        await cb.answer()
        return
    try:
        _, sid, kind = cb.data.split(":")
    except ValueError:
        await cb.answer(t(lang, "unknown_kind"), show_alert=True)
        return
    s, err = get_session(cb, sid, lang)
    info: Optional[MediaInfo] = (s or {}).get("info")
    if err or info is None or not info.playlist or kind not in ("v", "a"):
        await cb.answer(err or t(lang, "expired"), show_alert=True)
        return
    if u.id in PLAYLISTS:
        await cb.answer(t(lang, "pl_busy"), show_alert=True)
        return

    await cb.answer()
    status = cb.message
    PLAYLISTS.add(u.id)
    STOP.discard(u.id)
    total = len(info.playlist)
    ok_count = 0
    stopped = False
    try:
        for i, (purl, ptitle) in enumerate(info.playlist, 1):
            if u.id in STOP:
                stopped = True
                break
            if not await quota_ok(db, cfg, u.id):
                await safe_edit(status, t(lang, "err_quota", limit=cfg.daily_limit))
                return
            await safe_edit(
                status,
                t(lang, "pl_progress", i=i, n=total, title=html.escape((ptitle or purl)[:80])),
            )
            if not await is_public_url(purl):
                continue
            try:
                item = await extract_info(purl, cfg)
            except Exception:  # noqa
                continue
            if item.is_live or item.playlist:
                continue
            if cfg.max_duration and item.duration and item.duration > cfg.max_duration:
                continue
            k, q = ("v", "auto") if kind == "v" else ("a", "mp3_192")
            if await run_download(bot, cfg, db, status.chat.id, status, u.id, lang, item, k, q):
                ok_count += 1
        key = "pl_stopped" if stopped else "pl_done"
        await safe_edit(status, t(lang, key, ok=ok_count, n=total))
    except Exception as e:  # noqa
        log.exception("playlist failed")
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e)[:200])))
    finally:
        PLAYLISTS.discard(u.id)
        STOP.discard(u.id)
        SESSIONS.pop(sid, None)


# -------------------------------------------- user-sent media → MP3
@router.message(F.chat.type == "private", F.video | F.audio | F.voice | F.video_note | F.document)
async def on_media(message: Message, bot: Bot, cfg: Config, db: DB):
    media = message.video or message.audio or message.voice or message.video_note or message.document
    if message.document and not (message.document.mime_type or "").startswith(("video/", "audio/")):
        return
    u = message.from_user
    usr = await precheck(message, u, cfg, db, bot)
    if not usr:
        return
    lang = usr["lang"]
    if ACTIVE.get(u.id, 0) >= cfg.max_user_jobs:
        await message.answer(t(lang, "busy"))
        return
    if not await quota_ok(db, cfg, u.id):
        await message.answer(t(lang, "err_quota", limit=cfg.daily_limit))
        return

    status = await message.answer(t(lang, "converting"))
    outdir = os.path.join(cfg.download_dir, uuid.uuid4().hex)
    os.makedirs(outdir, exist_ok=True)
    ACTIVE[u.id] = ACTIVE.get(u.id, 0) + 1
    try:
        src = os.path.join(outdir, "src")
        try:
            await bot.download(media, destination=src, timeout=900)
        except TelegramBadRequest:
            await safe_edit(status, t(lang, "err_file20"))
            return
        dst = os.path.join(outdir, "audio.mp3")
        await convert_to_mp3(src, dst)
        title = getattr(media, "file_name", None) or getattr(media, "title", None) or "Audio"
        title = os.path.splitext(str(title))[0][:100] or "Audio"
        dur = int(await probe_duration(dst)) or None
        info = MediaInfo(
            id="upload", extractor="upload", title=title, uploader="", duration=dur or 0,
            thumbnail="", url="", is_live=False, has_video=False, heights=[], sizes={},
        )
        res = DownloadResult(dst, outdir, None, None, dur)
        username = await get_username(bot)
        caption = f"🎵 {html.escape(title)}" + (f"\n\n🤖 @{username}" if username else "")
        await deliver(
            bot, cfg, db, message.chat.id, status, lang, "a", "mp3_192", res, caption,
            info, None, {"doc": False, "big": "split"}, None,
        )
        await db.record(u.id, "", title, "upload")
        try:
            await status.delete()
        except Exception:  # noqa
            pass
    except TooBigError:
        await safe_edit(status, t(lang, "err_toobig", limit=limit_text(cfg)))
    except DownloadError as e:
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
    except Exception as e:  # noqa
        log.exception("media convert failed")
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e)[:200])))
    finally:
        ACTIVE[u.id] = max(0, ACTIVE.get(u.id, 1) - 1)
        shutil.rmtree(outdir, ignore_errors=True)