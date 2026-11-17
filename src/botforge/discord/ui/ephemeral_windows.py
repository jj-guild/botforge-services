"""The ephemeral window navigation — one mode per surface owner (#381).

Ruling 3 (Merlin 17/11): the kingdom mod defines ITS navigation mode
for ITS ephemeral views — and the mode the platform keeps today stays
the default for the platform and everyone else. This seam makes the
MODE a parameter instead of a hardwired behavior: every surface owner
(a scope, ``platform`` by default) registers the mode it wants at
boot, and the open/close plumbing lives here — once, generic.

Two modes ship today:

- ``PLAIN`` — fire-and-forget: the window is sent, nothing tracked
  (the platform's menus and panels, their frozen-menu contract);
- ``SINGLE`` — one live window per player: opening a new one closes
  the previous, best-effort (the kingdom mod's fenêtre unique).

A mod without a registered scope reads ``PLAIN`` — the seam never
changes a surface's behavior until its owner asks for it. The mode is
idempotent to set (a mod may set it at import time and again at
``register()``); the live-window registry is process-wide and restarts
empty, like every ephemeral thing (a restart already orphans the
Discord side — the deleted window is a no-op, swallowed).
"""

from __future__ import annotations

from enum import StrEnum
import logging
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # the seam is duck-typed at runtime — no discord import
    import discord

logger = logging.getLogger("botforge.discord.ui.ephemeral_windows")

PLATFORM_SCOPE = "platform"


class EphemeralWindowMode(StrEnum):
    """How one scope's ephemeral windows navigate."""

    PLAIN = "plain"
    SINGLE = "single"


_modes: dict[str, EphemeralWindowMode] = {PLATFORM_SCOPE: EphemeralWindowMode.PLAIN}
_live: dict[tuple[str, str], tuple[Any, float]] = {}


def set_window_mode(scope: str, mode: EphemeralWindowMode) -> None:
    """Declare one scope's navigation mode (idempotent, boot-time)."""
    _modes[str(scope)] = EphemeralWindowMode(mode)


def window_mode(scope: str) -> EphemeralWindowMode:
    """Return the scope's mode — an unregistered scope reads PLAIN."""
    return _modes.get(str(scope), EphemeralWindowMode.PLAIN)


async def close_ephemeral_window(scope: str, owner: str) -> None:
    """Close the owner's live window in this scope, best-effort."""
    window = _live.pop((str(scope), str(owner)), None)
    if window is None:
        return
    interaction = window[0]
    try:
        await interaction.delete_original_response()
        logger.info("ephemeral window closed (%s/%s)", scope, owner)
    except Exception:
        logger.info("ephemeral window close failed (ignored) (%s/%s)", scope, owner)


async def open_ephemeral_window(
    interaction: discord.Interaction,
    scope: str = PLATFORM_SCOPE,
    content: str | None = None,
    **kwargs: Any,
) -> None:
    """Send one ephemeral window under the scope's navigation mode.

    ``SINGLE`` closes the player's previous window first (the mod's
    fenêtre unique); ``PLAIN`` just sends. Ephemeral is enforced —
    every window this seam opens is the player's own, never a channel
    broadcast.
    """
    owner = str(interaction.user.id)
    mode = window_mode(scope)
    if mode is EphemeralWindowMode.SINGLE:
        await close_ephemeral_window(scope, owner)
    kwargs["ephemeral"] = True
    await interaction.response.send_message(content, **kwargs)
    if mode is EphemeralWindowMode.SINGLE:
        _live[(str(scope), owner)] = (interaction, time.monotonic())


__all__ = [
    "EphemeralWindowMode",
    "PLATFORM_SCOPE",
    "close_ephemeral_window",
    "open_ephemeral_window",
    "set_window_mode",
    "window_mode",
]
