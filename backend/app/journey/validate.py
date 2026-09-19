"""Server-side validation + normalisation of captured values.

The LLM proposes a value; this decides whether it is a valid payload value. A rejected value
is bounced back to the model with a re-ask hint, and counted toward the "same field failed
2-3 times -> escalate as confusion" rule.
"""

import re
from datetime import date, datetime

from app.journey.schema import FieldType, JourneyField

_YES = {"yes", "y", "yeah", "yep", "true", "sure", "correct", "ok", "okay", "i do", "i agree"}
_NO = {"no", "n", "nope", "false", "nah", "none"}
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%B %d, %Y", "%d.%m.%Y")


class Invalid(Exception):
    pass


def _to_date(raw: str) -> date:
    cleaned = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", raw.strip(), flags=re.I)
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    raise Invalid("not a recognisable date — ask for day, month and year")


def normalise(f: JourneyField, raw: str) -> str:
    """Return the canonical value for the payload, or raise Invalid with a reason."""
    raw = (raw or "").strip()
    if not raw:
        raise Invalid("empty value")

    if f.type == FieldType.boolean:
        low = raw.lower().strip(" .!")
        if low in _YES:
            return "true"
        if low in _NO:
            return "false"
        raise Invalid("expected a clear yes or no")

    if f.type == FieldType.enum:
        low = raw.lower().replace(" ", "_").replace("-", "_")
        for opt in f.options or []:
            if low == opt or low.replace("_", "") == opt.replace("_", ""):
                return opt
        raise Invalid(f"must be one of: {', '.join(f.options or [])}")

    if f.type == FieldType.date:
        d = _to_date(raw)
        if f.validation == "dob":
            today = date.today()
            age = today.year - d.year - ((today.month, today.day) < (d.month, d.day))
            if d > today or age > 120:
                raise Invalid("date of birth is not plausible")
            if age < 18:
                raise Invalid("customer must be 18 or over — escalate rather than continue")
        return d.isoformat()

    if f.type == FieldType.number:
        try:
            n = float(raw.replace(",", ""))
        except ValueError:
            raise Invalid("expected a number") from None
        if n <= 0:
            raise Invalid("must be greater than zero")
        return str(int(n)) if n.is_integer() else str(n)

    # text
    if f.validation == "email":
        email = raw.lower().replace(" at ", "@").replace(" dot ", ".").replace(" ", "")
        if not re.fullmatch(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", email):
            raise Invalid("not a valid email address — ask them to spell it")
        return email
    if f.validation == "phone":
        digits = re.sub(r"[\s\-()]", "", raw)
        if not re.fullmatch(r"\+?\d{8,15}", digits):
            raise Invalid("phone number needs 8-15 digits — ask again digit by digit")
        return digits
    if f.validation == "nmi":
        nmi = re.sub(r"[\s\-]", "", raw).upper()
        if not re.fullmatch(r"[A-Z0-9]{10,11}", nmi):
            raise Invalid("NMI is 10-11 letters/digits — ask again a few characters at a time")
        return nmi
    if len(raw) < 2:
        raise Invalid("too short")
    return raw
