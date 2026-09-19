"""Import the Vobiz SIP trunk + phone number into the Vapi account that VAPI_API_KEY belongs to.

    VOBIZ_SIP_PASSWORD='...' python scripts/setup_vapi_number.py <sip_domain> <sip_username> <e164_number>
    e.g. VOBIZ_SIP_PASSWORD='...' python scripts/setup_vapi_number.py 01a59afb.sip.vobiz.ai VoiceAI +918071582913

The password is read from the environment so it never lands in shell history or a file.
Prints the phone-number id to put in VAPI_PHONE_NUMBER_ID. A number can live in only ONE Vapi
account at a time: delete it from the old account first (see VAPI_SETUP.md).
"""

import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import get_settings

API = "https://api.vapi.ai"


def main() -> None:
    if len(sys.argv) != 4 or not os.environ.get("VOBIZ_SIP_PASSWORD"):
        print(__doc__)
        raise SystemExit(1)
    domain, username, number = sys.argv[1:]
    key = get_settings().vapi_api_key
    if not key:
        print("Set VAPI_API_KEY in backend/.env first.")
        raise SystemExit(1)
    headers = {"Authorization": f"Bearer {key}"}

    cred = httpx.post(f"{API}/credential", headers=headers, timeout=60, json={
        "provider": "byo-sip-trunk",
        "name": "Vobiz Trunk",
        "gateways": [{"ip": domain, "inboundEnabled": False, "outboundEnabled": True}],
        "outboundAuthenticationPlan": {"authUsername": username, "authPassword": os.environ["VOBIZ_SIP_PASSWORD"]},
    })
    if not cred.is_success:
        print("Credential failed:", cred.status_code, cred.text)
        raise SystemExit(1)
    print("SIP trunk credential created.")

    num = httpx.post(f"{API}/phone-number", headers=headers, timeout=60, json={
        "provider": "byo-phone-number",
        "name": "Vobiz India",
        "number": number,
        "numberE164CheckEnabled": False,
        "credentialId": cred.json()["id"],
    })
    if not num.is_success:
        print("Phone number failed:", num.status_code, num.text)
        raise SystemExit(1)
    print(f"\nbackend/.env:   VAPI_PHONE_NUMBER_ID={num.json()['id']}")


if __name__ == "__main__":
    main()
