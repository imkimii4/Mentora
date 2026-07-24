"""
تنظیمات پایه SmartSchoolBot.
مقادیر حساس (توکن) از environment variable خونده می‌شن، نه هاردکد.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

BOT_TOKEN = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    # فقط وقتی واقعاً اجرا می‌شه لازمه؛ برای تست واحد کد نیازی به توکن نیست.
    print("⚠️  BOT_TOKEN تنظیم نشده. برای اجرای واقعی، متغیر محیطی BOT_TOKEN رو ست کن.")

# --- تنظیمات Rule Engine (طبق MVP_Final_Unified.md) ---
CONSECUTIVE_ERROR_THRESHOLD = 3      # ۳ غلط متوالی
FATIGUE_WINDOW = 5                   # آخرین N پاسخ برای تشخیص خستگی
FATIGUE_ACCURACY_DROP = 0.4          # افت نسبی دقت نسبت به کل جلسه

# --- درس‌های فعال (فعلاً فقط درس ۱) ---
AVAILABLE_LESSONS = ["L1"]
FREE_LESSONS = ["L1"]  # درس ۱ همیشه رایگان؛ از درس ۲ اشتراک لازمه

# --- فیدبک کاربر (لایک/دیس‌لایک/ایده هر بخش) ---
# آیدی عددی چت تلگرام سازنده (کیمیا) که فیدبک‌ها براش فوروارد می‌شه.
# با پیام گرفتن از @userinfobot تو تلگرام می‌شه این عدد رو گرفت.
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or "0")
if not ADMIN_CHAT_ID:
    print("⚠️  ADMIN_CHAT_ID تنظیم نشده. لایک/دیس‌لایک/ایده‌ی کاربرها برای تو ارسال نمی‌شه.")

# --- اکانت‌های تست توسعه (فقط برای دستور /dev_reset) ---
# فقط این user_id ها اجازه‌ی ریست دستی وضعیت کاربر رو دارن؛ برای هر کاربر
# دیگه‌ای (از جمله کاربرهای واقعی رو Railway) این دستور کاملاً بی‌اثره.
DEV_TEST_USER_IDS = {115628307, 8650936164}
