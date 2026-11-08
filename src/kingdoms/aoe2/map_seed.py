"""The map seed: the fields a provider resolves for one map name.

AoE2 game data (kingdoms.aoe2, owner direction 2026-11-05) — shared by
the game service and the import flows, never core plumbing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class MapSeed:
    """The fields a provider resolves for one map name."""

    name: str
    description: str
    resource_url: str
    image_url: str
    icon_url: str = ""
    terrain: str = ""
    size: str = ""
    map_type: str = ""
    nomad: str = ""
    walls: str = ""
    tc: str = ""
    player_capacity: str = ""
    creator: str = ""
    creator_url: str = ""
    public: bool = True
    game_versions: tuple[str, ...] = ()
    versions: tuple[dict[str, object], ...] = ()
    tags: tuple[str, ...] = ()
    raw_wikitext: str = ""
    gallery_images: tuple[dict[str, str], ...] = ()


class LiquipediaUnconfiguredError(RuntimeError):
    """The liquipedia provider is not configured — a functional gap."""


class LiquipediaCircuitOpenError(RuntimeError):
    """The liquipedia circuit is open: the API is rate-limiting this IP.

    Every call fails fast while the window is open — no HTTP traffic.
    Retry later; the window doubles on each consecutive opening.
    """


def map_content_doc(entity_id: str, name: str, seed: MapSeed) -> dict[str, Any]:
    """Build the stored map content doc's ONE shape — every store path uses it.

    The sync's refresh and the three import flows (single creation,
    single import, bulk import) store the same doc: the parsed fields,
    the raw provider payload, the whole gallery and the freshness
    marker. The 2026-11-08 Michi/Canberra lesson: three hand-copied
    shapes drifted apart, and a doc without ``split_keys`` looked stale
    forever (empty summary, missing tags on the post).
    """
    return {
        "entity_id": entity_id,
        "locale": "en",
        "name": name,
        "summary": seed.description,
        "source_url": seed.resource_url,
        "image_url": seed.image_url,
        "icon_url": seed.icon_url,
        "walls": seed.walls,
        "nomad": seed.nomad,
        "tc": seed.tc,
        "player_capacity": seed.player_capacity,
        "creator": seed.creator,
        "creator_url": seed.creator_url,
        "label_gen": 2,
        "split_keys": True,
        "provider": "liquipedia",
        "game_versions": list(seed.game_versions),
        "versions": [dict(v) for v in seed.versions],
        "tags": list(seed.tags),
        "raw_wikitext": seed.raw_wikitext,
        "gallery_images": [dict(g) for g in seed.gallery_images],
    }
