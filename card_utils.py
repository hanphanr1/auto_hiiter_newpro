# -*- coding: utf-8 -*-
"""Card parse, format, Luhn check."""
import re

CARD_PATTERN = re.compile(
    r'(\d{15,19})\s*[|:/\\\-\s]\s*(\d{1,2})\s*[|:/\\\-\s]\s*(\d{2,4})\s*[|:/\\\-\s]\s*(\d{3,4})'
)

def luhn_check_digit(partial: str) -> int:
    """Given digits without last digit, return check digit (0-9)."""
    def sum_digits(n):
        s = 0
        for i in range(len(n) - 1, -1, -1):
            d = int(n[i])
            if (len(n) - 1 - i) % 2 == 1:
                d *= 2
                if d > 9:
                    d -= 9
            s += d
        return s
    for i in range(10):
        if (sum_digits(partial + str(i)) % 10) == 0:
            return i
    return 0

def parse_card(line: str) -> dict | None:
    line = line.strip()
    if not line:
        return None
    m = CARD_PATTERN.search(line)
    if not m:
        return None
    cc, mm, yy, cvv = m.groups()
    mm = mm.zfill(2)
    if not (1 <= int(mm) <= 12):
        return None
    if len(yy) == 4:
        yy = yy[2:]
    if len(yy) != 2:
        return None
    cvv = re.sub(r'\D', '', cvv)
    if not (3 <= len(cvv) <= 4):
        return None
    return {"cc": cc, "mm": mm, "yy": yy, "cvv": cvv}

def parse_cards(text: str) -> list[dict]:
    cards = []
    for line in text.strip().split("\n"):
        c = parse_card(line)
        if c:
            cards.append(c)
    return cards

def format_card(card: dict) -> str:
    return f"{card['cc']}|{card['mm']}|{card['yy']}|{card['cvv']}"
