"""libre:match reference data — the map and civilization id tables.

The provider consumes the FREE MATCH community mappings
(``maps_aoe2.json``, ``civs_aoe2.json`` — the files libre:match ships):
one entry per display name, and under it the id PER API VERSION
(``"1"``... the oldest epoch, ``"8"`` the newest). The upstream payloads
speak raw ids (the options blob's ``10``/location key, a member's
``race_id``), so the tables are read as-is and reversed here.

The files are DATA, owned by the provider's config directory
(``config/providers/librematch/``): a future table version is a file
drop, never a code change. ``LIBREMATCH_REFERENCE_DIR`` overrides the
location (tests, containers). Loaded ONCE at first use, cached.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger("botforge.ext_librematch.reference")

DEFAULT_REFERENCE_DIR = str(Path("config") / "providers" / "librematch")
MAPS_FILE = "maps_aoe2.json"
CIVS_FILE = "civs_aoe2.json"


def _reference_dir() -> Path:
    """Return the provider's reference directory (env override first)."""
    return Path(os.environ.get("LIBREMATCH_REFERENCE_DIR", DEFAULT_REFERENCE_DIR))


def _load(name: str) -> dict[str, Any]:
    """Load one reference table, degraded to {} when absent/broken."""
    path = _reference_dir() / name
    try:
        with path.open(encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        logger.warning("reference table missing: %s — ids pass through raw", path)
        return {}
    except (OSError, json.JSONDecodeError):
        logger.warning("reference table unreadable: %s", path, exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def _reverse(table: dict[str, Any]) -> dict[tuple[str, str], str]:
    """Reverse ``{name: {version: id}}`` into ``{(version, id): name}``."""
    index: dict[tuple[str, str], str] = {}
    for name, versions in table.items():
        if not isinstance(versions, dict):
            continue
        for version, raw_id in versions.items():
            if raw_id is None or isinstance(raw_id, bool):
                continue
            try:
                # -1 is the table's "not this epoch" filler (and the
                # upstream's RANDOM-CIV marker) \u2014 indexing it made
                # every -1 answer with the last-added civ name (the
                # 2026-11-21 merlin finding: random seats rendered as
                # "Varangians")
                if int(raw_id) < 0:
                    continue
            except (TypeError, ValueError):
                continue
            index[(str(version), str(raw_id))] = str(name)
    return index


@lru_cache(maxsize=2)
def _indexed(name: str) -> dict[tuple[str, str], str]:
    """Return the reversed, cached table for one file (keyed by file name)."""
    return _reverse(_load(name))


def _lookup(name: str, raw_id: Any) -> str:
    """Resolve one raw upstream id to its display name ("" unknown).

    The API epoch that produced a payload is not knowable from the
    payload alone, so the ids resolve newest version FIRST: the newest
    table is the world the ids were read from, the older epochs stay
    reachable for historical documents.
    """
    if raw_id is None or isinstance(raw_id, bool):
        return ""
    try:
        if int(raw_id) < 0:
            return ""  # the upstream's RANDOM marker, never a civ/map
    except (TypeError, ValueError):
        return ""
    index = _indexed(name)
    if not index:
        return ""
    key = str(raw_id)
    versions = sorted({version for version, _ in index}, key=lambda v: (len(v), v), reverse=True)
    for version in versions:
        name_found = index.get((version, key))
        if name_found:
            return name_found
    return ""


def map_name_of(location_id: Any) -> str:
    """Return the display name of a map id (the options blob's location)."""
    return _lookup(MAPS_FILE, location_id)


def civ_name_of(civ_id: Any) -> str:
    """Return the display name of a civilization id (a member's race_id)."""
    return _lookup(CIVS_FILE, civ_id)
