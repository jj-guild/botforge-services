"""pong mod slice tests: consent-gated registration + fr/en locale parity."""

from __future__ import annotations

from typing import Any

import pytest

from botforge.mods.pong.grpc.contract import PongContract
from botforge.mods.pong.grpc.service import PongServiceImpl
from botforge.mods.pong.service import RegistrationService


class RecordingStore:
    """A PongStore that records upserts (in-memory)."""

    def __init__(self) -> None:
        self.players: dict[str, dict[str, Any]] = {}

    async def upsert_player(self, document: dict[str, Any]) -> None:
        self.players[str(document["_id"])] = dict(document)

    async def get_player(self, discord_id: str) -> dict[str, Any] | None:
        document = self.players.get(discord_id)
        return dict(document) if document is not None else None

    async def player_count(self) -> int:
        return len(self.players)


@pytest.fixture
def store() -> RecordingStore:
    return RecordingStore()


async def test_consent_accepted_registers_the_player(store: RecordingStore) -> None:
    """SC-PONG-001: consent accepted -> the player is stored REGISTERED."""
    service = RegistrationService(store)
    result = await service.register_with_consent("guild-1", "user-1", consent=True)
    assert result["registered"] is True
    assert result["already_registered"] is False
    assert result["player"]["state"] == "registered"
    assert result["player"]["consent"] == "accepted"
    assert store.players["user-1"]["guild_id"] == "guild-1"


async def test_consent_refused_stores_nothing(store: RecordingStore) -> None:
    """SC-PONG-002: consent refused -> nothing is persisted."""
    service = RegistrationService(store)
    result = await service.register_with_consent("guild-1", "user-1", consent=False)
    assert result == {"registered": False, "consent": "refused"}
    assert store.players == {}


async def test_registration_is_idempotent(store: RecordingStore) -> None:
    """Re-registering an existing player keeps the earliest registration."""
    service = RegistrationService(store)
    first = await service.register_with_consent("guild-1", "user-1", consent=True)
    second = await service.register_with_consent("guild-1", "user-1", consent=True)
    assert second["already_registered"] is True
    assert second["player"] == first["player"]
    assert await store.player_count() == 1


async def test_status_reports_the_guild_and_player_count(store: RecordingStore) -> None:
    service = RegistrationService(store)
    await service.register_with_consent("guild-1", "user-1", consent=True)
    status = await service.status("guild-1")
    assert status["mod"] == "pong"
    assert status["guild"] == "guild-1"
    assert status["players"] == 1


def test_impl_satisfies_the_contract() -> None:
    impl = PongServiceImpl()
    assert isinstance(impl, PongContract)


class _NullBot:
    """A bot stand-in carrying only the home builders dict."""

    mod_home_builders: dict[str, Any] = {}


def test_cog_wires_views_and_actions_no_commands() -> None:
    """The mod adds NO slash commands: its surface rides declared views/actions."""
    from botforge.discord.views_routing import wired_actions, wired_views

    import botforge.mods.pong.cogs as cogs

    assert callable(getattr(cogs, "register", None))
    bot = _NullBot()
    cogs.register(bot)
    assert "menu:mod:pong:register" in wired_actions()
    assert "mod:pong" in wired_views()
    assert callable(bot.mod_home_builders.get("pong"))


def _flatten(mapping: dict[str, Any], prefix: str = "") -> set[tuple[str, str]]:
    """Flatten a locale YAML to ( dotted key, placeholder signature ) pairs."""
    keys: set[tuple[str, str]] = set()
    for key, value in mapping.items():
        dotted = f"{prefix}{key}"
        if isinstance(value, dict):
            keys |= _flatten(value, f"{dotted}.")
        else:
            placeholders = tuple(sorted({part for part in str(value).split("{")[1:] if "}" in part}))
            keys.add((dotted, ",".join(placeholders)))
    return keys


def test_locales_fr_en_parity() -> None:
    """The fr and en catalogs expose the same keys and placeholders."""
    import yaml

    from botforge.core.services.mod_layout import default_repo_root

    conf = default_repo_root() / "modules" / "mods" / "pong" / "conf" / "locales"
    en = yaml.safe_load((conf / "en.yaml").read_text(encoding="utf-8"))
    fr = yaml.safe_load((conf / "fr.yaml").read_text(encoding="utf-8"))
    assert _flatten(en) == _flatten(fr)
