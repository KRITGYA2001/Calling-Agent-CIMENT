"""Do-Not-Call gate. Every outbound dial goes through `check()` first.

STUB: reads the register list from the database plus the numbers customers opt out on during calls. In production this
is the ACMA Do Not Call Register wash service (https://www.donotcall.gov.au) plus the internal
suppression list — swap `_registry_lookup` and nothing else changes.
"""

import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.services import db


def _norm(number: str) -> str:
    return re.sub(r"[^\d+]", "", number)


def _registry_lookup(number: str) -> bool:
    return _norm(number) in {_norm(n) for n in db.dnc_numbers("register")}


def suppress(number: str) -> None:
    db.add_dnc(_norm(number), "opt_out")


def is_suppressed(number: str) -> bool:
    return _norm(number) in {_norm(n) for n in db.dnc_numbers("opt_out")}


def calling_window_ok(tz: str = "Australia/Sydney") -> tuple[bool, str]:
    """ACMA telemarketing hours: Mon-Fri 9am-8pm, Sat 9am-5pm, no Sundays/public holidays."""
    try:
        now = datetime.now(ZoneInfo(tz))
    except Exception:  # tzdata missing (Windows) — fall back to AEST
        now = datetime.now(timezone(timedelta(hours=10)))
    wd, hr = now.weekday(), now.hour + now.minute / 60
    ok = (wd < 5 and 9 <= hr < 20) or (wd == 5 and 9 <= hr < 17)
    return ok, now.strftime("%a %H:%M ") + tz


def check(number: str) -> dict:
    """Returns {allowed, checks:[{name, passed, detail}]} — shown in the console before dialling."""
    settings = get_settings()
    checks = []

    on_register = _registry_lookup(number)
    checks.append({"name": "ACMA Do Not Call register", "passed": not on_register,
                   "detail": "number is on the register" if on_register else "not listed (stub lookup)"})

    opted_out = is_suppressed(number)
    checks.append({"name": "Internal opt-out list", "passed": not opted_out,
                   "detail": "customer opted out on a previous call" if opted_out else "no opt-out on file"})

    in_window, when = calling_window_ok()
    if settings.enforce_calling_hours:
        checks.append({"name": "Permitted calling hours", "passed": in_window, "detail": when})
    else:
        checks.append({"name": "Permitted calling hours", "passed": True,
                       "detail": f"{when} — {'inside window' if in_window else 'outside window, not enforced in demo'}"})

    return {"allowed": all(c["passed"] for c in checks), "checks": checks}
