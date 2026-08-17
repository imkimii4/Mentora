import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from bot.handlers import onboarding, profile_onboarding, diagnostic, lesson, practice

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    # نکته برای بعد: MemoryStorage یعنی با هر ری‌استارت روی Railway،
    # session های در حال انجام کاربرها پاک می‌شن. برای MVP و تست با ۵-۱۰ نفر
    # مشکلی نیست؛ اگه بخوایم قابل اعتمادتر بشه، باید بریم سراغ
    # aiogram.fsm.storage.redis یا ذخیره‌ی state روی همون SQLite.
    storage = MemoryStorage()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=storage)

    dp.include_router(onboarding.router)
    dp.include_router(profile_onboarding.router)
    dp.include_router(diagnostic.router)
    dp.include_router(lesson.router)
    dp.include_router(practice.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
