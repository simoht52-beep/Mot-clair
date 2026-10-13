"""
generate_word.py — يولّد كلمة فرنسية جديدة (اسم شائع لحيوان/مهنة/فاكهة/غرض/
لون/عنصر طبيعة) عبر Groq، بدل الاعتماد على قائمة ثابتة — مع سجل (history.json)
يخزّن نص الكلمات نفسها (وليس بصمات مشفَّرة فقط) لمنع التكرار بشكل فعّال، لأن
البرومبت يحتاج أن "يرى" الكلمات المستخدَمة فعليًا ليتجنّبها — بصمة مشفَّرة
وحدها تكفي للتحقق المحلي لكنها عديمة الفائدة كتلميح استبعاد لـ Groq نفسه.
هذا بالضبط ما كان يسبّب استنفاد كل المحاولات باقتراحات مكرَّرة سابقًا.
"""
import os
import json
from pathlib import Path

from groq import Groq

BASE_DIR = Path(__file__).resolve().parent
HISTORY_PATH = BASE_DIR / "history.json"
HISTORY_MAX_ENTRIES = 3000      # سقف يضمن ألا يكبر الملف بلا حدود
HISTORY_HINT_SIZE = 200         # كم كلمة من السجل تُعرض فعليًا على Groq كاستبعاد

GROQ_MODELS = ["openai/gpt-oss-120b", "allam-2-7b", "qwen/qwen3.8-27b"]
ALLOWED_CATEGORIES = ["Un animal", "Un métier", "Un fruit", "Un objet", "Une couleur", "La nature"]

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))


def _normalize(word: str) -> str:
    """توحيد شكل الكلمة للمقارنة (حالة الأحرف + المسافات) بدل تشفيرها بالكامل،
    لأننا نحتاج نص الكلمة نفسه لاحقًا كتلميح استبعاد، وليس بصمة غير قابلة للقراءة."""
    return word.strip().lower()


def load_history() -> list:
    if not HISTORY_PATH.exists():
        return []
    try:
        return json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_history(words: list):
    trimmed = words[-HISTORY_MAX_ENTRIES:]
    HISTORY_PATH.write_text(json.dumps(trimmed, ensure_ascii=False, indent=0), encoding="utf-8")


def _ask_groq(avoid_words: list[str]) -> dict | None:
    avoid_hint = (
        f"N'utilise AUCUN de ces mots déjà utilisés : {', '.join(avoid_words[-150:])}.\n"
        if avoid_words else ""
    )
    prompt = (
        "Tu choisis UN mot français simple et courant, utile pour apprendre le "
        "vocabulaire de base (un animal, un métier, un fruit, un objet du "
        "quotidien, une couleur, ou un élément de la nature).\n"
        f"{avoid_hint}"
        "Règles strictes :\n"
        "1) Le mot doit inclure son article défini correct et grammaticalement "
        "exact (le/la/les/l').\n"
        "2) La catégorie doit être EXACTEMENT l'une de ces valeurs : "
        f"{ALLOWED_CATEGORIES}.\n"
        "3) Choisis UN SEUL emoji Unicode qui représente fidèlement ce mot.\n\n"
        'Réponds UNIQUEMENT avec un objet JSON valide, sans texte ni ``` '
        'autour, exactement sous cette forme :\n'
        '{"word": "le chat", "category": "Un animal", "emoji": "🐱"}'
    )
    for model_name in GROQ_MODELS:
        try:
            chat = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                response_format={"type": "json_object"},
            )
            raw = chat.choices[0].message.content.strip()
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            data = json.loads(raw)

            word = (data.get("word") or "").strip()
            category = (data.get("category") or "").strip()
            emoji = (data.get("emoji") or "").strip()

            if not word or not emoji or category not in ALLOWED_CATEGORIES:
                raise ValueError(f"استجابة غير مكتملة/غير صالحة: {data}")

            return {"word": word, "category": category, "emoji": emoji}
        except Exception:
            continue
    return None


def get_next_word(max_attempts: int = 8) -> dict:
    """يطلب من Groq كلمة جديدة لم تُستخدم من قبل. التاريخ الفعلي (نص الكلمات
    الأخيرة، وليس بصماتها) يُمرَّر منذ المحاولة الأولى كتلميح استبعاد حقيقي —
    هذا ما كان ناقصًا سابقًا وتسبَّب في استنفاد كل المحاولات باقتراحات مكرَّرة."""
    history = load_history()                       # قائمة نصوص كلمات، من كل الأيام السابقة
    seen = {_normalize(w) for w in history}         # للتحقق المحلي السريع والدقيق
    avoid_words = list(history[-HISTORY_HINT_SIZE:])  # تلميح حقيقي لـ Groq منذ البداية

    for _ in range(max_attempts):
        result = _ask_groq(avoid_words)
        if result is None:
            continue
        norm = _normalize(result["word"])
        if norm not in seen:
            save_history(history + [result["word"]])
            return result
        seen.add(norm)
        avoid_words.append(result["word"])          # نضيفها أيضًا كي لا تتكرر داخل نفس المحاولات

    raise RuntimeError("تعذّر الحصول على كلمة جديدة غير مكررة بعد عدة محاولات.")
