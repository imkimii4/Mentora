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
from logging import getLogger

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
from bot.profile_display_store import clear_display
from bot.practice_store import get_session_accuracies
from bot.lesson_quiz_store import get_quiz_answers
from bot.title_rank import get_title
from bot.event_log import log_event
from config import DEV_TEST_USER_IDS

router = Router()
logger = getLogger(__name__)

_DIAGNOSTIC_STATE_NAMES = {
    DiagnosticFlow.q1.state,
    DiagnosticFlow.q2.state,
    DiagnosticFlow.q3.state,
}


async def _in_diagnostic(state: FSMContext) -> bool:
    current = await state.get_state()
    return current in _DIAGNOSTIC_STATE_NAMES


# فاز 5D: عکس پروفایل به‌جای ذخیره‌شدن (که هیچ handler آپلودی هم برای پرش
# وجود نداره - profile_display_store.set_photo فعلاً هیچ‌جا صدا زده نمی‌شه)
# هر بار زنده از خودِ تلگرام گرفته می‌شه - همون عکس پروفایل فعلی کاربر تو
# تلگرام، نه چیزی که ما جایی نگه داشته باشیم. طبق اسکوپ فاز 5D عمداً
# storage جدیدی برای این ساخته نشد؛ profile_display_store دست‌نخورده موند
# (برای فاز‌های بعدی آپلود عکس دستی، اگه لازم شد).
async def _get_live_profile_photo_id(bot, user_id: int) -> str | None:
    """آخرین عکس پروفایل تلگرام کاربر رو زنده می‌گیره؛ در هر حالت غیرعادی
    (کاربر عکس نداره، حریم خصوصی محدودش کرده، خطای شبکه/API) بی‌صدا None
    برمی‌گردونه تا صدازننده مطمئن fallback به متن بزنه - هیچ‌وقت نباید
    نبودِ عکس باعث خطا به کاربر بشه.

    BUGFIX (5D): قبلاً user_id پوزیشنال پاس داده می‌شد
    (bot.get_user_profile_photos(user_id, limit=1))؛ ولی مدل واقعی این
    متد تو aiogram 3.15 (GetUserProfilePhotos) با یه `*` در ابتدای امضاش
    تعریف شده یعنی همه‌ی فیلدهاش از جمله user_id keyword-only هستن. این
    یعنی تماس قبلی به احتمال زیاد هر بار یه TypeError می‌داد که همون‌جا
    تو except قورت می‌شد و علتش دیده نمی‌شد - دقیقاً هم‌راستا با چیزی که
    تو تست واقعی دیدیم (همیشه fallback متنی، هیچ‌وقت عکس). الان user_id
    صریح keyword پاس داده می‌شه که با هر دو حالت (keyword-only یا معمولی)
    درست کار می‌کنه.
    """
    try:
        photos = await bot.get_user_profile_photos(user_id=user_id, limit=1)
    except Exception as exc:
        # لاگ موقت تشخیصی (فاز 5D bugfix) - فقط نوع/متن خطا و user_id
        # عددی، هیچ token یا داده‌ی حساسی چاپ نمی‌شه. اگه fix بالا کافی
        # نباشه، این لاگ علت واقعی رو تو اجرای بعدی نشون می‌ده.
        logger.warning(
            "profile photo fetch failed for user_id=%s: %s: %s",
            user_id, type(exc).__name__, exc,
        )
        return None
    if not photos or not photos.photos:
        return None
    # هر آیتم تو photos.photos خودش چند سایز از یه عکسه؛ آخرین سایز
    # (photos.photos[0][-1]) بزرگ‌ترین/باکیفیت‌ترینه.
    return photos.photos[0][-1].file_id


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

    streak = get_streak(user_id)
    title = get_title(streak["current_streak"])

    # آمار سؤال‌های پاسخ‌داده‌شده: تست (practice_store.get_session_accuracies)
    # + لسون‌کوییز (lesson_quiz_store.get_quiz_answers). فلش‌کارت حساب نمی‌شه
    # (فاز 5C، accessor/تعریف «درست» مناسب هنوز نداره).
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

    # فاز 5D: همون داده‌های واقعی قبلی (هیچ فیلد جدیدی اضافه نشده)، فقط
    # بخش‌بندی‌شده با هدر و جداکننده به‌جای یه بلوک یک‌دست - خوانایی تو
    # موبایل بهتر می‌شه، بدون هیچ tracking یا محاسبه‌ی جدید.
    identity_block = "\n".join([
        f"🧑 نام: {profile['name']}",
        f"🎂 سن: {profile['age']}",
        f"🏫 پایه: {grade_label}",
        f"🎯 هدف: {goal_label}",
        # لیبل عمداً «زمان مطالعه‌ی روزانه» (نه «زمان واقعی مطالعه») - این
        # همون ظرفیتیه که کاربر تو onboarding انتخاب کرده، نه چیزی که واقعاً
        # tracking شده؛ سیستم tracking واقعی هنوز نداریم (فاز آینده).
        f"⏱ زمان مطالعه‌ی روزانه: {time_label}",
    ])

    progress_block = "\n".join([
        f"📚 درس فعلی: {subject} — {lesson_title}",
        f"🔥 استریک فعلی: {streak['current_streak']} روز"
        + (f" (بهترین رکورد: {streak['longest_streak']} روز)"
           if streak["longest_streak"] > streak["current_streak"] else ""),
        f"🎖 عنوان: {title}",
    ])

    stats_lines = [f"📝 سؤال‌های پاسخ‌داده‌شده: {answered_total}"]
    if answered_total:
        success_pct = round((correct_total / answered_total) * 100)
        stats_lines.append(f"📊 درصد موفقیت کلی: {success_pct}٪")
    else:
        stats_lines.append("📊 درصد موفقیت کلی: هنوز داده‌ای ثبت نشده")
    stats_block = "\n".join(stats_lines)

    divider = "➖➖➖➖➖➖➖➖"
    text = "\n\n".join([
        "👤 <b>پروفایل من</b>",
        identity_block,
        divider,
        progress_block,
        divider,
        stats_block,
    ])

    # فاز 5D: عکس پروفایل دیگه از storage محلی نمیاد (هیچ‌وقت پر نمی‌شد)،
    # بلکه هر بار زنده از خودِ تلگرام گرفته می‌شه. هرجا نبود یا خطا داد،
    # امن fallback به همون متن ساده می‌کنیم - کاربر هیچ‌وقت با خطا مواجه نمی‌شه.
    photo_file_id = await _get_live_profile_photo_id(message.bot, user_id)
    if photo_file_id:
        # کپشن عکس تو تلگرام محدود به ۱۰۲۴ کاراکتره؛ اگه متن پروفایل ازش
        # بلندتر شد (کاربرهای با استریک/آمار زیاد)، به‌جای بریده‌شدن خاموش
        # کپشن، عکس رو بدون کپشن می‌فرستیم و متن کامل رو جدا زیرش می‌دیم.
        if len(text) <= 1024:
            await message.answer_photo(photo=photo_file_id, caption=text, parse_mode="HTML")
        else:
            await message.answer_photo(photo=photo_file_id)
            await message.answer(text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")
