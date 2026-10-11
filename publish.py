"""
publish.py — قناة مفردات فرنسية (Un mot par jour)
ينشر فيديو واحد قصير جدًا (5-8 ثوانٍ) في كل تشغيل: كلمة فرنسية واحدة مع صورة
ونطق، يتقدّم تسلسليًا عبر word_bank.json، ويُعيد الدورة من الصفر بعد اكتمالها.
"""
import os
import sys
import json
import time
import logging
import functools
from pathlib import Path

import requests
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from generate_video import build_word_video
from generate_word import get_next_word

BASE_DIR = Path(__file__).resolve().parent
PROGRESS_PATH = BASE_DIR / "progress.json"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
REQUIRED_ENV_VARS = ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN", "GROQ_API_KEY")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("french_vocab")


def check_required_env():
    missing = [k for k in REQUIRED_ENV_VARS if not os.environ.get(k)]
    if missing:
        sys.exit(f"❌ متغيرات بيئة ناقصة: {', '.join(missing)} — تحقق من GitHub Secrets.")


def notify_failure(message: str):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": f"🚨 مفردات فرنسية: {message}"},
            timeout=10,
        )
    except Exception as e:
        log.warning(f"تعذّر إرسال تنبيه Telegram: {e}")


def with_retries(max_attempts=3, base_delay=3.0):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if attempt < max_attempts:
                        delay = base_delay * (2 ** (attempt - 1))
                        log.warning(f"{func.__name__} فشلت (محاولة {attempt}/{max_attempts}): {e} — إعادة بعد {delay:.0f}s")
                        time.sleep(delay)
            raise last_error
        return wrapper
    return decorator


# --------------------------------------------------------------------------
# التقدّم (progress.json) — عدّاد بسيط لعدد الفيديوهات المنشورة فقط؛ منع
# التكرار نفسه يُدار عبر history.json داخل generate_word.py
# --------------------------------------------------------------------------
def load_progress() -> dict:
    if not PROGRESS_PATH.exists():
        return {"videos": 0}
    return json.loads(PROGRESS_PATH.read_text())


def save_progress(progress: dict):
    PROGRESS_PATH.write_text(json.dumps(progress, ensure_ascii=False, indent=2))


# --------------------------------------------------------------------------
# يوتيوب
# --------------------------------------------------------------------------
@with_retries(max_attempts=3, base_delay=5)
def upload_to_youtube(video_path: str, title: str, description: str) -> str:
    creds = Credentials(
        token=None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds)
    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["français", "vocabulaire", "apprendre le français", "shorts", "french"],
                "categoryId": "27",
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        },
        media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True),
    )
    response = None
    while response is None:
        _, response = request.next_chunk()
    return response["id"]


# --------------------------------------------------------------------------
# التشغيل الرئيسي
# --------------------------------------------------------------------------
def cleanup(*paths):
    for p in paths:
        if p and os.path.exists(p):
            os.remove(p)


def main():
    check_required_env()
    log.info("🚀 بدء تشغيل قناة المفردات الفرنسية...")

    progress = load_progress()
    video_path = str(BASE_DIR / "word_video.mp4")
    entry = None

    try:
        entry = get_next_word()
        log.info(f"🎬 بناء فيديو الكلمة رقم {progress['videos'] + 1}: {entry['word']} ({entry['category']})")
        build_word_video(entry, video_path)

        title = f"{entry['word']} — Apprendre le français | {entry['category']}"
        description = (
            f"Aujourd'hui : {entry['word']} ({entry['category']})\n\n"
            "Un mot de français par jour, avec sa prononciation. 🇫🇷\n"
            "🔔 Abonnez-vous pour apprendre un nouveau mot chaque jour !"
        )
        video_id = upload_to_youtube(video_path, title, description)
        log.info(f"✅ تم النشر: https://youtu.be/{video_id}")

        progress["videos"] += 1
        save_progress(progress)

    except Exception as e:
        word_hint = entry["word"] if entry else "(لم تُولَّد كلمة بعد)"
        log.error(f"❌ خطأ أوقف التشغيل: {e}")
        notify_failure(f"فشل نشر الكلمة '{word_hint}': {e}")
        raise
    finally:
        cleanup(video_path)


if __name__ == "__main__":
    main()
