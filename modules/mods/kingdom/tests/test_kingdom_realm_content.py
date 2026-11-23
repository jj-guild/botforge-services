"""realm-content-v1 — the tests (Drasah 21/11).

The portage of the diverged branch's salon feeding into the new
architecture, vague 1 :
- l'ORDRE des salons d'une catégorie royaume forcé (Discussions → Le
  royaume → Territoire → Alliances), zéro appel API quand convergé ;
- chaque salon porte SES messages marqués — l'upsert édite en place,
  purge les doublons, ne recrée que ce qui manque ;
- la bienvenue RP de Discussions part UNE fois (le marker gouverne) ;
- Territoire affiche l'état d'attente au sas, la fiche réelle après le
  départ ; Alliances porte son panneau + SES quatre boutons ;
- l'épinglé 🎯 de Discussions suit les objectifs du moteur.
"""

from __future__ import annotations

from typing import Any

import pytest

calls: list[str] = []


class _Message:
    def __init__(self, mid: str, content: str) -> None:
        self.id = mid
        self.content = content
        self.edits = 0
        self.deleted = False
        self.pinned = False

    async def edit(self, **kwargs: Any) -> None:
        self.content = str(kwargs.get("content", self.content))
        self.edits += 1

    async def delete(self) -> None:
        self.deleted = True
        if self in self._channel.history_msgs:
            self._channel.history_msgs.remove(self)

    async def pin(self) -> None:
        self.pinned = True


class _Channel:
    def __init__(self, name: str, messages: list[_Message] | None = None) -> None:
        self.id = f"chan-{name}-{len(messages or [])}"
        self.name = name
        self.messages = list(messages or [])
        self.space = 1 if not self.messages else 0
        self.history_msgs = list(self.messages)
        for message in self.history_msgs:
            message._channel = self

    async def history(self, limit: int) -> Any:
        for message in list(self.history_msgs):
            yield message

    async def send(self, content: str = "", view: Any = None, **kwargs: Any) -> _Message:
        message = _Message(f"m-new-{len(self.history_msgs) + 1}", content)
        message.view = view
        message._channel = self
        self.history_msgs.append(message)
        self.messages.append(message)
        calls.append("send")
        return message


class _Realm:
    def __init__(self, disc: dict[str, Any] | None = None) -> None:
        self.id = "realm-1"
        self.name = "Avelorn"
        self.king_id = "7"
        self.member_ids = ["7"]
        self.discord = dict(disc or {})
        self.engagement = {"kingdom_id": "k-1"}


class _Kingdom:
    def __init__(self) -> None:
        self.id = "k-1"
        self.name = "AEGIS"
        self.civilizations = ["aztecs"]
        self.civilization_acquisitions = {"aztecs": {"origin": "starter", "at": 100}}
        self.council_objectives = {"target_kingdom": "k-2", "target_kingdom_label": "Orcs"}


def _guild(channels: dict[str, _Channel]) -> Any:
    guild = type("G", (), {})()
    guild.id = "g-1"

    def get_channel(cid: Any) -> Any:
        return channels.get(str(cid))

    guild.get_channel = get_channel
    guild.channels = list(channels.values())
    guild.categories = []
    return guild


@pytest.fixture(autouse=True)
def _clean() -> None:
    calls.clear()


# ---------------------------------------------------------------------------
# L'ORDRE des salons — l'ordre FAIT PARTIE de la charte
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_realm_salons_are_reordered_to_the_charter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    positions: dict[str, int] = {}

    class _C:
        def __init__(self, name: str, slug: str) -> None:
            self.name = name
            self._slug = slug

        async def edit(self, **kwargs: Any) -> None:
            positions[self._slug] = int(kwargs.get("position", -1))

    # live order scrambled : Alliances, Territoire, Discussions, hub
    live = [
        _C("🏆 Alliances", "alliances"),
        _C("🌍 Territoire", "territoire"),
        _C("🔒 Discussions", "discussions"),
        _C("🏰 Le royaume", "le-royaume"),
    ]
    category = type("Cat", (), {})()
    category.id = "cat-1"
    category.name = "🏰 Avelorn"
    category.channels = live
    category_history: list[Any] = []

    async def noop(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(realms_module, "_apply_category_overwrites", noop)
    monkeypatch.setattr(realms_module, "_apply_dormancy", noop)
    monkeypatch.setattr(realms_module, "_shield_leftover", noop)
    async def _adopt(g: Any, c: Any, n: str, *, stored: str = "") -> Any:
        return next((ch for ch in c.channels if ch.name == n), None)

    monkeypatch.setattr(realms_module, "_adopt_realm_salon", _adopt)

    class _Guild:
        id = "g-1"

        def get_channel(self, cid: str) -> None:  # stale ids resolvable by name
            return None

        @property
        def channels(self) -> list[Any]:
            return []

        @property
        def categories(self) -> list[Any]:
            return [category]


    realm = _Realm({"category": "cat-1"})
    ids = await realms_module.ensure_realm_structure(_Guild(), realm, dormant=False)
    assert ids.get("category") == "cat-1"
    # the charter order, positions 0..3
    assert positions == {"discussions": 0, "le-royaume": 1, "territoire": 2, "alliances": 3}, (
        "l'ordre des salons est la charte : Discussions → Le royaume →"
        " Territoire → Alliances"
    )


@pytest.mark.asyncio
async def test_a_converged_order_costs_zero_api_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    edits: list[str] = []

    class _C:
        def __init__(self, name: str, slug: str) -> None:
            self.name = name
            self._slug = slug

        async def edit(self, **kwargs: Any) -> None:
            edits.append(self._slug)

    live = [
        _C("🔒 Discussions", "discussions"),
        _C("🏰 Le royaume", "le-royaume"),
        _C("🌍 Territoire", "territoire"),
        _C("🏆 Alliances", "alliances"),
    ]
    category = type("Cat", (), {})()
    category.id = "cat-1"
    category.name = "🏰 Avelorn"
    category.channels = live

    async def noop(*args: Any, **kwargs: Any) -> None:
        return None

    monkeypatch.setattr(realms_module, "_apply_category_overwrites", noop)
    monkeypatch.setattr(realms_module, "_apply_dormancy", noop)
    monkeypatch.setattr(realms_module, "_shield_leftover", noop)
    async def _adopt(g: Any, c: Any, n: str, *, stored: str = "") -> Any:
        return next((ch for ch in c.channels if ch.name == n), None)

    monkeypatch.setattr(realms_module, "_adopt_realm_salon", _adopt)

    class _Guild:
        id = "g-1"

        def get_channel(self, cid: str) -> None:
            return None

        @property
        def channels(self) -> list[Any]:
            return []

        @property
        def categories(self) -> list[Any]:
            return [category]

    await realms_module.ensure_realm_structure(_Guild(), _Realm({"category": "cat-1"}), dormant=False)
    assert edits == [], "un ordre déjà convergé ne coûte AUCUN appel API"


# ---------------------------------------------------------------------------
# The marked-message upsert — edit in place, purge duplicates, send once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_upsert_edits_in_place_and_never_duplicates() -> None:
    from botforge.mods.kingdom.cogs.realm_content import _marker, _upsert_marked

    existing = _Message("m-1", f"old fr\n{_marker('territory')}")
    duplicate = _Message("m-2", f"orphan copy\n{_marker('territory')}")
    channel = _Channel("🌍 Territoire", [existing, duplicate])

    fresh = f"fresh body\n{_marker('territory')}"
    first = await _upsert_marked(channel, "territory", fresh)
    assert first == "m-1" and existing.edits == 1, "the marked message is edited in place"
    assert "fresh body" in existing.content
    assert duplicate.deleted, "a duplicate marker is purged"
    assert calls == [], "no send happens while a marked message lives"

    second = await _upsert_marked(channel, "territory", fresh + " 2")
    assert second == "m-1" and existing.edits == 2 and calls == []


@pytest.mark.asyncio
async def test_the_upsert_resends_when_the_channel_is_empty() -> None:
    from botforge.mods.kingdom.cogs.realm_content import _marker, _upsert_marked

    channel = _Channel("🌍 Territoire")
    mid = await _upsert_marked(channel, "territory", f"body\n{_marker('territory')}")
    assert calls == ["send"] and mid.startswith("m-new-")


# ---------------------------------------------------------------------------
# La bienvenue RP — ONE marker, never stacked
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_welcome_deploys_once_then_edits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realm_content as content

    realm = _Realm(
        {
            "discussions": "101",
            "territory": "102",
            "alliances": "103",
        }
    )
    disc = _Channel("🔒 Discussions")
    terr = _Channel("🌍 Territoire")
    alli = _Channel("🏆 Alliances")
    guild = _guild({"101": disc, "102": terr, "103": alli})

    class _Stack:
        class kingdoms:  # noqa: N801 — the season seam
            @staticmethod
            async def current_season() -> None:
                return None

    monkeypatch.setattr(content, "wiring", lambda: _Stack())

    kingdom = _Kingdom()
    ids = await content.deploy_realm_welcome(guild, realm, kingdom, "fr")
    assert ids.get("welcome_message") and calls == ["send"]
    assert "bienvenue au foyer du royaume" in disc.history_msgs[0].content
    assert content._marker("welcome") in disc.history_msgs[0].content

    calls.clear()
    ids2 = await content.deploy_realm_welcome(guild, realm, kingdom, "fr")
    assert calls == [], "the welcome never duplicates — the marker governs"
    assert ids2.get("welcome_message") == ids["welcome_message"]


# ---------------------------------------------------------------------------
# Territoire — l'état d'attente au sas, la fiche réelle après le départ
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_territory_sheet_waits_in_setup_then_shows_the_lands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realm_content as content

    realm = _Realm(
        {"discussions": "101", "territory": "102", "alliances": "103"}
    )
    terr = _Channel("🌍 Territoire")
    alli = _Channel("🏆 Alliances")
    disc = _Channel("🔒 Discussions")
    guild = _guild({"101": disc, "102": terr, "103": alli})

    season = type("Season", (), {})()
    season.phase = "setup"

    class _Stack:
        class config:  # noqa: N801
            maps = ()
            civilizations = ()

        class kingdoms:  # noqa: N801
            @staticmethod
            async def current_season() -> Any:
                return season

            @staticmethod
            async def lords() -> list[Any]:
                return []

            @staticmethod
            async def kingdoms() -> list[Any]:
                return []

    monkeypatch.setattr(content, "wiring", lambda: _Stack())

    ids = await content.deploy_realm_content(guild, realm, _Kingdom(), "fr")
    assert calls == ["send", "send"], "Territoire then Alliances deploy at the acceptance"
    body = terr.history_msgs[0].content
    assert "La carte reste secrète" in body, "setup = the pending state, not the lands"
    assert "distribution au lancement" not in body or "lancement" in body

    # FICTION the departure: the season flips to started, one map owned
    calls.clear()
    season.phase = "started"

    class _Terr:
        map_key = "arabia"
        owner_kingdom_id = "k-1"
        protected_until = None
        cathedral_until = None

    class _Territories:
        @staticmethod
        async def territories() -> list[Any]:
            return [_Terr()]

    _Stack.territories = _Territories
    entry = type("Map", (), {})()
    entry.key = "arabia"
    entry.display_name = "Arabie"
    _Stack.config.maps = (entry,)

    ids2 = await content.deploy_realm_content(guild, realm, _Kingdom(), "fr")
    assert calls == [], "a marked sheet is EDITED at the departure, never stacked"
    assert "Arabie" in terr.history_msgs[0].content, "the real lands show after the start"
    assert ids2["territory_message"] == ids["territory_message"]


# ---------------------------------------------------------------------------
# Alliances — le panneau unifié + SES QUATRE boutons restart-proof
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_alliances_panel_carries_her_four_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realm_content as content

    realm = _Realm(
        {"discussions": "101", "territory": "102", "alliances": "103"}
    )
    terr = _Channel("🌍 Territoire")
    alli = _Channel("🏆 Alliances")
    disc = _Channel("🔒 Discussions")
    guild = _guild({"101": disc, "102": terr, "103": alli})

    season = type("Season", (), {})()
    season.phase = "setup"

    class _Stack:
        class config:  # noqa: N801
            maps = ()
            civilizations = ()

        class kingdoms:  # noqa: N801
            @staticmethod
            async def current_season() -> Any:
                return season

            @staticmethod
            async def lords() -> list[Any]:
                return []

            @staticmethod
            async def kingdoms() -> list[Any]:
                return []

    monkeypatch.setattr(content, "wiring", lambda: _Stack())
    ids = await content.deploy_realm_content(guild, realm, _Kingdom(), "fr")
    custom_ids = [
        str(getattr(item, "custom_id", ""))
        for item in alli.history_msgs[0].view.walk_children()  # type: ignore[attr-defined]
    ]
    for kind in ("next", "locked", "durations", "history"):
        assert f"kingdom:realm:alliances:{kind}" in custom_ids, (
            f"the alliances panel's {kind} button is restart-proof"
        )


@pytest.mark.asyncio
async def test_the_alliances_panel_is_v2_legal_no_naked_button_at_the_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """alliances-panel-v2-fix (live incident 23/11 10:12): a Components
    V2 message only accepts types (1, 9, 10, 12, 13, 14, 17) at the
    ROOT of ``components`` — a bare Button (type 2) there is rejected
    with 400 Invalid Form Body and the 🏆 salon stayed empty forever
    (the only sheet of the cycle carrying buttons). The panel's four
    buttons must ride inside an ActionRow, the reference's rule."""
    import botforge.mods.kingdom.cogs.realm_content as content

    realm = _Realm(
        {"discussions": "101", "territory": "102", "alliances": "103"}
    )
    alli = _Channel("🏆 Alliances")
    guild = _guild({"101": _Channel("🔒 Discussions"),
                    "102": _Channel("🌍 Territoire"),
                    "103": alli})

    class _Stack:
        class config:  # noqa: N801
            maps = ()  # type: ignore[var-annotated]
            civilizations = ()  # type: ignore[var-annotated]

        class kingdoms:  # noqa: N801
            @staticmethod
            async def current_season() -> Any:
                return type("S", (), {"phase": "started", "name": "Bêta 1"})()

            @staticmethod
            async def lords() -> list[Any]:
                return []

            @staticmethod
            async def kingdoms() -> list[Any]:
                return []

    monkeypatch.setattr(content, "wiring", lambda: _Stack())
    await content.deploy_realm_content(guild, realm, _Kingdom(), "fr")
    panel = alli.history_msgs[0]
    view = panel.view
    allowed = {1, 9, 10, 12, 13, 14, 17}
    top = [c.get("type") for c in view.to_components()]  # type: ignore[union-attr]
    assert all(t in allowed for t in top), (
        f"a naked component at the root would be 400-rejected: {top}"
    )
    row = next(
        channel for channel in view.to_components()  # type: ignore[union-attr]
        if channel.get("type") == 1
    )
    kids = row.get("components", [])
    assert len(kids) == 4 and all(k.get("type") == 2 for k in kids), (
        "the four buttons stay clickable inside their ActionRow"
    )


# ---------------------------------------------------------------------------
# L'épinglé 🎯 — le résumé suit les objectifs du moteur
# ---------------------------------------------------------------------------


def test_the_objectifs_pin_follows_the_engine_goals() -> None:
    from botforge.mods.kingdom.cogs.realm_content import _marker, _objectifs_content, content_strings

    content = _objectifs_content(content_strings("fr"), _Kingdom())
    assert "🎯 Objectifs du royaume" in content
    assert "⚔️ Orcs" in content, "the kingdom goal rides the recap"
    assert _marker("objectifs") in content

    empty = _Kingdom()
    empty.council_objectives = {}
    none_content = _objectifs_content(content_strings("fr"), empty)
    assert "Aucun objectif défini" in none_content


def test_the_content_strings_carry_fr_en_parity() -> None:
    from botforge.mods.kingdom.cogs.realm_content import _CONTENT_STRINGS

    fr, en = _CONTENT_STRINGS["fr"], _CONTENT_STRINGS["en"]
    assert set(fr.keys()) == set(en.keys()), "fr and en must carry the same keys"
    for key in fr:
        assert str(fr[key]).strip() != "" and str(en[key]).strip() != ""


def test_the_views_yaml_declares_the_content_surfaces() -> None:
    from pathlib import Path

    yaml_text = (Path(__file__).resolve().parents[1] / "conf" / "views.yaml").read_text()
    for surface_id in (
        "panel:mod:kingdom:realm:territory",
        "panel:mod:kingdom:realm:alliances",
        "panel:mod:kingdom:realm:welcome",
        "panel:mod:kingdom:lieux:objectif",
    ):
        assert surface_id in yaml_text, f"{surface_id} must be declared (#381)"


# ---------------------------------------------------------------------------
# locked-salon-v1 (Drasah 23/11) — l'incident live AEGIS/HeN, PROUVÉ PAR
# SIMULATION : un salon que le bot ne PEUT PLUS LIRE ne se répare par
# AUCUNE édition (Discord exige de le voir), et l'ancre naïve ratait les
# salons décorés → l'ensure DUP audit au lieu d'adopter. Deux contrats :
# le salon verrouillé est REMPLACÉ, le salon décoré est ADOPTÉ.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_locked_declared_salon_is_replaced_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.realms as realms_module

    class _C:
        def __init__(self, name: str, locked: bool = False) -> None:
            self.name = name
            self.id = f"id-{name}"
            self.locked = locked
            self.deleted = False

        async def edit(self, **kwargs: Any) -> None:
            return None

        async def delete(self, **kwargs: Any) -> None:
            self.deleted = True

    class _Cat:
        def __init__(self, channels: list[Any]) -> None:
            self.id = "cat-1"
            self.name = "🏰 Avelorn"
            self.channels = channels

        async def edit(self, **kwargs: Any) -> None:
            return None

    locked = _C("🌍 Territoire", locked=True)
    category = _Cat([_C("🔒 Discussions"), _C("🏰 Le royaume"), locked, _C("🏆 Alliances")])
    created: list[Any] = []

    async def _create(name: str, **kwargs: Any) -> Any:
        fresh = _C(name)
        created.append(fresh)
        return fresh

    async def noop(*args: Any, **kwargs: Any) -> None:
        return None

    guild = type("G", (), {})()
    guild.categories = [category]
    guild.get_channel = lambda cid: locked if str(cid) == locked.id else None
    guild.create_text_channel = staticmethod(_create)

    monkeypatch.setattr(realms_module, "_apply_category_overwrites", noop)
    monkeypatch.setattr(realms_module, "_apply_dormancy", noop)
    monkeypatch.setattr(realms_module, "_shield_leftover", noop)
    monkeypatch.setattr(
        realms_module, "_bot_can_view", lambda g, c: not getattr(c, "locked", False)
    )

    realm = type("R2", (), {})()
    realm.id = "r-2"
    realm.name = "Avelorn"
    realm.king_id = 11
    realm.member_ids = [11]
    realm.archived_at = None
    realm.discord = {"category": "cat-1", "territory": locked.id}

    ids = await realms_module.ensure_realm_structure(guild, realm, dormant=False)
    assert len(created) == 1, "the locked salon is replaced by ONE fresh salon"
    assert created[0].name == "🌍 Territoire"
    assert ids["territory"] == created[0].id, "the habitat ids point at the FRESH salon"
    assert locked.deleted is True, "the locked corpse is swept, not left as a duplicate"


@pytest.mark.asyncio
async def test_a_decorated_salon_is_adopted_blind_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """L'ancre d'adoption décode les petites capitales : « ᴛᴇʀʀɪᴛᴏɪʀᴇ » = « Territoire »."""
    import botforge.mods.kingdom.cogs.realms as realms_module

    class _C:
        def __init__(self, name: str) -> None:
            self.name = name
            self.id = f"id-{name}"

        async def edit(self, **kwargs: Any) -> None:
            if "name" in kwargs:
                self.name = str(kwargs["name"])

        async def delete(self, **kwargs: Any) -> None:
            raise AssertionError("an adopted salon is never swept")

    decorated = _C("🌍 ᴛᴇʀʀɪᴛᴏɪʀᴇ")
    category = type("Cat", (), {})()
    category.id = "cat-1"
    category.name = "🏰 Avelorn"
    category.channels = [_C("🔒 ᴅɪsᴄᴜssɪᴏɴs"), _C("🏰 ʟᴇ ʀᴏʏᴀᴜᴍᴇ"), decorated, _C("🏆 ᴀʟʟɪᴀɴᴄᴇs")]

    async def noop(*args: Any, **kwargs: Any) -> None:
        return None

    async def _no_create(name: str, **kwargs: Any) -> Any:
        raise AssertionError("adoption must find the decorated salon, not create one")

    guild = type("G", (), {})()
    guild.categories = [category]
    guild.get_channel = lambda cid: None
    guild.create_text_channel = staticmethod(_no_create)

    monkeypatch.setattr(realms_module, "_apply_category_overwrites", noop)
    monkeypatch.setattr(realms_module, "_apply_dormancy", noop)
    monkeypatch.setattr(realms_module, "_shield_leftover", noop)

    realm = type("R3", (), {})()
    realm.id = "r-3"
    realm.name = "Avelorn"
    realm.king_id = 11
    realm.member_ids = [11]
    realm.archived_at = None
    realm.discord = {"category": "cat-1"}

    ids = await realms_module.ensure_realm_structure(guild, realm, dormant=False)
    assert ids["territory"] == decorated.id, "the decorated salon IS the charter salon"
    assert decorated.name == "🌍 Territoire", "renamed to the charter, id-mapped inplace"
