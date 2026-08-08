"""
ذخیره‌ی persistent پیشرفت هر کاربر در لسون: کدوم section الان توشه و کدوم
بخش‌ها رو کامل کرده. هم‌الگوی onboarding_store.py (JSON کامل، keyed by
str(user_id)، overwrite کامل هر بار) - برای تعداد کاربر فعلی (۵-۲۰ نفر)
کافیه و نیازی به append-only مثل practice_store/event_log نداره.

عمداً فقط section-level است. current_question, review_queue و بقیه‌ی
جزئیات FSM اینجا persist نمی‌شن (طبق تصمیم: سؤالات تست random-sample
هستن، پیشرفت question-level معنی نداره؛ review_queue هم فعلاً session-only
می‌مونه - خارج از اسکوپ این تغییرات).

completed_sections فقط باید از lesson.py::_finish_section() نوشته بشه.
هیچ‌جای دیگه‌ای این تابع رو صدا نزنه.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR

_PROGRESS_FILE: Path = DATA_DIR / "progress.json"


def _load() -> dict:
    if not _PROGRESS_FILE.exists():
        return {}
    try:
        with open(_PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # فایل خراب یا غیرقابل‌خواندن - به‌جای crash کردن بات، انگار هنوز
        # progressـی ثبت نشده. چیزی که از دست می‌ره فقط تاریخچه‌ی progress
        # ذخیره‌شده‌ست، نه کارکرد بات؛ اولین save بعدی فایل رو سالم overwrite
        # می‌کنه.
        return {}


def _save(data: dict) -> None:
    with open(_PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_progress(user_id: int) -> dict | None:
    """رکورد progress این کاربر رو برمی‌گردونه، یا None اگه هنوز هیچ‌چیز
    ثبت نشده (کاربر کاملاً جدیده یا هنوز وارد هیچ section‌ای نشده)."""
    data = _load()
    return data.get(str(user_id))


def set_current_section(user_id: int, lesson_id: str, section_id: str) -> None:
    """هر بار کاربر وارد یه section می‌شه صدا زده می‌شه - از تنها نقطه‌ی
    مشترک ورود به section (_send_section_intro در lesson.py)، چه مسیر خطی
    باشه چه انتخاب مستقیم بخش، چه review_queue، چه /goto. رکورد رو اگه
    وجود نداشته باشه می‌سازه."""
    data = _load()
    record = data.get(str(user_id)) or {"lesson_id": lesson_id, "completed_sections": []}
    record["lesson_id"] = lesson_id
    record["current_section"] = section_id
    record["last_active"] = datetime.now(timezone.utc).isoformat()
    data[str(user_id)] = record
    _save(data)


def mark_section_complete(user_id: int, lesson_id: str, section_id: str) -> None:
    """فقط از lesson.py::_finish_section صدا زده می‌شه. Idempotent - اگه
    section_id از قبل تو completed_sections بود، دوباره اضافه نمی‌شه."""
    data = _load()
    record = data.get(str(user_id)) or {"lesson_id": lesson_id, "completed_sections": []}
    record["lesson_id"] = lesson_id
    if section_id not in record["completed_sections"]:
        record["completed_sections"].append(section_id)
    record["last_active"] = datetime.now(timezone.utc).isoformat()
    data[str(user_id)] = record
    _save(data)
