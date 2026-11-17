"""Kingdoms mod validation dashboard (#339, the detailed candidates view).

The pinned `realms` surface: one row per PENDING kingdom with its King
and the ✅/❌ decision buttons, the accepted/refused tables, Gaïa
excluded, restart-proof custom ids, the click-time guard, and the
decision applying through the service seams.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace as NS
from typing import Any


def _kv_module() -> Any:
    """The validation module — imported lazily, cog convention for mod tests."""
    from botforge.mods.kingdom.cogs.kingdom import validation

    return validation


def _fake_stack(pending: list[Any], approved: list[Any], refused: list[Any], lords: list[Any]) -> Any:
    async def _kingdoms() -> list[Any]:
        return [*pending, *approved, *refused]

    async def _lords() -> list[Any]:
        return lords

    return NS(kingdoms=NS(kingdoms=_kingdoms, lords=_lords))


def _flatten(items: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        out.append(item)
        out.extend(_flatten(item.get("components", []) or []))
    return out


def _texts(view: Any) -> list[str]:
    return [str(i.get("content", "")) for i in _flatten(view.to_components()) if i.get("type") == 10]


def _buttons(view: Any) -> list[dict[str, Any]]:
    return [i for i in _flatten(view.to_components()) if i.get("type") == 2]


def test_validation_module_import() -> None:
    """The validation surface exposes the panel and the decision button."""
    from botforge.mods.kingdom.cogs.kingdom.validation import (  # noqa: F401
        ValidationDecisionButton,
        build_validation_panel,
    )


def test_validation_custom_ids_are_stable() -> None:
    """The decision buttons are restart-proof DynamicItems (stable ids)."""
    from botforge.mods.kingdom.cogs.kingdom.validation import ValidationDecisionButton

    assert (
        ValidationDecisionButton("k3", "ok", "x", _kv_module().discord.ButtonStyle.success).custom_id
        == "kingdom:valid:k3:ok"
    )
    assert (
        ValidationDecisionButton("k3", "no", "x", _kv_module().discord.ButtonStyle.danger).custom_id
        == "kingdom:valid:k3:no"
    )


def test_validation_strings_parity() -> None:
    """The dashboard's keys exist in both locales and format with their arities."""
    from botforge.mods.kingdom.cogs.kingdom.strings import strings

    for locale in ("fr", "en"):
        s = strings(locale)
        for key in (
            "validation_title",
            "validation_help",
            "validation_pending_header",
            "validation_row",
            "validation_empty",
            "validation_accept_button",
            "validation_refuse_button",
            "validation_accepted_header",
            "validation_refused_header",
            "validation_table_kingdom",
            "validation_denied",
            "validation_approved_note",
            "validation_refused_note",
        ):
            assert s[key]
        s["validation_row"].format(name="X", king="Y")
        s["validation_approved_note"].format(name="X")
        s["validation_refused_note"].format(name="X")


def test_the_dashboard_builds_without_a_stack() -> None:
    """A boot with no wired service still pins the empty dashboard."""
    from botforge.mods.kingdom.cogs.kingdom import validation as kv

    original = kv.wiring
    kv.wiring = lambda: None
    try:
        view = asyncio.run(kv.build_validation_panel("42"))
        texts = _texts(view)
        assert any("validation" in t.lower() for t in texts), texts
        assert any(t for t in texts if "—" in t), texts
    finally:
        kv.wiring = original


def test_pending_kingdoms_carry_their_decision_buttons() -> None:
    """One row + one ✅/❌ pair per pending kingdom; Gaïa never rides."""
    from botforge.mods.kingdom import models
    from botforge.mods.kingdom.cogs.kingdom import validation as kv

    KV = models.KingdomValidation
    pending = NS(id="kb", is_gaia=False, name="Bourgogne", validation=KV.PENDING)
    approved = NS(id="ka", is_gaia=False, name="Anjou", validation=KV.APPROVED)
    refused = NS(id="kr", is_gaia=False, name="Breton", validation=KV.REFUSED)
    gaia = NS(id="gaia", is_gaia=True, name="Gaia", validation=KV.APPROVED)
    original = kv.wiring
    kv.wiring = _fake_stack([pending], [approved], [refused, gaia], [])
    try:
        view = asyncio.run(kv.build_validation_panel("42"))
        texts = _texts(view)
        assert any("Bourgogne" in t for t in texts), texts
        assert any("Anjou" in t for t in texts), texts
        assert any("Breton" in t for t in texts), texts
        assert not any("Gaia" in t for t in texts), texts
        ids = [b.get("custom_id") for b in _buttons(view)]
        assert "kingdom:valid:kb:ok" in ids and "kingdom:valid:kb:no" in ids, ids
        assert not any("gaia" in str(i) for i in ids), ids
    finally:
        kv.wiring = original


def test_the_decision_applies_through_the_service_and_rerenders() -> None:
    """✅ calls approve_kingdom, ❌ calls refuse_kingdom; the pin re-renders."""
    from botforge.mods.kingdom import models
    from botforge.mods.kingdom.cogs.kingdom import validation as kv

    KV = models.KingdomValidation
    pending = NS(id="kb", is_gaia=False, name="Bourgogne", validation=KV.PENDING)
    calls: list[tuple[str, str]] = []

    async def _approve(kid: str) -> Any:
        calls.append(("ok", kid))
        pending.validation = KV.APPROVED
        return pending

    async def _refuse(kid: str) -> Any:
        calls.append(("no", kid))
        pending.validation = KV.REFUSED
        return pending

    async def _kingdoms() -> list[Any]:
        return [pending]

    async def _lords() -> list[Any]:
        return []

    stack = NS(kingdoms=NS(kingdoms=_kingdoms, lords=_lords, approve_kingdom=_approve, refuse_kingdom=_refuse))
    original = kv.wiring
    kv.wiring = lambda: stack
    try:
        response = NS(
            edited=None,
            done=False,
            is_done=lambda: False,
            sent=None,
        )

        async def _edit(view: Any = None) -> None:
            response.edited = view  # type: ignore[assignment]
            response.done = True  # type: ignore[assignment]

        async def _send(msg: str, ephemeral: bool = False) -> None:
            response.sent = msg  # type: ignore[assignment]

        response.edit_message = _edit  # type: ignore[method-assign]
        response.send_message = _send  # type: ignore[method-assign]
        followup = NS(sent=[])

        async def _fsend(msg: str, ephemeral: bool = False) -> None:
            followup.sent.append(msg)

        followup.send = _fsend  # type: ignore[method-assign]
        inter: Any = NS(
            guild_id="42",
            user=NS(id="77"),
            client=NS(status_service=NS(bot_admins=("77",)), roles_service=None),
            response=response,
            followup=followup,
        )
        button = kv.ValidationDecisionButton("kb", "ok", "✅", _kv_module().discord.ButtonStyle.success)
        asyncio.run(button.callback(inter))
        assert calls == [("ok", "kb")], calls
        assert response.edited is not None, "the pin must re-render in place"
        assert followup.sent, "the operator gets his confirmation"
    finally:
        kv.wiring = original


def test_the_guard_blocks_a_non_admin() -> None:
    """A non-admin click never reaches the service (click-time guard)."""
    from botforge.mods.kingdom.cogs.kingdom import validation as kv

    calls: list[str] = []

    async def _approve(kid: str) -> Any:
        calls.append(kid)
        raise AssertionError("the service must not be called")

    async def _kingdoms() -> list[Any]:
        return []

    async def _lords() -> list[Any]:
        return []

    stack = NS(kingdoms=NS(kingdoms=_kingdoms, lords=_lords, approve_kingdom=_approve))
    original = kv.wiring
    kv.wiring = lambda: stack
    try:
        response = NS(is_done=lambda: False, sent=None)

        async def _send(msg: str, ephemeral: bool = False) -> None:
            response.sent = msg  # type: ignore[assignment]

        response.send_message = _send  # type: ignore[method-assign]
        followup = NS(sent=[])

        async def _fsend(msg: str, ephemeral: bool = False) -> None:
            followup.sent.append(msg)

        followup.send = _fsend  # type: ignore[method-assign]
        inter: Any = NS(
            guild_id="42",
            user=NS(id="66"),
            client=NS(status_service=NS(bot_admins=("77",)), roles_service=None),
            response=response,
            followup=followup,
        )
        button = kv.ValidationDecisionButton("kb", "ok", "✅", _kv_module().discord.ButtonStyle.success)
        asyncio.run(button.callback(inter))
        assert calls == [], "a denied click must not reach the service"
    finally:
        kv.wiring = original
