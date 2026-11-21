"""The ⚙️ Paramètres panel (epic #412 T1) — wiring smoke tests.

The admin cockpit is ONE template (``panel:mod:kingdom:admin:console``)
instantiated by the ``SETTINGS_ACTIONS`` table: every action rides a
platform seam (service contract, provisioning seams, beta phase
toggle, ``require_admin``) — these tests pin the contract down.
"""

from __future__ import annotations


def test_settings_panel_module_imports() -> None:
    """The panel exposes its template key, builder and button class."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        CONSOLE_VIEW_KEY,
        build_settings_panel,
    )

    assert CONSOLE_VIEW_KEY == "panel:mod:kingdom:admin:console"
    assert callable(build_settings_panel)


def test_settings_panel_is_one_template_of_twelve_actions() -> None:
    """The designer's actions, verbatim order (capture image-12 + tranches)."""
    from botforge.mods.kingdom.cogs import settings_panel

    actions = tuple(action for action, _key, _style in settings_panel._SETTINGS_ACTIONS)
    assert actions == (
        "launch",
        "start-season",
        "start-beta",
        "status",
        "deploy",
        "sync",
        "reset",
        "assign",
        "add-kingdom",
        "season-mode",
        "remove",
        # console-etats-regie-v1 (Drasah 21/11): the false start — the
        # organiser's last resort, confirmation card included
        "false-start",
        # fin-saison-v1 (Drasah 21/11): « Terminer la saison » — the test
        # loop closes cleanly (engine archive + realms back dormant)
        "end-season",
    )
    # every action key answers a DynamicItem custom id + a FR label
    from botforge.mods.kingdom.cogs.settings_panel import SettingsActionButton

    assert (
        SettingsActionButton("launch", "▶️ Lancer la saison").custom_id
        == "kingdom:settings:launch"
    )


def test_confirm_card_uses_its_own_custom_id_namespace() -> None:
    """The confirm card's yes/no ids never match the actions' template.

    discord.py 2.7 dispatches a click to EVERY registered dynamic
    template that fullmatches the id AND to the message's stored view:
    a ``kingdom:settings:reset-yes`` id would fire BOTH handlers (the
    second response dies with 40060) — the confirm card rides
    ``kingdom:confirm:<action>:<choice>`` instead.
    """
    import re

    from botforge.mods.kingdom.cogs.settings_panel import (
        SettingsActionButton,
        _confirm_card,
        settings_strings,
    )

    card = _confirm_card(settings_strings("fr"), "reset")
    ids = [
        str(item.custom_id)
        for item in card.walk_children()
        if getattr(item, "custom_id", None)
    ]
    assert sorted(ids) == ["kingdom:confirm:reset:no", "kingdom:confirm:reset:yes"]
    template = re.compile(SettingsActionButton.__discord_ui_compiled_template__.pattern)
    assert not any(template.fullmatch(i) for i in ids), (
        "the confirm ids must NOT fullmatch the settings actions' template"
    )


def test_settings_actions_declared_in_views_yaml() -> None:
    """The confirm card is declared by the mod; the console surface by the SDK.

    ``panel:mod:kingdom:admin:console`` is auto-declared for every mod by
    ``mod_views.declare_mod_views`` — the mod's views.yaml only carries
    its own extras (the inline confirm card).
    """
    from pathlib import Path

    views = (
        Path(__file__).resolve().parents[1]
        / "conf"
        / "views.yaml"
    ).read_text(encoding="utf-8")
    assert "panel:mod:kingdom:admin:console:confirm:" in views
    assert "panel:mod:kingdom:admin:console:" not in views.replace(
        "panel:mod:kingdom:admin:console:confirm:", ""
    ), "the console surface itself belongs to the SDK, not the mod's yaml"


def test_settings_strings_parity() -> None:
    """Every action's label exists in both locales; formats have arity."""
    from botforge.mods.kingdom.cogs.settings_panel import (
        _SETTINGS_ACTIONS,
        settings_strings,
    )

    keys = ["settings_title", "settings_section", "settings_denied", "settings_cancelled"]
    keys += [key for _action, key, _style in _SETTINGS_ACTIONS]
    keys += [
        "settings_deploy_done",
        "settings_sync_done",
        "settings_reset_done",
        "settings_mode_imposed",
        "settings_mode_free",
        # the modals' TextInput labels (Discord caps them at 45 chars)
        "settings_launch_modal_names_label",
        "settings_launch_modal_names_placeholder",
        "settings_assign_modal_player_label",
        "settings_assign_modal_kingdom_label",
        "settings_assign_modal_role_label",
        "settings_add_kingdom_modal_name_label",
        "settings_remove_modal_player_label",
        "settings_remove_modal_reason_label",
    ]
    for locale in ("fr", "en"):
        for key in (
            "settings_launch_modal_names_label",
            "settings_assign_modal_player_label",
            "settings_assign_modal_kingdom_label",
            "settings_assign_modal_role_label",
            "settings_add_kingdom_modal_name_label",
            "settings_remove_modal_player_label",
            "settings_remove_modal_reason_label",
        ):
            assert len(str(settings_strings(locale)[key])) <= 45, (
                f"{key} exceeds Discord's 45-char TextInput label cap in {locale}"
            )
    for locale in ("fr", "en"):
        s = settings_strings(locale)
        for key in keys:
            assert s.get(key), f"missing {key} in {locale}"
        s["settings_error"].format("boom")
        s["settings_deploy_done"].format(channels=1, roles=2, pins=3)
        s["settings_sync_done"].format(pins=1)
        s["settings_reset_done"].format(channels=4)


def test_the_settings_panel_builds_with_a_fake_service() -> None:
    """The pinned panel renders with a live season (status card data)."""
    import asyncio

    from botforge.mods.kingdom.cogs.settings_panel import build_settings_panel

    view = asyncio.run(build_settings_panel("123"))
    assert view is not None


def test_modals_build_without_deprecation_warnings() -> None:
    """discord.py 2.7: a TextInput rides a discord.ui.Label — the label
    property is deprecated (DeprecationWarning in the bot logs)."""
    import warnings

    from botforge.mods.kingdom.cogs.settings_panel import (
        _AddKingdomModal,
        _AssignModal,
        _LaunchModal,
        _RemoveModal,
        settings_strings,
    )

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        for cls in (_LaunchModal, _AssignModal, _AddKingdomModal, _RemoveModal):
            modal = cls(settings_strings("fr"))
            labels = [c for c in modal.walk_children() if type(c).__name__ == "Label"]
            assert labels, f"{cls.__name__}: every input must ride a discord.ui.Label"
            for label in labels:
                assert len(label.text) <= 45, "Label text caps at 45 chars (Discord 50035)"


def test_service_failures_map_to_user_facing_notes() -> None:
    """A KingdomError code maps to its i18n note (the user ALWAYS gets an
    answer — the log is never the only report); unknown errors fall back
    to the generic failure note."""
    from botforge.mods.kingdom.cogs.common import service_failure_note
    from botforge.mods.kingdom.cogs.settings_panel import settings_strings
    from botforge.mods.kingdom.service import KingdomLimitError, NoSeasonError

    err_keys = (
        "settings_err_kingdoms_no_season",
        "settings_err_kingdoms_kingdom_limit",
        "settings_err_kingdoms_kingdom_not_found",
        "settings_err_kingdoms_kingdom_full",
        "settings_err_kingdoms_name_invalid",
        "settings_err_kingdoms_already_enrolled",
    )
    for locale in ("fr", "en"):
        s = settings_strings(locale)
        for key in err_keys:
            assert s.get(key), f"missing {key} in {locale}"
    s = settings_strings("fr")
    assert (
        service_failure_note(s, "settings_failed", NoSeasonError("no season is running"))
        == s["settings_err_kingdoms_no_season"]
    )
    assert (
        service_failure_note(s, "settings_failed", KingdomLimitError("limit"))
        == s["settings_err_kingdoms_kingdom_limit"]
    )
    assert (
        service_failure_note(s, "settings_failed", RuntimeError("boom"))
        == s["settings_failed"].format("boom")
    )


def test_the_launch_modal_arms_the_beta_type_on_demand() -> None:
    """season-type-at-launch (Drasah 20/11): the « beta » type calls the
    engine's activate_beta with the « now » preset right after the
    fresh launch; every other value (empty, « normal ») never does."""
    import asyncio

    from botforge.mods.kingdom.cogs.settings_panel import _arm_compressed_beta

    calls: list[tuple[object, ...]] = []

    class _Events:
        async def activate_beta(self, name: str, *args: object, **kwargs: object) -> dict[str, object]:
            calls.append((name, kwargs.get("start_at")))
            return {"name": name}

    class _Stack:
        events = _Events()

    asyncio.run(_arm_compressed_beta(_Stack()))
    assert len(calls) == 1 and calls[0][0] == "now", "the beta type arms the « now » preset"


def test_the_reset_relands_the_mod_pins_immediately() -> None:
    """reset-repins-v1 (Drasah 20/11): the reset/sync/deploy actions run
    the MOD-wide pin pass too — the salons never wait on the 5-min
    refresher (« la catégorie admin est vide, rien n'a été remis »:
    only the SDK menus used to land, the mod's pins showed up late)."""
    import asyncio
    from types import SimpleNamespace

    from botforge.mods.kingdom.cogs import settings_panel as mod_settings

    calls: list[str] = []

    async def _fake_delete(bot: object, guild_id: str, mod: str) -> int:
        calls.append("delete")
        return 3

    async def _fake_roles(bot: object, guild_id: str, mod: str) -> int:
        return 2

    async def _fake_channels(bot: object, guild_id: str, mod: str) -> int:
        return 4

    async def _fake_pins(bot: object, guild_id: str, mod: str) -> int:
        calls.append("sdk_pins")
        return 1

    async def _fake_pass(bot: object) -> int:
        calls.append("mod_pin_pass")
        return 9

    interaction = SimpleNamespace(
        client=object(),
        guild_id="42",
        locale=None,
    )
    import unittest.mock as mock

    with (
        mock.patch("botforge.discord.mods_forum.delete_mod_scope", _fake_delete),
        mock.patch("botforge.discord.mods_forum.provision_mod_roles", _fake_roles),
        mock.patch("botforge.discord.mods_forum.provision_mod_channels", _fake_channels),
        mock.patch("botforge.discord.scope_pins.ensure_mod_pins", _fake_pins),
        mock.patch(
            "botforge.mods.kingdom.cogs.time_machine.run_mod_pin_refresh_pass",
            _fake_pass,
        ),
    ):
        note = asyncio.run(mod_settings._run_provisioning(interaction, "reset"))

    assert "mod_pin_pass" in calls, "the reset re-lands the mod's pins, not only the SDK menus"
    assert "sdk_pins" in calls and calls.index("sdk_pins") < calls.index("mod_pin_pass")
    assert "3" in note  # settings_reset_done carries the deleted count

    # pins-diag-wired: the ephemeral answer rides the per-pin diagnosis
    async def _fake_diag(client: object, guild_id: str) -> list[str]:
        return ["**Panneaux du mod — diagnostic**", "• `machine` — message 42 supprimé"]

    with (
        mock.patch("botforge.discord.mods_forum.delete_mod_scope", _fake_delete),
        mock.patch("botforge.discord.mods_forum.provision_mod_roles", _fake_roles),
        mock.patch("botforge.discord.mods_forum.provision_mod_channels", _fake_channels),
        mock.patch("botforge.discord.scope_pins.ensure_mod_pins", _fake_pins),
        mock.patch(
            "botforge.mods.kingdom.cogs.pins_diag.admin_pin_lines",
            _fake_diag,
        ),
        mock.patch(
            "botforge.mods.kingdom.cogs.time_machine.run_mod_pin_refresh_pass",
            _fake_pass,
        ),
    ):
        note = asyncio.run(mod_settings._run_provisioning(interaction, "deploy"))

    assert "diagnostic" in note and "message 42" in note
