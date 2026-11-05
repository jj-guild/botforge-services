"""Transition shim: the AoE2 game module lives in kingdoms.game_aoe2.

The game code NEVER lived in core (rule 3 — core knows the games by
their gRPC services, not their code). This shim keeps the old import
path alive while the call sites migrate; it dies with the last one.
"""

from __future__ import annotations

from kingdoms.game_aoe2.content_refresh import (  # noqa: F401
    DATASET_DIR,
    refresh_aoe2_content,
    refresh_aoe2_maps,
)
from kingdoms.game_aoe2.faction_content import (  # noqa: F401
    PROVIDER_KEY,
    SUPPORTED_LOCALES,
    TechtreeContentProvider,
)
from kingdoms.game_aoe2.seed import (  # noqa: F401
    MongoAoE2Database,
)
