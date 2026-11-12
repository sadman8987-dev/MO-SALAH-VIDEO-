"""إشعارات الفيديوهات الجديدة للقنوات المشترك فيها المستخدمين."""
import asyncio
import html
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Config
from .db import DB
from .downloader import DownloadError, latest_entries
from .texts import t

log = logging.getLogger(__name__)


async def check_feeds(bot: Bot, cfg: Config, db: DB) -> None:
    subs = await db.all_subs()
    by_url: dict = {}
    for s in subs:
        by_url.setdefault(s["url"], []).append(s)

    for url, rows in by_url.items():
        try:
            feed_title, entries = await latest_entries(url, cfg, 5)
        except DownloadError as e:
            log.info("feed check failed for %s: %s", url, e)
            continue
        if not entries:
            continue
        ids = [e["id"] for e in entries]
        for s in rows:
            last = s["last_id"]
            if last in ids:
                new = entries[: ids.index(last)]
            elif last:
                new = entries[:1]  # القديم اتشال: ابعت الأحدث بس
            else:
                new = []
            if ids[0] != last:
                await db.update_sub_last(s["id"], ids[0])
            if not new:
                continue
            lang = (await db.ensure_user(s["uid"], "", None))["lang"]
            for e in reversed(new):  # الأقدم أولاً
                hid = await db.add_history(s["uid"], e["url"], e["title"])
                kb = InlineKeyboardBuilder()
                kb.button(text=t(lang, "btn_sub_dl"), callback_data=f"h:{hid}")
                try:
                    await bot.send_message(
                        s["uid"],
                        t(
                            lang, "sub_new",
                            feed=html.escape(feed_title or s["title"] or ""),
                            title=html.escape(e["title"]), url=e["url"],
                        ),
                        reply_markup=kb.as_markup(),
                    )
                except TelegramForbiddenError:
                    await db.delete_user_subs(s["uid"])  # المستخدم حظر البوت
                    break
                except Exception as ex:  # noqa
                    log.debug("notify failed: %s", ex)
                await asyncio.sleep(0.1)
        await asyncio.sleep(1)


async def feeds_loop(bot: Bot, cfg: Config, db: DB) -> None:
    await asyncio.sleep(60)
    while True:
        try:
            await check_feeds(bot, cfg, db)
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa
            log.exception("feeds loop error")
        await asyncio.sleep(cfg.sub_interval * 60)