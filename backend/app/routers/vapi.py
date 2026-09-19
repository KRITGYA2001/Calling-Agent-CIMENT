import asyncio
import json
import time
import uuid

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.journey import signals
from app.journey.loader import get_journey
from app.journey.prompt import build_assistant_payload
from app.journey.validate import Invalid, normalise
from app.routers import sandbox
from app.services import db, dnc, leads, metrics
from app.services.call_state import CallState, store

router = APIRouter()

MAX_FAILS = 3
_control_urls: dict[str, str] = {}  # call_id -> Vapi live-control URL (server-side only)
_TERMINAL = {"completed", "escalated", "declined", "callback", "ended", "blocked"}


# ---------------------------------------------------------------------------
# Assistant config
# ---------------------------------------------------------------------------


@router.get("/assistant-config")
def assistant_config(public_base_url: str) -> dict:
    return build_assistant_payload(public_base_url)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attach_lead(state: CallState, lead_id: str | None) -> None:
    if not lead_id or state.lead_id == lead_id:
        return
    lead = leads.get_lead(lead_id)
    if not lead:
        return
    journey = get_journey()
    state.lead_id = lead["id"]
    state.lead_name = lead["full_name"]
    state.resume_section = leads.resume_section_id(lead, journey)
    for fid, val in leads.effective_prefilled(lead).items():
        state.fields.setdefault(fid, val)
        state.sources.setdefault(fid, "prefilled")
        db.seed_field(lead["id"], fid, val)
    state.event("lead", f"Lead {lead['id']} ({lead['full_name']}) — last completed step: {lead['last_completed_step']}, resuming at {state.resume_section}")


def _lead_id_from_message(message: dict) -> str | None:
    call = message.get("call") or {}
    vv = (call.get("assistantOverrides") or {}).get("variableValues") or {}
    return vv.get("lead_id") or (call.get("metadata") or {}).get("lead_id")


def _digits(s: str) -> str:
    return "".join(ch for ch in s if ch.isdigit())


def _phone_of(state: CallState) -> str | None:
    lead = leads.get_lead(state.lead_id) if state.lead_id else None
    return lead["phone"] if lead else None


def _next_field(state: CallState) -> str:
    """Server-driven 'what to ask next', walking sections from the resume point."""
    journey = get_journey()
    if state.consent is not True:
        f = journey.field("consent_recording")
        return f"Next: consent_recording — ask: \"{f.script}\"" if f else ""
    ids = [s.id for s in journey.sections]
    start = ids.index(state.resume_section) if state.resume_section in ids else 0
    ordered = journey.sections[start:] + journey.sections[:start]
    pending_optional = None
    for s in ordered:
        for f in s.fields:
            if f.id == "confirm_details" or state.sources.get(f.id) == "voice":
                continue
            if f.required:
                on_file = state.fields.get(f.id)
                tail = f" (on file: {on_file} — confirm it)" if on_file and not f.sensitive else ""
                return f"Next: {f.id}{tail} — ask: \"{f.script}\""
            pending_optional = pending_optional or f
    if pending_optional:
        return f"Next (optional, skip if unknown): {pending_optional.id} — ask: \"{pending_optional.script}\""
    return "All fields captured. Read every detail back, get an explicit yes, record confirm_details=true, then call complete_journey."


def _escalate(state: CallState, category: str, reason: str, summary: str, auto: bool = False) -> str:
    settings = get_settings()
    journey = get_journey()
    if state.escalation is None:
        state.status = "escalated"
        state.outcome = "escalated"
        state.escalation = {
            "category": category,
            "reason": reason,
            "summary_for_human": summary,
            "ts": time.time(),
            "auto": auto,
        }
        state.event("escalation", f"Escalated ({category.replace('_', ' ')}){' — detected by safety net' if auto else ''}: {reason}")
    script = journey.escalation_scripts.get(category, journey.escalation_scripts["low_confidence"])
    if category == "sensitive_topic" and (auto or "card" in reason.lower() or "payment" in reason.lower()):
        script = journey.payment_boundary_script
    if settings.human_handoff_number:
        how = "Then IMMEDIATELY call the transferCall tool to connect the customer to the human."
    else:
        how = ("Then tell them a colleague will phone them back shortly with everything so far, "
               "say goodbye and call endCall. Do not ask any more questions.")
    return f'Escalation logged. Say: "{script}" {how}'


def _payload_ok(state: CallState) -> list[str]:
    journey = get_journey()
    missing = [fid for fid in journey.required_field_ids() if state.sources.get(fid) != "voice"]
    return sorted(missing)


async def _submit(state: CallState) -> dict:
    settings = get_settings()
    payload = sandbox.build_payload(state.call_id, state.lead_id, state.fields, None)
    if settings.journey_sandbox_url:
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.post(settings.journey_sandbox_url, json=payload)
            return {"status": "accepted" if resp.is_success else "rejected", "http_status": resp.status_code,
                    "reference": (resp.json() or {}).get("reference") if resp.is_success else None,
                    "payload": payload, "errors": [] if resp.is_success else [resp.text[:300]]}
        except (httpx.HTTPError, ValueError) as exc:
            return {"status": "rejected", "errors": [f"sandbox unreachable: {exc}"], "payload": payload}
    return sandbox.submit(payload)


# ---------------------------------------------------------------------------
# Tool calls
# ---------------------------------------------------------------------------


async def _handle_tool_calls(message: dict) -> dict:
    call_id = (message.get("call") or {}).get("id", "unknown")
    state = store.get_or_create(call_id)
    _attach_lead(state, _lead_id_from_message(message))
    journey = get_journey()
    results = []

    for tc in message.get("toolCallList", []):
        fn = tc.get("function") or {}  # Vapi sends {"function": {"name", "arguments"}}; older shape is flat
        name = tc.get("name") or fn.get("name")
        args = tc.get("arguments") or tc.get("parameters") or fn.get("arguments") or fn.get("parameters") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        result = "ok"

        if name == "record_field":
            result = await _record_field(state, journey, args)

        elif name == "flag_capture_problem":
            fid = args.get("field_id", "")
            state.failures[fid] = state.failures.get(fid, 0) + 1
            state.event("capture_fail", f"Could not capture {fid} (attempt {state.failures[fid]}): {args.get('reason', '')}")
            if state.failures[fid] >= MAX_FAILS:
                result = _escalate(state, "confusion", f"Failed to capture {fid} {MAX_FAILS} times",
                                   f"Could not capture {fid} after {MAX_FAILS} attempts. {_summary(state)}")
            elif state.failures[fid] == 2:
                result = "Noted. Try a different way: ask them to spell it or say it one character at a time. One more failure means escalate."
            else:
                f = journey.field(fid)
                result = f'Noted. Re-ask: "{f.reprompt}"' if f else "Noted. Re-ask differently."

        elif name == "log_outcome":
            outcome = args.get("outcome", "declined")
            state.outcome = "callback" if outcome == "callback_requested" else outcome
            if outcome == "callback_requested":
                state.status = "callback"
                state.callback_time = args.get("callback_time")
                state.event("outcome", f"Callback requested: {args.get('callback_time', 'time not given')}")
                result = "Callback logged. Confirm the time back to them, thank them, then endCall."
            else:
                state.status = "declined"
                phone = _phone_of(state)
                if phone:
                    dnc.suppress(phone)
                state.event("outcome", f"Customer {outcome.replace('_', ' ')} — logged, added to suppression list, no further calls")
                result = "Logged and suppressed. Thank them politely and endCall. Do not persuade."

        elif name == "escalate_to_human":
            result = _escalate(state, args.get("category", "low_confidence"), args.get("reason", ""),
                               args.get("summary_for_human") or _summary(state))

        elif name == "complete_journey":
            result = await _complete(state, bool(args.get("confirmed")))

        if name not in ("record_field", "flag_capture_problem", "log_outcome", "escalate_to_human", "complete_journey"):
            state.event("error", f"Unknown tool call ignored: {name!r}")
        results.append({"toolCallId": tc.get("id"), "name": name, "result": result})

    await store.publish(call_id)
    return {"results": results}


async def _record_field(state: CallState, journey, args: dict) -> str:
    fid = args.get("field_id", "")
    value = str(args.get("value", ""))
    f = journey.field(fid)
    if f is None:
        return f"Error: unknown field '{fid}'. Use the exact id from the journey definition."

    if signals.has_card_number(value):
        state.event("guardrail", "Card number spoken — value discarded, not stored")
        return _escalate(state, "sensitive_topic", "Customer read out card details", _summary(state), auto=True)

    if fid != "consent_recording" and state.consent is not True:
        return "Error: consent not captured yet. Ask for consent to continue on a recorded line before anything else."

    if f.locked and state.lead_id:
        on_file = (state.fields.get(fid) or "")
        if _digits(value)[-10:] != _digits(on_file)[-10:]:
            state.event("guardrail", f"Blocked attempt to change {f.label} by voice (kept the number on file)")
            state.signals.append({"type": "change_blocked", "text": f"Asked to change {fid}", "ts": time.time()})
            return (f"Refused: the {f.label.lower()} is the number we use to reach this customer and cannot be changed on a call. "
                    "Do not store it. Tell them kindly that for their security it can only be updated through a verified request, "
                    "not by phone, and that you'll keep using the number on file. If they insist, escalate_to_human(off_script). "
                    f"Otherwise carry on. {_next_field(state)}")

    try:
        clean = normalise(f, value)
    except Invalid as exc:
        state.failures[fid] = state.failures.get(fid, 0) + 1
        state.validation_errors += 1
        state.event("validation", f"Rejected {fid}: {exc} (attempt {state.failures[fid]})")
        if state.failures[fid] >= MAX_FAILS:
            return _escalate(state, "confusion", f"{f.label} failed validation {MAX_FAILS} times",
                             f"Could not capture a valid {f.label}. {_summary(state)}")
        return f"Error: {exc}. Re-ask: \"{f.reprompt}\""

    if args.get("confidence") == "low" and not f.sensitive and state.failures.get(fid, 0) < 1:
        state.failures[fid] = state.failures.get(fid, 0) + 1
        state.event("low_confidence", f"Low confidence on {fid} — asked to re-confirm")
        return f"Stored tentatively but re-confirm it: read '{clean}' back to the customer and ask if it is right; then record_field again with confidence high."

    state.fields[fid] = clean
    state.sources[fid] = "voice"
    state.failures.pop(fid, None)
    shown = "••••" if f.sensitive else clean
    saved = ""
    if state.lead_id:
        try:
            db.upsert_field(state.lead_id, fid, clean, "voice", state.call_id)
            saved = " (saved to database)"
        except Exception:  # noqa: BLE001 - never break a live call over storage
            pass
    state.event("field", f"Captured {f.label}: {shown}{saved}")

    if fid == "consent_recording":
        state.consent = clean == "true"
        if state.consent:
            state.event("consent", "Customer consented to continue on a recorded line")
        else:
            state.status = "declined"
            state.outcome = "declined"
            phone = _phone_of(state)
            if phone:
                dnc.suppress(phone)
            state.event("outcome", "Consent refused — call ends, nothing collected")
            return f'No consent. Say: "{_say(journey.decline_script, state)}" then call endCall.'

    if fid == "life_support_flag" and clean == "true":
        state.event("guardrail", "Life-support customer — regulated, needs a person")
        return _escalate(state, "sensitive_topic", "Life support equipment at the property",
                         f"Customer reports life-support equipment. {_summary(state)}")

    return f"Recorded. {_next_field(state)}"


async def _complete(state: CallState, confirmed: bool) -> str:
    if not confirmed:
        return "Not confirmed. Keep going and read the details back again."
    if state.fields.get("confirm_details") != "true":
        return "Error: record_field confirm_details=true first (after the customer's explicit yes to the read-back)."
    missing = _payload_ok(state)
    if missing:
        return f"Cannot submit yet — still to capture or confirm on this call: {', '.join(missing)}. {_next_field(state)}"
    receipt = await _submit(state)
    state.submission = {k: v for k, v in receipt.items()}
    if receipt.get("status") == "accepted":
        state.status = "completed"
        state.outcome = "completed"
        state.event("submit", f"Journey submitted to sandbox — reference {receipt.get('reference')}")
        return f'Journey submitted (ref {receipt.get("reference")}). Say: "{_say(get_journey().close_script, state)}" then call endCall.'
    state.event("submit", f"Sandbox rejected submission: {receipt.get('errors')}")
    return f"Submission rejected: {receipt.get('errors')}. Fix the listed items with the customer."


def _say(script: str, state: CallState) -> str:
    lead = leads.get_lead(state.lead_id) if state.lead_id else None
    return script.replace("{first_name}", lead["first_name"] if lead else "there")


def _summary(state: CallState) -> str:
    voice = [f"{k}={v}" for k, v in state.fields.items() if state.sources.get(k) == "voice" and k != "payment_method"]
    return f"Captured so far: {', '.join(voice) or 'nothing yet'}."


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------


def _finalize(state: CallState, reason: str | None) -> None:
    if state.ended_at is None:
        state.ended_at = time.time()
    state.ended_reason = reason or state.ended_reason
    if state.status in ("dialling", "in_progress"):
        r = (reason or "").lower()
        if any(k in r for k in ("did-not-answer", "no-answer", "busy", "voicemail", "failed", "rejected")):
            state.outcome = "no_answer"
            state.status = "ended"
            state.event("outcome", f"No conversation — {reason}")
        else:
            state.outcome = state.outcome or "dropped"
            state.status = "ended"
            state.event("outcome", f"Call ended before completion ({reason or 'customer hung up'})")
    else:
        state.event("call", f"Call ended ({reason or 'normal'})")


@router.post("/webhook")
async def webhook(request: Request) -> dict:
    settings = get_settings()
    if settings.vapi_webhook_secret and request.headers.get("x-vapi-secret") != settings.vapi_webhook_secret:
        raise HTTPException(401, "bad webhook secret")

    body = await request.json()
    message = body.get("message", {})
    msg_type = message.get("type")
    call = message.get("call") or {}
    call_id = call.get("id", "unknown")

    if msg_type == "tool-calls":
        return await _handle_tool_calls(message)

    state = store.get_or_create(call_id)
    _attach_lead(state, _lead_id_from_message(message))

    if msg_type == "status-update":
        status = message.get("status")
        if status in ("queued", "ringing"):
            if state.status not in _TERMINAL:
                state.status = "dialling"
            state.event("call", f"Call {status}")
        elif status == "in-progress":
            if state.status in ("dialling", "in_progress"):
                state.status = "in_progress"
            state.event("call", "Customer answered — Ava is on the line")
        elif status == "forwarding":
            state.human_joined_at = state.human_joined_at or time.time()
            state.event("handoff", "Transfer to human requested (Vapi is bridging the call)")
        elif status == "ended":
            _finalize(state, message.get("endedReason"))

    elif msg_type == "transcript" and message.get("transcriptType") == "final":
        role = message.get("role")
        text = message.get("transcript") or ""
        if role == "user":
            for sig, category in signals.detect(text):
                state.signals.append({"type": sig, "text": text, "ts": time.time()})
                state.event("signal", f"Signal detected: {sig.replace('_', ' ')}")
                if sig == "opt_out":
                    phone = _phone_of(state)
                    if phone:
                        dnc.suppress(phone)
                if sig in ("card_data", "human_request", "anger") and category:
                    _escalate(state, category, f"Detected in customer speech: {sig.replace('_', ' ')}",
                              _summary(state), auto=True)
            text = signals.redact_card(text)
        state.transcript.append({"role": role, "text": text, "ts": time.time()})

    elif msg_type == "end-of-call-report":
        artifact = message.get("artifact") or {}
        state.recording_url = artifact.get("recordingUrl") or state.recording_url
        state.summary = message.get("summary") or (message.get("analysis") or {}).get("summary") or state.summary
        _finalize(state, message.get("endedReason"))

    await store.publish(call_id)
    return {}


# ---------------------------------------------------------------------------
# Leads, dialling, queue
# ---------------------------------------------------------------------------


def _lead_status(lead_id: str) -> tuple[str, str | None]:
    calls = [c for c in store.list_recent(200) if c.lead_id == lead_id]
    if not calls:
        return "new", None
    c = calls[0]
    if c.status in ("dialling", "in_progress"):
        return "calling", c.call_id
    if c.status == "blocked":
        return "dnc_blocked", c.call_id
    if c.outcome == "no_answer":
        return "no_answer", c.call_id
    return (c.outcome or c.status), c.call_id


@router.get("/leads")
def list_leads() -> list[dict]:
    journey = get_journey()
    out = []
    for lead in leads.list_leads():
        status, last_call = _lead_status(lead["id"])
        pre = dnc.check(lead["phone"])
        out.append({
            **lead,
            "resume_section": leads.resume_section_id(lead, journey),
            "status": status,
            "last_call_id": last_call,
            "dnc_allowed": pre["allowed"],
        })
    return out


@router.get("/leads/{lead_id}/precheck")
def precheck(lead_id: str) -> dict:
    lead = leads.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "unknown lead")
    return dnc.check(lead["phone"])


async def _dial(lead: dict) -> dict:
    settings = get_settings()
    check = dnc.check(lead["phone"])

    if not check["allowed"]:
        state = CallState(call_id=f"blocked-{uuid.uuid4().hex[:8]}", status="blocked", outcome="dnc_blocked",
                          mode="phone", dnc_check=check)
        state.ended_at = time.time()
        store._calls[state.call_id] = state
        _attach_lead(state, lead["id"])
        state.event("dnc", "Dial BLOCKED by Do-Not-Call gate: " + "; ".join(c["detail"] for c in check["checks"] if not c["passed"]))
        await store.publish(state.call_id)
        return {"allowed": False, "checks": check["checks"], "call_id": state.call_id}

    missing = [k for k, v in (("VAPI_API_KEY", settings.vapi_api_key), ("VAPI_ASSISTANT_ID", settings.vapi_assistant_id),
                              ("VAPI_PHONE_NUMBER_ID", settings.vapi_phone_number_id)) if not v]
    if missing:
        raise HTTPException(503, f"Backend not configured for outbound calls: set {', '.join(missing)}")

    journey = get_journey()
    body = {
        "assistantId": settings.vapi_assistant_id,
        "phoneNumberId": settings.vapi_phone_number_id,
        "customer": {"number": lead["phone"], "name": lead["full_name"]},
        "assistantOverrides": {
            "firstMessage": leads.opener(lead, journey),
            "variableValues": leads.call_variables(lead),
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post("https://api.vapi.ai/call", json=body,
                                 headers={"Authorization": f"Bearer {settings.vapi_api_key}"})
    if not resp.is_success:
        raise HTTPException(502, f"Vapi refused the call: {resp.text[:300]}")
    data = resp.json()
    call_id = data["id"]
    if (data.get("monitor") or {}).get("controlUrl"):
        _control_urls[call_id] = data["monitor"]["controlUrl"]

    state = store.get_or_create(call_id)
    state.status = "dialling"
    state.mode = "phone"
    state.dnc_check = check
    _attach_lead(state, lead["id"])
    state.event("dnc", "Do-Not-Call gate passed: " + "; ".join(f"{c['name']} ✓" for c in check["checks"]))
    state.event("call", f"Dialling {lead['full_name']}")
    await store.publish(call_id)
    return {"allowed": True, "checks": check["checks"], "call_id": call_id}


@router.post("/leads/{lead_id}/call")
async def call_lead(lead_id: str) -> dict:
    lead = leads.get_lead(lead_id)
    if not lead:
        raise HTTPException(404, "unknown lead")
    return await _dial(lead)


def _next_eligible() -> dict | None:
    """Cron simulation: the next lead worth calling — furthest through the journey first."""
    journey = get_journey()
    order = ["none"] + [s.id for s in journey.sections]
    candidates = []
    for lead in leads.list_leads():
        status, _ = _lead_status(lead["id"])
        if status in ("new", "no_answer", "callback", "dropped") and dnc.check(lead["phone"])["allowed"]:
            depth = order.index(lead["last_completed_step"]) if lead["last_completed_step"] in order else 0
            candidates.append((-depth, lead["id"], lead))
    candidates.sort(key=lambda t: t[:2])
    return candidates[0][2] if candidates else None


@router.get("/queue/next")
def queue_next() -> dict:
    lead = _next_eligible()
    return {"lead": lead}


@router.post("/queue/run")
async def queue_run() -> dict:
    lead = _next_eligible()
    if not lead:
        raise HTTPException(404, "No eligible leads left in the queue")
    return {"lead_id": lead["id"], **await _dial(lead)}


# ---------------------------------------------------------------------------
# Dashboard-facing API
# ---------------------------------------------------------------------------


@router.get("/calls")
def list_calls() -> list[dict]:
    return [c.to_dict() for c in store.list_recent() if c.call_id != "unknown"]


@router.get("/leads/{lead_id}/profile")
def lead_profile(lead_id: str) -> dict:
    """The customer's journey form as stored in the database, plus the audit trail of changes."""
    if not leads.get_lead(lead_id):
        raise HTTPException(404, "unknown lead")
    return {"lead_id": lead_id, "fields": db.get_profile(lead_id), "history": db.get_history(lead_id)}


@router.get("/calls/{call_id}")
def get_call(call_id: str) -> dict:
    call = store.get(call_id)
    if not call:
        raise HTTPException(404, "unknown call")
    return call.to_dict()


@router.post("/calls/{call_id}/take-over")
async def take_over(call_id: str) -> dict:
    call = store.get(call_id)
    if not call:
        raise HTTPException(404, "unknown call")
    call.human_joined_at = call.human_joined_at or time.time()
    call.event("handoff", f"{get_settings().human_agent_name} (human) took over with full context")
    await store.publish(call_id)
    return call.to_dict()


@router.post("/calls/{call_id}/end")
async def end_call(call_id: str) -> dict:
    url = _control_urls.get(call_id)
    if not url:
        raise HTTPException(404, "no live control channel for this call")
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, json={"type": "end-call"})
    return {"ok": True}


@router.get("/metrics")
def get_metrics() -> dict:
    return metrics.compute()


@router.get("/stream")
async def stream_all() -> StreamingResponse:
    """One SSE feed for the whole console: every call update, full state, as it happens."""

    async def source():
        queue = store.subscribe_all()
        try:
            yield ": connected\n\n"
            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            store.unsubscribe_all(queue)

    return StreamingResponse(source(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/journey")
def journey_definition() -> dict:
    j = get_journey()
    return {
        "vertical": j.vertical,
        "name": j.name,
        "opener_template": j.opener_template,
        "handoff_script": j.handoff_script,
        "agent_name": get_settings().human_agent_name,
        "guardrails": j.guardrails,
        "sections": [s.model_dump() for s in j.sections],
    }
