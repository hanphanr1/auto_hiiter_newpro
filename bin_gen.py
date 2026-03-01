# -*- coding: utf-8 -*-
"""Generate valid card numbers from BIN (Luhn). Like UsagiAutoX / TPropaganda."""
import random
import re
from card_utils import luhn_check_digit

def _is_amex(bin_str: str) -> bool:
    clean = re.sub(r'[^0-9]', '', bin_str)
    if len(clean) < 2:
        return False
    return clean[:2] in ("34", "37")

def _random_month() -> str:
    return str(random.randint(1, 12)).zfill(2)

def _random_year() -> str:
    return str(random.randint(24, 33))  # 2024-2033

def _random_cvv(amex: bool) -> str:
    length = 4 if amex else 3
    return "".join(str(random.randint(0, 9)) for _ in range(length))

def generate_card_from_bin(
    bin_input: str,
    month: str | None = None,
    year: str | None = None,
    cvv: str | None = None,
) -> dict:
    """
    bin_input: e.g. "521853" or "521853xx" (x = random digit).
    Returns {"cc", "mm", "yy", "cvv"} and formatted line cc|mm|yy|cvv.
    """
    bin_clean = re.sub(r'[^0-9xX]', '', bin_input)
    card_prefix = ""
    for c in bin_clean:
        if c in "xX":
            card_prefix += str(random.randint(0, 9))
        else:
            card_prefix += c

    amex = _is_amex(card_prefix)
    target_len = 15 if amex else 16
    need = target_len - len(card_prefix) - 1  # -1 for Luhn digit
    if need < 0:
        card_prefix = card_prefix[:target_len - 1]
        need = 0
    for _ in range(need):
        card_prefix += str(random.randint(0, 9))

    check = luhn_check_digit(card_prefix)
    cc = card_prefix + str(check)

    mm = month if month and len(month) == 2 and month.isdigit() and 1 <= int(month) <= 12 else _random_month()
    yy = year
    if yy:
        if len(yy) == 4:
            yy = yy[2:]
        if len(yy) != 2 or not yy.isdigit():
            yy = _random_year()
    else:
        yy = _random_year()
    cvv_val = cvv
    if not cvv_val or len(cvv_val) < 3:
        cvv_val = _random_cvv(amex)
    else:
        cvv_val = re.sub(r'\D', '', cvv_val)[:4] if amex else re.sub(r'\D', '', cvv_val)[:3]

    return {
        "cc": cc,
        "mm": mm,
        "yy": yy,
        "cvv": cvv_val,
        "line": f"{cc}|{mm}|{yy}|{cvv_val}",
    }

def generate_cards_from_bin(bin_input: str, count: int = 1, **kwargs) -> list[dict]:
    return [generate_card_from_bin(bin_input, **kwargs) for _ in range(count)]
