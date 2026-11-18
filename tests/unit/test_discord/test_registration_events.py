"""The registration event sink (salon-gating subscriptions, salon-parcours-v2).

The core emits transport-free intents; this Discord sink fans them out
to the bot's subscribers — a failing subscriber never breaks the bind.
"""

from __future__ import annotations

from typing import Any

import pytest

from botforge.discord.registration_events import (
    RegistrationEventSink,
    subscribe_registration_events,
)


class _Bot:
    """A bot shell carrying the subscriber list (like the factory wires)."""

    def __init__(self) -> None:
        self.registration_event_subscribers: list[Any] = []


@pytest.mark.asyncio
async def test_the_sink_fans_out_to_every_subscriber() -> None:
    bot = _Bot()
    seen: list[tuple[str, dict[str, Any]]] = []

    async def _handler(intent: str, payload: dict[str, Any]) -> None:
        seen.append((intent, payload))

    subscribe_registration_events(bot, _handler)
    subscribe_registration_events(bot, _handler)  # idempotent

    sink = RegistrationEventSink(bot)
    await sink.emit("profile.bound", {"user_id": "42", "guild_id": "123"})
    assert seen == [("profile.bound", {"user_id": "42", "guild_id": "123"})]
    assert len(bot.registration_event_subscribers) == 1


@pytest.mark.asyncio
async def test_a_failing_subscriber_never_breaks_the_emit() -> None:
    bot = _Bot()
    after: list[str] = []

    async def _boom(intent: str, payload: dict[str, Any]) -> None:
        raise RuntimeError("the gate exploded")

    async def _ok(intent: str, payload: dict[str, Any]) -> None:
        after.append(intent)

    subscribe_registration_events(bot, _boom)
    subscribe_registration_events(bot, _ok)

    sink = RegistrationEventSink(bot)
    await sink.emit("profile.unbound", {"user_id": "42"})
    assert after == ["profile.unbound"], "the bind keeps going, whatever a subscriber does"
