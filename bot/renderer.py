"""
تبدیل انواع مختلف 'type' موجود در lesson1.json به متن HTML مناسب تلگرام.

انواع type که در محتوای واقعی درس ۱ دیدیم:
  text, source_reference, quoted_text, translation, keywords,
  memory_hook, quiz, summary_list, golden_notes, reflection_prompt

پارس‌مود: HTML (parse_mode="HTML") - چون <blockquote> و <b> رو پشتیبانی می‌کنه
و برای متن فارسی/عربی مشکل escape کمتری نسبت به Markdown داره.
"""
import random
import re
from html import escape

# همون الگوی اعراب‌گذاری عربی که تو arabic_utils استفاده می‌شه؛ برای تشخیص
# اینکه یه quoted_text واقعاً آیه‌ی قرآنه (همیشه با اعراب کامل نوشته می‌شه)
# یا نقل‌قول فارسی/حدیثه (بدون اعراب).
_DIACRITICS_PATTERN = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u08D4-\u08E1\u08E3-\u08FF]"
)

# وقتی محتوا حاوی این عبارت باشه (پیام گذار به مرحله‌ی «کتاب رو ببند» در آخر
# هر بخش)، به‌جای متن ثابت، یکی از این نسخه‌ها به‌صورت تصادفی انتخاب می‌شه
# تا کاربر تو ۱۲ بخش پشت‌سرهم حس تکرار نکنه.
_BOOK_CLOSED_VARIANTS = [
    "📖 حالا کتاب رو ببند. نوبت مغزته — بدون نگاه به بالا:",
    "📖 کتاب رو ببند. ببینیم واقعاً چقدر تو ذهنت مونده:",
    "📖 دست از کتاب بکش. حالا فقط با حافظه‌ت جواب بده:",
    "📖 وقتشه بدون تقلب جواب بدی. کتاب رو ببند:",
    "📖 یه امتحان کوچیک از خودت بگیر — بدون نگاه‌کردن به بالا:",
    "📖 کتاب بسته! ببینیم چقدر واقعاً یاد گرفتی:",
    "📖 حالا نوبت خودتی. کتاب رو ببند و امتحان کن:",
    "📖 بدون کمک کتاب، ببین چقدر یادت مونده:",
]


_BOLD_MARKER_PATTERN = re.compile(r"\*\*(.+?)\*\*")


def _apply_bold_markers(text: str) -> str:
    """متن escape‌شده رو می‌گیره و **کلمه** رو به <b>کلمه</b> تبدیل می‌کنه.
    این یعنی هرجای lesson1.json که یه کلمه رو با ** دورش بذاریم، خودکار
    تو تلگرام بولد نمایش داده می‌شه، بدون نیاز به دست‌زدن به کد."""
    return _BOLD_MARKER_PATTERN.sub(r"<b>\1</b>", text)


def render_message(msg: dict) -> str:
    msg_type = msg["type"]
    raw = msg.get("content", "")
    content = _apply_bold_markers(escape(raw))

    if msg_type == "text":
        if "نوبت مغزته" in raw or "کتاب رو ببند" in raw:
            return random.choice(_BOOK_CLOSED_VARIANTS)
        return content

    if msg_type == "source_reference":
        return f"📖 <i>{content}</i>"

    if msg_type == "quoted_text":
        # اگه اعراب‌گذاری کامل داره، یعنی آیه‌ی قرآنه -> بولد هم بشه تا از
        # نقل‌قول‌های فارسی/حدیث (که اعراب ندارن) بصری متمایز باشه.
        if _DIACRITICS_PATTERN.search(raw):
            return f"<blockquote><b>{content}</b></blockquote>"
        return f"<blockquote>{content}</blockquote>"

    if msg_type == "translation":
        return f"🔤 {content}"

    if msg_type == "keywords":
        # فرمت هر خط: «🔑 ترم = توضیح». فقط خودِ ترم (قبل از =) رو بولد کن.
        lines = []
        for line in raw.split("\n"):
            if "=" in line:
                term, _, rest = line.partition("=")
                lines.append(f"<b>{escape(term.strip())}</b> ={_apply_bold_markers(escape(rest))}")
            else:
                lines.append(_apply_bold_markers(escape(line)))
        return "\n".join(lines)

    if msg_type == "memory_hook":
        return f"🧠 <b>قفل حافظه:</b>\n{content}"

    if msg_type == "summary_list":
        # خط اول (مقدمه) واضح می‌مونه؛ خط‌های شماره‌دار زیر اسپویلر می‌رن تا
        # کاربر قبل از دیدن جواب، خودش سعی کنه یادش بیاد.
        lines = raw.split("\n")
        rendered = []
        for line in lines:
            if re.match(r"^[۰-۹\d]+[.\)]", line.strip()):
                rendered.append(f"<tg-spoiler>{_apply_bold_markers(escape(line))}</tg-spoiler>")
            else:
                rendered.append(_apply_bold_markers(escape(line)))
        return "📋 " + "\n".join(rendered)

    if msg_type == "golden_notes":
        return f"⭐️ <b>نکات طلایی:</b>\n{content}"

    if msg_type == "reflection_prompt":
        return content

    # fallback برای type های ناشناخته (تا کرش نکنه اگه محتوای جدید فرمت جدید داشت)
    return content


def render_intro(section: dict) -> str:
    # عنوان بخش دیگه اینجا تکرار نمی‌شه - هدر بخش (تو _send_section_intro در
    # lesson.py) تنها منبع نمایش عنوانه. این تابع فقط hook و intro رو برمی‌گردونه.
    parts = []
    if section.get("hook"):
        parts.append(_apply_bold_markers(escape(section["hook"])))
    if section.get("intro"):
        parts.append(_apply_bold_markers(escape(section["intro"])))
    return "\n\n".join(parts)


def render_outro(section: dict) -> str:
    return _apply_bold_markers(escape(section.get("outro", "")))


def render_quiz_question(msg: dict) -> str:
    return f"❓ {escape(msg['question'])}"


# حروف گزینه‌ها (الف/ب/ج/د...) - هم تو متن پیام (کنار خودِ گزینه) و هم روی
# دکمه‌های شیشه‌ای (فقط حرف، بدون متن کامل) استفاده می‌شه. علتش: تلگرام دسکتاپ
# متن طولانی رو تو دکمه به‌جای چندخطی‌شدن، با ... قطع می‌کنه؛ برای همین متن کامل
# گزینه‌ها رو تو خودِ پیام می‌ذاریم و دکمه فقط حرف انتخابی رو نشون می‌ده.
OPTION_LETTERS = ["الف", "ب", "ج", "د", "ه", "و"]


def render_options_list(options: list[str]) -> str:
    lines = []
    for i, opt in enumerate(options):
        letter = OPTION_LETTERS[i] if i < len(OPTION_LETTERS) else str(i + 1)
        lines.append(f"<b>{letter})</b> {escape(opt)}")
    return "\n".join(lines)

