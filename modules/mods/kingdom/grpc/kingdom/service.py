"""The kingdom mod's service (§7 grpc): its data, its collections.

Implements the contract (contract.py). Never imports Discord — the cog
is the mod's only Discord layer.

The engine stack (P4.1a: KingdomService + TerritoryService +
AttackService over the mod's namespaced Mongo storage) builds LAZILY on
first use: an unwired boot (no Mongo) leaves ``stack()`` at None and
every cog surface degrades to its « service indisponible » note.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .contract import KingdomStack as KingdomStackContract
from .contract import KingdomService as KingdomContract

logger = logging.getLogger("kingdom.service")


class _KingdomStackImpl(KingdomStackContract):
    """The wired engine stack — built once, cached here."""

    def __init__(self, store: Any, config: Any) -> None:
        from botforge.mods.kingdom.service import KingdomService as EnrollmentService
        from botforge.mods.kingdom.territories import TerritoryService
        from botforge.mods.kingdom.attacks import AttackService
        from botforge.mods.kingdom.diplomacy import DiplomacyService
        from botforge.mods.kingdom.economy import EconomyService
        from botforge.mods.kingdom.events import EventService
        from botforge.mods.kingdom.ffa_exploration import FFAExplorationService
        from botforge.mods.kingdom.mercenary import MercenaryService
        from botforge.mods.kingdom.tavern import TavernService

        self._store = store
        self._config = config
        self._kingdoms = EnrollmentService(store, config)
        self._territories = TerritoryService(store, config, self._kingdoms)
        # chef-mercenaire-v1 T2c: the pick & ban consumes the LIVE held
        # civilization through the seam (the service is built first).
        self._mercenary = MercenaryService(store, config, self._kingdoms)
        self._attacks = AttackService(
            store, config, self._kingdoms, self._territories, mercenary=self._mercenary
        )
        self._diplomacy = DiplomacyService(store, config, self._kingdoms, self._territories)
        self._events = EventService(
            store, config, self._kingdoms, self._territories, self._attacks, self._diplomacy
        )
        self._economy = EconomyService(
            store, config, self._kingdoms, self._territories, self._attacks
        )
        self._ffa = FFAExplorationService(
            store, config, self._kingdoms, self._events
        )
        self._tavern = TavernService(store, config, self._kingdoms)

    @property
    def kingdoms(self) -> Any:
        return self._kingdoms

    @property
    def territories(self) -> Any:
        return self._territories

    @property
    def attacks(self) -> Any:
        return self._attacks

    @property
    def diplomacy(self) -> Any:
        return self._diplomacy

    @property
    def events(self) -> Any:
        return self._events

    @property
    def economy(self) -> Any:
        return self._economy

    @property
    def tavern(self) -> Any:
        return self._tavern

    @property
    def mercenary(self) -> Any:
        return self._mercenary

    @property
    def ffa(self) -> Any:
        return self._ffa

    @property
    def config(self) -> Any:
        return self._config


class KingdomServiceImpl(KingdomContract):
    """The kingdom mod's service implementation (in-process today)."""

    def __init__(self) -> None:
        self._stack: _KingdomStackImpl | None = None

    async def status(self, guild_id: str) -> dict[str, Any]:
        """Return the mod's status for the guild (the cog renders it)."""
        stack = self.stack()
        state = "wired"
        if stack is None:
            return {"mod": "kingdom", "guild": guild_id, "state": "no-storage"}
        try:
            season = await stack.kingdoms.current_season()
            state = str(getattr(season, "phase", "running")) if season else "none"
        except Exception:
            logger.warning("kingdom: status season probe failed", exc_info=True)
            state = "error"
        return {"mod": "kingdom", "guild": guild_id, "state": state}

    def stack(self) -> KingdomStackContract | None:
        """Build (once) or return the engine stack; None without Mongo."""
        if self._stack is not None:
            return self._stack
        try:
            from botforge.core.models.db import get_async_database
            from botforge.core.services.mod_storage import ModStorage

            database = get_async_database()
        except Exception:
            logger.warning("kingdom: no database wired — engine stack unavailable")
            return None
        from botforge.mods.kingdom.config import load_season_config
        from botforge.mods.kingdom.storage import MongoKingdomStore

        conf_dir = Path(__file__).resolve().parents[3] / "conf"
        config = load_season_config(conf_dir)
        store = MongoKingdomStore(ModStorage(database, "kingdom"))
        self._stack = _KingdomStackImpl(store, config)
        logger.info("kingdom: engine stack wired (conf=%s)", conf_dir)
        return self._stack
