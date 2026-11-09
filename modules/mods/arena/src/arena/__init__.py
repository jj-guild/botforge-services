"""Arena — the permanent example mod (botforge-services#267 chantier 4).

The whole parcours comes from the platform's generic surfaces
(``botforge.discord.mod_surfaces``): the /arena player panel (apply,
unregister, list the enrolled), the admin channel validation on every
manual candidate, the admin panel (suspend/resume, the section's
Synchroniser). This package is the one-line wiring a game designer
writes — everything else is declaration data (``mod.yaml``).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("botforge.mods.arena")

MOD_NAME = "arena"
GAME_KEY = "aoe2"


def register(bot: Any, config: Any) -> None:
    """Wire the generic surfaces onto the bot (idempotent, boot-safe)."""
    del config
    from botforge.discord.mod_surfaces import register_mod_surfaces

    definition = None
    registry = getattr(bot, "registry", None)
    if registry is not None:
        definition = registry.get(MOD_NAME)
    settings = dict(getattr(definition, "settings", {}) or {}) if definition is not None else {}
    register_mod_surfaces(
        bot,
        MOD_NAME,
        seasonal=False,
        settings=settings,
        game_key=GAME_KEY,
        admin_channel_key="admin",
    )
