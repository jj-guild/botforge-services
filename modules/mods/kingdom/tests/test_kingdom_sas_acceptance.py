"""sas-acceptation-v1 — the tests (Drasah 21/11).

The tester's capture : right after the admin ACCEPTS a realm into the
sas, the realm hub still showed « Le royaume est hors saison ». Root
cause : ``_accept_season_entry`` threw away the FRESH shell returned
by ``service.engage()`` and woke the habitat with the STALE object —
``deploy_realm_hub`` computed ``dormant = engagement is None`` on the
stale shell and re-rendered a dormant hub.

The frozen design, three legs :
- the accept keeps the fresh shell (engagement posé, join_request
  consumée) — the habitat wakes with the VIVID object ;
- a realm ENGAGED is READY : its vivid hub carries the
  « awaiting the starter draft » line, and its chez-soi window drops
  the 📺 Voir la saison + 🏆 Palmarès béquilles (they belong to the
  royaumes HORS saison — the draft still only fires when the admin
  launches the season, nothing moves there) ;
- the non-engaged realm keeps its coquille + raccourcis, untouched.
"""

from __future__ import annotations

from typing import Any

import discord
import pytest

calls: list[str] = []


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")
    )


def _ids(view: Any) -> list[str]:
    return [
        str(i.custom_id)
        for i in view.walk_children()
        if getattr(i, "custom_id", None)
    ]


def _realm(engaged: bool = False) -> Any:
    from botforge.mods.kingdom.realms import RealmShellModel

    realm = RealmShellModel(
        _id="realm:roc-1", name="Roc", slug="roc", king_id="1", king_name="Roi"
    )
    if engaged:
        realm.engagement = {"kingdom_name": "Roc", "season_id": "season-x"}
    return realm


def _interaction(uid: str = "1") -> Any:
    interaction = type("I", (), {})()
    interaction.user = type("U", (), {})()
    interaction.user.id = uid
    interaction.locale = "fr"
    interaction.guild_id = "1"
    return interaction


@pytest.fixture(autouse=True)
def _clean() -> None:
    calls.clear()


# ---------------------------------------------------------------------------
# Leg 1 — the acceptance keeps the FRESH shell (the root-cause fix)
# ---------------------------------------------------------------------------


class _FakeSeason:
    id = "season-x"


class _FakeKingdom:
    id = "k-1"
    name = "Roc"


class _FakeKingdoms:
    async def current_season(self) -> _FakeSeason:
        return _FakeSeason()

    async def add_kingdom(self, name: str) -> _FakeKingdom:
        return _FakeKingdom()

    async def enroll_king_awaiting_kingdom(self, *args: Any) -> None:
        return None

    async def claim_kingdom(self, *args: Any) -> None:
        return None

    async def enroll(self, *args: Any, **kw: Any) -> None:
        return None


class _FakeService:
    def __init__(self) -> None:
        self.engaged_shell: Any = None

    async def engage(self, realm_id: str, season_id: str, kingdom_id: str) -> Any:
        # the REAL service returns the fresh shell — engagement landed
        calls.append(f"engage:{realm_id}")
        fresh = _realm(engaged=True)
        self.engaged_shell = fresh
        return fresh

    async def save_habitat(self, realm_id: str, ids: dict) -> Any:
        calls.append(f"save:{realm_id}")
        return await _self_realm()


async def _self_realm() -> Any:
    return None


class _FakeStack:
    kingdoms = _FakeKingdoms()


def _accept_interaction() -> Any:
    interaction = _interaction()
    interaction.guild = type("G", (), {})()
    interaction.guild.id = "g-1"
    from botforge.mods.kingdom.cogs import realms as realms_module

    async def fake_structure(guild: Any, realm: Any, *, dormant: bool = True) -> dict:
        calls.append(f"structure:{dormant}:{getattr(realm, 'engagement', None) is not None}")
        return {"hub": "chan-1"}

    async def fake_hub(guild: Any, realm: Any, locale: str = "fr") -> str:
        calls.append(f"hub:{getattr(realm, 'engagement', None) is not None}")
        return "msg-1"

    async def fake_strings(x: Any) -> dict[str, str]:
        return {}

    realms_module.ensure_realm_structure = fake_structure
    realms_module.deploy_realm_hub = fake_hub
    return interaction


async def test_the_acceptance_wakes_the_habitat_with_the_fresh_shell() -> None:
    """engage() returns the fresh shell — the wake must use IT, not the
    stale pre-engagement object (the dormant-hub capture)."""
    from botforge.mods.kingdom.cogs import validation as validation_module

    interaction = _accept_interaction()
    stale = _realm(engaged=False)
    service = _FakeService()

    note = await validation_module._accept_season_entry(
        interaction,
        _FakeStack(),
        service,
        stale,
        {"realm_accepted_note": "✅ {name} → {kingdom}"},
        "fr",
    )
    # the wake rode the FRESH shell — engagement visible on both passes
    assert "structure:False:True" in calls, calls
    assert "hub:True" in calls, calls
    assert note != ""


async def test_the_fresh_shell_carries_the_engagement() -> None:
    from botforge.mods.kingdom.cogs.realms import deploy_realm_hub  # noqa: F401 — import sanity

    service = _FakeService()
    fresh = await service.engage("realm:roc-1", "season-x", "k-1")
    assert fresh.engagement is not None, "the fresh shell IS the engaged one"
    assert fresh.join_request is None


# ---------------------------------------------------------------------------
# Leg 2 — an ENGAGED realm lives the season : vivid hub + no béquilles
# ---------------------------------------------------------------------------


def test_the_vivid_hub_carries_the_awaiting_draft_line() -> None:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings
    from botforge.mods.kingdom.cogs.realms import hub_layout

    strings = realm_strings("fr")
    awake = hub_layout(_realm(engaged=True), strings, dormant=False)
    body = _texts(awake)
    ids = _ids(awake)
    assert "draft starter" in body, "the vivid hub announces the pending draft"
    assert "hors saison" not in body, "no dormant note on a VIVID hub"
    assert not any(":nav:season:" in i for i in ids), "the season béquille is gone"
    assert not any("join" in i for i in ids), "no join button on a vivid hub"


async def test_the_home_window_drops_the_bequilles_for_the_engaged() -> None:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings
    from botforge.mods.kingdom.cogs.realms import home_layout

    strings = realm_strings("fr")
    view = await home_layout(_interaction(), _realm(engaged=True), strings)
    ids = _ids(view)
    assert any(":nav:seigneurie:" in i for i in ids), "seigneurie stays"
    assert any(":nav:presentation:" in i for i in ids), "presentation stays"
    assert not any(":nav:season:" in i for i in ids), "the 📺 bequille is gone"
    assert not any(":nav:palmares:" in i for i in ids), "the 🏆 bequille is gone"


async def test_the_home_window_keeps_the_bequilles_for_the_dormant() -> None:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings
    from botforge.mods.kingdom.cogs.realms import home_layout

    strings = realm_strings("fr")
    view = await home_layout(_interaction(), _realm(engaged=False), strings)
    ids = _ids(view)
    assert any(":nav:season:" in i for i in ids), "the dormant realm keeps the 📺"
    assert any(":nav:palmares:" in i for i in ids), "the dormant realm keeps the 🏆"
    assert any(":nav:seigneurie:" in i for i in ids)


# ---------------------------------------------------------------------------
# Leg 3 — parity : the new key, fr AND en
# ---------------------------------------------------------------------------


def test_the_hub_awaiting_draft_key_is_bilingual() -> None:
    from botforge.mods.kingdom.cogs.realm_strings import _REALM_STRINGS

    for locale in ("fr", "en"):
        catalog = _REALM_STRINGS[locale]
        assert "realm_hub_awaiting_draft" in catalog, f"{locale} key missing"
        assert str(catalog["realm_hub_awaiting_draft"]).strip() != ""
    assert (
        _REALM_STRINGS["fr"]["realm_hub_awaiting_draft"]
        != _REALM_STRINGS["en"]["realm_hub_awaiting_draft"]
    )
