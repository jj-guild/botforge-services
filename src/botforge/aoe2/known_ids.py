"""Known profile ids + display names, shared by the AoE2 processes.

botforge-services#423: the log taxonomy rides the known ids — a line
about a known profile (or a match it plays) is INFO and NAMES the
player; everything else (lobby counts, heartbeats, stranger matches)
is DEBUG. Both the game_aoe2 aggregator (which owns the roster pushed
through UpdateEnrollments) and the ext_aoe2lobby adapter (which
forwards the same enrollments) resolve ids and names through this
module — one rule, one implementation (botforge.aoe2 sits on the ext
providers' shared-utils whitelist, layering rule R1).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any


class KnownIds:
    """The known profile ids and their display names.

    The roster (the enrollments push) is the source of truth; a
    nameless known profile falls back to its profile id rather than
    being demoted out of INFO. Names observed in match slots refine
    the roster without ever adding a stranger.
    """

    def __init__(self) -> None:
        self._names: dict[str, str] = {}

    def set_entries(self, entries: Iterable[Any]) -> None:
        """Replace the known ids from enrollment entries.

        Entries are dicts (``profile_id`` plus optional ``user_id`` /
        ``name`` — the enrollments push shape) or bare profile id
        strings (tests, degraded paths).
        """
        names: dict[str, str] = {}
        for entry in entries:
            if isinstance(entry, dict):
                profile_id = str(entry.get("profile_id", ""))
                name = str(entry.get("name", "") or entry.get("display_name", ""))
            else:
                profile_id, name = str(entry), ""
            if profile_id:
                names[profile_id] = name
        self._names = names

    def set_ids(self, profile_ids: Iterable[Any]) -> None:
        """Replace the known ids from bare ids, keeping the learned names."""
        wanted = {str(pid) for pid in profile_ids if str(pid)}
        self._names = {pid: self._names.get(pid, "") for pid in sorted(wanted)}

    def learn_name(self, profile_id: Any, name: str) -> None:
        """Record a display name observed for an already-known profile."""
        pid = str(profile_id)
        if name and pid in self._names and not self._names[pid]:
            self._names[pid] = name

    def is_known(self, profile_id: Any) -> bool:
        """Report whether one profile id is known (enrolled or tracked)."""
        return str(profile_id) in self._names

    def known_of(self, profile_ids: Iterable[Any]) -> list[str]:
        """Return the known ids among the given profile ids (input order kept)."""
        return [str(p) for p in profile_ids if str(p) in self._names]

    def display_name(self, profile_id: Any) -> str:
        """Return the display name of a profile, falling back to its id."""
        pid = str(profile_id)
        return self._names.get(pid) or pid

    def display_names(self, profile_ids: Iterable[Any]) -> str:
        """Build a comma-joined, human-readable list of the given profiles."""
        return ",".join(self.display_name(p) for p in profile_ids)


def log_match_event(
    logger: logging.Logger,
    label: str,
    event_type: str,
    match_ref: str,
    profile_ids: Iterable[Any],
    known: KnownIds,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log one match event under the #423 taxonomy.

    INFO — and the player is NAMED — when the event concerns a known
    profile; DEBUG when it concerns strangers only, so the INFO stream
    carries exactly what the dashboard and the bot follow.
    """
    ids = [str(p) for p in profile_ids]
    known_ids = known.known_of(ids)
    # ONE lifecycle lexicon (owner 2026-11-24: "début/update/fin de
    # lobby/match n°123456"): lobby_opened... maps to plain French
    # verbs, in the adapter, the game service and the panels' logs alike
    verbs = {
        "lobby_opened": "lobby début",
        "lobby_closed": "lobby fin",
        "match_updated": "lobby update",
        "game_started": "match début",
        "game_ended": "match fin",
    }
    event_type = verbs.get(event_type, event_type)
    if known_ids:
        map_name = str((metadata or {}).get("map", "") or "")
        suffix = f" map={map_name}" if map_name else ""
        logger.info(
            "%s: %s — %s n°%s%s",
            label,
            known.display_names(known_ids),
            event_type,
            match_ref or "(none)",
            suffix,
        )
    else:
        logger.debug(
            "%s (no known profile): profiles=%s match=%s type=%s",
            label,
            ",".join(ids),
            match_ref,
            event_type,
        )
