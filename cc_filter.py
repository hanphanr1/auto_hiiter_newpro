# -*- coding: utf-8 -*-
"""Extract CC (card) lines from text or formatted messages like CHARGED/Approved."""
import re

# CC format: 15-19 digits, then separator, mm, yy, cvv (3-4 digits)
CC_PATTERN = re.compile(
    r'(?:CC\s*:\s*|Card\s*:\s*|💳\s*Card\s*:\s*)?'
    r'(\d{15,19})\s*[|:/\\\-\s]\s*(\d{1,2})\s*[|:/\\\-\s]\s*(\d{2,4})\s*[|:/\\\-\s]\s*(\d{3,4})',
    re.IGNORECASE
)

def _norm_month(mm: str) -> str:
    mm = mm.strip()
    if len(mm) == 1:
        mm = "0" + mm
    if len(mm) == 2 and mm.isdigit() and 1 <= int(mm) <= 12:
        return mm
    return ""

def _norm_year(yy: str) -> str:
    yy = yy.strip()
    if len(yy) == 4:
        yy = yy[2:]
    if len(yy) == 2 and yy.isdigit():
        return yy
    return ""

def _norm_cvv(cvv: str) -> str:
    cvv = re.sub(r'\D', '', cvv)
    if 3 <= len(cvv) <= 4:
        return cvv
    return ""

def extract_cc_lines(text: str) -> list[str]:
    """Extract all CC lines in format cc|mm|yy|cvv from text.
    Handles:
    - CC: 5218531108462848|07|2029|282
    - 💳 Card: 4266902072261538|03|26|885
    - Plain 4744784515914481|08|30|002
    """
    seen = set()
    result = []
    for m in CC_PATTERN.finditer(text):
        cc = m.group(1)
        mm = _norm_month(m.group(2))
        yy = _norm_year(m.group(3))
        cvv = _norm_cvv(m.group(4))
        if not mm or not yy or not cvv:
            continue
        if len(cc) < 15 or len(cc) > 19:
            continue
        line = f"{cc}|{mm}|{yy}|{cvv}"
        if line not in seen:
            seen.add(line)
            result.append(line)
    return result
