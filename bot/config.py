import os
import secrets
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _bool(name: str, default: bool) -> bool:
    v = os.getenv(name, "").strip().lower()
    if not v:
        return default
    return v not in ("0", "false", "no", "off")


@dataclass(frozen=True)
class Config:
    token: str
    admins: frozenset
    api_url: str
    max_upload_mb: int
    max_concurrent: int
    max_user_jobs: int
    max_duration: int
    download_dir: str
    db_path: str
    force_channel: str
    cookies_file: str
    split_large: bool
    daily_limit: int
    max_playlist: int
    max_clip: int
    max_links: int
    group_auto: bool
    proxy: str
    use_aria2: bool
    webhook_url: str
    webhook_port: int
    webhook_secret: str
    premium_stars: int
    premium_days: int
    ref_bonus_days: int
    max_subs: int
    sub_interval: int
    log_dir: str

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


def load_config() -> Config:
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN غير موجود. انسخ .env.example إلى .env واكتب التوكن.")

    admins = frozenset(
        int(x)
        for x in os.getenv("ADMINS", "").replace(" ", "").split(",")
        if x.lstrip("-").isdigit()
    )
    api_url = os.getenv("LOCAL_API_URL", "").strip().rstrip("/")
    default_mb = 1900 if api_url else 49

    return Config(
        token=token,
        admins=admins,
        api_url=api_url,
        max_upload_mb=_int("MAX_UPLOAD_MB", default_mb),
        max_concurrent=max(1, _int("MAX_CONCURRENT", 4)),
        max_user_jobs=max(1, _int("MAX_USER_JOBS", 2)),
        max_duration=_int("MAX_DURATION", 10800),
        download_dir=os.getenv("DOWNLOAD_DIR", "downloads").strip() or "downloads",
        db_path=os.getenv("DB_PATH", "data/bot.db").strip() or "data/bot.db",
        force_channel=os.getenv("FORCE_CHANNEL", "").strip(),
        cookies_file=os.getenv("COOKIES_FILE", "cookies.txt").strip() or "cookies.txt",
        split_large=_bool("SPLIT_LARGE", True),
        daily_limit=max(0, _int("DAILY_LIMIT", 0)),
        max_playlist=max(1, _int("MAX_PLAYLIST", 25)),
        max_clip=max(5, _int("MAX_CLIP", 900)),
        max_links=max(1, _int("MAX_LINKS", 3)),
        group_auto=_bool("GROUP_AUTO", False),
        proxy=os.getenv("PROXY", "").strip(),
        use_aria2=_bool("USE_ARIA2", False),
        webhook_url=os.getenv("WEBHOOK_URL", "").strip().rstrip("/"),
        webhook_port=_int("WEBHOOK_PORT", 8080),
        webhook_secret=os.getenv("WEBHOOK_SECRET", "").strip() or secrets.token_hex(16),
        premium_stars=max(0, _int("PREMIUM_STARS", 0)),
        premium_days=max(1, _int("PREMIUM_DAYS", 30)),
        ref_bonus_days=max(0, _int("REF_BONUS_DAYS", 1)),
        max_subs=max(1, _int("MAX_SUBS", 5)),
        sub_interval=max(5, _int("SUB_INTERVAL", 30)),
        log_dir=os.getenv("LOG_DIR", "logs").strip() or "logs",
    )