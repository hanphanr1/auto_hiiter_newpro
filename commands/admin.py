# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

from config import ADMIN_ID
from user_id import add_user, remove_user, get_allowed_users

router = Router()

NO_PERMISSION_MSG = "Bạn không được cấp quyền hãy liên hệ với admin @idkbroo_fr"


def is_admin(user_id: int) -> bool:
    """Check if user is admin."""
    return user_id == ADMIN_ID


@router.message(Command("adduser"))
async def cmd_adduser(msg: Message):
    """Add a user to allowed list - admin only."""
    if not is_admin(msg.from_user.id):
        await msg.answer(NO_PERMISSION_MSG)
        return

    # Parse user ID from command
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /adduser <user_id>")
        return

    try:
        user_id_to_add = int(args[1])
    except ValueError:
        await msg.answer("Invalid user ID. Must be a number.")
        return

    if add_user(user_id_to_add):
        await msg.answer(f"✅ User <code>{user_id_to_add}</code> đã được thêm vào danh sách.")
    else:
        await msg.answer(f"ℹ️ User <code>{user_id_to_add}</code> đã có trong danh sách.")


@router.message(Command("removeuser"))
async def cmd_removeuser(msg: Message):
    """Remove a user from allowed list - admin only."""
    if not is_admin(msg.from_user.id):
        await msg.answer(NO_PERMISSION_MSG)
        return

    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("Usage: /removeuser <user_id>")
        return

    try:
        user_id_to_remove = int(args[1])
    except ValueError:
        await msg.answer("Invalid user ID. Must be a number.")
        return

    if remove_user(user_id_to_remove):
        await msg.answer(f"✅ User <code>{user_id_to_remove}</code> đã được xóa khỏi danh sách.")
    else:
        await msg.answer(f"ℹ️ User <code>{user_id_to_remove}</code> không có trong danh sách.")


@router.message(Command("listusers"))
async def cmd_listusers(msg: Message):
    """List all allowed users - admin only."""
    if not is_admin(msg.from_user.id):
        await msg.answer(NO_PERMISSION_MSG)
        return

    users = get_allowed_users()
    if not users:
        await msg.answer("Chưa có user nào được thêm.")
        return

    user_list = "\n".join([f"• <code>{uid}</code>" for uid in sorted(users)])
    await msg.answer(f"Danh sách user được phép sử dụng bot:\n\n{user_list}")
