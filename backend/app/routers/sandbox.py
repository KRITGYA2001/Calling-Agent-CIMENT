"""Mock journey-completion sandbox. Same payload shape we POST to the real sandbox on the day.

`submit()` is called in-process by the voice agent's complete_journey when JOURNEY_SANDBOX_URL is
unset; it can also be hit over HTTP (POST /api/sandbox/journeys) exactly like the real one.
"""

import time
import uuid

from fastapi import APIRouter, HTTPException

from app.journey.loader import get_journey
from app.journey.schema import FieldType
from app.journey.validate import Invalid, normalise

router = APIRouter()
_submissions: list[dict] = []


def _typed(field_type: FieldType, value: str):
    if field_type == FieldType.boolean:
        return value == "true"
    if field_type == FieldType.number:
        n = float(value)
        return int(n) if n.is_integer() else n
    return value


def build_payload(call_id: str, lead_id: str | None, fields: dict[str, str], consent_ts: float | None) -> dict:
    journey = get_journey()
    sections: dict[str, dict] = {}
    for s in journey.sections:
        block = {f.id: _typed(f.type, fields[f.id]) for f in s.fields if f.id in fields}
        if block:
            sections[s.id] = block
    return {
        "vertical": journey.vertical,
        "channel": "voice_agent",
        "lead_id": lead_id,
        "call_id": call_id,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "consent": {"recorded_line": fields.get("consent_recording") == "true", "captured_at": consent_ts},
        "sections": sections,
    }


def validate_payload(payload: dict) -> list[str]:
    journey = get_journey()
    errors: list[str] = []
    flat = {fid: v for block in payload.get("sections", {}).values() for fid, v in block.items()}
    for f in journey.all_fields():
        if f.id not in flat:
            if f.required:
                errors.append(f"missing required field {f.id}")
            continue
        raw = str(flat[f.id]).lower() if f.type == FieldType.boolean else str(flat[f.id])
        try:
            normalise(f, raw)
        except Invalid as exc:
            errors.append(f"{f.id}: {exc}")
    if not payload.get("consent", {}).get("recorded_line"):
        errors.append("recording consent not captured")
    return errors


def submit(payload: dict) -> dict:
    errors = validate_payload(payload)
    if errors:
        return {"status": "rejected", "errors": errors}
    receipt = {"status": "accepted", "reference": f"ECX-{uuid.uuid4().hex[:8].upper()}", "payload": payload}
    _submissions.append(receipt)
    return receipt


@router.post("/journeys")
def post_journey(payload: dict) -> dict:
    receipt = submit(payload)
    if receipt["status"] == "rejected":
        raise HTTPException(422, receipt)
    return receipt


@router.get("/journeys")
def list_journeys() -> list[dict]:
    return list(reversed(_submissions))
