# YT Downloader

موقع بسيط لتحميل فيديو/صوت باستخدام yt-dlp + FastAPI.

## متغيرات البيئة (Railway ← Variables)
- `YT_COOKIES` : محتوى ملف cookies.txt كله (صيغة Netscape)
- `YT_COOKIES_B64` : بديل لو النص المتعدد الأسطر عمل مشاكل (base64 للملف)
- `ACCESS_KEY` : اختياري، كلمة سر للموقع

## تشغيل محلي
```
pip install -r requirements.txt
uvicorn app:app --reload
```
