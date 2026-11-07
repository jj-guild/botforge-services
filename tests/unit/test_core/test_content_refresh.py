"""Content refresh tests: catalog reconciliation through the provider seam."""

from __future__ import annotations

from typing import Any

from kingdoms.game_aoe2.content_refresh import refresh_aoe2_content

# The refresh rides the PROVIDER seam (no vendored data): the tests
# inject a fake source standing in for the aoe2techtree provider.
_FAKE_SOURCE = None


class _FakeSource:
    """A stand-in for the aoe2techtree provider over the seam."""

    def __init__(self) -> None:
        self._data = {
            "Franks": {
                "en": {"name": "Franks", "summary": "Cavalry civ", "image_url": "https://x/franks.png"},
                "fr": {"name": "Francs", "summary": "Civilisation de cavalerie", "image_url": "https://x/franks.png"},
            },
            "Dravidians": {
                "en": {"name": "Dravidians", "summary": "Elephant civ", "image_url": "https://x/dravidians.png"},
                "fr": {"name": "Dravidiens", "summary": "Civilisation d'elephants", "image_url": "https://x/dravidians.png"},
            },
        }

    async def list_factions(self) -> list[str]:
        return sorted(self._data)

    async def faction_content(self, key: str, locale: str) -> dict[str, Any] | None:
        entry = self._data.get(key, {}).get(locale)
        if entry is None:
            return None
        from kingdoms.game_aoe2.content_source import LocalizedContent

        return LocalizedContent(
            entity_id=f"faction:aoe2:{key.lower()}",
            locale=locale,
            name=entry["name"],
            summary=entry["summary"],
            source_url="https://github.com/SiegeEngineers/aoe2techtree",
            image_url=entry["image_url"],

        )


def _patch_source(monkeypatch: Any) -> None:
    import kingdoms.game_aoe2.content_source as source_module

    monkeypatch.setattr(
        source_module, "resolve_aoe2_content_source", lambda *a, **k: _FakeSource()
    )


class FakeCollection:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, Any]] = {}

    async def replace_one(self, filter: Any, doc: dict[str, Any], upsert: bool = False) -> None:
        self.docs[str(doc["_id"])] = dict(doc)

    async def find_one(self, filter: dict[str, Any]) -> dict[str, Any] | None:
        if "_id" in filter:
            return self.docs.get(str(filter["_id"]))
        for doc in self.docs.values():
            if all(doc.get(k) == v for k, v in filter.items()):
                return doc
        return None

    async def create_index(self, keys: Any) -> None:
        del keys


class FakeDatabase:
    def __init__(self) -> None:
        self.collections: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())


async def test_refresh_creates_missing_factions_and_content(monkeypatch: Any) -> None:
    from kingdoms.core.models import db as db_module

    database = FakeDatabase()
    monkeypatch.setattr(db_module, "get_async_database", lambda: database)

    _patch_source(monkeypatch)
    counts = await refresh_aoe2_content()

    assert counts["factions"] == 2
    assert counts["content_docs"] == 4
    factions = database.collections["factions"].docs
    assert "faction:aoe2:franks" in factions
    assert "faction:aoe2:dravidians" in factions
    content = database.collections["faction_content"].docs
    assert "faction:aoe2:franks:fr" in content
    assert content["faction:aoe2:franks:fr"]["name"] == "Francs"


async def test_refresh_is_idempotent(monkeypatch: Any) -> None:
    from kingdoms.core.models import db as db_module

    database = FakeDatabase()
    monkeypatch.setattr(db_module, "get_async_database", lambda: database)

    _patch_source(monkeypatch)
    await refresh_aoe2_content()
    _patch_source(monkeypatch)
    counts = await refresh_aoe2_content()

    assert counts["factions"] == 0
    assert counts["content_docs"] == 4


async def test_maps_sync_rebuilds_every_known_map(monkeypatch: Any) -> None:
    """A sync means FRESH data for EVERY known map — no "complete" skip.

    Every active map re-resolves and re-stores (raw wikitext next to
    the parsed fields); archived maps stay untouched (owner direction
    2026-11-07).
    """
    import kingdoms.core.services.game_data as game_data_module
    import kingdoms.game_aoe2.content_refresh as refresh_module
    import kingdoms.game_aoe2.seed as seed_module
    from kingdoms.aoe2.map_seed import MapSeed
    from kingdoms.core.models import db as db_module
    from kingdoms.core.models.game_data import MapModel

    database = FakeDatabase()
    monkeypatch.setattr(db_module, "get_async_database", lambda: database)

    class FakeGameData:
        async def list_maps(self, game_key: str) -> list[MapModel]:
            del game_key
            return [
                MapModel(_id="map:aoe2:arena", game_key="aoe2", name="Arena"),
                MapModel(_id="map:aoe2:budapest", game_key="aoe2", name="Budapest"),
                MapModel(
                    _id="map:aoe2:old",
                    game_key="aoe2",
                    name="Old",
                    archived_at=1,
                ),
            ]

    monkeypatch.setattr(game_data_module, "GameDataService", lambda adapter: FakeGameData())
    monkeypatch.setattr(seed_module, "MongoAoE2Database", lambda database: None)

    async def fake_resolve(names: list[str]) -> dict[str, Any]:
        return {
            name: MapSeed(
                name=name,
                description=f"The {name} overview.",
                resource_url=f"https://liquipedia.net/ageofempires2/{name}",
                image_url=f"https://x/{name}.png",
                map_type="Land",
                walls="Stone Walls",
                nomad="No",
                tc="1",
                player_capacity="Up to 8",
                tags=("type:land", "walls:stone", "tc:1"),
                raw_wikitext="{{Infobox map|name=" + name + "}}",
            )
            for name in names
        }

    monkeypatch.setattr(refresh_module, "_resolve_map_seeds", fake_resolve)

    from kingdoms.game_aoe2.content_refresh import refresh_aoe2_maps

    counts = await refresh_aoe2_maps()
    assert counts["maps_total"] == 3
    assert counts["maps_enriched"] == 2, "every ACTIVE map re-stores — the archived one skips"
    docs = database.collections["faction_content"].docs
    assert "map:aoe2:arena:en" in docs and "map:aoe2:budapest:en" in docs
    assert "map:aoe2:old:en" not in docs
    arena = docs["map:aoe2:arena:en"]
    assert arena["raw_wikitext"] == "{{Infobox map|name=Arena}}", "the raw provider payload rides"
    assert "walls:stone" in arena["tags"] and "tc:1" in arena["tags"]

    # the SECOND sync re-stores everything again: no complete-skip —
    # a sync always means fresh data, even for an already-rich doc
    counts_again = await refresh_aoe2_maps()
    assert counts_again["maps_enriched"] == 2, "a sync is a full rebuild, never a skip"
