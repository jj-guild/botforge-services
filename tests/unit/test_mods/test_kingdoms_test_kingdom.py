"""kingdom-test-v1 (Drasah 01/11) — the Nilrem test kingdom, unit tests.

The reserved admin-only kingdom « Nilrem »: idempotent creation with
its fictional king, quota exemption, player-proof (never joined, never
claimed), empty hand at the season start, and the complete deletion.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import discord
import pytest

from kingdoms.mods.kingdoms.models import LordRole
from kingdoms.mods.kingdoms.service import (
    TEST_KINGDOM_ID,
    TEST_KINGDOM_NAME,
    TEST_KING_ID,
    KingdomLimitError,
    KingdomsService,
    NotEnrollableError,
    is_test_kingdom,
)

pytestmark = pytest.mark.asyncio


class _Store:
    """A minimal in-memory KingdomsStore (the service is store-agnostic)."""

    def __init__(self) -> None:
        self.seasons: list[dict[str, Any]] = []
        self.kingdoms: list[dict[str, Any]] = []
        self.lords: list[dict[str, Any]] = []

    @staticmethod
    def _upsert(items: list[dict[str, Any]], doc: dict[str, Any]) -> None:
        for index, existing in enumerate(items):
            if str(existing["_id"]) == str(doc["_id"]):
                items[index] = doc
                return
        items.append(doc)

    async def find_seasons(self) -> list[dict[str, Any]]:
        return list(self.seasons)

    async def upsert_season(self, doc: dict[str, Any]) -> None:
        self._upsert(self.seasons, doc)

    async def find_kingdoms(self) -> list[dict[str, Any]]:
        return list(self.kingdoms)

    async def upsert_kingdom(self, doc: dict[str, Any]) -> None:
        self._upsert(self.kingdoms, doc)

    async def delete_kingdom(self, document_id: str) -> None:
        self.kingdoms = [d for d in self.kingdoms if str(d["_id"]) != str(document_id)]

    async def find_lords(self) -> list[dict[str, Any]]:
        return list(self.lords)

    async def upsert_lord(self, doc: dict[str, Any]) -> None:
        self._upsert(self.lords, doc)

    async def delete_lord(self, document_id: str) -> None:
        self.lords = [d for d in self.lords if str(d["_id"]) != str(document_id)]

    async def wipe_season_data(self) -> None:
        self.seasons, self.kingdoms, self.lords = [], [], []

    async def upsert_season_archive(self, doc: dict[str, Any]) -> None:
        return None


def _config() -> Any:
    return SimpleNamespace(
        weeks=8,
        kingdoms_count=1,
        lords_per_kingdom=5,
        starting_civilizations=2,
        civilizations=(SimpleNamespace(key="azteques"), SimpleNamespace(key="berberes")),
        ages=(SimpleNamespace(key="dark_age", extra_marriages=0),),
        names=SimpleNamespace(min_length=3, max_length=24, pattern=r"[A-Za-zÀ-ÿ0-9 .'\-]+"),
        tavern=SimpleNamespace(purse_start=10),
    )


async def _launched_service() -> tuple[KingdomsService, _Store]:
    store = _Store()
    service = KingdomsService(store, _config())
    await service.launch()
    return service, store


async def test_ensure_test_kingdom_is_idempotent_with_a_fictional_king() -> None:
    service, store = await _launched_service()
    kingdom = await service.ensure_test_kingdom()

    assert str(kingdom.id) == TEST_KINGDOM_ID
    assert kingdom.name == TEST_KINGDOM_NAME
    assert str(kingdom.validation) == "approved"
    assert is_test_kingdom(kingdom)
    assert not is_test_kingdom(None)

    # idempotent: a second call adopts, never duplicates
    again = await service.ensure_test_kingdom()
    assert str(again.id) == TEST_KINGDOM_ID
    ids = [str(k["_id"]) for k in store.kingdoms]
    assert ids.count(TEST_KINGDOM_ID) == 1

    # the fictional king: non-digit id, King role, no chronicle noise
    (king,) = [lord for lord in await service.lords() if str(lord.id) == TEST_KING_ID]
    assert str(lord.kingdom_id) == TEST_KINGDOM_ID
    assert str(lord.role) == "king"
    assert lord.display_name == "Merlin"
    assert lord.in_queue is False


async def test_test_kingdom_never_consumes_the_kingdoms_quota() -> None:
    service, _store = await _launched_service()
    await service.ensure_test_kingdom()

    # kingdoms_count = 1: the player kingdom fits DESPITE Nilrem
    avalon = await service.add_kingdom("Avalon")
    assert avalon.id != TEST_KINGDOM_ID

    with pytest.raises(KingdomLimitError):
        await service.add_kingdom("Bravia")


async def test_test_kingdom_is_never_joined_or_claimed_by_players() -> None:
    service, _store = await _launched_service()
    await service.ensure_test_kingdom()

    with pytest.raises(NotEnrollableError):
        await service.enroll("111", "Bob", LordRole.LORD, "Nilrem")

    # the throne of Nilrem never appears on the claimable list
    await service.enroll_king_awaiting_kingdom("222", "Arthur")
    with pytest.raises(NotEnrollableError):
        await service.claim_kingdom("222", TEST_KINGDOM_ID)
    assert all(str(k.id) != TEST_KINGDOM_ID for k in await service.available_kingdoms())


async def test_start_season_grants_no_civilizations_to_the_test_kingdom() -> None:
    service, _store = await _launched_service()
    await service.ensure_test_kingdom()
    await service.add_kingdom("Avalon")

    await service.start_season()

    kingdoms = {str(k.id): k for k in await service.kingdoms()}
    assert len(kingdoms[TEST_KINGDOM_ID].civilizations) == 0  # admin-injected hand
    avalon = next(k for k in kingdoms.values() if k.name == "Avalon")
    assert len(avalon.civilizations) == 2  # the player kingdom draws


async def test_delete_kingdom_removes_the_test_kingdom_completely() -> None:
    service, store = await _launched_service()
    await service.ensure_test_kingdom()
    avalon = await service.add_kingdom("Avalon")

    deleted = await service.delete_kingdom(TEST_KINGDOM_ID)

    assert str(deleted.id) == TEST_KINGDOM_ID
    assert all(str(k["_id"]) != TEST_KINGDOM_ID for k in store.kingdoms)
    assert all(str(l["_id"]) != TEST_KING_ID for l in store.lords)
    # the other kingdoms and their lords survive untouched
    assert any(str(k["_id"]) == str(avalon.id) for k in store.kingdoms)

    # recreatable at any time (fresh documents, same reserved id)
    reborn = await service.ensure_test_kingdom()
    assert str(reborn.id) == TEST_KINGDOM_ID


def test_the_test_items_register_on_the_bot() -> None:
    from kingdoms.mods.kingdoms.kingdom_test import (
        KingdomTestCreateButton,
        KingdomTestDestructButton,
        KingdomTestRefreshButton,
        register_kingdom_test_items,
    )

    class _Bot:
        def __init__(self) -> None:
            self._client = discord.Client(intents=discord.Intents.none())
            self._dynamic_items: set[type] = set()

        def add_dynamic_items(self, *items: type) -> None:
            self._dynamic_items.update(items)

    bot = _Bot()
    register_kingdom_test_items(bot)  # type: ignore[arg-type]
    assert {
        KingdomTestCreateButton,
        KingdomTestDestructButton,
        KingdomTestRefreshButton,
    } <= bot._dynamic_items


class _RefreshInteraction:
    """A minimal interaction shell for the refresh callback."""

    def __init__(self, guild: Any = "guild") -> None:
        self.locale = "fr"
        self.guild = guild
        self.user = SimpleNamespace(id="42")

        class _Response:
            async def defer(self, ephemeral: bool = True) -> None:
                return None

        class _Followup:
            async def send(self, *args: Any, **kwargs: Any) -> Any:
                return SimpleNamespace(id="w")

        self.response = _Response()
        self.followup = _Followup()


def _patch_refresh_seam(
    monkeypatch: pytest.MonkeyPatch,
    kingdoms: list[Any],
) -> tuple[list[tuple[Any, Any, Any]], list[str]]:
    """Stub the persistent seam + record the provisioning calls."""
    import kingdoms.mods.kingdoms.kingdom_persistent as persistent
    import kingdoms.mods.kingdoms.kingdom_test as test_module

    provision_calls: list[tuple[Any, Any, Any]] = []
    fallback_calls: list[str] = []

    class _Service:
        async def kingdoms(self) -> list[Any]:
            return list(kingdoms)

    svc = _Service()

    async def fake_provision(guild: Any, kingdom: Any, service: Any) -> None:
        provision_calls.append((guild, kingdom, service))

    async def fake_refresh(guild: Any, kingdom_id: str) -> None:
        fallback_calls.append(str(kingdom_id))

    async def no_close(user_id: str) -> None:
        return None

    monkeypatch.setattr(test_module, "_provision_test_realm", fake_provision)
    monkeypatch.setattr(
        persistent, "_wiring", lambda: SimpleNamespace(kingdoms_service=svc, bot_admins=[])
    )
    monkeypatch.setattr(persistent, "_is_admin", lambda interaction, admins: True)
    monkeypatch.setattr(persistent, "_refresh_realm_views_for_kingdom_safe", fake_refresh)
    monkeypatch.setattr(persistent, "_close_previous_ephemeral", no_close)
    monkeypatch.setattr(persistent, "_EPHEMERAL_WINDOWS", {})
    return provision_calls, fallback_calls


async def test_refresh_rides_the_provisioning_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    """refresh-structure-v1: the click re-provisions Nilrem (not just views)."""
    from kingdoms.mods.kingdoms.kingdom_test import KingdomTestRefreshButton

    kingdom = SimpleNamespace(id=TEST_KINGDOM_ID)
    provision_calls, fallback_calls = _patch_refresh_seam(monkeypatch, [kingdom])
    button = KingdomTestRefreshButton("🔄 Actualiser")
    await button.callback(_RefreshInteraction(guild="guild"))
    # the SAME idempotent seam as the create flow, with the loaded kingdom
    assert len(provision_calls) == 1
    guild, loaded, service = provision_calls[0]
    assert guild == "guild"
    assert loaded is kingdom
    assert service is not None
    assert fallback_calls == []


async def test_refresh_falls_back_to_views_when_nilrem_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kingdoms.mods.kingdoms.kingdom_test import KingdomTestRefreshButton

    provision_calls, fallback_calls = _patch_refresh_seam(
        monkeypatch, [SimpleNamespace(id="k-3")]
    )
    button = KingdomTestRefreshButton("🔄 Actualiser")
    await button.callback(_RefreshInteraction(guild="guild"))
    assert provision_calls == []
    assert fallback_calls == [TEST_KINGDOM_ID]
