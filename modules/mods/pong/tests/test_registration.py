"""pong mod slice tests: consent-gated registration, locale parity, and the
no-commands surface rule (D-PONG-037)."""

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
    """The status payload feeds the home/status surfaces (mod + guild + count)."""
    service = RegistrationService(store)
    await service.register_with_consent("guild-1", "user-1", consent=True)
    status = await service.status("guild-1")
    assert status["mod"] == "pong"
    assert status["guild"] == "guild-1"
    assert status["players"] == 1


def test_impl_satisfies_the_contract() -> None:
    """The grpc implementation implements the contract (R5: the cog's seam)."""
    impl = PongServiceImpl()
    assert isinstance(impl, PongContract)


def test_cog_registers_no_slash_commands() -> None:
    """D-PONG-037 (owner direction 2026-11-24): the pong cog adds NO slash
    command — the mod surface rides the core /home + /admin commands and the
    auto-generated mod menus (botforge-services#377)."""
    from botforge.mods.pong import cogs

    added: list[Any] = []

    class _Tree:
        def add_command(self, command: Any) -> None:
            added.append(command)

    class _Bot:
        tree = _Tree()

    cogs.register(_Bot(), None)  # type: ignore[arg-type]
    assert not added
    # The one declared action (config/mods/pong.views.yaml) is wired instead.
    from botforge.discord.views_routing import wired_actions

    assert "menu:mod:pong:register" in wired_actions()


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
