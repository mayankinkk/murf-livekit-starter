"""Day 6 outbound-call tests.

Deterministic (no real phone calls / no network): we verify the reminder data,
the safety wording of the opening and system prompt, the metadata parser, and
that ``dial.py`` builds the exact dispatch the agent worker expects.
"""

import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest

import schemes
from telephony.outbound import agent as outbound_agent
from telephony.outbound import dial as outbound_dial
from telephony.outbound import reminder


def _job_with_metadata(metadata):
    return SimpleNamespace(job=SimpleNamespace(metadata=metadata))


def _assistant_text(*parts: str) -> str:
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Day 6 data / safety requirements
# ---------------------------------------------------------------------------


def test_reminder_is_clearly_demo_but_scheme_is_real() -> None:
    """The deadline is a documented DEMO, and the scheme exists in the Day 5 data."""
    assert reminder.is_demo() is True
    assert reminder.status_label() == "demo"
    assert reminder.scheme_name() == "Pradhan Mantri Jan Dhan Yojana"
    assert reminder.deadline_human() == "31 August 2026"

    deadline = datetime.fromisoformat(reminder.DEMO_REMINDER["deadline_iso"]).date()
    assert isinstance(deadline, date)

    # The scheme must not be invented: it is a real row in the Day 5 dataset.
    records, _ = schemes.load_schemes()
    assert reminder.scheme_name() in {r["name"] for r in records}

    # And it must sit in the Financial Services category RupeeGPT specialises in.
    matches = [r for r in records if r["name"] == reminder.scheme_name()]
    assert matches
    assert "Banking,Financial Services" in matches[0]["category"]


def test_opening_identifies_who_why_and_how_to_stop() -> None:
    """The opening says who is calling, why, and how to end the call."""
    text = _assistant_text(outbound_agent.GREETING)
    assert "RupeeGPT" in text  # who is calling
    assert "government scheme" in text  # why
    assert "deadline" in text  # why (concrete reason)
    assert "end the call" in text  # how to stop


def test_system_prompt_contains_day6_safety_rules() -> None:
    """The prompt: no guaranteed eligibility, demo deadline, preliminary match,
    opt-out honoured by ending the call, never invent details."""
    prompt = outbound_agent.build_system_prompt()
    low = prompt.lower()

    assert "preliminary" in low
    assert "guaranteed" in low  # only appears negated ("never claim guaranteed")
    assert "never claim guaranteed" in low
    assert "demonstration" in low or "demo" in low
    assert "not a verified live government deadline" in low
    assert "official scheme page" in low
    assert "do not invent" in low
    assert "end_call" in low  # opt-out path ends the call


def test_system_prompt_uses_demo_values() -> None:
    """The one scheme/deadline the agent may discuss come from the demo data."""
    prompt = outbound_agent.build_system_prompt().lower()
    assert reminder.scheme_name().lower() in prompt
    assert reminder.deadline_human().lower() in prompt
    # The opening instructs not to repeat the already-spoken greeting.
    assert "already been spoken" in prompt


# ---------------------------------------------------------------------------
# agent.py metadata parsing
# ---------------------------------------------------------------------------


def test_phone_number_from_metadata_json() -> None:
    assert (
        outbound_agent.phone_number_from_metadata(
            _job_with_metadata('{"phone_number": "lin.mani"}')
        )
        == "lin.mani"
    )


def test_phone_number_from_metadata_bare() -> None:
    assert (
        outbound_agent.phone_number_from_metadata(_job_with_metadata("lin.mani"))
        == "lin.mani"
    )


def test_phone_number_from_metadata_empty() -> None:
    assert outbound_agent.phone_number_from_metadata(_job_with_metadata("")) is None
    assert outbound_agent.phone_number_from_metadata(_job_with_metadata(None)) is None
    assert (
        outbound_agent.phone_number_from_metadata(
            _job_with_metadata('{"phone_number": "  "}')
        )
        is None
    )


# ---------------------------------------------------------------------------
# dial.py + agent.py consistency
# ---------------------------------------------------------------------------


def test_dial_and_agent_share_agent_name() -> None:
    assert outbound_dial.AGENT_NAME == outbound_agent.AGENT_NAME
    assert outbound_dial.AGENT_NAME == "outbound-agent"


def test_dial_metadata_roundtrip() -> None:
    metadata = json.loads(outbound_dial.build_metadata("lin.mani"))
    assert metadata == {"phone_number": "lin.mani"}
    # The agent must be able to read it back (it parses a JSON *string*).
    assert (
        outbound_agent.phone_number_from_metadata(
            _job_with_metadata(json.dumps(metadata))
        )
        == "lin.mani"
    )


class _FakeRoom:
    def __init__(self, owner) -> None:
        self.owner = owner

    async def create_room(self, req) -> None:
        self.owner.rooms.append(req.name)


class _FakeAgentDispatch:
    def __init__(self, owner) -> None:
        self.owner = owner

    async def create_dispatch(self, req) -> None:
        self.owner.dispatches.append((req.agent_name, req.room, req.metadata))


class _FakeApi:
    def __init__(self) -> None:
        self.rooms: list[str] = []
        self.dispatches: list[tuple[str, str, str]] = []
        self.closed = False
        self.room = _FakeRoom(self)
        self.agent_dispatch = _FakeAgentDispatch(self)

    async def aclose(self) -> None:
        self.closed = True


@pytest.mark.asyncio
async def test_create_dispatch_configures_the_agent_call() -> None:
    """dial.py must dispatch the outbound agent with the target in its
    metadata, into the named room - exactly what the worker consumes."""
    fake = _FakeApi()
    await outbound_dial.create_dispatch(
        fake,
        room_name="outbound-abc123",
        metadata=outbound_dial.build_metadata("lin.mani"),
    )

    assert fake.rooms == ["outbound-abc123"]
    assert len(fake.dispatches) == 1
    agent_name, room, metadata = fake.dispatches[0]
    assert agent_name == "outbound-agent"
    assert room == "outbound-abc123"
    assert json.loads(metadata)["phone_number"] == "lin.mani"
