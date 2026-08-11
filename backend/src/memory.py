"""Persistent caller memory backed by MongoDB (Day 4).

The agent never talks to MongoDB directly. It only reaches this module through the
`lookup_user` / `save_user_memory` agent tools in `agent.py`.

Top-level helpers are deliberately defensive:
- If `MONGODB_URI` is missing or the database is unreachable, every operation
  fails closed (returns `None` / `False`) instead of raising, so the voice agent
  keeps working even when memory is unavailable.
- Only non-sensitive caller facts are ever persisted. Never store bank account
  numbers, UPI IDs, OTPs, PINs, card details, or Aadhaar/PAN numbers.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo.server_api import ServerApi

logger = logging.getLogger("agent")

MONGODB_URI = os.environ.get("MONGODB_URI", "")
DATABASE_NAME = "rupeegpt"
COLLECTION_NAME = "caller_profiles"


class _MongoStore:
    def __init__(self) -> None:
        self._uri = MONGODB_URI.strip()
        self._client: MongoClient | None = None
        self._collection: Any | None = None
        self._failed = False

    def _get_collection(self) -> Any | None:
        if self._collection is not None:
            return self._collection
        if self._failed or not self._uri:
            return None

        try:
            server_api = ServerApi("1")
            client = MongoClient(
                self._uri, server_api=server_api, serverSelectionTimeoutMS=3000
            )
            client.admin.command("ping")
            self._client = client
            self._collection = client[DATABASE_NAME][COLLECTION_NAME]
            return self._collection
        except PyMongoError as e:
            logger.warning("MongoDB is unavailable; caller memory disabled: %s", e)
            self._failed = True
            self._client = None
            return None

    def is_available(self) -> bool:
        return self._get_collection() is not None

    def lookup_user(self, user_id: str) -> dict[str, Any] | None:
        """Return the caller profile document, or None if it doesn't exist."""
        if not user_id:
            return None
        collection = self._get_collection()
        if collection is None:
            return None
        try:
            return collection.find_one({"user_id": user_id}, {"_id": 0}) or None
        except PyMongoError as e:
            logger.warning("lookup_user failed for %s: %s", user_id, e)
            return None

    def save_user_memory(
        self,
        user_id: str,
        *,
        name: str | None = None,
        language_preference: str | None = None,
        facts: dict[str, Any] | None = None,
    ) -> bool:
        """Upsert a caller profile, merging new facts with any existing ones.

        Uses an upsert on `user_id` so a returning caller is never duplicated.
        `last_interaction` is refreshed on every successful save.
        """
        if not user_id:
            return False
        collection = self._get_collection()
        if collection is None:
            return False

        update: dict[str, Any] = {
            "user_id": user_id,
            "last_interaction": datetime.now(timezone.utc),
        }
        if name:
            update["name"] = name
        if language_preference:
            update["language_preference"] = language_preference
        if facts:
            try:
                existing = collection.find_one(
                    {"user_id": user_id}, {"facts": 1, "_id": 0}
                )
            except PyMongoError as e:
                logger.warning("save_user_memory lookup failed for %s: %s", user_id, e)
                existing = None
            current_facts = existing.get("facts", {}) if existing else {}
            if not isinstance(current_facts, dict):
                current_facts = {}
            merged_facts = _merge_facts(current_facts, facts)
            # Keep the saved profile in the standard shape from the spec so
            # returning callers always expose these keys.
            merged_facts.setdefault("schemes_checked", [])
            merged_facts.setdefault("eligibility_answers", {})
            update["facts"] = merged_facts

        try:
            collection.update_one({"user_id": user_id}, {"$set": update}, upsert=True)
            return True
        except PyMongoError as e:
            logger.warning("save_user_memory failed for %s: %s", user_id, e)
            return False


def _merge_facts(base: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge `new` facts into `base`, returning a new combined dict.

    Lists (e.g. `schemes_checked`) are unioned without duplicates; dicts are
    merged recursively; scalars overwrite.
    """
    merged: dict[str, Any] = {}
    for key, value in base.items():
        merged[key] = list(value) if isinstance(value, list) else value

    for key, value in new.items():
        if value is None:
            continue
        if isinstance(value, list):
            existing = merged.get(key, [])
            if not isinstance(existing, list):
                existing = []
            merged[key] = existing + [item for item in value if item not in existing]
        elif isinstance(value, dict):
            existing = merged.get(key, {})
            if not isinstance(existing, dict):
                existing = {}
            merged[key] = _merge_facts(existing, value)
        else:
            merged[key] = value

    return merged


_client = _MongoStore()


def lookup_user(user_id: str) -> dict[str, Any] | None:
    """Find a caller profile by user_id (None when missing or MongoDB is down)."""
    return _client.lookup_user(user_id)


def save_user_memory(
    user_id: str,
    *,
    name: str | None = None,
    language_preference: str | None = None,
    facts: dict[str, Any] | None = None,
) -> bool:
    """Create or update a caller profile using an upsert with merged facts."""
    return _client.save_user_memory(
        user_id,
        name=name,
        language_preference=language_preference,
        facts=facts,
    )


def memory_available() -> bool:
    """Whether MongoDB is currently reachable (used by logging/testing)."""
    return _client.is_available()
