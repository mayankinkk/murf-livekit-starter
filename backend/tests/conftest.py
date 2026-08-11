"""Shared test fixtures for Day 4 caller memory.

`FakeCollection` mimics the small slice of PyMongo's API that `memory._MongoStore`
uses, so the agent tools can be exercised without a real MongoDB server.
"""

import pytest

import memory as memory_module


class FakeCollection:
    def __init__(self, docs: dict | None = None) -> None:
        self._docs = dict(docs or {})

    def find_one(
        self, filter_dict: dict, projection: dict | None = None
    ) -> dict | None:
        doc = self._docs.get(filter_dict.get("user_id"))
        if doc is None:
            return None
        if projection and projection.get("_id") == 0:
            return {k: v for k, v in doc.items() if k != "_id"}
        return dict(doc)

    def update_one(self, filter_dict: dict, update: dict, upsert: bool = False) -> None:
        user_id = filter_dict["user_id"]
        if user_id in self._docs:
            self._docs[user_id].update(update["$set"])
        elif upsert:
            self._docs[user_id] = dict(update["$set"])

    def docs(self) -> dict:
        return self._docs


@pytest.fixture
def memory_collection(monkeypatch) -> FakeCollection:
    fake = FakeCollection()
    store = memory_module._client
    monkeypatch.setattr(store, "_failed", False)
    monkeypatch.setattr(store, "_collection", fake)
    return fake
