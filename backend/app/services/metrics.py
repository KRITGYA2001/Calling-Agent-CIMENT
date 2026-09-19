"""Efficiency / quality evidence, computed from real call records.

Manual-workflow baseline numbers are ASSUMPTIONS (the handout gives no measured baseline) — they
are exposed in the response so the console labels them and they can be replaced on the day.
"""

from app.services.call_state import CallState, store

BASELINE = {
    "manual_seconds_per_field": 25,  # find script section, ask, type, tab to next field
    "manual_call_overhead_seconds": 90,  # open lead, find last step, load journey iframe, wrap-up notes
    "manual_error_rate": 0.06,  # share of typed fields needing correction (assumed)
    "manual_fields_per_agent_hour": None,
}

TERMINAL = {"completed", "escalated", "declined", "callback", "ended", "blocked"}


def _duration(c: CallState) -> float | None:
    if c.ended_at:
        return max(0.0, c.ended_at - c.started_at)
    return None


def compute() -> dict:
    calls = [c for c in store.all() if c.lead_id or c.status != "in_progress"]
    real = [c for c in calls if c.status != "blocked"]
    total = len(real)
    completed = [c for c in real if c.outcome == "completed"]
    escalated = [c for c in real if c.escalation]
    declined = [c for c in real if c.outcome == "declined"]
    callbacks = [c for c in real if c.outcome == "callback_requested"]
    blocked = [c for c in calls if c.status == "blocked"]

    voice_fields = sum(1 for c in real for fid in c.fields if c.sources.get(fid) == "voice")
    val_errors = sum(c.validation_errors for c in real)

    completed_durations = [d for c in completed if (d := _duration(c))]
    all_durations = [d for c in real if (d := _duration(c))]

    per_field = BASELINE["manual_seconds_per_field"]
    overhead = BASELINE["manual_call_overhead_seconds"]
    # Human time a manual agent would have spent on the work the voice agent did on its own.
    manual_seconds_avoided = sum(
        (sum(1 for fid in c.fields if c.sources.get(fid) == "voice") * per_field + overhead)
        for c in real
        if c.outcome == "completed"
    )
    # Partial work on escalated calls still carries over (warm handoff => nothing re-typed).
    manual_seconds_avoided += sum(
        sum(1 for fid in c.fields if c.sources.get(fid) == "voice") * per_field for c in escalated if c.outcome != "completed"
    )

    by_category: dict[str, int] = {}
    for c in escalated:
        cat = (c.escalation or {}).get("category", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1

    handled_autonomously = len([c for c in completed if not c.escalation])

    return {
        "calls_total": total,
        "completed": len(completed),
        "escalated": len(escalated),
        "declined": len(declined),
        "callbacks": len(callbacks),
        "dnc_blocked": len(blocked),
        "completion_rate": round(len(completed) / total, 3) if total else None,
        "autonomous_completion_rate": round(handled_autonomously / total, 3) if total else None,
        "avg_call_seconds": round(sum(all_durations) / len(all_durations), 1) if all_durations else None,
        "avg_completed_call_seconds": round(sum(completed_durations) / len(completed_durations), 1)
        if completed_durations
        else None,
        "fields_captured_by_voice": voice_fields,
        "validation_errors_caught": val_errors,
        "human_minutes_avoided": round(manual_seconds_avoided / 60, 1),
        "escalations_by_category": by_category,
        "baseline_assumptions": BASELINE,
        "baseline_note": "Manual-workflow figures are assumptions, not measurements — replace with the on-site baseline.",
        "manual_estimate_seconds_per_journey": None
        if not completed
        else round(
            sum(len([1 for fid in c.fields if c.sources.get(fid) == "voice"]) for c in completed) / len(completed) * per_field
            + overhead
        ),
    }
