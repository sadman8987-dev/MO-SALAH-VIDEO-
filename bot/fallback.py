"""آخر router: الرسائل النصية العادية (روابط / بحث / وقت القص) والجروبات."""
import time

from aiogram import Bot, F, Router
from aiogram.types import Message

from .common import PENDING, extract_url, extract_urls
from .config import Config
from .db import DB
from .handlers import do_search, handle_clip_text, process_url

fallback_router = Router()


@fallback_router.message(F.chat.type == "private", F.text)
async def on_text(message: Message, cfg: Config, db: DB, bot: Bot):
    text = (message.text or "").strip()
    if not text or text.startswith("/"):
        return
    u = message.from_user
    urls = extract_urls(text, cfg.max_links)
    if urls:
        for url in urls:
            await process_url(message, url, cfg, db, bot)
        return
    pend = PENDING.get(u.id)
    if pend and time.time() - pend["ts"] < 600:
        await handle_clip_text(message, text, pend, cfg, db, bot)
        return
    if len(text) < 2:
        return
    await do_search(message, text[:100], cfg, db, bot)


@fallback_router.message(F.chat.type.in_({"group", "supergroup"}), F.text)
async def on_group_text(message: Message, cfg: Config, db: DB, bot: Bot):
    """تحميل تلقائي للروابط في الجروبات (لو GROUP_AUTO=1)."""
    if not cfg.group_auto:
        return
    url = extract_url(message.text or "")
    if url:
        await process_url(message, url, cfg, db, bot)