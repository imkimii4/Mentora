"""
نرمال‌سازی متن عربی برای مقایسه‌ی جواب‌های fill_blank.

هدف: وقتی کاربر جواب رو از نظر لغوی درست نوشته ولی اعراب‌گذاری
(فتحه/ضمه/کسره/تشدید/سکون/تنوین) یا رسم‌الخط (همزه، ة/ه، ى/ی) فرق داره،
نباید کامل "غلط" حساب بشه؛ باید بگیم درسته ولی شکل دقیقش رو نشون بدیم.
"""
import re

# بازه‌ی یونیکد حرکات و علائم اعرابی عربی (فتحه، ضمه، کسره، تشدید، سکون،
# تنوین‌ها، و علائم قرآنی مثل مد کوتاه/بلند)
_DIACRITICS_PATTERN = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D4-\u08E1\u08E3-\u08FF]"
)

_TATWEEL = "\u0640"  # کشیدگی حروف (ـ)

# نرمال‌سازی رسم‌الخطیِ رایج (برای غلط املایی‌های خیلی جزئی، نه معنایی)
_SPELLING_MAP = {
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ی", "ي": "ی",
    "ة": "ه",
    "ؤ": "و",
    "ئ": "ی",
}


def normalize_arabic(text: str) -> str:
    """حرکات و تفاوت‌های جزئی رسم‌الخط رو حذف می‌کنه تا مقایسه‌ی معنایی انجام بشه."""
    text = text.strip()
    text = _DIACRITICS_PATTERN.sub("", text)
    text = text.replace(_TATWEEL, "")
    for src, dst in _SPELLING_MAP.items():
        text = text.replace(src, dst)
    # حرف تعریف عربی «ال» رو از اول هر کلمه حذف کن (کاربر فارسی‌زبان اغلب
    # معادل فارسیِ بدون «ال» رو می‌نویسه، مثل «آخرت» به‌جای «الآخره»)
    text = re.sub(r"(?<!\S)ال(?=\S)", "", text)
    # در پایان کلمه، «ه» و «ت» معادل هم حساب بشن (تاء گرد عربی هم به «ه»
    # هم به «ت» در فارسی رایج نویسه‌گردانی می‌شه: آخرة/آخره/آخرت)
    text = re.sub(r"[هت]$", "ه", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compare_answers(user_answer: str, correct_answer: str) -> tuple[bool, bool]:
    """
    برمی‌گردونه (is_correct, is_exact).
    is_correct: آیا از نظر معنایی/نرمال‌شده درسته؟
    is_exact: آیا کاملاً کاراکتر‌به‌کاراکتر (با همون اعراب) درسته؟
    """
    user_answer = user_answer.strip()
    correct_answer = correct_answer.strip()

    is_exact = user_answer == correct_answer
    is_correct = is_exact or normalize_arabic(user_answer) == normalize_arabic(correct_answer)
    return is_correct, is_exact
