# -*- coding: utf-8 -*-
import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from commands import router

if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN in environment.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(router)

async def main():
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        from hitter.stripe_charge import _session
        if _session and not _session.closed:
            await _session.close()

if __name__ == "__main__":
    asyncio.run(main())
