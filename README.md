# SmartSchoolBot — اسکلت فاز کدنویسی (v0.1)

این اسکلت، جریان کامل درس اول رو با State Machine + Rule Engine مینیمال پیاده کرده.
هنوز چیزی روی تلگرام تست نشده — قدم بعدی گرفتن توکن از BotFather و اجراست.

## ساختار پروژه

```
smartschoolbot/
├── main.py                  # نقطه ورود - راه‌اندازی بات و polling
├── config.py                 # تنظیمات (توکن، threshold های rule engine)
├── requirements.txt
├── .env.example
├── data/
│   ├── lesson1.json          # همون فایلی که آپلود کردی
│   ├── flashcards_L1.json
│   └── test_bank_L1.json
└── bot/
    ├── states.py              # تعریف FSM states
    ├── rule_engine.py         # ۲ قانون: Consecutive Errors + Fatigue
    ├── data_loader.py         # لود و ایندکس JSON ها
    ├── renderer.py            # تبدیل message type ها به متن HTML
    ├── keyboards.py           # inline keyboard ها
    └── handlers/
        ├── onboarding.py      # /start
        └── lesson.py          # هسته‌ی اصلی: پیشروی درس + quiz + rule engine
```

## چطور اجرا کنم (لوکال، قبل از Railway)

```bash
cd smartschoolbot
pip install -r requirements.txt
export BOT_TOKEN="توکنی که از BotFather گرفتی"
python main.py
```

اگه توکن نداری، این خودش قدم بعدیه (شماره ۵ توی پلن اصلی‌ت): برو به @BotFather توی
تلگرام، `/newbot` بزن، اسم بده، توکن رو کپی کن.

## چی کار می‌کنه الان

- `/start` → پیام خوش‌آمد ساده → دکمه‌ی «شروع درس اول»
- کلیک روی شروع → بخش ۱ لود می‌شه، پیام‌های intro/hook نمایش داده می‌شن
- پیام‌های بدون دکمه (`button: null`) خودکار پشت‌سرهم می‌رن
- پیام‌های با دکمه (`ادامه`, `جواب رو ببینم`, ...) منتظر کلیک کاربر می‌مونن
- quiz های `multiple_choice` → دکمه‌های گزینه، quiz های `fill_blank` → منتظر تایپ جواب
- بعد از هر پاسخ، Rule Engine چک می‌کنه:
  - ۳ غلط متوالی → پیام re-teach (فعلاً placeholder، محتوای واقعی‌ش باید طراحی بشه)
  - افت دقت نسبت به کل جلسه (بعد از ۵ پاسخ) → پیشنهاد استراحت
- آخر هر بخش → outro، بعد بخش بعدی خودکار شروع می‌شه
- آخر بخش ۱۳ → پیام پایان درس

## چی کار نمی‌کنه / هنوز نساختیم

- ذخیره‌سازی دائمی (الان `MemoryStorage` هست؛ با ری‌استارت Railway، session های
  در حال انجام پاک می‌شن. برای تست با ۵-۱۰ نفر مشکلی نیست، ولی قبل از عمومی‌شدن
  باید بریم سراغ persistent storage)
- `quick_summary` mode (نسخه‌ی ۳۰ ثانیه‌ای) — فقط ساختار موجوده، هنوز وایر نشده به
  یه دکمه‌ی انتخاب سرعت در onboarding
- Diagnostic Test (طبق تصمیم، تأخیریه - بعد از درس ۲+)
- مدل درآمدی / paywall (طبق پلن: تست اولیه بدون paywall)
- متن نهایی پیام‌های onboarding و رفتار re-teach/fatigue (placeholder فعلی)
- درس‌های بعدی (`data_loader.py` فعلاً فقط L1 رو می‌شناسه؛ وقتی درس ۲ اومد باید
  mapping اونجا به دیکشنری تبدیل بشه)

## قدم بعدی پیشنهادی

۱. گرفتن توکن از BotFather و تست واقعی `/start` تا آخر درس با خودت
۲. دیدن اینکه کجاها متن‌ها/تایمینگ عجیب به نظر می‌رسه (مخصوصاً پیام‌های بدون دکمه که
   پشت‌سرهم می‌رن — ممکنه بخوای بینشون یه تأخیر کوچیک بذاری)
۳. طراحی متن دقیق onboarding
۴. دیپلوی روی Railway (همون فرآیندی که برای PetBarkGameBot طی کردی)
