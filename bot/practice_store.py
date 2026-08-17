"""
لاگ خام هر جواب تو حالت «تست بزن» و هر خودارزیابی تو «فلش‌کارت بخون».
عمداً هیچ تحلیلی اینجا انجام نمی‌شه (نه سرعت‌سنجی، نه تشخیص گپ مفهومی) —
طبق تصمیم: الان فقط داده‌ی خام ذخیره بشه، تحلیلش با داده‌ی واقعی کاربرها
بعد از لانچ انجام می‌شه. هر رکورد یک خط JSON (JSONL) تا append کردن ارزون باشه
و لازم نباشه کل فایل رو هر بار بخونیم/بنویسیم.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR

_LOG_FILE: Path = DATA_DIR / "practice_log.jsonl"


def _append(record: dict) -> None:
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_test_answer(
    user_id: int,
    question_id: int,
    section_ref: str,
    is_correct: bool,
    seconds_taken: float,
    session_id: str,
    used_hint: bool = False,
) -> None:
    # used_hint اختیاریه و پیش‌فرضش False - رکوردهای قدیمی JSONL این فیلد رو
    # ندارن و هیچ کد فعلی (get_session_accuracies) بهش نگاه نمی‌کنه، پس
    # backward-compatible‌ه. correct_with_hint یعنی is_correct=True و
    # used_hint=True با هم، نه یه مقدار جدا.
    _append({
        "type": "test",
        "user_id": user_id,
        "session_id": session_id,
        "question_id": question_id,
        "section_ref": section_ref,
        "is_correct": is_correct,
        "used_hint": used_hint,
        "seconds_taken": round(seconds_taken, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def log_flashcard_result(
    user_id: int,
    card_id: str,
    section_ref: str,
    knew_it: bool,
) -> None:
    _append({
        "type": "flashcard",
        "user_id": user_id,
        "card_id": card_id,
        "section_ref": section_ref,
        "knew_it": knew_it,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def get_session_accuracies(user_id: int) -> list[tuple[str, int, int]]:
    """لیست (session_id, correct, total) رو به ترتیب زمانی (قدیم -> جدید)
    برمی‌گردونه، فقط برای همین کاربر و نوع «test». برای مقایسه‌ی «نسبت به
    جلسه‌ی قبل» استفاده می‌شه - آخرین آیتم لیست همون جلسه‌ی الانه (چون قبل از
    صدا زدن این تابع، جواب‌های همین جلسه از قبل لاگ شدن)."""
    if not _LOG_FILE.exists():
        return []

    sessions: dict[str, dict] = {}
    order: list[str] = []
    with open(_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") != "test" or rec.get("user_id") != user_id:
                continue
            sid = rec.get("session_id")
            if not sid:
                continue
            if sid not in sessions:
                sessions[sid] = {"correct": 0, "total": 0}
                order.append(sid)
            sessions[sid]["total"] += 1
            if rec.get("is_correct"):
                sessions[sid]["correct"] += 1

    return [(sid, sessions[sid]["correct"], sessions[sid]["total"]) for sid in order]


def get_activity_dates(user_id: int) -> list[str]:
    """فقط برای backfill Active Day (learning_state_store.py): تاریخ
    تقویمی (YYYY-MM-DD، بر اساس timestamp ذخیره‌شده) هر رکورد test یا
    flashcard این کاربر رو برمی‌گردونه - بدون aggregate، بدون فیلتر
    session، بدون هیچ فیلد دیگه‌ای از رکورد خام. ممکنه تاریخ تکراری
    داشته باشه (چند فعالیت یه روز) - dedupe مسئولیت مصرف‌کننده‌ست، نه
    اینجا. هیچ تغییری تو schema یا رفتار لاگ‌گیری موجود ایجاد نمی‌کنه."""
    if not _LOG_FILE.exists():
        return []

    dates: list[str] = []
    with open(_LOG_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("user_id") != user_id or rec.get("type") not in ("test", "flashcard"):
                continue
            ts = rec.get("timestamp")
            if not ts:
                continue
            try:
                dates.append(datetime.fromisoformat(ts).date().isoformat())
            except ValueError:
                continue

    return dates
