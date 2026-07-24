"""
/start و منوی اصلی.

کاربر جدید در برابر برگشتی از onboarding_store.py تشخیص داده می‌شه، نه از
FSM state - چون handle_start همیشه state.clear() می‌زنه و هر state قبلی رو
پاک می‌کنه؛ تنها منبع پایدار onboarding_status.json روی دیسکه.

کاربر جدید: پیام کوتاه + انتخاب مسیر (شروع سریع / آزمون تشخیصی) از
diagnostic.py؛ هیچ reply keyboardی هنوز فرستاده نمی‌شه.
کاربر برگشتی: دقیقاً همون رفتار قبلی (خوش‌آمد + منوی اصلی)، بدون تغییر.

گارد DiagnosticFlow روی ۴ دکمه‌ی منوی اصلی: چون این‌ها F.text ساده‌ن (بدون
فیلتر state) و بدون تغییر می‌تونستن Diagnostic رو وسط کار قطع کنن. ریسک
اصلیش با این پلن از ریشه حذف شده (تا پایان Diagnostic اصلاً reply keyboardی
رو صفحه نیست)، این گارد فقط لایه‌ی دفاعی دومه برای حالت لبه‌ای که یه کیبورد
قدیمی از قبل مونده باشه.
"""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from bot.states import DiagnosticFlow
from bot.keyboards import main_menu_reply_keyboard, section_list_keyboard
from bot.data_loader import load_lesson
from bot.handlers.lesson import enter_lesson
from bot.handlers.practice import prompt_test_count, prompt_flashcard_count
from bot.handlers.diagnostic import send_onboarding_choice
from bot.onboarding_store import has_onboarded, clear_onboarded
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

    if has_onboarded(user_id):
        log_event(user_id, "return")
        lesson = load_lesson("L1")
        subject = lesson.get("subject", "")
        lesson_title = lesson.get("lesson_title") or "درس اول"

        await message.answer(
            "سلام! 🌟 به <b>Mentora</b> خوش اومدی.\n\n"
            f"📚 داری «{lesson_title}» رو از درس <b>{subject}</b> یاد می‌گیری.\n"
            "قدم‌به‌قدم و به شکل تعاملی، بدون نیاز به خرید کتاب جداگونه.\n\n"
            "می‌تونی درس رو از ابتدا و به‌ترتیب دنبال کنی، یا با «📑 انتخاب بخش» مستقیماً سراغ بخش موردنظرت بری.\n\n"
            "از دکمه‌های پایین صفحه شروع کن 👇",
            reply_markup=main_menu_reply_keyboard(),
            parse_mode="HTML",
        )
        return

    log_event(user_id, "start")
    await send_onboarding_choice(message.bot, message.chat.id)


# نقطه‌ی واحد ریست برای محیط توسعه. هر بخشی از داده‌ی کاربر که بعداً اضافه
# بشه (Progress، Diagnostic نتایج، Resume state و...) فقط کافیه تابع clear
# شبیه clear_onboarded براش نوشته بشه و به همین لیست اضافه بشه؛ خودِ handler
# و اسم Command دیگه لازم نیست تغییر کنه.
_DEV_RESET_ACTIONS = [
    clear_onboarded,
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
