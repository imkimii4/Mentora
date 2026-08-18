"""
دو مسیر مستقل از لسون که از کیبورد پایین صفحه وارد می‌شن:

- TestMode: تست ترکیبی از بانک ۵۱ سوالی (test_bank_L1.json). تعداد سوال با
  انتخاب کاربر (۵/۱۰/۱۵)، بدون تکرار تا کاربر کل بانک رو نبینه (seen_questions_store).
  سوالاتی که متن/گزینه‌هاشون تو محدودیت Telegram Quiz Poll جا می‌شه (سوال حداکثر
  ۳۰۰ کاراکتر، هر گزینه حداکثر ۱۰۰ کاراکتر) با Poll بومی تلگرام پرسیده می‌شن —
  گزینه‌ها زیر سوال به‌صورت لیست کامل میان، نه دکمه‌ی تنگ‌شونده. سوالاتی که آیه‌ی
  طولانی تو گزینه‌هاشونه (چندتاشون از ۱۰۰ کاراکتر رد می‌زنن) با روش قبلی (متن کامل
  تو پیام + دکمه‌ی حرف کوتاه) پرسیده می‌شن، چون Poll تحملشون نمی‌کنه.

- FlashcardMode: مرور فلش‌کارتی (flashcards_L1.json). هر کارت: نمایش سوال ->
  «نمایش جواب» -> خودارزیابی (بلد بودم/نبودم، بدون AI).

هر دو مسیر جواب‌ها رو خام تو practice_store لاگ می‌کنن (با session_id برای
مقایسه‌ی «نسبت به جلسه‌ی قبل»)؛ تحلیل عمیق‌تر (سرعت/دقت، گپ مفهومی) بعد از
لانچ با داده‌ی واقعی انجام می‌شه.
"""
from __future__ import annotations

import random
import re
import time
import uuid
from datetime import datetime, timezone
from html import escape

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, PollAnswer, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from bot.states import TestMode, FlashcardMode
from bot.data_loader import load_test_bank, load_flashcards
from bot.renderer import render_options_list
from bot.keyboards import (
    main_menu_reply_keyboard,
    test_count_keyboard,
    test_choice_keyboard,
    test_retry_keyboard,
    flashcard_count_keyboard,
    flashcard_reveal_keyboard,
    flashcard_selfcheck_keyboard,
    review_sections_keyboard,
    test_result_success_keyboard,
    test_result_needs_review_keyboard,
)
from bot.practice_store import log_test_answer, log_flashcard_result, get_session_accuracies
from bot.seen_questions_store import get_seen, mark_seen, reset_seen
from bot.learning_state_store import record_active_day

router = Router()

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")

# حالت‌های تشویقی/سازنده بعد از هر جواب - عمداً کلمه‌ی «غلط»/«اشتباه» توشون نیست
# (طبق فیدبک: لحن باید رشدمحور باشه، نه قضاوتی).
_CORRECT_FEEDBACK = [
    "✅ آفرین، درست بود!",
    "✅ دقیقاً همینه!",
    "✅ عالی بود!",
]

# ۱۰ حالت رندوم برای وقتی جواب درست نبود - همیشه یه تیکه‌ش بولد می‌شه.
_REVIEW_SUGGESTIONS = [
    "<b>فرصت خوبیه</b> که این بخش رو یه بار دیگه مرور کنی.",
    "<b>یه نگاه دوباره</b> به این بخش بنداز، کمکت می‌کنه.",
    "این بخش رو <b>یه بار دیگه بخون</b>، جا میفته.",
    "<b>ارزششو داره</b> یه دوره‌ی سریع رو این بخش بزنی.",
    "با <b>یه مرور کوتاه</b> این بخش، دفعه‌ی بعد راحت‌تری.",
    "<b>قوی‌تر شدن از همینجا شروع می‌شه</b> - یه نگاه دوباره بنداز.",
    "این یکی رو <b>بذار تو لیست مرور</b>، زود جا میفته.",
    "<b>یه بار دیگه با هم مرورش کنیم</b>، بهتر می‌شه.",
    "<b>نکته‌ی این بخش رو یه بار دیگه ببین</b>، کمک می‌کنه.",
    "<b>یه مرور کوچیک</b> همینجا فرق رو نشون می‌ده.",
]

# آستانه‌ی «جواب خیلی سریع» - واقع‌بینانه نمی‌شه تو کمتر از این خوند+فهمید+انتخاب کرد.
_FAST_ANSWER_THRESHOLD_SECONDS = 2.5

# وقتی یه جواب خیلی سریع میاد، همون لحظه (نه فقط تو جمع‌بندی آخر) یکی از
# اینا رو هم به فیدبک اضافه می‌کنیم - لحن معلم خصوصی دلسوز، نه گیر دادن یا
# متهم کردن به تقلب.
_FAST_ANSWER_NUDGES = [
    "⏱️ یه لحظه صبر کن، انگار این یکی رو با عجله زدی. وقتتو بذار رو خوندن سوال.",
    "⏱️ آروم‌تر برو، عجله نکن. این تست فقط برای نمره نیست، برای اینه که بفهمی کجا رو بلدی.",
    "⏱️ انگار سریع جواب دادی. یه بار دیگه سوال بعدی رو با دقت بخون.",
    "⏱️ وقت زیاده، عجله نکن. هرچی دقیق‌تر جواب بدی، خودتم بهتر می‌فهمی کجاها ضعیفی.",
    "⏱️ یکم آروم‌تر. هدف اینه که واقعاً یاد بگیری، نه فقط رد کردن سوال.",
    "⏱️ این یکی خیلی سریع رفت. یه نفس بکش، سوال بعدی رو با دقت بخون.",
    "⏱️ سرعتت بالاست، ولی دقت مهم‌تره. یکم بیشتر روی هر سوال وقت بذار.",
]


def _test_next_question_keyboard(label: str = "➡️ سؤال بعدی") -> InlineKeyboardMarkup:
    # کیبورد اختصاصی و مستقل از keyboards.py - callback_data جدا از هر namespace
    # دیگه (quiz_choice/test_choice/continue) تا با کلیک‌های قدیمیِ مسیرهای
    # دیگه قاطی نشه. label قابل تغییره تا برای آخرین سؤال، لیبل واقعی‌تر
    # («مشاهده نتیجه تست») نشون بدیم؛ callback_data و handler همیشه یکی می‌مونه
    # چون _send_test_question خودش تشخیص می‌ده تست تموم شده یا نه.
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="test_next_question")]]
    )


def _extract_section_ids(section_ref: str) -> list[str]:
    """از یه رشته مثل 'بخش ۶ (اسراء ۱۹)' یا 'بخش ۱۰ و ۱۲' آی‌دی بخش(ها) رو
    در میاره -> ['S6'] یا ['S10', 'S12']."""
    numbers = re.findall(r"بخش\s*([۰-۹]+)", section_ref)
    return [f"S{n.translate(_PERSIAN_DIGITS)}" for n in numbers]


def _question_fits_poll(q: dict) -> bool:
    """محدودیت‌های Telegram Quiz Poll: سوال حداکثر ۳۰۰ کاراکتر، هر گزینه
    حداکثر ۱۰۰ کاراکتر، بین ۲ تا ۱۰ گزینه. چندتا از سوالای بانک (اونایی که
    آیه‌ی کامل تو گزینه‌هاشونه) از این رد می‌زنن."""
    if not (1 <= len(q["q"]) <= 300):
        return False
    if not (2 <= len(q["options"]) <= 10):
        return False
    if any(len(o) > 100 for o in q["options"]):
        return False
    return True


# ---------- ورود از کیبورد پایین صفحه ----------

async def prompt_test_count(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(TestMode.choosing_count)
    await bot.send_message(chat_id, "چند تا سوال بزنیم؟", reply_markup=test_count_keyboard())


async def prompt_flashcard_count(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(FlashcardMode.choosing_count)
    await bot.send_message(chat_id, "چند تا فلش‌کارت مرور کنیم؟", reply_markup=flashcard_count_keyboard())


@router.message(Command("test"))
async def cmd_test(message: Message, state: FSMContext):
    await prompt_test_count(message.bot, message.chat.id, state)


@router.message(Command("flashcard"))
async def cmd_flashcard(message: Message, state: FSMContext):
    await prompt_flashcard_count(message.bot, message.chat.id, state)


# ---------- تست ترکیبی ----------

async def _begin_test(bot: Bot, chat_id: int, user_id: int, state: FSMContext, questions: list[dict]) -> None:
    await state.update_data(
        test_session_id=str(uuid.uuid4()),
        test_questions=questions,
        test_index=0,
        test_correct=0,
        test_wrong_sections=[],
        test_fast_answers=0,
    )
    await _send_test_question(bot, chat_id, state)


@router.callback_query(F.data.startswith("test_count:"), TestMode.choosing_count)
async def start_test(callback: CallbackQuery, state: FSMContext):
    count = int(callback.data.split(":")[1])
    await callback.answer()

    user_id = callback.from_user.id
    bank = load_test_bank("L1")["questions"]
    seen = get_seen(user_id)
    unseen = [q for q in bank if q["id"] not in seen]

    if len(unseen) < count:
        # کل بانک (یا بیشترش) رو قبلاً دیده؛ دور جدید رو از صفر شروع می‌کنیم.
        reset_seen(user_id)
        unseen = bank

    count = min(count, len(unseen))
    selected = random.sample(unseen, count)
    mark_seen(user_id, [q["id"] for q in selected])

    await _begin_test(callback.bot, callback.message.chat.id, user_id, state, selected)


@router.callback_query(F.data.startswith("retest:"))
async def retest_weak_sections(callback: CallbackQuery, state: FSMContext):
    """دکمه‌ی «🔁 تمرین جدید همین بخش‌ها» - از همون بخش‌هایی که کاربر غلط زده،
    یه ست تست کوچیک جدید می‌سازه. این عمداً از سیستم seen/unseen رد می‌شه چون
    کاربر خودش صریحاً خواسته دقیقاً همین بخش‌ها رو تمرین کنه."""
    target_ids = set(callback.data.split(":", 1)[1].split(","))
    await callback.answer()

    bank = load_test_bank("L1")["questions"]
    matching = [q for q in bank if set(_extract_section_ids(q.get("section_ref", ""))) & target_ids]
    if not matching:
        await callback.message.answer("سوال دیگه‌ای از این بخش‌ها تو بانک نداریم فعلاً.")
        return

    count = min(5, len(matching))
    selected = random.sample(matching, count)
    await state.set_state(TestMode.awaiting_answer)
    await _begin_test(callback.bot, callback.message.chat.id, callback.from_user.id, state, selected)


@router.callback_query(F.data.startswith("quick_review:"))
async def quick_review(callback: CallbackQuery, state: FSMContext):
    """دکمه‌ی «🎴 مرور سریع» - به‌جای اینکه کاربر رو مجبور کنه کل بخش (که
    ممکنه فقط برای یه سؤال باشه) رو دوباره بخونه، همون فلش‌کارت‌هایی که به
    این بخش‌ها مربوطن رو نشون می‌ده - نکته‌ی کلیدی، نه متن کامل بخش."""
    target_ids = set(callback.data.split(":", 1)[1].split(","))
    await callback.answer()

    cards = load_flashcards("L1")["cards"]
    matching = [c for c in cards if set(_extract_section_ids(c.get("section_ref", ""))) & target_ids]
    if not matching:
        await callback.message.answer(
            "فعلاً فلش‌کارتی برای این بخش‌ها نداریم؛ می‌تونی از «این بخش‌ها رو کامل بخون» استفاده کنی."
        )
        return

    await state.update_data(fc_cards=matching, fc_index=0, fc_known=0)
    await _send_flashcard(callback.bot, callback.message.chat.id, state)


async def _send_test_question(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    questions = data["test_questions"]
    index = data["test_index"]

    if index >= len(questions):
        await _finish_test(bot, chat_id, state)
        return

    q = questions[index]
    options = list(q["options"])
    correct_text = options[q["correct"]]
    random.shuffle(options)
    shuffled_correct_index = options.index(correct_text)

    await state.update_data(
        current_q_options=options,
        current_q_correct_index=shuffled_correct_index,
        current_q_id=q["id"],
        current_q_section=q.get("section_ref", ""),
        current_q_hint=q.get("hint"),
        current_q_sent_at=time.time(),
        current_q_poll_id=None,
        # هر دو flag برای هر سوال جدید ریست می‌شن: hint_shown تشخیص «تلاش
        # اول یا retry»، settled جلوی finalize دوباره‌ی همون سوال رو می‌گیره.
        current_q_hint_shown=False,
        current_q_settled=False,
    )

    header = f"📝 سوال {index + 1} از {len(questions)}:\n\n"

    if _question_fits_poll(q):
        # قبلاً type="quiz" بود با correct_option_id. برای Hint+Retry به
        # type="regular" تغییر کرد چون Quiz Poll بعد از اولین رأی از سمت
        # کلاینت تلگرام قفل می‌شه (امکان رأی دوباره نیست) و جواب درست رو
        # native نشون می‌ده - هر دو با این feature در تضادن. Regular Poll
        # اجازه‌ی رأی دوباره (نامحدود) می‌ده؛ محدودکردن به دقیقاً یک retry
        # وظیفه‌ی خودِ کد شده (current_q_hint_shown/current_q_settled در
        # handle_test_poll_answer)، نه تلگرام. correct_option_id فقط برای
        # type="quiz" معتبره، برای regular اصلاً نباید پاس داده بشه.
        sent = await bot.send_poll(
            chat_id,
            question=(header + q["q"])[:300],
            options=options,
            type="regular",
            is_anonymous=False,
        )
        await state.update_data(current_q_poll_id=sent.poll.id)
    else:
        # فقط برای سوالاتی که آیه‌ی کامل تو گزینه‌شونه و از محدودیت Poll رد می‌زنن.
        text = header + escape(q["q"]) + "\n\n" + render_options_list(options)
        await bot.send_message(
            chat_id, text, reply_markup=test_choice_keyboard(options), parse_mode="HTML"
        )

    await state.set_state(TestMode.awaiting_answer)


# متن hint وقتی سؤال فیلد "hint" نداره (الان یعنی هر ۵۱ سؤال، چون هنوز
# hint واقعی ننوشتیم) - fallback عمومی، نه چیزی مخصوص یه سؤال خاص.
_DEFAULT_HINT = "یه بار دیگه با دقت گزینه‌ها رو بخون؛ یکیشون از بقیه به متن دقیق‌تره."


async def _show_hint_and_await_retry(bot: Bot, chat_id: int, state: FSMContext, data: dict) -> None:
    """تلاش اول غلط بوده و هنوز finalize نشده. hint رو نشون می‌ده و منتظر
    retry می‌مونه. مسیر دکمه و poll این‌جا از هم جدا می‌شن چون UI فرق داره:
    دکمه یه کیبورد retry جدا لازم داره، ولی poll نیازی نداره چون خودِ
    revote-کردن روی همون poll همون retry حساب می‌شه."""
    hint_text = data.get("current_q_hint") or _DEFAULT_HINT
    await state.update_data(current_q_hint_shown=True)

    is_poll_question = data.get("current_q_poll_id") is not None
    if is_poll_question:
        await bot.send_message(
            chat_id,
            f"💡 {escape(hint_text)}\n\nرأیت رو عوض کن و گزینه‌ی دیگه‌ای رو انتخاب کن.",
            parse_mode="HTML",
        )
    else:
        await bot.send_message(
            chat_id, f"💡 {escape(hint_text)}", reply_markup=test_retry_keyboard(), parse_mode="HTML"
        )
    # برای مسیر دکمه لازمه (هندلر test_retry با همین state فیلتر شده). برای
    # مسیر poll اثر عملی نداره چون handle_test_poll_answer روی هیچ state‌ای
    # فیلتر نشده - فقط برای consistency ست می‌شه.
    await state.set_state(TestMode.awaiting_retry)


async def _finalize_answer(
    bot: Bot, chat_id: int, state: FSMContext, chosen_index: int, user_id: int, used_hint: bool
) -> None:
    """تنها نقطه‌ای که یه سؤال واقعاً scoring/log می‌شه - یا از تلاش اولِ
    درست میاد اینجا، یا از تلاش دومِ (retry) درست/غلط. تلاش اولِ غلط هرگز
    به این تابع نمی‌رسه (به‌جاش _show_hint_and_await_retry صدا زده می‌شه)."""
    data = await state.get_data()
    if data.get("current_q_settled"):
        # گارد نهایی؛ عملاً برای رأی سوم‌به‌بعد رو یه regular poll یا هر
        # race دیگه‌ای که باعث بشه این تابع دوبار برای یه سؤال صدا زده بشه.
        return
    await state.update_data(current_q_settled=True)

    correct_index = data["current_q_correct_index"]
    options = data["current_q_options"]
    is_correct = chosen_index == correct_index
    seconds_taken = time.time() - data["current_q_sent_at"]
    is_fast = seconds_taken < _FAST_ANSWER_THRESHOLD_SECONDS

    if is_correct:
        feedback = random.choice(_CORRECT_FEEDBACK)
    else:
        feedback = f"📚 پاسخ درست: <b>{escape(options[correct_index])}</b>\n{random.choice(_REVIEW_SUGGESTIONS)}"
    if is_fast:
        # همون لحظه، نه فقط تو جمع‌بندی آخر - کاربر رو سرِ حین کار متوجه می‌کنیم،
        # نه بعد از اینکه کل تست تموم شد.
        feedback += "\n\n" + random.choice(_FAST_ANSWER_NUDGES)

    new_test_index = data["test_index"] + 1
    is_last_question = new_test_index >= len(data["test_questions"])
    next_label = "📊 مشاهده نتیجه تست" if is_last_question else "➡️ سؤال بعدی"
    await bot.send_message(
        chat_id, feedback, reply_markup=_test_next_question_keyboard(next_label), parse_mode="HTML"
    )

    log_test_answer(
        user_id=user_id,
        question_id=data["current_q_id"],
        section_ref=data["current_q_section"],
        is_correct=is_correct,
        seconds_taken=seconds_taken,
        session_id=data["test_session_id"],
        used_hint=used_hint,
    )

    record_active_day(user_id, datetime.now(timezone.utc).date())

    wrong_sections = data["test_wrong_sections"]
    if not is_correct:
        wrong_sections = wrong_sections + [data["current_q_section"]]

    await state.update_data(
        test_correct=data["test_correct"] + (1 if is_correct else 0),
        test_wrong_sections=wrong_sections,
        test_index=new_test_index,
        test_fast_answers=data.get("test_fast_answers", 0) + (1 if is_fast else 0),
    )
    # به‌جای رفتن خودکار به سؤال بعد، صبر می‌کنیم تا کاربر خودش رو «➡️ سؤال بعدی»
    # کلیک کنه - همون فرصت خوندن feedback که قبلاً نبود.
    await state.set_state(TestMode.awaiting_next)


async def _handle_test_answer_attempt(
    bot: Bot, chat_id: int, state: FSMContext, chosen_index: int, user_id: int
) -> None:
    """نقطه‌ی ورودی مشترک هر دو مسیر (دکمه + poll) برای هر رأی/کلیک. تشخیص
    «تلاش اول یا retry» و «آیا سؤال از قبل settle شده» فقط از روی
    current_q_hint_shown/current_q_settled تو FSM data - نه از aiogram
    state - چون هندلر poll_answer روی هیچ state‌ای فیلتر نیست."""
    data = await state.get_data()
    if data.get("current_q_settled"):
        return

    is_first_attempt = not data.get("current_q_hint_shown")
    is_correct = chosen_index == data["current_q_correct_index"]

    if is_first_attempt and not is_correct:
        await _show_hint_and_await_retry(bot, chat_id, state, data)
        return

    await _finalize_answer(bot, chat_id, state, chosen_index, user_id, used_hint=not is_first_attempt)


@router.callback_query(F.data == "test_next_question", TestMode.awaiting_next)
async def handle_test_next_question(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await _send_test_question(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data.startswith("test_choice:"), TestMode.awaiting_answer)
async def handle_test_choice(callback: CallbackQuery, state: FSMContext):
    chosen_index = int(callback.data.split(":")[1])
    await callback.answer()
    await _handle_test_answer_attempt(callback.bot, callback.message.chat.id, state, chosen_index, callback.from_user.id)


@router.callback_query(F.data == "test_retry", TestMode.awaiting_retry)
async def handle_test_retry(callback: CallbackQuery, state: FSMContext):
    """فقط مسیر دکمه: همون سؤال (همون shuffle قبلی، بدون تغییر گزینه‌ها) رو
    دوباره با test_choice_keyboard می‌فرسته و منتظر جواب دوم می‌مونه."""
    await callback.answer()
    data = await state.get_data()
    questions = data["test_questions"]
    index = data["test_index"]
    q = questions[index]
    options = data["current_q_options"]

    header = f"📝 سوال {index + 1} از {len(questions)} (تلاش دوباره):\n\n"
    text = header + escape(q["q"]) + "\n\n" + render_options_list(options)
    await callback.message.answer(text, reply_markup=test_choice_keyboard(options), parse_mode="HTML")
    await state.set_state(TestMode.awaiting_answer)


@router.poll_answer()
async def handle_test_poll_answer(poll_answer: PollAnswer, state: FSMContext, bot: Bot):
    data = await state.get_data()
    if data.get("current_q_poll_id") != poll_answer.poll_id:
        return  # مربوط به تست فعلی این کاربر نیست (مثلاً poll قدیمی/بی‌ربط)
    if not poll_answer.option_ids:
        return  # کاربر رأیش رو پس گرفت (retract)، منتظر رأی بعدی می‌مونیم
    chosen_index = poll_answer.option_ids[0]
    await _handle_test_answer_attempt(bot, poll_answer.user.id, state, chosen_index, poll_answer.user.id)


async def _finish_test(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    total = len(data["test_questions"])
    correct = data["test_correct"]
    wrong_sections = data["test_wrong_sections"]
    fast_answers = data.get("test_fast_answers", 0)
    user_id = chat_id  # چت خصوصیه، چت‌آیدی همون یوزرآیدیه

    pct = round((correct / total) * 100) if total else 0

    # فاز 5C: بازطراحی presentation - همون داده‌های واقعی (total/correct/
    # pct/wrong_sections)، فقط متن خواناتر و دوستانه‌تر با یه هدر مشخص و
    # خطوط جدا برای هر بخش. منطق retry/hint/poll/محاسبه‌ی این مقادیر دست‌نخورده.
    lines = [f"🎯 نتیجه‌ی تست\nاز {total} سؤالی که جواب دادی:"]
    lines.append(f"✅ {correct} تا رو عالی زدی")
    if total - correct:
        lines.append(f"📚 {total - correct} تا هنوز جا برای بهتر شدن دارن")
    lines.append(f"📊 نتیجه: {pct}٪")

    # تشخیص جواب‌دادن خیلی سریع (احتمال شانسی‌زدن) - فقط یه یادآوری ملایم،
    # نه قضاوت. با داده‌ای که همین الان هم لاگ می‌شه (seconds_taken).
    if total >= 3 and fast_answers / total >= 0.5:
        lines.append(
            "\n⏱️ به نظر می‌رسه بعضی سؤالا رو خیلی سریع جواب دادی. "
            "اگه با دقت بیشتری جواب بدی، نتیجه واقعی‌تر نشون می‌ده چقدر بلدی."
        )

    weak_review_ids: list[str] = []
    if wrong_sections:
        counts: dict[str, int] = {}
        for section in wrong_sections:
            counts[section] = counts.get(section, 0) + 1
        lines.append("\nجایی که یه مرور کوچیک بهش میاد:")
        for section, cnt in sorted(counts.items(), key=lambda item: -item[1]):
            lines.append(f"• {section}: {cnt} سؤال")

        for section in wrong_sections:
            for sid in _extract_section_ids(section):
                if sid not in weak_review_ids:
                    weak_review_ids.append(sid)
    else:
        lines.append("\n🎉 همه‌ی سؤال‌ها رو عالی زدی!")

    # قبلاً وقتی wrong_sections خالی بود (یعنی نتیجه‌ی نهایی همه درست)، هیچ
    # کیبوردی فرستاده نمی‌شد - باگ اصلی همینجا بود. الان همیشه یه کیبورد
    # ادامه‌مسیر می‌فرستیم: بر اساس نتیجه‌ی نهایی (بعد از احتساب retry)، نه
    # صرفاً وجود weak_review_ids - چون ممکنه section_id از section_ref قابل
    # استخراج نباشه ولی همچنان سؤال غلطی وجود داشته باشه.
    if wrong_sections:
        keyboard = test_result_needs_review_keyboard(weak_review_ids)
    else:
        keyboard = test_result_success_keyboard()
    await bot.send_message(chat_id, "\n".join(lines), reply_markup=keyboard)

    await state.clear()


@router.callback_query(F.data == "test_again")
async def handle_test_again(callback: CallbackQuery, state: FSMContext):
    """دکمه‌ی «🧪 تست بیشتر بزنیم» بعد از نتیجه‌ی موفق. state تو _finish_test
    با state.clear() پاک شده، پس هیچ داده‌ی session قبلی (test_questions,
    test_index, current_q_* و...) باقی نمی‌مونه؛ prompt_test_count دقیقاً
    همون مسیر ورودی عادی «چند تا سوال بزنیم؟» رو از اول شروع می‌کنه، پس
    سناریوی «تست → پایان → تست بیشتر → تست جدید» توسط این پاک‌سازی همین
    الان هم تضمین می‌شه."""
    await callback.answer()
    await prompt_test_count(callback.bot, callback.message.chat.id, state)


@router.callback_query(F.data == "continue_lesson")
async def handle_continue_lesson(callback: CallbackQuery, state: FSMContext):
    """دکمه‌ی «📚 درس بخونیم» بعد از نتیجه‌ی موفق. طبق الگوی موجود پروژه
    (diagnostic.py هم برای ورود به درس از enter_lesson تو lesson.py استفاده
    می‌کنه)، همینجا هم همون تابع صدا زده می‌شه.

    ⚠️ FACT-CHECK لازم قبل از اجرا: lesson.py تو این جلسه در اختیارم نبوده،
    پس امضای enter_lesson (پارامترها، ترتیب آرگومان‌ها) رو حدس زدم بر اساس
    الگوی توابع مشابه تو همین فایل (مثل prompt_test_count(bot, chat_id,
    state)). قبل از تست واقعی، این import/فراخوانی رو با کد واقعی lesson.py
    تطبیق بده - اگه امضا فرق داره، فقط همین یه خط نیاز به اصلاح داره."""
    await callback.answer()
    from bot.handlers.lesson import enter_lesson  # ایمپورت داخل تابع، برای جلوگیری از circular import با lesson.py
    await enter_lesson(callback.bot, callback.message.chat.id, state)


# ---------- فلش‌کارت ----------

@router.callback_query(F.data.startswith("fc_count:"), FlashcardMode.choosing_count)
async def start_flashcards(callback: CallbackQuery, state: FSMContext):
    count = int(callback.data.split(":")[1])
    await callback.answer()

    cards = load_flashcards("L1")["cards"]
    count = min(count, len(cards))
    selected = random.sample(cards, count)

    await state.update_data(fc_cards=selected, fc_index=0, fc_known=0)
    await _send_flashcard(callback.bot, callback.message.chat.id, state)


async def _send_flashcard(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    cards = data["fc_cards"]
    index = data["fc_index"]

    if index >= len(cards):
        await _finish_flashcards(bot, chat_id, state)
        return

    card = cards[index]
    text = f"🎴 کارت {index + 1} از {len(cards)}\n\n{escape(card['front'])}"
    await bot.send_message(chat_id, text, reply_markup=flashcard_reveal_keyboard(), parse_mode="HTML")
    await state.set_state(FlashcardMode.awaiting_reveal)


@router.callback_query(F.data == "fc_reveal", FlashcardMode.awaiting_reveal)
async def reveal_flashcard(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    card = data["fc_cards"][data["fc_index"]]
    await callback.message.answer(
        f"📝 جواب:\n{escape(card['back'])}", reply_markup=flashcard_selfcheck_keyboard(), parse_mode="HTML"
    )
    await state.set_state(FlashcardMode.awaiting_selfcheck)


@router.callback_query(F.data.startswith("fc_know:"), FlashcardMode.awaiting_selfcheck)
async def handle_flashcard_selfcheck(callback: CallbackQuery, state: FSMContext):
    knew_it = callback.data.split(":")[1] == "yes"
    await callback.answer()
    data = await state.get_data()
    card = data["fc_cards"][data["fc_index"]]

    log_flashcard_result(
        user_id=callback.from_user.id,
        card_id=card["id"],
        section_ref=card.get("section_ref", ""),
        knew_it=knew_it,
    )

    record_active_day(callback.from_user.id, datetime.now(timezone.utc).date())

    await state.update_data(
        fc_known=data["fc_known"] + (1 if knew_it else 0),
        fc_index=data["fc_index"] + 1,
    )
    await _send_flashcard(callback.bot, callback.message.chat.id, state)


async def _finish_flashcards(bot: Bot, chat_id: int, state: FSMContext) -> None:
    data = await state.get_data()
    total = len(data["fc_cards"])
    known = data["fc_known"]
    await bot.send_message(chat_id, f"🏁 مرور تموم شد: {known} از {total} تا رو بلد بودی.")
    await state.clear()
    await bot.send_message(
        chat_id, "برای ادامه از دکمه‌های پایین انتخاب کن 👇", reply_markup=main_menu_reply_keyboard()
    )
