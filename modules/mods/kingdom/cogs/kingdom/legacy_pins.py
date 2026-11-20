"""The LEGS sweep — pins born by a name the mod has since RENAMED (pins-fusion-v1).

The registration key carries the memory of a pin RECOGNISED by its
declared name; a rename without a legacy remnant ORPHANS the old message:
the superseded-pin pass only ever retouches the pins it FINDS, and a
forgotten key's message survives — unmainted, unswappable, DUPLICATE
(the double « Validation des royaumes », Check 104).

``sweep_legacy_pins`` converges a guild to ONE message per name: every
``LEGACY_PIN_KEYS`` entry already superseded by its SURVIVOR (same
message id — the awaited banner pass) is skipped, an orphaned alias
(old message still live, survivor pointing elsewhere) is UNPINNED,
DELETED and forgotten, ONCE per boot per guild (``_SWEPT``).
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdom.legacy_pins")

# legacy key → the survivor that replaced it (declared pins-fusion leg)
LEGACY_PIN_KEYS: dict[str, str] = {
    "panel:mod:kingdom:candidates": "panel:mod:kingdom:validation",
}

_SWEPT: set[str] = set()


def reset_swept() -> None:
    """Test hook — the once-per-boot memory drops on demand."""
    _SWEPT.clear()


async def sweep_legacy_pins(bot: Any, guild_id: str = "") -> int:
    """Unpin+delete+forget every orphaned legacy pin (one guild, or all)."""
    registry = getattr(bot, "message_registry", None)
    if registry is None:
        return 0
    guilds = (
        [bot.get_guild(int(guild_id))]
        if str(guild_id).isdigit()
        else list(getattr(bot, "guilds", []) or [])
    )
    swept = 0
    for guild in guilds:
        if guild is None:
            continue
        gid = str(getattr(guild, "id", ""))
        if not gid or gid in _SWEPT:
            continue
        for legacy_key, survivor_key in LEGACY_PIN_KEYS.items():
            try:
                legacy = await registry.resolve("discord", legacy_key, gid)
            except Exception:  # noqa: BLE001 — nothing registered under the name
                legacy = None
            if legacy is None:
                continue
            try:
                survivor = await registry.resolve("discord", survivor_key, gid)
            except Exception:  # noqa: BLE001
                survivor = None
            if survivor is not None and str(survivor.message_id) == str(legacy.message_id):
                # the awaited banner pass already claimed the slot — the
                # alias is converge-consistent, only its NAME retires
                try:
                    await registry.forget("discord", legacy_key, gid)
                except Exception:  # noqa: BLE001
                    pass
                continue
            channel = (
                guild.get_channel(int(legacy.channel_id))
                if str(legacy.channel_id).isdigit()
                else None
            )
            message = None
            if channel is not None and str(legacy.message_id).isdigit():
                try:
                    message = await channel.fetch_message(int(legacy.message_id))
                except Exception:  # noqa: BLE001 — already deleted elsewhere
                    message = None
            if message is not None:
                try:
                    if getattr(message, "pinned", False):
                        await message.unpin(reason="botforge: the pin's name retired")
                    await message.delete(reason="botforge: the pin's name retired")
                    swept += 1
                except Exception:  # noqa: BLE001 — one leg never blocks the pass
                    logger.warning(
                        "kingdom: legacy pin sweep failed (%s, guild %s)",
                        legacy_key,
                        gid,
                        exc_info=True,
                    )
            try:
                await registry.forget("discord", legacy_key, gid)
            except Exception:  # noqa: BLE001
                pass
        _SWEPT.add(gid)
    return swept


__all__ = ["sweep_legacy_pins", "LEGACY_PIN_KEYS", "reset_swept"]
