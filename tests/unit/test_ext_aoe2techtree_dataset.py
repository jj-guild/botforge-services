"""The civ content over the REAL vendored aoe2techtree dataset — no fetch.

The civs' raw data is vendored in the repository (``data/core/aoe2techtree``:
data.json + strings-fr/en.json, licence-clean, offline). These tests run
the REAL DatasetContentSource and the REAL content seam (servicer +
client over loopback gRPC) against that data — the civ-side equivalent
of the map fixtures: tags, names, help text and crests are checked
against the actual bytes, never against assumptions.
"""

from __future__ import annotations

from typing import Any

import grpc
import pytest

from kingdoms.core.rpc.content import ContentServicer
from kingdoms.core.rpc.content_client import ContentProviderClient
from kingdoms.ext_aoe2techtree.source import DatasetContentSource, resolve_source
from kingdoms.rpc_generated.kingdoms.v1 import content_pb2_grpc

KNOWN_CIVS = ("Aztecs", "Franks", "Britons")


def test_the_dataset_serves_every_known_civ() -> None:
    """The vendored dataset's civ index carries the known civs."""
    source = DatasetContentSource()
    keys = source.faction_keys()
    assert len(keys) >= 40, f"a full civ index: {len(keys)} keys"
    for civ in KNOWN_CIVS:
        assert civ in keys, f"{civ} must be in the dataset's index"


def test_the_dataset_localizes_a_civ_in_fr_and_en() -> None:
    """A civ's name and help text resolve in both locales."""
    source = DatasetContentSource()
    fr = source.faction_content("Aztecs", "fr")
    en = source.faction_content("Aztecs", "en")
    assert fr is not None and en is not None
    assert fr["name"] == "Aztèques", f"the fr name is localized: {fr['name']!r}"
    assert en["name"] == "Aztecs"
    assert fr["entity_id"] == "faction:aoe2:Aztecs"
    assert fr["locale"] == "fr" and en["locale"] == "en"
    # the help text is the civ's bullet list, multi-line after <br> cleanup
    assert "\n" in str(fr["summary"]) and "\n" in str(en["summary"])
    assert str(en["summary"]).strip()


def test_the_dataset_serves_the_crest_image() -> None:
    """A civ's content carries its crest image URL."""
    source = DatasetContentSource()
    content = source.faction_content("Franks", "fr")
    assert content is not None
    assert str(content["image_url"]).endswith("/franks.png")


def test_an_unknown_civ_degrades_to_none() -> None:
    """An unknown civ key yields None — the caller falls back, never crashes."""
    source = DatasetContentSource()
    assert source.faction_content("Unknown", "fr") is None


def test_resolve_source_defaults_to_the_vendored_dataset() -> None:
    """Without an API url, the vendored dataset is the source (offline)."""
    source = resolve_source("")
    assert isinstance(source, DatasetContentSource)


@pytest.mark.asyncio
async def test_the_civ_seam_round_trips_over_the_real_dataset() -> None:
    """The REAL source, servicer and client over loopback — zero fakes."""
    source = DatasetContentSource()

    async def _list_factions() -> list[str]:
        return source.faction_keys()

    async def _faction_content(faction_key: str, locale: str) -> dict[str, Any] | None:
        return source.faction_content(faction_key, locale)

    async def _map_content(map_key: str, locale: str) -> dict[str, Any] | None:
        return source.map_content(map_key, locale)

    server = grpc.aio.server()
    servicer = ContentServicer(
        provider_key="aoe2techtree",
        game_key="aoe2",
        locales=("fr", "en"),
        list_factions=_list_factions,
        faction_content=_faction_content,
        map_content=_map_content,
    )
    content_pb2_grpc.add_ContentServicer_to_server(servicer, server)
    port = server.add_insecure_port("127.0.0.1:0")
    await server.start()
    try:
        client = ContentProviderClient(f"127.0.0.1:{port}")
        keys = await client.list_factions()
        assert "Aztecs" in keys and len(keys) >= 40

        fr = await client.get_faction_content("Aztecs", "fr")
        assert fr is not None
        assert fr["name"] == "Aztèques"
        assert fr["image_url"].endswith("/aztecs.png")

        en = await client.get_faction_content("Aztecs", "en")
        assert en is not None and en["name"] == "Aztecs"

        assert await client.get_faction_content("Unknown", "fr") is None
    finally:
        await server.stop(0)
