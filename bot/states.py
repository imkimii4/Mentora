"""
State Machine اصلی بات (بر اساس aiogram FSM).

جریان کلی:
  Onboarding -> InLesson (پیام‌به‌پیام) -> InQuiz (منتظر پاسخ) -> InLesson -> ...
  -> SectionComplete -> InLesson (بخش بعد) -> ... -> LessonComplete

نکته: خودِ "کجای درس هستیم" (section_index, message_index, ...) در FSMContext.data
نگه‌داری می‌شه، نه در state name؛ state name فقط "نوع فعلی تعامل" رو مشخص می‌کنه
(مثلاً منتظر کلیک روی دکمه‌ایم یا منتظر تایپ جواب fill_blank).
"""
from aiogram.fsm.state import State, StatesGroup


class LessonFlow(StatesGroup):
    # کاربر در حال دیدن پیام‌های درس است؛ منتظر کلیک روی دکمه‌ی "ادامه" یا مشابه
    in_lesson = State()

    # یک quiz از نوع چندگزینه‌ای نمایش داده شده؛ منتظر کلیک روی یکی از گزینه‌هاست
    awaiting_quiz_choice = State()

    # یک quiz از نوع fill_blank نمایش داده شده؛ منتظر تایپ متن جواب است
    awaiting_fill_blank = State()

    # درس کامل شد
    lesson_complete = State()

    # پایان یک بخش؛ outro نمایش داده شده و منتظر کلیک کاربر برای رفتن به بخش بعدیم
    section_transition = State()

    # کاربر روی دکمه "💡 ایده دارم" زده؛ منتظر تایپ متن ایده‌شه
    awaiting_feedback_idea = State()


class Onboarding(StatesGroup):
    welcome = State()


class DiagnosticFlow(StatesGroup):
    """مسیر اختیاری آزمون تشخیصی ۳ سؤالی برای کاربر جدید، قبل از S1.

    انتخاب مسیر (شروع سریع / آزمون تشخیصی) خودش به یه state جدا نیاز نداره،
    چون callback_data دو دکمه (onb_quick / onb_diagnostic) به‌تنهایی
    namespace کافی برای تشخیص کلیک داره - نیازی به state guard نیست.
    state فقط از سؤال اول به بعد لازم می‌شه، تا هندلرهای diag_choice: بدونن
    این کلیک مربوط به کدوم سؤاله (q1/q2/q3)."""
    q1 = State()
    q2 = State()
    q3 = State()


class TestMode(StatesGroup):
    """جریان مستقل «تست بزن» از منوی اصلی — کاملاً جدا از LessonFlow.
    کاربر تعداد سوال رو انتخاب می‌کنه، سوالات رندوم از بانک ۵۱ تایی میان،
    و در پایان یه خلاصه‌ی نتیجه (درصد + تفکیک بخش‌های پرغلط) نشون داده می‌شه."""
    choosing_count = State()
    awaiting_answer = State()
    awaiting_next = State()


class FlashcardMode(StatesGroup):
    """جریان مستقل «فلش‌کارت بخون». هر کارت: نمایش سوال -> کاربر «نمایش جواب»
    می‌زنه -> جواب نشون داده می‌شه -> کاربر خودش می‌گه بلد بود یا نه (خودارزیابی،
    بدون AI). نتیجه فقط لاگ خام می‌شه؛ تحلیلش بعد از لانچه."""
    choosing_count = State()
    awaiting_reveal = State()
    awaiting_selfcheck = State()
