"""Affaire 45 (Drasah 26/11) : panthéon-manuel-v1 — le salon à la demande.

Le salon vitrine n'est plus provisionné automatiquement dans
Kingdom-Gaïa : il est déclaré MANUEL (les données restent dans
mod.yaml), c'est l'ATELIER qui le crée (tout en haut, hors
catégorie), et l'organisateur le glisse ensuite où il veut — la
résolution suit l'id stocké, tout le branchement suit le salon.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


def _pantheon() -> Any:
    import botforge.mods.kingdom.cogs.pantheon as pantheon_module

    return pantheon_module


def _settings() -> Any:
    import botforge.mods.kingdom.cogs.settings_panel as settings_module

    return settings_module


def _conf_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "conf"


def _decl(manual: bool = True) -> SimpleNamespace:
    """The registry's declared panthéon salon (data, not hard-coded)."""
    policy = SimpleNamespace(everyone_view=False, view=("Kingdom Lord", "Kingdom Admin"))
    return SimpleNamespace(
        registry=SimpleNamespace(
            get=lambda name: SimpleNamespace(
                channel_categories=(
                    SimpleNamespace(
                        key="pantheon",
                        display_name="🏛️ panthéon",
                        access=policy,
                    ),
                ),
                roles=(
                    SimpleNamespace(display_name="Kingdom Lord", key="lord"),
                    SimpleNamespace(display_name="Kingdom Admin", key="admin"),
                ),
            )
        ),
        mod_roles_service=SimpleNamespace(
            resolve_role_id=AsyncLambda({"lord": "111", "admin": "222"})
        ),
    )


class AsyncLambda:
    """A callable that returns a canned value per key."""

    def __init__(self, answers: dict[str, str]) -> None:
        self.answers = answers

    async def __call__(self, *args: Any, **kwargs: Any) -> Any:
        key = args[2] if len(args) > 2 else kwargs.get("role_key", "")
        return self.answers.get(str(key), "")


class _Role:
    """A hashable fake role (the overwrites dict needs hashable keys)."""

    def __init__(self, rid: int) -> None:
        self.id = rid

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, _Role) and other.id == self.id


class _Channel:
    def __init__(self, cid: str, name: str = "🏛️ panthéon") -> None:
        self.id = int(cid)
        self.name = name
        self.edits: list[dict[str, Any]] = []

    async def edit(self, **kwargs: Any) -> None:
        self.edits.append(kwargs)


class _Guild:
    def __init__(self, channels: dict[str, Any] | None = None) -> None:
        self.id = 555
        self.name = "test-guild"
        self.default_role = _Role(999)
        self.me = _Role(42)
        self.channels = channels or {}
        self.created: list[Any] = []

    def get_channel(self, cid: int) -> Any:
        return self.channels.get(str(cid))

    def get_role(self, rid: int) -> Any:
        return _Role(rid) if rid in (111, 222) else None

    async def create_text_channel(self, name: str, **kwargs: Any) -> Any:
        channel = _Channel("777", name)
        self.created.append((name, kwargs))
        self.channels["777"] = channel
        return channel


def _fake_pin_store(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Fake the static-pin ensure seam; record the (bot, guild_id) calls."""
    ensured: list[tuple[str, str]] = []

    class _Pins:
        def registered_static_pins(self) -> list[Any]:
            return [SimpleNamespace(key="panel:mod:kingdom:pantheon")]

        async def ensure_static_pin(self, bot: Any, spec: Any, guild_id: str) -> bool:
            ensured.append((str(spec.key), guild_id))
            return True

    pins = _Pins()
    import sys
    import types

    fake = types.ModuleType("botforge.discord.static_pins")
    fake.registered_static_pins = lambda: pins.registered_static_pins()
    fake.ensure_static_pin = pins.ensure_static_pin
    monkeypatch.setitem(sys.modules, "botforge.discord.static_pins", fake)
    return ensured


def _fake_resolution(monkeypatch: pytest.MonkeyPatch, stored: str = "") -> dict[str, str]:
    """Fake stored_channel_id + persist_resolutions (the resolution seam)."""
    state = {"stored": stored, "persisted": {}}

    async def fake_stored(guild_id: str, scope: str, key: str) -> str | None:
        return state["stored"] or None

    async def fake_persist(guild_id: str, scope: str, resolved: dict[str, str]) -> None:
        state["persisted"].update(resolved)

    import sys
    import types

    fake = types.ModuleType("botforge.discord.ui.panels_provisioning")
    fake.stored_channel_id = fake_stored
    fake.persist_resolutions = fake_persist
    fake.provision_scope = None
    fake.provision_all = None
    monkeypatch.setitem(sys.modules, "botforge.discord.ui.panels_provisioning", fake)
    return state


# ---------------------------------------------------------------------------
# The declaration is DATA — the salon is manual, never provisioned
# ---------------------------------------------------------------------------


def test_mod_yaml_declares_the_pantheon_manual_and_ungrouped() -> None:
    content = (_conf_dir() / "mod.yaml").read_text(encoding="utf-8")
    block = content.split("- key: pantheon", 1)[1].split("- key:", 1)[0]
    assert "manual: true" in block, "the salon never rides the provisioning"
    assert "group:" not in block, "no group: it is born OUTSIDE any category"
    assert "view: [Kingdom Lord, Kingdom King, Kingdom Admin]" in block, (
        "the access policy stays declared data"
    )


def test_the_core_decl_parses_the_manual_flag() -> None:
    from botforge.core.services.mod_registry import _parse_channel_categories

    parsed = _parse_channel_categories(
        [
            {"key": "pantheon", "display_name": "🏛️ panthéon", "manual": True},
            {"key": "attack", "display_name": "⚔️ attaque"},
        ],
        [],
        "test.yaml",
    )
    by_key = {c.key: c for c in parsed}
    assert by_key["pantheon"].manual is True
    assert by_key["attack"].manual is False, "the default stays automatic"


def test_the_provisioning_skips_manual_salons() -> None:
    from botforge.discord.mods_forum import _seasonal_standard_channels

    definition = SimpleNamespace(
        channel_categories=(
            SimpleNamespace(key="pantheon", manual=True),
            SimpleNamespace(key="attack", manual=False),
            SimpleNamespace(key="general", manual=False),
        )
    )
    kept = {c.key for c in _seasonal_standard_channels(definition)}
    assert "pantheon" not in kept, "a manual salon is NEVER auto-provisioned"
    assert "attack" in kept
    assert "general" in kept, "the SDK's standard back-end channels stay injected"


# ---------------------------------------------------------------------------
# The atelier creates the salon — top of the sidebar, no category
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_atelier_creates_the_salon_top_and_uncategorized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    state = _fake_resolution(monkeypatch)
    _fake_pin_store(monkeypatch)
    bot, guild = _decl(), _Guild()
    channel_id, status = await pantheon.add_pantheon_salon(bot, guild)
    assert status == "created"
    assert channel_id == "777"
    name, kwargs = guild.created[0]
    assert name == "🏛️ panthéon", "the name comes from the DECLARATION"
    overwrites = kwargs["overwrites"]
    assert overwrites[guild.default_role].view_channel is False, "@everyone is gated"
    granted = any(getattr(target, "id", None) in (111, 222) for target in overwrites)
    assert granted, "the declared view roles carry the grant"
    channel = guild.channels["777"]
    assert channel.edits and channel.edits[0].get("position") == 0, (
        "the salon is born at the very TOP of the sidebar"
    )
    assert state["persisted"] == {"pantheon": "777"}, (
        "the resolution is stored — everything wired follows a hand-made move"
    )


@pytest.mark.asyncio
async def test_a_second_click_answers_exists_and_never_duplicates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pantheon = _pantheon()
    _fake_resolution(monkeypatch, stored="777")
    ensured = _fake_pin_store(monkeypatch)
    bot, guild = _decl(), _Guild(channels={"777": _Channel("777")})
    channel_id, status = await pantheon.add_pantheon_salon(bot, guild)
    assert (channel_id, status) == ("777", "exists")
    assert not guild.created, "an existing salon is never duplicated"
    assert ensured, "the pin is ensured on both paths"


# ---------------------------------------------------------------------------
# The atelier wiring — action, handler, labels
# ---------------------------------------------------------------------------


def test_the_atelier_owns_the_add_pantheon_action() -> None:
    settings = _settings()
    actions = tuple(action for action, _key, _style in settings._SETTINGS_ACTIONS)
    assert "add-pantheon" in actions
    assert "add-pantheon" in settings._SETTINGS_HANDLERS, (
        "the action answers a handler (a dead button is a drift)"
    )
    from botforge.mods.kingdom.cogs.settings_panel import SettingsActionButton

    button = SettingsActionButton(
        "add-pantheon", "🏛️ Ajouter Panthéon"
    )
    assert button.custom_id == "kingdom:settings:add-pantheon"
    assert re.fullmatch(r"kingdom:settings:(?P<action>[a-z0-9-]+)", button.custom_id)


def test_the_atelier_drawer_carries_the_button() -> None:
    source = Path(_settings().__file__).read_text(encoding="utf-8")
    assert '"add-pantheon"' in source.split("def _atelier_drawer", 1)[1].split(
        "def ", 1
    )[0], "the button lives in the ATELIER drawer (Drasah's pick)"


@pytest.mark.parametrize("locale_file", ["fr.yaml", "en.yaml"])
def test_the_labels_live_in_the_locales(locale_file: str) -> None:
    content = (_conf_dir() / "locales" / locale_file).read_text(encoding="utf-8")
    for key in (
        "settings_add_pantheon_button",
        "settings_add-pantheon_button",
        "settings_add_pantheon_done",
        "settings_add_pantheon_exists",
        "settings_add_pantheon_no_guild",
        "settings_add_pantheon_failed",
    ):
        assert key in content, f"{locale_file} misses {key}"
