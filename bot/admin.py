"""أوامر الأدمن."""
import asyncio
import html
import logging
import os
import sys
import time

from aiogram import Bot, Router
from aiogram.exceptions import TelegramRetryAfter
from aiogram.filters import Command, CommandObject
from aiogram.types import FSInputFile, Message

from .common import ACTIVE, MAINT, admin_only, safe_edit
from .config import Config
from .db import DB

log = logging.getLogger(__name__)
admin_router = Router()


def _ytdlp_version() -> str:
    try:
        import yt_dlp

        return str(yt_dlp.version.__version__)
    except Exception:  # noqa
        return "?"


@admin_router.message(Command("stats"), admin_only)
async def cmd_stats(message: Message, db: DB):
    s = await db.stats()
    top = await db.top_platforms(5)
    top_txt = "\n".join(f"  • {html.escape(p)}: {n}" for p, n in top) or "  —"
    await message.answer(
        f"📊 <b>Stats</b>\n👥 Users: {s['users']}  (💎 {s['premium']})\n"
        f"⬇️ Downloads: {s['downloads']}\n"
        f"📅 Today: {s['downloads_today']} by {s['active_today']} users\n"
        f"🔔 Subscriptions: {s['subs']}\n"
        f"🚫 Banned: {s['banned']}\n💾 Cached files: {s['cached']}\n"
        f"🔄 Active jobs: {sum(ACTIVE.values())}\n"
        f"🛠 Maintenance: {'ON' if MAINT['on'] else 'off'}\n"
        f"🎞 yt-dlp: {_ytdlp_version()}\n\n"
        f"🏆 <b>Top platforms</b>\n{top_txt}"
    )


@admin_router.message(Command("ban"), admin_only)
async def cmd_ban(message: Message, command: CommandObject, db: DB):
    if not command.args or not command.args.strip().lstrip("-").isdigit():
        await message.answer("/ban &lt;user_id&gt;")
        return
    await db.set_banned(int(command.args.strip()), True)
    await message.answer("🚫 banned")


@admin_router.message(Command("unban"), admin_only)
async def cmd_unban(message: Message, command: CommandObject, db: DB):
    if not command.args or not command.args.strip().lstrip("-").isdigit():
        await message.answer("/unban &lt;user_id&gt;")
        return
    await db.set_banned(int(command.args.strip()), False)
    await message.answer("✅ unbanned")


@admin_router.message(Command("premium"), admin_only)
async def cmd_premium(message: Message, command: CommandObject, db: DB):
    parts = (command.args or "").split()
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].lstrip("-").isdigit():
        await message.answer("/premium &lt;user_id&gt; &lt;days&gt;   (days=0 لإلغاء الاشتراك)")
        return
    until = await db.set_premium(int(parts[0]), int(parts[1]))
    if until:
        await message.answer("💎 Premium until " + time.strftime("%Y-%m-%d", time.localtime(until)))
    else:
        await message.answer("💎 Premium removed")


@admin_router.message(Command("maintenance"), admin_only)
async def cmd_maintenance(message: Message, command: CommandObject):
    arg = (command.args or "").strip().lower()
    if arg not in ("on", "off"):
        await message.answer(f"/maintenance on|off   (now: {'ON' if MAINT['on'] else 'off'})")
        return
    MAINT["on"] = arg == "on"
    await message.answer(f"🛠 Maintenance {'ON' if MAINT['on'] else 'OFF'}")


@admin_router.message(Command("broadcast"), admin_only)
async def cmd_broadcast(message: Message, command: CommandObject, bot: Bot, db: DB):
    src = message.reply_to_message
    text = command.args
    if not src and not text:
        await message.answer("/broadcast &lt;text&gt;  — أو رد على رسالة بـ /broadcast")
        return
    ids = await db.all_user_ids()
    status = await message.answer(f"📣 Sending to {len(ids)} users...")
    ok = fail = 0
    for uid in ids:
        for _attempt in range(2):
            try:
                if src:
                    await src.copy_to(uid)
                else:
                    await bot.send_message(uid, text)
                ok += 1
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except Exception:  # noqa
                fail += 1
                break
        await asyncio.sleep(0.05)
    await safe_edit(status, f"📣 Done. ✅ {ok}  ❌ {fail}")


@admin_router.message(Command("cookies"), admin_only)
async def cmd_cookies(message: Message, bot: Bot, cfg: Config):
    doc = message.document or (
        message.reply_to_message.document if message.reply_to_message else None
    )
    if not doc:
        await message.answer("↩️ Reply to a <b>cookies.txt</b> (Netscape format) file with /cookies")
        return
    tmp = cfg.cookies_file + ".tmp"
    try:
        await bot.download(doc, destination=tmp)
        with open(tmp, "rb") as f:
            head = f.read(4096)
        if b"\t" not in head and b"Netscape" not in head:
            os.remove(tmp)
            await message.answer("❌ Not a valid Netscape cookies file.")
            return
        os.replace(tmp, cfg.cookies_file)
        await message.answer("🍪 Cookies updated. Active immediately.")
    except Exception as e:  # noqa
        await message.answer(f"❌ Failed: {html.escape(str(e)[:200])}")


@admin_router.message(Command("delcookies"), admin_only)
async def cmd_delcookies(message: Message, cfg: Config):
    if os.path.isfile(cfg.cookies_file):
        os.remove(cfg.cookies_file)
        await message.answer("🍪 Cookies deleted.")
    else:
        await message.answer("No cookies file.")


@admin_router.message(Command("logs"), admin_only)
async def cmd_logs(message: Message, cfg: Config):
    path = os.path.join(cfg.log_dir, "bot.log")
    if not os.path.isfile(path):
        await message.answer("No log file.")
        return
    await message.answer_document(FSInputFile(path))


@admin_router.message(Command("backup"), admin_only)
async def cmd_backup(message: Message, cfg: Config, db: DB):
    await db.checkpoint()
    await message.answer_document(FSInputFile(cfg.db_path), caption="💾 Database backup")


@admin_router.message(Command("cleancache"), admin_only)
async def cmd_cleancache(message: Message, db: DB):
    n = await db.cache_clear()
    await message.answer(f"🧹 Cache cleared ({n})")


@admin_router.message(Command("update"), admin_only)
async def cmd_update(message: Message):
    st = await message.answer("⏳ Updating yt-dlp + gallery-dl...")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "pip", "install", "-U", "yt-dlp[default]", "gallery-dl",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
    )
    out, _ = await proc.communicate()
    tail = html.escape(out.decode(errors="ignore")[-400:])
    await safe_edit(st, f"✅ Done (exit {proc.returncode}). Use /restart to apply.\n<code>{tail}</code>")


@admin_router.message(Command("restart"), admin_only)
async def cmd_restart(message: Message):
    await message.answer("♻️ Restarting...")
    await asyncio.sleep(1)
    os._exit(0)  # docker/systemd restart policy يشغّله تاني