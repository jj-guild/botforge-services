"""Per-channel edit pacing — unit tests (#276 W4).

The pacer keeps consecutive post edits on one forum channel apart
(``EDIT_PACING_S``) so a sync pass never eats the channel's PATCH
budget (the 492-second 429 of the test env). Threads of the same
forum share the parent channel's key; different forums pace
independently.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from botforge.core.services import entity_forum
from botforge.core.services.entity_forum import _edit_pacing_key, pace_channel_edit


class _Thread:
    """A thread stand-in with a parent forum channel."""

    def __init__(self, thread_id: int, parent_id: int | None = 123) -> None:
        self.id = thread_id
        self.parent_id = parent_id


def test_pacing_key_is_the_parent_forum() -> None:
    assert _edit_pacing_key(_Thread(42, 123)) == "123"
    # a thread with no parent paces on its own id (never shared, never None)
    assert _edit_pacing_key(_Thread(42, None)) == "42"


async def test_consecutive_edits_of_one_channel_are_paced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entity_forum, "EDIT_PACING_S", 0.05)
    entity_forum._last_edit_at.clear()
    sleeps: list[float] = []

    async def _spy_sleep(wait: float) -> None:
        sleeps.append(wait)

    monkeypatch.setattr(asyncio, "sleep", _spy_sleep)

    await pace_channel_edit("123")
    await pace_channel_edit("123")
    await pace_channel_edit("123")

    # the first edit goes through without sleeping, every following one waits
    assert len(sleeps) == 2
    assert all(w > 0.04 for w in sleeps)


async def test_different_channels_pace_independently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entity_forum, "EDIT_PACING_S", 60.0)
    entity_forum._last_edit_at.clear()
    slept = []

    async def _spy_sleep(wait: float) -> None:
        slept.append(wait)

    monkeypatch.setattr(asyncio, "sleep", _spy_sleep)

    await pace_channel_edit("forum-a")
    await pace_channel_edit("forum-b")

    # two forums never block each other, whatever the budget state
    assert slept == []


async def test_pacer_never_sleeps_past_the_recorded_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(entity_forum, "EDIT_PACING_S", 0.01)
    entity_forum._last_edit_at.clear()
    await pace_channel_edit("123")
    await asyncio.sleep(0.05)
    # long after the window the next edit is immediate
    start = time.monotonic()
    await pace_channel_edit("123")
    assert time.monotonic() - start < 0.005
