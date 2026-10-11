"""
generate_image.py — بطاقة مفردات فرنسية: إيموجي كبير + تصنيف + الكلمة بالفرنسية
(بأداتها الصحيحة le/la/les/l') بخط مبهج وواضح، خلفية مشرقة مناسبة لقناة تعليمية.
"""
import os
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "assets", "Fredoka-Bold.ttf")
EMOJI_FONT_FILE = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"

WIDTH, HEIGHT = 1080, 1920

CATEGORY_COLORS = {
    "Un animal":   {"top": (255, 213, 128), "bottom": (255, 158, 97)},
    "Un métier":   {"top": (137, 207, 240), "bottom": (84, 160, 214)},
    "Un fruit":    {"top": (168, 230, 163), "bottom": (108, 194, 111)},
    "Un objet":    {"top": (216, 191, 255), "bottom": (170, 136, 240)},
    "Une couleur": {"top": (255, 182, 193), "bottom": (255, 133, 161)},
    "La nature":   {"top": (160, 221, 230), "bottom": (100, 181, 196)},
}
DEFAULT_COLORS = {"top": (255, 213, 128), "bottom": (255, 158, 97)}


def _vertical_gradient(size, top_color, bottom_color):
    img = Image.new("RGB", size, top_color)
    draw = ImageDraw.Draw(img)
    h = size[1]
    for y in range(h):
        ratio = y / h
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        draw.line([(0, y), (size[0], y)], fill=(r, g, b))
    return img


def _load_fredoka(size, weight="Bold"):
    font = ImageFont.truetype(FONT_PATH, size)
    try:
        font.set_variation_by_name(weight)
    except Exception:
        pass
    return font


def _fit_word_font(draw, word, max_width, start_size=96, min_size=44):
    """يصغّر حجم الخط تدريجيًا حتى تدخل الكلمة كاملة ضمن عرض البطاقة —
    ضروري لأن طول كلمات الفرنسية يتفاوت كثيرًا (le chat / l'informaticien)
    ولا نريد أي قطع أو خروج عن حدود البطاقة."""
    size = start_size
    while size > min_size:
        font = _load_fredoka(size, "Bold")
        w = draw.textbbox((0, 0), word, font=font)[2]
        if w <= max_width:
            return font
        size -= 4
    return _load_fredoka(min_size, "Bold")


def generate_word_card(emoji: str, word: str, category: str, output_path: str) -> str:
    colors = CATEGORY_COLORS.get(category, DEFAULT_COLORS)
    img = _vertical_gradient((WIDTH, HEIGHT), colors["top"], colors["bottom"])
    draw = ImageDraw.Draw(img)

    card_margin = 70
    card_top, card_bottom = int(HEIGHT * 0.22), int(HEIGHT * 0.78)
    draw.rounded_rectangle(
        [card_margin, card_top, WIDTH - card_margin, card_bottom],
        radius=60, fill=(255, 255, 255, 235),
    )

    cat_font = _load_fredoka(44, "SemiBold")
    cat_bbox = draw.textbbox((0, 0), category, font=cat_font)
    cat_w = cat_bbox[2] - cat_bbox[0]
    pill_pad_x, pill_h = 40, 70
    pill_y = card_top - pill_h / 2
    draw.rounded_rectangle(
        [(WIDTH - cat_w) / 2 - pill_pad_x, pill_y,
         (WIDTH + cat_w) / 2 + pill_pad_x, pill_y + pill_h],
        radius=pill_h / 2, fill=colors["bottom"],
    )
    draw.text(((WIDTH - cat_w) / 2, pill_y + (pill_h - (cat_bbox[3] - cat_bbox[1])) / 2 - cat_bbox[1]),
              category, font=cat_font, fill=(255, 255, 255))

    # الإيموجي: NotoColorEmoji خط Bitmap ثابت الحجم (~109px، غير متجهي)،
    # فنرسمه بحجمه الطبيعي على صورة صغيرة منفصلة ثم نُكبّرها بجودة (LANCZOS).
    emoji_scale = 2.6
    try:
        native_font = ImageFont.truetype(EMOJI_FONT_FILE, 109)
        tmp = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
        tdraw = ImageDraw.Draw(tmp)
        tdraw.text((80, 80), emoji, font=native_font, embedded_color=True, anchor="mm")
        cropped = tmp.crop(tmp.getbbox() or (0, 0, 160, 160))
        big = cropped.resize(
            (int(cropped.width * emoji_scale), int(cropped.height * emoji_scale)), Image.LANCZOS,
        )
        ex = (WIDTH - big.width) / 2
        ey = card_top + (card_bottom - card_top) * 0.36 - big.height / 2
        img.paste(big, (int(ex), int(ey)), big)
    except Exception:
        fallback_font = _load_fredoka(220, "Bold")
        _fbbox = draw.textbbox((0, 0), emoji, font=fallback_font)
        fx = (WIDTH - (_fbbox[2] - _fbbox[0])) / 2
        fy = card_top + (card_bottom - card_top) * 0.30
        draw.text((fx, fy), emoji, font=fallback_font, fill=(80, 80, 90))

    # الكلمة الفرنسية — بحجم خط يتكيّف مع طولها لضمان عدم تجاوز حدود البطاقة
    max_word_width = (WIDTH - 2 * card_margin) - 80
    word_font = _fit_word_font(draw, word, max_word_width)
    wbbox = draw.textbbox((0, 0), word, font=word_font)
    ww = wbbox[2] - wbbox[0]
    wy = card_top + (card_bottom - card_top) * 0.72
    draw.text(((WIDTH - ww) / 2, wy), word, font=word_font, fill=(45, 45, 60))

    img.save(output_path, "PNG")
    return output_path


if __name__ == "__main__":
    generate_word_card("🧑‍💻", "l'informaticien", "Un métier", os.path.join(BASE_DIR, "test_longest.png"))
    print("saved test_longest.png")
