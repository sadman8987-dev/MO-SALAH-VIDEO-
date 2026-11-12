import asyncio
import logging
import os
import shutil
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault

from bot.admin import admin_router
from bot.common import gc_sessions
from bot.config import load_config
from bot.db import DB
from bot.extras import extras_router
from bot.fallback import fallback_router
from bot.feeds import feeds_loop
from bot.handlers import router

COMMANDS_EN = [
    ("start", "Start"),
    ("help", "Help & features"),
    ("search", "Search YouTube"),
    ("history", "My last downloads"),
    ("subscribe", "Get alerts for a channel"),
    ("subscriptions", "My subscriptions"),
    ("invite", "Invite friends (earn premium)"),
    ("buy", "Premium"),
    ("me", "My account"),
    ("settings", "Settings"),
    ("dl", "Download a link (groups)"),
    ("stop", "Stop playlist download"),
]
COMMANDS_AR = [
    ("start", "ابدأ"),
    ("help", "المساعدة والمميزات"),
    ("search", "بحث في يوتيوب"),
    ("history", "آخر تحميلاتي"),
    ("subscribe", "إشعارات قناة"),
    ("subscriptions", "اشتراكاتي"),
    ("invite", "ادعُ أصحابك واكسب مميز"),
    ("buy", "الاشتراك المميز"),
    ("me", "حسابي"),
    ("settings", "الإعدادات"),
    ("dl", "تحميل رابط (في الجروبات)"),
    ("stop", "إيقاف تحميل قائمة التشغيل"),
]


def setup_logging(log_dir: str) -> None:
    os.makedirs(log_dir, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    fh = RotatingFileHandler(
        os.path.join(log_dir, "bot.log"), maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    root.addHandler(sh)
    root.addHandler(fh)


async def main() -> None:
    cfg = load_config()
    setup_logging(cfg.log_dir)
    log = logging.getLogger("main")

    # نظّف مخلفات التحميلات القديمة
    shutil.rmtree(cfg.download_dir, ignore_errors=True)
    os.makedirs(cfg.download_dir, exist_ok=True)

    db = DB(cfg.db_path)
    await db.init()

    if cfg.api_url:
        session = AiohttpSession(
            api=TelegramAPIServer.from_base(cfg.api_url, is_local=True), timeout=3600
        )
    else:
        session = AiohttpSession(timeout=1800)

    bot = Bot(
        cfg.token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp["cfg"] = cfg
    dp["db"] = db
    # الترتيب مهم: الأدمن ← الإضافات ← الأساسي ← الرسائل العادية
    dp.include_router(admin_router)
    dp.include_router(extras_router)
    dp.include_router(router)
    dp.include_router(fallback_router)

    await bot.set_my_commands(
        [BotCommand(command=c, description=d) for c, d in COMMANDS_EN],
        scope=BotCommandScopeDefault(),
    )
    await bot.set_my_commands(
        [BotCommand(command=c, description=d) for c, d in COMMANDS_AR],
        scope=BotCommandScopeDefault(),
        language_code="ar",
    )

    tasks = [
        asyncio.create_task(gc_sessions()),
        asyncio.create_task(feeds_loop(bot, cfg, db)),
    ]
    me = await bot.me()
    log.info(
        "Bot started as @%s | upload limit: %s MB | mode: %s",
        me.username, cfg.max_upload_mb, "webhook" if cfg.webhook_url else "polling",
    )

    try:
        if cfg.webhook_url:
            from aiohttp import web
            from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

            await bot.set_webhook(
                cfg.webhook_url + "/webhook",
                secret_token=cfg.webhook_secret,
                drop_pending_updates=True,
                allowed_updates=dp.resolve_used_update_types(),
            )
            app = web.Application()

            async def health(_request):
                return web.json_response({"ok": True})

            app.router.add_get("/health", health)
            SimpleRequestHandler(
                dispatcher=dp, bot=bot, secret_token=cfg.webhook_secret
            ).register(app, path="/webhook")
            setup_application(app, dp, bot=bot)
            runner = web.AppRunner(app)
            await runner.setup()
            await web.TCPSite(runner, "0.0.0.0", cfg.webhook_port).start()
            log.info("Webhook listening on :%s", cfg.webhook_port)
            try:
                await asyncio.Event().wait()
            finally:
                await runner.cleanup()
        else:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        for task in tasks:
            task.cancel()
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
