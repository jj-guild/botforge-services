"""The ephemeral window seam: one navigation mode per surface owner.

#381 ruling 3 (Merlin 17/11): a mod defines ITS mode for ITS ephemeral
views; the platform's today mode (fire-and-forget) stays the default.
"""

from __future__ import annotations

import pytest

from botforge.discord.ui import ephemeral_windows
from botforge.discord.ui.ephemeral_windows import (
    PLATFORM_SCOPE,
    EphemeralWindowMode,
    close_ephemeral_window,
    open_ephemeral_window,
    set_window_mode,
    window_mode,
)


class _Response:
    """A recorder for one fake interaction's response side."""

    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []
        self._done = False

    async def send_message(self, content, **kwargs):  # type: ignore[no-untyped-def]
        self.sent.append({"content": content, **kwargs})
        self._done = True

    def is_done(self) -> bool:
        return self._done


class _Interaction:
    """The minimal interaction surface the seam touches (duck-typed)."""

    def __init__(self, user_id: str) -> None:
        self.user = type("U", (), {"id": user_id})()
        self.response = _Response()
        self.deleted: list[str] = []

    async def delete_original_response(self) -> None:
        self.deleted.append("original")


@pytest.fixture(autouse=True)
def _fresh_window_registry() -> None:
    """Isolate the seam's process-wide registries between tests."""
    ephemeral_windows._modes = {PLATFORM_SCOPE: EphemeralWindowMode.PLAIN}
    ephemeral_windows._live = {}


def test_the_platform_default_is_plain() -> None:
    """The platform and every unregistered scope read PLAIN (today's mode)."""
    assert window_mode(PLATFORM_SCOPE) is EphemeralWindowMode.PLAIN
    assert window_mode("mod/unregistered") is EphemeralWindowMode.PLAIN


def test_a_scope_declares_its_own_mode() -> None:
    """A mod registers its mode — idempotent, and scoped to it alone."""
    set_window_mode("mod/kingdom", EphemeralWindowMode.SINGLE)
    assert window_mode("mod/kingdom") is EphemeralWindowMode.SINGLE
    assert window_mode(PLATFORM_SCOPE) is EphemeralWindowMode.PLAIN
    set_window_mode("mod/kingdom", EphemeralWindowMode.SINGLE)
    assert window_mode("mod/kingdom") is EphemeralWindowMode.SINGLE


@pytest.mark.asyncio
async def test_single_closes_the_previous_window() -> None:
    """SINGLE: a new window deletes the player's previous one."""
    set_window_mode("mod/kingdom", EphemeralWindowMode.SINGLE)
    first = _Interaction("42")
    second = _Interaction("42")

    await open_ephemeral_window(first, "mod/kingdom", "one")
    await open_ephemeral_window(second, "mod/kingdom", "two")

    assert len(first.deleted) == 1, "the previous window closed"
    assert not second.deleted, "the LIVE window is never closed"
    assert second.response.sent[0]["content"] == "two"
    assert second.response.sent[0]["ephemeral"] is True


@pytest.mark.asyncio
async def test_plain_sends_without_tracking() -> None:
    """PLAIN: no window is tracked, nothing is ever deleted."""
    first = _Interaction("42")
    second = _Interaction("42")

    await open_ephemeral_window(first, PLATFORM_SCOPE, "one")
    await open_ephemeral_window(second, PLATFORM_SCOPE, "two")

    assert not first.deleted and not second.deleted
    assert ephemeral_windows._live == {}, "PLAIN tracks nothing"


@pytest.mark.asyncio
async def test_scopes_never_close_each_other() -> None:
    """A mod's window never closes the platform's (one registry, scoped keys)."""
    set_window_mode("mod/kingdom", EphemeralWindowMode.SINGLE)
    platform_window = _Interaction("42")
    mod_window = _Interaction("42")

    await open_ephemeral_window(platform_window, PLATFORM_SCOPE, "platform")
    await open_ephemeral_window(mod_window, "mod/kingdom", "mod")

    assert not platform_window.deleted, "the platform's window lives on"
    await close_ephemeral_window("mod/kingdom", "42")
    assert mod_window.deleted, "the mod's window closed on demand"
