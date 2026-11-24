"""lancer-unique-v1 (Drasah 24/11) — le levier est la source de vérité.

« Lancer la saison ne devrait pas avoir ce comportement » : le
questionnaire du lancement est RETIRÉ (noms imposés, question du sas —
le levier de la régie les possède), la FOURCHE au départ est morte
(UN bouton « Démarrer la saison — Classique/Bêta » dont le CLIC route
selon la valeur EFFECTIVE du levier), et l'admin ne cible plus
personne : le héraut « 📣 Prévenir les royaumes » dit à chaque royaume
vivant hors saison que le SAS est ouvert. Le moteur des départs
(classique/bêta : distribution du sas, week-end compressé, drapeau)
reste celui de depart-fourche-v1, inchangé.
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


class _Kingdom:
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
    def __init__(self, kingdoms: _Kingdom) -> None:
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


def test_the_launch_gesture_asks_nothing() -> None:
    """lancer-unique-v1: NO wizard — the launch prepares SANS questions."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    assert not hasattr(sp, "_launch_type_card"), "the fork card must be GONE (depart owns the format)"
    assert not hasattr(sp, "_BetaLaunchModal"), "the beta modal must be GONE (no fork)"
    assert not hasattr(sp, "_LaunchModal"), "the prepare wizard must be GONE too"


@pytest.mark.asyncio
async def test_the_launch_prepares_with_a_sas_open_default() -> None:
    """SAS ouvert ⇒ launch(None), sas left open, the note says PREPARED."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdom()
    stack = _Stack(kingdoms)
    interaction = _interaction()
    tail: list[str] = []
    with mock.patch(
        "botforge.mods.kingdom.cogs.regie.regie_open", new=mock.AsyncMock(return_value=True)
    ), mock.patch.object(sp, "_needs_stack", new=lambda s: (stack, None)), \
            mock.patch.object(sp, "_lower_beta_flag", new=mock.AsyncMock(return_value=False)), \
            mock.patch.object(
                sp, "_finish_launch",
                new=mock.AsyncMock(side_effect=lambda i, sas_answer: tail.append(sas_answer)),
            ), \
            mock.patch.object(sp, "open_unique_ephemeral", new=mock.AsyncMock()):
        await sp._open_launch(interaction, sp.settings_strings("fr"))

    assert kingdoms.launched == [None], "no imposed names ride the launch"
    assert tail == ["open"], "the sas stays open (the régie lever owns it)"
    assert interaction.followup.sent[-1] == str(sp.settings_strings("fr")["settings_launch_done"])


def test_the_one_start_button_and_the_herald_live_in_the_setup_cycle_row() -> None:
    """Setup phase: ONE Démarrer (routed by the lever) + the herald."""
    import asyncio

    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdom(phase="setup")
    stack = _Stack(kingdoms)

    async def _empty() -> list[Any]:
        return []

    stack.realms = NS(realms=_empty)
    with mock.patch.object(sp, "wiring", lambda: stack), \
            mock.patch.object(sp, "_pending_admissions", new=mock.AsyncMock(return_value=[])), \
            mock.patch.object(
                sp, "_start_button_label",
                new=mock.AsyncMock(return_value="🎯 Démarrer la saison — Classique"),
            ):
        view = asyncio.run(sp.build_settings_panel("123"))
    ids = _ids(view)
    assert "kingdom:settings:start" in ids, "the ONE Démarrer must be a click away"
    assert "kingdom:settings:announce" in ids, "the herald must warn the realms"
    assert "kingdom:settings:start-season" not in ids, "the dedicated classic departure is GONE"
    assert "kingdom:settings:start-beta" not in ids, "the dedicated beta departure is GONE"
    assert "kingdom:settings:launch" not in ids, "setup: a fresh launch would wipe the sas"


def test_the_new_keys_exist_in_both_locales() -> None:
    """Frozen contract: the router + herald keys ship fr AND en."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    keys = (
        "settings_start_button",
        "settings_start_parcours_classic",
        "settings_start_parcours_beta",
        "settings_start_confirm_title",
        "settings_start_confirm_hint",
        "settings_start_confirm_button",
        "settings_announce_button",
        "settings_announce_dm",
        "settings_announce_done",
        "settings_announce_empty",
        "settings_launch_button",
        "settings_launch_done",
        "settings_start_season_done",
        "settings_start_blocked_running",
        "settings_beta_started_season",
        "settings_launch_beta_failed",  # reused by the beta departure
        "settings_regie_sas_idle_hint",
    )
    for loc in ("fr", "en"):
        strings = sp.settings_strings(loc)
        for key in keys:
            assert strings.get(key), f"{loc} missing {key}"
        for fmt in ("settings_start_button", "settings_announce_done"):
            strings[fmt].format(parcours="X", count=3)
    # the RETIRED keys must be GONE (a stale fork misleads no one)
    fr = sp.settings_strings("fr")
    for key in (
        "settings_launch_type_title",
        "settings_launch_type_hint",
        "settings_launch_type_classic_button",
        "settings_launch_type_beta_button",
        "settings_launch_beta_modal_title",
        # lancer-unique-v1 (Drasah 24/11) : wizard et fourche retirés
        "settings_launch_modal_title",
        "settings_launch_modal_names_label",
        "settings_launch_modal_names_placeholder",
        "settings_launch_modal_sas_label",
        "settings_launch_modal_sas_placeholder",
        "settings_start_season_button",
        "settings_start_beta_button",
        "settings_start_season_confirm_title",
        "settings_start_season_confirm_hint",
        "settings_start_season_confirm_button",
        "settings_start_beta_confirm_title",
        "settings_start_beta_confirm_hint",
        "settings_start_beta_confirm_button",
        "settings_start_beta_solo_confirm_title",
        "settings_start_beta_solo_confirm_hint",
        "settings_start_beta_solo_confirm_button",
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
        assert key not in fr, f"{key} must be GONE (lancer-unique-v1)"


def test_the_generic_start_confirm_card_is_a_declared_cycle_card() -> None:
    """The ONE departure rides the confirm card template + a surface."""
    from pathlib import Path

    from botforge.mods.kingdom.cogs import settings_panel as sp

    strings = sp.settings_strings("fr")
    view = sp._cycle_confirm_card(strings, "start")
    ids = _ids(view)
    assert "kingdom:cycle-confirm:start:yes" in ids
    assert "kingdom:cycle-confirm:start:no" in ids
    texts = _texts(view)
    assert strings["settings_start_confirm_title"] in texts
    assert strings["settings_start_confirm_hint"] in texts
    views = (
        Path(sp.__file__).resolve().parents[2] / "conf" / "views.yaml"
    ).read_text(encoding="utf-8")
    assert "panel:mod:kingdom:cycle:confirm-start:" in views, (
        "the generic confirm card must be a declared surface"
    )
    assert "panel:mod:kingdom:cycle:confirm-start-beta:" not in views, (
        "the retired fork surface is gone"
    )


@pytest.mark.asyncio
async def test_the_router_obeyes_the_lever_effective_value() -> None:
    """lancer-unique-v1 : the CLICK routes on the lever's EFFECTIVE value —
    a lever flipped between render and click is obeyed at click."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    interaction = _interaction()
    strings = sp.settings_strings("fr")
    routes: list[str] = []
    async def _beta_route(i: Any, s: Any, solo_ok: bool = False) -> None:
        routes.append(f"beta:{solo_ok}")

    async def _classic_route(i: Any, s: Any) -> None:
        routes.append("classic")

    with mock.patch.object(sp, "_parcours_is_beta", new=mock.AsyncMock(return_value=True)), \
            mock.patch.object(sp, "_start_beta", new=mock.AsyncMock(side_effect=_beta_route)), \
            mock.patch.object(sp, "_start_season", new=mock.AsyncMock(side_effect=_classic_route)):
        await sp._start_confirmed(interaction, strings)
    assert routes == ["beta:True"], "the beta lever routes beta, solo already confirmed"

    with mock.patch.object(sp, "_parcours_is_beta", new=mock.AsyncMock(return_value=False)), \
            mock.patch.object(sp, "_start_beta", new=mock.AsyncMock(side_effect=_beta_route)), \
            mock.patch.object(sp, "_start_season", new=mock.AsyncMock(side_effect=_classic_route)):
        await sp._start_confirmed(interaction, strings)
    assert routes[-1] == "classic", "the classic lever routes classic"


@pytest.mark.asyncio
async def test_the_lever_owns_the_start_label_suffix() -> None:
    """The label suffix rides the lever: Classique vs Bêta."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    strings = sp.settings_strings("fr")
    with mock.patch.object(sp, "_parcours_is_beta", new=mock.AsyncMock(return_value=False)):
        label = await sp._start_button_label(NS(), "42", strings)
    assert label == "🎯 Démarrer la saison — Classique"
    with mock.patch.object(sp, "_parcours_is_beta", new=mock.AsyncMock(return_value=True)):
        label = await sp._start_button_label(NS(), "42", strings)
    assert label == "🎯 Démarrer la saison — Bêta"


@pytest.mark.asyncio
async def test_the_herald_warns_only_free_living_realms() -> None:
    """📣 Prévenir les royaumes: the admin targets NO ONE — the herald DMs
    every non-archived, non-engaged realm's King and reports the count."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    realms = [
        NS(id="libre", king_id="1", archived_at=0, engagement=None),
        NS(id="autre", king_id="2", archived_at=0, engagement=None),
        NS(id="engage", king_id="3", archived_at=0, engagement={"season_id": "s"}),
        NS(id="mort", king_id="4", archived_at=99, engagement=None),
    ]

    class _Realms:
        async def realms(self) -> list[Any]:
            return realms

    stack = NS(realms=_Realms())
    interaction = _interaction()
    strings = sp.settings_strings("fr")
    dms: list[str] = []

    async def _dm(client: Any, user_id: str, content: str) -> Any:
        dms.append(user_id)
        return NS(id="dm")

    with mock.patch.object(sp, "_needs_stack", new=lambda s: (stack, None)), \
            mock.patch("botforge.mods.kingdom.cogs.common.dm_user_safe", new=_dm):
        await sp._announce_season(interaction, strings)

    assert sorted(dms) == ["1", "2"], "only the free living realms hear the herald"
    note = interaction.followup.sent[-1]
    assert note == strings["settings_announce_done"].format(count=2)


@pytest.mark.asyncio
async def test_the_herald_says_it_when_nobody_can_hear() -> None:
    """No eligible realm: the empty note, nothing thrown."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    class _Realms:
        async def realms(self) -> list[Any]:
            return []

    stack = NS(realms=_Realms())
    interaction = _interaction()
    strings = sp.settings_strings("fr")
    with mock.patch.object(sp, "_needs_stack", new=lambda s: (stack, None)):
        await sp._announce_season(interaction, strings)
    assert interaction.followup.sent[-1] == strings["settings_announce_empty"]


# ---------------------------------------------------------------------------
# The departures: the format owns the parcours flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_beta_departure_distributes_the_sas() -> None:
    """Bêta ⇂ arme le week-end, lève le drapeau, DÉMARRE, ferme le SAS."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdom(phase="setup")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=NS())
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "_sas_roster_counts", mock.AsyncMock(return_value=(2, 0))), \
            mock.patch.object(sp, "_consume_sas", mock.AsyncMock(return_value=2)), \
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

    kingdoms = _Kingdom(phase="started")
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

    stack = _Stack(_Kingdom())
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

    kingdoms = _Kingdom(phase="setup", beta_name="now")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=NS())
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "_sas_roster_counts", mock.AsyncMock(return_value=(2, 0))), \
            mock.patch.object(sp, "_consume_sas", mock.AsyncMock(return_value=2)), \
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

    kingdoms = _Kingdom(phase="setup")
    stack = _Stack(kingdoms)
    interaction = _interaction(state=None)  # no state_service ⇂ _lower_beta_flag False
    calls: list[str] = []

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "_sas_roster_counts", mock.AsyncMock(return_value=(2, 0))), \
            mock.patch.object(sp, "_consume_sas", mock.AsyncMock(return_value=2)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _switch_recorder(calls)):
        await sp._start_season(interaction, sp.settings_strings("fr"))

    assert kingdoms.start_calls, "no flag, no mutex — the classic departure stands"


@pytest.mark.asyncio
async def test_the_end_of_season_lowers_the_beta_flag() -> None:
    """fin-saison-v1 + depart-fourche : une saison finie baisse le drapeau."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    kingdoms = _Kingdom(phase="started")
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
