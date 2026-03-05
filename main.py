# -*- coding: utf-8 -*-
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.dispatcher.middlewares.base import BaseMiddleware

from config import BOT_TOKEN, ADMIN_ID
from commands import router
from user_id import is_user_allowed
from i18n import get_lang

if not BOT_TOKEN:
    raise SystemExit("Set BOT_TOKEN in environment.")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
dp.include_router(router)


class UserPermissionMiddleware(BaseMiddleware):
    """Middleware to check if user is allowed to use the bot."""

    async def on_process_message(self, message: Message, data: dict):
        user_id = message.from_user.id
        # Allow admin to use all commands
        if user_id == ADMIN_ID:
            return
        # Check if user is in allowed list
        if not is_user_allowed(user_id):
            # Check user language for response
            lang = get_lang(user_id)
            if lang == "vi":
                await message.answer("Bạn không được cấp quyền hãy liên hệ với admin @idkbroo_fr")
            else:
                await message.answer("You don't have permission. Please contact the admin @idkbroo_fr.")
            raise asyncio.CancelledError()


# Register middleware
dp.message.middleware(UserPermissionMiddleware())

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
