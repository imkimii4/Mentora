"""
Activity/Streak state (Phase 2) - جدا از Pattern/Inference (که هنوز پیاده
نشده). اینجا فقط current_streak، longest_streak و last_active_date هر
کاربر نگه‌داری می‌شه - نه هیچ رویداد خام رفتاری. رویدادهای خام همچنان فقط
تو practice_store.py و lesson_quiz_store.py ذخیره می‌شن؛ این فایل صرفاً
یه state مشتق‌شده و کوچیکه، هم‌الگوی progress_store.py (JSON کامل، keyed
by str(user_id)، overwrite کامل هر بار).

Active Day منابع (طبق تصمیم معماری):
- lesson.py::_finish_section
- practice.py::_finalize_answer
- practice.py::handle_flashcard_selfcheck
هیچ نقطه‌ی دیگه‌ای (مثل _send_section_intro) نباید این ماژول رو صدا بزنه.

Backfill (فقط یک‌بار، برای کاربرهای قبل از وجود این ماژول) از دو منبع
historical واقعی استفاده می‌کنه: practice_store.get_activity_dates و
lesson_quiz_store.get_quiz_answers. progress_store.py عمداً استفاده نمی‌شه
چون last_active فقط آخرین مقدار رو نگه می‌داره، نه تاریخچه - و نمی‌شه ازش
Active Day های قبلی رو بازسازی کرد.

نکته‌ی مهم درباره‌ی lesson_quiz_store به‌عنوان منبع backfill: این عمداً یه
proxy تاریخی برای فعالیت لسونه، نه معادل _finish_section. هیچ رکورد
historical واقعی از خودِ _finish_section وجود نداره (progress_store
overwrite می‌شه)، پس برای BACKFILL ONLY از تاریخ پاسخ‌های quiz استفاده
می‌شه؛ این تصمیم هوک آینده رو تغییر نمی‌ده - _finish_section همچنان تنها
منبع زنده‌ی Active Day برای لسونه.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

from config import DATA_DIR
from bot.practice_store import get_activity_dates
from bot.lesson_quiz_store import get_quiz_answers

_STATE_FILE: Path = DATA_DIR / "learning_state.json"

_DEFAULT_RECORD = {
    "current_streak": 0,
    "longest_streak": 0,
    "last_active_date": None,
    "backfilled": False,
}


def _load() -> dict:
    if not _STATE_FILE.exists():
        return {}
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # فایل خراب یا غیرقابل‌خواندن - هم‌الگوی progress_store._load: به‌جای
        # crash کردن بات، انگار هنوز هیچ learning_state ای ثبت نشده. اولین
        # save بعدی فایل رو سالم overwrite می‌کنه.
        return {}


def _save(data: dict) -> None:
    with open(_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _apply_active_day(record: dict, day: date) -> dict:
    """منطق مشترک idempotent/incremental - هم از record_active_day (زنده)
    و هم از backfill_streak (replay تاریخ‌های تاریخی به ترتیب صعودی)
    استفاده می‌شه، تا رفتار streak دقیقاً یکسان باشه."""
    last_str = record.get("last_active_date")

    if last_str is not None:
        last_date = date.fromisoformat(last_str)
        if day == last_date:
            return record  # idempotent - همین روز قبلاً ثبت شده
        if day < last_date:
            # فقط تئوریک - چون record_active_day همیشه امروز رو می‌فرسته و
            # backfill تاریخ‌ها رو صعودی replay می‌کنه. برای ایمنی، بدون
            # دستکاری streak نادیده گرفته می‌شه.
            return record
        if day == last_date + timedelta(days=1):
            record["current_streak"] = record.get("current_streak", 0) + 1
        else:
            record["current_streak"] = 1  # گپ
    else:
        record["current_streak"] = 1  # اولین فعالیت

    record["last_active_date"] = day.isoformat()
    record["longest_streak"] = max(record.get("longest_streak", 0), record["current_streak"])
    return record


def get_streak(user_id: int) -> dict:
    """current_streak/longest_streak/last_active_date این کاربر رو
    برمی‌گردونه؛ اگه هنوز هیچ فعالیتی ثبت نشده، مقدار صفر/None پیش‌فرض."""
    data = _load()
    record = data.get(str(user_id))
    if record is None:
        return {"current_streak": 0, "longest_streak": 0, "last_active_date": None}
    return {
        "current_streak": record.get("current_streak", 0),
        "longest_streak": record.get("longest_streak", 0),
        "last_active_date": record.get("last_active_date"),
    }


def record_active_day(user_id: int, day: date) -> None:
    """فقط از ۳ نقطه‌ی مجاز صدا زده می‌شه: lesson.py::_finish_section،
    practice.py::_finalize_answer، practice.py::handle_flashcard_selfcheck.
    idempotent برای همون تاریخ تقویمی، incremental برای روز متوالی، گپ
    باعث ریست به ۱ می‌شه."""
    data = _load()
    record = data.get(str(user_id)) or dict(_DEFAULT_RECORD)
    record = _apply_active_day(record, day)
    data[str(user_id)] = record
    _save(data)


def backfill_streak(user_id: int) -> None:
    """یک‌بار برای کاربرهای موجود (قبل از وجود این ماژول) اجرا می‌شه.
    فقط از timestamp های واقعی این دو منبع استفاده می‌کنه - هیچ تاریخ
    synthetic ساخته نمی‌شه:
    - practice_store.get_activity_dates(user_id)  (test + flashcard)
    - lesson_quiz_store.get_quiz_answers(user_id)  (proxy تاریخی لسون)

    Idempotent: اگه قبلاً backfill شده (پرچم backfilled=True تو رکورد
    کاربر)، دوباره اجرا نمی‌شه - حتی اگه دوباره صدا زده بشه."""
    data = _load()
    existing = data.get(str(user_id))
    if existing and existing.get("backfilled"):
        return

    historical_dates: set[str] = set(get_activity_dates(user_id))

    for rec in get_quiz_answers(user_id):
        ts = rec.get("timestamp")
        if not ts:
            continue
        try:
            historical_dates.add(datetime.fromisoformat(ts).date().isoformat())
        except ValueError:
            continue

    # اگه از قبل (مثلاً یه hook زنده قبل از اجرای backfill صدا خورده)
    # last_active_date ای ثبت شده، اونم باید تو replay لحاظ بشه - وگرنه
    # ممکنه streak زنده‌ی موجود با replay تاریخی جایگزین/گم بشه.
    if existing and existing.get("last_active_date"):
        historical_dates.add(existing["last_active_date"])

    if not historical_dates:
        # هیچ فعالیت historical معتبری نیست - فقط پرچم backfilled ست می‌شه
        # تا دوباره تلاش نکنه؛ هیچ تاریخ synthetic ساخته نمی‌شه.
        data[str(user_id)] = dict(_DEFAULT_RECORD, backfilled=True)
        _save(data)
        return

    sorted_dates = sorted(date.fromisoformat(d) for d in historical_dates)
    record = dict(_DEFAULT_RECORD)
    for day in sorted_dates:
        record = _apply_active_day(record, day)
    record["backfilled"] = True

    data[str(user_id)] = record
    _save(data)


def clear_learning_state(user_id: int) -> None:
    """فقط رکورد این user_id رو حذف می‌کنه؛ بقیه‌ی کاربرها دست‌نخورده
    می‌مونن. برای /dev_reset."""
    data = _load()
    if str(user_id) in data:
        del data[str(user_id)]
        _save(data)
