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

import asyncio
import logging
import time
from enum import StrEnum
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:  # the seam is duck-typed at runtime — no discord import
    import discord

logger = logging.getLogger("botforge.discord.ui.ephemeral_windows")

PLATFORM_SCOPE = "platform"

# ONE window per mode scope may declare a TTL: a live window closes
# ITSELF after ``ttl`` seconds (the designer's anti-pollution rule —
# Discord keeps an ephemeral message until its owner dismisses it, a
# bot that never dismisses leaves a trail behind). The clock is
# per-scope data (``set_window_ttl``), arithmetic on the stored
# interaction token: the close rides the token's webhook and dies
# quietly once the token expires (15 min) — a TTL beyond that is a
# no-op, so the sane range is below.
_ttls: dict[str, float] = {}
_close_tasks: dict[tuple[str, str], asyncio.Task[None]] = {}


def set_window_ttl(scope: str, seconds: float) -> None:
    """Declare one scope's self-closing delay (0 or negative = never)."""
    _ttls[str(scope)] = float(seconds)


def window_ttl(scope: str) -> float:
    """Return the scope's self-closing delay (0 = never)."""
    return _ttls.get(str(scope), 0.0)


def get_live_window(scope: str, owner: str) -> Any | None:
    """Return the owner's tracked window (the interaction or adapter).

    Feeds an owner-side close button that deletes the message it rides.
    """
    record = _live.get((str(scope), str(owner)))
    return record[0] if record is not None else None


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
    _cancel_auto_close(str(scope), str(owner))
    window = _live.pop((str(scope), str(owner)), None)
    if window is None:
        return
    interaction = window[0]
    try:
        await interaction.delete_original_response()
        logger.info("ephemeral window closed (%s/%s)", scope, owner)
    except Exception:
        logger.info("ephemeral window close failed (ignored) (%s/%s)", scope, owner)


def _cancel_auto_close(scope: str, owner: str) -> None:
    task = _close_tasks.pop((str(scope), str(owner)), None)
    if task is not None and not task.done():
        task.cancel()


def _arm_auto_close(scope: str, owner: str, ttl: float) -> None:
    """Schedule the window's self-close, cancelling any prior timer first.

    A replaced window cancels its own timer (``_cancel`` runs in the replace path).
    """
    key = (str(scope), str(owner))
    if ttl <= 0:
        return

    async def _later() -> None:
        try:
            await asyncio.sleep(ttl)
        except asyncio.CancelledError:
            return
        # only close what is still the live record (a replaced window
        # re-arms; a manually closed one already popped the record)
        await close_ephemeral_window(scope, owner)

    try:
        _close_tasks[key] = asyncio.create_task(_later())
    except RuntimeError:  # no loop (a sync import-time call) — never armed
        pass


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
    broadcast. A click ALREADY acknowledged (``response.defer`` — the
    fast-ack pattern: the 3-second interaction clock belongs to the
    ACK, the build then takes its time) rides the followup: the window
    is the follow-up message, and the single-window close tracks it
    through the same delete seam.
    """
    owner = str(interaction.user.id)
    mode = window_mode(scope)
    if mode is EphemeralWindowMode.SINGLE:
        await close_ephemeral_window(scope, owner)
    ttl = window_ttl(scope)
    kwargs["ephemeral"] = True
    if interaction.response.is_done():
        message = await interaction.followup.send(cast("str", content), **kwargs)
        if mode is EphemeralWindowMode.SINGLE:
            _live[(str(scope), owner)] = (_FollowupWindow(message), time.monotonic())
            _arm_auto_close(str(scope), owner, ttl)
    else:
        await interaction.response.send_message(content, **kwargs)
        if mode is EphemeralWindowMode.SINGLE:
            _live[(str(scope), owner)] = (interaction, time.monotonic())
            _arm_auto_close(str(scope), owner, ttl)


class _FollowupWindow:
    """A follow-up window closable through the same delete seam.

    ``close_ephemeral_window`` calls ``delete_original_response()`` on
    whatever it tracked; a follow-up message answers ``delete()``
    instead — this adapter speaks the interaction's protocol so the
    close path stays ONE code path.
    """

    def __init__(self, message: Any) -> None:
        self._message = message

    async def delete_original_response(self) -> None:
        await self._message.delete()


__all__ = [
    "PLATFORM_SCOPE",
    "EphemeralWindowMode",
    "close_ephemeral_window",
    "get_live_window",
    "open_ephemeral_window",
    "set_window_mode",
    "set_window_ttl",
    "window_mode",
    "window_ttl",
]
