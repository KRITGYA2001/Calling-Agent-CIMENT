"""Synthetic Energy leads, stored in SQLite and loaded by scripts/seed_data.py (test data only) + the personalised per-lead call context."""

from app.journey.loader import get_journey
from app.journey.schema import JourneyDefinition
from app.services import db

AGENT_NAME = "Aarav"  # the human who takes over on a warm handoff


def list_leads() -> list[dict]:
    return db.list_leads()


def get_lead(lead_id: str) -> dict | None:
    return db.get_lead(lead_id)


_NOT_CARRIED = {"consent_recording", "confirm_details", "cooling_off_acknowledged"}


def effective_prefilled(lead: dict) -> dict[str, str]:
    """What is on file for this customer: the original journey data, overridden by anything saved in the database."""
    values = dict(lead.get("prefilled", {}))
    for fid, row in db.get_profile(lead["id"]).items():
        if fid not in _NOT_CARRIED and row["value"] is not None:
            values[fid] = row["value"]
    return values


def resume_section_id(lead: dict, journey: JourneyDefinition) -> str:
    """First section after the last one the customer completed."""
    ids = [s.id for s in journey.sections]
    last = lead.get("last_completed_step")
    if last in ids:
        idx = ids.index(last) + 1
        return ids[idx] if idx < len(ids) else ids[-1]
    return ids[0]


def opener(lead: dict, journey: JourneyDefinition) -> str:
    return journey.opener_template.format(
        first_name=lead["first_name"], dropout_when=lead.get("dropout_when", "recently")
    )


def call_variables(lead: dict) -> dict[str, str]:
    """Values substituted into the assistant prompt ({{lead_context}} etc.) for this call."""
    journey = get_journey()
    resume = resume_section_id(lead, journey)
    resume_title = next(s.title for s in journey.sections if s.id == resume)
    done = lead.get("last_completed_step")
    on_file = "\n".join(f"    - {k}: {v}" for k, v in effective_prefilled(lead).items()) or "    (nothing on file)"
    context = (
        f"Customer: {lead['full_name']} (call them {lead['first_name']}). Lead id {lead['id']}.\n"
        f"They dropped out {lead.get('dropout_when', 'recently')}; last completed step: "
        f"{done if done and done != 'none' else 'none (dropped at the very start)'}.\n"
        f"RESUME at section: {resume_title} ({resume}). Do NOT re-ask sections already completed.\n"
        f"Already on file from the journey (confirm briefly with the customer — 'I have your email as X, "
        f"still right?' — then record_field; do not interrogate):\n{on_file}\n"
        f"consent_recording is never on file: always get it live on this call first."
    )
    return {
        "lead_id": lead["id"],
        "first_name": lead["first_name"],
        "lead_context": context,
    }
