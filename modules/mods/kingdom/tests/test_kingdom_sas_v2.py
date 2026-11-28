"""sas-v2 (Drasah 5/12, Check 143) — le SAS vit SANS saison.

Les décisions :
1. Le sas est FERMÉ PAR DÉFAUT, TOUJOURS — la phase ne l'ouvre plus
   (l'incident : un setup de saison rouvrait la porte en silence).
2. Le sas = la PRÉPARATION : ouvert, un Roi dépose sa demande dans
   la salle d'attente MÊME SANS saison lancée.
3. Le lancement CONSOMME le sas : tout ce qui est dedans part en
   saison avec sa draft starter. Seuils : classique min 2 (refus
   net), bêta min 1 (à 1 : avertissement « quand même ? », à 0 :
   refus). Les seuils vivent en DONNÉES (SAS_FLOORS, la saison 2
   déplacera vers conf, #369).
5. « ↩️ Retirer ma demande » : le Roi sort de la salle d'attente
   LUI-MÊME, jamais celle d'un autre.

The regression net : defaults + floors, the classic refusal and
departure, the beta's three doors (refuse / warn / go), the waitlist
without a season, the withdraw button, the season_layout block.
"""

from __future__ import annotations

import inspect
import re
from types import SimpleNamespace as NS

import pytest


def _ids(view: object) -> list[str]:
    return [
        str(item.custom_id)
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    ]


def _texts(view: object) -> list[str]:
    return [
        str(child.content)
        for child in view.walk_children()  # type: ignore[attr-defined]
        if type(child).__name__ == "TextDisplay"
    ]


class _Resp:
    def __init__(self) -> None:
        self.done = False
        self.deferred = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True
        self.deferred = True


class _Follow:
    def __init__(self) -> None:
        self.sent: list[tuple[object, dict]] = []

    async def send(self, content: object = None, **kwargs: object):  # type: ignore[no-untyped-def]
        self.sent.append((content, kwargs))
        return NS(id=f"f{len(self.sent)}")


def _interaction(resp: _Resp, follow: _Follow) -> NS:  # type: ignore[no-untyped-def]
    return NS(
        locale="fr", guild_id="7", guild=None,
        user=NS(id="7", guild_permissions=None),
        client=NS(),
        response=resp, followup=follow,
    )


def _shell(name: str = "roc", *, join: bool = True) -> NS:
    return NS(
        id=f"realm:{name}-1", name=name, slug=name, king_id="7",
        join_request={"season_id": "", "requested_at": 1} if join else None,
        engagement=None, archived_at=0,
    )


def _stack(shells: list[NS], season: object = None) -> NS:
    class _Kingdom:
        started: list[bool] = []

        async def current_season(self):  # type: ignore[no-untyped-def]
            return season

        async def start_season(self) -> None:
            self.started.append(True)

    class _Realms:
        async def realms(self) -> list[NS]:
            return shells

        async def realm_of_slug(self, slug: str) -> NS:
            for shell in shells:
                if shell.slug == slug:
                    return shell
            raise LookupError(slug)

        async def request_season_entry(self, realm_id: str, user_id: str, season_id: str) -> None:
            return None

        async def clear_join_request(self, realm_id: str) -> None:
            return None

    kingdoms = _Kingdom()
    return NS(kingdoms=kingdoms, realms=_Realms(), events=NS())


# ---------------------------------------------------------------------------
# (1) the sas stays CLOSED by default, whatever the phase
# ---------------------------------------------------------------------------


def test_the_sas_is_closed_by_default_whatever_the_phase() -> None:
    """No phase ever opens the sas anymore — the admin's hand does."""
    from botforge.mods.kingdom.cogs.regie import _REGIE_DEFAULTS, read_regie

    assert _REGIE_DEFAULTS["season_entry_open"] is False, "sas-v2: closed, always"
    src = inspect.getsource(read_regie)
    assert 'season_entry_open' not in src or 'phase == "setup"' not in src, (
        "the setup phase default MUST be gone (the sas opens by hand only)"
    )


def test_the_floors_live_as_data() -> None:
    """Seuils = données (SAS_FLOORS), shaped for #369 (season 2)."""
    from botforge.mods.kingdom.cogs.regie import SAS_FLOORS

    assert SAS_FLOORS == {"classic": 2, "beta": 1}


def test_the_realm_strings_carry_fr_en_parity() -> None:
    """Every realm key exists in fr AND en (the parity rule)."""
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    fr = set(realm_strings("fr").keys())
    en = set(realm_strings("en").keys())
    assert fr == en, f"fr-only: {fr - en} / en-only: {en - fr}"
    fr_strings = realm_strings("fr")
    for key in ("season_join_waitlist", "season_join_withdraw_button",
                "season_join_withdrawn", "season_join_withdraw_denied"):
        assert str(fr_strings[key]).strip(), f"{key} must carry a real string"


# ---------------------------------------------------------------------------
# (2) the CLASSIC departure — refuse under 2, consume at 2+
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_classic_departure_refuses_below_two(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """1 royaume dans le sas = refus net, la note porte le compte."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    stack = _stack([_shell("roc")])  # ONE realm waits
    windows: list[dict] = []
    monkeypatch.setattr(sp, "wiring", lambda: stack)
    monkeypatch.setattr(sp, "_needs_stack", lambda s: (stack, None))
    async def _open(i, content=None, **kw):  # type: ignore[no-untyped-def]
        windows.append({"content": content, **kw})

    monkeypatch.setattr(sp, "open_unique_ephemeral", _open)
    consumed: list[object] = []
    monkeypatch.setattr(sp, "_consume_sas",
                        lambda *a, **k: consumed.append(True) or _async_int(0))

    resp, follow = _Resp(), _Follow()
    await sp._start_season(_interaction(resp, follow), sp.settings_strings("fr"))

    assert windows, "the refusal note reaches the admin"
    assert "1 royaume" in str(windows[0]["content"])
    assert not stack.kingdoms.started, "under the floor, NOTHING starts"
    assert not consumed, "under the floor, the sas is not even consumed"


@pytest.mark.asyncio
async def test_the_classic_departure_consumes_the_sas_and_starts(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """2 royaumes dans le sas = le casting part AVEC le départ."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    stack = _stack([_shell("roc"), _shell("aegis")])
    windows: list[dict] = []
    switches: list[tuple[str, bool]] = []
    monkeypatch.setattr(sp, "wiring", lambda: stack)
    monkeypatch.setattr(sp, "_needs_stack", lambda s: (stack, None))
    async def _open(i, content=None, **kw):  # type: ignore[no-untyped-def]
        windows.append({"content": content, **kw})

    monkeypatch.setattr(sp, "open_unique_ephemeral", _open)

    async def _consume(interaction, stack, strings):  # type: ignore[no-untyped-defined]
        return 2

    async def _set_switch(bot, gid, key, value):  # type: ignore[no-untyped-defined]
        switches.append((key, value))
        return True

    async def _pins(interaction) -> None:
        return None

    async def _flag(interaction) -> bool:
        return False

    monkeypatch.setattr(sp, "_consume_sas", _consume)
    monkeypatch.setattr(sp, "_lower_beta_flag", _flag)
    monkeypatch.setattr(sp, "refresh_live_pins_after", _pins)
    from botforge.mods.kingdom.cogs import regie
    monkeypatch.setattr(regie, "set_switch", _set_switch)

    resp, follow = _Resp(), _Follow()
    await sp._start_season(_interaction(resp, follow), sp.settings_strings("fr"))

    assert stack.kingdoms.started, "at the floor, the classic departure STARTS"
    assert not windows, "no refusal at 2 realms"
    assert ("season_entry_open", False) in switches, "the departure closes the sas"


# ---------------------------------------------------------------------------
# (3) the BETA departure — 0 refuses, 1 warns, solo confirmed goes
# ---------------------------------------------------------------------------


def _beta_patches(monkeypatch, stack):  # type: ignore[no-untyped-def]
    from botforge.mods.kingdom.cogs import settings_panel as sp

    windows: list[dict] = []
    switches: list[tuple[str, bool]] = []
    consumed: list[int] = []

    async def _consume(interaction, stk, strings):  # type: ignore[no-untyped-defined]
        consumed.append(1)
        return 1

    async def _set_switch(bot, gid, key, value):  # type: ignore[no-untyped-defined]
        switches.append((key, value))
        return True

    async def _pins(interaction) -> None:
        return None

    async def _flag(interaction) -> bool:
        return True

    async def _arm(stack) -> None:
        return None

    monkeypatch.setattr(sp, "wiring", lambda: stack)
    monkeypatch.setattr(sp, "_needs_stack", lambda s: (stack, None))
    async def _open(i, content=None, **kw):  # type: ignore[no-untyped-def]
        windows.append({"content": content, **kw})

    monkeypatch.setattr(sp, "open_unique_ephemeral", _open)
    monkeypatch.setattr(sp, "_consume_sas", _consume)
    monkeypatch.setattr(sp, "_arm_compressed_beta", _arm)
    monkeypatch.setattr(sp, "_raise_beta_flag", _flag)
    monkeypatch.setattr(sp, "refresh_live_pins_after", _pins)
    from botforge.mods.kingdom.cogs import regie
    monkeypatch.setattr(regie, "set_switch", _set_switch)
    return windows


@pytest.mark.asyncio
async def test_the_beta_departure_refuses_an_empty_sas(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Roster 0 : la bêta ne part jamais à vide."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    season = NS(phase="setup", beta_name=None)
    stack = _stack([], season=season)
    windows = _beta_patches(monkeypatch, stack)

    resp, follow = _Resp(), _Follow()
    await sp._start_beta(_interaction(resp, follow), sp.settings_strings("fr"))

    assert windows, "the empty-sas refusal reaches the admin"
    assert "saison" in str(windows[0]["content"]).lower() or "bêta" in str(
        windows[0]["content"]
    ).lower()
    assert not stack.kingdoms.started, "an empty sas never departs"


@pytest.mark.asyncio
async def test_a_solo_roster_warns_before_the_beta_depares(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Roster 1 SANS confirmation : la carte « quand même ? », PAS le départ."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    season = NS(phase="setup", beta_name=None)
    stack = _stack([_shell("roc")], season=season)
    windows = _beta_patches(monkeypatch, stack)

    resp, follow = _Resp(), _Follow()
    await sp._start_beta(_interaction(resp, follow), sp.settings_strings("fr"))

    assert windows, "the solo warning card opens"
    view = windows[0].get("view")
    assert view is not None, "the warning is a CONFIRM CARD, not a bare note"
    assert "kingdom:cycle-confirm:start-beta-solo:yes" in _ids(view)
    assert not stack.kingdoms.started, "solo: no confirmation, no departure"


@pytest.mark.asyncio
async def test_the_solo_confirmation_depares_the_beta(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """solo_ok=True (ou la carte confirmée) : la bêta part à 1 royaume."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    season = NS(phase="setup", beta_name=None)
    stack = _stack([_shell("roc")], season=season)
    windows = _beta_patches(monkeypatch, stack)

    resp, follow = _Resp(), _Follow()
    await sp._start_beta(_interaction(resp, follow), sp.settings_strings("fr"), solo_ok=True)

    assert stack.kingdoms.started, "confirmed solo: the beta departs"
    assert not windows, "no confirmation card once solo_ok rides"


def test_the_generic_start_confirm_card_is_wired_to_the_router() -> None:
    """lancer-unique-v1 : la carte générique route — the confirm card's
    yes leads to the LEVER router (never a dedicated departure, never
    a solo card — the generic card already asked once)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    assert sp._CYCLE_CONFIRM_HANDLERS["start"] is sp._start_confirmed
    assert "start-season" not in sp._CYCLE_CONFIRM_HANDLERS
    assert "start-beta" not in sp._CYCLE_CONFIRM_HANDLERS
    assert "start-beta-solo" not in sp._CYCLE_CONFIRM_HANDLERS
    assert sp._start_confirmed.__doc__ and "lever" in sp._start_confirmed.__doc__.lower()
    assert not hasattr(sp, "_start_beta_solo"), "the solo handler is retired"
    assert not hasattr(sp, "_LaunchModal"), "the launch wizard is retired"


def _async_int(value: int):  # type: ignore[no-untyped-def]
    import asyncio

    fut = asyncio.get_event_loop().create_future()
    fut.set_result(value)
    return fut


# ---------------------------------------------------------------------------
# (4) the SAS button — closed by hand, waitlist WITHOUT a season
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_join_button_reads_the_sas_before_the_season(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Sas ouvert + saison None : la demande part avec l'id VIDE."""
    from botforge.mods.kingdom.cogs import notices, panel, regie
    from botforge.mods.kingdom.cogs import realms as realms_mod

    stack = _stack([_shell("roc")], season=None)
    requested: list[tuple[str, str, str]] = []

    async def _request(realm_id, user_id, season_id):  # type: ignore[no-untyped-defined]
        requested.append((realm_id, user_id, season_id))

    monkeypatch.setattr(realms_mod, "wiring", lambda: stack)
    stack.realms.request_season_entry = _request  # type: ignore[method-assign]
    monkeypatch.setattr(regie, "regie_open", lambda *a: _async_bool(True))
    monkeypatch.setattr(notices, "announce_season_entry_request", lambda *a, **k: _async_bool(None))
    monkeypatch.setattr(panel, "_guild_locale", lambda gid: _async_str("fr"))

    btn = realms_mod.RealmJoinButton("Inscrire", "roc")
    resp, follow = _Resp(), _Follow()
    await btn.callback(_interaction(resp, follow))

    assert requested == [("realm:roc-1", "7", "")], (
        "no season: the request rides with the EMPTY season id"
    )
    assert follow.sent, "the waitlist note answers the Roi"
    assert "salle" in str(follow.sent[-1][0]).lower() or "atten" in str(follow.sent[-1][0]).lower()


@pytest.mark.asyncio
async def test_a_closed_sas_refuses_the_join_even_without_a_season(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Sas fermé : la note fermée, JAMAIS la demande."""
    from botforge.mods.kingdom.cogs import regie
    from botforge.mods.kingdom.cogs import realms as realms_mod

    stack = _stack([_shell("roc")], season=None)
    requested: list[tuple] = []

    async def _request(*a):  # type: ignore[no-untyped-defined]
        requested.append(a)

    stack.realms.request_season_entry = _request  # type: ignore[method-assign]
    monkeypatch.setattr(realms_mod, "wiring", lambda: stack)
    monkeypatch.setattr(regie, "regie_open", lambda *a: _async_bool(False))

    btn = realms_mod.RealmJoinButton("Inscrire", "roc")
    resp, follow = _Resp(), _Follow()
    await btn.callback(_interaction(resp, follow))

    assert not requested, "a closed sas never registers a wish"
    assert follow.sent, "the closed note answers"
    assert "fermé" in str(follow.sent[-1][0]).lower()


def _async_bool(value: object):  # type: ignore[no-untyped-def]
    import asyncio

    fut = asyncio.get_event_loop().create_future()
    fut.set_result(value)
    return fut


def _async_str(value: str):  # type: ignore[no-untyped-def]
    import asyncio

    fut = asyncio.get_event_loop().create_future()
    fut.set_result(value)
    return fut


# ---------------------------------------------------------------------------
# (5) « ↩️ Retirer ma demande » — the Roi exits the waitlist himself
# ---------------------------------------------------------------------------


def test_the_withdraw_template_is_anchored_and_alone() -> None:
    """No double dispatch with the join act."""
    from botforge.mods.kingdom.cogs.realms import RealmJoinButton, RealmJoinWithdrawButton

    withdraw = re.compile(RealmJoinWithdrawButton.__discord_ui_compiled_template__.pattern)
    join = re.compile(RealmJoinButton.__discord_ui_compiled_template__.pattern)
    assert withdraw.fullmatch("kingdom:realm:join-withdraw:aegis-42")
    assert not withdraw.fullmatch("kingdom:realm:join:roc")
    assert not join.fullmatch("kingdom:realm:join-withdraw:roc")


@pytest.mark.asyncio
async def test_the_king_withdraws_his_own_request(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """The Roi clears HIS request and reads the withdrawn note."""
    from botforge.mods.kingdom.cogs import realms as realms_mod

    realm = _shell("roc")
    realm.join_request = {"season_id": "", "requested_at": 1}
    stack = _stack([])
    stack.realms.realm_of_slug = lambda slug: _async_ns(realm)  # type: ignore[method-assign]
    cleared: list[str] = []

    async def _clear(realm_id):  # type: ignore[no-untyped-defined]
        cleared.append(realm_id)

    stack.realms.clear_join_request = _clear  # type: ignore[method-assign]
    monkeypatch.setattr(realms_mod, "wiring", lambda: stack)

    btn = realms_mod.RealmJoinWithdrawButton("↩️", "roc")
    resp, follow = _Resp(), _Follow()
    await btn.callback(_interaction(resp, follow))  # user id 7 == king_id 7

    assert cleared == ["realm:roc-1"], "the king's request is cleared"
    assert follow.sent, "the withdrawn note answers"


@pytest.mark.asyncio
async def test_nobody_withdraws_another_kings_request(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Un rendu périmé ne retire JAMAIS la demande d'un autre."""
    from botforge.mods.kingdom.cogs import realms as realms_mod

    realm = _shell("roc")
    realm.join_request = {"season_id": "", "requested_at": 1}
    stack = _stack([])
    stack.realms.realm_of_slug = lambda slug: _async_ns(realm)  # type: ignore[method-assign]
    cleared: list[str] = []

    async def _clear(realm_id):  # type: ignore[no-untyped-defined]
        cleared.append(realm_id)

    stack.realms.clear_join_request = _clear  # type: ignore[method-assign]
    monkeypatch.setattr(realms_mod, "wiring", lambda: stack)

    btn = realms_mod.RealmJoinWithdrawButton("↩️", "roc")
    resp, follow = _Resp(), _Follow()
    interaction = _interaction(resp, follow)
    interaction.user = NS(id="99", guild_permissions=None)  # NOT the king
    await btn.callback(interaction)

    assert not cleared, "a stranger's click clears NOTHING"
    assert follow.sent, "the denied note answers"


def _async_ns(value: object):  # type: ignore[no-untyped-def]
    import asyncio

    fut = asyncio.get_event_loop().create_future()
    fut.set_result(value)
    return fut


# ---------------------------------------------------------------------------
# (6) sas accessible EN PHASE OFF — le correctif « où est le sas ? »
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_off_phase_cockpit_still_opens_the_admissions(monkeypatch) -> None:
    """Phase off : Admissions (+badge) vit à côté de « Lancer la saison ».

    sas-v2 (retour Drasah 23/11) : le sas vit SANS saison, donc la
    salle d'attente doit se VOIR même sans saison — sinon un Roi dépose
    sa demande et l'admin n'a AUCUNE surface pour la lire.
    """
    from botforge.mods.kingdom.cogs import apply_flow, panel
    from botforge.mods.kingdom.cogs import settings_panel as sp

    async def _locale(guild_id):  # type: ignore[no-untyped-def]
        return "fr"

    async def _state(strings, bot=None, guild_id=""):  # type: ignore[no-untyped-def]
        return ["aucune saison"], "off"

    async def _pending():  # type: ignore[no-untyped-def]
        return [NS(), NS()]  # two waiting realms

    monkeypatch.setattr(apply_flow, "_guild_locale", _locale)
    monkeypatch.setattr(sp, "_season_state", _state)
    monkeypatch.setattr(sp, "_pending_admissions", _pending)
    monkeypatch.setattr(panel, "current_bot", lambda: NS())

    view = await sp.build_settings_panel("7")
    ids = _ids(view)
    buttons = {
        str(item.custom_id): item
        for item in view.walk_children()  # type: ignore[attr-defined]
        if getattr(item, "custom_id", None)
    }
    assert "kingdom:console-nav:admissions" in ids, (
        "off phase: the sas door MUST show (Drasah cannot read the waitlist otherwise)"
    )
    assert "kingdom:settings:launch" in ids, "the launch button stays"
    assert "(2)" in str(buttons["kingdom:console-nav:admissions"].label), (
        "the badge carries the waitlist count"
    )
