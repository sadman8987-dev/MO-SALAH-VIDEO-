"""اشتراك القنوات، الدعوات، الدفع بنجوم تليجرام، والوضع Inline."""
import html
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery,
    InlineQueryResultArticle, InputTextMessageContent, LabeledPrice,
    Message, PreCheckoutQuery,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .common import extract_url, fmt_duration, get_username, precheck, safe_edit
from .config import Config
from .db import DB
from .downloader import (
    DownloadError, is_public_url, latest_entries, normalize_feed_url, search_youtube,
)
from .texts import t

log = logging.getLogger(__name__)
extras_router = Router()
YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


# ------------------------------------------------------------ اشتراكات
@extras_router.message(Command("subscribe"))
async def cmd_subscribe(message: Message, command: CommandObject, cfg: Config, db: DB, bot: Bot):
    u = message.from_user
    usr = await precheck(message, u, cfg, db, bot)
    if not usr:
        return
    lang = usr["lang"]
    url = extract_url(command.args or "")
    if not url:
        await message.answer(t(lang, "sub_usage"))
        return
    if not await is_public_url(url):
        await message.answer(t(lang, "invalid_url"))
        return
    limit = cfg.max_subs * (3 if (usr["premium"] or u.id in cfg.admins) else 1)
    if await db.count_subs(u.id) >= limit:
        await message.answer(t(lang, "sub_limit", limit=limit))
        return
    status = await message.answer(t(lang, "analyzing"))
    try:
        feed_title, entries = await latest_entries(url, cfg, 3)
    except DownloadError as e:
        await safe_edit(status, t(lang, "err_generic", reason=html.escape(str(e))))
        return
    if not entries:
        await safe_edit(status, t(lang, "sub_invalid"))
        return
    norm = normalize_feed_url(url)
    added = await db.add_sub(u.id, norm, feed_title or norm, entries[0]["id"])
    if added:
        await safe_edit(status, t(lang, "sub_added", title=html.escape(feed_title or norm)))
    else:
        await safe_edit(status, t(lang, "sub_exists"))


def _subs_kb(rows: list):
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text="🗑 " + (r["title"] or r["url"])[:50], callback_data=f"usub:{r['id']}")
    b.adjust(1)
    return b.as_markup()


@extras_router.message(Command("subscriptions"))
async def cmd_subscriptions(message: Message, db: DB):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    rows = await db.list_subs(u.id)
    if not rows:
        await message.answer(t(lang, "sub_none"))
        return
    await message.answer(t(lang, "sub_list_title"), reply_markup=_subs_kb(rows))


@extras_router.callback_query(F.data.startswith("usub:"))
async def cb_unsub(cb: CallbackQuery, db: DB):
    u = cb.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    try:
        sid = int(cb.data.split(":")[1])
    except (ValueError, IndexError):
        await cb.answer()
        return
    await db.del_sub(u.id, sid)
    await cb.answer(t(lang, "sub_removed"))
    rows = await db.list_subs(u.id)
    if rows:
        await safe_edit(cb.message, t(lang, "sub_list_title"), _subs_kb(rows))
    else:
        await safe_edit(cb.message, t(lang, "sub_none"))


# -------------------------------------------------------------- دعوات
@extras_router.message(Command("invite"))
async def cmd_invite(message: Message, db: DB, cfg: Config, bot: Bot):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    if not cfg.ref_bonus_days:
        await message.answer(t(lang, "invite_off"))
        return
    username = await get_username(bot)
    n = await db.count_referrals(u.id)
    await message.answer(
        t(lang, "invite", days=cfg.ref_bonus_days,
          link=f"https://t.me/{username}?start=ref_{u.id}", n=n)
    )


# ---------------------------------------------- دفع بنجوم تليجرام (XTR)
@extras_router.message(Command("buy"))
async def cmd_buy(message: Message, db: DB, cfg: Config, bot: Bot):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    lang = user["lang"]
    if not cfg.premium_stars:
        await message.answer(t(lang, "buy_off"))
        return
    await bot.send_invoice(
        chat_id=message.chat.id,
        title=t(lang, "buy_title"),
        description=t(lang, "buy_desc", days=cfg.premium_days),
        payload=f"premium_{cfg.premium_days}",
        currency="XTR",
        prices=[LabeledPrice(label="Premium", amount=cfg.premium_stars)],
        provider_token="",
    )


@extras_router.pre_checkout_query()
async def on_pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)


@extras_router.message(F.successful_payment)
async def on_payment(message: Message, db: DB, cfg: Config):
    u = message.from_user
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    payload = message.successful_payment.invoice_payload or ""
    days = cfg.premium_days
    if payload.startswith("premium_") and payload[8:].isdigit():
        days = min(int(payload[8:]), 365)
    await db.set_premium(u.id, days)
    log.info("premium purchased: uid=%s days=%s", u.id, days)
    await message.answer(t(user["lang"], "buy_ok", days=days))


# ----------------------------------------------------------- Inline mode
@extras_router.inline_query()
async def on_inline(q: InlineQuery, cfg: Config, bot: Bot):
    text = (q.query or "").strip()
    if len(text) < 2:
        await q.answer([], cache_time=1)
        return
    try:
        results = await search_youtube(text[:100], cfg, 10)
    except Exception:  # noqa
        await q.answer([], cache_time=5)
        return
    username = await get_username(bot)
    items = []
    for r in results:
        vid = r.get("id") or ""
        if not YT_ID_RE.match(vid):
            continue
        dur = fmt_duration(r.get("duration"))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(
                    text="⬇️ Download", url=f"https://t.me/{username}?start=yt_{vid}"
                )
            ]]
        )
        items.append(
            InlineQueryResultArticle(
                id=vid,
                title=r["title"][:100],
                description=dur or "YouTube",
                thumbnail_url=f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                input_message_content=InputTextMessageContent(
                    message_text=f"🎬 {html.escape(r['title'])}\n{r['url']}"
                ),
                reply_markup=kb,
            )
        )
    await q.answer(items, cache_time=300, is_personal=False)