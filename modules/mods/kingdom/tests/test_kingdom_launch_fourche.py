"""lancement-fourche-v1 (Drasah 21/11).

« Je lance ma saison, et APRÈS on me pose la question classique ou
bêta. » Un seul geste ▶️ Lancer la saison, PUIS une carte fourche
visible — plus jamais un champ texte à deviner pour dire le format.
Le format pilote le drapeau parcours (classic ⇂ flag baissé,
bêta ⇂ flag levé), le sas reste une question d'admin indépendante,
et les deux flous (« le switch dit ouvert mais rien ne tourne »)
sont tués par le hint régie + la phrase season_none.
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

    async def send_modal(self, modal: Any) -> None:
        self.modal = modal

    modal: Any = None


class _Follow:
    def __init__(self) -> None:
        self.sent: list[Any] = []

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self.sent.append((content, kwargs))
        return NS(id="f1")


@pytest.fixture(autouse=True)
def _clean_live_window() -> Any:
    from botforge.discord.ui import ephemeral_windows as ew

    ew._live.clear()
    yield
    ew._live.clear()


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
    """Launch/order fake — the engine seam records the call."""

    def __init__(self) -> None:
        self.launched: list[Any] = []
        self.events = NS(activate_beta=mock.AsyncMock())

    async def launch(self, imposed: Any) -> None:
        self.launched.append(imposed)


class _Stack:
    def __init__(self) -> None:
        self.kingdoms = _Kingdoms()
        self.events = self.kingdoms.events


def _ids(view: Any) -> list[str]:
    return [
        str(item.custom_id) for item in view.walk_children() if getattr(item, "custom_id", None)
    ]


def _texts(view: Any) -> str:
    return "\n".join(str(c.content) for c in view.walk_children() if hasattr(c, "content"))


# ---------------------------------------------------------------------------
# The fork card
# ---------------------------------------------------------------------------


def test_the_fork_card_is_one_gesture_two_visible_formats() -> None:
    """3 buttons on a declared surface — the format is VISIBLE, never typed."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    view = sp._launch_type_card(sp.settings_strings("fr"))
    ids = _ids(view)
    assert "kingdom:launch:fork:classic" in ids
    assert "kingdom:launch:fork:beta" in ids
    assert "kingdom:launch:fork:cancel" in ids
    assert len(ids) == 3
    texts = _texts(view)
    assert sp.settings_strings("fr")["settings_launch_type_title"][:12] in texts
    assert sp.settings_strings("fr")["settings_launch_type_hint"][:12] in texts


def test_the_fork_labels_answer_the_designers_question() -> None:
    """Each side of the same catalogue — the labels say classic vs bêta."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    for loc in ("fr", "en"):
        strings = sp.settings_strings(loc)
        assert strings["settings_launch_type_classic_button"]
        assert strings["settings_launch_type_beta_button"]


def test_the_classic_modal_lost_the_hidden_type_field() -> None:
    """The retired hole: NO text input ever says the format again."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    modal = sp._LaunchModal(sp.settings_strings("fr"))
    ids = _ids(modal)
    assert "kingdom:settings:launch:type" not in ids
    assert "kingdom:settings:launch:names" in ids
    assert "kingdom:settings:launch:sas" in ids


def test_the_beta_modal_is_the_sas_question_only() -> None:
    """The beta path: no imposed names, no account — Drasah's sas alone."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    modal = sp._BetaLaunchModal(sp.settings_strings("fr"))
    ids = _ids(modal)
    assert "kingdom:settings:launch:sas" in ids
    assert "kingdom:settings:launch:names" not in ids
    assert "kingdom:settings:launch:type" not in ids


def test_the_new_keys_exist_in_both_locales() -> None:
    """Frozen contract: the fork keys ship fr AND en, old type keys gone."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    keys = (
        "settings_launch_type_title",
        "settings_launch_type_hint",
        "settings_launch_type_classic_button",
        "settings_launch_type_beta_button",
        "settings_launch_beta_modal_title",
        "settings_regie_sas_idle_hint",
    )
    for loc in ("fr", "en"):
        strings = sp.settings_strings(loc)
        for key in keys:
            assert strings.get(key), f"{loc} missing {key}"
    # the RETIRED keys must be GONE (a stale hole misleads no one)
    fr = sp.settings_strings("fr")
    assert "settings_launch_modal_type_label" not in fr
    assert "settings_launch_modal_type_placeholder" not in fr


def test_the_regie_drawer_says_when_nothing_applies() -> None:
    """The sas switch keeps its value — but says it bites at the NEXT season."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    strings = sp.settings_strings("fr")
    idle = sp._regie_drawer(strings, season_live=False)
    live = sp._regie_drawer(strings, season_live=True)
    assert strings["settings_regie_sas_idle_hint"][:10] in _texts(idle)
    assert strings["settings_regie_sas_idle_hint"][:10] not in _texts(live)


def test_the_season_none_note_points_at_the_cockpit() -> None:
    """Blanc's side of the fork fix: the button appears once a season exists."""
    from botforge.mods.kingdom.cogs import realm_strings

    assert "cockpit" in realm_strings._REALM_STRINGS["fr"]["season_none"]
    assert "cockpit" in realm_strings._REALM_STRINGS["en"]["season_none"]


# ---------------------------------------------------------------------------
# The submits: the format owns the parcours flag
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_classic_submit_launches_and_lowers_the_flag() -> None:
    """Classic ⇂ a lingering beta flag lowers NOW (the mutex trap at « Démarrer »)."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    stack = _Stack()
    interaction = _interaction(state=NS())
    modal = sp._LaunchModal(sp.settings_strings("fr"))
    calls: list[str] = []

    async def _set_switch(client: Any, guild: str, key: str, value: bool) -> bool:
        calls.append(f"{key}={value}")
        return True

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _set_switch), \
            mock.patch("botforge.mods.kingdom.cogs.conscription_gate.run_conscription_gate_pass", mock.AsyncMock()), \
            mock.patch("botforge.core.services.beta.is_beta", new=mock.AsyncMock(return_value=True)), \
            mock.patch("botforge.core.services.beta.exit_beta", new=mock.AsyncMock()) as exit_beta, \
            mock.patch.object(type(modal.sas), "value", new_callable=mock.PropertyMock, return_value=""):
        await modal.on_submit(interaction)

    assert stack.kingdoms.launched == [None]
    exit_beta.assert_awaited_once()
    # the sas defaults OPEN — an empty answer is NOT a refusal
    assert "season_entry_open=True" in calls


@pytest.mark.asyncio
async def test_the_beta_submit_launches_arms_and_raises_the_flag() -> None:
    """Bêta ⇂ flag levé : la saison compressée roule sous règles bêta."""
    from botforge.mods.kingdom.cogs import settings_panel as sp

    stack = _Stack()
    interaction = _interaction(state=NS())
    modal = sp._BetaLaunchModal(sp.settings_strings("fr"))
    calls: list[str] = []

    async def _set_switch(client: Any, guild: str, key: str, value: bool) -> bool:
        calls.append(f"{key}={value}")
        return True

    with mock.patch.object(sp, "_needs_stack", lambda s: (stack, None)), \
            mock.patch.object(sp, "refresh_live_pins_after", mock.AsyncMock()), \
            mock.patch("botforge.mods.kingdom.cogs.regie.set_switch", _set_switch), \
            mock.patch("botforge.mods.kingdom.cogs.conscription_gate.run_conscription_gate_pass", mock.AsyncMock()), \
            mock.patch("botforge.core.services.beta.is_beta", new=mock.AsyncMock(return_value=False)), \
            mock.patch("botforge.core.services.beta.enter_beta", new=mock.AsyncMock()) as enter_beta, \
            mock.patch.object(type(modal.sas), "value", new_callable=mock.PropertyMock, return_value="non"):
        await modal.on_submit(interaction)

    assert stack.kingdoms.launched == [None]
    stack.kingdoms.events.activate_beta.assert_awaited_once()
    enter_beta.assert_awaited_once()
    # an explicit « non » CLOSES the sas — the admin's word is the limit
    assert "season_entry_open=False" in calls
