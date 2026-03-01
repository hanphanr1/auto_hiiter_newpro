# -*- coding: utf-8 -*-
"""Decode Stripe checkout URL and init – combined from autohitter + extensions.
- PK/CS decode (XOR from URL hash) from autohitter co_functions
- Detailed init parsing (amount, merchant, product, mode) from TPropaganda inject.js
- browser_locale/timezone from extensions
"""
import re
import base64
from urllib.parse import unquote
import aiohttp

from billing_data import build_stripe_headers, random_user_agent, random_locale, random_timezone

def extract_checkout_url(text: str) -> str | None:
    patterns = [
        r"https?://checkout\.stripe\.com/c/pay/cs_[^\s\"'<>\)]+",
        r"https?://checkout\.stripe\.com/[^\s\"'<>\)]+",
        r"https?://buy\.stripe\.com/[^\s\"'<>\)]+",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(0).rstrip(".,;:")
    return None

def decode_pk_from_url(url: str) -> dict:
    result = {"pk": None, "cs": None, "site": None}
    try:
        cs_match = re.search(r"cs_(live|test)_[A-Za-z0-9]+", url)
        if cs_match:
            result["cs"] = cs_match.group(0)
        if "#" not in url:
            return result
        hash_part = url.split("#")[1]
        hash_decoded = unquote(hash_part)
        try:
            decoded_bytes = base64.b64decode(hash_decoded)
            xored = "".join(chr(b ^ 5) for b in decoded_bytes)
            pk_match = re.search(r"pk_(live|test)_[A-Za-z0-9]+", xored)
            if pk_match:
                result["pk"] = pk_match.group(0)
            site_match = re.search(r"https?://[^\s\"'<>]+", xored)
            if site_match:
                result["site"] = site_match.group(0)
        except Exception:
            pass
    except Exception:
        pass
    return result

def _currency_sym(c: str) -> str:
    return {
        "USD": "$", "EUR": "€", "GBP": "£", "INR": "₹", "JPY": "¥",
        "CNY": "¥", "KRW": "₩", "CAD": "C$", "AUD": "A$", "BRL": "R$",
        "CHF": "CHF", "MXN": "MX$", "SGD": "S$", "HKD": "HK$", "TWD": "NT$",
    }.get(c, "")

async def get_checkout_info(url: str, proxy_url: str | None = None) -> dict:
    result = {
        "url": url,
        "pk": None,
        "cs": None,
        "merchant": None,
        "price": None,
        "currency": None,
        "product": None,
        "mode": None,
        "country": None,
        "customer_email": None,
        "support_email": None,
        "cards_accepted": None,
        "success_url": None,
        "init_data": None,
        "error": None,
    }
    try:
        decoded = decode_pk_from_url(url)
        result["pk"] = decoded.get("pk")
        result["cs"] = decoded.get("cs")
        if result["pk"] and result["cs"]:
            ua = random_user_agent()
            headers = build_stripe_headers(ua)
            locale = random_locale()
            tz = random_timezone()
            body = f"key={result['pk']}&eid=NA&browser_locale={locale}&browser_timezone={tz}&redirect_type=url"
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://api.stripe.com/v1/payment_pages/{result['cs']}/init",
                    headers=headers,
                    data=body,
                    proxy=proxy_url,
                ) as r:
                    init_data = await r.json()
                if "error" not in init_data:
                    result["init_data"] = init_data
                    acc = init_data.get("account_settings", {})
                    result["merchant"] = acc.get("display_name") or acc.get("business_name")
                    result["support_email"] = acc.get("support_email")
                    result["country"] = acc.get("country")

                    lig = init_data.get("line_item_group")
                    inv = init_data.get("invoice")
                    if lig:
                        result["price"] = lig.get("total", 0) / 100
                        result["currency"] = (lig.get("currency") or "").upper()
                        if lig.get("line_items"):
                            sym = _currency_sym(result["currency"])
                            parts = []
                            for item in lig["line_items"]:
                                qty = item.get("quantity", 1)
                                name = item.get("name", "Product")
                                amt = item.get("amount", 0) / 100
                                interval = item.get("recurring_interval")
                                if interval:
                                    parts.append(f"{qty}x {name} ({sym}{amt:.2f}/{interval})")
                                else:
                                    parts.append(f"{qty}x {name} ({sym}{amt:.2f})")
                            result["product"] = ", ".join(parts)
                    elif inv:
                        result["price"] = inv.get("total", 0) / 100
                        result["currency"] = (inv.get("currency") or "").upper()

                    mode = init_data.get("mode", "")
                    if mode:
                        result["mode"] = mode.upper()
                    elif init_data.get("subscription"):
                        result["mode"] = "SUBSCRIPTION"
                    else:
                        result["mode"] = "PAYMENT"

                    result["customer_email"] = init_data.get("customer_email")
                    pm_types = init_data.get("payment_method_types") or []
                    if pm_types:
                        result["cards_accepted"] = ", ".join(t.upper() for t in pm_types)
                    result["success_url"] = init_data.get("success_url")
                else:
                    result["error"] = init_data.get("error", {}).get("message", "Init failed")
        else:
            result["error"] = "Could not decode PK/CS from URL"
    except Exception as e:
        result["error"] = str(e)
    return result
