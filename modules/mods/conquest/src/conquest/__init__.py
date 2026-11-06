"""Conquest — the seasonal example mod (kingdoms-services#267 chantier 4).

The whole parcours comes from the platform's generic surfaces
(``kingdoms.discord.mod_surfaces``): the /conquest player panel (apply
against the active season, unregister, list the enrolled), the admin
channel validation, the admin panel (suspend/resume, create/start/end
the season, the section's Synchroniser). This package is the one-line
wiring — everything else is declaration data (``mod.yaml``).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdoms.mods.conquest")

MOD_NAME = "conquest"
GAME_KEY = "aoe2"


def register(bot: Any, config: Any) -> None:
    """Wire the generic surfaces onto the bot (idempotent, boot-safe)."""
    del config
    from kingdoms.discord.mod_surfaces import register_mod_surfaces

    definition = None
    registry = getattr(bot, "registry", None)
    if registry is not None:
        definition = registry.get(MOD_NAME)
    settings = dict(getattr(definition, "settings", {}) or {}) if definition is not None else {}
    register_mod_surfaces(
        bot,
        MOD_NAME,
        seasonal=True,
        settings=settings,
        game_key=GAME_KEY,
        admin_channel_key="admin",
    )
