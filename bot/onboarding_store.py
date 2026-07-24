"""
ذخیره‌ی ساده‌ی وضعیت onboarding هر کاربر (کاربر جدید در برابر برگشتی، و
اینکه کدوم مسیر رو رفته: شروع سریع یا آزمون تشخیصی)، توی یه فایل JSON کنار
بقیه‌ی دیتای درس - دقیقاً هم‌الگوی feedback_store.py.

این تنها منبع تشخیص کاربر جدید/برگشتی است. FSMContext برای این کار مناسب
نیست چون handle_start هر بار state.clear() می‌زنه و همه‌چیز رو پاک می‌کنه؛
پس باید persistent روی دیسک باشه، نه تو state.
"""
import json
from pathlib import Path

from config import DATA_DIR

_STATUS_FILE = DATA_DIR / "onboarding_status.json"


def _load() -> dict:
    if not _STATUS_FILE.exists():
        return {}
    with open(_STATUS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def has_onboarded(user_id: int) -> bool:
    data = _load()
    return str(user_id) in data


def mark_onboarded(user_id: int, path: str) -> None:
    """path باید 'quick' یا 'diagnostic' باشه - فقط برای دیباگ/کنجکاوی بعدی،
    خود تصمیم مسیر رو تغییر نمی‌ده (طبق تصمیم ۴: همه از S1 شروع می‌کنن)."""
    data = _load()
    data[str(user_id)] = {"path": path}
    _save(data)


def clear_onboarded(user_id: int) -> None:
    """فقط برای دستور توسعه‌ای /dev_reset. entry مربوط به این user_id رو
    حذف می‌کنه تا has_onboarded() دوباره False برگردونه و کاربر دوباره
    جریان کامل onboarding رو ببینه."""
    data = _load()
    data.pop(str(user_id), None)
    _save(data)
