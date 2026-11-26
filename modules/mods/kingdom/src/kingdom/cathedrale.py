"""The Lieu Sacrée / Cathédrale service (lieu-sacree-v1, porté Affaire 36).

Au palier Cathédrale, le Roi paie 3 ⚙️ et consacre un de ses
territoires : un chantier cathédrale de 72h y est posé. Tant qu'il
court, le territoire résiste à TOUTE technologie adverse mais reste
attaquable en CLASSIQUE. Un chantier qui survit rend le territoire
SACRÉ à vie : immunisé contre tout.

Harmonisation (Drasah : le générique vit dans le moteur, le cog ne
garde que le spécifique) : ce service est le premier APPELANT des
immunités déjà portées (models.TerritoryModel.sacred /
is_chantier_at / is_tech_protected_at + les gardes d'attacks.py et
d'economy.py) — avant l'Affaire 36, personne n'écrivait
``cathedral_until``.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from botforge.mods.kingdom.admin_debug import bypass_guard
from botforge.mods.kingdom.game_clock import game_now
from botforge.mods.kingdom.models import KingdomModel, TerritoryModel
from botforge.mods.kingdom.service import KING_ROLE, KingdomModError, NoSeasonError

logger = logging.getLogger("kingdom.cathedrals")


class CathedralError(KingdomModError):
    """Base of the Lieu Sacrée errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)


class CathedralKingOnlyError(CathedralError):
    """Raised when a non-King tries to consecrate."""


class CathedralTierError(CathedralError):
    """Raised below the Cathédrale palier."""


class CathedralNotFoundError(CathedralError):
    """Raised for a territory outside the King's kingdom."""


class CathedralActiveError(CathedralError):
    """Raised when the kingdom already runs a chantier or the map is sacred."""


class CathedralInsufficientTechError(CathedralError):
    """Raised when the treasury cannot pay the consecration."""


class CathedralService:
    """Own the Lieu Sacrée consecration and its 72h verdict.

    Built over the mod's OWN seams only (store / config / kingdoms /
    territories) — no Discord here, the cog stays the only UI layer.
    """

    def __init__(self, store: Any, config: Any, kingdoms: Any, territories: Any) -> None:
        self._store = store
        self._config = config
        self._kingdoms = kingdoms
        self._territories = territories

    # ------------------------------------------------------------------
    # Consecration (King only)
    # ------------------------------------------------------------------

    async def _kingdom_by_id(self, kingdom_id: str) -> KingdomModel:
        return next(k for k in await self._kingdoms.kingdoms() if str(k.id) == kingdom_id)

    async def _owned_territory(self, kingdom_id: str, map_key: str) -> TerritoryModel | None:
        """The kingdom's territory of a map key, None when foreign."""
        return next(
            (
                item
                for item in await self._territories.territories()
                if item.map_key == map_key and str(item.owner_kingdom_id) == kingdom_id
            ),
            None,
        )

    def _tier_ok(self, kingdom: KingdomModel) -> bool:
        tiers = getattr(self._config.parish, "tiers", ()) or ()
        return int(getattr(kingdom, "parish_tier", 1) or 1) >= len(tiers)

    async def consecrate(
        self,
        player_id: str,
        map_key: str,
        *,
        now: datetime | None = None,
    ) -> TerritoryModel:
        """Set a cathedral chantier on the King's territory (lieu-sacree-v1).

        The King pays the consecration price (3 ⚙️ par défaut, donnée de
        config, jamais codée en dur) ; le territoire porte le chantier
        72h et résiste à toute technologie adverse jusqu'au verdict.
        """
        timestamp = now or game_now()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        season = await self._kingdoms.current_season()
        if season is None or getattr(season, "finished", False):
            raise NoSeasonError("no season runs the Lieu Sacrée consecration")
        lord = next(
            (item for item in await self._kingdoms.lords() if str(item.id) == player_id),
            None,
        )
        if lord is None or lord.role is not KING_ROLE or not lord.kingdom_id:
            raise CathedralKingOnlyError("only the King consecrates a Lieu Sacrée")
        kingdom = await self._kingdom_by_id(str(lord.kingdom_id))
        territory = await self._owned_territory(str(lord.kingdom_id), map_key)
        if territory is None:
            raise CathedralNotFoundError("the territory belongs to no land of this kingdom")
        if not self._tier_ok(kingdom) and not bypass_guard(
            f"cathedral tier of {kingdom.name} (parish tier {kingdom.parish_tier})"
        ):
            raise CathedralTierError("the kingdom did not reach the Cathédrale palier")
        if territory.sacred or territory.is_chantier_at(timestamp):
            raise CathedralActiveError("the territory already carries a Lieu Sacrée")
        others = await self.consecratable(str(lord.kingdom_id), now=timestamp)
        if map_key not in {item.map_key for item in others}:
            raise CathedralActiveError("the kingdom already runs a cathedral chantier")
        cost = int(getattr(self._config.parish, "cathedral_cost", 3) or 0)
        if int(kingdom.tech_points_bank) < cost and not bypass_guard(
            f"cathedral consecration cost {cost} of {kingdom.name} "
            f"(bank {kingdom.tech_points_bank})"
        ):
            raise CathedralInsufficientTechError("the treasury cannot pay the consecration")
        # The bypassed path pays what the treasury holds (never negative).
        paid = min(int(kingdom.tech_points_bank), cost)
        kingdom.tech_points_bank = int(kingdom.tech_points_bank) - paid
        await self._store.upsert_kingdom(kingdom.to_mongo())
        chantier_hours = int(getattr(self._config.parish, "cathedral_chantier_hours", 72) or 72)
        territory.cathedral_until = timestamp + timedelta(hours=chantier_hours)
        await self._store.upsert_territory(territory.to_mongo())
        logger.info(
            "kingdoms: %s consecrated the Lieu Sacrée on %s (-%d tech)",
            lord.kingdom_id,
            map_key,
            cost,
        )
        return territory

    async def consecratable(
        self,
        kingdom_id: str,
        *,
        now: datetime | None = None,
    ) -> list[TerritoryModel]:
        """The kingdom's territories open to a consecration.

        A territory already SACRED or carrying a chantier is never
        consecratable ; when the kingdom already runs a chantier
        elsewhere, NOTHING is (one Lieu Sacrée per kingdom).
        """
        timestamp = now or game_now()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        owned = [
            item
            for item in await self._territories.territories()
            if str(item.owner_kingdom_id) == kingdom_id
        ]
        if any(item.sacred or item.is_chantier_at(timestamp) for item in owned):
            return []
        return [item for item in owned if not item.sacred]

    # ------------------------------------------------------------------
    # The 72h verdict
    # ------------------------------------------------------------------

    async def resolve_due(
        self,
        *,
        now: datetime | None = None,
    ) -> list[TerritoryModel]:
        """Turn every expired chantier into a SACRED territory, forever.

        The tick is idempotent : replaying it after the verdict changes
        nothing (the chantier is already consumed).
        """
        timestamp = now or game_now()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        season = await self._kingdoms.current_season()
        if season is None or getattr(season, "finished", False):
            return []
        consecrated: list[TerritoryModel] = []
        for territory in await self._territories.territories():
            if not territory.sacred and territory.is_chantier_at(timestamp):
                continue  # the chantier still runs
            if territory.sacred or territory.cathedral_until is None:
                continue  # nothing pending
            if territory.cathedral_until > timestamp:
                continue
            territory.sacred = True
            territory.cathedral_until = None
            await self._store.upsert_territory(territory.to_mongo())
            consecrated.append(territory)
            logger.info(
                "kingdoms: the Lieu Sacrée of %s survived — SACRED forever",
                territory.map_key,
            )
        return consecrated
