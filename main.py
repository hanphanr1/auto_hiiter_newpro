# -*- coding: utf-8 -*-
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_ID
from commands.start import router as start_router
from commands.admin import router as admin_router
from commands.proxy_cmd import router as proxy_router
from commands.co import router as co_router
from commands.filter_cc import router as filter_cc_router
from commands.scanner import router as scanner_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN in environment.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Register all routers
dp.include_router(start_router)
dp.include_router(admin_router)
dp.include_router(proxy_router)
dp.include_router(co_router)
dp.include_router(filter_cc_router)
dp.include_router(scanner_router)

logger.info(f"Starting bot with ADMIN_ID: {ADMIN_ID}")

async def main():
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        from hitter.stripe_charge import close_session
        from hitter.browser_charge import close_browser
        await close_session()
        await close_browser()

if __name__ == "__main__":
    asyncio.run(main())
