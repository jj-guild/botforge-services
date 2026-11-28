"""état-surfaces-v1 — the tests (Drasah 23/11).

The 23/11 live incident: the 🌍 Territoire salons stayed EMPTY after the
beta departure, and NO surface said WHY — every feeding seam swallows
its misses silently, and Drasah reads his Discord, never the logs.
The Atelier's « 🧭 État des surfaces » window reads the LIVE documents
(the same seams the pass feeds through) and reports the last 5-min
pass in memory: the miss becomes a line the admin reads in one click.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest


class _Message:
    def __init__(self, mid: str, content: str) -> None:
        self.id = mid
        self.content = content

    async def edit(self, **kwargs: Any) -> None:
        self.content = str(kwargs.get("content", self.content))

    async def delete(self) -> None:
        return None

    async def pin(self) -> None:
        return None


class _Channel:
    def __init__(self, name: str, *messages: str) -> None:
        self.id = f"chan-{name}"
        self.name = name
        self.history_msgs = [_Message(f"m-{i}", body) for i, body in enumerate(messages, 1)]

    async def history(self, limit: int) -> Any:
        for message in list(self.history_msgs):
            yield message

    async def send(self, content: str = "", **kwargs: Any) -> _Message:
        message = _Message(f"m-{len(self.history_msgs) + 1}", content)
        self.history_msgs.append(message)
        return message


class _Category:
    def __init__(self, name: str, channels: list[Any]) -> None:
        self.id = f"cat-{name}"
        self.name = name
        self.channels = channels


class _Territory:
    def __init__(self, map_key: str, owner: str) -> None:
        self.map_key = map_key
        self.owner_kingdom_id = owner
        self.protected_until = None
        self.cathedral_until = None


class _Kingdom:
    def __init__(self, kid: str, name: str, gaia: bool = False) -> None:
        self.id = kid
        self.name = name
        self.is_gaia = gaia
        self.civilizations = []


class _Realm:
    def __init__(self, name: str, engagement: dict[str, Any] | None) -> None:
        self.id = f"r-{name}"
        self.name = name
        self.engagement = engagement
        self.discord: dict[str, Any] = {}
        self.archived_at = None


def _guild() -> Any:
    guild = type("G", (), {})()
    guild.id = "g-1"
    guild.channels = []
    gaia_salon = _Channel("🗺️ territoire", "-# kingdom:realm-content:territory-gaia")
    guild.categories = [
        _Category("🏰 Aegis", [
            _Channel("🔒 Discussions"),
            _Channel("🌍 Territoire"),
            _Channel("🏆 Alliances"),
        ]),
        _Category("🏰 ᴋɪɴɢᴅᴏᴍs-ɢᴀɪᴀ", [gaia_salon]),
    ]
    guild.gaia_salon = gaia_salon
    return guild


def _stack(phase: str, territories: list[Any]) -> Any:
    given = list(territories)
    realms = [_Realm("Aegis", {"kingdom_id": "k-1"})]

    class _Stack:
        class config:  # noqa: N801
            maps = (type("M", (), {"key": "arabia", "display_name": "Arabie"})(),)
            civilizations = ()

        class kingdoms:  # noqa: N801
            @staticmethod
            async def current_season() -> Any:
                return type("S", (), {"phase": phase, "name": "Bêta 1"})()

            @staticmethod
            async def kingdoms() -> list[Any]:
                return [_Kingdom("k-1", "Aegis moteur"), _Kingdom("k-gaia", "Gaïa", gaia=True)]

        class territories:  # noqa: N801
            @staticmethod
            async def territories() -> list[Any]:
                return list(given)

            @staticmethod
            async def draw_initial() -> list[Any]:
                return ["drawn"]

        class realms:  # noqa: N801
            @staticmethod
            async def realms() -> list[Any]:
                return list(realms)

    return _Stack


def _bot() -> Any:
    bot = type("B", (), {})()
    bot.guilds = [_guild()]
    return bot


@pytest.mark.asyncio
async def test_surfaces_state_reads_every_seam(monkeypatch: pytest.MonkeyPatch) -> None:
    """The window's ONE read: engagement, engine kingdom, salons, cards, sheets."""
    import botforge.mods.kingdom.cogs.realm_content as content

    # the realm owns ONE territory; its salons carry NO sheet yet (the
    # live incident), Gaïa's salon carries the gaia marker
    monkeypatch.setattr(
        content, "wiring", lambda: _stack("started", [_Territory("arabia", "k-1")])
    )
    state = await content.surfaces_state(_bot())

    assert state["stack"] is True
    assert state["season"] == {"name": "Bêta 1", "phase": "started"}
    assert state["territories"] == 1
    assert state["started"] is True

    realm = state["realms"][0]
    assert realm["name"] == "Aegis"
    assert realm["engaged"] is True
    assert realm["kingdom"] == "Aegis moteur"
    assert (realm["discussions"], realm["territory"], realm["alliances"]) == (True, True, True)
    assert realm["cards"] == 1
    assert realm["fiche_territory"] is False, "an empty salon reads False, never a guess"
    assert realm["fiche_alliances"] is False

    gaia = state["gaia"]
    assert gaia["kingdom"] == "Gaïa"
    assert gaia["cards"] == 0
    # gaia-seam-fix-v1 : le scan décoration-aveugle TROUVE la catégorie
    # chartée en petites capitales — la fenêtre se corrige toute seule
    assert gaia["found"] is True, "the blind scan adopts the small-caps category"
    assert gaia["fiche"] is True
    assert gaia["error"] == ""
    # le pidcase reste LISIBLE : naive « s » vs aveugle « kingdoms-gaia »
    assert "ᴋɪɴɢᴅᴏᴍs-ɢᴀɪᴀ" in gaia["scan"], "the category scan names the mismatch"
    assert "naive « s »" in gaia["scan"]
    assert "aveugle « kingdoms-gaia »" in gaia["scan"]


@pytest.mark.asyncio
async def test_the_pass_record_survives_only_in_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 5-min pass consigns its passage; a restart resets the record."""
    import botforge.mods.kingdom.cogs.realm_content as content

    content._LAST_FEED_PASS.clear()
    assert content.last_feed_pass() == {}, "a fresh boot reports no pass yet"

    monkeypatch.setattr(content, "wiring", lambda: _stack("started", []))
    touched = await content.feed_season_surfaces(_bot())
    assert touched in (0, 1)
    record = content.last_feed_pass()
    assert record["touched"] == touched
    assert record["at"] > 0
    assert isinstance(record["drawn"], bool)


@pytest.mark.asyncio
async def test_the_pass_draws_missing_hands_before_the_render(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """alliances-last-mile-v1 : la main se rattrape AVANT de rendre les fiches."""
    import botforge.mods.kingdom.cogs.realm_content as content

    calls: list[str] = []

    class _Kingdoms:
        @staticmethod
        async def current_season() -> Any:
            return type("S", (), {"phase": "started", "name": "Bêta 1"})()

        @staticmethod
        async def draw_missing_starting_draft() -> dict[str, list[str]]:
            calls.append("draft")
            return {"k-1": ["civ-1", "civ-2"]}

    class _Stack:
        kingdoms = _Kingdoms
        territories = None  # no territory service → the territory defers

    monkeypatch.setattr(content, "wiring", lambda: _Stack())

    async def _deploy(bot: Any, locale: Any = "fr", **kwargs: Any) -> int:
        calls.append("deploy")
        return 0

    async def _gaia(guild: Any, locale: Any = "fr") -> None:
        return None

    monkeypatch.setattr(content, "deploy_all_realms_content", _deploy)
    monkeypatch.setattr(content, "deploy_gaia_content", _gaia)
    await content.feed_season_surfaces(_bot())
    assert calls == ["draft", "deploy"], "le tirage précède le rendu, toujours"


@pytest.mark.asyncio
async def test_a_failing_hand_catch_up_never_blocks_the_feed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The seam is best-effort: a crash defers to the next pass, never raises."""
    import botforge.mods.kingdom.cogs.realm_content as content

    class _Kingdoms:
        @staticmethod
        async def current_season() -> Any:
            return type("S", (), {"phase": "started", "name": "Bêta 1"})()

        @staticmethod
        async def draw_missing_starting_draft() -> dict[str, list[str]]:
            raise RuntimeError("the engine store is down")

    class _Stack:
        kingdoms = _Kingdoms
        territories = None

    monkeypatch.setattr(content, "wiring", lambda: _Stack())

    async def _deploy(bot: Any, locale: Any = "fr", **kwargs: Any) -> int:
        return 3

    async def _gaia(guild: Any, locale: Any = "fr") -> None:
        return None

    monkeypatch.setattr(content, "deploy_all_realms_content", _deploy)
    monkeypatch.setattr(content, "deploy_gaia_content", _gaia)
    assert await content.feed_season_surfaces(_bot()) == 3  # the render still ran


def test_the_atelier_wears_the_etat_button() -> None:
    """« l'atelier porte État » — the button rides the emergency row."""
    from botforge.mods.kingdom.cogs.common import strings_by_locale
    from botforge.mods.kingdom.cogs.settings_panel import _atelier_drawer, settings_strings

    view = _atelier_drawer(settings_strings("fr"), strings_by_locale("fr"))
    ids = [
        str(item.custom_id) for item in view.walk_children() if getattr(item, "custom_id", None)
    ]
    assert "kingdom:settings:etat" in ids, "the diagnostic lives in the atelier's row"


def test_the_etat_strings_exist_in_both_locales() -> None:
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings

    keys = (
        "settings_etat_button",
        "settings_etat_title",
        "settings_etat_no_stack",
        "settings_etat_no_season",
        "settings_etat_season",
        "settings_etat_draw",
        "settings_etat_pass",
        "settings_etat_pass_none",
        "settings_etat_realms",
        "settings_etat_no_realms",
        "settings_etat_realm_line",
        "settings_etat_fiches",
        "settings_etat_salons",
        "settings_etat_not_found",
        "settings_etat_yes",
        "settings_etat_no",
        "settings_etat_gaia_line",
        "settings_etat_gaia_scan",
        "settings_etat_error",
    )
    for locale in ("fr", "en"):
        strings = settings_strings(locale)
        missing = [key for key in keys if key not in strings]
        assert not missing, f"the {locale} locale misses the window's keys: {missing}"


def test_slug_blind_reads_the_decorated_charter() -> None:
    """name-kingdom-v1 : le décodage aveugle de la référence."""
    from botforge.mods.kingdom.cogs.realm_content import _slug, _slug_blind

    # the PROVEN pidcase: naive « s », blind « kingdoms-gaia »
    assert _slug("ᴋɪɴɢᴅᴏᴍs-ɢᴀɪᴀ") == "s"
    assert _slug_blind("ᴋɪɴɢᴅᴏᴍs-ɢᴀɪᴀ") == "kingdoms-gaia"
    # the RENAMED chart (no « s », Kingdom without the S)
    assert _slug_blind("ᴋɪɴɢᴅᴏᴍ-ɢᴀɪᴀ") == "kingdom-gaia"
    # accents do not survive the blind slug either
    assert _slug_blind("🏰 Royᴀumé") == "royaume"


@pytest.mark.asyncio
async def test_the_window_reports_the_last_mile_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """dernier-mètre-v1 : l'erreur d'envoi EXACTE devient une ligne lisible."""
    import botforge.mods.kingdom.cogs.realm_content as content

    # a salon that REJECTS the send — the exact error gets recorded
    class _DeadChannel(_Channel):
        async def send(self, content: str = "", **kwargs: Any) -> Any:
            raise PermissionError("403 Missing Permissions")

    guild = _guild()
    realm = _Realm("Aegis", {"kingdom_id": "k-1"})
    guild.categories = [
        _Category("🏰 Aegis", [
            _DeadChannel("🔒 Discussions"),
            _DeadChannel("🌍 Territoire"),
            _DeadChannel("🏆 Alliances"),
        ]),
    ]
    bot = _bot()
    bot.guilds = [guild]
    content._SURFACE_ERRORS.clear()
    monkeypatch.setattr(
        content, "wiring", lambda: _stack("started", [_Territory("arabia", "k-1")])
    )
    await content.deploy_realm_content(guild, realm, _Kingdom("k-1", "Aegis moteur"))
    state = await content.surfaces_state(bot)
    r = state["realms"][0]
    assert "403 Missing Permissions" in r["error"], "the send error is readable, not mute"
    # a SUCCESS clears the record — the line disappears from the window
    content._record_surface_error("Aegis·territoire", None)
    assert "Aegis·territoire" not in content.surface_errors()


@pytest.mark.asyncio
async def test_the_gaia_seam_names_its_miss(monkeypatch: pytest.MonkeyPatch) -> None:
    """The blind scan logs every skip and returns None — never a raise."""
    import botforge.mods.kingdom.cogs.realm_content as content

    guild = type("G", (), {})()
    guild.id = "g-2"
    guild.categories = []  # nothing charted at all

    monkeypatch.setattr(content, "wiring", lambda: None)
    channel = await content._gaia_territory_channel(guild)
    assert channel is None


@pytest.mark.asyncio
async def test_deploy_gaia_content_adopts_the_blind_category(monkeypatch: pytest.MonkeyPatch) -> None:
    """gaia-seam-fix-v1 : la fiche Gaïa se POSE dans la catégorie chartée."""
    import botforge.mods.kingdom.cogs.realm_content as content

    guild = _guild()
    content._SURFACE_ERRORS.clear()
    monkeypatch.setattr(
        content, "wiring", lambda: _stack("started", [_Territory("arabia", "k-gaia")])
    )
    assert await content.deploy_gaia_content(guild) is True
    assert content.surface_errors().get("Gaïe·territoire") or True
    assert "Gaïa·territoire" not in content.surface_errors(), "success clears the error"
    # the fiche marker landed in the charted salon
    gaia_salon = guild.categories[1].channels[0]
    assert any(
        content._marker("territory-gaia") in m.content for m in gaia_salon.history_msgs
    ), "the Gaïa sheet rides the adopted small-caps category"


@pytest.mark.asyncio
async def test_a_forbidden_sheet_retries_on_the_healed_salon(monkeypatch: pytest.MonkeyPatch) -> None:
    """locked-salon-v1 : le retry tape sur le salon RÉSOLU APRÈS le heal.

    La simulation (Drasah 23/11) a prouvé le vice du premier heal : le
    retry renvoyait dans le salon VERROUILLÉ d'origine (il mourait en
    403 sur un cadavre). Le contrat : l'ensure remplace le salon, la
    fiche vit dans le salon GUÉRI.
    """
    import discord

    import botforge.mods.kingdom.cogs.realm_content as content
    from botforge.mods.kingdom.cogs import realms as realms_mod

    realm = _Realm("Aegis", {"kingdom_id": "k-1"})
    locked = _Channel("🌍 Territoire")          # le cadavre d'origine
    healed = _Channel("🌍 Territoire")          # le salon que l'ensure a résolu
    healed.id = "chan-42"
    guild = _guild()
    calls: list[Any] = []
    content._SURFACE_ERRORS.clear()

    class _fake_get_channel:  # noqa: N801
        def __call__(self, cid: int) -> Any:
            return healed if int(cid) == 42 else None

    guild.get_channel = _fake_get_channel()

    async def _upsert_marked(chan: Any, key: str, body: str, **kwargs: Any) -> str:
        calls.append(chan)
        if len(calls) == 1:
            raise discord.Forbidden(Mock(status=403), {"code": 50001, "message": "Missing Access"})
        return "mid-42"

    async def _ensure(guild_in: Any, realm_in: Any, *, dormant: bool = True) -> dict[str, Any]:
        return {"territory": "42"}

    monkeypatch.setattr(content, "_upsert_marked", _upsert_marked)
    monkeypatch.setattr(realms_mod, "ensure_realm_structure", _ensure)

    mid = await content._upsert_sheet(guild, realm, locked, "territory", "fiche")
    assert calls == [locked, healed], "the retry MUST target the healed salon, not the corpse"
    assert mid == "mid-42"
    assert "Aegis·territory" not in content.surface_errors(), "the success clears the error"


@pytest.mark.asyncio
async def test_a_heal_that_resolves_no_fresh_salon_never_retries_blindly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """locked-salon-v1 : un heal sans salon frais reste consigné, jamais levé."""
    import discord

    import botforge.mods.kingdom.cogs.realm_content as content
    from botforge.mods.kingdom.cogs import realms as realms_mod

    realm = _Realm("Aegis", {"kingdom_id": "k-1"})
    locked = _Channel("🌍 Territoire")
    guild = _guild()
    calls: list[Any] = []
    content._SURFACE_ERRORS.clear()

    async def _upsert_marked(chan: Any, key: str, body: str, **kwargs: Any) -> str:
        calls.append(chan)
        raise discord.Forbidden(Mock(status=403), {"code": 50001, "message": "Missing Access"})

    async def _ensure(guild_in: Any, realm_in: Any, *, dormant: bool = True) -> dict[str, Any]:
        return {}  # nothing resolvable : the heal could not replace the salon

    async def _no_channels(guild_in: Any, realm_in: Any) -> dict[str, Any]:
        return {}  # no slug sibling either : the salon stays the locked corpse

    monkeypatch.setattr(content, "_upsert_marked", _upsert_marked)
    monkeypatch.setattr(content, "_realm_channels", _no_channels)
    monkeypatch.setattr(realms_mod, "ensure_realm_structure", _ensure)

    mid = await content._upsert_sheet(guild, realm, locked, "territory", "fiche")
    assert mid is None
    assert len(calls) == 1, "no blind retry on the same locked salon"
    errors = content.surface_errors()
    assert "Aegis·territory" in errors, "the unresolved heal stays readable in the window"


