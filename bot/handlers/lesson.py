"""
هسته‌ی اصلی جریان درس: ارسال پیام‌ها یکی‌یکی، مدیریت quiz ها،
و فراخوانی Rule Engine بعد از هر پاسخ.

منطق پیشروی (به‌روزرسانی‌شده):
- هر پیام، بدون استثنا، با یه دکمه فرستاده می‌شه و منتظر کلیک کاربر می‌مونه.
  قبلاً پیام‌هایی با button=null فوری و پشت‌سرهم فرستاده می‌شدن که باعث
  می‌شد چند پیام یهو روی صفحه‌ی کاربر بریزه؛ این رفتار عمداً حذف شده.
- پیام‌های type=quiz همیشه منتظر پاسخ کاربر می‌مونن (چه چندگزینه‌ای چه fill_blank).
- گزینه‌های quiz چندگزینه‌ای هر بار به‌صورت تصادفی جابه‌جا می‌شن تا کاربر
  جای گزینه‌ها رو حفظ نکنه.
"""
from __future__ import annotations  # سازگاری type hint های جدید با پایتون ۳.۹

import random
from datetime import datetime, timezone

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

from bot.states import LessonFlow
from bot.data_loader import get_section, total_sections, get_section_index_by_id
from bot.renderer import render_message, render_intro, render_outro, render_quiz_question, render_options_list
from bot.keyboards import (
    continue_keyboard,
    quiz_choice_keyboard,
    feedback_keyboard,
    next_section_keyboard,
    main_menu_reply_keyboard,
)
from bot.rule_engine import RuleEngine, QuizSession, TriggeredRule
from bot.arabic_utils import compare_answers
from bot.feedback_store import increment as increment_feedback
from bot.progress_store import set_current_section, mark_section_complete
from bot.lesson_quiz_store import log_quiz_answer
from bot.learning_state_store import record_active_day
from config import ADMIN_CHAT_ID

router = Router()
rule_engine = RuleEngine()

# پیام‌های تشویقی متنوع برای وقتی کاربر جواب رو درست می‌زنه، تا حس تکراری
# «آفرین درست بود» رو تو کل درس نده. برای multiple_choice همیشه استفاده
# می‌شه؛ برای fill_blank فقط وقتی سؤال feedback_correct اختصاصی نداره.
_CORRECT_FEEDBACK_POOL = [
    "✅ آفرین، درست بود!",
    "✅ دقیقاً همینه!",
    "✅ عالی بود!",
    "✅ صد درصد درست!",
    "✅ آره، همینه!",
    "✅ درسته، خوب یاد گرفتی!",
    "✅ همینه، ادامه بده همین‌جوری!",
    "✅ کاملاً درست!",
    "✅ زدی وسط خال!",
    "✅ آفرین، حواست جمعه!",
    "✅ درست جواب دادی!",
    "✅ همین بود، خوبه!",
    "✅ خیلی خوب، درسته!",
    "✅ دقیق و درست!",
    "✅ آره درسته، جلو بریم!",
]


def _random_correct_feedback() -> str:
    return random.choice(_CORRECT_FEEDBACK_POOL)


# ---------- کمک‌توابع مدیریت session در FSMContext ----------

async def _get_quiz_session(state: FSMContext) -> QuizSession:
    data = await state.get_data()
    return QuizSession(
        answers=data.get("answers", []),
        consecutive_errors=data.get("consecutive_errors", 0),
    )


async def _save_quiz_session(state: FSMContext, session: QuizSession) -> None:
    await state.update_data(
        answers=session.answers,
        consecutive_errors=session.consecutive_errors,
    )


# ---------- شروع درس ----------

async def enter_lesson(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    lesson_id: str = "L1",
    section_index: int = 0,
    review_queue: list[str] | None = None,
) -> None:
    """منطق شروع/ری‌استارت درس - هم از دکمه‌ی «📖 شروع درس» تو کیبورد پایین
    (متن ساده، نه callback) و هم از callback قدیمی start_lesson صدا زده می‌شه.
    نکته: فعلاً «ادامه» یعنی از اول همون درس شروع کن، نه resume دقیق از جایی که
    ول کرده بودی — چون resume واقعی هنوز پیاده نشده (خارج از اسکوپ این تغییرات).

    review_queue: وقتی کاربر از نتیجه‌ی تست میاد رو «این بخش‌ها رو کامل بخون»،
    لیست section_id های باقی‌مونده رو اینجا نگه می‌داریم. بعد از تموم شدن هر
    بخش، به‌جای پیشروی خطی معمولی (section_index+1)، سراغ بعدی تو همین لیست
    می‌ریم - نه بخش بعدی درس."""
    await state.set_data({
        "lesson_id": lesson_id,
        "section_index": section_index,
        "message_index": 0,
        "answers": [],
        "consecutive_errors": 0,
        "review_queue": review_queue,
    })
    await state.set_state(LessonFlow.in_lesson)
    await _send_section_intro(bot, chat_id, lesson_id, section_index)
    await _advance(bot, chat_id, state)


@router.callback_query(F.data.startswith("start_lesson:"))
async def start_lesson(callback: CallbackQuery, state: FSMContext):
    lesson_id = callback.data.split(":")[1]
    await callback.answer()
    await enter_lesson(callback.bot, callback.message.chat.id, state, lesson_id)


@router.callback_query(F.data.startswith("review_queue:"))
async def start_review_queue(callback: CallbackQuery, state: FSMContext):
    """کاربر رو «این بخش‌ها رو کامل بخون» زده - می‌ریم سراغ اولین بخش ضعیف،
    بقیه رو به‌عنوان صف نگه می‌داریم تا بعد از هرکدوم، خودکار بریم سراغ بعدی
    (نه بخش بعدیِ خطیِ درس)."""
    section_ids = callback.data.split(":", 1)[1].split(",")
    lesson_id = "L1"
    first_id, rest = section_ids[0], section_ids[1:]
    section_index = get_section_index_by_id(lesson_id, first_id)
    if section_index is None:
        await callback.answer("این بخش پیدا نشد 😕", show_alert=True)
        return
    await callback.answer()
    await enter_lesson(callback.bot, callback.message.chat.id, state, lesson_id, section_index, review_queue=rest)


@router.callback_query(F.data.startswith("select_section:"))
async def handle_select_section(callback: CallbackQuery, state: FSMContext):
    """کاربر از لیست «📑 انتخاب بخش» یه section_id (مثل S6) رو انتخاب کرده.
    دقیقاً همون مسیر ورودی enter_lesson که مسیر خطی هم ازش استفاده می‌کنه؛
    فقط section_index به‌جای ۰، مستقیم روی بخش انتخاب‌شده تنظیم می‌شه."""
    section_id = callback.data.split(":", 1)[1]
    lesson_id = "L1"
    section_index = get_section_index_by_id(lesson_id, section_id)
    if section_index is None:
        await callback.answer("این بخش پیدا نشد 😕", show_alert=True)
        return
    await callback.answer()
    await enter_lesson(callback.bot, callback.message.chat.id, state, lesson_id, section_index)


async def _send_section_intro(bot: Bot, chat_id: int, lesson_id: str, section_index: int) -> None:
    section = get_section(lesson_id, section_index)
    # قبل از intro، شماره و عنوان بخش رو واضح نشون می‌دیم تا کاربر بدونه دقیقاً
    # وارد کدوم بخش شده - چه از مسیر خطی، چه از انتخاب مستقیم بخش، چه /goto.
    header = f"📍 بخش {section['section_number']} از {total_sections(lesson_id)} — {section['title']}"
    await bot.send_message(
        chat_id,
        f"{header}\n\n{render_intro(section)}",
        parse_mode="HTML",
    )
    # چت خصوصیه، چت‌آیدی همون یوزرآیدیه (همون فرض استفاده‌شده تو practice.py).
    # این تنها نقطه‌ی مشترک ورود به یه section است (خطی، انتخاب مستقیم بخش،
    # review_queue، و /goto همه از همینجا رد می‌شن) - جای درستی برای آپدیت
    # current_section بدون نیاز به چند نقطه‌ی هوک جدا.
    set_current_section(chat_id, lesson_id, section["section_id"])


# ---------- ابزار تست: پرش مستقیم به یه بخش خاص (فقط برای ادمین/کیمیا) ----------
# وقتی یه کاربر واقعی گزارش اشکال از یه بخش خاص می‌ده، به‌جای اینکه از اول
# لسون رد بشی تا برسی به همون بخش، با /goto S4 (دقیقاً همون section_id که
# تو JSON هست، نه شماره‌ی ذهنی) مستقیم می‌ری اونجا و از اون‌جا تست می‌کنی.

@router.message(Command("goto"))
async def handle_goto_section(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_CHAT_ID:
        return  # این دستور فقط برای تست خودته؛ کاربر عادی نباید بهش دسترسی داشته باشه

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("فرمت درست: /goto S4  (دقیقاً همون section_id که تو JSON هست، مثل S1 تا S13)")
        return

    section_id = parts[1].strip()
    lesson_id = "L1"
    section_index = get_section_index_by_id(lesson_id, section_id)
    if section_index is None:
        await message.answer(f"بخشی با section_id «{section_id}» پیدا نشد.")
        return

    await state.set_data({
        "lesson_id": lesson_id,
        "section_index": section_index,
        "message_index": 0,
        "answers": [],
        "consecutive_errors": 0,
    })
    await state.set_state(LessonFlow.in_lesson)
    await message.answer(f"⏩ رفتیم مستقیم به {section_id}.")
    await _send_section_intro(message.bot, message.chat.id, lesson_id, section_index)
    await _advance(message.bot, message.chat.id, state)


# ---------- موتور پیشروی اصلی ----------

async def _advance(bot: Bot, chat_id: int, state: FSMContext) -> None:
    """پیام بعدی رو می‌فرسته. هر پیام (به‌جز quiz که خودش هندلر جدا داره)
    با یه دکمه‌ی «ادامه» (یا لیبل سفارشی‌شده‌ی خودش) فرستاده می‌شه و اینجا
    متوقف می‌شیم؛ کلیک بعدی کاربر روی هندلر handle_continue می‌ره."""
    data = await state.get_data()
    lesson_id = data["lesson_id"]
    section_index = data["section_index"]
    message_index = data["message_index"]

    section = get_section(lesson_id, section_index)
    messages = section["messages"]

    if message_index >= len(messages):
        await _finish_section(bot, chat_id, state)
        return

    msg = messages[message_index]

    if msg["type"] == "quiz":
        await _send_quiz(bot, chat_id, state, msg)
        return  # منتظر پاسخ کاربر می‌مونیم؛ ادامه‌ی پیشروی در handler پاسخ quiz اتفاق می‌افته

    text = render_message(msg)
    button_label = msg.get("button") or "ادامه"

    await bot.send_message(chat_id, text, reply_markup=continue_keyboard(button_label), parse_mode="HTML")
    await state.set_state(LessonFlow.in_lesson)
    # منتظر کلیک کاربر روی "continue" می‌مونیم


@router.callback_query(F.data == "continue", LessonFlow.in_lesson)
async def handle_continue(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    await state.update_data(message_index=data["message_index"] + 1)
    await _advance(callback.bot, callback.message.chat.id, state)


# ---------- Quiz: چندگزینه‌ای و fill_blank ----------

async def _send_quiz(bot: Bot, chat_id: int, state: FSMContext, msg: dict) -> None:
    if msg["quiz_type"] == "multiple_choice":
        # گزینه‌ها رو تصادفی جابه‌جا می‌کنیم تا جای گزینه‌ی درست هر بار فرق کنه.
        # روی یه کپی جدید کار می‌کنیم تا محتوای cache‌شده‌ی lesson1.json دست‌نخورده بمونه.
        options = list(msg["options"])
        correct_option_text = options[msg["correct_index"]]
        random.shuffle(options)

        shuffled_msg = dict(msg)
        shuffled_msg["options"] = options
        shuffled_msg["correct_index"] = options.index(correct_option_text)

        await state.update_data(pending_quiz=shuffled_msg)
        question_text = render_quiz_question(shuffled_msg) + "\n\n" + render_options_list(options)
        await bot.send_message(
            chat_id, question_text,
            reply_markup=quiz_choice_keyboard(options),
            parse_mode="HTML",
        )
        await state.set_state(LessonFlow.awaiting_quiz_choice)

    elif msg["quiz_type"] == "fill_blank":
        await state.update_data(pending_quiz=msg)
        question_text = render_quiz_question(msg)
        await bot.send_message(chat_id, question_text, parse_mode="HTML")
        await state.set_state(LessonFlow.awaiting_fill_blank)

    else:
        raise ValueError(f"quiz_type ناشناخته: {msg['quiz_type']}")


@router.callback_query(F.data.startswith("quiz_choice:"), LessonFlow.awaiting_quiz_choice)
async def handle_quiz_choice(callback: CallbackQuery, state: FSMContext):
    chosen_index = int(callback.data.split(":")[1])
    data = await state.get_data()
    quiz = data["pending_quiz"]
    is_correct = chosen_index == quiz["correct_index"]

    section = get_section(data["lesson_id"], data["section_index"])
    log_quiz_answer(
        user_id=callback.message.chat.id,
        lesson_id=data["lesson_id"],
        section_id=section["section_id"],
        question_ref=data["message_index"],
        quiz_type=quiz["quiz_type"],
        is_correct=is_correct,
    )

    await callback.answer("✅ درست بود!" if is_correct else "❌ غلط بود")
    feedback = _random_correct_feedback() if is_correct else (
        f"❌ جواب درست: {quiz['options'][quiz['correct_index']]}"
    )
    await callback.message.answer(feedback)

    await _record_answer_and_continue(callback.bot, callback.message.chat.id, state, is_correct)


@router.message(LessonFlow.awaiting_fill_blank)
async def handle_fill_blank(message: Message, state: FSMContext):
    data = await state.get_data()
    quiz = data["pending_quiz"]
    user_answer = (message.text or "").strip()
    correct_answer = quiz["correct_answer"].strip()
    is_correct, is_exact = compare_answers(user_answer, correct_answer)

    section = get_section(data["lesson_id"], data["section_index"])
    log_quiz_answer(
        user_id=message.chat.id,
        lesson_id=data["lesson_id"],
        section_id=section["section_id"],
        question_ref=data["message_index"],
        quiz_type=quiz["quiz_type"],
        is_correct=is_correct,
    )

    if is_correct and is_exact:
        # اگه سؤال فیدبک اختصاصی داره از همون استفاده کن، وگرنه از استخر متنوع
        feedback = quiz.get("feedback_correct") or _random_correct_feedback()
    elif is_correct and not is_exact:
        # کلمه درسته، فقط اعراب‌گذاری یا رسم‌الخطش با نسخه‌ی دقیق فرق داره
        feedback = f"✅ درسته! فقط اعراب‌گذاری کاملش این‌شکلیه: {correct_answer}"
    else:
        feedback = f"❌ جواب درست: {correct_answer}"
    await message.answer(feedback)

    await _record_answer_and_continue(message.bot, message.chat.id, state, is_correct)


async def _record_answer_and_continue(bot: Bot, chat_id: int, state: FSMContext, is_correct: bool) -> None:
    session = await _get_quiz_session(state)
    session.record_answer(is_correct)

    triggered = rule_engine.evaluate(session)
    if triggered != TriggeredRule.NONE:
        await _handle_triggered_rule(bot, chat_id, triggered)
        rule_engine.reset_after_handling(session, triggered)

    await _save_quiz_session(state, session)

    data = await state.get_data()
    await state.update_data(message_index=data["message_index"] + 1)
    await state.set_state(LessonFlow.in_lesson)
    await _advance(bot, chat_id, state)


async def _handle_triggered_rule(bot: Bot, chat_id: int, rule: TriggeredRule) -> None:
    # TODO: این پیام‌ها بعداً باید content-driven بشن (طبق ContentRules_v2.md، Rule 43-49)
    if rule == TriggeredRule.CONSECUTIVE_ERRORS:
        await bot.send_message(
            chat_id,
            "🔄 به نظر می‌رسه این بخش یه‌کم سخت شده. بیا با هم دوباره نگاه سریعی به نکته‌ی اصلی بندازیم.",
        )
    elif rule == TriggeredRule.FATIGUE:
        await bot.send_message(
            chat_id,
            "☕️ دقتت نسبت به اول جلسه افت کرده. شاید وقتشه چند دقیقه استراحت کنی و بعد ادامه بدی. هر وقت آماده بودی برگرد 💪",
        )


# ---------- پایان بخش، فیدبک، و رفتن به بخش بعد ----------

async def _finish_section(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    lesson_id = data["lesson_id"]
    section_index = data["section_index"]
    section = get_section(lesson_id, section_index)

    outro = render_outro(section)
    if outro:
        await bot.send_message(chat_id, outro, parse_mode="HTML")

    # completed_sections فقط از همین نقطه ثبت می‌شه (طبق تصمیم) - idempotent،
    # پس اگه کاربر یه section رو دوباره ببینه (مثلاً از انتخاب مستقیم بخش)،
    # duplicate اضافه نمی‌شه.
    mark_section_complete(chat_id, lesson_id, section["section_id"])

    # تنها نقطه‌ی هوک Active Day برای فعالیت لسون (طبق تصمیم معماری Phase 2)؛
    # عمداً تو _send_section_intro نیست - فقط اتمام واقعی یه section شمرده می‌شه.
    record_active_day(chat_id, datetime.now(timezone.utc).date())

    # به‌جای رفتن خودکار به بخش بعد، صبر می‌کنیم تا کاربر یا فیدبک بده یا مستقیم بره جلو.
    await bot.send_message(
        chat_id,
        "این بخش رو چطور دیدی؟",
        reply_markup=feedback_keyboard(section["section_id"]),
    )
    await state.set_state(LessonFlow.section_transition)


async def _go_to_next_section(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    lesson_id = data["lesson_id"]
    section_index = data["section_index"]
    review_queue = data.get("review_queue")

    if review_queue is not None:
        # تو حالت «مرور بخش‌های ضعیف» هستیم - نه پیشروی خطی معمولی درس.
        # بعد از هر بخش، سراغ بعدیِ همین لیست می‌ریم، نه section_index+1.
        if review_queue:
            next_id = review_queue[0]
            remaining = review_queue[1:]
            next_index = get_section_index_by_id(lesson_id, next_id)
            if next_index is not None:
                await bot.send_message(
                    chat_id,
                    f"✅ این بخش رو مرور کردی. {len(remaining) + 1} بخش دیگه از لیست ضعیفت مونده."
                    if len(remaining) + 1 > 1 else "✅ این بخش رو هم مرور کردی. یکی دیگه مونده.",
                )
                await state.update_data(section_index=next_index, message_index=0, review_queue=remaining)
                await state.set_state(LessonFlow.in_lesson)
                await _send_section_intro(bot, chat_id, lesson_id, next_index)
                await _advance(bot, chat_id, state)
                return
            # section_id نامعتبر تو صف بود - ردش کن و برو سراغ بعدی
            await state.update_data(review_queue=remaining)
            await _go_to_next_section(bot, chat_id, state)
            return

        # صف تموم شد
        await state.update_data(review_queue=None)
        await state.set_state(LessonFlow.lesson_complete)
        await bot.send_message(chat_id, "🎉 همه‌ی بخش‌های ضعیفت رو مرور کردی!")
        await bot.send_message(
            chat_id,
            "می‌خوای الان یه تست جدید از همینا بزنی؟ از دکمه‌های پایین انتخاب کن 👇",
            reply_markup=main_menu_reply_keyboard(),
        )
        return

    next_index = section_index + 1
    if next_index >= total_sections(lesson_id):
        await state.set_state(LessonFlow.lesson_complete)
        await bot.send_message(chat_id, "🎉 درس اول رو کامل تموم کردی!")
        await bot.send_message(
            chat_id,
            "می‌خوای الان یه تست بزنی یا فلش‌کارت‌ها رو مرور کنی؟ از دکمه‌های پایین انتخاب کن 👇",
            reply_markup=main_menu_reply_keyboard(),
        )
        return

    await state.update_data(section_index=next_index, message_index=0)
    await state.set_state(LessonFlow.in_lesson)
    await _send_section_intro(bot, chat_id, lesson_id, next_index)
    await _advance(bot, chat_id, state)


@router.callback_query(F.data == "next_section")
async def handle_next_section(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _go_to_next_section(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback_button(callback: CallbackQuery, state: FSMContext):
    _, kind, section_id = callback.data.split(":", 2)
    user = callback.from_user
    username = f"@{user.username}" if user.username else "بدون یوزرنیم"

    if kind == "idea":
        await callback.answer()
        await state.update_data(feedback_section_id=section_id)
        await state.set_state(LessonFlow.awaiting_feedback_idea)
        await callback.message.answer("💡 بگو چی تو ذهنته، برات به توسعه‌دهنده می‌فرستم:")
        return

    await callback.answer("🙏 ممنون از نظرت!")
    label = "👍 پسندیدم" if kind == "like" else "👎 دوست نداشتم"
    total = increment_feedback(section_id, kind)
    if ADMIN_CHAT_ID:
        await callback.bot.send_message(
            ADMIN_CHAT_ID,
            f"{label}\nبخش: {section_id}\nکاربر: {user.full_name} ({username})\nمجموع {label} این بخش تا الان: {total}",
        )


@router.message(LessonFlow.awaiting_feedback_idea)
async def handle_feedback_idea_text(message: Message, state: FSMContext):
    data = await state.get_data()
    section_id = data.get("feedback_section_id", "?")
    user = message.from_user
    username = f"@{user.username}" if user.username else "بدون یوزرنیم"

    if ADMIN_CHAT_ID:
        await message.bot.send_message(
            ADMIN_CHAT_ID,
            f"💡 ایده‌ی جدید\nبخش: {section_id}\nکاربر: {user.full_name} ({username})\n\n{message.text}",
        )
    await message.answer("ممنون بابت ایده‌ت! 🙏")
    await message.answer("برای ادامه:", reply_markup=next_section_keyboard())
    await state.set_state(LessonFlow.section_transition)
