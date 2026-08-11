"""Trigger a Day 6 RupeeGPT outbound call.

The outbound agent doesn't call anyone on its own - it waits to be dispatched
into a room with a target number attached. This script does that dispatch.

Make sure the worker is running first (terminal 1):

    uv run python src/telephony/outbound/agent.py dev

Then place a call (terminal 2):

    uv run python src/telephony/outbound/dial.py --to <your-linphone-username>

For this challenge the target is a Linphone account, so `--to` is the Linphone
username (LiveKit dials it as ``sip:<username>@sip.linphone.org`` through the
configured outbound trunk). E.164 phone numbers such as ``+15551234567`` work
too if a PSTN trunk is configured. To check the dispatch without ringing
anyone, add ``--dry-run``.

This is the scriptable equivalent of:

    lk dispatch create --agent-name outbound-agent --room my-room \
      --metadata '{"phone_number": "<username>"}'
"""

import argparse
import asyncio
import json
import os
import uuid

from dotenv import load_dotenv
from livekit import api

load_dotenv(".env.local")

# Must match AGENT_NAME in agent.py.
AGENT_NAME = "outbound-agent"

DEFAULT_ROOM_PREFIX = "outbound"


def build_metadata(phone_number: str) -> str:
    """JSON payload the agent reads to know who to call."""
    return json.dumps({"phone_number": phone_number})


async def create_dispatch(lk, *, room_name: str, metadata: str) -> None:
    """Create the room and dispatch the outbound agent into it.

    ``lk`` is a ``livekit.api.LiveKitAPI`` instance; it is injected so the same
    code path can be unit-tested without a real server, and wrapped by
    :func:`dial` with the real client.
    """
    await lk.room.create_room(api.CreateRoomRequest(name=room_name))
    await lk.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=AGENT_NAME,
            room=room_name,
            metadata=metadata,
        )
    )


async def dial(phone_number: str, room_name: str) -> None:
    """Connect to LiveKit and dispatch the outbound agent (real call)."""
    lk = api.LiveKitAPI()
    try:
        await create_dispatch(
            lk, room_name=room_name, metadata=build_metadata(phone_number)
        )
    finally:
        await lk.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Place an outbound call.")
    parser.add_argument(
        "--to",
        required=True,
        help=(
            "Target to call: a Linphone username (e.g. myname) or an E.164 "
            "phone number (e.g. +15551234567)."
        ),
    )
    parser.add_argument(
        "--room",
        default=None,
        help="Room name to use. Defaults to a generated one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate config and print what would be dispatched without "
            "connecting to LiveKit or ringing anyone."
        ),
    )
    args = parser.parse_args()

    target = (args.to or "").strip()
    if not target:
        parser.error("--to cannot be empty.")

    room_name = args.room or f"{DEFAULT_ROOM_PREFIX}-{uuid.uuid4().hex[:8]}"
    metadata = build_metadata(target)

    if args.dry_run:
        trunk = os.getenv("LIVEKIT_SIP_OUTBOUND_TRUNK_ID", "").strip()
        status = "OK" if trunk else "MISSING"
        print(f"[dry-run] agent name : {AGENT_NAME}")
        print(f"[dry-run] room        : {room_name}")
        print(f"[dry-run] metadata    : {metadata}")
        print(
            f"[dry-run] trunk env    : "
            f"{'LIVEKIT_SIP_OUTBOUND_TRUNK_ID is set' if trunk else 'LIVEKIT_SIP_OUTBOUND_TRUNK_ID is MISSING'} "
            f"(used by the agent to dial)"
        )
        print(f"[dry-run] status      : {status} — no call was placed")
        return

    asyncio.run(dial(target, room_name))

    print(f"Dispatched {AGENT_NAME} to room '{room_name}' to call {target}.")
    print("Watch the worker terminal for call progress.")


if __name__ == "__main__":
    main()
