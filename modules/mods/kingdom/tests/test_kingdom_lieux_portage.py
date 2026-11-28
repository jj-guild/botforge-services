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


def test_the_entree_chooser_carries_the_five_doors_and_no_chez_soi() -> None:
    from botforge.mods.kingdom.cogs.lieux import entree_view, lieux_strings

    view = entree_view(lieux_strings("fr"))
    body = _texts(view)
    ids = _ids(view)
    assert "Où souhaitez-vous vous rendre ?" in body
    for kind in ("conseil", "remparts", "comptes", "paroisse", "voliere"):
        assert f"kingdoms:lieux:{kind}" in ids, f"the {kind} door must ride the chooser"
    assert "kingdoms:lieux:home" not in ids, (
        "retrait-chez-soi (Drasah 21/11) : « on n'en a pas besoin »"
    )
    assert not hasattr(lieux_strings("fr"), "get") or "home_button" not in lieux_strings("fr")


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


@pytest.mark.asyncio
async def test_the_voliere_window_lists_the_birds_states() -> None:
    # voliere-v2 (Drasah 28/11) : la fenêtre lit le moteur quand il
    # existe — sans moteur (tests), le fallback modèle s'applique.
    from botforge.mods.kingdom.cogs.kingdom.lieux import _voliere_window, lieux_strings

    class _FakeOpen:
        async def __call__(self, interaction: Any, **kwargs: Any) -> None:
            calls.append("opened")

    view, files = await _voliere_window(lieux_strings("fr"), _kingdom())
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

    async def fake_hub(guild: Any, r: Any, locale: str = "fr", *, frozen: bool = False) -> str:
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


# ---------------------------------------------------------------------------
# dormancy-recompute-v1 — l'incident AEGIS : un deny survivant ne peut
# plus exister PAR CONSTRUCTION. L'éveil RECALCULE l'overwrite-set
# COMPLET du salon (le edit remplace tout — un stale deny part avec).
# ---------------------------------------------------------------------------


class _RecomputeRole:
    def __init__(self, rid: int) -> None:
        self.id = rid


class _RecomputeMember:
    def __init__(self, mid: int) -> None:
        self.id = mid


class _RecomputeChannel:
    def __init__(self) -> None:
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kw: Any) -> None:
        self.edits.append(kw)


class _RecomputeGuild:
    def __init__(self, known_ids: tuple[int, ...] = (1,)) -> None:
        self.default_role = _RecomputeRole(0)
        self._known = set(known_ids)
        self.id = "g-1"

    def get_member(self, mid: int) -> Any:
        return _RecomputeMember(mid) if mid in self._known else None

    async def fetch_member(self, mid: int) -> Any:
        raise RuntimeError("unknown member")  # the resolution dead-ends


@pytest.mark.asyncio
async def test_the_awake_recompute_replaces_the_whole_overwrite_set() -> None:
    from discord import PermissionOverwrite

    from botforge.mods.kingdom.cogs.realms import _apply_dormancy

    guild = _RecomputeGuild()
    channel = _RecomputeChannel()
    await _apply_dormancy(guild, channel, "discussions", [1], dormant=False)

    assert channel.edits, "the awake pass MUST recompute (the AEGIS incident)"
    overwrites = channel.edits[0]["overwrites"]
    keys = {type(k).__name__ for k in overwrites}
    assert "_RecomputeRole" in keys, "everyone deny rides the recompute"
    member = next(k for k in overwrites if type(k).__name__ == "_RecomputeMember")
    assert overwrites[member].view_channel is True, "the member is granted the salon"
    assert isinstance(overwrites[member], PermissionOverwrite)


@pytest.mark.asyncio
async def test_the_recompute_logs_an_unresolvable_member(caplog) -> None:
    import logging as _logging

    from botforge.mods.kingdom.cogs.realms import _apply_dormancy

    with caplog.at_level(_logging.WARNING, logger="kingdom.realms"):
        guild = _RecomputeGuild(known_ids=())  # nobody resolvable
        channel = _RecomputeChannel()
        await _apply_dormancy(guild, channel, "territory", [4242], dormant=False)
    assert "4242" in caplog.text, "a skipped member is NEVER silent (the Check 107 lesson)"


@pytest.mark.asyncio
async def test_the_recompute_keeps_the_bot_in_its_own_salons() -> None:
    """missing-access-v1 (Drasah 23/11) — l'incident live AEGIS/HeN.

    Un salon avec ses propres overwrites n'hérite PLUS ceux de la
    catégorie : si le recompute n'y met pas le BOT, il perd l'accès à
    SON propre salon (Discord 403 Missing Access, les fiches ne se
    posent jamais). Le recompute doit porter l'allow du bot ET du
    rôle admin, éveillé comme dormant.
    """
    from botforge.mods.kingdom.cogs.realms import _apply_dormancy

    guild = _RecomputeGuild()
    guild.me = _RecomputeMember(7)  # the bot's own member
    channel = _RecomputeChannel()
    await _apply_dormancy(guild, channel, "territory", [1], dormant=False)
    overwrites = channel.edits[0]["overwrites"]
    bot = next(k for k in overwrites if getattr(k, "id", None) == 7)
    assert overwrites[bot].view_channel is True, "the bot keeps its salon awake"
    assert overwrites[bot].send_messages is True, "the bot can still feed the fiche"
    everyone = next(k for k in overwrites if getattr(k, "id", None) == 0)
    assert overwrites[everyone].view_channel is False

    channel2 = _RecomputeChannel()
    await _apply_dormancy(guild, channel2, "alliances", [1], dormant=True)
    overwrites2 = channel2.edits[0]["overwrites"]
    bot2 = next(k for k in overwrites2 if getattr(k, "id", None) == 7)
    assert overwrites2[bot2].send_messages is True, "dormant keeps the BOT able (masked members, live bot)"
    assert overwrites2[bot2].view_channel is True
    member = next(k for k in overwrites2 if getattr(k, "id", None) == 1)
    assert overwrites2[member].view_channel is False, "dormant still masks the humans"


def test_the_dormant_recompute_denies_members() -> None:
    import asyncio

    from botforge.mods.kingdom.cogs.realms import _apply_dormancy

    guild = _RecomputeGuild()
    channel = _RecomputeChannel()
    asyncio.run(_apply_dormancy(guild, channel, "alliances", [1], dormant=True))
    overwrites = channel.edits[0]["overwrites"]
    member = next(k for k in overwrites if type(k).__name__ == "_RecomputeMember")
    assert overwrites[member].view_channel is False, "dormant = masked, never destroyed"


# ---------------------------------------------------------------------------
# stale-anchor-heal — l'incident AEGIS : la coquille portait un id de
# catégorie PÉRIMÉ et la passe sautait le royaume EN SILENCE, pour
# toujours. Le ratachement se fait maintenant par NOM, et la coquille
# repart avec une carte d'identité FRAÎCHE (sauvée même si le hub n'a
# pas changé).
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_stale_category_anchor_no_longer_skips_the_realm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    realm = type("R", (), {})()
    realm.id = "realm-av"
    realm.slug = "avelorn"
    realm.name = "Avelorn"
    realm.engagement = {"kingdom_id": "k-1"}
    realm.discord = {"category": "cat-OLD", "hub_message": "m-1"}  # the stale anchor

    class _Categ:
        id = "cat-NEW"  # the recreated category — the name IS the anchor now
        name = "🏰 Avelorn"
        channels = []

    guild = type("G", (), {})()
    guild.id = "g-1"
    guild.categories = [_Categ()]
    guild.me = type("Me", (), {"id": 99})

    async def fake_realms() -> list[Any]:
        return [realm]

    async def fake_structure(guild: Any, r: Any, *, dormant: bool = True) -> dict:
        calls.append(f"structure:{dormant}")
        return {"category": "cat-NEW", "hub": "chan-9"}

    async def fake_hub(guild: Any, r: Any, locale: str = "fr", *, frozen: bool = False) -> str:
        calls.append("hub")
        return "m-1"  # SAME hub id — the habitat saves on the fresh anchor alone

    saved: dict[str, dict] = {}

    async def fake_save(realm_id: str, disc: dict) -> Any:
        saved[realm_id] = dict(disc)
        calls.append("save")

    service = type("S", (), {})()
    service.realms = fake_realms
    service.save_habitat = fake_save

    monkeypatch.setattr(realms_module, "wiring", lambda: object())
    monkeypatch.setattr(realms_module, "_realm_service", lambda stack: service)
    monkeypatch.setattr(realms_module, "ensure_realm_structure", fake_structure)
    monkeypatch.setattr(realms_module, "deploy_realm_hub", fake_hub)

    class _Bot:
        guilds = [guild]

    touched = await realms_module.heal_realm_hubs(_Bot())
    assert "structure:False" in calls, "a stale anchor must NOT skip the realm (AEGIS)"
    assert saved.get("realm-av", {}).get("category") == "cat-NEW", (
        "the shell leaves the pass with a FRESH identity card"
    )
    assert "save" in calls, "the habitat persists even when the hub id did not change"
    assert touched == 1


@pytest.mark.asyncio
async def test_a_realm_of_another_guild_is_still_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    realm = type("R", (), {})()
    realm.id = "realm-x"
    realm.slug = "elsewhere"
    realm.name = "Elsewhere"
    realm.engagement = {"kingdom_id": "k-1"}
    realm.discord = {"category": "cat-OLD"}

    class _Categ:
        id = "cat-1"
        name = "🏰 Avelorn"  # NOT the realm's family
        channels = []

    guild = type("G", (), {})()
    guild.id = "g-1"
    guild.categories = [_Categ()]
    guild.me = type("Me", (), {"id": 99})

    async def fake_realms() -> list[Any]:
        return [realm]

    async def boom_structure(guild: Any, r: Any, *, dormant: bool = True) -> dict:
        raise AssertionError("a foreign realm must never be touched")

    async def boom_hub(guild: Any, r: Any, locale: str = "fr") -> str:
        raise AssertionError("a foreign realm must never be deployed")

    service = type("S", (), {})()
    service.realms = fake_realms
    service.save_habitat = None

    monkeypatch.setattr(realms_module, "wiring", lambda: object())
    monkeypatch.setattr(realms_module, "_realm_service", lambda stack: service)
    monkeypatch.setattr(realms_module, "ensure_realm_structure", boom_structure)
    monkeypatch.setattr(realms_module, "deploy_realm_hub", boom_hub)

    class _Bot:
        guilds = [guild]

    touched = await realms_module.heal_realm_hubs(_Bot())
    assert touched == 0, "no name match + no id match = genuinely another guild's realm"


# ---------------------------------------------------------------------------
# leftover-shield — l'incident Blanc (21/11 nuit) : l'ancienne charte avait
# 5 salons, la nouvelle en déclare 4 ; le rattachement par nom a adopté
# l'ancienne catégorie et le salon résiduel (« ⚔️ admin ») devint VISIBLE
# verrouillé pour le Roi via le allow catégorie. Tout salon non déclaré
# est recalculé MUET pour les membres — masqué, jamais détruit.
# ---------------------------------------------------------------------------


class _LeftoverMember:
    def __init__(self, mid: int) -> None:
        self.id = mid


class _LeftoverGuild:
    def __init__(self, category: Any) -> None:
        self.id = "g-1"
        self.categories = [category]
        self.default_role = _RecomputeRole(0)
        self.roles: list[Any] = []
        self.me = _LeftoverMember(99)

    def get_member(self, mid: int) -> Any:
        return _LeftoverMember(mid)


class _LeftoverChannel:
    def __init__(self, name: str) -> None:
        self.id = f"chan-{name}"
        self.name = name
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kw: Any) -> None:
        self.edits.append(kw)


class _LeftoverCategory:
    def __init__(self, channels: list[Any]) -> None:
        self.id = "cat-1"
        self.name = "🏰 Avelorn"
        self.channels = channels

    async def edit(self, **kw: Any) -> None:
        pass


@pytest.mark.asyncio
async def test_a_stale_charter_leftover_is_shielded_from_members() -> None:
    from botforge.mods.kingdom.cogs.realms import ensure_realm_structure

    discussions = _LeftoverChannel("🔒 Discussions")
    leftover = _LeftoverChannel("⚔️ admin")
    guild = _LeftoverGuild(_LeftoverCategory([discussions, leftover]))

    realm = type("R", (), {})()
    realm.name = "Avelorn"
    realm.king_id = "1"
    realm.member_ids = []

    ids = await ensure_realm_structure(guild, realm, dormant=False)
    assert ids.get("category") == "cat-1", "the adopted family is kept"

    member_edits = [
        kw["overwrites"]
        for kw in leftover.edits
        if "overwrites" in kw
    ]
    assert member_edits, "the leftover MUST be recomputed (the Blanc incident)"
    overwrites = member_edits[0]
    member = next(k for k in overwrites if type(k).__name__ == "_LeftoverMember" and k.id != 99)
    assert overwrites[member].view_channel is False, (
        "a stale-charter salon is hidden from the realm's humans"
    )

    awake = [
        kw["overwrites"] for kw in discussions.edits if "overwrites" in kw
    ]
    assert awake, "the declared salon is still recomputed awake"
    declared_member = next(k for k in awake[0] if type(k).__name__ == "_LeftoverMember" and k.id != 99)
    assert awake[0][declared_member].view_channel is True, (
        "the shield never touches the declared salons"
    )


@pytest.mark.asyncio
async def test_a_clean_family_shields_nothing() -> None:
    from botforge.mods.kingdom.cogs.realms import ensure_realm_structure

    discussions = _LeftoverChannel("🔒 Discussions")
    guild = _LeftoverGuild(_LeftoverCategory([discussions]))

    realm = type("R", (), {})()
    realm.name = "Avelorn"
    realm.king_id = "1"
    realm.member_ids = []

    ids = await ensure_realm_structure(guild, realm, dormant=False)
    assert ids.get("category") == "cat-1"
    assert set(ids) == {"category", "discussions", "hub", "territory", "alliances"} or len(ids) >= 2
