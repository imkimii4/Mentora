"""
ذخیره‌ی ساده‌ی تعداد لایک/دیس‌لایک هر بخش، توی یه فایل JSON کنار بقیه‌ی
دیتای درس. برای MVP و تعداد کاربر کم کافیه؛ اگه بعداً کاربر زیاد شد،
باید بریم سراغ یه دیتابیس واقعی (SQLite حداقل).
"""
import json
from pathlib import Path

from config import DATA_DIR

_COUNTS_FILE = DATA_DIR / "feedback_counts.json"


def _load() -> dict:
    if not _COUNTS_FILE.exists():
        return {}
    with open(_COUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_COUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def increment(section_id: str, kind: str) -> int:
    """kind باید 'like' یا 'dislike' باشه. عدد جدید بعد از افزایش برمی‌گرده."""
    data = _load()
    section_counts = data.setdefault(section_id, {"like": 0, "dislike": 0})
    section_counts[kind] = section_counts.get(kind, 0) + 1
    _save(data)
    return section_counts[kind]


def get_counts(section_id: str) -> dict:
    data = _load()
    return data.get(section_id, {"like": 0, "dislike": 0})
