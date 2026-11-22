"""La Régie (console-etats-regie-v1, Drasah 21/11) — the admin's switches.

The designer's TWO WORLDS split: the PLAYERS' life (register, found a
realm, join a realm) is permanent and OPEN by default; the admin's
régie is a handful of ON/OFF switches that close an exception — never
a mode the flows are rewritten around (extensible data, #369: the
season 2 adds a switch by adding ONE key here and ONE string).

The switches live in the mod's OWN state scope (``mod:kingdom:``,
key ``regie:<guild>``) — never another service's storage, never a bare
prefix. Everything degrades safely: a missing state service or an
unset key falls back to the DEFAULTS, which mirror the pre-régie
behaviour EXACTLY (Drasah's running season must never wake up closed):

- ``registration_open``   — the account/enrollment door (True)
- ``registration_required`` — the parcours' ACCOUNT TIER (True: the
  compte first, the declared classical parcours). Flipped OFF, the
  players postulent directly without any account, whatever the season
  (registration-switch-v1, Drasah 22/11 — the beta's own shortcut,
  decoupled from the beta and handed to the régie). The beta season
  still bends it the same way (ONE beta): OFF wins, the account step
  never rides.
- ``realm_creation_open`` — « Prendre le Trône » (True)
- ``realm_join_open``     — joining a realm (True)
- ``season_entry_open``   — the 🛂 sas : the one switch with a
  phase-aware default — open while a season PREPARES, closed once it
  runs (the sas shuts itself at the season's departure, Drasah 21/11
  « de base, par défaut, oui, le sas se ferme »), re-openable by hand
  for the latecomers (the régie drawer), and the admin can always
  inject a realm by the existing « Ajouter un royaume » gesture.
  sas-cycle-v1 (Drasah 21/11) : the sas is the ADMIN's will — open
  = préparation ; it is a LAUNCH PREREQUISITE (⇒ « ▶️ Lancer la
  saison » refuses while closed) ; « 🏁 Terminer la saison » closes
  it AUTOMATICALLY (the only automatic gesture of the cycle) and the
  manual close EMPTIES the waiting room ( MPs best-effort) — the
  re-open is NEVER automatic.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("kingdom.regie")

_MOD = "kingdom"
REGIE_KEY = "regie"

# The switches, in the drawer's display order — DATA (#369): adding a
# switch is one key + one label string, never a new flow.
REGIE_SWITCHES: tuple[str, ...] = (
    "registration_open",
    "registration_required",
    "realm_creation_open",
    "realm_join_open",
    "season_entry_open",
)

# The players' life is OPEN by default; the sas is PHASE-mapped (below).
_REGIE_DEFAULTS: dict[str, bool] = {
    "registration_open": True,
    "registration_required": True,
    "realm_creation_open": True,
    "realm_join_open": True,
    "season_entry_open": False,
}

SWITCH_LABEL_KEYS: dict[str, str] = {
    "registration_open": "settings_regie_registration",
    "registration_required": "settings_regie_registration_required",
    "realm_creation_open": "settings_regie_creation",
    "realm_join_open": "settings_regie_join",
    "season_entry_open": "settings_regie_sas",
}


def _cache(bot: Any) -> Any | None:
    """The mod's state door, degraded to None (a missing service never bends)."""
    from botforge.core.services.mod_storage import ModStateCache

    state_service = getattr(bot, "state_service", None)
    return ModStateCache(state_service, _MOD) if state_service is not None else None


async def _current_phase(bot: Any) -> str:
    """The live season's phase, best-effort ('off' when none/unreadable)."""
    from .common import wiring

    stack = wiring()
    if stack is None or getattr(stack, "kingdoms", None) is None:
        return "off"
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001 — an unreadable season never bends the doors
        logger.warning("kingdom: the régie's season read failed", exc_info=True)
        return "off"
    if season is None or bool(getattr(season, "finished", False)):
        return "off"
    return str(getattr(season, "phase", "started")) or "started"


async def read_regie(bot: Any, guild_id: str) -> dict[str, bool]:
    """Every switch's live value (defaults when unset — never a closed fallback).

    ``season_entry_open`` alone maps the legacy behaviour when no data
    exists: open while the season prepares, closed once it runs.
    """
    defaults = dict(_REGIE_DEFAULTS)
    phase = await _current_phase(bot)
    defaults["season_entry_open"] = phase == "setup"
    cache = _cache(bot)
    if cache is None:
        return defaults
    try:
        stored = await cache.get(f"{REGIE_KEY}:{guild_id}") or {}
    except Exception:  # noqa: BLE001 — unreadable data is the same as unset
        logger.warning("kingdom: the régie read failed", exc_info=True)
        return defaults
    values = dict(defaults)
    for key in REGIE_SWITCHES:
        if key in stored:
            values[key] = bool(stored[key])
    return values


async def set_switch(bot: Any, guild_id: str, key: str, value: bool) -> bool:
    """Flip one switch (best-effort: the drawer always gets a fresh read)."""
    if key not in REGIE_SWITCHES:
        raise ValueError(key)
    cache = _cache(bot)
    if cache is None:
        return False
    stored_key = f"{REGIE_KEY}:{guild_id}"
    try:
        stored = (await cache.get(stored_key)) or {}
    except Exception:  # noqa: BLE001
        stored = {}
    stored[str(key)] = bool(value)
    await cache.set(stored_key, stored)
    logger.info("kingdom: régie %s -> %s (guild %s)", key, bool(value), guild_id)
    return True


async def toggle_switch(bot: Any, guild_id: str, key: str) -> bool:
    """Flip one switch to its opposite; returns the switch's NEW value."""
    values = await read_regie(bot, guild_id)
    new = not bool(values.get(key, False))
    await set_switch(bot, guild_id, key, new)
    return new


async def regie_open(bot: Any, guild_id: str, key: str) -> bool:
    """One switch's live value, defaults included (the doors' one-liner)."""
    return bool((await read_regie(bot, guild_id)).get(key, False))


async def registration_required(bot: Any, guild_id: str) -> bool:
    """Whether the parcours demands the ACCOUNT step — the one answer.

    registration-switch-v1 (Drasah 22/11) : the régie's switch is the
    designer's live word (OFF = on postule directement, whatever the
    season); the beta season bends it the SAME way (ONE beta, 21/11 —
    a beta never asks for a compte). The default mirrors the declared
    classical parcours exactly: required.
    """
    if not await regie_open(bot, guild_id, "registration_required"):
        return False
    from .camp_beta import kingdom_is_beta

    return not await kingdom_is_beta(bot, guild_id)


__all__ = [
    "REGIE_SWITCHES",
    "registration_required",
    "SWITCH_LABEL_KEYS",
    "read_regie",
    "regie_open",
    "set_switch",
    "toggle_switch",
]
