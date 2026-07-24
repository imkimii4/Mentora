"""
لاگ خام و ساده‌ی eventهای کاربر - یه خط JSON در هر رویداد، برای validation
اولیه‌ی ۵ تا ۲۰ کاربر اول. بدون دیتابیس، بدون dashboard، فقط append به یه
فایل که بعداً دستی یا با یه اسکریپت کوچیک می‌شه خوندش.

Scope فعلی eventها (طبق تصمیم آخر): start, diagnostic_completed,
first_learning_action, return. هر جای دیگه‌ی کد نباید مستقیم فایل رو باز
کنه - فقط از log_event استفاده بشه، تا اگه بعداً فرمت عوض شد یه‌جا اصلاح بشه.
"""
import json
import time
from pathlib import Path

from config import DATA_DIR

_EVENTS_FILE = DATA_DIR / "events.jsonl"


def log_event(user_id: int, event_name: str, meta: dict | None = None) -> None:
    record = {
        "user_id": user_id,
        "event": event_name,
        "ts": time.time(),
    }
    if meta:
        record["meta"] = meta
    with open(_EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
