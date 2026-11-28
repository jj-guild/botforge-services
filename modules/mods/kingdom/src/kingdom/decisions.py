"""The admin decisions ledger (decisions-admin-v1, Drasah 25/11).

One decision = ONE document, never a hand-rolled send:

- ``type`` : ``"arbitrage"`` (a winner was designated) or
  ``"annulation"`` (the attack ends with NO winner) — the list is
  DATA, a future decision kind (season 2) is a new value, never a new
  code path;
- ``attack_id`` / ``map_key`` : the meeting context, when applicable;
- ``kingdom_ids`` : the CONCERNED kingdoms — an EMPTY list means a
  GLOBAL decision (a technical issue that touches everyone): the B2
  consultation surface shows it to every kingdom, and the in-game
  announcement reaches every discussion salon of the season;
- ``reason`` : the MANDATORY reason typed by the admin — the public
  trace is the anti-abus (Affaire 18);
- ``admin_id`` : who decided, ``announced`` : the idempotence flag of
  the in-game announcement.

#396 annonce-ready: the announcement of a decision is one template +
params — never a hand-rolled send; the day the announcement seam
lands, this doc becomes its parameters untouched.

The scope is SEASON-TRANSCENDENT: like the realm shells, the ledger is
NEVER wiped with the season data (consultation across seasons, B2).
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from .storage import KingdomStore


class DecisionService:
    """The admin decisions' persistence + reads (over the store seam)."""

    def __init__(self, store: KingdomStore) -> None:
        """Wrap the mod's namespaced storage."""
        self._store = store

    async def record_decision(
        self,
        *,
        type: str,
        kingdom_ids: list[str],
        summary: str,
        reason: str,
        admin_id: str,
        attack_id: str = "",
        map_key: str = "",
        winner_kingdom_id: str = "",
        now: float | None = None,
    ) -> dict[str, Any]:
        """Persist one decision — the reason is MANDATORY (anti-abus)."""
        cleaned_reason = str(reason or "").strip()
        if not cleaned_reason:
            raise ValueError("la raison d'une décision admin est obligatoire")
        document: dict[str, Any] = {
            "_id": f"decision:{uuid.uuid4().hex[:12]}",
            "type": str(type or "").strip() or "arbitrage",
            "attack_id": str(attack_id or ""),
            "map_key": str(map_key or ""),
            "kingdom_ids": [str(kingdom_id) for kingdom_id in (kingdom_ids or [])],
            "winner_kingdom_id": str(winner_kingdom_id or ""),
            "summary": str(summary or "").strip(),
            "reason": cleaned_reason,
            "admin_id": str(admin_id or ""),
            "created_at": int(now if now is not None else time.time()),
            "announced": False,
        }
        await self._store.upsert_decision(document)
        return document

    async def decisions(self) -> list[dict[str, Any]]:
        """Every decision, ascending by ``created_at`` (oldest first)."""
        docs = await self._store.find_decisions()
        return sorted(
            [dict(doc) for doc in docs], key=lambda doc: int(doc.get("created_at") or 0)
        )

    async def last_decisions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the N newest decisions (the drawer's history section)."""
        decisions = await self.decisions()
        return list(reversed(decisions))[: max(0, int(limit))]

    async def mark_announced(self, decision_id: str) -> None:
        """Flag one decision as announced (idempotent — the tick replays)."""
        for decision in await self.decisions():
            if decision.get("_id") == decision_id and not decision.get("announced"):
                decision["announced"] = True
                await self._store.upsert_decision(decision)

    async def to_announce(self) -> list[dict[str, Any]]:
        """Return the recorded-but-unannounced decisions (the tick replays safely)."""
        return [decision for decision in await self.decisions() if not decision.get("announced")]
