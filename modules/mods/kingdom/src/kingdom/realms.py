"""The PERSISTENT realm shell (royaume-persistant-v1, Drasah 20/11).

The engine's KingdomModel is a SEASON entity (it carries a season_id
and dies in the season wipe). The realm — name, Roi, members,
presentation, salons — is **persistent**: it survives season ends, and
a kingdom only ENTERS a season by receiving its draft starter (the
act of entry, never the creation).

This module is the persistent shell's model + store + service:

- ``RealmShellModel``: the realm's identity, ownership and Discord ids
- the realm CRUD rides the mod's OWN store (the KingdomStore
  protocol / MongoKingdomStore): ``upsert_realm`` / ``find_realms`` /
  ``delete_realm`` — and the season wipe NEVER lists the collection
- ``RealmService``: found / leave / crown-transfer / presentation /
  join-request — the season engagement itself stays with the engine
  (tranche 2 wires the draft starter distribution).

Data rules (#369): the salons, palace text and history are DATA, never
hardcoded; the service owns the rules the cog consumes via ``wiring()``.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger("kingdom.realms")

# The shell collection — namespaced by the mod's ModStorage. The
# season wipe (storage.wipe_season_data) MUST NOT list it: a realm
# outlives every season (the docstring there says why).
REALMS_COLLECTION = "kingdoms_realms"

NAME_MIN = 2
NAME_MAX = 45


class RealmError(Exception):
    """One realm rule refused the operation (functional message)."""

    def __init__(self, message: str, **context: str) -> None:
        super().__init__(message)
        self.message = message
        self.context = context


def realm_slug(name: str) -> str:
    """Flatten a realm name to a stable slug (adoption anchor).

    Accents fold to their base letters (« Château Noir » →
    « chateau-noir ») — the readable slug is the realm's anchor key.
    """
    import unicodedata

    folded = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    return text or "royaume"


class RealmShellModel(BaseModel):
    """The persistent realm — identity, ownership, Discord habitat."""

    model_config = ConfigDict(strict=False)

    id: str = Field(alias="_id")
    name: str
    slug: str
    king_id: str
    king_name: str
    member_ids: list[str] = Field(default_factory=list)
    founded_at: int = Field(default_factory=lambda: int(time.time()))
    presentation: str = ""
    """「📝 Présentation」 — written by the Roi ONLY, read by everyone,
    persistent with the realm; RESERVED to power the « Joindre un
    Royaume » showcase (royaume-persistant-v1)."""
    discord: dict[str, Any] = Field(default_factory=dict)
    """The realm's Discord habitat ids by key: ``category``, ``hub``
    (🏰 Le royaume), ``discussions``, ``territory``, ``alliances``."""
    season_history: list[dict[str, Any]] = Field(default_factory=list)
    """🏆 Palmarès — one ``{"season", "note", "at"}`` line per past
    season the realm played (filled at season end, tranche 2)."""
    join_request: dict[str, Any] | None = None
    """The pending « s'inscrire à la saison » request from the Roi:
    ``{"season_id", "requested_at"}`` — an admin accepts or refuses."""
    engagement: dict[str, Any] | None = None
    """The LIVE season link shell ↔ engine (t2a, Drasah 20/11):
    ``{"season_id", "kingdom_id", "engaged_at"}`` set by the admin's
    acceptance (the draft starter IS the act of entry), cleared at
    season end — a realm out of season carries None."""
    archived_at: int = 0
    """📦 The archive stamp (ejection-archive-v1, Drasah 22/11): 0 = the
    realm lives (vivant ou dormant), anything else = ARCHIVED — out of
    the game (SAS, lists, habitat Discord demolished), data KEPT for a
    restore, the name still RESERVED. The restore zeroes it back; the
    definitive deletion drops the shell (and frees the name)."""

    def to_mongo(self) -> dict[str, Any]:
        """The stored document (Mongo lives on ``_id``)."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "RealmShellModel":
        return cls.model_validate(document)


class RealmStore(Protocol):
    """The realm shell's persistence seam (protocol like KingdomStore)."""

    async def upsert_realm(self, document: dict[str, Any]) -> None: ...

    async def find_realms(self) -> list[dict[str, Any]]: ...

    async def delete_realm(self, realm_id: str) -> None: ...


class RealmService:
    """The persistent realm's rules (found / leave / crown / write)."""

    def __init__(self, store: RealmStore) -> None:
        self._store = store

    async def _all(self) -> list[RealmShellModel]:
        return [RealmShellModel.from_mongo(doc) for doc in await self._store.find_realms()]

    async def realms(self) -> list[RealmShellModel]:
        """Every persistent realm (the cog sorts what it shows)."""
        return await self._all()

    async def realm_of_member(self, user_id: str) -> RealmShellModel | None:
        """The realm the user belongs to (member or Roi), if any."""
        for realm in await self._all():
            if user_id == realm.king_id or user_id in realm.member_ids:
                return realm
        return None

    async def realm_of_slug(self, slug: str) -> RealmShellModel | None:
        """The realm carrying this slug (adoption by flattened name)."""
        for realm in await self._all():
            if realm.slug == realm_slug(slug):
                return realm
        return None

    async def found_realm(self, player_id: str, display_name: str, name: str) -> RealmShellModel:
        """Found a persistent realm — the Roi is crowned, nobody else.

        royaume-persistant-v1: founding NEVER engages a season (the
        draft starter is the act of entry — a separate gesture).
        """
        proposed = str(name or "").strip()
        if not (NAME_MIN <= len(proposed) <= NAME_MAX):
            raise RealmError("length", name=proposed)
        if await self.realm_of_member(player_id) is not None:
            raise RealmError("already-in-realm")
        if await self.realm_of_slug(realm_slug(proposed)) is not None:
            raise RealmError("duplicate", name=proposed)
        realm = RealmShellModel(
            _id=f"realm:{realm_slug(proposed)}-{player_id}",
            name=proposed,
            slug=realm_slug(proposed),
            king_id=player_id,
            king_name=str(display_name or player_id),
            member_ids=[],
        )
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def join_realm(self, realm_id: str, member_id: str) -> RealmShellModel:
        """A player joins a persistent realm as a MEMBER (the picker's op).

        console-etats-regie-v1 (Drasah 21/11): the players' life is
        permanent — « rejoindre un royaume » without any season. A
        player belongs to ONE realm ; the Roi cannot "join" his own
        realm (he is already its crown).
        """
        realm = await self._get(realm_id)
        if getattr(realm, "archived_at", 0):
            # ejection-archive follow-up : une coquille archivée est en
            # boîte — seul le FONDATEUR la réveille (le picker propose la
            # restauration), un join direct ne ressuscite jamais rien
            raise RealmError("join-archived", realm_id=realm_id)
        if member_id == realm.king_id or member_id in realm.member_ids:
            raise RealmError("already-in-realm", realm_id=realm_id)
        if await self.realm_of_member(member_id) is not None:
            raise RealmError("already-in-realm", realm_id=realm_id)
        realm.member_ids = list(realm.member_ids) + [str(member_id)]
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def release_engagement(self, realm_id: str) -> RealmShellModel:
        """Un-bind the shell from its season (🚫 Faux départ, Drasah 21/11).

        A false start rebasculates to the season's origin state: the
        realm goes back to DORMANT and must ASK AGAIN — the re-request
        is the realm's own reconfirmation, never an admin's guess.
        """
        realm = await self._get(realm_id)
        realm.engagement = None
        realm.join_request = None
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def set_presentation(self, realm_id: str, king_id: str, text: str) -> RealmShellModel:
        """The Roi writes the realm's presentation (Roi ONLY)."""
        realm = await self._get(realm_id)
        if realm.king_id != king_id:
            raise RealmError("not-king", realm_id=realm_id)
        realm.presentation = str(text or "").strip()[:2000]
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def leave_realm(self, realm_id: str, member_id: str) -> RealmShellModel:
        """A (non-Roi) member leaves the realm — between seasons."""
        realm = await self._get(realm_id)
        if member_id == realm.king_id:
            raise RealmError("king-cannot-leave")
        if member_id not in realm.member_ids:
            raise RealmError("not-a-member")
        realm.member_ids = [m for m in realm.member_ids if m != member_id]
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def transfer_crown(self, realm_id: str, king_id: str, target_id: str) -> RealmShellModel:
        """Hand the crown to a member — the old Roi becomes a member."""
        realm = await self._get(realm_id)
        if realm.king_id != king_id:
            raise RealmError("not-king")
        if target_id not in realm.member_ids:
            raise RealmError("target-not-member")
        realm.member_ids = [m for m in realm.member_ids if m != target_id] + [king_id]
        realm.king_id = target_id
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def request_season_entry(self, realm_id: str, king_id: str, season_id: str) -> RealmShellModel:
        """The Roi manifests the realm's wish to enter the season —
        an admin accepts (draft starter) or refuses (tranche 2)."""
        realm = await self._get(realm_id)
        if realm.king_id != king_id:
            raise RealmError("not-king")
        realm.join_request = {"season_id": str(season_id), "requested_at": int(time.time())}
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def save_habitat(self, realm_id: str, ids: dict[str, Any]) -> RealmShellModel:
        """Persist the realm's Discord habitat ids (one upsert, best-effort keys)."""
        realm = await self._get(realm_id)
        merged = dict(getattr(realm, "discord", {}) or {})
        merged.update({k: v for k, v in (ids or {}).items() if v})
        realm.discord = merged
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def clear_join_request(self, realm_id: str) -> RealmShellModel:
        """Drop a stale/carried-out join request (admin decision made)."""
        realm = await self._get(realm_id)
        realm.join_request = None
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def realm_by_id(self, realm_id: str) -> RealmShellModel | None:
        """One realm by id (None when gone — the admin flow reports)."""
        for realm in await self._all():
            if realm.id == realm_id:
                return realm
        return None

    async def engage(self, realm_id: str, season_id: str, kingdom_id: str) -> RealmShellModel:
        """Bind the shell to the season's engine kingdom (t2a).

        The admin accepted the Roi's entry request: the engine kingdom
        exists (its starter draft was the act of entry), the link lands
        on the shell and the request is consumed — ONE gesture, idempotent
        on re-engage (the new kingdom id wins).
        """
        realm = await self._get(realm_id)
        realm.engagement = {
            "season_id": str(season_id),
            "kingdom_id": str(kingdom_id),
            "engaged_at": int(time.time()),
        }
        realm.join_request = None
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def _get(self, realm_id: str) -> RealmShellModel:
        for realm in await self._all():
            if realm.id == realm_id:
                return realm
        raise RealmError("unknown-realm", realm_id=realm_id)

    # ------------------------------------------------------------------
    # ejection-archive-v1 (Drasah 22/11): the archive-restore-delete
    # triplet. The ARCHIVE replaces the old « supprimer » of a dormant
    # realm — the data stays (stats, roster) and only the Discord
    # habitat goes; the restore brings the realm back (hors saison); the
    # definitive deletion frees the NAME forever. An ENGAGED realm is
    # never archivable (the engine refuses, the surface ejects first).
    # ------------------------------------------------------------------

    async def archive_realm(self, realm_id: str, reason: str = "") -> RealmShellModel:
        """Take a DORMANT realm out of play — data kept, name reserved.

        Sets ``archived_at``, drops any pending join request and any
        engagement link. An ENGAGED realm refuses (an in-season realm
        leaves through the EJECTION, never the archive).
        """
        realm = await self._get(realm_id)
        if getattr(realm, "engagement", None):
            raise RealmError("archive-engaged", realm_id=realm_id)
        if getattr(realm, "archived_at", 0):
            return realm  # idempotent — the second pass is a no-op
        realm.archived_at = int(time.time())
        realm.join_request = None
        realm.engagement = None
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def restore_realm(self, realm_id: str) -> RealmShellModel:
        """Bring an archived realm back — DORMANT (hors saison).

        Zeroes the stamp: the realm re-enters the lists, may request the
        next season's sas, and its Discord habitat rebuilds on the next
        provisioning pass. Idempotent — restoring a living realm is a
        no-op.
        """
        realm = await self._get(realm_id)
        if not getattr(realm, "archived_at", 0):
            return realm
        realm.archived_at = 0
        await self._store.upsert_realm(realm.to_mongo())
        return realm

    async def destroy_realm(self, realm_id: str) -> RealmShellModel:
        """The definitive deletion — the shell goes, the NAME is freed.

        Returns the shell for the surface's note; nothing else survives
        (the season history goes with the shell — the season archive
        keeps the played seasons' own records elsewhere).
        """
        realm = await self._get(realm_id)
        await self._store.delete_realm(str(realm.id))
        return realm

    async def dissolve_realm(self, realm_id: str, reason: str = "") -> RealmShellModel:
        """reset-joueurs-v1 (Drasah 22/11) — vider la maison, garder la boîte.

        Le geste d'outillage de test : tous les MEMBRES sortent (ils
        récupèrent leur parcours), la coquille part ARCHIVÉE (nom
        réservé, données conservées, restaurable par le fondateur ou la
        régie). Le Roi fondateur reste gravé (``king_id``) — c'est lui
        qui réveille la maison. Un royaume ENGAGÉ refuse (on ne vide
        jamais une saison vivante), un archivé est un no-op idempotent
        (déjà en boîte, déjà vide côté parcours des joueurs).
        """
        realm = await self._get(realm_id)
        if getattr(realm, "engagement", None):
            raise RealmError("archive-engaged", realm_id=realm_id)
        if getattr(realm, "archived_at", 0):
            return realm
        realm.member_ids = []
        realm.join_request = None
        realm.engagement = None
        realm.archived_at = int(time.time())
        await self._store.upsert_realm(realm.to_mongo())
        if reason:
            logger.info("kingdom: realm %s archived (%s)", realm_id, reason)
        return realm


__all__ = [
    "REALMS_COLLECTION",
    "RealmError",
    "RealmService",
    "RealmShellModel",
    "realm_slug",
]
