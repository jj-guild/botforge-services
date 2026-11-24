"""The pong mod's exception taxonomy: typed, i18n-ready errors.

`code` is the machine-stable identifier for logs/audits; `user_key`
selects the ephemeral i18n message the cog renders to the player;
`context` carries serializable data only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorContext:
    """Serializable extra data attached to a PongError (never raised raw)."""

    data: dict[str, Any] = field(default_factory=dict)


class PongError(Exception):
    """Base of the mod's typed errors; subclasses fix `code` and `user_key`."""

    code: str = "PONG_ERROR"
    user_key: str = "pong.errors.unexpected"

    def __init__(self, message: str, context: ErrorContext | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext()

    def to_dict(self) -> dict[str, Any]:
        """A log/audit-friendly representation."""
        return {"code": self.code, "message": self.message, "context": self.context.data}


class RegistrationError(PongError):
    """Registration failed on the mod's side (storage or validation)."""

    code = "REGISTRATION_ERROR"
    user_key = "pong.errors.registration"
