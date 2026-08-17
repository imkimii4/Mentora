"""
تست end-to-end برای Slice «Onboarding / User Profile»، با aiogram Dispatcher
و FSM واقعی (MemoryStorage) + یک Bot جعلی (FakeBot) که به‌جای تلگرام واقعی،
فقط پیام‌ها رو ضبط می‌کنه - بدون نیاز به توکن واقعی یا اتصال شبکه.

اجرا: BOT_TOKEN=dummy python3 tests/test_onboarding_profile.py
(BOT_TOKEN فقط برای import شدن config.py لازمه، مقدارش برای این تست مهم نیست.)

هر سناریو یه تابع async جدا با assert های خودشه. در پایان تعداد
موفق/ناموفق چاپ می‌شه و exit code غیرصفر برمی‌گرده اگه چیزی fail بشه.
"""
from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

# --- قبل از هر ایمپورت پروژه، DATA_DIR رو به یه پوشه‌ی موقت redirect می‌کنیم
# تا تست‌ها هیچ‌وقت به data/ واقعی پروژه دست نزنن. ---
_TMP_DATA_DIR = Path(tempfile.mkdtemp(prefix="mentora_test_data_"))
import os
os.environ.setdefault("BOT_TOKEN", "123456:TESTTESTTESTTESTTESTTESTTESTTESTTES")

import config
_REAL_DATA_DIR = config.DATA_DIR
config.DATA_DIR = _TMP_DATA_DIR
config.DEV_TEST_USER_IDS = {999001}

# فایل‌های محتوای فقط-خواندنی (لسون/بانک‌تست/فلش‌کارت) رو از data/ واقعی
# کپی می‌کنیم تا load_lesson کار کنه - بدون این‌که تست هیچ‌وقت چیزی رو تو
# data/ واقعی بنویسه (همه‌ی نوشتن‌ها روی _TMP_DATA_DIR انجام می‌شه).
import shutil
for _content_file in ("lesson1.json", "test_bank_L1.json", "flashcards_L1.json"):
    _src = _REAL_DATA_DIR / _content_file
    if _src.exists():
        shutil.copy(_src, _TMP_DATA_DIR / _content_file)

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import (
    SendMessage,
    AnswerCallbackQuery,
    EditMessageReplyMarkup,
    EditMessageText,
    DeleteMessage,
)
from aiogram.methods.base import TelegramMethod
from aiogram.types import Message as TgMessage, Chat, User, Update, CallbackQuery

from bot.handlers import onboarding, profile_onboarding, diagnostic
import bot.profile_store as profile_store
import bot.onboarding_store as onboarding_store

_next_id = [1]


def _new_id() -> int:
    _next_id[0] += 1
    return _next_id[0]


class FakeBot(Bot):
    """جایگزین aiogram.Bot که به‌جای درخواست HTTP واقعی، متدها رو ضبط
    می‌کنه. تنها نقطه‌ی تماس بین aiogram و «شبکه» متد __call__ است، پس
    override کردن همینجا کافیه - بقیه‌ی کد پروژه (bot.send_message,
    message.answer, callback.answer, ...) بدون تغییر کار می‌کنه."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.sent: list[SendMessage] = []
        # این فاز: پیام‌های ویرایش‌شده به خلاصه (grade/goal/daily_time) و
        # id پیام‌های حذف‌شده (سؤال متنی نام/سن) رو هم ضبط می‌کنیم، چون
        # رفتار جدید (شلوغی چت) از همین دو مسیر تست می‌شه.
        self.edited_texts: list[str] = []
        self.deleted_message_ids: list[int] = []

    async def __call__(self, method: TelegramMethod, request_timeout: int | None = None):
        if isinstance(method, SendMessage):
            self.sent.append(method)
            return TgMessage(
                message_id=_new_id(),
                date=int(time.time()),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text or "",
            )
        if isinstance(method, AnswerCallbackQuery):
            return True
        if isinstance(method, EditMessageReplyMarkup):
            return True
        if isinstance(method, EditMessageText):
            self.edited_texts.append(method.text or "")
            return True
        if isinstance(method, DeleteMessage):
            self.deleted_message_ids.append(method.message_id)
            return True
        raise RuntimeError(f"تماس API پیش‌بینی‌نشده در تست: {type(method).__name__}")


# Router های aiogram فقط یه‌بار قابل attach شدن به یه Dispatcher هستن (خطای
# RuntimeError می‌ده اگه دوباره include بشن) - دقیقاً مثل برنامه‌ی واقعی که
# فقط یه Dispatcher تو main.py می‌سازه. برای همین اینجا هم فقط یه Dispatcher
# یه‌بار ساخته می‌شه؛ برای شبیه‌سازی "ری‌استارت بات" (از دست رفتن FSM state)
# به‌جای ساخت Dispatcher جدید، فقط storage عوض می‌شه - چون تو main.py واقعی
# هم این دقیقاً همون چیزیه که با MemoryStorage روی ری‌استارت اتفاق می‌افته.
_dp: Dispatcher | None = None


def get_dispatcher() -> Dispatcher:
    global _dp
    if _dp is None:
        _dp = Dispatcher(storage=MemoryStorage())
        _dp.include_router(onboarding.router)
        _dp.include_router(profile_onboarding.router)
        _dp.include_router(diagnostic.router)
    return _dp


def reset_fsm_storage() -> None:
    """شبیه‌سازی ری‌استارت بات: محتوای MemoryStorage (که فقط تو RAM هست)
    خالی می‌شه، دقیقاً همون اتفاقی که با ری‌استارت واقعی بات می‌افته -
    بدون نیاز به ساخت Dispatcher/Router جدید."""
    get_dispatcher().storage.storage.clear()


def make_dispatcher() -> tuple[Dispatcher, FakeBot]:
    dp = get_dispatcher()
    bot = FakeBot(token="123456:TESTTESTTESTTESTTESTTESTTESTTESTTES")
    return dp, bot


def make_user(user_id: int, chat_id: int | None = None) -> User:
    return User(id=user_id, is_bot=False, first_name="Test")


def make_message(user: User, text: str, chat_id: int) -> TgMessage:
    return TgMessage(
        message_id=_new_id(),
        date=int(time.time()),
        chat=Chat(id=chat_id, type="private"),
        from_user=user,
        text=text,
    )


def make_callback(user: User, data: str, chat_id: int) -> CallbackQuery:
    msg = TgMessage(
        message_id=_new_id(),
        date=int(time.time()),
        chat=Chat(id=chat_id, type="private"),
        from_user=user,
        text="(prompt)",
    )
    return CallbackQuery(
        id=str(_new_id()),
        from_user=user,
        chat_instance="test-chat-instance",
        data=data,
        message=msg,
    )


async def send_text(dp: Dispatcher, bot: FakeBot, user: User, text: str) -> None:
    update = Update(update_id=_new_id(), message=make_message(user, text, user.id))
    await dp.feed_update(bot, update)


async def click(dp: Dispatcher, bot: FakeBot, user: User, data: str) -> None:
    update = Update(update_id=_new_id(), callback_query=make_callback(user, data, user.id))
    await dp.feed_update(bot, update)


def last_text(bot: FakeBot) -> str:
    return bot.sent[-1].text or ""


def texts(bot: FakeBot) -> list[str]:
    return [m.text or "" for m in bot.sent]


def last_buttons(bot: FakeBot) -> list[str]:
    """متن دکمه‌های inline keyboard آخرین پیام ارسالی - چون متن گزینه‌های
    شروع سریع/تشخیصی و پروفایل تو دکمه‌ست، نه تو متن پیام. اگه آخرین پیام
    reply keyboard (منوی پایین صفحه) داشته باشه یا اصلاً کیبوردی نداشته
    باشه، لیست خالی برمی‌گرده - نه کرش."""
    markup = bot.sent[-1].reply_markup
    if markup is None or not hasattr(markup, "inline_keyboard"):
        return []
    return [btn.text for row in markup.inline_keyboard for btn in row]


# ==================== سناریوها ====================

async def scenario_full_happy_path():
    """کاربر کاملاً جدید، کل ۶ مرحله رو با جواب معتبر طی می‌کنه و باید به
    صفحه‌ی انتخاب شروع سریع/آزمون تشخیصی برسه."""
    dp, bot = make_dispatcher()
    user = make_user(111001)

    await send_text(dp, bot, user, "/start")
    assert "Mentora" in texts(bot)[0], f"پیام معرفی اولیه ارسال نشد: {texts(bot)}"
    assert "اسمت چیه" in last_text(bot), f"سؤال نام پرسیده نشد: {last_text(bot)}"

    await send_text(dp, bot, user, "کیمیا")
    assert "چند سالته" in last_text(bot), f"سؤال سن پرسیده نشد: {last_text(bot)}"

    await send_text(dp, bot, user, "۱۶")  # رقم فارسی
    assert "پایه" in last_text(bot), f"سؤال پایه پرسیده نشد: {last_text(bot)}"

    await click(dp, bot, user, "profile_grade:g10")
    assert "هدفت" in last_text(bot), f"سؤال هدف پرسیده نشد: {last_text(bot)}"

    await click(dp, bot, user, "profile_goal:konkur")
    assert "چقدر وقت" in last_text(bot), f"سؤال زمان مطالعه پرسیده نشد: {last_text(bot)}"

    await click(dp, bot, user, "profile_time:30_60")
    assert "🚀 شروع سریع" in last_buttons(bot) and "🎯 آزمون تشخیصی بزنم" in last_buttons(bot), (
        f"بعد از پایان پروفایل باید انتخاب شروع سریع/تشخیصی نشون داده بشه: {last_buttons(bot)}"
    )

    profile = profile_store.get_profile(111001)
    assert profile["name"] == "کیمیا"
    assert profile["age"] == 16
    assert profile["grade"] == "g10"
    assert profile["goal"] == "konkur"
    assert profile["daily_minutes"] == "30_60"
    assert "completed_at" in profile
    assert profile_store.is_profile_complete(profile)


async def scenario_invalid_name_then_valid():
    dp, bot = make_dispatcher()
    user = make_user(111002)
    await send_text(dp, bot, user, "/start")

    await send_text(dp, bot, user, "")  # خالی (تلگرام معمولاً همچین چیزی نمی‌فرسته ولی دفاعی چک می‌کنیم)
    # متن خالی truthy نیست، پس F.text رد می‌شه و هندلر fallback (نوع پیام
    # نامعتبر) صداش می‌زنه - در عمل هم قابل قبوله (کاربر بازم گیر نمی‌کنه)
    assert "متن بفرست" in last_text(bot) or "اسم معتبر" in last_text(bot), last_text(bot)

    await send_text(dp, bot, user, "12345")  # فقط عدد
    assert "اسم معتبر" in last_text(bot), f"نام عددی باید رد بشه: {last_text(bot)}"

    await send_text(dp, bot, user, "ص" * 60)  # خیلی طولانی
    assert "اسم معتبر" in last_text(bot), "نام خیلی طولانی باید رد بشه"

    await send_text(dp, bot, user, "/notacommand")  # شبه‌دستور ولی نه یه Command ثبت‌شده - باید توسط اعتبارسنجی خودمون رد بشه
    assert "اسم معتبر" in last_text(bot), f"چیزی شبیه دستور باید رد بشه: {last_text(bot)}"

    await send_text(dp, bot, user, "پریا")
    assert "چند سالته" in last_text(bot), "بعد از نام معتبر باید سؤال سن بیاد"
    assert profile_store.get_profile(111002)["name"] == "پریا"


async def scenario_invalid_age_then_valid():
    dp, bot = make_dispatcher()
    user = make_user(111003)
    await send_text(dp, bot, user, "/start")
    await send_text(dp, bot, user, "سینا")
    assert "چند سالته" in last_text(bot)

    await send_text(dp, bot, user, "abc")
    assert "فقط به‌صورت عدد" in last_text(bot), "سن غیرعددی باید رد بشه"

    await send_text(dp, bot, user, "500")
    assert "سن معتبر" in last_text(bot), "سن خارج از بازه باید رد بشه"

    await send_text(dp, bot, user, "-5")
    assert "فقط به‌صورت عدد" in last_text(bot), "سن منفی باید رد بشه"

    await send_text(dp, bot, user, "17")
    assert "پایه" in last_text(bot), "بعد از سن معتبر باید سؤال پایه بیاد"
    assert profile_store.get_profile(111003)["age"] == 17


async def scenario_resume_after_restart():
    """شبیه‌سازی ری‌استارت بات: FSM (MemoryStorage) با یه Dispatcher جدید
    از صفر ساخته می‌شه (state از دست می‌ره)، ولی profile_store روی
    "دیسک" (فایل موقت تست) باقی می‌مونه. /start بعدی باید دقیقاً از فیلد
    ناقص بعدی ادامه بده، نه از اول."""
    user = make_user(111004)

    dp1, bot1 = make_dispatcher()
    await send_text(dp1, bot1, user, "/start")
    await send_text(dp1, bot1, user, "شیما")
    await send_text(dp1, bot1, user, "15")
    assert "پایه" in last_text(bot1)
    # کاربر اینجا رهاش می‌کنه - قبل از انتخاب پایه. نه گزینه‌ای کلیک می‌کنه.

    # --- "ری‌استارت بات" ---
    reset_fsm_storage()
    dp2, bot2 = make_dispatcher()
    await send_text(dp2, bot2, user, "/start")
    assert any("ادامه بدیم" in t for t in texts(bot2)), f"پیام resume نشون داده نشد: {texts(bot2)}"
    # نباید دوباره معرفی کامل + سؤال نام رو ببینه
    assert not any("اسمت چیه" in t for t in texts(bot2)), "نباید از اول (نام) شروع بشه"
    assert "پایه" in texts(bot2)[-1], f"باید مستقیم سراغ سؤال پایه بره: {texts(bot2)}"

    await click(dp2, bot2, user, "profile_grade:g11")
    assert "هدفت" in last_text(bot2)

    profile = profile_store.get_profile(111004)
    assert profile["name"] == "شیما"
    assert profile["age"] == 15
    assert profile["grade"] == "g11"


async def scenario_returning_user_skips_profile():
    """کاربری که قبلاً کل onboarding (پروفایل + انتخاب مسیر) رو تموم کرده،
    نباید دوباره هیچ‌کدوم از سؤال‌های پروفایل رو ببینه."""
    user = make_user(111005)
    onboarding_store.mark_onboarded(111005, path="quick")
    for field, value in [
        ("name", "مهشید"), ("age", 30), ("grade", "grad"),
        ("goal", "deep_learning"), ("daily_minutes", "gt60"),
    ]:
        profile_store.save_profile_field(111005, field, value)

    dp, bot = make_dispatcher()
    await send_text(dp, bot, user, "/start")
    assert not any("اسمت چیه" in t for t in texts(bot)), "کاربر برگشتی نباید سؤال پروفایل ببینه"
    assert "🚀 شروع سریع" not in last_buttons(bot), "کاربر برگشتی نباید دوباره انتخاب مسیر ببینه"
    assert "خوش اومدی" in last_text(bot)


async def scenario_profile_complete_but_path_not_chosen():
    """کاربری که پروفایلش کامله ولی هنوز مسیر شروع سریع/تشخیصی رو انتخاب
    نکرده (has_onboarded=False) - باید مستقیم بره سراغ همون انتخاب، بدون
    تکرار سؤال‌های پروفایل."""
    user = make_user(111006)
    for field, value in [
        ("name", "پریسا"), ("age", 18), ("grade", "g12"),
        ("goal", "school_exam"), ("daily_minutes", "lt15"),
    ]:
        profile_store.save_profile_field(111006, field, value)
    profile_store.mark_profile_complete(111006)
    assert not onboarding_store.has_onboarded(111006)

    dp, bot = make_dispatcher()
    await send_text(dp, bot, user, "/start")
    assert not any("اسمت چیه" in t for t in texts(bot)), "نباید دوباره سؤال پروفایل بپرسه"
    assert "🚀 شروع سریع" in last_buttons(bot) and "🎯 آزمون تشخیصی بزنم" in last_buttons(bot)


async def scenario_invalid_callback_key_ignored():
    """callback_data دستکاری‌شده/ناشناخته (مثلاً کلاینت قدیمی یا دستکاری
    دستی) نباید باعث ذخیره‌ی دیتای نامعتبر یا کرش بشه."""
    dp, bot = make_dispatcher()
    user = make_user(111007)
    await send_text(dp, bot, user, "/start")
    await send_text(dp, bot, user, "علی")
    await send_text(dp, bot, user, "20")
    assert "پایه" in last_text(bot)

    await click(dp, bot, user, "profile_grade:not_a_real_grade")
    # نباید جلو بره؛ باید همچنان تو همون مرحله (سؤال پایه) بمونه
    assert "پایه" in last_text(bot), "کلید نامعتبر نباید باعث پیشروی بشه"
    profile = profile_store.get_profile(111007)
    assert "grade" not in profile, "کلید نامعتبر نباید ذخیره بشه"

    await click(dp, bot, user, "profile_grade:g9")
    assert "هدفت" in last_text(bot)
    assert profile_store.get_profile(111007)["grade"] == "g9"


async def scenario_dev_reset_clears_profile():
    user = make_user(999001)  # داخل DEV_TEST_USER_IDS تنظیم‌شده در بالای فایل
    dp, bot = make_dispatcher()
    await send_text(dp, bot, user, "/start")
    await send_text(dp, bot, user, "کاربر تست")
    assert profile_store.get_profile(999001) is not None

    await send_text(dp, bot, user, "/dev_reset")
    assert profile_store.get_profile(999001) is None, "پروفایل باید بعد از dev_reset پاک بشه"

    await send_text(dp, bot, user, "/start")
    assert "اسمت چیه" in last_text(bot), "بعد از dev_reset باید از اول شروع بشه"


async def scenario_storage_is_separate_file():
    """پروفایل باید تو فایل مستقل خودش باشه، نه تو onboarding_status.json
    یا progress.json."""
    user = make_user(111008)
    dp, bot = make_dispatcher()
    await send_text(dp, bot, user, "/start")
    await send_text(dp, bot, user, "کاربر جدا")

    profile_file = _TMP_DATA_DIR / "user_profile.json"
    assert profile_file.exists(), "فایل user_profile.json باید ساخته شده باشه"
    with open(profile_file, encoding="utf-8") as f:
        data = json.load(f)
    assert "111008" in data
    assert data["111008"]["name"] == "کاربر جدا"

    onboarding_file = _TMP_DATA_DIR / "onboarding_status.json"
    if onboarding_file.exists():
        with open(onboarding_file, encoding="utf-8") as f:
            onb_data = json.load(f)
        assert "111008" not in onb_data, "قبل از پایان کامل onboarding نباید تو onboarding_status.json ثبت بشه"

    progress_file = _TMP_DATA_DIR / "progress.json"
    assert not progress_file.exists(), "پروفایل نباید هیچ اثری روی progress.json بذاره"


async def scenario_previous_question_deleted_for_text_fields():
    """کاهش شلوغی چت، بخش نام/سن: بعد از هر جواب معتبر، پیام سؤال قبلی
    بات باید حذف بشه (delete_message صدا زده بشه)."""
    dp, bot = make_dispatcher()
    user = make_user(111009)
    await send_text(dp, bot, user, "/start")
    assert bot.deleted_message_ids == [], "قبل از هیچ جواب معتبری نباید حذفی انجام بشه"

    await send_text(dp, bot, user, "بهار")
    assert len(bot.deleted_message_ids) == 1, "بعد از نام معتبر باید پیام سؤال نام حذف بشه"

    # یه جواب نامعتبر سن - نباید حذف اضافه‌ای اتفاق بیفته
    await send_text(dp, bot, user, "abc")
    assert len(bot.deleted_message_ids) == 1, "جواب نامعتبر نباید باعث حذف بشه"

    await send_text(dp, bot, user, "13")
    assert len(bot.deleted_message_ids) == 2, "بعد از سن معتبر باید پیام سؤال سن حذف بشه"


async def scenario_button_questions_collapse_to_summary():
    """کاهش شلوغی چت، بخش پایه/هدف/زمان مطالعه: هر سؤال دکمه‌ای بعد از
    انتخاب باید به یه خلاصه‌ی کوتاه تبدیل بشه (edit_text)، نه فقط حذف
    کیبورد."""
    dp, bot = make_dispatcher()
    user = make_user(111010)
    await send_text(dp, bot, user, "/start")
    await send_text(dp, bot, user, "نگار")
    await send_text(dp, bot, user, "17")

    await click(dp, bot, user, "profile_grade:g10")
    assert any("✅ پایه: دهم" == t for t in bot.edited_texts), bot.edited_texts

    await click(dp, bot, user, "profile_goal:konkur")
    assert any(t.startswith("✅ هدف:") and "کنکور" in t for t in bot.edited_texts), bot.edited_texts

    await click(dp, bot, user, "profile_time:30_60")
    assert any(t.startswith("✅ زمان مطالعه:") for t in bot.edited_texts), bot.edited_texts


async def scenario_personalized_completion_message():
    """پیام پایان onboarding باید دقیقاً اسم واقعی همون کاربر رو داشته
    باشه، قبل از دعوت به شروع سریع/آزمون تشخیصی."""
    dp, bot = make_dispatcher()
    user = make_user(111011)
    await send_text(dp, bot, user, "/start")
    await send_text(dp, bot, user, "کیمیا")
    await send_text(dp, bot, user, "16")
    await click(dp, bot, user, "profile_grade:g10")
    await click(dp, bot, user, "profile_goal:konkur")
    await click(dp, bot, user, "profile_time:30_60")

    assert any("کیمیا، از همین الان با هم شروع می‌کنیم" in t for t in texts(bot)), texts(bot)
    # و بعدش هنوز باید همون دعوت موجود (شروع سریع/تشخیصی) بیاد
    assert "🚀 شروع سریع" in last_buttons(bot)


async def scenario_profile_menu_shows_real_data():
    """دکمه‌ی «پروفایل من» فقط باید داده‌ی واقعی از profile_store رو نشون
    بده - نام، سن، لیبل خوانای پایه/هدف/زمان مطالعه."""
    user = make_user(111012)
    onboarding_store.mark_onboarded(111012, path="quick")
    for field, value in [
        ("name", "آرمین"), ("age", 14), ("grade", "g8"),
        ("goal", "weak_points"), ("daily_minutes", "15_30"),
    ]:
        profile_store.save_profile_field(111012, field, value)
    profile_store.mark_profile_complete(111012)

    dp, bot = make_dispatcher()
    await send_text(dp, bot, user, "👤 پروفایل من")
    text = last_text(bot)
    assert "آرمین" in text
    assert "14" in text
    assert "هشتم" in text, f"لیبل خوانای پایه باید نشون داده بشه: {text}"
    assert "تقویت نقاط ضعف" in text, f"لیبل خوانای هدف باید نشون داده بشه: {text}"
    assert "۱۵ تا ۳۰ دقیقه" in text, f"لیبل خوانای زمان مطالعه باید نشون داده بشه: {text}"


async def scenario_profile_menu_when_incomplete():
    """اگه پروفایل هنوز کامل نشده، نباید هیچ داده‌ی fake/ناقصی نشون داده
    بشه - فقط یه پیام روشن که هنوز کامل نیست."""
    user = make_user(111013)
    profile_store.save_profile_field(111013, "name", "نیم‌کاره")

    dp, bot = make_dispatcher()
    await send_text(dp, bot, user, "👤 پروفایل من")
    assert "کامل نشده" in last_text(bot), last_text(bot)
    assert "نیم‌کاره" not in last_text(bot), "نباید داده‌ی ناقص رو نصفه‌نیمه نشون بده"


SCENARIOS = [
    scenario_full_happy_path,
    scenario_invalid_name_then_valid,
    scenario_invalid_age_then_valid,
    scenario_resume_after_restart,
    scenario_returning_user_skips_profile,
    scenario_profile_complete_but_path_not_chosen,
    scenario_invalid_callback_key_ignored,
    scenario_dev_reset_clears_profile,
    scenario_storage_is_separate_file,
    scenario_previous_question_deleted_for_text_fields,
    scenario_button_questions_collapse_to_summary,
    scenario_personalized_completion_message,
    scenario_profile_menu_shows_real_data,
    scenario_profile_menu_when_incomplete,
]


async def main() -> int:
    passed, failed = 0, 0
    for scenario in SCENARIOS:
        name = scenario.__name__
        try:
            await scenario()
            print(f"✅ PASS - {name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ FAIL - {name}: {e}")
            failed += 1
        except Exception:
            print(f"💥 ERROR - {name}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed} passed, {failed} failed (data dir: {_TMP_DATA_DIR})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
