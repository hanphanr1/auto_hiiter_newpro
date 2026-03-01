# -*- coding: utf-8 -*-
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

router = Router()

HELP_TEXT = """━━━━━━━━━━━━━━━━━━━━━━━━━━
  <b>TPTTH PRIVATE HITTER</b>
  <i>CC Filter & Auto Hitter</i>
━━━━━━━━━━━━━━━━━━━━━━━━━━

🔹 <b>CC FILTER</b>
├ Gửi <b>file .txt</b> → Lọc ra <code>cc|mm|yy|cvv</code>, trả file
├ Gửi <b>text</b> có CC → Reply các dòng CC
└ Tự nhận diện mọi format

🔹 <b>AUTO HITTER</b>
├ <code>/co &lt;url&gt;</code> — Parse checkout info
├ <code>/co &lt;url&gt; cc|mm|yy|cvv</code> — Hit 1 thẻ
├ <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> — Gen & hit (max 50)
└ Auto retry, random billing, anti-fraud bypass

🔹 <b>PROXY</b>
├ <code>/addproxy host:port:user:pass</code> — Add (auto check)
├ <code>/removeproxy all</code> — Remove all
├ <code>/proxy</code> — List | <code>/proxy check</code> — Check alive
└ Auto-rotate khi hit

━━━━━━━━━━━━━━━━━━━━━━━━━━
  <b>by @idkbroo_fr</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━"""

@router.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(HELP_TEXT, parse_mode=ParseMode.HTML)

@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(HELP_TEXT, parse_mode=ParseMode.HTML)
