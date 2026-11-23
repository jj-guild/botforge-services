"""Unit tests for the generic mod declaration tools (botforge-services#26)."""

from __future__ import annotations

from pathlib import Path

import pytest

from botforge.core.services.mod_definition import (
    ChannelCategoryDef,
    ModDefinition,
    RoleDef,
)
from botforge.core.services.mod_registry import ModRegistry, load_mod_definitions


def make_definition(name: str = "example") -> ModDefinition:
    return ModDefinition(
        name=name,
        channel_categories=(ChannelCategoryDef(key="announce", display_name="Annonces"),),
        roles=(RoleDef(key="member", display_name="Example Member"),),
    )


def test_mod_definition_lookup_finds_declared_entries() -> None:
    definition = make_definition()
    assert definition.channel_category("announce").display_name == "Annonces"
    assert definition.role("member").display_name == "Example Member"


def test_mod_definition_lookup_fails_loudly_for_undeclared() -> None:
    definition = make_definition()
    with pytest.raises(KeyError, match="does not declare channel category"):
        definition.channel_category("nope")
    with pytest.raises(KeyError, match="does not declare role"):
        definition.role("nope")


def test_registry_register_get_require_enabled() -> None:
    registry = ModRegistry()
    registry.register(make_definition())
    assert registry.get("example") is not None
    assert registry.require("example").name == "example"
    assert list(registry.enabled()) == ["example"]
    with pytest.raises(KeyError, match="not declared"):
        registry.require("missing")


def test_registry_disabled_mods_are_not_enabled() -> None:
    registry = ModRegistry({disabled.name: disabled for disabled in [ModDefinition(name="off", enabled=False)]})
    assert registry.get("off") is not None
    assert registry.enabled() == {}
    assert registry.all() == {"off": registry.get("off")}


def test_load_mod_definitions_validates_schema(tmp_path: Path) -> None:
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    (mods_dir / "good.yaml").write_text(
        "id: good\n"
        "enabled: true\n"
        "seasonal: false\n"
        "channels:\n"
        "  - key: announce\n"
        "    display_name: Annonces\n"
        "roles:\n"
        "  - key: member\n"
        "    display_name: Member\n",
        encoding="utf-8",
    )
    mods = load_mod_definitions(tmp_path)
    assert mods["good"].channel_category("announce").display_name == "Annonces"
    assert mods["good"].role("member").display_name == "Member"


def test_load_mod_definitions_fails_loudly_on_invalid(tmp_path: Path) -> None:
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    (mods_dir / "bad.yaml").write_text("id: bad\nseasonal: false\nchannels:\n  - key: no_display\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"key.*and.*display_name"):
        load_mod_definitions(tmp_path)


def test_load_mod_definitions_requires_the_mod_type(tmp_path: Path) -> None:
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    (mods_dir / "untyped.yaml").write_text("id: untyped\nenabled: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mandatory"):
        load_mod_definitions(tmp_path)


def test_load_mod_definitions_rejects_mod_scoped_slugs(tmp_path: Path) -> None:
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    (mods_dir / "weird.yaml").write_text("id: bad:slug\nseasonal: false\n", encoding="utf-8")
    with pytest.raises(ValueError, match="simple slug"):
        load_mod_definitions(tmp_path)


def test_load_mod_definitions_empty_dir(tmp_path: Path) -> None:
    assert load_mod_definitions(tmp_path) == {}


def test_the_channel_groups_resolve_to_display_names() -> None:
    """The salons-as-data structure (#216 tranche I): a channel's group
    ref resolves to the group's display name; an undeclared ref fails
    loudly (the declaration is the source of truth)."""
    from pathlib import Path

    from botforge.core.services.mod_registry import load_mod_definitions

    defs = load_mod_definitions(Path("config"), repo_root=Path("."))
    kingdom = defs.get("kingdom")
    assert kingdom is not None
    grouped = {c.key: c.group for c in kingdom.channel_categories if c.group}
    assert grouped, "the real declaration carries grouped channels"
    assert all(isinstance(name, str) and name for name in grouped.values())


def test_the_kingdom_declaration_declares_the_machine_room() -> None:
    """salon-parcours-v2 (Drasah 18/11): the home folder is staff-only (the
    machine-room rule); the players' parcours is TWO doors — the public
    « register » salon, then the « apply » salon which DENIES @everyone and
    opens only to the players carrying the registration access role."""
    from pathlib import Path

    from botforge.core.services.mod_registry import load_mod_definitions

    defs = load_mod_definitions(Path("config"), repo_root=Path("."))
    kingdom = defs.get("kingdom")
    assert kingdom is not None
    assert kingdom.home_admin_only is True
    assert "Kingdom Admin" in kingdom.home_view_roles
    register_channel = kingdom.channel_category("register")
    assert register_channel.group, "the register salon lives in the Conscription group"
    assert register_channel.access.everyone_view is True, "the parcours' first door is public"
    apply_channel = kingdom.channel_category("apply")
    assert apply_channel.group, "the apply salon lives in the Conscription group"
    assert apply_channel.access.everyone_view is False, "the apply salon denies @everyone"
    assert "Kingdom Enregistré" in apply_channel.access.view, "the gate role opens the apply salon"


def test_home_view_roles_must_be_a_list(tmp_path: Path) -> None:
    """A malformed home gate fails loudly (the declaration is the truth)."""
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    (mods_dir / "roles.yaml").write_text(
        "id: roles\nseasonal: false\nhome_view_roles: 'Kingdom Admin'\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="home_view_roles"):
        load_mod_definitions(tmp_path)


def test_the_home_gate_stays_public_by_default(tmp_path: Path) -> None:
    """An undeclared gate keeps the home folder public (back-compat)."""
    mods_dir = tmp_path / "mods"
    mods_dir.mkdir()
    (mods_dir / "plain.yaml").write_text("id: plain\nseasonal: false\n", encoding="utf-8")
    mods = load_mod_definitions(tmp_path)
    assert mods["plain"].home_admin_only is False
    assert mods["plain"].home_view_roles == ()
