import asyncio
import glob
import importlib.util
import ipaddress
import logging
import math
import os
import re
import shutil
import socket
import sys
import uuid
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import unquote, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError as YDLError
from yt_dlp.utils import download_range_func

from .config import Config

log = logging.getLogger(__name__)

URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
STD_HEIGHTS = (144, 240, 360, 480, 720, 1080, 1440, 2160)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

GALLERY_OK = importlib.util.find_spec("gallery_dl") is not None

# صيغ الصوت: المفتاح -> (codec, quality)
AUDIO_FORMATS = {
    "mp3_128": ("mp3", "128"),
    "mp3_192": ("mp3", "192"),
    "mp3_320": ("mp3", "320"),
    "m4a": ("m4a", "192"),
    "opus": ("opus", "160"),
    "flac": ("flac", None),
    "wav": ("wav", None),
    "voice": ("opus", "64"),
}

IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VID_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}
GALLERY_EXTS = IMG_EXTS | VID_EXTS | {".gif"}
# ملفات بتتحمل مباشرة (مش ميديا بيفهمها yt-dlp)
DIRECT_EXTS = {
    ".pdf", ".zip", ".rar", ".7z", ".tar", ".gz", ".apk", ".exe", ".iso", ".dmg",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".epub", ".mobi",
    ".csv", ".json", ".xml", ".jpg", ".jpeg", ".png", ".webp", ".gif",
}


class DownloadError(Exception):
    pass


class TooBigError(DownloadError):
    pass


@dataclass
class MediaInfo:
    id: str
    extractor: str
    title: str
    uploader: str
    duration: int
    thumbnail: str
    url: str
    is_live: bool
    has_video: bool
    heights: list
    sizes: dict
    subs: list = field(default_factory=list)       # [{"code":"en","auto":False}]
    playlist: list = field(default_factory=list)   # [(url, title)]


@dataclass
class DownloadResult:
    path: str
    outdir: str
    width: Optional[int]
    height: Optional[int]
    duration: Optional[int]


def _clean_error(e: Exception) -> str:
    s = ANSI_RE.sub("", str(e)).strip().replace("ERROR: ", "")
    lines = [ln for ln in s.splitlines() if ln.strip()]
    return (lines[-1] if lines else "unknown error")[:300]


def _opts(cfg: Config) -> dict:
    o = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 20,
        "retries": 5,
        "fragment_retries": 5,
        "concurrent_fragment_downloads": 5,
        "http_chunk_size": 10 * 1024 * 1024,
        "geo_bypass": True,
        "ignoreerrors": False,
    }
    if cfg.cookies_file and os.path.isfile(cfg.cookies_file):
        o["cookiefile"] = cfg.cookies_file
    if cfg.proxy:
        o["proxy"] = cfg.proxy
    if cfg.use_aria2 and shutil.which("aria2c"):
        o["external_downloader"] = {"default": "aria2c"}
        o["external_downloader_args"] = {"aria2c": ["-x16", "-s16", "-k1M"]}
    return o


def _has(codec) -> bool:
    return codec not in (None, "none", "")


# ------------------------------------------------------------ safety
async def is_public_url(url: str) -> bool:
    """يرفض الروابط الداخلية (localhost / شبكات خاصة) لحماية السيرفر (SSRF)."""
    try:
        p = urlparse(url)
        host = p.hostname
        if p.scheme not in ("http", "https") or not host:
            return False
        port = p.port or (443 if p.scheme == "https" else 80)
        loop = asyncio.get_running_loop()
        infos = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        if not infos:
            return False
        for _fam, _t, _p, _c, sa in infos:
            if not ipaddress.ip_address(sa[0]).is_global:
                return False
        return True
    except Exception:  # noqa
        return False


def is_direct_url(url: str) -> bool:
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    return ext in DIRECT_EXTS


# ------------------------------------------------------------ extraction
def _extract_sync(url: str, cfg: Config, flat: bool = True) -> dict:
    opts = _opts(cfg)
    opts["skip_download"] = True
    if flat:
        opts["extract_flat"] = "in_playlist"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except YDLError as e:
        raise DownloadError(_clean_error(e))
    except Exception as e:  # noqa
        raise DownloadError(_clean_error(e))
    if not info:
        raise DownloadError("no media found")

    if info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        if not entries:
            raise DownloadError("no media found")
        if not flat:
            return entries[0]
        if len(entries) == 1:
            e = entries[0]
            eurl = e.get("url") or e.get("webpage_url")
            if isinstance(eurl, str) and eurl.startswith("http"):
                return _extract_sync(eurl, cfg, flat=False)
            return e
        info["entries"] = entries
    return info


def _build_subs(info: dict) -> list:
    subs = []
    manual = info.get("subtitles") or {}
    for code in list(manual.keys()):
        if code != "live_chat":
            subs.append({"code": code, "auto": False})
        if len(subs) >= 6:
            break
    auto = info.get("automatic_captions") or {}
    if auto:
        orig = [c for c in auto if str(c).endswith("-orig")]
        lang = info.get("language")
        pick = orig or ([lang] if lang and lang in auto else (["en"] if "en" in auto else []))
        for c in pick[:2]:
            if c not in manual:
                subs.append({"code": c, "auto": True})
    return subs


def _build_info(info: dict, url: str, max_pl: int) -> MediaInfo:
    if info.get("_type") == "playlist":
        pl = []
        for e in info.get("entries") or []:
            eu = e.get("url") or e.get("webpage_url") or ""
            if isinstance(eu, str) and eu.startswith("http"):
                pl.append((eu, str(e.get("title") or "")[:120]))
            if len(pl) >= max_pl:
                break
        if pl:
            return MediaInfo(
                id=str(info.get("id") or uuid.uuid4().hex[:10]),
                extractor=str(info.get("extractor_key") or "playlist"),
                title=str(info.get("title") or "Playlist")[:300],
                uploader=str(info.get("uploader") or info.get("channel") or "")[:100],
                duration=0, thumbnail="", url=url, is_live=False, has_video=True,
                heights=[], sizes={}, playlist=pl,
            )
        info = (info.get("entries") or [{}])[0]

    fmts = info.get("formats") or []
    vids = [f for f in fmts if _has(f.get("vcodec")) and f.get("height")]
    auds = [f for f in fmts if _has(f.get("acodec")) and not _has(f.get("vcodec"))]
    any_video = any(_has(f.get("vcodec")) for f in fmts)
    audio_only = bool(auds) and not any_video
    audio_size = max(
        [f.get("filesize") or f.get("filesize_approx") or 0 for f in auds] or [0]
    )

    heights, sizes = [], {}
    maxh = max([f["height"] for f in vids] or [0])
    for s in STD_HEIGHTS:
        if maxh < s * 0.9:
            break
        cands = [f for f in vids if f["height"] <= s * 1.05]
        if not cands:
            continue
        top = max(f["height"] for f in cands)
        if top < s * 0.9:
            continue
        best = None
        for f in cands:
            if f["height"] != top:
                continue
            sz = f.get("filesize") or f.get("filesize_approx")
            if sz:
                if not _has(f.get("acodec")):
                    sz += audio_size
                best = max(best or 0, sz)
        heights.append(s)
        sizes[s] = best

    return MediaInfo(
        id=str(info.get("id") or uuid.uuid4().hex[:10]),
        extractor=str(info.get("extractor_key") or info.get("extractor") or "web"),
        title=str(info.get("title") or "Media")[:300],
        uploader=str(info.get("uploader") or info.get("channel") or "")[:100],
        duration=int(info.get("duration") or 0),
        thumbnail=str(info.get("thumbnail") or ""),
        url=url,
        is_live=bool(info.get("is_live")),
        has_video=not audio_only,
        heights=heights,
        sizes=sizes,
        subs=_build_subs(info),
    )


async def extract_info(url: str, cfg: Config) -> MediaInfo:
    info = await asyncio.to_thread(_extract_sync, url, cfg)
    return _build_info(info, url, cfg.max_playlist)


# ---------------------------------------------------------------- search
def _search_sync(query: str, cfg: Config, n: int) -> list:
    opts = _opts(cfg)
    opts.update(extract_flat=True, skip_download=True)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{n}:{query}", download=False)
    except YDLError as e:
        raise DownloadError(_clean_error(e))
    except Exception as e:  # noqa
        raise DownloadError(_clean_error(e))
    out = []
    for e in (info or {}).get("entries") or []:
        if not e:
            continue
        vid = str(e.get("id") or "")
        url = e.get("url") or ""
        if not str(url).startswith("http"):
            url = f"https://www.youtube.com/watch?v={vid}" if vid else ""
        if not url:
            continue
        out.append(
            {
                "id": vid,
                "url": url,
                "title": str(e.get("title") or "?"),
                "duration": int(e.get("duration") or 0),
            }
        )
    return out


async def search_youtube(query: str, cfg: Config, n: int = 8) -> list:
    return await asyncio.to_thread(_search_sync, query, cfg, n)


# ------------------------------------------------------------- feeds
_YT_CHANNEL_RE = re.compile(
    r"^https?://(www\.|m\.)?youtube\.com/(@[^/?#]+|channel/[^/?#]+|c/[^/?#]+|user/[^/?#]+)/?$",
    re.I,
)


def normalize_feed_url(url: str) -> str:
    url = url.strip()
    if _YT_CHANNEL_RE.match(url):
        return url.rstrip("/") + "/videos"
    return url


def _latest_sync(url: str, cfg: Config, n: int):
    opts = _opts(cfg)
    opts.update(
        extract_flat="in_playlist", skip_download=True, playlistend=n, noplaylist=False
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except YDLError as e:
        raise DownloadError(_clean_error(e))
    except Exception as e:  # noqa
        raise DownloadError(_clean_error(e))
    if not info:
        raise DownloadError("no media found")
    raw = [e for e in (info.get("entries") or [info]) if e]
    entries = []
    for e in raw[:n]:
        eid = str(e.get("id") or "")
        eu = e.get("url") or e.get("webpage_url") or ""
        if not str(eu).startswith("http"):
            if eid and "youtube" in str(e.get("ie_key") or info.get("extractor_key") or "").lower():
                eu = f"https://www.youtube.com/watch?v={eid}"
            else:
                continue
        entries.append({"id": eid or eu, "url": eu, "title": str(e.get("title") or "?")[:200]})
    return str(info.get("title") or "")[:150], entries


async def latest_entries(url: str, cfg: Config, n: int = 5):
    """يرجع (عنوان القناة, [أحدث العناصر])."""
    return await asyncio.to_thread(_latest_sync, normalize_feed_url(url), cfg, n)


# -------------------------------------------------------------- download
def _download_sync(url, outdir, kind, q, cfg: Config, state: dict, clip=None):
    def hook(d):
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            if total:
                state["pct"] = min(99.0, done * 100.0 / total)
            state["speed"] = d.get("speed")
            state["eta"] = d.get("eta")
            state["stage"] = "downloading"
        elif d.get("status") == "finished":
            state["pct"] = 100.0
            state["stage"] = "processing"

    opts = _opts(cfg)
    opts.update(
        outtmpl=os.path.join(outdir, "media.%(ext)s"),
        progress_hooks=[hook],
        restrictfilenames=True,
        merge_output_format="mp4",
        overwrites=True,
    )
    if clip:
        opts["download_ranges"] = download_range_func(
            None, [(float(clip[0]), float(clip[1]))]
        )
        opts["force_keyframes_at_cuts"] = True

    if kind == "a":
        codec, qual = AUDIO_FORMATS.get(q, ("mp3", "192"))
        pp = {"key": "FFmpegExtractAudio", "preferredcodec": codec}
        if qual:
            pp["preferredquality"] = qual
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [pp, {"key": "FFmpegMetadata", "add_metadata": True}]
    else:
        cap = "" if q == "best" else f"[height<={int(q)}]"
        opts["format"] = (
            f"bv*{cap}[ext=mp4]+ba[ext=m4a]/b{cap}[ext=mp4]/"
            f"bv*{cap}+ba/b{cap}/b"
        )

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except YDLError as e:
        raise DownloadError(_clean_error(e))
    except Exception as e:  # noqa
        raise DownloadError(_clean_error(e))

    skip = (".part", ".ytdl", ".temp", ".jpg", ".jpeg", ".webp", ".png", ".json", ".vtt", ".srt")
    files = [
        os.path.join(outdir, f)
        for f in os.listdir(outdir)
        if not f.endswith(skip) and os.path.isfile(os.path.join(outdir, f))
    ]
    if not files:
        raise DownloadError("download failed: no output file")
    path = max(files, key=os.path.getsize)
    if info and info.get("_type") == "playlist":
        entries = [e for e in (info.get("entries") or []) if e]
        info = entries[0] if entries else {}
    info = info or {}
    return DownloadResult(
        path=path,
        outdir=outdir,
        width=info.get("width"),
        height=info.get("height"),
        duration=int(info["duration"]) if info.get("duration") else None,
    )


async def download_media(
    url: str, kind: str, q: str, cfg: Config, state: dict, clip=None
) -> DownloadResult:
    outdir = os.path.join(cfg.download_dir, uuid.uuid4().hex)
    os.makedirs(outdir, exist_ok=True)
    try:
        return await asyncio.to_thread(
            _download_sync, url, outdir, kind, q, cfg, state, clip
        )
    except BaseException:
        shutil.rmtree(outdir, ignore_errors=True)
        raise


# ----------------------------------------------------- direct file links
async def download_direct(url: str, outdir: str, cfg: Config, state: dict, hard_cap: int) -> str:
    import aiohttp  # جاي مع aiogram

    name = re.sub(r"[^\w.\-() ]+", "_", unquote(os.path.basename(urlparse(url).path)))[:100] or "file"
    path = os.path.join(outdir, name)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=20, sock_read=60)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MediaBot/1.0)"}
    kwargs = {"proxy": cfg.proxy} if cfg.proxy else {}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as s:
            async with s.get(url, allow_redirects=True, max_redirects=5, **kwargs) as r:
                if r.status != 200:
                    raise DownloadError(f"HTTP {r.status}")
                if not await is_public_url(str(r.url)):
                    raise DownloadError("blocked url")
                total = r.content_length or 0
                if total and total > hard_cap:
                    raise TooBigError(str(total))
                done = 0
                last_t = asyncio.get_running_loop().time()
                last_b = 0
                with open(path, "wb") as f:
                    async for chunk in r.content.iter_chunked(256 * 1024):
                        done += len(chunk)
                        if done > hard_cap:
                            raise TooBigError(str(done))
                        f.write(chunk)
                        now = asyncio.get_running_loop().time()
                        if now - last_t >= 1:
                            state["speed"] = (done - last_b) / (now - last_t)
                            last_t, last_b = now, done
                            if total:
                                state["pct"] = min(99.0, done * 100.0 / total)
                                if state["speed"]:
                                    state["eta"] = (total - done) / state["speed"]
    except DownloadError:
        raise
    except asyncio.TimeoutError:
        raise DownloadError("timeout")
    except Exception as e:  # noqa
        raise DownloadError(_clean_error(e))
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise DownloadError("empty file")
    return path


def split_file_raw(path: str, limit_bytes: int, max_parts: int = 20) -> list:
    """تقسيم ملف عادي لأجزاء name.001 name.002 ... (تتجمع بـ cat أو 7-Zip)."""
    size = os.path.getsize(path)
    n = math.ceil(size / limit_bytes)
    if n > max_parts:
        raise TooBigError("too many parts")
    parts = []
    with open(path, "rb") as src:
        for i in range(1, n + 1):
            part = f"{path}.{i:03d}"
            remaining = limit_bytes
            with open(part, "wb") as dst:
                while remaining > 0:
                    chunk = src.read(min(4 * 1024 * 1024, remaining))
                    if not chunk:
                        break
                    dst.write(chunk)
                    remaining -= len(chunk)
            parts.append(part)
    return parts


# --------------------------------------------------- gallery-dl (صور)
async def fetch_gallery(url: str, cfg: Config, max_files: int = 10):
    """تحميل صور/فيديوهات من مواقع بتتخطى yt-dlp (انستجرام، بنترست، تويتر...).
    يرجع (files, outdir) أو ([], '')."""
    if not GALLERY_OK:
        return [], ""
    outdir = os.path.join(cfg.download_dir, uuid.uuid4().hex)
    os.makedirs(outdir, exist_ok=True)
    cmd = [sys.executable, "-m", "gallery_dl", "-q", "-D", outdir, "--range", f"1-{max_files}"]
    if cfg.cookies_file and os.path.isfile(cfg.cookies_file):
        cmd += ["--cookies", cfg.cookies_file]
    if cfg.proxy:
        cmd += ["--proxy", cfg.proxy]
    cmd.append(url)
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=150)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
    except Exception as e:  # noqa
        log.warning("gallery-dl failed: %s", e)
    files = sorted(
        os.path.join(outdir, f)
        for f in os.listdir(outdir)
        if os.path.isfile(os.path.join(outdir, f))
        and os.path.splitext(f)[1].lower() in GALLERY_EXTS
    )
    if not files:
        shutil.rmtree(outdir, ignore_errors=True)
        return [], ""
    return files, outdir


# ------------------------------------------------------------- subtitles
def _subs_sync(url: str, outdir: str, code: str, auto: bool, cfg: Config) -> str:
    opts = _opts(cfg)
    opts.update(
        skip_download=True,
        outtmpl=os.path.join(outdir, "sub.%(ext)s"),
        writesubtitles=not auto,
        writeautomaticsub=auto,
        subtitleslangs=[code],
        subtitlesformat="srt/vtt/best",
        postprocessors=[{"key": "FFmpegSubtitlesConvertor", "format": "srt"}],
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
    except YDLError as e:
        raise DownloadError(_clean_error(e))
    except Exception as e:  # noqa
        raise DownloadError(_clean_error(e))
    files = glob.glob(os.path.join(outdir, "*.srt")) or glob.glob(os.path.join(outdir, "*.vtt"))
    if not files:
        raise DownloadError("subtitle not available")
    return files[0]


async def download_subtitle(url: str, code: str, auto: bool, cfg: Config):
    outdir = os.path.join(cfg.download_dir, uuid.uuid4().hex)
    os.makedirs(outdir, exist_ok=True)
    try:
        path = await asyncio.to_thread(_subs_sync, url, outdir, code, auto, cfg)
        return path, outdir
    except BaseException:
        shutil.rmtree(outdir, ignore_errors=True)
        raise


# ----------------------------------------------------- ffmpeg utilities
async def _run(*args):
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    out, err = await proc.communicate()
    return proc.returncode, out, err


async def probe_duration(path: str) -> float:
    rc, out, _ = await _run(
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    )
    try:
        return float(out.decode().strip())
    except ValueError:
        return 0.0


async def convert_to_mp3(src: str, dst: str, bitrate: str = "192k") -> None:
    rc, _, _ = await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", src,
        "-vn", "-map", "0:a:0", "-c:a", "libmp3lame", "-b:a", bitrate, dst,
    )
    if rc != 0 or not os.path.isfile(dst):
        raise DownloadError("conversion failed (no audio stream?)")


async def make_video_note(src: str, dst: str, seconds: int = 60) -> None:
    """فيديو دائري (Video Note): مربع 384px بحد أقصى 60 ثانية."""
    rc, _, _ = await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", str(seconds),
        "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", dst,
    )
    if rc != 0 or not os.path.isfile(dst):
        raise DownloadError("video note conversion failed")


async def make_gif(src: str, dst: str, seconds: int = 30) -> None:
    """GIF (mp4 صامت خفيف) بيظهر كـ animation في تليجرام."""
    rc, _, _ = await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", src, "-t", str(seconds), "-an",
        "-vf", "fps=15,scale='min(480,iw)':-2",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", dst,
    )
    if rc != 0 or not os.path.isfile(dst):
        raise DownloadError("gif conversion failed")


async def compress_video(src: str, dst: str, target_bytes: int, duration: float) -> None:
    """إعادة ترميز الفيديو عشان يدخل تحت الحد (بديل للتقسيم)."""
    audio_k = 96
    total_k = target_bytes * 8 / 1000 / max(duration, 1) * 0.90
    video_k = int(total_k - audio_k)
    if video_k < 120:
        raise TooBigError("too long to compress")
    rc, _, _ = await _run(
        "ffmpeg", "-y", "-loglevel", "error", "-i", src,
        "-vf", "scale='min(1280,iw)':-2",
        "-c:v", "libx264", "-preset", "veryfast",
        "-b:v", f"{video_k}k", "-maxrate", f"{int(video_k * 1.3)}k",
        "-bufsize", f"{video_k * 2}k", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", f"{audio_k}k", "-movflags", "+faststart", dst,
    )
    if rc != 0 or not os.path.isfile(dst):
        raise DownloadError("compression failed")


async def fetch_thumb(url: str, outdir: str, cfg: Config) -> Optional[str]:
    """ينزّل الصورة المصغرة ويصغّرها لتناسب حد تليجرام (320px / 200KB)."""
    if not url or not url.startswith("http"):
        return None
    try:
        import aiohttp

        raw = os.path.join(outdir, "thumb_raw")
        out = os.path.join(outdir, "thumb.jpg")
        kwargs = {"proxy": cfg.proxy} if cfg.proxy else {}
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)) as s:
            async with s.get(url, **kwargs) as r:
                if r.status != 200:
                    return None
                data = await r.read()
        if not data or len(data) > 10 * 1024 * 1024:
            return None
        with open(raw, "wb") as f:
            f.write(data)
        for qv in (4, 8, 15, 25):
            rc, _, _ = await _run(
                "ffmpeg", "-y", "-loglevel", "error", "-i", raw,
                "-vf", "scale='min(320,iw)':-2", "-frames:v", "1", "-q:v", str(qv), out,
            )
            if rc == 0 and os.path.isfile(out) and os.path.getsize(out) <= 200 * 1024:
                return out
    except Exception as e:  # noqa
        log.debug("thumb failed: %s", e)
    return None


async def split_media(path: str, limit_bytes: int, max_parts: int = 30) -> list:
    """يقسّم الملف لأجزاء قابلة للتشغيل (بدون إعادة ترميز) كل جزء <= limit_bytes."""
    size = os.path.getsize(path)
    dur = await probe_duration(path)
    if dur <= 0:
        raise DownloadError("cannot split this file")
    ext = os.path.splitext(path)[1]
    folder = os.path.dirname(path)
    pattern = os.path.join(folder, "part_%03d" + ext)

    for factor in (0.85, 0.65, 0.45, 0.3):
        parts = max(2, math.ceil(size / (limit_bytes * factor)))
        if parts > max_parts:
            raise TooBigError("too many parts")
        seg = max(1, math.ceil(dur / parts))
        for old in glob.glob(os.path.join(folder, "part_*")):
            os.remove(old)
        rc, _, _ = await _run(
            "ffmpeg", "-y", "-loglevel", "error", "-i", path,
            "-map", "0:v:0?", "-map", "0:a:0?", "-c", "copy",
            "-f", "segment", "-segment_time", str(seg),
            "-reset_timestamps", "1", pattern,
        )
        if rc != 0:
            raise DownloadError("splitting failed")
        files = sorted(glob.glob(os.path.join(folder, "part_*")))
        if files and all(0 < os.path.getsize(f) <= limit_bytes for f in files):
            return files
    raise TooBigError("cannot fit parts")


def pick_fit(info: MediaInfo, cfg: Config, cap: Optional[int] = None) -> str:
    """أفضل جودة فيديو مناسبة لحد الرفع (و اختياريا لا تتعدى cap)."""
    cands = [h for h in sorted(info.heights, reverse=True) if cap is None or h <= cap]
    if not cands:
        return "best"
    for h in cands:
        sz = info.sizes.get(h)
        if sz is None or sz <= cfg.max_upload_bytes:
            return str(h)
    return str(cands[-1])