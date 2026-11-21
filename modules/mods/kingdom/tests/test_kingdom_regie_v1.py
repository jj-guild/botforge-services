"""console-etats-regie-v1 (Drasah 21/11) — la Régie, le sas, le faux départ.

The approved design's contract, one test per actée decision :

- the switches are DATA with SAFE defaults : a mid-season guild with no
  stored régie wakes up EXACTLY as before (players' life open, sas
  phase-mapped) — Drasah's running season can never break ;
- the sas shuts ITSELF at the season's departure, re-opens by hand
  (the régie) and at a false start ;
- « Joindre un royaume » (the persistent realm, no season needed) and
  « Prendre le Trône » ride the OFF-season camp window ;
- the false start rebasculates to the season's ORIGIN state (setup,
  sas open, the engaged realms re-ask).
"""

from __future__ import annotations

from typing import Any
from types import SimpleNamespace

import pytest


# ---------------------------------------------------------------------------
# The fake state service (the regie lives in mod:kingdom / regie:<guild>)
# ---------------------------------------------------------------------------


class _RegieStateService:
    """A StateService stand-in: get_state/set_state over ONE dict store."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], dict[str, Any]] = {}

    async def get_state(self, scope: str, key: str) -> dict[str, Any] | None:
        return self.store.get((scope, key))

    async def set_state(self, scope: str, key: str, value: dict[str, Any], ttl: int | None = None) -> bool:
        self.store[(scope, key)] = value
        return True

    async def delete_state(self, scope: str, key: str) -> bool:
        return self.store.pop((scope, key), None) is not None


def _bot(state: _RegieStateService | None = None) -> SimpleNamespace:
    return SimpleNamespace(state_service=state or _RegieStateService())


def _stack(phase: str | None) -> SimpleNamespace:
    season = SimpleNamespace(phase=phase, imposed_kingdoms=False) if phase else None

    class _Kingdoms:
        async def kingdoms(self):
            return []

        async def lords(self):
            return []

        async def current_season(self):
            return season

    return SimpleNamespace(kingdoms=_Kingdoms())


@pytest.mark.asyncio
async def test_the_defaults_never_close_a_midseason_guild() -> None:
    """No stored régie = the PRE-régie behaviour, for every phase."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common
    from botforge.mods.kingdom.cogs.regie import read_regie

    bot = _bot()
    for phase, sas in ((None, False), ("setup", True), ("started", False)):
        with mock.patch.object(common, "wiring", lambda s=_stack(phase): s):
            values = await read_regie(bot, "123")
        assert values["registration_open"] is True, f"phase={phase}: life stays open"
        assert values["realm_creation_open"] is True
        assert values["realm_join_open"] is True
        assert values["season_entry_open"] is sas, f"phase={phase}: the sas maps the phase"


@pytest.mark.asyncio
async def test_an_explicit_switch_beats_the_default() -> None:
    """A hand-closed sas stays closed even while the season prepares."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common
    from botforge.mods.kingdom.cogs.regie import read_regie, set_switch, toggle_switch

    state = _RegieStateService()
    bot = _bot(state)
    with mock.patch.object(common, "wiring", lambda: _stack("setup")):
        assert await set_switch(bot, "123", "season_entry_open", False) is True
        values = await read_regie(bot, "123")
        assert values["season_entry_open"] is False, "the admin's hand beats the phase"
        assert await toggle_switch(bot, "123", "season_entry_open") is True
        assert (await read_regie(bot, "123"))["season_entry_open"] is True
    # the state rides the mod's OWN scope, per guild
    assert ("mod:kingdom", "regie:123") in state.store


@pytest.mark.asyncio
async def test_the_departure_shuts_the_sas_by_itself() -> None:
    """start_season = the casting leaves, the sas CLOSES (Drasah 21/11)."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common, settings_panel as sp

    state = _RegieStateService()
    started: dict[str, Any] = {}

    class _Kingdoms(_stack("setup").kingdoms.__class__):  # type: ignore[misc]
        async def start_season(self):
            started["yes"] = True

    stack = SimpleNamespace(kingdoms=_Kingdoms())
    notes: list[str] = []

    async def _send(content: str, ephemeral: bool = True) -> None:
        notes.append(str(content))

    interaction = SimpleNamespace(
        client=_bot(state),
        guild_id="123",
        response=SimpleNamespace(is_done=lambda: True),
        followup=SimpleNamespace(send=_send),
    )
    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(sp, "wiring", lambda: stack):
        await sp._start_season(interaction, sp.settings_strings("fr"))
    assert started.get("yes") is True
    from botforge.mods.kingdom.cogs.regie import read_regie

    with mock.patch.object(common, "wiring", lambda: stack):
        # the stored False beats the setup phase's default-open
        assert (await read_regie(interaction.client, "123"))["season_entry_open"] is False


@pytest.mark.asyncio
async def test_the_false_start_rebasculates_to_the_origin_state() -> None:
    """🛑 Faux départ : setup + sas open + every engaged realm RE-ASKS."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common, settings_panel as sp

    state = _RegieStateService()
    phases: list[str] = []
    released: list[str] = []

    class _Kingdoms(_stack("started").kingdoms.__class__):  # type: ignore[misc]
        async def set_phase(self, phase: str):
            phases.append(phase)

    class _Realms:
        async def realms(self):
            return [
                SimpleNamespace(
                    id="realm:a-1",
                    engagement={"season_id": "s1", "kingdom_id": "k-1"},
                ),
                SimpleNamespace(id="realm:b-2", engagement=None),
            ]

        async def release_engagement(self, realm_id: str):
            released.append(realm_id)

    stack = SimpleNamespace(kingdoms=_Kingdoms(), realms=_Realms())
    notes: list[str] = []

    async def _send(content: str, ephemeral: bool = True) -> None:
        notes.append(str(content))

    interaction = SimpleNamespace(
        client=_bot(state),
        guild_id="123",
        response=SimpleNamespace(is_done=lambda: True),
        followup=SimpleNamespace(send=_send),
    )
    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(sp, "wiring", lambda: stack):
        await sp._false_start(interaction, sp.settings_strings("fr"))
    assert phases == ["setup"], "the engine returns to preparation"
    assert released == ["realm:a-1"], "only the ENGAGED realms re-ask"
    from botforge.mods.kingdom.cogs.regie import read_regie

    with mock.patch.object(common, "wiring", lambda: stack):
        assert (await read_regie(interaction.client, "123"))["season_entry_open"] is True


def test_a_player_joins_a_persistent_realm() -> None:
    """join_realm : member in, king refused, one realm per player."""
    import asyncio

    from botforge.mods.kingdom.realms import RealmError, RealmService

    class _Store:
        def __init__(self) -> None:
            self.docs: dict[str, dict[str, Any]] = {}

        async def upsert_realm(self, document):
            self.docs[document["_id"]] = document

        async def find_realms(self):
            return list(self.docs.values())

        async def delete_realm(self, realm_id):
            self.docs.pop(realm_id, None)

    store = _Store()
    service = RealmService(store)
    home = asyncio.run(service.found_realm("1", "Roi A", "Roc"))
    other = asyncio.run(service.found_realm("9", "Roi B", "Val"))

    joined = asyncio.run(service.join_realm(str(home.id), "77"))
    assert "77" in joined.member_ids

    def _refused(fn, rid: str, pid: str) -> None:
        try:
            asyncio.run(fn(rid, pid))
        except RealmError:
            return
        raise AssertionError("the realm rule should have refused")

    _refused(service.join_realm, str(home.id), "1")    # the king cannot 'join'
    _refused(service.join_realm, str(other.id), "77")  # one realm per player


def test_release_on_a_fresh_shell() -> None:
    """release_engagement + engage round-trip (in-memory store)."""
    import asyncio

    from botforge.mods.kingdom.realms import RealmService

    class _Store:
        def __init__(self) -> None:
            self.docs: dict[str, dict[str, Any]] = {}

        async def upsert_realm(self, document):
            self.docs[document["_id"]] = document

        async def find_realms(self):
            return list(self.docs.values())

        async def delete_realm(self, realm_id):
            self.docs.pop(realm_id, None)

    service = RealmService(_Store())
    realm = asyncio.run(service.found_realm("1", "Roi", "Roc"))
    realm = asyncio.run(service.engage(str(realm.id), "s1", "k-1"))
    assert realm.engagement is not None
    realm = asyncio.run(service.release_engagement(str(realm.id)))
    assert realm.engagement is None and realm.join_request is None


@pytest.mark.asyncio
async def test_the_closed_sas_hides_the_entry_button() -> None:
    """season_layout : closed sas = the note, never the button."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import common, panel
    from botforge.mods.kingdom.cogs.realms import season_layout
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    strings = realm_strings("fr")
    realm = SimpleNamespace(
        name="Roc", slug="roc", king_id="1", member_ids=[],
        join_request=None, engagement=None, guild_id="",
    )
    stack = _stack("started")
    from botforge.mods.kingdom.cogs import realms as realms_mod

    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(realms_mod, "wiring", lambda: stack), \
            mock.patch.object(panel, "current_bot", lambda: _bot(None)):
        view = await season_layout(realm, strings, king=True, guild_id="123")
    ids = [str(i.custom_id) for i in view.walk_children() if getattr(i, "custom_id", None)]
    texts = [c.content for c in view.walk_children() if type(c).__name__ == "TextDisplay"]
    assert not any("kingdom:realm:join" in i for i in ids), "closed sas: no button"
    assert any("fermé" in str(t) for t in texts)


@pytest.mark.asyncio
async def test_the_off_season_camp_offers_the_persistent_doors() -> None:
    """Hors saison : « Prendre le Trône » + « Joindre un royaume »."""
    import unittest.mock as mock

    from botforge.mods.kingdom.cogs import camp_beta, common

    class _Kingdoms(_stack(None).kingdoms.__class__):  # type: ignore[misc]
        async def realms(self):
            return []

    stack = SimpleNamespace(kingdoms=_Kingdoms(), realms=SimpleNamespace(realms=_Kingdoms().realms))

    async def _send(*args, **kwargs):
        return None

    interaction = SimpleNamespace(
        client=_bot(),
        user=SimpleNamespace(id="42", display_name="Joueur"),
        guild_id="123",
        locale="fr",
        response=SimpleNamespace(is_done=lambda: True, send_modal=lambda m: None),
        followup=SimpleNamespace(send=_send),
    )
    with mock.patch.object(common, "wiring", lambda: stack):
        view = await camp_beta._camp_window(interaction)
    ids = [str(i.custom_id) for i in view.walk_children() if getattr(i, "custom_id", None)]
    texts = [c.content for c in view.walk_children() if type(c).__name__ == "TextDisplay"]
    assert "kingdom:camp:found" in ids, "off-season: Prendre le Trône"
    assert "kingdom:camp:join" in ids, "off-season: Joindre un royaume"
    assert any("Hors saison" in str(t) for t in texts), "the window_help_off_season line rides"
    # the doors respect the régie: creation closed = no found button
    from botforge.mods.kingdom.cogs.regie import set_switch

    await set_switch(interaction.client, "123", "realm_creation_open", False)
    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(camp_beta, "wiring", lambda: stack):
        view = await camp_beta._camp_window(interaction)
    ids = [str(i.custom_id) for i in view.walk_children() if getattr(i, "custom_id", None)]
    texts = [c.content for c in view.walk_children() if type(c).__name__ == "TextDisplay"]
    assert "kingdom:camp:found" not in ids, "a closed régie door stays closed"
    assert "kingdom:camp:join" in ids, "the OTHER doors stay open (one switch per door)"
    # every door closed = the window says WHY, in plain words
    await set_switch(interaction.client, "123", "realm_join_open", False)
    with mock.patch.object(common, "wiring", lambda: stack), \
            mock.patch.object(camp_beta, "wiring", lambda: stack):
        view = await camp_beta._camp_window(interaction)
    texts = [c.content for c in view.walk_children() if type(c).__name__ == "TextDisplay"]
    assert any("régie" in str(t) for t in texts), "the window says why"
