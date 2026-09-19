"""Create or update the Vapi assistant from our journey config.

Usage (from backend/, venv active, PYTHONPATH=.):
    python scripts/create_assistant.py https://your-public-backend-url          # update VAPI_ASSISTANT_ID in place, else create
    python scripts/create_assistant.py https://your-public-backend-url --new    # always create a new assistant

Updating in place keeps the assistant id stable, so nothing else needs re-pasting.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings
from app.journey.prompt import build_assistant_payload


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force_new = "--new" in sys.argv
    if len(args) != 1:
        print("Usage: python scripts/create_assistant.py <public_base_url> [--new]")
        raise SystemExit(1)

    settings = get_settings()
    if not settings.vapi_api_key:
        print("Set VAPI_API_KEY in backend/.env first.")
        raise SystemExit(1)

    payload = build_assistant_payload(args[0])
    headers = {"Authorization": f"Bearer {settings.vapi_api_key}"}

    if settings.vapi_assistant_id and not force_new:
        resp = httpx.patch(f"https://api.vapi.ai/assistant/{settings.vapi_assistant_id}", headers=headers, json=payload, timeout=30)
        verb = "Updated"
    else:
        resp = httpx.post("https://api.vapi.ai/assistant", headers=headers, json=payload, timeout=30)
        verb = "Created"
    if not resp.is_success:
        print(resp.status_code, resp.text)
        raise SystemExit(1)
    assistant_id = resp.json()["id"]
    print(f"{verb} assistant: {assistant_id}")
    print(f"\nbackend/.env:   VAPI_ASSISTANT_ID={assistant_id}")


if __name__ == "__main__":
    main()
