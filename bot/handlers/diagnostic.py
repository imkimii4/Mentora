"""
Diagnostic Flow: مسیر اختیاری کاربر جدید، قبل از S1. ۳ سؤال رندوم، نه از کل
بانک ۵۱ تایی (test_bank_L1.json)، بلکه از یه زیرمجموعه‌ی از‌پیش‌بررسی‌شده‌ی
۱۵ تایی (_DIAGNOSTIC_QUESTION_POOL_IDS) که کوتاه و تک‌مفهومی‌ان و نیازی به
تشخیص متن دقیق آیه ندارن؛ بدون claim دقیق تشخیص بخش ضعیف - فقط یه
نتیجه‌ی کوتاه و آشناکننده؛ بعدش همه‌ی کاربرها (چه مسیر سریع، چه تشخیصی) از
S1 شروع می‌کنن (طبق تصمیم: با ۳ سؤال ادعای تشخیص دقیق نداریم).

عمداً از _send_test_question/TestMode توی practice.py استفاده نمی‌کنیم:
اون تابع و state fieldهاش (test_session_id, seen_questions_store,
practice_store logging و...) مخصوص مسیر «تست بزن» از منوی اصلی‌ان. قاطی
کردنشون با DiagnosticFlow یعنی غیرمستقیم practice.py رو لمس می‌کردیم - این
فایل به‌جاش یه نسخه‌ی مینیمال و کاملاً مستقل از همون منطق شافل گزینه‌ها رو
داره، بدون هیچ وابستگی به practice.py.

اتصال به لسون فقط از طریق تابع عمومی و از قبل موجود enter_lesson() هست -
هیچ چیزی داخل lesson.py برای این اتصال لازم نیست تغییر کنه.

ورود به درس (چه از مسیر Quick Start چه از پایان Diagnostic) خودکار نیست:
هر دو مسیر به یه پیام با دکمه‌ی «🚀 شروع درس» می‌رسن (_ENTER_LESSON_CALLBACK)
و enter_lesson() فقط بعد از کلیک کاربر روی همین دکمه صدا زده می‌شه.
"""
from __future__ import annotations

import random
from html import escape

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from bot.states import DiagnosticFlow
from bot.data_loader import load_test_bank
from bot.renderer import render_options_list
from bot.keyboards import (
    onboarding_choice_keyboard,
    diagnostic_choice_keyboard,
    main_menu_reply_keyboard,
)
from bot.handlers.lesson import enter_lesson
from bot.onboarding_store import mark_onboarded
from bot.event_log import log_event

router = Router()

_DIAGNOSTIC_QUESTION_COUNT = 3

# استخر سؤال‌های مناسب Diagnostic از test_bank_L1.json (کوتاه، تک‌مفهومی،
# بدون نیاز به تشخیص متن دقیق آیه). این لیست دستی بررسی و انتخاب شده -
# اگر بعداً بانک سؤال عوض شد یا سؤال جدیدی اضافه شد، این استخر جدا از
# _DIAGNOSTIC_QUESTION_COUNT به‌روزرسانی می‌شه.
_DIAGNOSTIC_QUESTION_POOL_IDS = {
    7, 8, 21, 26, 27, 34, 35, 36, 37, 38, 39, 41, 46, 47, 49,
}

# دکمه‌ی مشترک «شروع درس» - هم بعد از معرفی Quick Start و هم بعد از پیام
# پایانی Diagnostic استفاده می‌شه، تا ورود به درس با کلیک کاربر انجام بشه
# نه به‌صورت خودکار (طبق تصمیم پروژه).
_ENTER_LESSON_CALLBACK = "diag_enter_lesson"


def _enter_lesson_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🚀 شروع درس", callback_data=_ENTER_LESSON_CALLBACK)]]
    )


async def send_onboarding_choice(bot: Bot, chat_id: int) -> None:
    """از onboarding.py صدا زده می‌شه، فقط برای کاربر جدید (بعد از /start).
    عمداً reply keyboard اینجا فرستاده نمی‌شه - تا پایان مسیر (quick یا
    diagnostic) کاربر هیچ reply keyboardی نمی‌بینه، پس دکمه‌ای برای تداخل
    با Diagnostic روی صفحه نیست."""
    await bot.send_message(
        chat_id,
        "سلام! 🌟 به <b>Mentora</b> خوش اومدی.\n\n"
        "می‌تونی همین الان بری سراغ درس، یا اول یه آزمون کوتاه ۳ سؤالی بزنی "
        "تا با فضای سؤال‌ها آشنا بشی (نتیجه‌ش فقط یه راهنمای کلیه، دقیق نیست).",
        reply_markup=onboarding_choice_keyboard(),
        parse_mode="HTML",
    )


async def _start_quick_path(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    mark_onboarded(user_id, path="quick")
    await state.update_data(onboarding_path="quick")
    # Placeholder: متن ثابته، بعداً اگه متادیتای درس از فایل جدا خونده بشه
    # داینامیک می‌شه. هدف این مرحله فقط اصلاح UX (نمایش معرفی) بود، نه
    # داینامیک‌کردن اطلاعات.
    await bot.send_message(
        chat_id,
        "📘 درس اول: هدف زندگی\n"
        "• ۱۳ بخش کوتاه\n"
        "• حدود ۲۰ تا ۳۰ دقیقه\n\n"
        "در این درس قدم‌به‌قدم با مفهوم هدف زندگی آشنا می‌شوی.",
        reply_markup=_enter_lesson_keyboard(),
    )


@router.callback_query(F.data == "onb_quick")
async def handle_onboarding_quick(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _start_quick_path(callback.bot, callback.message.chat.id, callback.from_user.id, state)


@router.callback_query(F.data == "onb_diagnostic")
async def handle_onboarding_diagnostic(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    bank = load_test_bank("L1")["questions"]
    pool = [q for q in bank if q["id"] in _DIAGNOSTIC_QUESTION_POOL_IDS]
    count = min(_DIAGNOSTIC_QUESTION_COUNT, len(pool))
    questions = random.sample(pool, count)
    await state.update_data(diag_questions=questions, diag_index=0, diag_correct=0)
    await state.set_state(DiagnosticFlow.q1)
    await _send_diagnostic_question(callback.bot, callback.message.chat.id, state)


async def _send_diagnostic_question(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["diag_questions"]
    index = data["diag_index"]

    q = questions[index]
    options = list(q["options"])
    correct_text = options[q["correct"]]
    random.shuffle(options)
    shuffled_correct_index = options.index(correct_text)

    await state.update_data(diag_current_correct_index=shuffled_correct_index)

    # نکته‌ی مهم (باگ قبلی همین‌جا بود): diagnostic_choice_keyboard فقط حرف
    # (الف/ب/ج/د) روی دکمه‌ها می‌ذاره - دقیقاً هم‌الگوی quiz_choice_keyboard و
    # test_choice_keyboard. پس متن کامل گزینه‌ها باید همین‌جا، تو خودِ متن
    # پیام، با render_options_list ساخته بشه - وگرنه کاربر فقط حرف می‌بینه
    # بدون اینکه بدونه هر حرف به چه متنی اشاره داره.
    header = f"🎯 سؤال {index + 1} از {len(questions)}:\n\n"
    text = header + escape(q["q"]) + "\n\n" + render_options_list(options)
    await bot.send_message(
        chat_id,
        text,
        reply_markup=diagnostic_choice_keyboard(options),
        parse_mode="HTML",
    )


async def _handle_diagnostic_answer(callback: CallbackQuery, state: FSMContext, next_state) -> None:
    chosen_index = int(callback.data.split(":")[1])
    data = await state.get_data()
    is_correct = chosen_index == data["diag_current_correct_index"]
    await callback.answer("✅ درست بود!" if is_correct else "❌ غلط بود")

    await state.update_data(
        diag_correct=data["diag_correct"] + (1 if is_correct else 0),
        diag_index=data["diag_index"] + 1,
    )

    if next_state is None:
        await _finish_diagnostic(callback.bot, callback.message.chat.id, callback.from_user.id, state)
    else:
        await state.set_state(next_state)
        await _send_diagnostic_question(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data.startswith("diag_choice:"), DiagnosticFlow.q1)
async def handle_diag_q1(callback: CallbackQuery, state: FSMContext):
    await _handle_diagnostic_answer(callback, state, DiagnosticFlow.q2)


@router.callback_query(F.data.startswith("diag_choice:"), DiagnosticFlow.q2)
async def handle_diag_q2(callback: CallbackQuery, state: FSMContext):
    await _handle_diagnostic_answer(callback, state, DiagnosticFlow.q3)


@router.callback_query(F.data.startswith("diag_choice:"), DiagnosticFlow.q3)
async def handle_diag_q3(callback: CallbackQuery, state: FSMContext):
    await _handle_diagnostic_answer(callback, state, None)


async def _finish_diagnostic(bot: Bot, chat_id: int, user_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    total = len(data["diag_questions"])
    correct = data["diag_correct"]

    await state.update_data(onboarding_path="diagnostic")
    await bot.send_message(
        chat_id,
        f"از {total} سؤال، {correct} تا رو درست زدی. این فقط یه آشنایی کوتاهه، "
        "نه یه تشخیص دقیق 🙂",
        reply_markup=_enter_lesson_keyboard(),
    )
    log_event(user_id, "diagnostic_completed", {"correct": correct, "total": total})
    mark_onboarded(user_id, path="diagnostic")


@router.callback_query(F.data == _ENTER_LESSON_CALLBACK)
async def handle_enter_lesson(callback: CallbackQuery, state: FSMContext) -> None:
    """هم بعد از معرفی Quick Start و هم بعد از پیام پایانی Diagnostic صدا زده
    می‌شه - ورود واقعی به درس فقط با کلیک کاربر روی همین دکمه اتفاق می‌افته،
    نه خودکار (طبق تصمیم پروژه)."""
    await callback.answer()
    # حذف دکمه بعد از کلیک، تا کلیک دوم باعث ورود/لاگ تکراری نشه.
    await callback.message.edit_reply_markup(reply_markup=None)

    data = await state.get_data()
    path = data.get("onboarding_path", "unknown")
    chat_id = callback.message.chat.id

    await callback.bot.send_message(chat_id, "بزن بریم 🚀", reply_markup=main_menu_reply_keyboard())
    log_event(callback.from_user.id, "first_learning_action", {"path": path})
    await enter_lesson(callback.bot, chat_id, state)
