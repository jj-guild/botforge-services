"""The pong mod's domain core (the mod's own collections, its own rules).

Slice 1 scope: the player registration model behind a consent gate
(RG-REG-1), the storage seam (a Protocol, storage-agnostic), and the
registration service. No Discord imports here (R6): the cog is the
mod's only Discord layer. Collections are storage-injected (R8); the
persistent ModStorage wiring lands with the season engine (step 3).
"""

from botforge.mods.pong.errors import ErrorContext, PongError, RegistrationError
from botforge.mods.pong.models import ConsentDecision, PlayerModel, PlayerState
from botforge.mods.pong.service import RegistrationService
from botforge.mods.pong.storage import PongStore

__all__ = [
    "ConsentDecision",
    "ErrorContext",
    "PlayerModel",
    "PlayerState",
    "PongError",
    "PongStore",
    "RegistrationError",
    "RegistrationService",
]
