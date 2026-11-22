"""depart-fourche-v1 (Drasah 22/11).

« Lancer » = préparer (noms + sas), le DÉPART vit dans la zone Le
cycle : 🎯 Démarrer la saison classique et 🚀 Démarrer la bêta sont
deux boutons qui DISTRIBUENT le SAS admis (start_season + sas fermé).
Le départ bêta arme le week-end compressé + lève le drapeau parcours;
le départ classique désarme une bêta armée + baisse le drapeau. Le
drapeau ne bloque PLUS JAMAIS un départ (l'ancien mutex — le piège du
21/11 — est mort), une saison qui tourne refuse (« il faut finir
d'abord »), et la fourche au lancement n'existe plus.
"""

from __future__ import annotations

import unittest.mock as mock
from types import SimpleNamespace as NS
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# The fakes (Check-107 lesson: locale + delete_original_response + message.delete)
# ---------------------------------------------------------------------------


class _Resp:
    def __init__(self) -> None:
        self.done = False

    def is_done(self) -> bool:
        return self.done

    async def defer(self, ephemeral: bool = False) -> None:
        self.done = True

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        self.done = True


class _Follow:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self.sent.append(str(content))
        return NS(id="f1")


def _interaction(user: str = "7", state: Any = None) -> Any:
    resp = _Resp()
    follow = _Follow()
    message = NS(id="m1", deleted=False)

    async def _delete() -> None:
        message.deleted = True

    message.delete = _delete
    outer = NS(
        user=NS(id=user, guild_permissions=None),
        locale="fr",
        guild_id="42",
        guild=None,
        client=NS(
            status_service=NS(bot_admins=(user,)),
            roles_service=None,
            state_service=state,
        ),
        response=resp,
        followup=follow,
        message=message,
        deleted_original=False,
    )

    async def _delete_original() -> None:
        outer.deleted_original = True

    outer.delete_original_response = _delete_original
    return outer


class _Kingdoms:
    """Departure fake — the engine seams record the calls."""

    def __init__(self, phase: str = "setup", beta_name: str | None = None) -> None:
        self.season = NS(phase=phase, beta_name=beta_name, imposed_kingdoms=False)
        self.start_calls: list[bool] = []
        self.launched: list[Any] = []
        self.events = NS(
            activate_beta=mock.AsyncMock(),
            deactivate_beta=mock.AsyncMock(),
        )

    async def current_season(self) -> Any:
        return self.season

    async def start_season(self) -> None:
        self.start_calls.append(True)

    async def launch(self, imposed: Any) -> None:
        self.launched.append(imposed)


class _Stack:
    def __init__(self, kingdoms: _Kingdoms) -> None:
        self.kingdoms = kingdoms
        self.events = kingdoms.events


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id) for item in view.walk_children() if getattr(item, "custom_id", None)
    ]


def _texts(view: Any) -> str:
    return "\n".join(str(c.content) for c in view.walk_children() if hasattr(c, "content"))


def _switch_recorder(calls: list[str]) -> Any:
    async def _set_switch(client: Any, guild: str, key: str, value: bool) -> bool:
        calls.append(f"{key}={value}")
        return True

    return _set_switch


# ---------------------------------------------------------------------------
# « Lancer » prepare only — the fork card is GONE
# ---------------------------------------------------------------------------


def test_the_launch_gesture_lost_its_fork() -> None:
    """One gesture opens the prepare modal — no fork card anymore."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    assert not hasattr(sp, "_launch_type_card"), "the fork card must be GONE (depart owns the format)"
    assert not hasattr(sp, "_BetaLaunchModal"), "the beta modal must be GONE (no fork)"
    modal = sp._LaunchModal(sp.settings_strings("fr"))
    ids = _ids(modal)
    assert "kingdom:settings:launch:names" in ids
    assert "kingdom:settings:launch:sas" in ids
    assert "kingdom:settings:launch:type" not in ids, "the retired hole stays retired"


def test_the_two_departures_live_in_the_setup_cycle_row() -> None:
    """Setup phase: BOTH departure buttons distribute the sas."""
    import asyncio

    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdoms(phase="setup")
    stack = _Stack(kingdoms)

    async def _empty() -> list[Any]:
        return []

    stack.realms = NS(realms=_empty)
    with mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch.object(sp, "_pending_admissions", new=mock.AsyncMock(return_value=[])):
        view = asyncio.run(sp.build_settings_panel("123"))
    ids = _ids(view)
    assert "kingdom:settings:start-season" in ids, "the classic departure must be a click away"
    assert "kingdom:settings:start-beta" in ids, "the beta departure must be a click away"
    assert "kingdom:settings:launch" not in ids, "setup: a fresh launch would wipe the sas"


def test_the_new_keys_exist_in_both_locales() -> None:
    """Frozen contract: the departure keys ship fr AND en, fork keys gone."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    keys = (
        "settings_start_season_button",
        "settings_start_beta_button",
        "settings_start_beta_confirm_title",
        "settings_start_beta_confirm_hint",
        "settings_start_beta_confirm_button",
        "settings_start_blocked_running",
        "settings_beta_started_season",
        "settings_launch_beta_failed",  # reused by the beta departure
        "settings_regie_sas_idle_hint",
    )
    for loc in ("fr", "en"):
        strings = sp.settings_strings(loc)
        for key in keys:
            assert strings.get(key), f"{loc} missing {key}"
    # the RETIRED keys must be GONE (a stale fork misleads no one)
    fr = sp.settings_strings("fr")
    for key in (
        "settings_launch_type_title",
        "settings_launch_type_hint",
        "settings_launch_type_classic_button",
        "settings_launch_type_beta_button",
        "settings_launch_beta_modal_title",
        "settings_beta_close_button",
        "settings_beta_started",
        "settings_beta_exited",
        "settings_beta_blocked_season",
        "settings_season_blocked_beta",
        # tiroir-bêta retiré (Drasah 22/11) : plus de surface, plus de clés
        "settings_beta_title",
        "settings_beta_hint",
        "settings_beta_state_active",
        "settings_beta_state_off",
        "settings_beta_depart_hint",
        "settings_beta_false_start_hint",
        "settings_beta_sas_note",
        "settings_nav_beta_button",
    ):
        assert key not in fr, f"{key} must be GONE (depart-fourche-v1)"


def test_the_beta_confirm_card_is_a_declared_cycle_card() -> None:
    """The beta departure rides the SAME confirm card template + a surface."""
    from pathlib import Path

    from botforge.mods.kingdom.cogs import settings_panel as sp

    strings = sp.settings_strings("fr")
    view = sp._cycle_confirm_card(strings, "start-beta")
    ids = _ids(view)
    assert "kingdom:cycle-confirm:start-beta:yes" in ids
    assert "kingdom:cycle-confirm:start-beta:no" in ids
    texts = _texts(view)
    assert strings["settings_start_beta_confirm_title"] in texts
    assert strings["settings_start_beta_confirm_hint"] in texts
    views = (
        Path(sp.__file__).resolve().parents[2] / "conf" / "views.yaml"
    ).read_text(encoding="utf-8")
    assert "panel:mod:kingdom:cycle:confirm-start-beta:" in views, (
        "the beta confirm card must be a declared surface"
    )


# ---------------------------------------------------------------------------
# The departures: the format owns the parcours flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_beta_departure_distributes_the_sas() -> None:
    """Bêta ⇂ arme le week-end, lève le drapeau, DÉMARRE, ferme le SAS."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdoms(phase="setup")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=NS())
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _switch_recorder(calls)), \
            mock.patch(
                "botforge.mods.kingdom.cogs.realm_content.deploy_all_realms_content",
                new=mock.AsyncMock(return_value=2),
            ) as deploy, \
            mock.patch(
                "botforge.mods.kingdom.cogs.conscription_gate.run_conscription_gate_pass",
                mock.AsyncMock(),
            ), \
            mock.patch("botforge.core.services.beta.is_beta", new=mock.AsyncMock(return_value=False)), \
            mock.patch("botforge.core.services.beta.enter_beta", new=mock.AsyncMock()) as enter_beta:
        await sp._start_beta(interaction, sp.settings_strings("fr"))

    kingdoms.events.activate_beta.assert_awaited_once()
    enter_beta.assert_awaited_once()
    assert kingdoms.start_calls, "the beta departure must START the season (distribute the sas)"
    assert "season_entry_open=False" in calls, "the departure closes the sas by itself"
    deploy.assert_awaited_once()
    note = interaction.followup.sent[-1]
    strings = sp.settings_strings("fr")
    assert note == str(strings["settings_beta_started_season"])


@pytest.mark.asyncio
async def test_the_beta_departure_refuses_a_running_season() -> None:
    """Drasah : « il faut finir d'abord » — pas de format sous une saison."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdoms(phase="started")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=NS())

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)):
        await sp._start_beta(interaction, sp.settings_strings("fr"))

    assert not kingdoms.start_calls, "a running season is never restarted by a departure"
    note = interaction.followup.sent[-1]
    strings = sp.settings_strings("fr")
    assert note == str(strings["settings_start_blocked_running"])


@pytest.mark.asyncio
async def test_the_beta_departure_needs_a_season() -> None:
    """No season ⇂ the false-start note, nothing thrown."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    stack = _Stack(_Kingdoms())
    stack.kingdoms.season = None
    interaction = _interaction(state=NS())

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)):
        await sp._start_beta(interaction, sp.settings_strings("fr"))

    strings = sp.settings_strings("fr")
    assert interaction.followup.sent[-1] == str(strings["settings_false_start_no_season"])


@pytest.mark.asyncio
async def test_the_classic_departure_disarms_a_leftover_beta() -> None:
    """Classique ⇂ désarme la bêta armée + baisse le drapeau, PUIS démarre."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdoms(phase="setup", beta_name="now")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=NS())
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _switch_recorder(calls)), \
            mock.patch(
                "botforge.core.services.beta.is_beta", new=mock.AsyncMock(return_value=True)
            ), \
            mock.patch("botforge.core.services.beta.exit_beta", new=mock.AsyncMock()) as exit_beta:
        await sp._start_season(interaction, sp.settings_strings("fr"))

    kingdoms.events.deactivate_beta.assert_awaited_once(), (
        "the classic departure disarms a leftover beta on the season"
    )
    exit_beta.assert_awaited_once()
    assert kingdoms.start_calls, "the classic departure must START the season"
    assert "season_entry_open=False" in calls


@pytest.mark.asyncio
async def test_the_classic_departure_never_stops_on_a_dead_flag() -> None:
    """The flag lowering is BEST-EFFORT — a state service failure bars nothing."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdoms(phase="setup")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=None)  # no state_service ⇂ _lower_beta_flag False
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _switch_recorder(calls)):
        await sp._start_season(interaction, sp.settings_strings("fr"))

    assert kingdoms.start_calls, "no flag, no mutex — the classic departure stands"


@pytest.mark.asyncio
async def test_the_end_of_season_lowers_the_beta_flag() -> None:
    """fin-saison-v1 + depart-fourche : une saison finie baisse le drapeau."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdoms(phase="started")
    kingdoms.reset = mock.AsyncMock()
    stack_st = _Stack(kingdoms)
    stack_st.attacks = NS(cancel_ongoing=mock.AsyncMock(return_value=[]))
    interaction = _interaction(state=NS())  # guild=None ⇂ le sommeil des royaumes est sauté
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack_st, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch(
                "botforge.mods.kingdom.cogs.apply_flow._guild_locale",
                new=mock.AsyncMock(return_value="fr"),
            ), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _switch_recorder(calls)), \
            mock.patch.object(sp, "_drain_sas", new=mock.AsyncMock()), \
            mock.patch(
                "botforge.core.services.beta.is_beta", new=mock.AsyncMock(return_value=True)
            ), \
            mock.patch(
                "botforge.core.services.beta.exit_beta", new=mock.AsyncMock()
            ) as exit_beta:
        await sp._end_season(interaction, sp.settings_strings("fr"))

    kingdoms.reset.assert_awaited_once()
    exit_beta.assert_awaited_once(), "the end of season lowers a lingering beta flag"
    assert "season_entry_open=False" in calls, "the end of season closes the sas"
