"""The composed interactive view base (#407): items in, SDK base out.

The gameplay pattern — a DM or message whose buttons/selects are built
elsewhere — must never construct a raw ``discord.ui.View`` (rule #367
arbitrage 2): ``ComposedView`` owns the base (permission checks,
delivery policies, the mod anchor), the caller only brings its items.
"""

from __future__ import annotations

import asyncio

import discord

from botforge.discord.ui.views import ComposedView


def _button(label: str) -> discord.ui.Button[discord.ui.View]:
    return discord.ui.Button(label=label, custom_id=f"test:{label}")


def test_items_passed_at_construction_are_attached() -> None:
    view = ComposedView(_button("a"), _button("b"), mod="kingdom", timeout=None)
    assert [i.label for i in view.children] == ["a", "b"]  # type: ignore[union-attr]


def test_items_added_later_ride_the_same_base() -> None:
    view = ComposedView(mod="kingdom", timeout=300.0)
    view.add_item(_button("later"))
    assert [i.label for i in view.children] == ["later"]  # type: ignore[union-attr]


def test_mod_anchor_and_timeout_carry() -> None:
    view = ComposedView(mod="kingdom", timeout=None)
    assert view.mod == "kingdom"
    assert view.timeout is None


def test_interaction_check_fails_open_without_a_permission_service() -> None:
    view = ComposedView(_button("go"), mod="kingdom", timeout=None)

    class _Interaction:
        data: dict[str, object] = {"custom_id": "test:go"}  # noqa: RUF012 — a test double

    assert asyncio.run(view.interaction_check(_Interaction())) is True  # type: ignore[arg-type]
