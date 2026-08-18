"""
Onboarding / User Profile: قدم اول از فرآیند /start برای کاربر جدید،
قبل از انتخاب موجود «شروع سریع / آزمون تشخیصی» (diagnostic.py) و قبل از
S1. طبق اصل Personalization Engine: قبل از هر آموزشی، یه پروفایل کوتاه از
کاربر می‌سازیم - نام، سن، پایه، هدف یادگیری، زمان مطالعه‌ی روزانه.

ذخیره‌سازی در bot/profile_store.py، جدا از onboarding_status.json (مسیر
شروع سریع/تشخیصی) و progress.json (پیشرفت درسی).

Resume: چون FSM state (MemoryStorage) با ری‌استارت بات پاک می‌شه، بعد از
هر جواب معتبر بلافاصله در profile_store ذخیره می‌شه؛ start_profile_flow
(نقطه‌ی ورود از onboarding.py::handle_start) با get_next_missing_field
دقیقاً از اولین فیلد ناقص ادامه می‌ده، نه از اول.

اتصال به مرحله‌ی بعد (send_onboarding_choice) از diagnostic.py وارد
می‌شه و بدون هیچ تغییری در diagnostic.py صدا زده می‌شه - دقیقاً هم‌الگوی
اتصال diagnostic.py به enter_lesson() در lesson.py.

فیلدهای شمارشی (پایه/هدف/زمان مطالعه) با دکمه پرسیده می‌شن، نه متن آزاد -
یعنی جواب نامعتبر برای این‌ها اصلاً ممکن نیست. فقط نام و سن متن آزادن و
نیاز به اعتبارسنجی و re-ask دارن.

--- شلوغی چت (این فاز) ---
برای نام/سن (سؤال متنی): بعد از یه جواب معتبر، پیام سؤال قبلی بات حذف
می‌شه (best-effort - _delete_last_prompt). id همون پیام سؤال تو FSM data
(کلید last_prompt_msg_id) نگه داشته می‌شه، چون تنها نقطه‌ای که بعداً به
پیام قبلی دسترسی داره همینه (FSM data، نه تلگرام).
برای پایه/هدف/زمان مطالعه (سؤال دکمه‌ای): به‌جای فقط حذف کیبورد، خودِ متن
پیام با _finalize_choice_message به یه خلاصه‌ی کوتاه («✅ پایه: دهم» و
مشابه) تبدیل می‌شه - چون callback.message مستقیم در دسترسه، نیازی به
ذخیره‌ی جدای id نیست.
"""
from __future__ import annotations

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from bot.states import ProfileOnboarding
from bot.keyboards import (
    grade_choice_keyboard,
    goal_choice_keyboard,
    daily_time_choice_keyboard,
    GRADE_OPTIONS,
    GOAL_OPTIONS,
    DAILY_TIME_OPTIONS,
)
from bot.profile_store import get_profile, save_profile_field, mark_profile_complete, get_next_missing_field
from bot.handlers.diagnostic import send_onboarding_choice

router = Router()

_MAX_NAME_LENGTH = 40
_MIN_AGE = 5
_MAX_AGE = 90

_GRADE_KEYS = {key for key, _ in GRADE_OPTIONS}
_GOAL_KEYS = {key for key, _ in GOAL_OPTIONS}
_TIME_KEYS = {key for key, _ in DAILY_TIME_OPTIONS}

# رقم‌های فارسی/عربی -> انگلیسی، چون کاربر ممکنه سنش رو با کیبورد فارسی
# تایپ کنه (مثلاً «۱۶» به‌جای «16»).
_DIGIT_MAP = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def _normalize_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


async def _delete_last_prompt(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """پیام سؤال متنی قبلی (نام/سن) رو بعد از یه جواب معتبر حذف می‌کنه تا
    چت شلوغ نمونه. best-effort: اگه id ثبت نشده باشه (مثلاً بعد از
    ری‌استارت بات، چون FSM data پاک شده) یا خودِ حذف به هر دلیلی رد بشه،
    بی‌سروصدا نادیده گرفته می‌شه - نباید هیچ‌وقت جلوی ادامه‌ی فلو رو بگیره."""
    data = await state.get_data()
    msg_id = data.get("last_prompt_msg_id")
    if not msg_id:
        return
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


async def _finalize_choice_message(callback: CallbackQuery, summary_text: str) -> None:
    """پیام سؤال دکمه‌ای (پایه/هدف/زمان مطالعه) رو بعد از انتخاب کاربر، به‌جای
    فقط حذف کیبورد، به یه خلاصه‌ی کوتاه («✅ پایه: دهم») تبدیل می‌کنه - تا
    متن کامل سؤال + گزینه‌ها تو چت نمونه. اگه ویرایش متن به هر دلیلی ممکن
    نبود (مثلاً پیام خیلی قدیمیه)، حداقل کیبورد حذف می‌شه که کاربر دوباره
    نتونه روش کلیک کنه."""
    try:
        await callback.message.edit_text(summary_text, reply_markup=None)
    except Exception:
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass


async def start_profile_flow(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    """نقطه‌ی ورود واحد از onboarding.py::handle_start. بر اساس اینکه
    پروفایل کاربر تا کجا کامله، یا از اول شروع می‌کنه، یا دقیقاً از اولین
    فیلد ناقص ادامه می‌ده، یا (اگه پروفایل کامل بود ولی مسیر quick/diagnostic
    هنوز انتخاب نشده) مستقیم می‌ره سراغ send_onboarding_choice موجود."""
    profile = get_profile(user_id)

    if profile is None:
        await bot.send_message(
            chat_id,
            "سلام! 🌟 به <b>Mentora</b> خوش اومدی.\n"
            "چند سؤال کوتاه بپرسم تا بشناسمت؟ 🙂",
            parse_mode="HTML",
        )
        await _ask_name(bot, chat_id, state)
        return

    missing = get_next_missing_field(profile)
    if missing is None:
        # پروفایل کامله ولی مسیر شروع سریع/تشخیصی هنوز انتخاب نشده (کاربر
        # بین پایان پروفایل و اون انتخاب رها کرده بود) - می‌ریم سراغ همون
        # مرحله‌ی موجود، بدون تکرار سؤال‌های پروفایل.
        await send_onboarding_choice(bot, chat_id)
        return

    await bot.send_message(chat_id, "بریم ادامه بدیم 🙂")
    await _resume_at(missing, bot, chat_id, state)


async def _resume_at(field: str, bot: Bot, chat_id: int, state: FSMContext) -> None:
    if field == "name":
        await _ask_name(bot, chat_id, state)
    elif field == "age":
        await _ask_age(bot, chat_id, state)
    elif field == "grade":
        await _ask_grade(bot, chat_id, state)
    elif field == "goal":
        await _ask_goal(bot, chat_id, state)
    elif field == "daily_minutes":
        await _ask_daily_time(bot, chat_id, state)


# --- نام ---

async def _ask_name(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(ProfileOnboarding.name)
    msg = await bot.send_message(chat_id, "اسمت چیه؟ ✍️")
    await state.update_data(last_prompt_msg_id=msg.message_id)


@router.message(ProfileOnboarding.name, F.text)
async def handle_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not name or name.startswith("/") or len(name) > _MAX_NAME_LENGTH or name.isdigit():
        await message.answer("یه اسم معتبر بفرست (بدون عدد یا دستور) 🙂")
        return
    save_profile_field(message.from_user.id, "name", name)
    await _delete_last_prompt(message.bot, message.chat.id, state)
    await _ask_age(message.bot, message.chat.id, state)


@router.message(ProfileOnboarding.name)
async def handle_name_invalid_type(message: Message, state: FSMContext) -> None:
    # کاربر چیزی غیر از متن فرستاده (عکس، استیکر و...)
    await message.answer("لطفاً اسمت رو به‌صورت متن بفرست ✍️")


# --- سن ---

async def _ask_age(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(ProfileOnboarding.age)
    msg = await bot.send_message(chat_id, "چند سالته؟ 🔢")
    await state.update_data(last_prompt_msg_id=msg.message_id)


@router.message(ProfileOnboarding.age, F.text)
async def handle_age(message: Message, state: FSMContext) -> None:
    raw = _normalize_digits(message.text.strip())
    if not raw.isdigit():
        await message.answer("سن رو فقط به‌صورت عدد بفرست، مثلاً ۱۶ 🔢")
        return
    age = int(raw)
    if not (_MIN_AGE <= age <= _MAX_AGE):
        await message.answer(f"یه سن معتبر بین {_MIN_AGE} تا {_MAX_AGE} بفرست 🔢")
        return
    save_profile_field(message.from_user.id, "age", age)
    await _delete_last_prompt(message.bot, message.chat.id, state)
    await _ask_grade(message.bot, message.chat.id, state)


@router.message(ProfileOnboarding.age)
async def handle_age_invalid_type(message: Message, state: FSMContext) -> None:
    await message.answer("سن رو فقط به‌صورت عدد بفرست 🔢")


# --- پایه/کلاس ---

async def _ask_grade(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(ProfileOnboarding.grade)
    await bot.send_message(chat_id, "پایه/کلاست چیه؟ 🎓", reply_markup=grade_choice_keyboard())


@router.callback_query(ProfileOnboarding.grade, F.data.startswith("profile_grade:"))
async def handle_grade(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    key = callback.data.split(":", 1)[1]
    if key not in _GRADE_KEYS:
        return
    save_profile_field(callback.from_user.id, "grade", key)
    label = dict(GRADE_OPTIONS)[key]
    await _finalize_choice_message(callback, f"✅ پایه: {label}")
    await _ask_goal(callback.bot, callback.message.chat.id, state)


# --- هدف یادگیری ---

async def _ask_goal(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(ProfileOnboarding.goal)
    await bot.send_message(chat_id, "هدفت از یادگیری چیه؟ 🎯", reply_markup=goal_choice_keyboard())


@router.callback_query(ProfileOnboarding.goal, F.data.startswith("profile_goal:"))
async def handle_goal(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    key = callback.data.split(":", 1)[1]
    if key not in _GOAL_KEYS:
        return
    save_profile_field(callback.from_user.id, "goal", key)
    label = dict(GOAL_OPTIONS)[key]
    await _finalize_choice_message(callback, f"✅ هدف: {label}")
    await _ask_daily_time(callback.bot, callback.message.chat.id, state)


# --- زمان مطالعه‌ی روزانه ---

async def _ask_daily_time(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(ProfileOnboarding.daily_time)
    await bot.send_message(
        chat_id,
        "روزانه چقدر وقت داری برای مطالعه بذاری؟ ⏱",
        reply_markup=daily_time_choice_keyboard(),
    )


@router.callback_query(ProfileOnboarding.daily_time, F.data.startswith("profile_time:"))
async def handle_daily_time(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    key = callback.data.split(":", 1)[1]
    if key not in _TIME_KEYS:
        return
    save_profile_field(callback.from_user.id, "daily_minutes", key)
    mark_profile_complete(callback.from_user.id)
    label = dict(DAILY_TIME_OPTIONS)[key]
    await _finalize_choice_message(callback, f"✅ زمان مطالعه: {label}")
    await state.set_state(None)

    # فاز 5C: پیام پایانی جدای «{name}، از همین الان شروع می‌کنیم» عمداً
    # حذف شد - باعث دو تا خوش‌آمد پشت‌سرهم می‌شد، چون send_onboarding_choice
    # (diagnostic.py) خودش الان یه خوش‌آمد شخصی و زمان‌محور
    # (time_based_greeting، با همین اسم از profile_store) می‌فرسته. یه
    # تجربه‌ی یکپارچه به‌جای دو پیام جدا.
    await send_onboarding_choice(callback.bot, callback.message.chat.id)
