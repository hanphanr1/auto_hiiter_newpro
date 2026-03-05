# -*- coding: utf-8 -*-
"""Random billing data generator.
Enhanced with fingerprint techniques from DeepBypasser + Dot Bypasser.
"""
import random
import json as _json

HUMAN_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
    "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
    "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly",
    "Emily", "Donna", "Michelle", "Alex", "Chris", "Jordan", "Taylor", "Morgan",
    "Casey", "Riley", "Quinn", "Avery", "Cameron", "Ethan", "Noah", "Liam",
    "Mason", "Logan", "Lucas", "Oliver", "Aiden", "Elijah", "Benjamin",
    "Sophia", "Olivia", "Emma", "Ava", "Isabella", "Mia", "Charlotte", "Harper",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson",
    "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
    "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson", "Walker",
    "Hall", "Allen", "Young", "King", "Wright", "Scott", "Green", "Baker",
    "Adams", "Nelson", "Hill", "Ramirez", "Campbell", "Mitchell", "Roberts",
]

STREETS = [
    "Main Street", "Oak Road", "Park Avenue", "Maple Drive", "Cedar Lane",
    "Pine Street", "Lake Drive", "Forest Avenue", "River Road", "Hill Street",
    "Elm Street", "Washington Blvd", "Lincoln Ave", "Highland Drive",
    "Sunset Blvd", "Broadway", "Market Street", "Church Road", "Spring Lane",
    "Valley Drive", "Meadow Lane", "Ridge Road", "Harbor View",
]

CITIES = [
    ("New York", "NY", "10001"),
    ("Los Angeles", "CA", "90001"),
    ("Chicago", "IL", "60601"),
    ("Houston", "TX", "77001"),
    ("Phoenix", "AZ", "85001"),
    ("Philadelphia", "PA", "19101"),
    ("San Antonio", "TX", "78201"),
    ("San Diego", "CA", "92101"),
    ("Dallas", "TX", "75201"),
    ("Pinetop", "AZ", "85929"),
    ("Denver", "CO", "80201"),
    ("Seattle", "WA", "98101"),
    ("Portland", "OR", "97201"),
    ("Miami", "FL", "33101"),
    ("Atlanta", "GA", "30301"),
    ("Boston", "MA", "02101"),
    ("Nashville", "TN", "37201"),
    ("Las Vegas", "NV", "89101"),
    ("Austin", "TX", "73301"),
    ("Columbus", "OH", "43004"),
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com",
                 "protonmail.com", "aol.com", "live.com"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Anchorage", "Pacific/Honolulu",
    "Europe/London", "Europe/Berlin", "Europe/Paris",
]

LOCALES = ["en-US", "en-US", "en-US", "en-GB", "en-CA", "en-AU"]

BILLING_COUNTRIES = [
    {"code": "US", "name": "United States", "zip": None},
    {"code": "MO", "name": "Macau", "zip": "999078"},
]

CHROME_VERSIONS = [
    ("120", "120.0.0.0"),
    ("121", "121.0.0.0"),
    ("122", "122.0.0.0"),
    ("123", "123.0.0.0"),
    ("124", "124.0.0.0"),
]

STRIPE_JS_VERSIONS = [
    "stripe.js/v3",
    "stripe.js/v3",
    "stripe.js/67cf46a31c",
    "stripe.js/5bbff3ff47",
]

OS_CONFIGS = [
    {"name": "Windows", "version": "10"},
    {"name": "Windows", "version": "11"},
    {"name": "Mac OS", "version": "10.15.7"},
    {"name": "Linux", "version": ""},
]


def random_name() -> str:
    return random.choice(HUMAN_NAMES)

def random_full_name() -> str:
    return f"{random.choice(HUMAN_NAMES)} {random.choice(LAST_NAMES)}"

def random_email() -> str:
    first = random.choice(HUMAN_NAMES).lower()
    last = random.choice(LAST_NAMES).lower()
    num = random.randint(1, 9999)
    domain = random.choice(EMAIL_DOMAINS)
    fmt = random.choice([
        f"{first}{num}@{domain}",
        f"{first}.{last}{num}@{domain}",
        f"{first}{last}{num}@{domain}",
        f"{first[0]}{last}{num}@{domain}",
    ])
    return fmt

def random_address() -> dict:
    city, state, base_zip = random.choice(CITIES)
    return {
        "name": random_full_name(),
        "line1": f"{random.randint(1, 9999)} {random.choice(STREETS)}",
        "city": city,
        "state": state,
        "postal_code": base_zip,
        "country": "US",
    }

def random_billing_for_country(country_code: str = "US") -> dict:
    addr = random_address()
    if country_code == "MO":
        addr["country"] = "MO"
        addr["city"] = "Macau"
        addr["state"] = ""
        addr["postal_code"] = "999078"
    return addr

def random_user_agent() -> str:
    return random.choice(USER_AGENTS)

def random_timezone() -> str:
    return random.choice(TIMEZONES)

def random_locale() -> str:
    return random.choice(LOCALES)

def random_phone() -> str:
    return f"+1{random.randint(200,999)}{random.randint(2000000,9999999)}"


def _stripe_client_ua(ua: str) -> str:
    """Generate Stripe-Client-User-Agent matching the given UA string.
    Mimics the fingerprint that Stripe.js sends, inspired by DeepBypasser's
    fingerprint spoofing and Dot Bypasser's approach."""
    chrome_ver = random.choice(CHROME_VERSIONS)
    os_conf = random.choice(OS_CONFIGS)
    stripe_js = random.choice(STRIPE_JS_VERSIONS)

    if "Chrome/" in ua:
        import re
        m = re.search(r"Chrome/(\d+\.\d+\.\d+\.\d+)", ua)
        if m:
            chrome_ver = (m.group(1).split(".")[0], m.group(1))
    if "Windows" in ua:
        os_conf = {"name": "Windows", "version": "10"}
    elif "Mac OS" in ua or "Macintosh" in ua:
        os_conf = {"name": "Mac OS", "version": "10.15.7"}
    elif "Linux" in ua:
        os_conf = {"name": "Linux", "version": ""}

    browser_info = {"name": "Chrome", "version": chrome_ver[1]}
    if "Firefox" in ua:
        import re
        m = re.search(r"Firefox/(\d+\.\d+)", ua)
        browser_info = {"name": "Firefox", "version": m.group(1) if m else "125.0"}
    elif "Safari" in ua and "Chrome" not in ua:
        import re
        m = re.search(r"Version/(\d+\.\d+)", ua)
        browser_info = {"name": "Safari", "version": m.group(1) if m else "17.4"}

    return _json.dumps({
        "os": os_conf,
        "browser": browser_info,
        "device": {"name": "Desktop"},
        "bindings_version": stripe_js,
        "lang": "js",
        "lang_version": "",
        "platform": "browser",
        "analytics_method": stripe_js.replace("stripe.js/", "stripe-js/"),
        "user_agent": ua,
    }, separators=(",", ":"))


def build_stripe_headers(ua: str | None = None, origin: str = "https://checkout.stripe.com") -> dict:
    agent = ua or random_user_agent()
    return {
        "authority": "api.stripe.com",
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": origin,
        "referer": f"{origin}/",
        "user-agent": agent,
        "stripe-client-user-agent": _stripe_client_ua(agent),
        "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }


def build_stripe_headers_js(ua: str | None = None) -> dict:
    return build_stripe_headers(ua, origin="https://js.stripe.com")
