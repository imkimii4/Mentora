"""
لاگ خام هر جواب quiz داخل جریان لسون (LessonFlow.awaiting_quiz_choice /
awaiting_fill_blank در lesson.py) - مستقل از practice_store.py، چون
لسون‌کوییز و تست/فلش‌کارت concernهای جدایی‌ان (طبق تصمیم معماری).

عمداً هیچ تحلیلی اینجا انجام نمی‌شه (نه pattern detection، نه mastery
calculation، نه planning logic) - فقط داده‌ی خام ذخیره می‌شه، هم‌الگوی
practice_store.py. تحلیلش بعداً در لایه‌ی Pattern/Learning State انجام
می‌شه.

عمداً "seconds_taken" نداره - طبق تصمیم معماری، فعلاً فقط timestamp برای
chronology/activity کافیه؛ افزودن timing به آینده موکول شده.

هر رکورد یک خط JSON (JSONL) تا append کردن ارزون باشه و لازم نباشه کل
فایل رو هر بار بخونیم/بنویسیم - دقیقاً هم‌الگوی practice_store.py.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR

_LOG_FILE: Path = DATA_DIR / "lesson_quiz_log.jsonl"


def _append(record: dict) -> None:
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_quiz_answer(
    user_id: int,
    lesson_id: str,
    section_id: str,
    question_ref: str,
    quiz_type: str,
    is_correct: bool,
) -> None:
    """یه رکورد خام برای یه جواب quiz داخل لسون ثبت می‌کنه. question_ref
    شناسه‌ی سؤال داخل بخشه (مثلاً message_index یا id سؤال - بسته به چیزی
    که lesson.py در دسترس داره)؛ quiz_type همون "multiple_choice" یا
    "fill_blank" هست که تو محتوای لسون هم استفاده می‌شه."""
    _append({
        "type": "lesson_quiz",
        "user_id": user_id,
        "lesson_id": lesson_id,
        "section_id": section_id,
        "question_ref": question_ref,
        "quiz_type": quiz_type,
        "is_correct": is_correct,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def get_quiz_answers(user_id: int) -> list[dict]:
    """همه‌ی رکوردهای معتبر lesson-quiz این کاربر رو به ترتیب زمانی
    (قدیم -> جدید، همون ترتیب فایل) برمی‌گردونه - برای مصرف آینده‌ی
    Pattern/Learning State. رکوردهای خراب (JSON نامعتبر) بی‌صدا رد
    می‌شن، هم‌الگوی get_session_accuracies در practice_store.py.
    هیچ aggregate/محاسبه‌ای اینجا انجام نمی‌شه - فقط داده‌ی خام filtered
    شده برمی‌گرده؛ جمع‌بندی/تحلیلش مسئولیت لایه‌ی مصرف‌کننده‌ست."""
    if not _LOG_FILE.exists():
        return []

    records: list[dict] = []
    with open(_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "lesson_quiz" or rec.get("user_id") != user_id:
                continue
            records.append(rec)

    return records


def clear_lesson_quiz(user_id: int) -> None:
    """فقط برای دستور توسعه‌ای /dev_reset. چون فایل JSONL و append-only
    هست (نه JSON کامل قابل overwrite مثل progress_store.py)، حذف رکوردهای
    این کاربر یعنی کل فایل خونده بشه، رکوردهای این user_id فیلتر بشن، و
    بقیه دوباره نوشته بشن - رکوردهای کاربرهای دیگه دست‌نخورده می‌مونن.
    اگه فایل هنوز وجود نداره، کاری لازم نیست انجام بشه."""
    if not _LOG_FILE.exists():
        return

    remaining: list[str] = []
    with open(_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rec = json.loads(stripped)
            except json.JSONDecodeError:
                # رکورد خراب - عمداً نگه داشته می‌شه، چون این تابع فقط
                # مسئول حذف داده‌ی این user_id هست، نه پاکسازی فایل.
                remaining.append(stripped)
                continue
            if rec.get("type") == "lesson_quiz" and rec.get("user_id") == user_id:
                continue
            remaining.append(stripped)

    with open(_LOG_FILE, "w", encoding="utf-8") as f:
        for line in remaining:
            f.write(line + "\n")
