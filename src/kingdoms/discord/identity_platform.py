"""Async MongoDB adapter for the IdentityService persistence seam.

The identity database is intentionally narrow: the home profile only
needs to read one user document and persist a renamed display name, so
the adapter exposes exactly the ``IdentityDatabase`` protocol surface.
"""

from __future__ import annotations

import logging
from typing import Any

from kingdoms.core.models.user import UserModel
from kingdoms.core.services.identity import IDENTITY_COLLECTION, USERS_COLLECTION

logger = logging.getLogger("kingdoms.discord.identity_platform")


class MongoIdentityDatabase:
    """Async MongoDB adapter for the IdentityService persistence seam."""

    def __init__(self, database: Any) -> None:
        """Wrap an async MongoDB database (``get_async_database``)."""
        self._database = database

    async def find_identity(self, platform: str, platform_user_id: str) -> str | None:
        """Return the internal user_id bound to a platform account; None when unbound."""
        doc = await self._database[IDENTITY_COLLECTION].find_one(
            {"platform": platform, "platform_user_id": platform_user_id}
        )
        return str(doc["user_id"]) if doc is not None else None

    async def bind_identity(self, platform: str, platform_user_id: str, user_id: str) -> None:
        """Persist the (platform, account) → user_id binding (upsert)."""
        await self._database[IDENTITY_COLLECTION].update_one(
            {"platform": platform, "platform_user_id": platform_user_id},
            {"$set": {"user_id": user_id}},
            upsert=True,
        )

    async def unbind_identity(self, platform: str, platform_user_id: str) -> bool:
        """Remove a binding; True when one was removed."""
        result = await self._database[IDENTITY_COLLECTION].delete_one(
            {"platform": platform, "platform_user_id": platform_user_id}
        )
        return bool(result.deleted_count > 0)

    async def find_user(self, user_id: str) -> UserModel | None:
        """Return the internal user document; None when absent."""
        doc = await self._database[USERS_COLLECTION].find_one({"_id": user_id})
        if doc is None:
            return None
        return UserModel.model_validate(dict(doc))

    async def find_many_users(self, user_ids: list[str]) -> list[UserModel]:
        """Return the existing user documents for a batch of ids (ONE read).

        The players panel's roster read: the per-user find_one loop was
        one Mongo round-trip per enrolled member — the panel's real
        bottleneck (owner direction: the panel must be immediate).
        """
        if not user_ids:
            return []
        docs = []
        cursor = self._database[USERS_COLLECTION].find({"_id": {"$in": user_ids}})
        async for doc in cursor:
            try:
                docs.append(UserModel.model_validate(dict(doc)))
            except Exception:
                logger.debug("a batched user doc failed validation — skipped", exc_info=True)
        return docs

    async def upsert_user(self, user: UserModel) -> None:
        """Insert or replace the user document."""
        await self._database[USERS_COLLECTION].replace_one({"_id": user.id}, user.to_mongo(), upsert=True)
