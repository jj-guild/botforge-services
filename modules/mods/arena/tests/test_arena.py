"""Arena (the permanent example mod): declaration + generic surfaces wiring."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kingdoms.core.services.mod_registry import load_mod_definitions

REPO_ROOT = Path(__file__).resolve().parents[4]


def _definition() -> Any:
    """Load the arena declaration from the modular layout."""
    return load_mod_definitions(REPO_ROOT / "config", repo_root=REPO_ROOT)["arena"]


def test_declaration_validates() -> None:
    """The declaration loads: permanent, game-bound, admin-only group."""
    definition = _definition()
    assert definition.seasonal is False
    assert definition.required_games == ("aoe2",)
    groups = {group.key: group for group in definition.channel_groups}
    assert groups["admin"].admin_only is True
    assert groups["jeux"].admin_only is False
    (annonces,) = [c for c in definition.channel_categories if c.key == "annonces"]
    assert annonces.kind == "announce"
    assert annonces.read_only is True
    (admin,) = [c for c in definition.channel_categories if c.key == "admin"]
    assert admin.admin_only is True


def test_enrollment_settings_parse() -> None:
    """The declared settings land on the definition and parse as criteria."""
    from kingdoms.core.services.enrollment import parse_criteria

    definition = _definition()
    criteria = parse_criteria(definition.settings)
    assert criteria.get("manual") is True
    assert criteria.get("requires_profile") is True


def test_register_wires_the_generic_surfaces() -> None:
    """The one-line register gives the mod the whole parcours."""
    import arena

    class FakeCommand:
        def __init__(self, name: str) -> None:
            self.name = name

    class FakeTree:
        def __init__(self) -> None:
            self.commands: list[Any] = []

        def add_command(self, command: Any) -> None:
            self.commands.append(command)

        def get_commands(self) -> list[Any]:
            return list(self.commands)

    class FakeBot:
        def __init__(self) -> None:
            self.tree = FakeTree()
            self.items: list[type] = []
            self.registry = None

        def add_dynamic_items(self, *classes: type) -> None:
            self.items.extend(classes)

    from kingdoms.discord import mod_surfaces

    bot = FakeBot()
    # the definition rides the registry at runtime; the register hook
    # degrades to no criteria without one
    arena.register(bot, None)
    assert "arena" in mod_surfaces.registered_mod_surfaces()
    assert [command.name for command in bot.tree.get_commands()] == ["arena"]
    from kingdoms.discord.mod_surfaces import ApplyButton, SyncModButton

    assert ApplyButton in bot.items
    assert SyncModButton in bot.items
