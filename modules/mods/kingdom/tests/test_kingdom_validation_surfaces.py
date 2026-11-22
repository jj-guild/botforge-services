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
    from botforge.mods.kingdom.cogs import validation

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
    from botforge.mods.kingdom.cogs.validation import (  # noqa: F401
        ValidationDecisionButton,
        build_validation_panel,
    )


def test_validation_custom_ids_are_stable() -> None:
    """The decision buttons are restart-proof DynamicItems (stable ids)."""
    from botforge.mods.kingdom.cogs.validation import ValidationDecisionButton

    assert (
        ValidationDecisionButton("k3", "ok", "x", _kv_module().discord.ButtonStyle.success).custom_id
        == "kingdom:valid:k3:ok"
    )
    assert (
        ValidationDecisionButton("k3", "no", "x", _kv_module().discord.ButtonStyle.danger).custom_id
        == "kingdom:valid:k3:no"
    )


def test_validation_strings_parity() -> None:
    """The dashboard's yaml keys exist in both locales and format with their arities."""
    from botforge.mods.kingdom.cogs.common import mod_catalog

    for locale in ("fr", "en"):
        s = mod_catalog().section("kingdom.validation", locale)
        for key in (
            "title",
            "help",
            "pending_header",
            "row",
            "empty",
            "accept_button",
            "refuse_button",
            "accepted_header",
            "refused_header",
            "table_kingdom",
            "denied",
            "approved_note",
            "refused_note",
        ):
            assert s[key], (locale, key)
        s["row"].format(name="X", king="Y")
        s["approved_note"].format(name="X")
        s["refused_note"].format(name="X")


def test_validation_strings_live_in_the_mod_yaml_not_the_python_dict() -> None:
    """Merlin's rule: the mod's translations are yaml data, never hardcoded."""
    from botforge.mods.kingdom.cogs import strings as legacy

    for locale in ("fr", "en"):
        assert not [k for k in legacy.strings(locale) if k.startswith("validation_")]


def test_the_dashboard_builds_without_a_stack() -> None:
    """A boot with no wired service still pins the empty dashboard."""
    from botforge.mods.kingdom.cogs import validation as kv

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
    from botforge.mods.kingdom.cogs import validation as kv

    KV = models.KingdomValidation
    pending = NS(id="kb", is_gaia=False, name="Bourgogne", validation=KV.PENDING)
    approved = NS(id="ka", is_gaia=False, name="Anjou", validation=KV.APPROVED)
    refused = NS(id="kr", is_gaia=False, name="Breton", validation=KV.REFUSED)
    gaia = NS(id="gaia", is_gaia=True, name="Gaia", validation=KV.APPROVED)
    original = kv.wiring
    kv.wiring = lambda: _fake_stack([pending], [approved], [refused, gaia], [])
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
    from botforge.mods.kingdom.cogs import validation as kv

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
            sent=None,
            deferred=False,
        )
        response.is_done = lambda: response.done  # type: ignore[method-assign]

        async def _defer(ephemeral: bool = False) -> None:
            # windows-v2 fast-ack: the ack goes FIRST, the work after
            response.deferred = True  # type: ignore[assignment]
            response.done = True  # type: ignore[assignment]

        async def _send(msg: str, ephemeral: bool = False) -> None:
            response.sent = msg  # type: ignore[assignment]

        response.defer = _defer  # type: ignore[method-assign]
        response.send_message = _send  # type: ignore[method-assign]
        followup = NS(sent=[], edited=None)

        async def _fsend(msg: str, ephemeral: bool = False, **kwargs: Any) -> None:
            followup.sent.append(msg)

        async def _fedit(message_id: Any = None, **kwargs: Any) -> None:
            followup.edited = kwargs.get("view")  # type: ignore[assignment]

        followup.send = _fsend  # type: ignore[method-assign]
        followup.edit_message = _fedit  # type: ignore[method-assign]
        inter: Any = NS(
            guild_id="42",
            user=NS(id="77"),
            locale="fr",
            client=NS(status_service=NS(bot_admins=("77",)), roles_service=None),
            response=response,
            followup=followup,
            message=NS(id="m1"),
        )
        button = kv.ValidationDecisionButton("kb", "ok", "✅", _kv_module().discord.ButtonStyle.success)
        asyncio.run(button.callback(inter))
        assert response.deferred, "the click is ACKED before the seconds of work"
        assert calls == [("ok", "kb")], calls
        assert followup.edited is not None, "the pin must re-render in place"
        assert followup.sent, "the operator gets his confirmation"
    finally:
        kv.wiring = original


def test_the_guard_blocks_a_non_admin() -> None:
    """A non-admin click never reaches the service (click-time guard)."""
    from botforge.mods.kingdom.cogs import validation as kv

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


# ---------------------------------------------------------------------------
# validation-cards-v1 (Drasah 20/11): the approved kingdoms become cards
# with the sovereign admin actions — 🗑️ Supprimer + 👑 Changer le roi.
# ---------------------------------------------------------------------------


def test_validation_cards_strings_parity() -> None:
    """Every new yaml key exists in both locales and formats with its arity."""
    from botforge.mods.kingdom.cogs.common import mod_catalog

    for locale in ("fr", "en"):
        s = mod_catalog().section("kingdom.validation", locale)
        for key in (
            "accepted_empty",
            "delete_button",
            "crown_button",
            "gone_note",
            "delete_confirm_hint",
            "delete_confirm_button",
            "delete_cancel_button",
            "crown_hint",
            "crown_select_placeholder",
            "crown_king_option",
            "crown_no_lords",
        ):
            assert s[key], (locale, key)
        s["delete_confirm_title"].format(name="X")
        s["deleted_note"].format(name="X")
        s["crown_title"].format(name="X")
        s["crown_note"].format(king="X", name="Y")
        # ejection-archive-v1 : l'éjection (territoires redistribués),
        # l'archive (la maison part, les données restent)
        s["ejected_realms_note"].format(
            territories=6, kingdoms=2, per_kingdom=2, to_gaia=1
        )
        for key in ("archive_button", "archive_already_note", "archive_confirm_button"):
            assert s[key], (locale, key)
        s["archive_confirm_title"].format(name="X")
        s["archive_confirm_hint"].format(name="X", deleted=3)
        s["archived_note"].format(name="X", deleted=3)


def test_approved_kingdoms_carry_the_sovereign_actions() -> None:
    """One 🗑️/👑 pair per approved kingdom, restart-proof custom ids."""
    from botforge.mods.kingdom import models
    from botforge.mods.kingdom.cogs import validation as kv

    KV = models.KingdomValidation
    approved = NS(id="ka", is_gaia=False, name="Anjou", validation=KV.APPROVED)
    original = kv.wiring
    kv.wiring = lambda: _fake_stack([], [approved], [], [])
    try:
        view = asyncio.run(kv.build_validation_panel("42"))
        ids = [b.get("custom_id") for b in _buttons(view)]
        assert "kingdom:valid:del:ka" in ids, ids
        assert "kingdom:valid:crown:ka" in ids, ids
    finally:
        kv.wiring = original


def _fake_style() -> Any:
    from botforge.mods.kingdom.cogs import validation as kv

    return kv.discord.ButtonStyle.danger


def test_sovereign_buttons_rebuild_from_the_wire() -> None:
    """The dynamic templates fullmatch the two custom ids (boot registration)."""
    import re

    from botforge.mods.kingdom.cogs import validation as kv

    del_match = re.match(
        kv.ValidationDeleteButton.__discord_ui_compiled_template__.pattern,
        "kingdom:valid:del:ka",
    )
    crown_match = re.match(
        kv.ValidationCrownButton.__discord_ui_compiled_template__.pattern,
        "kingdom:valid:crown:ka",
    )
    assert del_match and del_match["kingdom_id"] == "ka"
    assert crown_match and crown_match["kingdom_id"] == "ka"
    assert not re.match(
        kv.ValidationDeleteButton.__discord_ui_compiled_template__.pattern,
        "kingdom:valid:ka:ok",
    )


def test_the_king_role_wins_the_display_name_and_sorts_first() -> None:
    """_is_king + _active_members: the KING rides first, left lords never do."""
    from botforge.mods.kingdom.cogs import validation as kv

    class Role:
        name = "KING"

    king = NS(id="p1", kingdom_id="ka", left=False, role=Role(), display_name="Drasah")
    lord = NS(id="p2", kingdom_id="ka", left=False, role=NS(name="LORD"), display_name="PytoLux")
    gone = NS(id="p3", kingdom_id="ka", left=True, role=Role(), display_name="Gone")
    elsewhere = NS(id="p4", kingdom_id="kb", left=False, role=Role(), display_name="X")

    async def _lords() -> list[Any]:
        return [lord, gone, elsewhere, king]

    stack = NS(kingdoms=NS(lords=_lords))
    members = asyncio.run(kv._active_members(stack, "ka"))
    assert [m.id for m in members] == ["p1", "p2"], members
    assert kv._is_king(king) and not kv._is_king(lord)


def test_the_delete_confirm_card_builds_and_carries_both_choices() -> None:
    """The red confirm card renders with its two stable choice buttons."""
    from botforge.mods.kingdom.cogs.common import mod_catalog
    from botforge.mods.kingdom.cogs import validation as kv

    strings = mod_catalog().section("kingdom.validation", "fr")
    kingdom = NS(id="ka", name="Anjou")
    view = kv._delete_confirm_card(strings, "fr", kingdom)
    flat = [str(i.get("custom_id", "")) for i in _flatten(view.to_components()) if i.get("type") == 2]
    assert any("del-yes:ka" in cid for cid in flat), flat
    assert any("del-no:ka" in cid for cid in flat), flat


# ---------------------------------------------------------------------------
# t2a (Drasah 20/11): the realms' season-entry requests ride the dashboard —
# the admin enrolls the realm, refuses it, or finds no season to join.
# ---------------------------------------------------------------------------


def _fake_realm_stack(realms: list[Any]) -> Any:
    async def _realms() -> list[Any]:
        return realms

    async def _realm_of_slug(slug: str) -> Any:
        for realm in realms:
            if realm.slug == slug:
                return realm
        return None

    service = NS(realms=_realms, realm_of_slug=_realm_of_slug)
    return NS(kingdoms=NS(kingdoms=_no_kingdoms, lords=_no_lords), realms=service)


async def _no_kingdoms() -> list[Any]:
    return []


async def _no_lords() -> list[Any]:
    return []


def test_the_dashboard_shows_the_realm_entry_requests() -> None:
    """One card + one ✅/❌ pair per realm with a pending join request."""
    from botforge.mods.kingdom.cogs import validation as kv

    realm = NS(
        id="realm:x-77",
        slug="x",
        name="Château Noir",
        king_id="77",
        king_name="Drasah",
        presentation="Le val oublié.",
        join_request={"season_id": "s1", "requested_at": 1760000000},
        member_ids=[],
    )
    quieter = NS(id="realm:y-88", slug="y", name="Quiet", king_id="88", king_name="Q", presentation="", join_request=None, member_ids=[])
    original = kv.wiring
    kv.wiring = lambda: _fake_realm_stack([realm, quieter])
    try:
        view = asyncio.run(kv.build_validation_panel("42"))
        texts = _texts(view)
        assert any("Château Noir" in t for t in texts), texts
        assert any("Le val oublié" in t for t in texts), texts
        assert not any("Quiet" in t for t in texts), texts
        ids = [b.get("custom_id") for b in _buttons(view)]
        assert "kingdom:valid:realmjoin:x:ok" in ids, ids
        assert "kingdom:valid:realmjoin:x:no" in ids, ids
    finally:
        kv.wiring = original


def test_the_realm_entry_button_rebuilds_from_the_wire() -> None:
    """The dynamic template fullmatches the slug-keyed custom id."""
    import re

    from botforge.mods.kingdom.cogs import validation as kv

    match = re.match(
        kv.ValidationRealmEntryButton.__discord_ui_compiled_template__.pattern,
        "kingdom:valid:realmjoin:chateau-noir:ok",
    )
    assert match and match["slug"] == "chateau-noir" and match["choice"] == "ok"
    assert not re.match(
        kv.ValidationRealmEntryButton.__discord_ui_compiled_template__.pattern,
        "kingdom:valid:chateau-noir:ok",
    )


def test_the_admin_refusal_withdraws_the_request() -> None:
    """❌ calls clear_join_request and reports the off-season note."""
    from botforge.mods.kingdom.cogs import validation as kv

    calls: list[str] = []
    realm = NS(id="realm:x-77", slug="x", name="Château Noir", join_request={"season_id": "s1"})

    async def _clear(realm_id: str) -> Any:
        calls.append(realm_id)
        realm.join_request = None
        return realm

    service = NS(clear_join_request=_clear)
    note = asyncio.run(kv._refuse_season_entry(service, realm, {"realm_refused_note": "off {name}"} | {"realm_refused_note": "🚫 {name}"}))
    assert calls == ["realm:x-77"], calls
    assert "Château Noir" in note, note
    assert realm.join_request is None


def test_the_acceptance_needs_a_running_season() -> None:
    """No season → the admin gets the no-season note, nothing touched."""
    from botforge.mods.kingdom.cogs import validation as kv

    realm = NS(id="realm:x-77", slug="x", name="Château Noir")
    stack = NS(kingdoms=NS(current_season=_none_season), realms=NS())
    note = asyncio.run(
        kv._accept_season_entry(None, stack, NS(), realm, {"realm_entry_no_season": "NO"}, "fr")
    )
    assert note == "NO", note


async def _none_season() -> Any:
    return None


def test_the_acceptance_orchestrates_the_full_entry() -> None:
    """✅ → add_kingdom (the draft starter), queue+claim for the Roi,
    one enroll per member, engage() binds the shell."""
    from botforge.mods.kingdom import models
    from botforge.mods.kingdom.cogs import validation as kv

    engine: dict[str, list[Any]] = {"calls": [], "lords": []}
    kingdom = NS(id="k42", name="Château Noir", civilizations=["heaps"])
    realm = NS(
        id="realm:x-77",
        slug="x",
        name="Château Noir",
        king_id="77",
        king_name="Drasah",
        join_request={"season_id": "s1", "requested_at": 1},
        member_ids=["78"],
    )

    async def _current_season() -> Any:
        return NS(id="s1")

    async def _require_season() -> Any:
        return NS(id="s1")

    async def _add_kingdom(name: str) -> Any:
        engine["calls"].append(("add_kingdom", name))
        return kingdom

    async def _queue_king(pid: str, display: str) -> Any:
        engine["calls"].append(("queue", pid))
        engine["lords"].append(NS(id=pid, in_queue=True))

    async def _claim(pid: str, kid: str) -> Any:
        engine["calls"].append(("claim", pid, kid))

    async def _enroll(pid: str, display: str, role: Any, kingdom_name: str | None = None) -> Any:
        engine["calls"].append(("enroll", pid, str(role)))
        engine["lords"].append(NS(id=pid, kingdom=kingdom_name))

    async def _engage(realm_id: str, season_id: str, kingdom_id: str) -> Any:
        engine["calls"].append(("engage", realm_id, kingdom_id))
        realm.engagement = {"season_id": season_id, "kingdom_id": kingdom_id}
        return realm

    stack = NS(
        kingdoms=NS(
            current_season=_current_season,
            _require_season=_require_season,
            add_kingdom=_add_kingdom,
            enroll_king_awaiting_kingdom=_queue_king,
            claim_kingdom=_claim,
            enroll=_enroll,
        ),
        realms=NS(engage=_engage),
    )
    inter = NS(guild=None)
    note = asyncio.run(
        kv._accept_season_entry(
            inter, stack, stack.realms, realm,
            {"realm_accepted_note": "✅ {name} → {kingdom}"}, "fr",
        )
    )
    calls = engine["calls"]
    assert ("add_kingdom", "Château Noir") in calls, calls
    assert ("queue", "77") in calls and ("claim", "77", "k42") in calls, calls
    assert any(c[0] == "enroll" and c[1] == "78" for c in calls), calls
    assert ("engage", "realm:x-77", "k42") in calls, calls
    assert "✅" in note, note


def test_t2a_strings_parity() -> None:
    """The nine new yaml keys exist in both locales with their arities."""
    from botforge.mods.kingdom.cogs.common import mod_catalog

    for locale in ("fr", "en"):
        s = mod_catalog().section("kingdom.validation", locale)
        for key in (
            "realm_requests_header",
            "realm_abort_button" if False else "realm_request_presentation",
            "realm_accept_button",
            "realm_refuse_button",
            "realm_entry_no_season",
        ):
            assert s[key], (locale, key)
        s["realm_request_row"].format(name="X", king="Y", when="Z")
        s["realm_accepted_note"].format(name="X", kingdom="Y")
        s["realm_refused_note"].format(name="X")
        s["realm_entry_error"].format(error="X")
        rs = None
        from botforge.mods.kingdom.cogs.realm_strings import realm_strings
        rs = realm_strings(locale)
        assert rs["season_engaged_line"], locale
        rs["season_engaged_line"].format(season="X", kingdom="Y")
