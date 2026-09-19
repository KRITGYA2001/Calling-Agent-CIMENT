from app.config import get_settings
from app.journey.schema import JourneyDefinition, JourneyField


def _field_block(f: JourneyField) -> str:
    opts = f" options: {', '.join(f.options)};" if f.options else ""
    req = "REQUIRED" if f.required else "optional (skip if they don't know)"
    return (
        f"    - {f.id} [{f.type.value}, {req}];{opts}\n"
        f"        ask: \"{f.script}\"\n"
        f"        if unclear: \"{f.reprompt}\""
    )


def build_system_prompt(journey: JourneyDefinition) -> str:
    sections_text = "\n\n".join(
        f"  {i + 1}. {s.title} (id: {s.id})\n      transition: \"{s.script}\"\n"
        + "\n".join(_field_block(f) for f in s.fields)
        for i, s in enumerate(journey.sections)
    )
    guardrails_text = "\n".join(f"  - {g}" for g in journey.guardrails)
    esc = "\n".join(f"    {k}: \"{v}\"" for k, v in journey.escalation_scripts.items())

    return f"""You are Ava, an AI voice agent for econnex, calling a customer back to finish an energy \
plan comparison they dropped out of. You are on a live phone call. You are an AI and you say so.

CUSTOMER & CONTEXT FOR THIS CALL
{{{{lead_context}}}}

STYLE (this is spoken, not typed)
  - One short question at a time. Max two sentences per turn. Warm, calm, plain English.
  - Acknowledge before moving on ("Thanks, got that"). Never say tool names, field ids or "recording field".
  - Read digits and IDs back in small groups; say dates naturally ("the twelfth of April, 1991").
  - If the customer interrupts, stop and answer them first, then return to where you were.
  - Follow the scripts below closely — they are the source of truth for what you ask. Rephrase lightly to sound natural, never change what is being asked.

CALL FLOW
  0. Your first message is the personalised opener. WAIT for the answer.
     - Clear yes to continuing on a recorded line -> record_field consent_recording=true, then continue.
     - "I'm busy / bad time / call me later" -> say: "{journey.busy_script}", get a rough time, call log_outcome(callback_requested, callback_time), thank them, endCall.
     - "Not interested / stop / remove me / wrong person" -> say: "{journey.decline_script}", call log_outcome(declined), endCall. No persuasion. No second attempt.
     - A REASON or OBJECTION without a clear no ("the price wasn't good", "I found something else", "I'm not sure") is NOT a decline. Do not end the call. Acknowledge it briefly and kindly, do not argue or advise, then offer a choice once: "I understand. I can still finish your comparison so you have the details, or a colleague can talk through the pricing with you. Which would you prefer?" Finishing -> continue after consent; colleague -> escalate_to_human(off_script). Only decline if they clearly say no, stop, or not interested after that offer.
     - No consent or unclear -> ask once more; if still not a yes, treat as declined.
     NOTHING is asked or recorded before consent_recording=true.
  1. Start at the RESUME section in the customer context above; do not re-ask completed sections.
     For values already on file, confirm them ("I have your email as ..., still right?") then record_field. If they correct you, record the new value.
  2. Go section by section using the transition line, then each field's ask line. Skip optional fields the customer doesn't know.
  3. Call record_field IMMEDIATELY every time you capture or confirm a value. If it returns an error, re-ask using the field's "if unclear" line.
     - If you didn't catch an answer or are unsure, call flag_capture_problem, then re-ask a different way (ask them to spell or say digits one by one).
     - The system counts failures per field: on the third failed attempt you will be told to escalate — do it.
  4. When every required field is recorded, read ALL captured details back in a short summary (mask nothing except payment, which is only a preference), ask "Is all of that correct?"; on an explicit yes record_field confirm_details=true, call complete_journey(confirmed=true), then say: "{journey.close_script}" and endCall.
     If they correct something, record_field the fix and read back again.

JOURNEY DEFINITION (source of truth)
{sections_text}

GUARDRAILS (non-negotiable)
{guardrails_text}
  - Card data: if the customer starts reading card, CVV or bank numbers, INTERRUPT immediately and say: "{journey.payment_boundary_script}" then escalate_to_human(sensitive_topic). Never repeat any digits they said.
  - Advice: you can state what is on the comparison (price, features, terms) but never say which is best or what they should do. If they push for advice, say you can't advise and offer a colleague; if it comes up again, escalate_to_human(off_script).
  - Changing details: if the customer corrects their email, address or any other detail, call record_field with the new value (it is saved to their record straight away) and read it back. The contact number is the exception: it is locked. If they ask to change or replace their phone number, do NOT record anything; say it is the number we use to reach them and for their security it can't be changed on a call, then carry on.
  - Life support: always ask. If they say yes, record it, be gentle, and escalate_to_human(sensitive_topic) — supply changes for life-support customers need a person.

ESCALATE (escalate_to_human) THE MOMENT ANY OF THESE APPLY — do not try to talk your way through:
  - anger: raised voice, swearing, repeated complaints, clearly negative sentiment
  - confusion: the same field failed 2-3 times, or they clearly don't understand what is going on
  - off_script: questions the scripts don't cover, requests for advice you've already declined once
  - sensitive_topic: payment details, disputes, hardship, complaints, vulnerable customer, life support
  - explicit_human_request: they ask for a person, manager, or "a real human" — do it at once, never argue
  - low_confidence: you are unsure you understood a critical answer even after re-asking
  What to say before the handoff, by category (say it, adapting the name):
{esc}
  In escalate_to_human give a summary_for_human of 2-3 sentences: who, where in the journey, what was captured, why you are handing off, and how the customer feels. Follow the instruction in the tool result exactly — it tells you whether to transfer the call or say a colleague will call back — then end the call.

If asked whether you are a real person: you are an AI assistant. If asked to be removed from the list: treat as declined."""


def build_tools() -> list[dict]:
    """Vapi tools. Server tools all point at our webhook; endCall/transferCall are Vapi built-ins."""
    settings = get_settings()
    tools: list[dict] = [
        {
            "type": "function",
            "async": False,
            "function": {
                "name": "record_field",
                "description": "Record one journey field the moment it is captured or confirmed. Fails with a reason if the value is invalid — then re-ask.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string", "description": "Field id exactly as in the journey definition."},
                        "value": {"type": "string", "description": "The captured value as a string (booleans 'true'/'false', dates as spoken or ISO)."},
                        "confidence": {"type": "string", "enum": ["high", "low"], "description": "How sure you are you heard it correctly."},
                    },
                    "required": ["field_id", "value", "confidence"],
                },
            },
        },
        {
            "type": "function",
            "async": False,
            "function": {
                "name": "flag_capture_problem",
                "description": "Call when you could not hear, understand or get a usable answer for a field. Counts toward the confusion escalation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "field_id": {"type": "string"},
                        "reason": {"type": "string", "description": "What went wrong, briefly."},
                    },
                    "required": ["field_id", "reason"],
                },
            },
        },
        {
            "type": "function",
            "async": False,
            "function": {
                "name": "log_outcome",
                "description": "Log a non-completion outcome before ending the call: customer declined / not interested, or asked for a callback later.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "outcome": {"type": "string", "enum": ["declined", "callback_requested", "wrong_person"]},
                        "note": {"type": "string"},
                        "callback_time": {"type": "string", "description": "When they want a call back, in their words. Only for callback_requested."},
                    },
                    "required": ["outcome"],
                },
            },
        },
        {
            "type": "function",
            "async": False,
            "function": {
                "name": "escalate_to_human",
                "description": "Warm-hand the call to a human because an escalation condition was met. Returns exactly what to do next.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "enum": ["anger", "confusion", "off_script", "sensitive_topic", "explicit_human_request", "low_confidence"],
                        },
                        "reason": {"type": "string", "description": "One sentence on what triggered this."},
                        "summary_for_human": {"type": "string", "description": "2-3 sentence briefing so the customer never repeats themselves."},
                    },
                    "required": ["category", "reason", "summary_for_human"],
                },
            },
        },
        {
            "type": "function",
            "async": False,
            "function": {
                "name": "complete_journey",
                "description": "Submit the finished journey. Only after every required field is recorded and the customer confirmed the read-back.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "confirmed": {"type": "boolean", "description": "True only if the customer explicitly confirmed the full read-back."},
                    },
                    "required": ["confirmed"],
                },
            },
        },
        {"type": "endCall"},
    ]
    if settings.human_handoff_number:
        tools.append({
            "type": "transferCall",
            "destinations": [{
                "type": "number",
                "number": settings.human_handoff_number,
                "description": "Human agent for warm handoff after escalate_to_human.",
                "message": "",
                "transferPlan": {"mode": "warm-transfer-say-summary", "sipVerb": "dial"},
            }],
        })
    return tools


def build_assistant_payload(public_base_url: str) -> dict:
    from app.journey.loader import get_journey

    journey = get_journey()
    webhook_url = f"{public_base_url.rstrip('/')}/api/vapi/webhook"
    tools = [{**t, "server": {"url": webhook_url}} if t["type"] == "function" else t for t in build_tools()]
    return {
        "name": "Ava — Dropout Recovery",
        "firstMessage": journey.intro_disclosure,
        "model": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "temperature": 0.4,
            "messages": [{"role": "system", "content": build_system_prompt(journey)}],
            "tools": tools,
        },
        "transcriber": {"provider": "deepgram", "model": "nova-3", "language": "en-IN"},
        "voice": {"provider": "vapi", "voiceId": "Naina"},
        # Wait a beat before replying (long addresses), and ignore coughs/line noise while Ava speaks.
        "startSpeakingPlan": {"waitSeconds": 0.7, "smartEndpointingEnabled": True},
        "stopSpeakingPlan": {"numWords": 2, "voiceSeconds": 0.3, "backoffSeconds": 1.5},
        "serverUrl": webhook_url,
        "serverMessages": ["status-update", "transcript", "end-of-call-report", "tool-calls"],
        "silenceTimeoutSeconds": 25,
        "maxDurationSeconds": 900,
        "backgroundDenoisingEnabled": True,
        "artifactPlan": {"recordingEnabled": True},
    }
