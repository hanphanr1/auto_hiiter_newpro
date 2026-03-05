# -*- coding: utf-8 -*-
"""Custom filters for the bot."""
from aiogram.filters import Filter
from aiogram.types import Message

from config import ADMIN_ID
from user_id import is_user_allowed


class IsAdmin(Filter):
    """Filter to check if user is admin."""

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id == ADMIN_ID


class IsAllowedUser(Filter):
    """Filter to check if user is allowed to use the bot."""

    async def __call__(self, message: Message) -> bool:
        # Allow /start command
        if message.text and message.text.strip().startswith("/start"):
            return True

        user_id = message.from_user.id

        # Allow admin
        if user_id == ADMIN_ID:
            return True

        # Check if user is allowed
        return is_user_allowed(user_id)
