"""Exception handling: log, audit shape, user-facing key (#10).

The handler is **core-agnostic**: it never imports a platform. It
resolves what to log and which message the user should see; the
Discord side (ephemeral answer, bot-logs audit) lives in
:mod:`botforge.discord.error_handler` and builds on the resolution
here.
"""

from __future__ import annotations

import logging

from botforge.core.exceptions.base import USER_KEY_BY_CODE, BotforgeError

__all__ = [
    "ExceptionHandler",
    "fallback_user_key",
]

logger = logging.getLogger("botforge.core.exceptions")

FALLBACK_USER_KEY = "errors.unexpected"


def fallback_user_key() -> str:
    """Return the i18n key answering any non-BotForge failure."""
    return FALLBACK_USER_KEY


class ExceptionHandler:
    """Resolve a failure into its log line and its user-facing key."""

    @classmethod
    def log(cls, exc: BaseException) -> None:
        """Log the failure with its taxonomy (BotForge) or raw type."""
        if isinstance(exc, BotforgeError):
            logger.error("BOTFORGE ERROR %s: %s | %s", exc.code, exc.message, exc.context.data)
        else:
            logger.error("UNEXPECTED ERROR %s: %s", type(exc).__name__, exc, exc_info=exc)

    @classmethod
    def user_key(cls, exc: BaseException) -> str:
        """Return the i18n key of the answer to render to the user."""
        if isinstance(exc, BotforgeError):
            return USER_KEY_BY_CODE.get(exc.code, FALLBACK_USER_KEY)
        return FALLBACK_USER_KEY

    @classmethod
    def audit_payload(cls, exc: BaseException) -> dict[str, object]:
        """Return the serializable audit shape riding the bot-logs record."""
        if isinstance(exc, BotforgeError):
            return exc.to_dict()
        return {"error": "UNEXPECTED", "message": str(exc), "details": {"type": type(exc).__name__}}
