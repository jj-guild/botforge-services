"""architecture-salons-v1 (Drasah 24/11) — la sidebar est une RÈGLE.

« Conscription, champs de bataille, Kingdom-Gaïa, puis les royaumes ;
admin TOUJOURS dernier, quoi qu'il arrive ; un royaume créé en saison
rejoint le bandeau, jamais sous admin. » L'ordre des groupes déclarés
est de la DONNÉE (les `position` du mod.yaml, bandes de 10 par groupe),
et le bandeau des royaumes est assujetti par un seam idempotent :
place_realm_categories, appelé à chaque ensure et au boot self-heal.

R6 discipline (tests/architecture/test_layering.py): a file under
modules/ OUTSIDE cogs/ never imports discord. The seams are patched
through importlib (no ``from botforge...`` line).
"""

from __future__ import annotations

import asyncio
import importlib
from types import SimpleNamespace
from typing import Any

import pytest


def _realms():
    return importlib.import_module("botforge.mods.kingdom.cogs.realms")


def _selfheal():
    return importlib.import_module("botforge.mods.kingdom.cogs.selfheal")


class FakeCategory:
    """A sidebar category — the move() calls are RECORDED."""

    def __init__(self, name: str, cid: str, position: int) -> None:
        self.name = name
        self.id = cid
        self.position = position
        self.moves: list[dict[str, Any]] = []
        self.channels: list[Any] = []
        self.deleted = False

    async def move(self, **kwargs: Any) -> None:
        self.moves.append(kwargs)

    async def delete(self, reason: str = "") -> None:
        self.deleted = True


def _guild(*categories: FakeCategory) -> Any:
    return SimpleNamespace(
        id="77",
        categories=list(categories),
        get_channel=lambda cid: next((c for c in categories if c.id == cid), None),
    )


# ---------------------------------------------------------------------------
# The declared group order is DATA (bandes de 10 par groupe)
# ---------------------------------------------------------------------------


def test_the_declared_groups_order_is_explicit_positions() -> None:
    """The channel_groups' order = the channels' `position` bands."""
    from pathlib import Path

    import yaml

    data = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "conf" / "mod.yaml").read_text(encoding="utf-8")
    )
    groups = [str(g["key"]) for g in data.get("channel_groups") or []]
    # architecture-salons-v1 : PROFILS est RETIRE de la declaration
    assert "profiles" not in groups, "the profiles group must be GONE from the declaration"
    positions = {
        str(c["key"]): int(c["position"]) for c in data.get("channels") or []
    }
    first_of = {
        group: min(positions[c["key"]] for c in data["channels"] if c["group"] == group)
        for group in ("conscription", "battlefield", "kingdom", "admin")
    }
    # conscription < champs de bataille < Kingdom-Gaïa < admin (dernier)
    assert (
        first_of["conscription"] < first_of["battlefield"] < first_of["kingdom"] < first_of["admin"]
    ), first_of
    # l'ordre interne d'admin est EXPLICITE (jamais un accident alphabétique)
    assert (
        positions["time_machine"] < positions["distributor"] < positions["console"]
        < positions["admin_log"]
    ), "admin-logs-v2: the requests salon is merged into logs"


# ---------------------------------------------------------------------------
# Le bandeau des royaumes : au-dessus d'admin, jamais en dessous
# ---------------------------------------------------------------------------


def test_the_realm_band_rides_above_admin() -> None:
    """Deux royaumes ÉGARÉS sous admin rejoignent le bandeau, l'ordre
    relatif préservé : Kingdom-Gaïa → Blanc → Aegis → admin."""
    realms = _realms()
    kingdom = FakeCategory(realms.KINGDOM_CATEGORY, "k1", 0)
    admin = FakeCategory(realms.ADMIN_CATEGORY, "a1", 5)
    home = FakeCategory("Kingdom", "h1", 6)
    blanc = FakeCategory("🏰 Blanc", "b1", 1)
    aegis = FakeCategory("🏰 Aegis", "g1", 2)
    # l'état bizarroïde : un royaume accepté au milieu de la saison est
    # tombé SOUS admin (créé en fin de sidebar)
    below = FakeCategory("🏰 Raté", "r0", 7)
    guild = _guild(kingdom, blanc, aegis, admin, below, home)

    async def _patched_stored(guild_id: str, scope: str, key: str) -> None:
        return None

    import botforge.discord.ui.panels_provisioning as pp

    original = pp.stored_channel_id
    pp.stored_channel_id = _patched_stored
    try:
        moved = asyncio.run(realms.place_realm_categories(guild))
    finally:
        pp.stored_channel_id = original

    assert moved == 3, "three realm categories join the band"
    # chaque déplacement vise JUSTE AVANT admin (le bandeau serre)
    for category in (blanc, aegis, below):
        assert category.moves, f"{category.name} must move"
        assert category.moves[-1].get("before") is admin
    # convergé : une seconde passe ne coûte AUCUN appel (fix-reset-429)
    below.moves.clear()
    blanc.moves.clear()
    aegis.moves.clear()


def test_the_converged_band_costs_no_api_call() -> None:
    """Un bandeau déjà en place ne déclenche AUCUN move()."""
    realms = _realms()
    kingdom = FakeCategory(realms.KINGDOM_CATEGORY, "k1", 0)
    elsewhere = FakeCategory("Divers", "c1", -1)
    blanc = FakeCategory("🏰 Blanc", "b1", 4)
    aegis = FakeCategory("🏰 Aegis", "g1", 5)
    admin = FakeCategory(realms.ADMIN_CATEGORY, "a1", 6)
    home = FakeCategory("Kingdom", "h1", 7)
    guild = _guild(elsewhere, kingdom, blanc, aegis, admin, home)

    import botforge.discord.ui.panels_provisioning as pp

    async def _patched_stored(guild_id: str, scope: str, key: str) -> None:
        return None

    original = pp.stored_channel_id
    pp.stored_channel_id = _patched_stored
    try:
        moved = asyncio.run(realms.place_realm_categories(guild))
    finally:
        pp.stored_channel_id = original

    assert moved == 0, "the band already rides above admin"
    assert not blanc.moves and not aegis.moves and not admin.moves


def test_a_new_realm_adopts_the_band_at_its_first_breath() -> None:
    """ensure_realm_structure resserre la règle : le bandeau est
    ré-asserté à chaque ensure (règle sine qua non vu de l'habitat)."""
    realms = _realms()
    admins_seen: list[str] = []

    async def _fake_place(guild: Any) -> int:
        admins_seen.append(str(getattr(guild, "id", "")))
        return 1

    original_place = realms.place_realm_categories
    original_overwrites = realms.realm_overwrites
    realms.place_realm_categories = _fake_place

    async def _no_overwrites(guild: Any, member_ids: list[int], **kwargs: Any) -> dict:
        return {}

    realms.realm_overwrites = _no_overwrites
    category = FakeCategory("🏰 Neuf", "n1", 3)
    guild = _guild(category)
    realm = SimpleNamespace(id="9", name="Neuf", king_id="1", member_ids=[], discord={})
    try:
        asyncio.run(realms.ensure_realm_structure(guild, realm, dormant=True))
    finally:
        realms.place_realm_categories = original_place
        realms.realm_overwrites = original_overwrites
    assert admins_seen == ["77"], "every ensure re-asserts the realm band"


def test_no_admin_no_band_a_dead_folder_never_crashes() -> None:
    """Sans catégorie admin (un guild sans provision), zéro geste, zéro crash."""
    realms = _realms()
    guild = _guild(FakeCategory(realms.KINGDOM_CATEGORY, "k1", 0), FakeCategory("🏰 Blanc", "b1", 1))
    assert asyncio.run(realms.place_realm_categories(guild)) == 0


# ---------------------------------------------------------------------------
# Le boot self-heal rattrape la sidebar vivante
# ---------------------------------------------------------------------------


def test_the_boot_pass_places_the_band_and_sweeps_profiles(monkeypatch) -> None:
    """Le rattrapage : le bandeau est resserré et la catégorie vide
    legacy PROFILS est balayée — un PROFILS HABITÉ reste intouché."""
    selfheal = _selfheal()
    placed: list[Any] = []

    async def fake_place(guild: Any) -> int:
        placed.append(guild)
        return 2

    tails: list[Any] = []

    async def fake_enforce(bot: Any) -> int:
        tails.append(bot)
        return 0

    realms = _realms()
    monkeypatch.setattr(realms, "place_realm_categories", fake_place)
    import botforge.discord.ui.panels_provisioning as pp

    monkeypatch.setattr(pp, "enforce_bottom_categories", fake_enforce)

    empty_profiles = FakeCategory(selfheal.RETIRED_PROFILES_CATEGORY, "p1", 2)
    empty_profiles.channels = []
    lived_profiles = FakeCategory(selfheal.RETIRED_PROFILES_CATEGORY, "p2", 3)
    lived_profiles.channels = [SimpleNamespace(name="résidu")]
    guild = SimpleNamespace(id="111", categories=[empty_profiles, lived_profiles], tree=None)

    async def fake_ensure_mod_pins(bot: Any, guild_id: str, name: str) -> int:
        return 3

    import botforge.discord.scope_pins as scope_pins

    monkeypatch.setattr(scope_pins, "ensure_mod_pins", fake_ensure_mod_pins)
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "on")
    # the provisioning seams are mocked empty (this test owns the sweep only)
    import botforge.discord.mods_forum as mods_forum

    async def fake_channels(bot: Any, guild_id: str, name: str) -> int:
        return 0

    async def fake_roles(bot: Any, guild_id: str, name: str) -> int:
        return 0

    monkeypatch.setattr(mods_forum, "provision_mod_channels", fake_channels)
    monkeypatch.setattr(mods_forum, "provision_mod_roles", fake_roles)
    bot = SimpleNamespace(guilds=[guild], tree=SimpleNamespace())

    asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert placed == [guild], "the boot pass re-asserts the realm band"
    assert tails, "the boot pass re-asserts the declared tail (admin, home, plumbing)"
    assert empty_profiles.deleted, "the EMPTY retired PROFILS is swept"
    assert not lived_profiles.deleted, "an inhabited PROFILS stays untouched"


def test_the_reporting_stays_stable_when_the_provisioning_is_off(monkeypatch) -> None:
    """Provision off ⇒ le résumé gardee la même forme (pas de geste)."""
    selfheal = _selfheal()

    async def fake_ensure_mod_pins(bot: Any, guild_id: str, name: str) -> int:
        return 4

    import botforge.discord.scope_pins as scope_pins

    monkeypatch.setattr(scope_pins, "ensure_mod_pins", fake_ensure_mod_pins)
    monkeypatch.setenv("BOTFORGE_KINGDOM_BOOT_PROVISION", "off")
    bot = SimpleNamespace(guilds=[SimpleNamespace(id=111, categories=None)], tree=SimpleNamespace(
        fetch_commands=None,
    ))
    out = asyncio.run(selfheal.ensure_kingdom_surfaces(bot))
    assert out[0][1] == "provisioning: off; 4 pins, commands: error"


@pytest.mark.asyncio
async def test_dynamic_channel_resolves_the_client_the_library_exposes(monkeypatch) -> None:
    """salon-dynamique-client-v1 (Drasah 24/11, incident « j'ai pas eu
    le salon qui s'écrit ») : the vendored discord.py has NO
    ``Guild.client`` — the seam must reach the client through the
    connection state's ``_get_client()`` or EVERY dynamic channel
    (attack salon, battle room, FFA salon) is silently skipped."""
    from botforge.mods.kingdom.cogs.common import open_dynamic_channel_safe

    import botforge.discord.dynamic_channels as dyn

    seized: dict[str, Any] = {}

    class _FakePlatform:
        def __init__(self, client: Any) -> None:
            seized["client"] = client

        async def create_channel(self, guild_id: str, name: str, **kwargs: Any) -> Any:
            seized.update(guild_id=guild_id, name=name)
            return SimpleNamespace(id=42)

    monkeypatch.setattr(dyn, "DiscordDynamicChannelsPlatform", _FakePlatform)

    state = SimpleNamespace(_get_client=lambda: "the-client")
    guild = SimpleNamespace(id="77", _state=state)  # NO `client` attr — the vendor's guild
    channel = await open_dynamic_channel_safe(guild, "🗡️-blank-vs-hen")
    assert channel is not None and channel.id == 42
    assert seized["client"] == "the-client", "the client rides the state's _get_client"
    assert seized["name"] == "🗡️-blank-vs-hen"
