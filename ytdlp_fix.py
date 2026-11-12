"""
ytdlp_fix.py
حل مشكلة: "Sign in to confirm you're not a bot" في يوتيوب على Railway.

الاستخدام في كود البوت:

    from ytdlp_fix import apply_fix
    import yt_dlp

    ydl_opts = apply_fix({
        "format": "bestvideo+bestaudio/best",
        "outtmpl": "downloads/%(title)s.%(ext)s",
    })
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

متغيرات البيئة في Railway (Variables):
    YT_COOKIES_B64  = محتوى ملف cookies.txt بعد تحويله base64   (الأفضل)
    YT_COOKIES      = أو محتوى cookies.txt كنص عادي
    YT_PROXY        = (اختياري) بروكسي سكني مثل http://user:pass@host:port
"""

import base64
import os
import tempfile

_COOKIES_PATH = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")


def _prepare_cookies():
    """يكتب ملف الكوكيز من متغير البيئة ويرجع مساره (أو None)."""
    b64 = os.getenv("YT_COOKIES_B64", "").strip()
    raw = os.getenv("YT_COOKIES", "").strip()

    content = None
    if b64:
        try:
            content = base64.b64decode(b64).decode("utf-8")
        except Exception:
            content = None
    elif raw:
        content = raw.replace("\\n", "\n")

    if content:
        with open(_COOKIES_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        return _COOKIES_PATH

    # دعم ملف cookies.txt موجود في مجلد المشروع
    if os.path.exists("cookies.txt"):
        return "cookies.txt"
    return None


def apply_fix(opts: dict | None = None) -> dict:
    """يضيف إعدادات تقلل حظر يوتيوب إلى خيارات yt-dlp."""
    opts = dict(opts or {})

    cookies = _prepare_cookies()
    if cookies:
        opts["cookiefile"] = cookies

    proxy = os.getenv("YT_PROXY", "").strip()
    if proxy:
        opts["proxy"] = proxy

    # عملاء يوتيوب البديلة (أقل عرضة لطلب تسجيل الدخول)
    extractor_args = opts.setdefault("extractor_args", {})
    youtube_args = extractor_args.setdefault("youtube", {})
    youtube_args.setdefault("player_client", ["tv", "web_safari", "mweb", "android"])

    opts.setdefault("retries", 5)
    opts.setdefault("fragment_retries", 5)
    opts.setdefault("socket_timeout", 30)
    opts.setdefault("noplaylist", True)
    opts.setdefault("geo_bypass", True)
    return opts
