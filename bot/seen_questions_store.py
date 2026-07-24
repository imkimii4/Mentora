"""
ردیابی اینکه هر کاربر تو حالت «تست بزن» تا الان کدوم سوال‌ها رو دیده،
تا وقتی دوباره تست می‌زنه (حتی تو یه نشست جدا)، تا جای ممکن سوال‌های
تکراری نیاد. وقتی کل بانک (۵۱ تا) رو یه بار دید، دور بعدی خودش ریست
می‌شه و از اول شروع می‌شه — یعنی تکرار فقط بعد از دیدن کل بانکه.
"""
import json
from pathlib import Path

from config import DATA_DIR

_SEEN_FILE: Path = DATA_DIR / "seen_questions.json"


def _load() -> dict:
    if not _SEEN_FILE.exists():
        return {}
    with open(_SEEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    with open(_SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_seen(user_id: int) -> set[int]:
    data = _load()
    return set(data.get(str(user_id), []))


def mark_seen(user_id: int, question_ids: list[int]) -> None:
    data = _load()
    key = str(user_id)
    existing = set(data.get(key, []))
    existing.update(question_ids)
    data[key] = list(existing)
    _save(data)


def reset_seen(user_id: int) -> None:
    """وقتی کل بانک دیده شده، پاکش می‌کنیم تا دور بعدی از نو شروع بشه."""
    data = _load()
    data.pop(str(user_id), None)
    _save(data)
