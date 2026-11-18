"""The Discord-side registration event sink (salon-gating subscriptions).

The core's ``RegistrationEvents`` seam stays transport-free — this
module is the Discord dispatcher: an intent emitted by the
RegistrationService fans out to every subscriber registered on the bot
(``bot.registration_event_subscribers``). Mods subscribe to grant
access (a role the gated salons read); the platform wires the sink in
the factory, never the other way around.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("botforge.registration_events")


def subscribe_registration_events(bot: Any, handler: Any) -> None:
    """Register one async ``(intent, payload)`` subscriber (idempotent)."""
    subscribers = getattr(bot, "registration_event_subscribers", None)
    if subscribers is None:
        subscribers = []
        bot.registration_event_subscribers = subscribers
    if handler not in subscribers:
        subscribers.append(handler)


class RegistrationEventSink:
    """Fan the core's registration intents out to the bot's subscribers.

    The sink is best-effort by contract (the core wraps the emit): a
    failing subscriber logs and NEVER breaks the bind itself.
    """

    def __init__(self, bot: Any = None) -> None:
        """Store the bot the subscribers live on."""
        self._bot = bot

    async def emit(self, intent: str, payload: dict[str, Any]) -> None:
        """Forward one intent to every subscriber (best-effort)."""
        subscribers = getattr(self._bot, "registration_event_subscribers", None) or ()
        for handler in subscribers:
            try:
                await handler(intent, payload)
            except Exception:
                logger.warning(
                    "REGISTRATION EVENT SUBSCRIBER FAILED (%s)",
                    intent,
                    exc_info=True,
                )
