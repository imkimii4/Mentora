"""
لود و ایندکس‌کردن فایل‌های JSON محتوا (درس، فلش‌کارت، بانک تست).
همه چیز در حافظه cache می‌شه چون فایل‌ها کوچیکن و در استارت‌آپ فقط یک بار خونده می‌شن.
"""
import json
from functools import lru_cache
from typing import Any

from config import DATA_DIR


def _load_json(filename: str) -> dict[str, Any]:
    path = DATA_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_lesson(lesson_id: str) -> dict[str, Any]:
    # فعلاً فقط L1 -> lesson1.json. وقتی درس‌های بعدی اضافه شدن،
    # این mapping باید به یه دیکشنری lesson_id -> filename تبدیل بشه.
    if lesson_id != "L1":
        raise ValueError(f"درس {lesson_id} هنوز موجود نیست")
    return _load_json("lesson1.json")


@lru_cache(maxsize=None)
def load_flashcards(lesson_id: str) -> dict[str, Any]:
    if lesson_id != "L1":
        raise ValueError(f"فلش‌کارت‌های {lesson_id} هنوز موجود نیست")
    return _load_json("flashcards_L1.json")


@lru_cache(maxsize=None)
def load_test_bank(lesson_id: str) -> dict[str, Any]:
    if lesson_id != "L1":
        raise ValueError(f"بانک تست {lesson_id} هنوز موجود نیست")
    return _load_json("test_bank_L1.json")


def get_section(lesson_id: str, section_index: int) -> dict[str, Any] | None:
    """section_index صفر-پایه است (0 = بخش ۱)."""
    lesson = load_lesson(lesson_id)
    sections = lesson["sections"]
    if 0 <= section_index < len(sections):
        return sections[section_index]
    return None


def total_sections(lesson_id: str) -> int:
    return len(load_lesson(lesson_id)["sections"])


def get_section_index_by_id(lesson_id: str, section_id: str) -> int | None:
    """section_id مثل 'S6' - برای پیدا کردن ایندکس بخش وقتی فقط section_id
    رو داریم (مثلاً از section_ref تو بانک تست/فلش‌کارت استخراج شده)."""
    sections = load_lesson(lesson_id)["sections"]
    for i, s in enumerate(sections):
        if s.get("section_id") == section_id:
            return i
    return None


def get_section_index_by_id(lesson_id: str, section_id: str) -> int | None:
    """پیدا کردن ایندکس صفر-پایه‌ی یه بخش با section_id واقعی‌ش (مثل 'S4')
    -- دقیقاً همون آیدی که تو lesson1.json هست، نه شماره‌ای که تو ذهن حساب
    می‌شه. برای دستور /goto استفاده می‌شه تا آفست اشتباه پیش نیاد."""
    sections = load_lesson(lesson_id)["sections"]
    for i, section in enumerate(sections):
        if section.get("section_id", "").strip().lower() == section_id.strip().lower():
            return i
    return None


def get_flashcards_by_ids(lesson_id: str, card_ids: list[str]) -> list[dict[str, Any]]:
    cards = load_flashcards(lesson_id)["cards"]
    by_id = {c["id"]: c for c in cards}
    return [by_id[cid] for cid in card_ids if cid in by_id]


def get_test_questions_by_ids(lesson_id: str, question_ids: list[int]) -> list[dict[str, Any]]:
    questions = load_test_bank(lesson_id)["questions"]
    by_id = {q["id"]: q for q in questions}
    return [by_id[qid] for qid in question_ids if qid in by_id]
