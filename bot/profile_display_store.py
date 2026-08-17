"""
Profile Display (Phase 3) - جدا از هویت پروفایل (profile_store.py) و جدا
از Activity/Streak (learning_state_store.py). این فایل فقط چیزهایی که به
"نمایش" پروفایل مربوطن رو نگه می‌داره - فعلاً فقط photo_file_id.

هم‌الگوی progress_store.py/learning_state_store.py (JSON کامل، keyed by
str(user_id)، overwrite کامل هر بار).

عمداً از profile_store.py جداست: طبق تصمیم معماری، name/age/grade/goal/
daily_minutes فقط تو profile_store.py و PROFILE_FIELDS باقی می‌مونن؛
عکس پروفایل مفهوماً یه چیز جداست (display، نه identity) و نباید
PROFILE_FIELDS رو دست بزنه یا داخلش تعریف بشه.

این فاز (Phase 3) فقط storage API رو قرار می‌ده - set_photo فعلاً از هیچ
handler آپلود عکسی صدا زده نمی‌شه (اون یه فاز جداست)؛ فقط برای اینه که
لایه‌ی نمایش پروفایل (bot/handlers/onboarding.py::handle_menu_profile)
بتونه get_display رو صدا بزنه و اگه بعداً عکسی ثبت شد نشونش بده.

title/rank عمداً اینجا نیست - طبق تصمیم معماری، فقط وقتی که صراحتاً لازم
بشه اضافه می‌شه، نه از پیش.
"""
import json
from pathlib import Path

from config import DATA_DIR

_DISPLAY_FILE: Path = DATA_DIR / "profile_display.json"

_DEFAULT_RECORD = {
    "photo_file_id": None,
}


def _load() -> dict:
    if not _DISPLAY_FILE.exists():
        return {}
    try:
        with open(_DISPLAY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # فایل خراب یا غیرقابل‌خواندن - هم‌الگوی بقیه‌ی storeها: به‌جای
        # crash کردن بات، انگار هنوز هیچ display ای ثبت نشده. اولین save
        # بعدی فایل رو سالم overwrite می‌کنه.
        return {}


def _save(data: dict) -> None:
    with open(_DISPLAY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_display(user_id: int) -> dict:
    """رکورد نمایش این کاربر رو برمی‌گردونه؛ اگه هنوز هیچی ثبت نشده،
    مقدار پیش‌فرض (photo_file_id=None) - هیچ‌وقت None برنمی‌گردونه، برخلاف
    get_profile، چون این یه state مکمله نه یه چک «کاربر جدید هست یا نه»."""
    data = _load()
    record = data.get(str(user_id))
    if record is None:
        return dict(_DEFAULT_RECORD)
    return {"photo_file_id": record.get("photo_file_id")}


def set_photo(user_id: int, file_id: str) -> None:
    """فقط storage API - فعلاً هیچ handler آپلود عکسی این رو صدا نمی‌زنه
    (خارج از اسکوپ Phase 3)."""
    data = _load()
    record = data.get(str(user_id)) or dict(_DEFAULT_RECORD)
    record["photo_file_id"] = file_id
    data[str(user_id)] = record
    _save(data)


def clear_display(user_id: int) -> None:
    """فقط رکورد این user_id رو حذف می‌کنه؛ بقیه‌ی کاربرها دست‌نخورده
    می‌مونن. برای /dev_reset."""
    data = _load()
    if str(user_id) in data:
        del data[str(user_id)]
        _save(data)
