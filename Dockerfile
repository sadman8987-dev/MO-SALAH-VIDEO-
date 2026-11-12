FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg aria2 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Deno مطلوب لـ yt-dlp لتشغيل بعض مصادر YouTube
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -U -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/downloads /app/logs

EXPOSE 8080
CMD ["python", "main.py"]
