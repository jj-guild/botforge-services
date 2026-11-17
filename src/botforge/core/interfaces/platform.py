"""Platform abstraction contracts (IPlatform, IMessage, IChannel, IUser, IView, IWorkflow).

Structural typing via ``typing.Protocol`` (ADR-0011): implementations do not
inherit from these classes, they just satisfy the shape, checked by mypy.
``@runtime_checkable`` enables lightweight isinstance checks (member
presence only, not signatures).

Reference: docs/ARCHITECTURE.md (botforge repo) and botforge-services#3.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from botforge.core.models.workflow import WorkflowTransition


@runtime_checkable
class IUser(Protocol):
    """Platform-agnostic user identity."""

    @property
    def id(self) -> str:
        """Platform-specific unique user identifier."""
        ...

    @property
    def display_name(self) -> str:
        """Human-readable user name."""
        ...


@runtime_checkable
class IChannel(Protocol):
    """Platform-agnostic channel."""

    @property
    def id(self) -> str:
        """Platform-specific unique channel identifier."""
        ...

    @property
    def name(self) -> str:
        """Human-readable channel name."""
        ...


@runtime_checkable
class IMessage(Protocol):
    """Platform-agnostic message exchanged between the core and a platform."""

    @property
    def id(self) -> str:
        """Platform-specific unique message identifier."""
        ...

    @property
    def content(self) -> str:
        """Message text content."""
        ...

    @property
    def author(self) -> IUser:
        """Message author."""
        ...

    @property
    def channel(self) -> IChannel:
        """Channel the message was sent in."""
        ...


@runtime_checkable
class IView(Protocol):
    """Opaque handle to an interactive component set (buttons, selects).

    The contract carries a HANDLE, never a platform type (ADR-0011,
    botforge-services#221): an implementation receives it and renders it
    the way its platform knows — the Discord seam passes a
    ``discord.ui.View`` through, a future platform maps the same
    interactions to its own widgets. There is intentionally nothing to
    read on this surface: interactivity is behavior, and behavior is the
    implementation's business, not the contract's.
    """


@runtime_checkable
class IPlatform(Protocol):
    """Platform abstraction: messaging, channel management, roles, DMs.

    First implementation: DiscordPlatform (botforge-services#11).
    """

    async def send_message(self, channel: IChannel, content: str) -> IMessage:
        """Send a text message to a channel."""
        ...

    async def send_dm(self, user: IUser, content: str, view: IView | None = None) -> IMessage:
        """Send a direct message to a user, optionally with a view.

        DMs are interactive when a view rides along (botforge-services#407):
        the view handle is opaque to the contract (#221) and rendered by
        the platform implementation.
        """
        ...

    async def edit_dm(
        self, message: IMessage, content: str, view: IView | None = None
    ) -> IMessage:
        """Edit a previously sent direct message in place."""
        ...

    async def delete_dm(self, message: IMessage) -> None:
        """Delete a previously sent direct message (best-effort).

        A message already gone is not an error: the platform may skip
        silently, exactly like every ephemeral cleanup.
        """
        ...

    async def create_channel(
        self,
        guild_id: str,
        name: str,
        category_id: str | None = None,
        kind: str = "text",
        overwrites: Mapping[str, Mapping[str, bool]] | None = None,
        position: int | None = None,
        options: Mapping[str, Any] | None = None,
    ) -> IChannel:
        """Create a channel in a guild — the dynamic-channel seam (#408).

        ``kind`` is "text" or "voice". ``overwrites`` is DATA (#221), never
        platform objects: a mapping of target key to permission flags.
        Target keys: ``@everyone``, ``@me`` (the bot itself — the
        lesson of locking a bot out of its own channel), or a role NAME
        resolved through the guild's roles. ``position`` is the channel's
        position hint (below a declared channel, for a sidebar that reads).
        ``options`` carries the kind-specific extras (``user_limit`` for a
        voice room) — data, pass-through, never platform types.
        """
        ...

    async def delete_channel(self, channel_id: str) -> None:
        """Delete a channel — best-effort (already gone is not an error)."""
        ...

    async def assign_role(self, user: IUser, role_key: str) -> None:
        """Assign a role (referenced by logical role key) to a user."""
        ...


@runtime_checkable
class IWorkflow(Protocol):
    """Contract for an interaction sequence executed by the WorkflowEngine.

    Workflows are stateless executors: the engine passes the current state
    in the envelope and applies the returned transition to persistence.
    Reference: docs/architecture/core.md §1, ADR-0002.
    """

    @property
    def name(self) -> str:
        """Unique workflow name (registration key for the engine)."""
        ...

    def steps(self) -> list[str]:
        """Ordered step names; the first is the entry step."""
        ...

    async def start(self, context: dict[str, Any]) -> WorkflowTransition:
        """Return the initial transition (first step, PENDING/IN_PROGRESS)."""
        ...

    async def handle_interaction(self, state: WorkflowTransition, event: dict[str, Any]) -> WorkflowTransition:
        """Apply one interaction to the current state; return the next transition."""
        ...

    async def on_timeout(self, state: WorkflowTransition) -> WorkflowTransition:
        """Return the transition to apply when the current step times out."""
        ...
