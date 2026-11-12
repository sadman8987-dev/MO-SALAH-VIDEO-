import base64
import os
import shutil
import tempfile
from pathlib import Path

import yt_dlp
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI(title="YT Downloader")

COOKIES_PATH = "/tmp/cookies.txt"
ACCESS_KEY = os.environ.get("ACCESS_KEY")

_raw = os.environ.get("YT_COOKIES")
_b64 = os.environ.get("YT_COOKIES_B64")
if _b64:
    _raw = base64.b64decode(_b64).decode("utf-8")
if _raw:
    Path(COOKIES_PATH).write_text(_raw)

PAGE = """<!doctype html>
<html lang="ar" dir="rtl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تحميل فيديو</title>
<style>
body{font-family:system-ui,sans-serif;max-width:520px;margin:40px auto;padding:0 16px}
input,select,button{width:100%;padding:12px;margin:6px 0;font-size:16px;box-sizing:border-box}
button{background:#111;color:#fff;border:0;border-radius:8px;cursor:pointer}
</style></head><body>
<h2>تحميل فيديو</h2>
<form action="/download" method="get">
<input name="url" placeholder="رابط يوتيوب" required>
<select name="kind"><option value="video">فيديو MP4</option><option value="audio">صوت MP3</option></select>
<input name="key" placeholder="كلمة السر (لو متفعلة)" type="password">
<button type="submit">تحميل</button>
</form></body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return PAGE


@app.get("/health")
def health():
    return {"ok": True, "cookies": Path(COOKIES_PATH).exists()}


@app.get("/download")
def download(url: str, background: BackgroundTasks, kind: str = "video", key: str = ""):
    if ACCESS_KEY and key != ACCESS_KEY:
        raise HTTPException(status_code=401, detail="كلمة السر غلط")

    tmp = tempfile.mkdtemp()
    opts = {
        "outtmpl": f"{tmp}/%(title).80s.%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "restrictfilenames": True,
    }
    if Path(COOKIES_PATH).exists():
        opts["cookiefile"] = COOKIES_PATH

    if kind == "audio":
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}
        ]
    else:
        opts["format"] = "bv*[height<=720]+ba/b[height<=720]/b"
        opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(e)[:500])

    files = list(Path(tmp).iterdir())
    if not files:
        shutil.rmtree(tmp, ignore_errors=True)
        raise HTTPException(status_code=500, detail="مفيش ملف اتحمل")

    background.add_task(shutil.rmtree, tmp, True)
    return FileResponse(files[0], filename=files[0].name)
