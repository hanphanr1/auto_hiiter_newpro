# -*- coding: utf-8 -*-
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode

from i18n import set_lang, get_lang, t

router = Router()

_LANG_KB = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang:en"),
        InlineKeyboardButton(text="🇻🇳 Tiếng Việt", callback_data="set_lang:vi"),
    ]
])


@router.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(
        "🌟 <b>Welcome / Chào mừng!</b> 🌟\n\n"
        "📱 Please select your language / Vui lòng chọn ngôn ngữ:",
        reply_markup=_LANG_KB,
        parse_mode=ParseMode.HTML,
    )


@router.callback_query(F.data.startswith("set_lang:"))
async def cb_set_lang(cb: CallbackQuery):
    lang = cb.data.split(":")[1]
    uid = cb.from_user.id
    set_lang(uid, lang)
    await cb.answer(t(uid, "lang_set"))
    await cb.message.edit_text(
        t(uid, "help"),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@router.message(Command("help"))
async def cmd_help(msg: Message):
    uid = msg.from_user.id
    lang = get_lang(uid)
    if not lang:
        await msg.answer(
            "🌟 <b>Welcome / Chào mừng!</b> 🌟\n\n"
            "📱 Please select your language / Vui lòng chọn ngôn ngữ:",
            reply_markup=_LANG_KB,
            parse_mode=ParseMode.HTML,
        )
        return
    await msg.answer(
        t(uid, "help"),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@router.message(Command("lang"))
async def cmd_lang(msg: Message):
    await msg.answer(
        "🌟 <b>Change Language / Đổi ngôn ngữ</b> 🌟\n\n"
        "📱 Please select / Vui lòng chọn:",
        reply_markup=_LANG_KB,
        parse_mode=ParseMode.HTML,
    )
