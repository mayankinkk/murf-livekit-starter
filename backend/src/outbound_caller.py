"""
outbound_caller.py — Day 6: BharatPay Outbound Calls

Use case (Financial Services track):
    A scheme enrollment deadline is approaching for users already found eligible.
    Pooja proactively calls them so they don't miss the window.

Supported telephony backends:
    1. Twilio  — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in .env.local
    2. Linphone SIP — set LINPHONE_SIP_URI, LINPHONE_SIP_PASSWORD, LINPHONE_OUTBOUND_SERVER

How it works:
    ┌─────────────────────────────────────────────────────────┐
    │                                                         │
    │  outbound_caller.py                                     │
    │   1. Creates a LiveKit room for this call               │
    │   2. Dispatches the 'pooja-voice' agent to the room     │
    │   3. Dials the target phone number (Twilio or Linphone) │
    │   4. Bridges the PSTN call into the LiveKit room via SIP│
    │                                                         │
    └─────────────────────────────────────────────────────────┘

Usage:
    uv run src/outbound_caller.py --phone +91XXXXXXXXXX --scheme "PM Mudra Yojana" --name "Rahul"
    uv run src/outbound_caller.py --phone +91XXXXXXXXXX --backend linphone
"""

import argparse
import asyncio
import logging
import os
import sys
import uuid

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env.local"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("outbound")

# ---------------------------------------------------------------------------
# LiveKit imports for room + agent dispatch
# ---------------------------------------------------------------------------
try:
    from livekit import api as livekit_api
except ImportError:
    logger.error("livekit package not installed. Run: uv sync")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helper — create a LiveKit room and dispatch the agent to it
# ---------------------------------------------------------------------------

async def _create_room_and_dispatch_agent(
    room_name: str,
    caller_phone: str,
    scheme_name: str,
    caller_name: str | None,
) -> str:
    """
    Creates a LiveKit room, dispatches 'pooja-voice' to it, and returns
    the room name so we can bridge the PSTN call into it.
    """
    livekit_url = os.environ["LIVEKIT_URL"]
    api_key = os.environ["LIVEKIT_API_KEY"]
    api_secret = os.environ["LIVEKIT_API_SECRET"]

    lkapi = livekit_api.LiveKitAPI(livekit_url, api_key, api_secret)

    # 1. Create the room
    await lkapi.room.create_room(
        livekit_api.CreateRoomRequest(
            name=room_name,
            empty_timeout=300,   # auto-delete after 5 min of silence
            max_participants=5,
        )
    )
    logger.info("LiveKit room created: %s", room_name)

    # 2. Dispatch the agent with outbound metadata so it knows the context
    import json
    metadata = json.dumps({
        "call_type": "outbound",
        "caller_phone": caller_phone,
        "scheme_name": scheme_name,
        "caller_name": caller_name or "",
        "trigger": "scheme_deadline_reminder",
    })

    await lkapi.agent.create_agent_dispatch(
        livekit_api.CreateAgentDispatchRequest(
            agent_name="pooja-voice",
            room=room_name,
            metadata=metadata,
        )
    )
    logger.info("Agent 'pooja-voice' dispatched to room: %s", room_name)

    await lkapi.aclose()
    return room_name


# ---------------------------------------------------------------------------
# Backend 1 — Twilio
# ---------------------------------------------------------------------------

async def _call_via_twilio(
    phone_number: str,
    room_name: str,
    caller_name: str | None,
    scheme_name: str,
) -> None:
    """
    Uses Twilio to dial the phone number and bridge it into the LiveKit room via SIP.
    Requires:
        TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER
    Optional:
        LIVEKIT_SIP_TRUNK_URI  — your LiveKit SIP trunk domain
    """
    try:
        from twilio.rest import Client as TwilioClient
    except ImportError:
        logger.error(
            "twilio package not installed.\n"
            "Install it: uv add twilio\n"
            "Then re-run this script."
        )
        sys.exit(1)

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER", "")

    if not all([account_sid, auth_token, from_number]):
        logger.error(
            "Twilio credentials missing. Set TWILIO_ACCOUNT_SID, "
            "TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER in backend/.env.local"
        )
        sys.exit(1)

    # LiveKit SIP trunk URI — looks like: sip:<room>@<project>.sip.livekit.cloud
    livekit_url = os.environ.get("LIVEKIT_URL", "")
    sip_domain = os.environ.get("LIVEKIT_SIP_TRUNK_URI", "")
    if not sip_domain:
        # Derive from LiveKit URL if not explicitly set
        # ws://localhost:7880 → sip.livekit.local (dev fallback)
        if "livekit.cloud" in livekit_url:
            host = livekit_url.replace("wss://", "").replace("ws://", "")
            project = host.split(".")[0]
            sip_domain = f"{project}.sip.livekit.cloud"
        else:
            sip_domain = "sip.livekit.local"

    sip_uri = f"sip:{room_name}@{sip_domain}"

    # TwiML: <Dial> into SIP URI = bridge PSTN → LiveKit
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="en-IN">
        Connecting you to BharatPay. Please wait a moment.
    </Say>
    <Dial>
        <Sip>{sip_uri}</Sip>
    </Dial>
</Response>"""

    client = TwilioClient(account_sid, auth_token)
    call = client.calls.create(
        twiml=twiml,
        to=phone_number,
        from_=from_number,
    )

    logger.info(
        "Twilio call initiated → SID: %s  To: %s  SIP: %s",
        call.sid, phone_number, sip_uri,
    )
    print(f"\n✅ Twilio call placed successfully!")
    print(f"   Call SID : {call.sid}")
    print(f"   Calling  : {phone_number}")
    print(f"   Room     : {room_name}")
    print(f"   Status   : {call.status}")


# ---------------------------------------------------------------------------
# Backend 2 — Linphone SIP (free trial / no Twilio)
# ---------------------------------------------------------------------------

async def _call_via_linphone(
    phone_number: str,
    room_name: str,
    caller_name: str | None,
    scheme_name: str,
) -> None:
    """
    Uses linphonec (Linphone CLI) to place an outbound SIP call.
    The call goes through your SIP provider and is bridged via SIP into LiveKit.

    Requires (in .env.local):
        LINPHONE_SIP_URI         — your SIP account, e.g. sip:+91XXXXXXXXXX@sip.linphone.org
        LINPHONE_SIP_PASSWORD    — your SIP account password
        LINPHONE_OUTBOUND_PROXY  — e.g. sip:sip.linphone.org;transport=tls

    Also requires:
        linphonec installed: sudo apt install linphone-nogtk
    """
    import shutil
    import tempfile

    sip_uri = os.environ.get("LINPHONE_SIP_URI", "")
    sip_password = os.environ.get("LINPHONE_SIP_PASSWORD", "")
    outbound_proxy = os.environ.get("LINPHONE_OUTBOUND_PROXY", "")

    if not all([sip_uri, sip_password]):
        logger.error(
            "Linphone credentials missing.\n"
            "Set LINPHONE_SIP_URI and LINPHONE_SIP_PASSWORD in backend/.env.local\n\n"
            "Example:\n"
            "  LINPHONE_SIP_URI=sip:+91XXXXXXXXXX@sip.linphone.org\n"
            "  LINPHONE_SIP_PASSWORD=your_linphone_password\n"
            "  LINPHONE_OUTBOUND_PROXY=sip:sip.linphone.org;transport=tls"
        )
        sys.exit(1)

    if shutil.which("linphonec") is None:
        logger.error(
            "linphonec not found. Install with:\n"
            "  sudo apt install linphone-nogtk\n"
            "Or on Fedora/RHEL: sudo dnf install linphone"
        )
        sys.exit(1)

    # Build a temporary linphonerc config
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".rc", prefix="linphone_", delete=False
    ) as f:
        rc_path = f.name
        f.write(f"""[proxy_0]
reg_proxy={outbound_proxy or sip_uri.split("@")[1] if "@" in sip_uri else "sip.linphone.org"}
reg_identity={sip_uri}
reg_expires=3600
reg_sendregister=1

[auth_info_0]
username={sip_uri.split(":")[1].split("@")[0] if ":" in sip_uri else sip_uri}
passwd={sip_password}
realm=*

[sound]
capture_dev=default
playback_dev=default

[video]
enabled=0
""")

    logger.info("Linphone config written to: %s", rc_path)

    # Linphone CLI command sequence
    # We send DTMF commands as a script piped to linphonec
    linphone_commands = f"""
register {sip_uri} {sip_password}
sleep 2
call {phone_number}
sleep 60
terminate
quit
""".strip()

    logger.info("Placing call via Linphone to: %s", phone_number)
    print(f"\n📞 Placing call via Linphone SIP...")
    print(f"   Calling  : {phone_number}")
    print(f"   From     : {sip_uri}")
    print(f"   Room     : {room_name}")

    # Use linphonec in command mode
    proc = await asyncio.create_subprocess_exec(
        "linphonec", "--pipe", "-c", rc_path,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await proc.communicate(input=linphone_commands.encode())
    logger.info("Linphone stdout:\n%s", stdout.decode(errors="replace"))
    if stderr:
        logger.warning("Linphone stderr:\n%s", stderr.decode(errors="replace"))

    os.unlink(rc_path)
    print("✅ Linphone call session completed.")


# ---------------------------------------------------------------------------
# Main outbound call orchestrator
# ---------------------------------------------------------------------------

async def make_outbound_call(
    phone_number: str,
    caller_name: str | None = None,
    scheme_name: str = "PM Mudra Yojana",
    backend: str = "twilio",
) -> None:
    """
    Full outbound call flow:
    1. Generate a unique room name for this call
    2. Create the LiveKit room + dispatch Pooja to it
    3. Dial the phone number via the chosen backend
    """
    # Sanitise phone number for use as room name component
    safe_phone = phone_number.replace("+", "").replace("-", "").replace(" ", "")
    room_name = f"outbound-{safe_phone}-{uuid.uuid4().hex[:8]}"

    logger.info(
        "Starting outbound call | phone=%s  scheme=%s  backend=%s  room=%s",
        phone_number, scheme_name, backend, room_name,
    )

    print(f"\n{'─'*60}")
    print(f"  BharatPay Day 6 — Outbound Call")
    print(f"{'─'*60}")
    print(f"  Target    : {phone_number}")
    print(f"  Name      : {caller_name or 'unknown'}")
    print(f"  Scheme    : {scheme_name}")
    print(f"  Backend   : {backend}")
    print(f"  Room      : {room_name}")
    print(f"{'─'*60}\n")

    # Step 1: Create room + dispatch agent
    await _create_room_and_dispatch_agent(
        room_name=room_name,
        caller_phone=phone_number,
        scheme_name=scheme_name,
        caller_name=caller_name,
    )

    # Step 2: Dial the phone
    if backend == "twilio":
        await _call_via_twilio(phone_number, room_name, caller_name, scheme_name)
    elif backend == "linphone":
        await _call_via_linphone(phone_number, room_name, caller_name, scheme_name)
    else:
        logger.error("Unknown backend: %s. Use 'twilio' or 'linphone'.", backend)
        sys.exit(1)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="BharatPay Day 6 — Place an outbound call via Pooja Voice Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Call via Twilio (default):
  uv run src/outbound_caller.py --phone +91XXXXXXXXXX --name "Rahul" --scheme "PM Mudra Yojana"

  # Call via Linphone (free SIP):
  uv run src/outbound_caller.py --phone +91XXXXXXXXXX --backend linphone

  # Test without a real phone (just dispatch agent to room):
  uv run src/outbound_caller.py --phone +91XXXXXXXXXX --dry-run
        """,
    )
    parser.add_argument(
        "--phone",
        required=True,
        help="Target phone number in E.164 format (e.g. +91XXXXXXXXXX)",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Name of the person being called (optional, for personalized greeting)",
    )
    parser.add_argument(
        "--scheme",
        default="PM Mudra Yojana",
        help="Government scheme whose deadline is approaching (default: PM Mudra Yojana)",
    )
    parser.add_argument(
        "--backend",
        choices=["twilio", "linphone"],
        default="twilio",
        help="Telephony backend to use (default: twilio)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Create the LiveKit room and dispatch the agent, but do NOT dial the phone",
    )

    args = parser.parse_args()

    if args.dry_run:
        safe_phone = args.phone.replace("+", "").replace("-", "").replace(" ", "")
        room_name = f"outbound-{safe_phone}-{uuid.uuid4().hex[:8]}"
        print(f"\n🔧 DRY RUN — agent will be dispatched but phone will NOT be dialled")
        print(f"   Room: {room_name}\n")
        asyncio.run(
            _create_room_and_dispatch_agent(
                room_name=room_name,
                caller_phone=args.phone,
                scheme_name=args.scheme,
                caller_name=args.name,
            )
        )
        print("\n✅ Dry run complete. Agent dispatched and waiting in room.")
        return

    asyncio.run(
        make_outbound_call(
            phone_number=args.phone,
            caller_name=args.name,
            scheme_name=args.scheme,
            backend=args.backend,
        )
    )


if __name__ == "__main__":
    main()
