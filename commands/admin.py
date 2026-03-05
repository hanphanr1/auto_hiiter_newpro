# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from config import ADMIN_ID
from user_id import add_user, remove_user, get_allowed_users
import logging

logger = logging.getLogger(__name__)

router = Router()


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID


@router.message(Command("adduser"))
async def cmd_adduser(msg: Message):
    """Add a user to allowed list - admin only."""
    if not is_admin(msg.from_user.id):
        await msg.answer("You don't have permission.")
        return

    # Parse user ID from command
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /adduser USER_ID")
        return

    try:
        user_id_to_add = int(args[1])
    except ValueError:
        await msg.answer("Invalid user ID. Must be a number.")
        return

    if add_user(user_id_to_add):
        await msg.answer(f"User {user_id_to_add} added.")
    else:
        await msg.answer(f"User {user_id_to_add} already exists.")


@router.message(Command("removeuser"))
async def cmd_removeuser(msg: Message):
    """Remove a user from allowed list - admin only."""
    if not is_admin(msg.from_user.id):
        await msg.answer("You don't have permission.")
        return

    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /removeuser USER_ID")
        return

    try:
        user_id_to_remove = int(args[1])
    except ValueError:
        await msg.answer("Invalid user ID. Must be a number.")
        return

    if remove_user(user_id_to_remove):
        await msg.answer(f"User {user_id_to_remove} removed.")
    else:
        await msg.answer(f"User {user_id_to_remove} not found.")


@router.message(Command("listusers"))
async def cmd_listusers(msg: Message):
    """List all allowed users - admin only."""
    if not is_admin(msg.from_user.id):
        await msg.answer("You don't have permission.")
        return

    users = get_allowed_users()
    if not users:
        await msg.answer("No users added yet.")
        return

    user_list = "\n".join([f"- {uid}" for uid in sorted(users)])
    await msg.answer(f"Allowed users:\n\n{user_list}")
