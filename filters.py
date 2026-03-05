# -*- coding: utf-8 -*-
"""Custom filters for the bot."""
from aiogram.filters import Filter
from aiogram.types import Message

from config import ADMIN_ID
from user_id import is_user_allowed


class IsAdminOrAllowed(Filter):
    """Check if user is admin or allowed."""

    async def __call__(self, message: Message) -> bool:
        # Allow /start
        if message.text and message.text.strip().startswith("/start"):
            return True

        user_id = message.from_user.id

        # Allow admin
        if user_id == ADMIN_ID:
            return True

        # Check allowed users
        if not is_user_allowed(user_id):
            await message.answer("You don't have permission. Contact admin @idkbroo_fr")
            return False

        return True
