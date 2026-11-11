"""Unit tests for the mods catalog forum (botforge-services#374)."""

from __future__ import annotations

import re

from botforge.discord.mods_forum import (
    _INSTALL_TEMPLATE,
    _UNINSTALL_TEMPLATE,
    ModUninstallModal,
    _catalog_post_id,
    _catalog_post_view,
)


def test_catalog_post_view_carries_the_id_footer() -> None:
    """The post view carries its id footer (the declared-views norm)."""
    view = _catalog_post_view("mod", "kingdoms", installed=True, labels={"title": "kingdoms"})
    rendered = str(view.to_components())
    assert "modcatalog:post:mod:kingdoms" in rendered


def test_installed_post_shows_uninstall_not_install() -> None:
    """An installed item offers Uninstall; a non-installed one offers Install."""
    installed = _catalog_post_view("mod", "kingdoms", installed=True, labels={})
    rendered = str(installed.to_components())
    assert "modcatalog:uninstall:mod:kingdoms" in rendered
    assert "modcatalog:install:mod:kingdoms" not in rendered
    missing = _catalog_post_view("game", "aoe2", installed=False, labels={})
    rendered_missing = str(missing.to_components())
    assert "modcatalog:install:game:aoe2" in rendered_missing


def test_required_games_render_on_the_post() -> None:
    """A mod's required games ride the post (the dependency is visible)."""
    view = _catalog_post_view("mod", "kingdoms", installed=False, required_games=("aoe2",), labels={})
    rendered = str(view.to_components())
    assert "aoe2" in rendered


def test_install_button_rebuilds_from_the_wire() -> None:
    """The DynamicItem template parses the custom id back (from_custom_id)."""
    assert re.search(_INSTALL_TEMPLATE, "modcatalog:install:mod:kingdoms")
    assert re.search(_UNINSTALL_TEMPLATE, "modcatalog:uninstall:game:aoe2")
    assert not re.search(_INSTALL_TEMPLATE, "modcatalog:uninstall:mod:kingdoms")


def test_uninstall_modal_selects_are_optional() -> None:
    """Both selects (data, channels/roles) are optional — the modal trap."""
    modal = ModUninstallModal(
        kind="mod",
        name="kingdoms",
        title="Uninstall kingdoms",
        data_label="Data",
        data_keep="Keep the data",
        data_delete="Delete the data",
        channels_label="Channels and roles",
        channels_keep="Keep the channels",
        channels_delete="Delete the channels",
        done="Uninstalled.",
        refused="Refused: {reason}",
    )
    for select in (modal.data_select, modal.channels_select):
        assert select.required is False
        assert select.min_values == 0
        assert {opt.value for opt in select.options} == {ModUninstallModal.KEEP, ModUninstallModal.DELETE}


def test_catalog_post_id_is_stable() -> None:
    """The bookkeeping id is deterministic (guild, kind, name)."""
    assert _catalog_post_id("123", "mod", "kingdoms") == "123:mod:kingdoms"
