"""kingdom-test-v1 push 2 (Drasah 01/11) — the admin-as-king fallback.

An admin with no record of their own resolves as the fictional Nilrem
king (``nilrem-roi``) through ``_king_of``/``_lord_of``: the admin
pilots the test kingdom like a king. A real record always wins, and a
non-admin never falls back.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from kingdoms.mods.kingdoms.kingdom_persistent import _king_of, _lord_of
from kingdoms.mods.kingdoms.service import (
    TEST_KINGDOM_ID,
    TEST_KING_ID,
    KING_ROLE,
    LORD_ROLE,
)

pytestmark = pytest.mark.asyncio


def _lord(lord_id: str, role: Any = LORD_ROLE, *, left: bool = False, kingdom_id: str | None = None) -> Any:
    return SimpleNamespace(
        id=lord_id, role=role, left=left, kingdom_id=kingdom_id or TEST_KINGDOM_ID,
        display_name="X", in_queue=False,
    )


def _service(*lords: Any) -> Any:
    return SimpleNamespace(lords=lambda: _list(lords))


async def _list(items: list[Any]) -> list[Any]:
    return list(items)


async def test_an_admin_without_a_record_is_the_nilrem_king() -> None:
    merlin = _lord(TEST_KING_ID, KING_ROLE)
    service = _service(merlin)

    king = await _king_of(service, "999", ("999",))
    lord = await _lord_of(service, "999", ("999",))

    assert king is not None and str(king.id) == TEST_KING_ID
    assert lord is not None and str(lord.id) == TEST_KING_ID


async def test_a_real_record_always_wins_over_the_fallback() -> None:
    real = _lord("999", KING_ROLE, kingdom_id="k-2")
    service = _service(real, _lord(TEST_KING_ID, KING_ROLE))

    king = await _king_of(service, "999", ("999",))

    assert king is not None and str(king.id) == "999" and str(king.kingdom_id) == "k-2"


async def test_non_admins_never_fall_back() -> None:
    service = _service(_lord(TEST_KING_ID, KING_ROLE))

    assert await _king_of(service, "777", ("999",)) is None
    assert await _lord_of(service, "777", ("999",)) is None
    # no admin wire at all: legacy callers keep the old behaviour
    assert await _king_of(service, "777") is None


async def test_the_fallback_never_adopts_a_departed_or_unseated_king() -> None:
    departed = _lord(TEST_KING_ID, KING_ROLE, left=True)
    assert await _king_of(_service(departed), "999", ("999",)) is None

    unseated = _lord(TEST_KING_ID, KING_ROLE, kingdom_id=None)
    assert await _king_of(_service(unseated), "999", ("999",)) is None

    # _king_of is king-only: a non-king Nilrem doc is not a throne
    not_king = _lord(TEST_KING_ID, LORD_ROLE)
    assert await _king_of(_service(not_king), "999", ("999",)) is None
    # _lord_of adopts any active Nilrem doc
    assert await _lord_of(_service(not_king), "999", ("999",)) is not None


async def test_without_the_test_kingdom_an_admin_stays_an_admin() -> None:
    service = _service(_lord("123", LORD_ROLE))

    assert await _king_of(service, "999", ("999",)) is None
    assert await _lord_of(service, "999", ("999",)) is None
