"""Day 6 domain data for the RupeeGPT outbound reminder.

This is the "government scheme deadline reminder" use case (Financial Services
track): the agent calls a person who was previously identified as a
*preliminary* match for a scheme (Day 5) and tells them an application deadline
is approaching.

What is real
------------
The *scheme* is real: "Pradhan Mantri Jan Dhan Yojana" exists in the Day 5
dataset (``backend/data/Schemes.csv``, Financial Services category, Central
scheme, dataset collected 5 July 2026).

What is NOT real
----------------
The public scheme dataset has **no verified live government application
deadlines** - it is a static snapshot derived from myscheme.gov.in (see
``src/schemes.py``). Per the Day 6 rules we therefore use a clearly documented
**DEMO/TEST deadline** instead of inventing a real government deadline. It is
hard-coded below and flagged with ``is_demo=True``.

The agent is instructed to state, whenever it talks about the deadline, that
this is a demonstration/test reminder and that the caller should verify current
details on the official scheme page.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# DEMO / TEST reminder. Only the deadline is fictional - the scheme is real.
# ---------------------------------------------------------------------------
DEMO_REMINDER: dict[str, object] = {
    "scheme_name": "Pradhan Mantri Jan Dhan Yojana",
    "category": "Banking, Financial Services and Insurance",
    "is_demo": True,
    "deadline": "31 August 2026",
    "deadline_iso": "2026-08-31",
}

DEMO_NOTICE = (
    "DEMONSTRATION / TEST ONLY: this reminder and its deadline are a test/demo "
    "for the Day 6 outbound-call challenge. They are NOT a verified live "
    "government deadline. Always treat them as a demonstration, and tell the "
    "caller to verify current details on the official scheme page."
)


def demo() -> dict[str, object]:
    """Return a copy of the DEMO/TEST reminder the agent talks about."""
    return dict(DEMO_REMINDER)


def is_demo() -> bool:
    return bool(DEMO_REMINDER.get("is_demo"))


def scheme_name() -> str:
    return str(DEMO_REMINDER.get("scheme_name", ""))


def deadline_human() -> str:
    return str(DEMO_REMINDER.get("deadline", ""))


def status_label() -> str:
    """'demo' when the deadline is fictional, else 'preliminary'."""
    return "demo" if is_demo() else "preliminary"
