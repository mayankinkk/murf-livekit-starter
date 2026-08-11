import json
import os
import pytest
from unittest.mock import MagicMock

from agent import Assistant
from livekit.agents import RunContext


@pytest.mark.asyncio
async def test_create_escalation() -> None:
    # Instantiate Assistant
    assistant = Assistant()

    # Mock RunContext
    context = MagicMock(spec=RunContext)

    # Escalation parameters
    name = "Test User"
    contact_number = "+919999999999"
    reason = "Possible Fraud / Unauthorized Transaction"
    summary = "Tested escalation tool locally"
    urgency = "Urgent"
    preferred_language = "Hinglish"

    # Call the tool method directly
    result_str = await assistant.create_escalation(
        context=context,
        name=name,
        contact_number=contact_number,
        reason=reason,
        summary=summary,
        urgency=urgency,
        preferred_language=preferred_language,
    )

    # Verify return value
    result = json.loads(result_str)
    assert result["status"] == "success"
    assert "reference_id" in result
    assert result["reference_id"].startswith("ESC-")

    # Verify that the JSON file was written and contains the entry
    paths = [
        "/home/mayank/Documents/Murf AI/murf-livekit-starter/frontend/public/escalations.json",
        "../frontend/public/escalations.json",
        "frontend/public/escalations.json",
        "./frontend/public/escalations.json",
    ]

    found = False
    for path in paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, list):
                        continue
                    # Find our entry
                    entry = next(
                        (e for e in data if e["id"] == result["reference_id"]),
                        None,
                    )
                    if entry:
                        assert entry["name"] == name
                        assert entry["contact_number"] == contact_number
                        assert entry["reason"] == reason
                        assert entry["summary"] == summary
                        assert entry["urgency"] == urgency
                        assert entry["preferred_language"] == preferred_language
                        assert entry["status"] == "Open"
                        found = True

                        # Clean up: remove the test entry from the file
                        data.remove(entry)
                        with open(path, "w", encoding="utf-8") as f_out:
                            json.dump(
                                data, f_out, indent=2, ensure_ascii=False
                            )
                        break
            except Exception:
                continue

    assert (
        found is True
    ), "Escalation entry was not found in any of the public JSON paths"
