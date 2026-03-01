# -*- coding: utf-8 -*-
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

router = Router()

HELP_TEXT = """<b>🤖 Bot Telegram – CC Filter & Auto Hitter</b>

<b>📌 Tính năng 1 – Lọc CC</b>
• Gửi <b>file .txt</b> chứa CC (hoặc text kiểu CHARGED/Approved) → Bot lọc ra dòng <code>cc|mm|yy|cvv</code> và trả file .txt hoặc text.
• Gửi <b>text</b> (1–2 tin) có CC → Bot trả lời bằng text chỉ gồm các dòng CC.

<b>📌 Tính năng 2 – Auto Hitter (Stripe)</b>
• <code>/co &lt;url_stripe_checkout&gt;</code> – Parse checkout.
• <code>/co &lt;url&gt; cc|mm|yy|cvv</code> – Charge 1 thẻ.
• <code>/co &lt;url&gt; bin &lt;BIN&gt; [số_lượng]</code> – Gen thẻ từ BIN và hit (mặc định 1 thẻ).

<b>Ví dụ</b>
<code>/co https://checkout.stripe.com/... 521853 5</code> – hit 5 thẻ gen từ BIN 521853."""

@router.message(Command("start"))
async def cmd_start(msg: Message):
    await msg.answer(HELP_TEXT, parse_mode=ParseMode.HTML)

@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(HELP_TEXT, parse_mode=ParseMode.HTML)
