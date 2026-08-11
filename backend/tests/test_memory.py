"""Unit tests for the Day 4 memory store.

These run without a real MongoDB server by pointing the store at an in-memory
FakeCollection (see conftest.py).
"""

from datetime import datetime

from conftest import FakeCollection

import memory


def _stored(collection: FakeCollection, user_id: str) -> dict:
    return collection.docs()[user_id]


def test_defaults_create_is_disabled_when_no_database() -> None:
    assert memory.lookup_user("") is None
    assert memory.save_user_memory("someone", name="Rahul") is False


def test_save_creates_new_caller_profile(memory_collection: FakeCollection) -> None:
    saved = memory.save_user_memory(
        "u-1",
        name="Rahul",
        language_preference="Hinglish",
        facts={"schemes_checked": ["PM Jan Dhan Yojana"]},
    )
    assert saved is True

    doc = _stored(memory_collection, "u-1")
    assert doc["user_id"] == "u-1"
    assert doc["name"] == "Rahul"
    assert doc["language_preference"] == "Hinglish"
    assert doc["facts"]["schemes_checked"] == ["PM Jan Dhan Yojana"]
    assert isinstance(doc["last_interaction"], datetime)


def test_upsert_never_duplicates_a_caller(memory_collection: FakeCollection) -> None:
    memory.save_user_memory("u-1", name="Rahul")
    memory.save_user_memory("u-1", name="Rahul")

    assert len(memory_collection.docs()) == 1


def test_save_merges_facts_instead_of_overwriting(
    memory_collection: FakeCollection,
) -> None:
    memory.save_user_memory(
        "u-1",
        name="Rahul",
        facts={"schemes_checked": ["PM Jan Dhan Yojana"]},
    )
    memory.save_user_memory(
        "u-1",
        facts={
            "schemes_checked": ["Sukanya Samriddhi Yojana"],
            "eligibility_answers": {"rural": True},
        },
    )

    doc = _stored(memory_collection, "u-1")
    assert doc["facts"]["schemes_checked"] == [
        "PM Jan Dhan Yojana",
        "Sukanya Samriddhi Yojana",
    ]
    assert doc["facts"]["eligibility_answers"] == {"rural": True}
    # Fields omitted on the second save are preserved, not wiped.
    assert doc["name"] == "Rahul"


def test_last_interaction_refreshed_on_each_save(
    memory_collection: FakeCollection,
) -> None:
    memory.save_user_memory("u-1", name="Rahul")
    first = _stored(memory_collection, "u-1")["last_interaction"]

    memory.save_user_memory("u-1", language_preference="Hindi")
    second = _stored(memory_collection, "u-1")["last_interaction"]

    assert isinstance(first, datetime)
    assert isinstance(second, datetime)
    assert second >= first


def test_lookup_returns_saved_profile(memory_collection: FakeCollection) -> None:
    memory.save_user_memory("u-1", name="Rahul", language_preference="Hinglish")
    profile = memory.lookup_user("u-1")

    assert profile is not None
    assert profile["name"] == "Rahul"
    assert profile["language_preference"] == "Hinglish"


def test_empty_user_id_is_ignored(memory_collection: FakeCollection) -> None:
    assert memory.save_user_memory("", name="Rahul") is False
    assert memory.lookup_user("") is None
    assert memory_collection.docs() == {}
