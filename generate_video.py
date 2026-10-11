"""
generate_video.py — فيديو قصير جدًا (5-8 ثوانٍ): بطاقة الكلمة + نطقها بالفرنسية
مرتين (عادي ثم أبطأ قليلاً للتوضيح)، عبر edge-tts (مجاني تمامًا، بلا مفتاح API).
"""
import os
import asyncio
import subprocess

import edge_tts

from generate_image import generate_word_card

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEO_WIDTH, VIDEO_HEIGHT = 1080, 1920

TTS_VOICE = "fr-FR-DeniseNeural"   # صوت فرنسي نسائي واضح، مجاني عبر edge-tts
TTS_RATE_NORMAL = "+0%"
TTS_RATE_SLOW = "-25%"
SILENCE_BETWEEN = 0.5             # ثانية صمت بين النطقتين
TAIL_PADDING = 0.6                # ثانية إضافية بعد آخر نطق قبل نهاية الفيديو


async def _tts_to_file(text: str, rate: str, out_path: str):
    communicate = edge_tts.Communicate(text, TTS_VOICE, rate=rate)
    await communicate.save(out_path)


def _synthesize_pronunciation(word: str, out_path: str):
    """ينطق الكلمة مرتين (عادية ثم أبطأ) مع صمت قصير بينهما، في ملف صوتي واحد."""
    # نزيل أداة التعريف الملتصقة (l') من النطق الصوتي فقط عند الحاجة لاحقًا؛
    # هنا نُبقيها لأن نطق "l'ananas" ضمن الجملة صحيح لغويًا كما هو.
    normal_path = out_path.replace(".mp3", "_normal.mp3")
    slow_path = out_path.replace(".mp3", "_slow.mp3")

    asyncio.run(_tts_to_file(word, TTS_RATE_NORMAL, normal_path))
    asyncio.run(_tts_to_file(word, TTS_RATE_SLOW, slow_path))

    silence_path = out_path.replace(".mp3", "_silence.mp3")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi",
        "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(SILENCE_BETWEEN), "-q:a", "4", silence_path,
    ], check=True)

    concat_list = out_path.replace(".mp3", "_concat.txt")
    with open(concat_list, "w") as f:
        for p in (normal_path, silence_path, slow_path):
            f.write(f"file '{os.path.abspath(p)}'\n")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
        "-i", concat_list, "-c", "copy", out_path,
    ], check=True)

    for p in (normal_path, slow_path, silence_path, concat_list):
        if os.path.exists(p):
            os.remove(p)


def build_word_video(entry: dict, output_path: str) -> str:
    """entry: {"emoji": ..., "word": ..., "category": ...} من word_bank.json"""
    tmp_dir = os.path.dirname(output_path) or "."
    base_name = os.path.splitext(os.path.basename(output_path))[0]

    image_path = os.path.join(tmp_dir, f"{base_name}.png")
    audio_path = os.path.join(tmp_dir, f"{base_name}.mp3")

    generate_word_card(entry["emoji"], entry["word"], entry["category"], image_path)
    _synthesize_pronunciation(entry["word"], audio_path)

    # مدة الفيديو = مدة الصوت الفعلية + هامش بسيط في النهاية
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", audio_path],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    duration = float(probe) + TAIL_PADDING

    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-loop", "1", "-i", image_path,
        "-i", audio_path,
        "-t", f"{duration:.2f}",
        "-vf", f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT},format=yuv420p",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-shortest",
        output_path,
    ], check=True)

    for p in (image_path, audio_path):
        if os.path.exists(p):
            os.remove(p)

    return output_path


if __name__ == "__main__":
    from generate_word import get_next_word
    entry = get_next_word()
    build_word_video(entry, os.path.join(BASE_DIR, "test_video.mp4"))
    print("saved test_video.mp4 for:", entry["word"])
