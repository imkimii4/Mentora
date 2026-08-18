from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from bot.renderer import OPTION_LETTERS


def continue_keyboard(label: str = "ادامه") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=label, callback_data="continue")]]
    )


def quiz_choice_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    # لیبل دکمه فقط حرف (الف/ب/ج/د)، نه متن کامل گزینه — چون تلگرام دسکتاپ
    # متن طولانی رو رو دکمه‌ی inline truncate می‌کنه (به‌جای چندخطی‌شدن). متن
    # کامل گزینه‌ها تو خودِ پیام میاد (render_options_list تو renderer.py).
    # همه‌ی حروف تو یه ردیف، چون کوتاهن و جا می‌شن.
    buttons = [
        InlineKeyboardButton(text=OPTION_LETTERS[i], callback_data=f"quiz_choice:{i}")
        for i in range(len(options))
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def main_menu_reply_keyboard() -> ReplyKeyboardMarkup:
    """کیبورد شیشه‌ای ثابت پایین صفحه (کنار جعبه‌ی تایپ) — برخلاف inline
    keyboard که فقط زیر یه پیام خاصه و با اسکرول از چشم گم می‌شه، این همیشه
    پیداست، دقیقاً مثل منوی «/» که بات‌فادر می‌سازه ولی به‌شکل دکمه.
    لیبل «شروع درس» نه «ادامه» - چون resume واقعی هنوز نداریم، هر بار از اول
    شروع می‌کنه؛ اسمش باید با رفتار واقعیش یکی باشه.

    فاز 5D: چیدمان ۲×۲ برای ۴ دکمه‌ی اصلی محتوا (شروع درس/انتخاب بخش/تست/
    فلش‌کارت) - قبلاً «شروع درس» و «انتخاب بخش» هرکدوم ردیف جدا بودن، الان
    کنار هم؛ نتیجه یه گرید فشرده‌تر و متقارن‌تره. «👤 پروفایل من» عمداً بیرون
    از این گرید و ردیف آخر می‌مونه - این یه دکمه‌ی محتوایی نیست (مسیر
    معنایی‌ش با ۴ تای دیگه فرق داره)، پس تو گرید ۲×۲ محتوا جا نمی‌گیره،
    زیرش می‌مونه. متن/اموجی هر ۵ دکمه دقیقاً دست‌نخورده - هندلرهای F.text
    تو onboarding.py دقیقاً همین رشته‌ها رو match می‌کنن."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 شروع درس"), KeyboardButton(text="📑 انتخاب بخش")],
            [KeyboardButton(text="📝 تست بزن"), KeyboardButton(text="🎴 فلش‌کارت بخون")],
            [KeyboardButton(text="👤 پروفایل من")],
        ],
        resize_keyboard=True,
    )


def section_list_keyboard(sections: list[dict]) -> InlineKeyboardMarkup:
    """لیست بخش‌های درس برای انتخاب مستقیم (ورود مستقیم به یه بخش خاص،
    بدون نیاز به طی‌کردن بخش‌های قبلی). هر ردیف یه بخش؛ callback_data
    شامل section_id واقعی‌شه (مثل S6) نه شماره‌ی ذهنی، دقیقاً همون چیزی که
    get_section_index_by_id در data_loader.py انتظارش رو داره."""
    rows = [
        [InlineKeyboardButton(
            text=f"{s['section_id']} • {s['title']}",
            callback_data=f"select_section:{s['section_id']}",
        )]
        for s in sections
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def test_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="۵ سوال", callback_data="test_count:5"),
            InlineKeyboardButton(text="۱۰ سوال", callback_data="test_count:10"),
            InlineKeyboardButton(text="۱۵ سوال", callback_data="test_count:15"),
        ]]
    )


def test_choice_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    # namespace جدا (test_choice) از quiz_choice تو لسون، تا کالبک‌ها قاطی نشن.
    # اینجا هم فقط حرف کوتاه رو دکمه‌ست، متن کامل تو خودِ پیامه.
    buttons = [
        InlineKeyboardButton(text=OPTION_LETTERS[i], callback_data=f"test_choice:{i}")
        for i in range(len(options))
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def test_retry_keyboard() -> InlineKeyboardMarkup:
    # فقط مسیر دکمه‌ی تست ازش استفاده می‌کنه (بعد از جواب غلط تلاش اول و
    # نمایش hint). namespace جدا (test_retry) تا با test_choice/test_next_question
    # قاطی نشه.
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔁 یه بار دیگه امتحان کن", callback_data="test_retry")]]
    )


def flashcard_count_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="۵ کارت", callback_data="fc_count:5"),
            InlineKeyboardButton(text="۱۰ کارت", callback_data="fc_count:10"),
            InlineKeyboardButton(text="همه (۲۰ تا)", callback_data="fc_count:20"),
        ]]
    )


def flashcard_reveal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="👀 نمایش جواب", callback_data="fc_reveal")]]
    )


def flashcard_selfcheck_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ بلد بودم", callback_data="fc_know:yes"),
            InlineKeyboardButton(text="❌ بلد نبودم", callback_data="fc_know:no"),
        ]]
    )


def review_sections_keyboard(section_ids: list[str], retest_ids: list[str] | None = None) -> InlineKeyboardMarkup:
    """بعد از تست، به‌جای یه دکمه‌ی جدا برای هر بخش (که هم شلوغ می‌شد هم کاربر
    رو مجبور می‌کرد کل بخش رو برای یه سؤال بخونه)، فقط ۲ تا مسیر روشن می‌دیم:
    مرور سریع (فلش‌کارت، فقط نکته‌ی کلیدی) یا خوندن کامل بخش‌ها (به‌ترتیب،
    با شمارش «چندتا مونده»). دکمه‌ی تمرین جدید هم همینجا کنارشونه.

    NOTE: این تابع دیگه از _finish_test صدا زده نمی‌شه (جاش رو
    test_result_success_keyboard/test_result_needs_review_keyboard گرفتن)،
    ولی خودِ تابع و هندلر retest_weak_sections که بهش وابسته‌ست حذف نشدن -
    فقط دیگه دکمه‌ای بهشون منتهی نمی‌شه، برای اگه بعداً لازم شدن."""
    ids_param = ",".join(section_ids)
    rows = [
        [InlineKeyboardButton(text="🎴 مرور سریع (نکته‌های کلیدی)", callback_data=f"quick_review:{ids_param}")],
        [InlineKeyboardButton(text="📖 این بخش‌ها رو کامل بخون", callback_data=f"review_queue:{ids_param}")],
    ]
    if retest_ids:
        rows.append([
            InlineKeyboardButton(text="🔁 تمرین جدید همین بخش‌ها", callback_data=f"retest:{','.join(retest_ids)}")
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def test_result_success_keyboard() -> InlineKeyboardMarkup:
    """بعد از پایان تست وقتی نتیجه‌ی نهایی همه‌ی سؤال‌ها درسته (با احتساب
    retry) - دو مسیر ادامه: یه دور تست دیگه بزنه، یا برگرده تو درس.
    callback_data های جدا و مستقل (test_again / continue_lesson) - قاطی
    نمی‌شن با namespace های دیگه."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🧪 تست بیشتر بزنیم", callback_data="test_again"),
            InlineKeyboardButton(text="📚 درس بخونیم", callback_data="continue_lesson"),
        ]]
    )


def test_result_needs_review_keyboard(section_ids: list[str]) -> InlineKeyboardMarkup:
    """بعد از پایان تست وقتی کاربر تو حداقل یه سؤال (نهایتاً) مشکل داشته -
    سه مسیر یادگیری. callback_data های review_queue/quick_review/next_section
    از قبل تو پروژه وجود دارن (review_sections_keyboard و feedback_keyboard/
    next_section_keyboard)، اینجا فقط دوباره استفاده می‌شن، بازسازی نشدن."""
    ids_param = ",".join(section_ids)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 برو مرور کن", callback_data=f"review_queue:{ids_param}")],
            [InlineKeyboardButton(text="➡️ بریم بخش بعد", callback_data="next_section")],
            [InlineKeyboardButton(text="🧠 مرور نکات کلیدی", callback_data=f"quick_review:{ids_param}")],
        ]
    )


def feedback_keyboard(section_id: str) -> InlineKeyboardMarkup:
    """دکمه‌های لایک/دیس‌لایک/ایده + دکمه‌ی رفتن به بخش بعد، زیر پیام «این بخش رو چطور دیدی؟»."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👍 پسندیدم", callback_data=f"fb:like:{section_id}"),
                InlineKeyboardButton(text="👎 دوست نداشتم", callback_data=f"fb:dislike:{section_id}"),
            ],
            [InlineKeyboardButton(text="💡 ایده دارم", callback_data=f"fb:idea:{section_id}")],
            [InlineKeyboardButton(text="➡️ بخش بعد", callback_data="next_section")],
        ]
    )


def next_section_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="➡️ بخش بعد", callback_data="next_section")]]
    )


def onboarding_choice_keyboard() -> InlineKeyboardMarkup:
    """دو مسیر ورودی کاربر جدید: شروع سریع بدون آزمون، یا آزمون تشخیصی ۳
    سؤالی قبل از شروع. namespace این دو دکمه (onb_quick / onb_diagnostic)
    ثابت و جدا از هر callback دیگه‌ای تو پروژه‌ست."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="🚀 شروع سریع", callback_data="onb_quick"),
            InlineKeyboardButton(text="🎯 آزمون تشخیصی بزنم", callback_data="onb_diagnostic"),
        ]]
    )


def diagnostic_choice_keyboard(options: list[str]) -> InlineKeyboardMarkup:
    # namespace جدا (diag_choice) از quiz_choice و test_choice، تا با
    # هندلرهای LessonFlow/TestMode قاطی نشه - دقیقاً همون منطقی که خودِ
    # quiz_choice_keyboard و test_choice_keyboard قبلاً رعایت کردن.
    buttons = [
        InlineKeyboardButton(text=OPTION_LETTERS[i], callback_data=f"diag_choice:{i}")
        for i in range(len(options))
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


# --- Onboarding / User Profile (bot/handlers/profile_onboarding.py) ---
# هر سه لیست (key, label) هستن: key تو callback_data می‌ره و در
# profile_store ذخیره می‌شه (پایدار، مستقل از تغییر بعدی متن دکمه)، label
# چیزیه که کاربر می‌بینه. لیست‌ها اینجان (نه تو handler) چون خودِ
# profile_onboarding.py هم برای ساخت کیبورد هم برای اعتبارسنجی callback
# بهشون نیاز داره - دقیقاً مثل OPTION_LETTERS بالا که renderer.py هم ازش
# استفاده می‌کنه.

GRADE_OPTIONS: list[tuple[str, str]] = [
    ("g7", "هفتم"),
    ("g8", "هشتم"),
    ("g9", "نهم"),
    ("g10", "دهم"),
    ("g11", "یازدهم"),
    ("g12", "دوازدهم"),
    ("grad", "فارغ‌التحصیل / کنکوری"),
]

GOAL_OPTIONS: list[tuple[str, str]] = [
    ("school_exam", "📘 امتحان مدرسه"),
    ("konkur", "🎯 کنکور"),
    ("deep_learning", "🧠 یادگیری عمیق"),
    ("weak_points", "🔧 تقویت نقاط ضعف"),
]

DAILY_TIME_OPTIONS: list[tuple[str, str]] = [
    ("lt15", "کمتر از ۱۵ دقیقه"),
    ("15_30", "۱۵ تا ۳۰ دقیقه"),
    ("30_60", "۳۰ تا ۶۰ دقیقه"),
    ("gt60", "بیشتر از ۱ ساعت"),
]


def _chunked_choice_keyboard(
    options: list[tuple[str, str]], callback_prefix: str, per_row: int = 2
) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=label, callback_data=f"{callback_prefix}:{key}")
        for key, label in options
    ]
    rows = [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def grade_choice_keyboard() -> InlineKeyboardMarkup:
    return _chunked_choice_keyboard(GRADE_OPTIONS, "profile_grade", per_row=2)


def goal_choice_keyboard() -> InlineKeyboardMarkup:
    return _chunked_choice_keyboard(GOAL_OPTIONS, "profile_goal", per_row=2)


def daily_time_choice_keyboard() -> InlineKeyboardMarkup:
    return _chunked_choice_keyboard(DAILY_TIME_OPTIONS, "profile_time", per_row=2)
