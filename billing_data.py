# -*- coding: utf-8 -*-
"""Random billing data generator. Combined from UsagiAutoX + TPropaganda extensions."""
import random

HUMAN_NAMES = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth",
    "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Daniel", "Matthew",
    "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua", "Kenneth",
    "Nancy", "Betty", "Margaret", "Sandra", "Ashley", "Dorothy", "Kimberly",
    "Emily", "Donna", "Michelle", "Alex", "Chris", "Jordan", "Taylor", "Morgan",
    "Casey", "Riley", "Quinn", "Avery", "Cameron",
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
    "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson",
    "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee",
    "Thompson", "White", "Harris", "Clark", "Lewis", "Robinson", "Walker",
]

STREETS = [
    "Main Street", "Oak Road", "Park Avenue", "Maple Drive", "Cedar Lane",
    "Pine Street", "Lake Drive", "Forest Avenue", "River Road", "Hill Street",
    "Elm Street", "Washington Blvd", "Lincoln Ave", "Highland Drive",
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
]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

TIMEZONES = [
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "America/Phoenix", "America/Anchorage", "Pacific/Honolulu",
]

LOCALES = ["en-US", "en-US", "en-US", "en-GB", "en-CA"]

# Country-based billing (from UsagiAutoX: Macau trick, autohitter: US default)
BILLING_COUNTRIES = [
    {"code": "US", "name": "United States", "zip": None},
    {"code": "MO", "name": "Macau", "zip": "999078"},
]


def random_name() -> str:
    return random.choice(HUMAN_NAMES)

def random_full_name() -> str:
    return f"{random.choice(HUMAN_NAMES)} {random.choice(LAST_NAMES)}"

def random_email() -> str:
    name = random.choice(HUMAN_NAMES).lower()
    num = random.randint(1, 9999)
    domain = random.choice(EMAIL_DOMAINS)
    return f"{name}{num}@{domain}"

def random_address() -> dict:
    city, state, base_zip = random.choice(CITIES)
    return {
        "name": random_full_name(),
        "line1": f"{random.randint(1, 999)} {random.choice(STREETS)}",
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

def build_stripe_headers(ua: str | None = None) -> dict:
    """Build realistic Stripe API headers like extensions do."""
    return {
        "authority": "api.stripe.com",
        "accept": "application/json",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://checkout.stripe.com",
        "referer": "https://checkout.stripe.com/",
        "user-agent": ua or random_user_agent(),
    }
