"""
Title/Rank (Phase 4) - محاسبه‌ی خالص و بدون‌حالت (pure/deterministic) از
روی current_streak، بدون هیچ persistence و بدون هیچ side effect.

عمداً جدا از profile_store.py (هویت)، profile_display_store.py (نمایش)،
learning_state_store.py (منبع خودِ streak) و rule_engine.py (موتور
per-session لسون) - این ماژول فقط یه تابع نگاشت خالصه: همون ورودی همیشه
همون خروجی رو می‌ده، هیچ فایلی نمی‌خونه/نمی‌نویسه.

Phase 4 v1: فقط current_streak به‌عنوان سیگنال رفتاری استفاده می‌شه - نه
دقت/تسلط/hint/زمان. صدا زده می‌شه از bot/handlers/onboarding.py::
handle_menu_profile، دقیقاً در لحظه‌ی نمایش پروفایل (dynamic، نه persisted).
"""
from __future__ import annotations

# آستانه‌ها (بر حسب current_streak، روز) - ترتیب از کم به زیاد، هر بازه
# شامل حد پایینش و تا قبل از آستانه‌ی بعدی.
_TITLE_THRESHOLDS: list[tuple[int, str]] = [
    (2, "تازه‌کار"),    # 0-2 روز
    (6, "پیگیر"),       # 3-6 روز
    (13, "پرتلاش"),     # 7-13 روز
    (29, "حرفه‌ای"),     # 14-29 روز
    # 30+ روز -> استاد (پایین‌تر، بعد از حلقه)
]
_TOP_TITLE = "استاد"  # 30+ روز


def get_title(current_streak: int) -> str:
    """current_streak -> عنوان/رتبه. تابع خالصه: فقط بر اساس مقدار ورودی
    تصمیم می‌گیره، هیچ فایل/store ای نمی‌خونه. فراخوان مسئول تهیه‌ی
    current_streak واقعیه (مثلاً از learning_state_store.get_streak)."""
    for upper_bound, title in _TITLE_THRESHOLDS:
        if current_streak <= upper_bound:
            return title
    return _TOP_TITLE
