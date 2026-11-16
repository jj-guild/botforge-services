"""The seasonal panels: the phase machine, the row rule, Postuler.

The drastic simplification (owner spec 2026-11-15): a season is a
name, a phase (préparation -> inscriptions ouvertes -> en attente
d'ouverture -> ouverte -> fermée, with a direct start from
inscriptions), TODO criteria, and the admin validation in the
candidates channel. Regression pins:

- the 5-per-row rule stays hardcoded in the SDK (``split_action_rows``);
- Postuler never asks the pseudo or the AoE2 profile ids in a form:
  both resolve from the core; a player missing either one is
  redirected to #general (``/register``).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

import botforge.discord.ui.panels_provisioning as panels_provisioning
from botforge.discord.season_panels import (
    SeasonApplyButton,
    build_candidates_panel,
    build_seasons_panel,
)
from botforge.discord.ui.factory import (
    MAX_ITEMS_PER_ROW,
    Row,
    UILayoutError,
    split_action_rows,
)
from botforge.discord.ui.factory import (
    Button as SdkButton,
)


def _rows_of(view: discord.ui.LayoutView) -> list[Any]:
    return [c for c in view.children if isinstance(c, discord.ui.ActionRow)]


def _interaction(bot: Any) -> MagicMock:
    interaction = MagicMock()
    interaction.client = bot
    interaction.guild_id = 123
    user = MagicMock()
    user.id = 42
    user.display_name = "Drasah"
    user.name = "drasah"
    interaction.user = user
    interaction.response = MagicMock()
    interaction.response.is_done = MagicMock(return_value=True)
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.followup = MagicMock()
    interaction.followup.send = AsyncMock()
    return interaction


class TestSdkRowRule:
    def test_row_rejects_more_than_five_items(self) -> None:
        with pytest.raises(UILayoutError):
            Row(*[SdkButton(label=str(i), url="https://example.com") for i in range(MAX_ITEMS_PER_ROW + 1)])

    def test_split_action_rows_chunks_at_the_sdk_limit(self) -> None:
        items = [discord.ui.Button(label=str(i), custom_id=f"season:x:{i}") for i in range(8)]
        rows = split_action_rows(items)
        assert [len(r.children) for r in rows] == [MAX_ITEMS_PER_ROW, 3]

    def test_split_action_rows_empty_list(self) -> None:
        assert split_action_rows([]) == []


class _FakeEnrollment:
    def __init__(self, applications: list[Any]) -> None:
        self._applications = applications

    async def list_applications(self, guild_id: str, state: str | None = None) -> list[Any]:
        return [a for a in self._applications if state is None or a.state == state]


class TestCandidatesPanel:
    async def test_the_public_panel_carries_no_admin_buttons(self) -> None:
        pending = [SimpleNamespace(user_id=str(100 + i), display_name=f"P{i}", state="pending") for i in range(3)]
        stack = SimpleNamespace(enrollment=_FakeEnrollment(pending))
        bot = SimpleNamespace(season_stacks={("kingdom", "123"): stack})
        view = await build_candidates_panel(bot, "123", "kingdom")
        rows = _rows_of(view)
        # the public view: NO rows of buttons at all (the decisions are
        # private — the admin announce + the ephemeral bar)
        assert not rows


class TestPhasePanel:
    async def test_the_panel_renders_the_phase_and_transitions(self) -> None:
        bot = SimpleNamespace()
        bot.state_service = None
        bot.season_stacks = {}
        view = await build_seasons_panel(bot, "123", "kingdom")
        rows = _rows_of(view)
        buttons = [i for r in rows for i in r.children]
        # no active season: the create button only
        assert any("Créer" in str(getattr(b, "label", "")) for b in buttons)


class _FakeIdentity:
    def __init__(self, name: str | None) -> None:
        self._name = name

    async def get_user(self, user_id: str) -> Any:
        assert user_id == "discord:42"
        return SimpleNamespace(display_name=self._name) if self._name else None


class _FakeRegistration:
    def __init__(self, bindings: list[dict[str, str]]) -> None:
        self._bindings = bindings

    async def list_bindings(self, user_id: str) -> list[dict[str, str]]:
        return list(self._bindings)


class _RecordingEnrollment:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def apply(self, guild_id: str, user_id: str, display_name: str, profiles: Any = None, **kwargs: Any) -> Any:
        self.calls.append({"display_name": display_name, "profiles": profiles})
        return SimpleNamespace(state="pending", reasons=())


def _apply_bot(identity: Any, registration: Any, enrollment: Any) -> SimpleNamespace:
    registry = SimpleNamespace(get=lambda mod: SimpleNamespace(required_games=("aoe2",)))
    stack = SimpleNamespace(enrollment=enrollment)
    return SimpleNamespace(
        identity_service=identity,
        registration_service=registration,
        registry=registry,
        season_stacks={("kingdom", "123"): stack},
    )


@pytest.fixture()
def general_channel(monkeypatch: pytest.MonkeyPatch) -> None:
    """Resolve the root scope's general channel to a fixed id."""

    async def _fake_channel(guild_id: str, scope: str, key: str) -> str | None:
        assert (scope, key) == ("root", "general")
        return "555"

    monkeypatch.setattr(panels_provisioning, "stored_channel_id", _fake_channel)


class TestPostulerFlow:
    async def test_the_core_pseudo_and_aoe2_profiles_feed_the_application(self) -> None:
        enrollment = _RecordingEnrollment()
        bot = _apply_bot(
            _FakeIdentity("Rollon"),
            _FakeRegistration(
                [
                    {"game_key": "aoe2", "profile_id": "111"},
                    {"game_key": "aoe2", "profile_id": "222"},
                    {"game_key": "aoe2", "profile_id": "111"},  # duplicate
                    {"game_key": "other", "profile_id": "999"},  # not the mod's game
                ]
            ),
            enrollment,
        )
        interaction = _interaction(bot)
        await SeasonApplyButton("kingdom").callback(interaction)
        assert interaction.response.defer.await_count == 1
        assert len(enrollment.calls) == 1
        call = enrollment.calls[0]
        assert call["display_name"] == "Rollon"  # the core's pseudo, never a form field
        assert call["profiles"] == ["111", "222"]  # the mod's game bindings only, deduplicated
        assert interaction.followup.send.await_count == 1
        text = interaction.followup.send.await_args.args[0]
        assert "en attente" in text and "`111`" in text and "`222`" in text

    async def test_no_name_and_no_profile_redirects_to_general(self, general_channel: None) -> None:
        enrollment = _RecordingEnrollment()
        bot = _apply_bot(_FakeIdentity(None), _FakeRegistration([]), enrollment)
        interaction = _interaction(bot)
        await SeasonApplyButton("kingdom").callback(interaction)
        assert enrollment.calls == []
        assert interaction.followup.send.await_count == 1
        text = interaction.followup.send.await_args.args[0]
        assert "<#555>" in text and "/register" in text

    async def test_a_missing_profile_alone_also_redirects(self, general_channel: None) -> None:
        enrollment = _RecordingEnrollment()
        bot = _apply_bot(_FakeIdentity("Rollon"), _FakeRegistration([]), enrollment)
        interaction = _interaction(bot)
        await SeasonApplyButton("kingdom").callback(interaction)
        assert enrollment.calls == []
        text = interaction.followup.send.await_args.args[0]
        assert "<#555>" in text and "/register" in text

    async def test_a_missing_name_alone_also_redirects(self, general_channel: None) -> None:
        enrollment = _RecordingEnrollment()
        bot = _apply_bot(
            _FakeIdentity(None), _FakeRegistration([{"game_key": "aoe2", "profile_id": "111"}]), enrollment
        )
        interaction = _interaction(bot)
        await SeasonApplyButton("kingdom").callback(interaction)
        assert enrollment.calls == []
        text = interaction.followup.send.await_args.args[0]
        assert "<#555>" in text and "/register" in text
