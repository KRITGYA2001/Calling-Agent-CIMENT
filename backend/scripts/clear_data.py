"""Delete the demo data from the SQLite database.

    python scripts/clear_data.py            # everything: leads, DNC list, calls, saved customer answers
    python scripts/clear_data.py --calls    # only call history + saved answers (keeps leads and DNC list)

Then run seed_data.py to load fresh data. The running backend keeps calls in memory, so restart it
after clearing (scripts/demo_reset.sh does clear + seed + restart in one go on the VM).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import db  # noqa: E402

CALL_TABLES = ("calls", "lead_profile", "profile_history")
ALL_TABLES = CALL_TABLES + ("leads", "dnc_list")


def main() -> None:
    tables = CALL_TABLES if "--calls" in sys.argv else ALL_TABLES
    counts = db.clear(*tables)
    print("Deleted: " + ", ".join(f"{n} {t}" for t, n in counts.items()))
    print("Restart the backend so it drops calls held in memory.")


if __name__ == "__main__":
    main()
