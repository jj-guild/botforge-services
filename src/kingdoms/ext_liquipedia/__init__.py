"""ext-liquipedia — Liquipedia content provider process.

A real provider (ADR-0020/0021), not an in-process module: it owns the
Liquipedia MediaWiki access (terms-of-use compliance, rate limiting,
licence guard) and its own Mongo tables — the raw fetched data lives
here, exploited and served over ``kingdoms.v1.Content``. Liquipedia is
a multi-game source (AoE2 today; the wiki family covers every esport),
so the map seeding is keyed by ``game_key``.

Tables owned (logical base ``liquipedia``):
- ``liquipedia_maps``  — one document per (game, page): the parsed
  descriptor, the raw wikitext, licence outcome, fetched_at — the debug
  and replay source of every import;
- ``liquipedia_pages`` — the raw MediaWiki API responses (cache-aside:
  a page already fetched is never re-requested until the TTL lapses).
"""

from __future__ import annotations

PROVIDER_ID = "ext-liquipedia"
PROVIDER_KEY = "liquipedia"
SUPPORTED_LOCALES = ("en",)

# The provider is game-AGNOSTIC: it serves whatever game_key the request
# carries, and never knows who consumes it. The wiki family is the only
# game-specific fact — declared here as data (aoe2 -> ageofempires wiki).
GAME_WIKIS: dict[str, str] = {"aoe2": "ageofempires"}

MAPS_COLLECTION = "liquipedia_maps"
PAGES_COLLECTION = "liquipedia_pages"

PAGE_CACHE_TTL_S = 7 * 24 * 3600

# The persisted descriptors' parser generation. The cache-aside serves a
# stored descriptor ONLY when its generation matches: a parser change
# bumps this number and every pre-era descriptor becomes a cache miss —
# the next seed request re-fetches with the new parser and re-persists
# (the merlin 2026-11-07 lesson: the 7-day TTL alone served the old
# parse for a week after the fix shipped).
# Gen 2: the whole overview (all paragraphs) + the gallery icon's bare
# form + the captioned-icon preference.
# Gen 3: the English tag vocabulary (walls:no/wood/stone/partial, tc:<n>
# from 1) + the raw wikitext riding the descriptor.
# Gen 4: the infobox field regex stays on ONE line — an empty value
# (|caption=) no longer swallows the next line (Nomad's creator).
# Gen 5: the map type's display casing normalized ("hybrid" -> "Hybrid")
# + the raw wikitext rides the provider wire.
SEED_GEN = 5
