"""Pong mod domain models: player registration and the consent trace.

Identity (steam_id <-> discord_id, AoE2 profile data) lives in the
core's /home > Profil surface; the mod never copies game profile data
into its own state (RG-REG-1). The models carry only what the
tournament needs: entity keys and the consent decision (SC-PONG-001).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PlayerState(StrEnum):
    """A player's tournament lifecycle state (slice: registration only)."""

    REGISTERED = "registered"  # consent accepted, candidate pending enrollment (RG-REG-1)
    # Later states (waitlist/player/replacing/departed) land with the engine (step 3, #439).


class ConsentDecision(StrEnum):
    """The privacy-gate outcome recorded with every registration (RG-REG-1)."""

    ACCEPTED = "accepted"
    REFUSED = "refused"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class PlayerModel(BaseModel):
    """A registered pong player (the mod's own collection entity)."""

    model_config = ConfigDict(populate_by_name=True)

    discord_id: str = Field(alias="_id")
    guild_id: str
    state: PlayerState
    consent: ConsentDecision
    registered_at: str = Field(default_factory=_utc_now_iso)

    def to_mongo(self) -> dict[str, Any]:
        """Serialize to the storage document (R8: the seam speaks plain dicts)."""
        return self.model_dump(by_alias=True)

    @classmethod
    def from_mongo(cls, data: dict[str, Any]) -> PlayerModel:
        """Rebuild from a storage document."""
        return cls.model_validate(data)
