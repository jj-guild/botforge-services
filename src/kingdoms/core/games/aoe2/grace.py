"""Transition re-export: the grace rule lives in the shared timing util.

The lobby-closed grace is consumed by the provider (ext-aoe2lobby) and
the game service alike — it is a SHARED rule, never game-module code
(architecture rule R1). The re-export keeps the old import path alive
while the callers migrate.
"""

from __future__ import annotations

from kingdoms.core.timing import GRACE_PERIOD_S, LobbyClosedGrace  # noqa: F401
