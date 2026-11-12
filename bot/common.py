"""حالة مشتركة ودوال مساعدة بين كل الـ routers."""
import asyncio
import logging
import re
import time
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, User
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import Config
from .db import DB
from .downloader import URL_RE
from .texts import t

log = logging.getLogger(__name__)

SESSIONS: dict = {}     # sid -> {"uid", "ts", "info"?, "results"?}
ACTIVE: dict = {}       # uid -> عدد التحميلات الجارية
PLAYLISTS: set = set()  # uids عندهم قائمة تشغيل شغالة
STOP: set = set()       # uids طلبوا /stop
PENDING: dict = {}      # uid -> {"sid", "ts"} في انتظار وقت القص
MAINT = {"on": False}   # وضع الصيانة
SESSION_TTL = 3600

_sem: Optional[asyncio.Semaphore] = None
_username: Optional[str] = None


def get_sem(cfg: Config) -> asyncio.Semaphore:
    global _sem
    if _sem is None:
        _sem = asyncio.Semaphore(cfg.max_concurrent)
    return _sem


async def gc_sessions() -> None:
    while True:
        await asyncio.sleep(300)
        now = time.time()
        for k in [k for k, v in SESSIONS.items() if now - v["ts"] > SESSION_TTL]:
            SESSIONS.pop(k, None)
        for k in [k for k, v in PENDING.items() if now - v["ts"] > 600]:
            PENDING.pop(k, None)


# ------------------------------------------------------------- formatting
def human_size(n) -> str:
    if not n:
        return "—"
    n = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024
    return "—"


def fmt_duration(sec, lang: str = "en") -> str:
    if not sec:
        return ""
    sec = int(sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_ts(s: str) -> int:
    sec = 0
    for p in s.split(":"):
        sec = sec * 60 + int(p)
    return sec


def progress_bar(pct: float, width: int = 12) -> str:
    filled = int(width * max(0.0, min(100.0, pct)) / 100)
    return "▓" * filled + "░" * (width - filled)


def render_progress(lang: str, state: dict) -> str:
    if state.get("stage") == "processing":
        return t(lang, "processing")
    pct = state.get("pct") or 0.0
    speed = state.get("speed")
    eta = state.get("eta")
    return t(
        lang,
        "downloading",
        bar=progress_bar(pct),
        pct=f"{pct:.0f}",
        speed=(human_size(speed) + "/s") if speed else "—",
        eta=(fmt_duration(int(eta), lang) if eta else "—"),
    )


def safe_name(text: str) -> str:
    return re.sub(r'[\\/:*?"<>|\s]+', "_", text).strip("_")[:60] or "file"


def limit_text(cfg: Config) -> str:
    mb = cfg.max_upload_mb
    return f"{mb / 1024:.1f} GB" if mb >= 1024 else f"{mb} MB"


def extract_urls(text: str, limit: int = 1) -> list:
    out = []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(".,)]}،")
        if u and u not in out:
            out.append(u)
        if len(out) >= limit:
            break
    return out


def extract_url(text: str) -> Optional[str]:
    urls = extract_urls(text, 1)
    return urls[0] if urls else None


# --------------------------------------------------------------- telegram
async def safe_edit(msg: Message, text: str, markup=None) -> None:
    try:
        await msg.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        pass
    except Exception as e:  # noqa
        log.debug("edit failed: %s", e)


async def get_username(bot: Bot) -> str:
    global _username
    if _username is None:
        _username = (await bot.me()).username or ""
    return _username


async def check_sub(bot: Bot, uid: int, cfg: Config) -> bool:
    if not cfg.force_channel:
        return True
    try:
        m = await bot.get_chat_member(cfg.force_channel, uid)
        return m.status not in ("left", "kicked")
    except Exception as e:  # noqa
        log.warning("force-sub check failed: %s", e)
        return True


def join_kb(cfg: Config, lang: str):
    b = InlineKeyboardBuilder()
    b.button(
        text=t(lang, "btn_join"),
        url=f"https://t.me/{cfg.force_channel.lstrip('@')}",
    )
    b.button(text=t(lang, "btn_check"), callback_data="chk")
    b.adjust(1)
    return b.as_markup()


def admin_only(message: Message, cfg: Config) -> bool:
    return bool(message.from_user and message.from_user.id in cfg.admins)


async def precheck(message: Message, u: User, cfg: Config, db: DB, bot: Bot) -> Optional[dict]:
    """تحقق من الحظر والصيانة والاشتراك الإجباري. يرجع بيانات المستخدم أو None."""
    user = await db.ensure_user(u.id, u.full_name, u.language_code)
    if user["banned"]:
        return None
    if MAINT["on"] and u.id not in cfg.admins:
        await message.answer(t(user["lang"], "maintenance"))
        return None
    if not await check_sub(bot, u.id, cfg):
        await message.answer(t(user["lang"], "join"), reply_markup=join_kb(cfg, user["lang"]))
        return None
    return user


async def quota_ok(db: DB, cfg: Config, uid: int) -> bool:
    if not cfg.daily_limit or uid in cfg.admins:
        return True
    if await db.is_premium(uid):
        return True
    return await db.usage_today(uid) < cfg.daily_limit


def get_session(cb: CallbackQuery, sid: str, lang: str):
    """يرجع (session, error_text)."""
    s = SESSIONS.get(sid)
    if not s:
        return None, t(lang, "expired")
    if s["uid"] != cb.from_user.id:
        return None, t(lang, "not_yours")
    s["ts"] = time.time()
    return s, None