"""Server-side safety net: scans what the *customer* says and flags escalation / guardrail signals.

The model is instructed to handle these itself via tools; this independently detects them so the
console can show them live and so a missed escalation still gets caught.
"""

import re

# (signal, regex, auto_escalate_category or None)
_RULES: list[tuple[str, re.Pattern[str], str | None]] = [
    ("human_request", re.compile(r"\b(speak|talk|put me)\b.{0,25}\b(human|person|someone|somebody|manager|agent|supervisor|real)\b|\breal person\b|\bget me a (human|person|manager)\b", re.I), "explicit_human_request"),
    ("anger", re.compile(r"\b(fuck\w*|shit|bullshit|bloody hell|damn it|pissed|idiot|useless|ridiculous|unacceptable|fed up|sick of|waste of (my )?time|this is a joke|how many times)\b", re.I), "anger"),
    ("opt_out", re.compile(r"\b(not interested|stop calling|don'?t (call|ring|contact)|do not (call|contact)|remove me|take me off|unsubscribe|leave me alone)\b", re.I), None),
    ("busy", re.compile(r"\b(i'?m busy|bad time|not a good time|call (me )?(back )?later|in a meeting|i'?m driving|can'?t talk)\b", re.I), None),
    ("sensitive", re.compile(r"\b(hardship|can'?t (afford|pay)|behind on (my )?bill|dispute|complain\w*|ombudsman|disconnect(ed|ion)|passed away|died|scam|lawyer|legal action|cvv|card number|credit card|debit card|bank account)\b", re.I), "sensitive_topic"),
    ("advice", re.compile(r"\b(which (plan|one|retailer) (is|would be|should)|what (do|would) you (recommend|suggest)|should i (switch|sign|take|go)|is it worth|what'?s (the )?best)\b", re.I), None),
]

_WORDS = {"zero": "0", "oh": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}
_TOKEN = r"(?:\d|" + "|".join(_WORDS) + r")"
# 13-19 digits, spoken as numerals ("4242 4242...") or as words ("four two four two ...")
_DIGIT_RUN = re.compile(r"(?<![\w])" + _TOKEN + r"(?:[ ,.-]{0,2}" + _TOKEN + r"){12,18}(?![\w])", re.I)


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def _digits_of(run: str) -> str:
    return "".join(_WORDS.get(t.lower(), t) for t in re.findall(_TOKEN, run, re.I))


def has_card_number(text: str) -> bool:
    for m in _DIGIT_RUN.finditer(text):
        digits = _digits_of(m.group())
        if 13 <= len(digits) <= 19 and _luhn(digits):
            return True
    return False


def redact_card(text: str) -> str:
    return _DIGIT_RUN.sub("[card number redacted]", text)


def detect(text: str) -> list[tuple[str, str | None]]:
    """Return [(signal, auto_escalate_category)] found in one customer utterance."""
    found: list[tuple[str, str | None]] = []
    if has_card_number(text):
        found.append(("card_data", "sensitive_topic"))
    for name, rx, category in _RULES:
        if rx.search(text):
            found.append((name, category))
    return found
