"""lieux-portage-v1 — the tests (Drasah 21/11).

The portage of the reference branch's lieux-et-conseil-v1 into the new
architecture, tranche 1 (the consultation faces) :
- the ENGAGED realm's Entrée routes to « Où souhaitez-vous vous rendre ? »
  with the FIVE doors + the chez-soi door, the DORMANT realm's Entrée
  keeps its chez-soi (nothing crushed — Drasah 21/11 : « l'ancienne vue
  ne doit pas être écrasée ») ;
- every lieu window carries its illustration attachment + Sortir last ;
- the dormancy heal re-ensures the structure of every ENGAGED realm at
  each hub pass (the Blanc lesson : a salon-deny surviving the one-shot
  accept-time wake could never re-open).
"""

from __future__ import annotations

from typing import Any

import discord
import pytest

calls: list[str] = []


class _FakeResponse:
    def __init__(self) -> None:
        self.done = False
        self.defer_kwargs: dict[str, Any] = {}

    def is_done(self) -> bool:
        return self.done

    async def defer(self, **kwargs: Any) -> None:
        self.defer_kwargs = dict(kwargs)
        self.done = True


class _FakeUser:
    def __init__(self, uid: str) -> None:
        self.id = uid


def _interaction(uid: str = "1") -> Any:
    interaction = type("I", (), {})()
    interaction.user = _FakeUser(uid)
    interaction.locale = "fr"
    interaction.guild_id = "g-1"
    interaction.response = _FakeResponse()
    return interaction


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    ]


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")  # type: ignore[attr-defined]
    )


def _kingdom() -> Any:
    kingdom = type("K", (), {})()
    kingdom.id = "k-1"
    kingdom.name = "AEGIS"
    kingdom.tech_points_bank = 7
    kingdom.civilizations = ["aztecs", "britons"]
    kingdom.parish_tier = 2
    kingdom.marriage_points = 1
    kingdom.arranged_marriage_stock = 2
    kingdom.voliere_slots = ["pigeon", "corbeau"]
    kingdom.voliere_cooldowns = {"corbeau": 99999999999}
    kingdom.traquenard_until = None
    return kingdom


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    calls.clear()

    async def fake_open_entree(interaction: Any) -> None:
        calls.append("open_entree")

    import botforge.mods.kingdom.cogs.lieux as lieux_module

    monkeypatch.setattr(lieux_module, "open_entree", fake_open_entree)


# ---------------------------------------------------------------------------
# The Entrée chooser — the five doors + the chez-soi door
# ---------------------------------------------------------------------------


def test_the_entree_chooser_carries_the_five_doors_and_the_home_door() -> None:
    from botforge.mods.kingdom.cogs.lieux import entree_view, lieux_strings

    view = entree_view(lieux_strings("fr"))
    body = _texts(view)
    ids = _ids(view)
    assert "Où souhaitez-vous vous rendre ?" in body
    for kind in ("conseil", "remparts", "comptes", "paroisse", "voliere"):
        assert f"kingdoms:lieux:{kind}" in ids, f"the {kind} door must ride the chooser"
    assert "kingdoms:lieux:home" in ids, "the chez-soi door rides the second row"


def test_the_lieux_strings_carry_fr_en_parity() -> None:
    from botforge.mods.kingdom.cogs.lieux import LIEUX_STRINGS

    fr, en = LIEUX_STRINGS["fr"], LIEUX_STRINGS["en"]
    assert set(fr.keys()) == set(en.keys()), "fr and en must carry the same keys"
    for key in fr:
        assert str(fr[key]).strip() != "" and str(en[key]).strip() != ""
    assert fr["entree_title"] != en["entree_title"]


def test_the_illustrations_exist_on_disk() -> None:
    from botforge.mods.kingdom.cogs.lieux import _LIEUX_ASSETS

    for name in (
        "Royaume.png",
        "Rempart.png",
        "salle du conseil.png",
        "chambre des comptes.png",
        "paroisse1.png",
        "paroisse2.png",
        "paroisse3.png",
        "voliere.png",
    ):
        assert (_LIEUX_ASSETS / name).is_file(), f"{name} must ride assets/lieux"


# ---------------------------------------------------------------------------
# The routing — ENGAGED goes to the lieux, DORMANT keeps its chez-soi
# ---------------------------------------------------------------------------


async def test_the_engaged_realm_entry_routes_to_the_lieux(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from botforge.mods.kingdom.cogs import realms as realms_module

    realm = type("R", (), {})()
    realm.king_id = "1"
    realm.member_ids = []
    realm.engagement = {"kingdom_id": "k-1"}

    async def fake_realm_of(interaction: Any, slug: str) -> Any:
        return realm

    async def fake_open_unique(interaction: Any, **kwargs: Any) -> None:
        calls.append("home-window")

    monkeypatch.setattr(realms_module, "_realm_of", fake_realm_of)
    monkeypatch.setattr(realms_module, "open_unique_ephemeral", fake_open_unique)

    button = realms_module.RealmHomeButton("🏰 Entrée", discord.ButtonStyle.primary, "hen")
    await button.callback(_interaction("1"))
    assert calls == ["open_entree"], (
        "an ENGAGED realm's Entrée must open the lieux chooser, never the chez-soi"
    )


# ---------------------------------------------------------------------------
# The consultation windows — every lieu carries its illustration + Sortir
# ---------------------------------------------------------------------------


def test_the_voliere_window_lists_the_birds_states() -> None:
    from botforge.mods.kingdom.cogs.lieux import _voliere_window, lieux_strings

    class _FakeOpen:
        async def __call__(self, interaction: Any, **kwargs: Any) -> None:
            calls.append("opened")

    view, files = _voliere_window(lieux_strings("fr"), _kingdom())
    body = _texts(view)
    assert "Pigeon" in body and "sur son perchoir" in body
    assert "Corbeau" in body and "en vol" in body
    assert [f.filename for f in files] == ["voliere.png"]
    assert "kingdoms:lieux:sortir" in _ids(view)


def test_the_remparts_window_reads_the_live_state() -> None:
    from botforge.mods.kingdom.cogs.lieux import _remparts_window, lieux_strings

    kingdom = _kingdom()
    state = {
        "wallet": 7,
        "purchases": {"patrouille_slot_2": 14, "patrouille_unlock_1": 1, "garde_royale_stock": 2},
        "base_ai": 2,
        "territories": [],
    }
    view, files = _remparts_window(lieux_strings("fr"), kingdom, state)
    body = _texts(view)
    assert "Niveau de votre IA" in body
    assert "patrouille [2/2]" in body and "14h00" in body
    assert "patrouille [1/2]" in body
    assert "En réserve : 2" in body
    assert [f.filename for f in files] == ["rempart.png"]
    assert "kingdoms:lieux:sortir" in _ids(view)


async def test_the_paroisse_window_follows_the_palier(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    tier = type("T", (), {})()
    tier.display_name = "Église"
    tier.offering = 1
    config = type("C", (), {})()
    config.parish = type("P", (), {})()
    config.parish.tiers = (tier, tier, tier)
    monkeypatch.setattr(lieux_module, "wiring", lambda: type("S", (), {"config": config})())
    strings = lieux_module.lieux_strings("fr")
    view, files = await lieux_module._paroisse_window(strings, _kingdom(), {"wallet": 7})
    body = _texts(view)
    assert "Église" in body and "(2/3)" in body
    assert "Bague : 1" in body and "Mariage arrangé : 2" in body
    assert files and files[0].filename == "paroisse.png"  # the attachment's wire name
    assert "paroisse2" in str(getattr(files[0], "fp", "")), "the tier rides the illustration"
    assert "kingdoms:lieux:sortir" in _ids(view)


# ---------------------------------------------------------------------------
# The dormancy heal — an ENGAGED realm's structure re-ensured at each pass
# ---------------------------------------------------------------------------


async def test_the_heal_pass_reensures_the_engaged_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    realm = type("R", (), {})()
    realm.id = "realm-1"
    realm.slug = "hen"
    realm.name = "HeN"
    realm.engagement = {"kingdom_id": "k-1"}
    realm.discord = {"category": "cat-1", "hub_message": "m-1"}

    class _Channel:
        id = "chan-9"
        category_id = "cat-1"

        async def history(self, limit: int) -> Any:
            return
            yield  # pragma: no cover — async gen placeholder

    guild = type("G", (), {})()
    guild.id = "g-1"
    guild.categories = []
    guild.guilds = [guild]
    guild.categories = [type("Categ", (), {"id": "cat-1", "channels": []})]
    guild.me = type("Me", (), {"id": 99})

    async def fake_service() -> Any:
        return None

    async def fake_realms() -> list[Any]:
        return [realm]

    async def fake_structure(guild: Any, r: Any, *, dormant: bool = True) -> dict:
        calls.append(f"structure:{dormant}")
        return {"hub": "chan-9"}

    async def fake_hub(guild: Any, r: Any, locale: str = "fr") -> str:
        calls.append("hub")
        return "m-1"

    async def fake_save(realm_id: str, disc: dict) -> Any:
        calls.append("save")
        return realm

    service = type("S", (), {})()
    service.realms = fake_realms
    service.save_habitat = fake_save

    monkeypatch.setattr(realms_module, "_realm_service", lambda stack: service)
    monkeypatch.setattr(realms_module, "ensure_realm_structure", fake_structure)
    monkeypatch.setattr(realms_module, "deploy_realm_hub", fake_hub)

    class _Bot:
        guilds = [guild]

    touched = await realms_module.heal_realm_hubs(_Bot())
    assert "structure:False" in calls, "the ENGAGED realm's salons re-open at each pass"
    assert "hub" in calls
    assert touched == 1


# ---------------------------------------------------------------------------
# lieux-portage-v1-hotfix — the lord seam reads id (the player IS the id)
#
# The incident: the portal read ``lord.player_id``, a field the engine
# never had — the Roi of an ACCEPTED kingdom was read « not a lord »
# (Blanc's capture). The resolver must ride the canonical seam
# ``lord_of``/``kingdom_by_id`` — and the CB engine lord has ``id``.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_resolver_reads_the_engine_lord_by_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    class _EngineLord:  # the engine's shape: id IS the player, NO player_id
        id = "1"
        kingdom_id = "k-orc"
        left = False
        display_name = "Blanc"

    class _Kingdom:
        id = "k-orc"
        name = "Orc"

    class _Kingdoms:
        async def lords(self) -> list[Any]:
            return [_EngineLord()]

        async def kingdoms(self) -> list[Any]:
            return [_Kingdom()]

    stack = type("S", (), {})()
    stack.kingdoms = _Kingdoms()
    monkeypatch.setattr(lieux_module, "wiring", lambda: stack)
    monkeypatch.setattr(lieux_module, "open_unique_ephemeral", _record_open)

    lord, kingdom, _ = await lieux_module._lord_kingdom_of(_interaction("1"), _love_strings())
    assert lord is not None and kingdom is not None, (
        "the Roi of an accepted kingdom MUST resolve (the Blanc incident)"
    )
    assert str(kingdom.id) == "k-orc"
    assert calls == [], "no refusal note when the lord resolves"


@pytest.mark.asyncio
async def test_the_resolver_refuses_a_lord_who_left(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    class _EngineLord:
        id = "1"
        kingdom_id = "k-orc"
        left = True  # the record exists but the player LEFT the season

        display_name = "Blanc"

    class _Kingdoms:
        async def lords(self) -> list[Any]:
            return [_EngineLord()]

        async def kingdoms(self) -> list[Any]:
            return []

    stack = type("S", (), {})()
    stack.kingdoms = _Kingdoms()
    monkeypatch.setattr(lieux_module, "wiring", lambda: stack)
    monkeypatch.setattr(lieux_module, "open_unique_ephemeral", _record_open)

    lord, kingdom, _ = await lieux_module._lord_kingdom_of(_interaction("1"), _love_strings())
    assert lord is None and kingdom is None
    assert calls == ["not_lord"], "a left record is not an active lord"


def _love_strings() -> dict[str, str]:
    import botforge.mods.kingdom.cogs.lieux as lieux_module

    return lieux_module.lieux_strings("fr")


async def _record_open(interaction: Any, content: str | None = None, **kwargs: Any) -> None:
    calls.append("not_lord" if "seigneurs" in str(content or "") else str(content or "view"))
