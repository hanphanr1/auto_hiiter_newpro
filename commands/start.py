# -*- coding: utf-8 -*-
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

router = Router()

HELP_TEXT = """<b>Bot Telegram – CC Filter & Auto Hitter</b>

<b>1. Lọc CC</b>
• Gửi <b>file .txt</b> chứa CC → Bot lọc ra <code>cc|mm|yy|cvv</code>, trả file .txt
• Gửi <b>text</b> có CC → Bot reply các dòng CC

<b>2. Auto Hitter (Stripe)</b>
• <code>/co &lt;url&gt;</code> – Parse checkout
• <code>/co &lt;url&gt; cc|mm|yy|cvv</code> – Charge 1 thẻ
• <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> – Gen thẻ từ BIN & hit (tối đa 50)

<b>3. Proxy</b>
• <code>/addproxy host:port:user:pass</code> – Thêm proxy (tự check alive)
• <code>/removeproxy all</code> – Xóa hết proxy
• <code>/proxy</code> – Xem proxy | <code>/proxy check</code> – Check alive

<b>Tính năng nâng cao:</b>
• Proxy auto-rotate khi hit
• Random billing address / user-agent / timezone (bypass anti-fraud)
• Luhn card gen từ BIN (như UsagiAutoX / TPropaganda)
• Retry tự động khi disconnect/timeout"""

@router.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(HELP_TEXT, parse_mode=ParseMode.HTML)

@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(HELP_TEXT, parse_mode=ParseMode.HTML)
