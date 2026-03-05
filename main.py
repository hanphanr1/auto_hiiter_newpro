# -*- coding: utf-8 -*-
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.filters import Filter

from config import BOT_TOKEN, ADMIN_ID
from commands.start import router as start_router
from commands.admin import router as admin_router
from commands.proxy_cmd import router as proxy_router
from commands.co import router as co_router
from commands.filter_cc import router as filter_cc_router
from user_id import is_user_allowed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN in environment.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


class IsAdminOrAllowed(Filter):
    """Check if user is admin or allowed."""

    async def __call__(self, message: Message) -> bool:
        # Allow /start
        if message.text and message.text.strip().startswith("/start"):
            return True

        user_id = message.from_user.id
        logger.info(f"User: {user_id}, admin: {ADMIN_ID}")

        # Allow admin
        if user_id == ADMIN_ID:
            return True

        # Check allowed users
        if not is_user_allowed(user_id):
            await message.answer("You don't have permission. Contact admin @idkbroo_fr")
            return False

        return True


# Register all routers
dp.include_router(start_router)
dp.include_router(admin_router)
dp.include_router(proxy_router)
dp.include_router(co_router)
dp.include_router(filter_cc_router)

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
