"""Load the dummy demo data (leads + Do Not Call register) into the SQLite database.

Edit the LEADS / DNC_REGISTER lists below, then run:
    python scripts/seed_data.py

Safe to re-run: leads are replaced by id. To start from a blank slate first, run clear_data.py.
Leads are read live by the backend, so no restart is needed after seeding.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import db  # noqa: E402

# Sections in order: identity_consent -> property_supply -> plan_selection -> payment_confirmation
# last_step = the last section the customer COMPLETED before dropping out ("none" = dropped at the very start).


def lead(id, name, phone, dropout_when, last_step, note="", dob="1990-01-01", email=None, **already_on_file):
    """Builds a lead. Identity details are pre-filled for anyone who got past the first step;
    pass extra fields as keyword args, e.g. service_address="1 Test St", current_retailer="AGL"."""
    first = name.split()[0]
    prefilled = {}
    if last_step != "none":
        prefilled = {"full_name": name, "date_of_birth": dob, "contact_phone": phone,
                     "contact_email": email or f"{first.lower()}.test@example.com"}
    prefilled.update({k: str(v) for k, v in already_on_file.items()})
    return {"id": id, "first_name": first, "full_name": name, "phone": phone, "dropout_when": dropout_when,
            "last_completed_step": last_step, "note": note, "prefilled": prefilled}


LEADS = [
    lead("L-1001", "Kritgya Kumar", "+916397103051", "yesterday", "identity_consent",
         note="Test contact (presenter phone; handoff goes to the other test phone).", dob="1991-04-12", email="kritgya.test@example.com",
         move_in_date="2026-10-01", nmi_or_mirn="4102345678"),  # optional fields pre-filled so the demo is 4 short questions
    lead("L-1002", "Daniel Okafor", "+61491570006", "a couple of days ago", "property_supply",
         note="ACMA-reserved fictional number.", dob="1985-11-03",
         service_address="12 Test Street, Richmond VIC 3121", current_retailer="Origin Energy",
         life_support_flag="false", concession_card_flag="false"),
    lead("L-1003", "Mei Tan", "+61491570157", "yesterday", "plan_selection",
         note="ACMA-reserved fictional number.", dob="1993-07-22",
         service_address="48 Example Road, Parramatta NSW 2150", life_support_flag="false",
         concession_card_flag="true", selected_retailer="AGL", selected_plan_name="Value Saver"),
    lead("L-1004", "Tom Nguyen", "+61491570158", "last week", "identity_consent",
         note="On the Do Not Call register: dialling must be blocked.", dob="1979-01-30"),
    lead("L-1005", "Sarah Collins", "+61491570159", "this morning", "none", note="Dropped at the very first step."),
    lead("L-1006", "Rahul Mehta", "+61491570110", "two days ago", "identity_consent",
         note="ACMA-reserved fictional number.", dob="1988-09-09"),
]

# Numbers on the (stub) ACMA Do Not Call register. Dialling these is blocked before the call is placed.
DNC_REGISTER = ["+61491570158"]


def main() -> None:
    for pos, l in enumerate(LEADS):
        db.replace_lead(l, pos)
    for n in DNC_REGISTER:
        db.add_dnc(n, "register")
    print(f"Seeded {len(LEADS)} leads and {len(DNC_REGISTER)} Do Not Call number(s).")


if __name__ == "__main__":
    main()
