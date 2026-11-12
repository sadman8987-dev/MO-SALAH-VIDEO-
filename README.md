# 🎬 Telegram Media Downloader Bot — النسخة الكاملة

بوت تليجرام لتحميل الفيديو والصوت والصور والملفات من أكتر من 1000 موقع باستخدام **yt-dlp** و**gallery-dl** و**aiogram 3**.

## ✨ المميزات
- تحميل الفيديو بجودات متعددة من 144p حتى 4K.
- تحميل الصوت بصيغ MP3 وM4A وOPUS وFLAC وWAV.
- تحميل الصور والألبومات والملفات المباشرة.
- قوائم تشغيل وترجمات وقص مقاطع وتحويل الملفات إلى MP3.
- كاش للتحميلات وشريط تقدم وطابور تحميلات.
- دعم Webhook وPolling وDocker.
- إعدادات عربية وإنجليزية وأوامر إدارة واشتراكات مميزة.

## 🚀 التشغيل باستخدام Docker
```bash
cp .env.example .env
# أضف BOT_TOKEN وADMINS إلى ملف .env
docker compose up -d --build
docker compose logs -f
```

## 🖥 التشغيل بدون Docker
يتطلب Python 3.10+ وffmpeg وdeno.
```bash
sudo apt install -y ffmpeg aria2
pip install -r requirements.txt
cp .env.example .env
python main.py
```

## ⚙️ ملفات المشروع
- `main.py`: نقطة تشغيل البوت.
- `requirements.txt`: مكتبات Python المطلوبة.
- `Dockerfile` و`docker-compose.yml`: إعداد Docker.

**مهم:** يلزم وجود مجلد `bot/` الذي يحتوي وحدات المشروع المستوردة في `main.py`، بالإضافة إلى ملف `.env.example`، قبل التشغيل. لا ترفع أسرار البوت أو ملف `.env` إلى GitHub.

## ⚖️ تنبيه
استخدم البوت فقط لتحميل المحتوى الذي تملك حق تحميله، والتزم بشروط المنصات وحقوق الملكية.
