"""
ذخیره‌ی persistent پروفایل هر کاربر (نام، سن، پایه، هدف یادگیری، زمان
مطالعه‌ی روزانه)، توی یه فایل JSON جدا کنار بقیه‌ی دیتای پروژه - هم‌الگوی
onboarding_store.py و progress_store.py (JSON کامل، keyed by str(user_id)،
overwrite کامل هر بار).

عمداً از onboarding_status.json و progress.json جداست:
  - onboarding_status.json فقط می‌گه مسیر شروع سریع/تشخیصی انتخاب شده یا نه
  - progress.json پیشرفت درسی (section-level) است
  - این فایل («کی هست این کاربر») مفهوماً مستقل از هر دوی بالاست و باید
    بتونه بدون وابستگی به اون‌ها توسط مراحل بعدی (شخصی‌سازی مسیر یادگیری،
    برنامه‌ریزی) خونده بشه.

Resume: هر فیلد بلافاصله بعد از جواب معتبر کاربر با save_profile_field
ذخیره می‌شه (نه فقط در پایان کل فرآیند) - چون FSM state با ری‌استارت بات
(MemoryStorage) پاک می‌شه ولی این فایل رو دیسک persistent می‌مونه.
get_next_missing_field تنها منبع تشخیص "کاربر تا کجا جلو رفته" است.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from config import DATA_DIR

_PROFILE_FILE: Path = DATA_DIR / "user_profile.json"

# ترتیب سؤال‌ها ثابت و معنادار است - get_next_missing_field دقیقاً به همین
# ترتیب اولین فیلد ناقص رو پیدا می‌کنه. اگه بعداً سؤال جدیدی اضافه شد،
# فقط کافیه به همین لیست (در جای درست ترتیب) اضافه بشه.
PROFILE_FIELDS = ["name", "age", "grade", "goal", "daily_minutes"]


def _load() -> dict:
    if not _PROFILE_FILE.exists():
        return {}
    try:
        with open(_PROFILE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # فایل خراب یا غیرقابل‌خواندن - مثل progress_store.py، به‌جای کرش
        # کردن بات، انگار هنوز پروفایلی ثبت نشده. اولین save بعدی فایل رو
        # سالم overwrite می‌کنه.
        return {}


def _save(data: dict) -> None:
    with open(_PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_profile(user_id: int) -> dict | None:
    """رکورد پروفایل این کاربر رو برمی‌گردونه، یا None اگه هنوز هیچ سؤالی
    جواب نداده (کاملاً کاربر جدید)."""
    data = _load()
    return data.get(str(user_id))


def save_profile_field(user_id: int, field: str, value) -> None:
    """یه فیلد رو فوراً ذخیره می‌کنه (partial save) - برای اینکه اگه کاربر
    وسط راه رها کنه، جوابی که تا الان داده از دست نره."""
    if field not in PROFILE_FIELDS:
        raise ValueError(f"فیلد پروفایل ناشناخته: {field}")
    data = _load()
    record = data.get(str(user_id)) or {}
    record[field] = value
    record["last_updated"] = datetime.now(timezone.utc).isoformat()
    data[str(user_id)] = record
    _save(data)


def get_next_missing_field(profile: dict | None) -> str | None:
    """اولین فیلدی که هنوز جواب داده نشده رو برمی‌گردونه، یا None اگه همه‌ی
    فیلدها کاملن. profile=None یعنی هیچ‌کدوم جواب داده نشده -> فیلد اول."""
    if not profile:
        return PROFILE_FIELDS[0]
    for field in PROFILE_FIELDS:
        if field not in profile:
            return field
    return None


def is_profile_complete(profile: dict | None) -> bool:
    return get_next_missing_field(profile) is None


def mark_profile_complete(user_id: int) -> None:
    """بعد از ذخیره‌ی آخرین فیلد صدا زده می‌شه - فقط یه timestamp برای
    دیباگ/کنجکاوی بعدی ثبت می‌کنه؛ خودِ "کامل بودن" از PROFILE_FIELDS
    محاسبه می‌شه، نه از این timestamp."""
    data = _load()
    record = data.get(str(user_id)) or {}
    record["completed_at"] = datetime.now(timezone.utc).isoformat()
    data[str(user_id)] = record
    _save(data)


def clear_profile(user_id: int) -> None:
    """فقط برای دستور توسعه‌ای /dev_reset - هم‌الگوی clear_onboarded در
    onboarding_store.py."""
    data = _load()
    data.pop(str(user_id), None)
    _save(data)
