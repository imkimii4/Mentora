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
    شروع می‌کنه؛ اسمش باید با رفتار واقعیش یکی باشه."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 شروع درس")],
            [KeyboardButton(text="📑 انتخاب بخش")],
            [KeyboardButton(text="📝 تست بزن"), KeyboardButton(text="🎴 فلش‌کارت بخون")],
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
    با شمارش «چندتا مونده»). دکمه‌ی تمرین جدید هم همینجا کنارشونه."""
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
