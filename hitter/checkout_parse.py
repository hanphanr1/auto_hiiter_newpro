# -*- coding: utf-8 -*-
"""Decode Stripe checkout URL (PK/CS) and init. From autohitter co_functions."""
import re
import base64
from urllib.parse import unquote
import aiohttp

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

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

async def get_checkout_info(url: str) -> dict:
    result = {
        "url": url,
        "pk": None,
        "cs": None,
        "merchant": None,
        "price": None,
        "currency": None,
        "product": None,
        "init_data": None,
        "error": None,
    }
    try:
        decoded = decode_pk_from_url(url)
        result["pk"] = decoded.get("pk")
        result["cs"] = decoded.get("cs")
        if result["pk"] and result["cs"]:
            async with aiohttp.ClientSession() as session:
                body = f"key={result['pk']}&eid=NA&browser_locale=en-US&redirect_type=url"
                async with session.post(
                    f"https://api.stripe.com/v1/payment_pages/{result['cs']}/init",
                    headers=HEADERS,
                    data=body,
                ) as r:
                    init_data = await r.json()
                if "error" not in init_data:
                    result["init_data"] = init_data
                    acc = init_data.get("account_settings", {})
                    result["merchant"] = acc.get("display_name") or acc.get("business_name")
                    lig = init_data.get("line_item_group")
                    inv = init_data.get("invoice")
                    if lig:
                        result["price"] = lig.get("total", 0) / 100
                        result["currency"] = (lig.get("currency") or "").upper()
                        if lig.get("line_items"):
                            result["product"] = lig["line_items"][0].get("name", "")
                    elif inv:
                        result["price"] = inv.get("total", 0) / 100
                        result["currency"] = (inv.get("currency") or "").upper()
                else:
                    result["error"] = init_data.get("error", {}).get("message", "Init failed")
        else:
            result["error"] = "Could not decode PK/CS from URL"
    except Exception as e:
        result["error"] = str(e)
    return result
