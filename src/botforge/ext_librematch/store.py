"""libre:match stats store — the provider's OWN history database (#404 T1).

The provider is the source of truth of its perimeter: the RAW match
documents and the per-account status live HERE, in the provider's
namespaced collections — never filtered at ingestion (store first,
exploit later), never read by another service's process.

Collections (all under the ``librematch:`` namespace):

- ``librematch:matches`` — one document per (match, leaderboard): the
  raw upstream payload plus the exploited projection (participants,
  elo deltas, outcome);
- ``librematch:accounts`` — one document per known account: the elo
  status per leaderboard (current + MAX) and the sync freshness;
- ``librematch:bindings`` — the profile -> platform-user mapping pushed
  by the core through ``UpdateSubscriptions`` (the per-USER
  unification's key).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("botforge.ext_librematch.store")

MATCHES_COLLECTION = "librematch:matches"
ACCOUNTS_COLLECTION = "librematch:accounts"
BINDINGS_COLLECTION = "librematch:bindings"

DEFAULT_HISTORY_LIMIT = 50


class LibrematchStore:
    """The provider's own persistence seam over async MongoDB."""

    def __init__(self, database: Any) -> None:
        """Wrap the provider's async Mongo database."""
        self._db = database

    def _matches(self) -> Any:
        """Return the raw match documents collection."""
        return self._db[MATCHES_COLLECTION]

    def _accounts(self) -> Any:
        """Return the per-account status collection."""
        return self._db[ACCOUNTS_COLLECTION]

    def _bindings(self) -> Any:
        """Return the profile -> user mapping collection."""
        return self._db[BINDINGS_COLLECTION]

    async def upsert_matches(self, documents: list[dict[str, Any]]) -> int:
        """Insert or replace the raw match documents; return the new count.

        The document ``_id`` is ``<match_id>:<leaderboard_id>`` — the
        upstream may list the same match id under several leaderboards.
        """
        count = 0
        for doc in documents:
            await self._matches().replace_one({"_id": doc["_id"]}, doc, upsert=True)
            count += 1
        return count

    async def stored_match_ids(self, ids: list[str]) -> set[str]:
        """Return which of the given match ids are already stored."""
        if not ids:
            return set()
        cursor = self._matches().find({"_id": {"$in": list(ids)}}, {"_id": 1})
        return {str(doc["_id"]) async for doc in cursor}

    async def insert_matches_new_only(self, documents: list[dict[str, Any]]) -> int:
        """Insert the matches that do not exist yet; return the inserted count.

        A FINISHED match is immutable — an already stored document is
        never rewritten (the smart-sync rule of #404 T4: the incremental
        sync only ever APPENDS the new games).
        """
        ids = [str(doc["_id"]) for doc in documents]
        stored = await self.stored_match_ids(ids)
        inserted = 0
        for doc in documents:
            if str(doc["_id"]) in stored:
                continue
            try:
                await self._matches().insert_one(doc)
                inserted += 1
            except Exception:
                # a concurrent insert of the same id: the match is
                # already stored — immutability wins, not the error
                logger.debug("match %s already stored concurrently", doc.get("_id"))
        return inserted

    async def count_matches_of_profile(self, profile_id: str) -> int:
        """Count the stored matches of one profile (deep-vs-quick preset)."""
        return int(await self._matches().count_documents({"profile_ids": str(profile_id)}))

    async def find_incomplete_docs(self, profile_id: str, limit: int = 100) -> list[dict[str, Any]]:
        """Return the profile's stored captures of an OLDER era.

        The repair is era-gated (the merlin loops of 2026-11-21: any
        content-based marker midjudged and the deep refetch looped):
        a capture written before the current era \u2014 or by an older
        revision (no era field at all) \u2014 repairs ONCE, the rebuilt
        capture carries the current era and never candidates again,
        whatever the upstream genuinely failed to carry.
        """
        from botforge.ext_librematch.history import CAPTURE_ERA

        marker = {
            "$or": [
                {"capture_era": {"$exists": False}},
                {"capture_era": {"$lt": CAPTURE_ERA}},
            ]
        }
        cursor = self._matches().find({"profile_ids": str(profile_id), **marker})
        return [dict(doc) async for doc in cursor][:limit]

    async def delete_matches(self, doc_ids: list[str]) -> int:
        """Delete stored captures by their document ids (the repair)."""
        removed = 0
        for doc_id in doc_ids:
            if await self._matches().delete_one({"_id": doc_id}) and True:
                removed += 1
        return removed

    async def count_incomplete_matches(self, profile_id: str) -> int:
        """Count the profile's stored matches whose capture is incomplete.

        A document stored by an older revision may carry a raw payload
        WITHOUT the members/description fields (incomplete
        captures) — the heal re-reads the raw, so it cannot invent
        them: those documents need a fresh upstream fetch that REPLACES the
        capture. An empty (or absent) ``players`` list is the marker.
        """
        return len(await self.find_incomplete_docs(profile_id))

    async def find_matches(
        self,
        profile_ids: list[str],
        limit: int = 0,
        since_s: int = 0,
        leaderboard_id: str = "",
    ) -> list[dict[str, Any]]:
        """Query the stored history: matches of the profiles, newest first.

        An empty ``profile_ids`` means every known account's matches.
        """
        query: dict[str, Any] = {}
        if profile_ids:
            query["profile_ids"] = {"$in": [str(p) for p in profile_ids]}
        if since_s > 0:
            query["finished_at"] = {"$gte": since_s}
        if leaderboard_id:
            query["leaderboard_id"] = str(leaderboard_id)
        cursor = self._matches().find(query)
        cursor = cursor.sort("finished_at", -1)
        if limit > 0:
            cursor = cursor.limit(limit)
        return [dict(doc) async for doc in cursor]

    async def find_undecoded_matches(
        self, profile_ids: list[str], limit: int = 25
    ) -> list[dict[str, Any]]:
        """List the stored matches whose encoded fields are not decoded yet.

        The decode step (T2) exploits the stored documents AFTER the
        ingestion — this is its work queue, newest first.
        """
        query: dict[str, Any] = {"options_json": ""}
        if profile_ids:
            query["profile_ids"] = {"$in": [str(p) for p in profile_ids]}
        cursor = self._matches().find(query)
        cursor = cursor.sort("finished_at", -1)
        return [dict(doc) async for doc in cursor.limit(limit)]

    async def update_match_fields(self, doc_id: str, fields: dict[str, Any]) -> None:
        """Patch the projection fields of one stored match document."""
        await self._matches().update_one({"_id": doc_id}, {"$set": fields})

    async def count_matches_since(self, profile_ids: list[str], since_s: int) -> int:
        """Count the matches of the profiles finished after ``since_s``."""
        query: dict[str, Any] = {"finished_at": {"$gte": since_s}}
        if profile_ids:
            query["profile_ids"] = {"$in": [str(p) for p in profile_ids]}
        return int(await self._matches().count_documents(query))

    async def upsert_account(self, document: dict[str, Any]) -> None:
        """Insert or replace one account's status document."""
        await self._accounts().replace_one({"_id": document["_id"]}, document, upsert=True)

    async def find_accounts(self, profile_ids: list[str]) -> list[dict[str, Any]]:
        """Return the status documents of the accounts (missing ones absent)."""
        if not profile_ids:
            return []
        cursor = self._accounts().find({"_id": {"$in": [str(p) for p in profile_ids]}})
        return [dict(doc) async for doc in cursor]

    async def list_known_profiles(self) -> list[str]:
        """List every account the store has a status or binding for."""
        cursor = self._accounts().find({}, {"_id": 1})
        profiles = {str(doc["_id"]) async for doc in cursor}
        cursor = self._bindings().find({}, {"_id": 1})
        profiles |= {str(doc["_id"]) async for doc in cursor}
        return sorted(profiles)

    async def upsert_bindings(self, profile_ids: list[str], user_ids: list[str]) -> int:
        """Record the profile -> user mapping pushed by the core.

        ``user_ids`` is parallel to ``profile_ids``; an empty owner
        entry keeps whatever mapping is already stored (the core may
        push a list without owners — the realtime reconciliation).
        """
        count = 0
        for profile_id, user_id in zip(
            [str(p) for p in profile_ids],
            [str(u) for u in user_ids],
            strict=False,
        ):
            if not user_id:
                count += 1
                continue
            await self._bindings().replace_one(
                {"_id": profile_id},
                {"_id": profile_id, "user_id": user_id},
                upsert=True,
            )
            count += 1
        return count

    async def find_profiles_of_user(self, user_id: str) -> list[str]:
        """Return the platform user's known accounts (the unification's key)."""
        cursor = self._bindings().find({"user_id": str(user_id)}, {"_id": 1})
        profiles = [str(doc["_id"]) async for doc in cursor]
        return sorted(profiles)

    async def find_user_of_profile(self, profile_id: str) -> str:
        """Return the account's platform owner; empty when unknown."""
        doc = await self._bindings().find_one({"_id": str(profile_id)})
        return str(doc.get("user_id", "")) if doc is not None else ""
