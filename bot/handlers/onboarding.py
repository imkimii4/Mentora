"""
/start و منوی اصلی.

کاربر جدید در برابر برگشتی از onboarding_store.py تشخیص داده می‌شه، نه از
FSM state - چون handle_start همیشه state.clear() می‌زنه و هر state قبلی رو
پاک می‌کنه؛ تنها منبع پایدار onboarding_status.json روی دیسکه.

کاربر جدید: قبل از هرچیز از مسیر Onboarding/Profile (profile_onboarding.py)
رد می‌شه - نام/سن/پایه/هدف/زمان مطالعه - و بعدش انتخاب مسیر (شروع سریع /
آزمون تشخیصی) از diagnostic.py؛ هیچ reply keyboardی تا پایان همه‌ی این‌ها
فرستاده نمی‌شه. start_profile_flow خودش تشخیص می‌ده کاربر کاملاً جدیده یا
باید از یه فیلد ناقص ادامه بده (رجوع به profile_onboarding.py).
کاربر برگشتی: دقیقاً همون رفتار قبلی (خوش‌آمد + منوی اصلی)، بدون تغییر.

گارد DiagnosticFlow روی ۴ دکمه‌ی منوی اصلی: چون این‌ها F.text ساده‌ن (بدون
فیلتر state) و بدون تغییر می‌تونستن Diagnostic رو وسط کار قطع کنن. ریسک
اصلیش با این پلن از ریشه حذف شده (تا پایان Diagnostic اصلاً reply keyboardی
رو صفحه نیست)، این گارد فقط لایه‌ی دفاعی دومه برای حالت لبه‌ای که یه کیبورد
قدیمی از قبل مونده باشه. همین منطق دقیقاً برای ProfileOnboarding هم صادقه
(اونم قبل از هر reply keyboardی اتفاق می‌افته) - گارد جدا براش لازم نیست.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.states import DiagnosticFlow
from bot.keyboards import (
    main_menu_reply_keyboard,
    section_list_keyboard,
    GRADE_OPTIONS,
    GOAL_OPTIONS,
    DAILY_TIME_OPTIONS,
)
from bot.data_loader import load_lesson
from bot.handlers.lesson import enter_lesson
from bot.handlers.practice import prompt_test_count, prompt_flashcard_count
from bot.handlers.profile_onboarding import start_profile_flow
from bot.handlers.diagnostic import time_based_greeting
from bot.onboarding_store import has_onboarded, clear_onboarded
from bot.profile_store import get_profile, clear_profile, is_profile_complete
from bot.learning_state_store import clear_learning_state, get_streak
from bot.profile_display_store import get_display, clear_display
from bot.practice_store import get_session_accuracies
from bot.lesson_quiz_store import get_quiz_answers
from bot.title_rank import get_title
from bot.event_log import log_event
from config import DEV_TEST_USER_IDS

router = Router()

_DIAGNOSTIC_STATE_NAMES = {
    DiagnosticFlow.q1.state,
    DiagnosticFlow.q2.state,
    DiagnosticFlow.q3.state,
}


async def _in_diagnostic(state: FSMContext) -> bool:
    current = await state.get_state()
    return current in _DIAGNOSTIC_STATE_NAMES


@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    profile = get_profile(user_id)

    # فیکس فاز 5B (باید حفظ بشه): قبل از تصمیم بر اساس has_onboarded، اول
    # باید پروفایل کامل باشه - وگرنه کاربری که وسط سؤال‌های پروفایل رها
    # کرده (و هنوز onboarded نشده) با /start دوباره از صفر پرتاب می‌شد،
    # به‌جای ادامه از همون فیلد ناقص. get_next_missing_field/start_profile_flow
    # خودش تشخیص می‌ده از کجا ادامه بده.
    if not is_profile_complete(profile):
        # log_event("start") فقط یه‌بار، برای اولین /start واقعی کاربر - نه
        # هر بار که resume می‌شه. تشخیصش از روی پروفایل: اگه هنوز هیچ فیلدی
        # ثبت نشده، این واقعاً اولین ورود کاربره.
        if profile is None:
            log_event(user_id, "start")
        await start_profile_flow(message.bot, message.chat.id, user_id, state)
        return

    if has_onboarded(user_id):
        log_event(user_id, "return")
        lesson = load_lesson("L1")
        subject = lesson.get("subject", "")
        lesson_title = lesson.get("lesson_title") or "درس اول"

        # فاز 5C: خوش‌آمد ثابت قبلی جای خودش رو به خوش‌آمد شخصی و
        # زمان‌محور (نام از profile + ساعت محلی Asia/Tehran) داد -
        # time_based_greeting هم‌الگوی همون چیزیه که send_onboarding_choice
        # تو diagnostic.py برای کاربر تازه‌وارد استفاده می‌کنه.
        await message.answer(
            f"{time_based_greeting(profile.get('name'))}\n\n"
            f"📚 داری «{lesson_title}» رو از درس <b>{subject}</b> یاد می‌گیری.\n"
            "قدم‌به‌قدم و به شکل تعاملی، بدون نیاز به خرید کتاب جداگونه.\n\n"
            "می‌تونی درس رو از ابتدا و به‌ترتیب دنبال کنی، یا با «📑 انتخاب بخش» مستقیماً سراغ بخش موردنظرت بری.\n\n"
            "از دکمه‌های پایین صفحه شروع کن 👇",
            reply_markup=main_menu_reply_keyboard(),
            parse_mode="HTML",
        )
        return

    # پروفایل کامله ولی مسیر شروع سریع/آزمون تشخیصی هنوز انتخاب نشده
    # (کاربر بین پایان پروفایل و اون انتخاب رها کرده بود) - start_profile_flow
    # خودش این حالت رو تشخیص می‌ده و مستقیم می‌ره سراغ send_onboarding_choice،
    # بدون تکرار سؤال‌های پروفایل.
    await start_profile_flow(message.bot, message.chat.id, user_id, state)


# نقطه‌ی واحد ریست برای محیط توسعه. هر بخشی از داده‌ی کاربر که بعداً اضافه
# بشه (Progress، Diagnostic نتایج، Resume state و...) فقط کافیه تابع clear
# شبیه clear_onboarded براش نوشته بشه و به همین لیست اضافه بشه؛ خودِ handler
# و اسم Command دیگه لازم نیست تغییر کنه.
_DEV_RESET_ACTIONS = [
    clear_onboarded,
    clear_profile,
    clear_learning_state,
    clear_display,
]


@router.message(Command("dev_reset"))
async def handle_dev_reset(message: Message, state: FSMContext):
    """دستور توسعه‌ای. فقط برای user_id های داخل DEV_TEST_USER_IDS کار
    می‌کنه؛ برای بقیه بی‌صدا نادیده گرفته می‌شه (عمداً بدون پاسخ، تا وجودش
    برای کاربر عادی لو نره)."""
    user_id = message.from_user.id
    if user_id not in DEV_TEST_USER_IDS:
        return
    for reset_action in _DEV_RESET_ACTIONS:
        reset_action(user_id)
    await state.clear()
    await message.answer("✅ وضعیت کاربر ریست شد. حالا /start بزن.")


@router.message(Command("menu"))
async def handle_menu(message: Message, state: FSMContext):
    # اگه کیبورد پایین به هر دلیلی گم شد یا کاربر خواست مطمئن بشه هست،
    # /menu دوباره نشونش می‌ده. پیشرفت لسون/تست/فلش‌کارت دست‌نخورده می‌مونه.
    await message.answer("منوی اصلی همین پایینه 👇", reply_markup=main_menu_reply_keyboard())


@router.message(F.text == "📖 شروع درس")
async def handle_menu_lesson(message: Message, state: FSMContext):
    if await _in_diagnostic(state):
        await message.answer("اول این ۳ سؤال رو تموم کن 🙂")
        return
    await enter_lesson(message.bot, message.chat.id, state)


@router.message(F.text == "📝 تست بزن")
async def handle_menu_test(message: Message, state: FSMContext):
    if await _in_diagnostic(state):
        await message.answer("اول این ۳ سؤال رو تموم کن 🙂")
        return
    await prompt_test_count(message.bot, message.chat.id, state)


@router.message(F.text == "🎴 فلش‌کارت بخون")
async def handle_menu_flashcard(message: Message, state: FSMContext):
    if await _in_diagnostic(state):
        await message.answer("اول این ۳ سؤال رو تموم کن 🙂")
        return
    await prompt_flashcard_count(message.bot, message.chat.id, state)


@router.message(F.text == "📑 انتخاب بخش")
async def handle_menu_select_section(message: Message, state: FSMContext):
    if await _in_diagnostic(state):
        await message.answer("اول این ۳ سؤال رو تموم کن 🙂")
        return
    # فقط لیست بخش‌ها رو نشون می‌ده؛ ورود واقعی به بخش انتخاب‌شده تو
    # select_section handler در bot/handlers/lesson.py اتفاق می‌افته.
    lesson = load_lesson("L1")
    await message.answer(
        "کدوم بخش رو می‌خوای بخونی؟",
        reply_markup=section_list_keyboard(lesson["sections"]),
    )


@router.message(F.text == "👤 پروفایل من")
async def handle_menu_profile(message: Message, state: FSMContext):
    """نام/سن/پایه/هدف/زمان مطالعه‌ی روزانه از profile_store، درس فعلی از
    data_loader.load_lesson (نه hardcode)، استریک (current/longest) از
    learning_state_store، عنوان/رتبه‌ی dynamic (نه persisted) از title_rank
    بر اساس همون current_streak، آمار سؤال‌های پاسخ‌داده‌شده و درصد موفقیت
    کلی از داده‌ی خام واقعی practice_store + lesson_quiz_store (فلش‌کارت
    عمداً حساب نمی‌شه - فاز 5C، accessor/تعریف «درست» مناسب هنوز نداره)، و
    در صورت وجود عکس پروفایل از profile_display_store - هیچ fake/placeholder
    data اینجا تولید نمی‌شه؛ قابلیت‌هایی که backend ندارن (📊 پیشرفت، دسته‌بندی
    آیه/مفهوم/حفظیات، لقب‌های روزانه) عمداً اضافه نشدن."""
    if await _in_diagnostic(state):
        await message.answer("اول این ۳ سؤال رو تموم کن 🙂")
        return

    user_id = message.from_user.id
    profile = get_profile(user_id)
    if not profile or not is_profile_complete(profile):
        # فاز 5C: به‌جای پیام بن‌بست قبلی («هنوز پروفایلت کامل نشده»)،
        # کاربر رو مستقیم می‌بریم سراغ ادامه‌ی فرآیند پروفایل - دقیقاً از
        # همون فیلد ناقصی که get_next_missing_field تشخیص می‌ده.
        await start_profile_flow(message.bot, message.chat.id, user_id, state)
        return

    grade_label = dict(GRADE_OPTIONS).get(profile["grade"], profile["grade"])
    goal_label = dict(GOAL_OPTIONS).get(profile["goal"], profile["goal"])
    time_label = dict(DAILY_TIME_OPTIONS).get(profile["daily_minutes"], profile["daily_minutes"])

    lesson = load_lesson("L1")
    subject = lesson.get("subject", "")
    lesson_title = lesson.get("lesson_title") or "درس اول"

    lines = [
        "👤 <b>پروفایل من</b>",
        "",
        f"نام: {profile['name']}",
        f"سن: {profile['age']}",
        f"پایه: {grade_label}",
        f"هدف: {goal_label}",
        # لیبل عمداً «زمان مطالعه‌ی روزانه» (نه «زمان واقعی مطالعه») - این
        # همون ظرفیتیه که کاربر تو onboarding انتخاب کرده، نه چیزی که واقعاً
        # tracking شده؛ سیستم tracking واقعی هنوز نداریم (فاز آینده).
        f"⏱ زمان مطالعه‌ی روزانه: {time_label}",
        "",
        f"📚 درس فعلی: {subject} — {lesson_title}",
    ]

    streak = get_streak(user_id)
    lines.append(f"\n🔥 استریک فعلی: {streak['current_streak']} روز")
    if streak["longest_streak"] > streak["current_streak"]:
        lines.append(f"🏆 بهترین رکورد: {streak['longest_streak']} روز")

    title = get_title(streak["current_streak"])
    lines.append(f"🎖 عنوان: {title}")

    # آمار سؤال‌های پاسخ‌داده‌شده: تست (practice_store.get_session_accuracies)
    # + لسون‌کوییز (lesson_quiz_store.get_quiz_answers). فلش‌کارت حساب نمی‌شه.
    test_correct = 0
    test_total = 0
    for _session_id, session_correct, session_total in get_session_accuracies(user_id):
        test_correct += session_correct
        test_total += session_total

    quiz_answers = get_quiz_answers(user_id)
    quiz_total = len(quiz_answers)
    quiz_correct = sum(1 for rec in quiz_answers if rec.get("is_correct"))

    answered_total = test_total + quiz_total
    correct_total = test_correct + quiz_correct

    lines.append(f"\n📝 سؤال‌های پاسخ‌داده‌شده: {answered_total}")
    if answered_total:
        success_pct = round((correct_total / answered_total) * 100)
        lines.append(f"📊 درصد موفقیت کلی: {success_pct}٪")
    else:
        lines.append("📊 درصد موفقیت کلی: هنوز داده‌ای ثبت نشده")

    text = "\n".join(lines)

    display = get_display(user_id)
    photo_file_id = display.get("photo_file_id")
    if photo_file_id:
        await message.answer_photo(photo=photo_file_id, caption=text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")
