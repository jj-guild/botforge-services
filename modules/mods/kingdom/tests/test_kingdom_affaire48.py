"""Affaire 48 (Drasah 27/11) : UN seul déroulé de fin de saison.

Le verdict tombe (le TEMPS ou le bouton rouge), le monde SE FIGE
(hubs grisés), la Géopolitique porte l'annonce AVEC le bouton admin de
clôture (🔒 classique / 🔁 bêta), et le clic archive + rafraîchit le
panthéon (+ relance bêta). L'établi gris de test est SUPPRIMÉ, la
boucle bêta ne relance plus toute seule.
"""


from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest

_ROOT = Path(__file__).resolve().parents[1]


def _strings(locale: str = "fr") -> dict[str, str]:
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings

    return settings_strings(locale)


def _hub_strings(locale: str = "fr") -> dict[str, str]:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    return realm_strings(locale)


def _end_strings(locale: str = "fr") -> dict[str, str]:
    from botforge.mods.kingdom.cogs.phases import _end_strings as merged

    return merged(locale)


def _texts(view: Any) -> str:
    return "\n".join(
        str(c.content) for c in view.walk_children() if hasattr(c, "content")
    )


def _labels(view: Any) -> list[str]:
    return [
        str(c.label)
        for c in view.walk_children()
        if getattr(c, "label", None)
    ]


def _wire_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.panel as panel_module

    async def _fake_locale(gid: str) -> str:
        return "fr"

    monkeypatch.setattr(panel_module, "_guild_locale", _fake_locale)


class _Response:
    def __init__(self) -> None:
        self.done = False
        self.sent: list[str] = []

    def is_done(self) -> bool:
        return self.done

    async def send_message(self, content: str, ephemeral: bool = False) -> None:
        self.sent.append(content)


def _interaction(admin: bool = False, role: str | None = None) -> Any:
    return SimpleNamespace(
        locale="fr",
        user=SimpleNamespace(
            guild_permissions=SimpleNamespace(administrator=admin),
            roles=[SimpleNamespace(name=role)] if role else [],
        ),
        response=_Response(),
    )


# ---------------------------------------------------------------------------
# The close button: one DynamicItem, two kinds, template-safe
# ---------------------------------------------------------------------------


def test_the_close_button_builds_both_kinds() -> None:
    from botforge.mods.kingdom.cogs.settings_panel import SeasonCloseButton

    classic = SeasonCloseButton("🔒 Clôturer la saison", "classic")
    assert classic.custom_id == "kingdom:season:close:classic"
    assert re.fullmatch(r"kingdom:season:close:(classic|beta)", classic.custom_id)
    beta = SeasonCloseButton("🔁 Boucler", "beta")
    assert beta.custom_id == "kingdom:season:close:beta"
    # discord.py wraps the template as a class property — the literal
    # regex IS the contract (a DynamicItem with an empty match crashes)
    template = r"kingdom:season:close:(?P<kind>classic|beta)"
    assert re.fullmatch(template, beta.custom_id)
    assert re.fullmatch(template, classic.custom_id)


def test_the_workbench_is_gone_from_the_settings_actions() -> None:
    import botforge.mods.kingdom.cogs.settings_panel as settings_panel

    actions = {action for action, _key, _style in settings_panel._SETTINGS_ACTIONS}
    assert "season-test" not in actions
    assert "close-season" in settings_panel._CYCLE_CONFIRM_ACTIONS, (
        "the ended card carries the closure"
    )
    assert settings_panel._CYCLE_CONFIRM_HANDLERS["end-season"].__name__ == "_finish_season"
    assert settings_panel._CYCLE_CONFIRM_HANDLERS["close-season"].__name__ == "_end_season"


def test_views_yaml_declares_the_unified_end_surface() -> None:
    yaml_text = (_ROOT / "conf" / "views.yaml").read_text()
    assert "panel:mod:kingdom:season:end:" in yaml_text
    assert "panel:mod:kingdom:admin:season-test:" not in yaml_text


def test_locales_carry_the_unified_end_keys() -> None:
    keys = (
        "settings_finish_done",
        "settings_finish_showmatch",
        "settings_close_confirm_title",
        "settings_close_confirm_button",
        "season_close_classic_button",
        "season_close_beta_button",
        "season_close_not_admin",
        "season_end_admin_note",
        "settings_relaunch_beta_done",
    )
    for locale in ("fr", "en"):
        flat = (_ROOT / "conf" / "locales" / f"{locale}.yaml").read_text()
        for key in keys:
            assert key in flat, f"{key} missing from {locale}.yaml"
    # the frozen hub note lives in the REALM catalog, not the yaml
    for locale in ("fr", "en"):
        assert "realm_hub_frozen_note" in _hub_strings(locale)


# ---------------------------------------------------------------------------
# The season-end announcement: verdict + podium + the close button
# ---------------------------------------------------------------------------


def _report(beta: bool = False) -> dict[str, Any]:
    return {
        "kind": "end",
        "beta": beta,
        "winner_name": "AEGIS",
        "territories": {"AEGIS": 3, "HeN": 1},
    }


def _patch_report_text(monkeypatch: pytest.MonkeyPatch) -> None:
    import botforge.mods.kingdom.cogs.phases as phases_module

    async def _fake_text(strings: dict[str, str], report: dict[str, Any]) -> str:
        parts = [f"Verdict : **{report.get('winner')}**"]
        parts.append(str(report.get("podium", "")))
        return "\n".join(parts)

    monkeypatch.setattr(phases_module, "_event_report_text", _fake_text)


@pytest.mark.asyncio
async def test_the_classic_end_announcement_carries_the_close_button() -> None:
    import botforge.mods.kingdom.cogs.phases as phases_module

    view = await phases_module.season_end_layout(_end_strings(), _report(beta=False))
    body = _texts(view)
    assert "verdict est tombé : AEGIS" in body, "the verdict leads the announcement"
    assert "🥇 **AEGIS** — 3 territoire(s)" in body, "the podium rides the announcement"
    labels = _labels(view)
    assert "🔒 Clôturer la saison" in labels, "the classic close button"


@pytest.mark.asyncio
async def test_the_beta_end_announcement_carries_the_loop_button() -> None:
    import botforge.mods.kingdom.cogs.phases as phases_module

    view = await phases_module.season_end_layout(_end_strings(), _report(beta=True))
    assert "🔁 Boucler" in _labels(view), "a beta end loops, it never re-arms classic"


@pytest.mark.asyncio
async def test_an_admin_caused_end_is_flagged_in_the_announcement() -> None:
    import botforge.mods.kingdom.cogs.phases as phases_module

    view = await phases_module.season_end_layout(_end_strings(), _report(), cause="admin")
    body = _texts(view)
    assert "organisateur" in body, "the admin note leads the announcement"


@pytest.mark.asyncio
async def test_the_announcement_reaches_every_geopolitics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import botforge.mods.kingdom.cogs.phases as phases_module

    _patch_report_text(monkeypatch)
    _wire_locale(monkeypatch)
    # keep the announcement honest: the layout reads the merged catalog
    posted: list[Any] = []

    class _Channel:
        async def send(self, *args: Any, **kwargs: Any) -> None:
            posted.append(kwargs)

    class _Guild:
        id = "7"
        name = "jj-guild"
        categories: ClassVar[list[Any]] = []

    import botforge.mods.kingdom.cogs.battle as battle_module

    def _fake_geo(guild: Any) -> Any:
        return _Channel()

    monkeypatch.setattr(battle_module, "_geopolitics_channel", _fake_geo)
    import botforge.mods.kingdom.cogs.common as common_module

    monkeypatch.setattr(common_module, "wiring", lambda: None)
    bot = SimpleNamespace(guilds=[_Guild()])
    await phases_module.announce_season_end(bot, _report(beta=True), cause="natural")
    assert posted, "the announcement posts in the Géopolitique"


# ---------------------------------------------------------------------------
# The close guard: organisers only
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_close_guard_refuses_a_plain_player() -> None:
    from botforge.mods.kingdom.cogs.settings_panel import _close_guard

    interaction = _interaction(admin=False)
    assert await _close_guard(interaction) is False
    assert interaction.response.sent, "the refusal leaves a note"


@pytest.mark.asyncio
async def test_the_close_guard_accepts_admin_and_role() -> None:
    from botforge.mods.kingdom.cogs.settings_panel import _close_guard

    assert await _close_guard(_interaction(admin=True)) is True
    assert await _close_guard(_interaction(role="Kingdom Admin")) is True


# ---------------------------------------------------------------------------
# The beta loop: the pass is inert, the click relaunches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_pass_never_relaunches_anymore() -> None:
    from botforge.mods.kingdom.cogs.beta_loop import run_beta_loop_safe

    assert await run_beta_loop_safe(SimpleNamespace(guilds=[])) is None


@pytest.mark.asyncio
async def test_relaunch_beta_ignores_a_running_season() -> None:
    from botforge.mods.kingdom.cogs.beta_loop import relaunch_beta

    class _Kingdoms:
        async def current_season(self) -> Any:
            return SimpleNamespace(id="s-1", phase="started", beta_name="w")

    stack = SimpleNamespace(kingdoms=_Kingdoms())
    assert await relaunch_beta(SimpleNamespace(guilds=[]), stack) is None


# ---------------------------------------------------------------------------
# The frozen world: the hubs grey out while the closure waits
# ---------------------------------------------------------------------------


def _realm() -> Any:
    return SimpleNamespace(name="AEGIS", slug="aegis", engagement=SimpleNamespace(kingdom_id="k-1"))


def _disabled(view: Any) -> list[bool]:
    return [bool(c.disabled) for c in view.walk_children() if hasattr(c, "disabled")]


def test_the_frozen_hub_greys_the_player_buttons() -> None:
    from botforge.mods.kingdom.cogs.realms import hub_layout

    strings = _hub_strings()
    alive = hub_layout(_realm(), strings, dormant=False)
    frozen = hub_layout(_realm(), strings, dormant=False, frozen=True)
    assert strings["realm_hub_frozen_note"] in _texts(frozen), "the note explains"
    # the informatif settings button is ALWAYS grey — compare the REST
    alive_by_label = {
        str(c.label): bool(c.disabled) for c in alive.walk_children() if getattr(c, "label", None)
    }
    frozen_by_label = {
        str(c.label): bool(c.disabled) for c in frozen.walk_children() if getattr(c, "label", None)
    }
    for label, disabled in frozen_by_label.items():
        if label in alive_by_label:
            assert disabled, f"the frozen world greys « {label} »"
            if label != str(strings["realm_user_settings_button"]):
                assert not alive_by_label[label], f"a live hub keeps « {label} » open"


def test_a_dormant_hub_never_needs_the_freeze() -> None:
    from botforge.mods.kingdom.cogs.realms import hub_layout

    strings = _hub_strings()
    dormant = hub_layout(_realm(), strings, dormant=True, frozen=True)
    assert strings["realm_hub_frozen_note"] not in _texts(dormant), (
        "a dormant hub already reads asleep"
    )
