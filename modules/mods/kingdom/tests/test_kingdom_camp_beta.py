"""camp-beta-v1 (Drasah 19/11) — the beta founding door contract.

Drasah's ruling: a BETA season arms the PROVISIONAL Roi/Seigneur door
(found auto-approved, join picker, queue fallback); a normal season
shows nothing provisional. The tests pin the door's contract down: the
declared window id, the FR/EN parity, the restart-proof custom ids, the
modal's label budget, and the beta gate (armed only on a beta season).
"""

from __future__ import annotations

CAMP_KEYS = (
    "button",
    "window_title",
    "window_help",
    "found_button",
    "join_button",
    "join_window_title",
    "join_help",
    "pick_placeholder",
    "seats_left",
    "queue_button",
    "modal_title",
    "modal_label",
    "found_done",
    "join_done",
    "queue_done",
    "no_kingdoms",
    "already_king_line",
    "already_lord_line",
    "already_queue_line",
    "none_note",
    "err_kingdoms_already_enrolled",
    "err_kingdoms_no_season",
    "err_kingdoms_name_invalid",
    "err_kingdoms_kingdom_limit",
    "err_kingdoms_kingdom_full",
    "err_kingdoms_not_enrollable",
    "err_kingdoms_imposed",
    "err_kingdoms_kingdom_not_found",
    "error",
    "realms_pick_restore_placeholder",
    "realms_pick_archived_label",
    "realms_pick_archived_hint",
    "realms_restore_confirm_title",
    "realms_restore_confirm_hint",
    "realms_restore_yes",
    "realms_restore_no",
    "realms_restore_done",
    "realms_restore_failed",
    "realms_restore_not_yours",
    "realms_restore_gone",
    # fonder-purge-v1 (Drasah 24/11) : fonder contre SA coquille archivée
    "found_once_note",
    "found_refound_title",
    "found_refound_hint",
    "found_refound_yes",
    "found_refound_no",
    "found_refound_cancelled",
    "found_refound_missing",
    "found_refound_gone",
    "found_refound_taken",
    "found_refound_done",
)


def test_camp_surface_is_declared() -> None:
    """The provisional door's window appears in conf/views.yaml (#381 ruling 1)."""
    from pathlib import Path

    views = (
        Path(__file__).resolve().parents[1] / "conf" / "views.yaml"
    ).read_text(encoding="utf-8")
    assert "panel:mod:kingdom:camp" in views, "panel:mod:kingdom:camp must be declared"


def test_camp_strings_parity() -> None:
    """Every camp string exists in BOTH locales and formats cleanly."""
    from botforge.mods.kingdom.cogs.camp_beta import camp_strings

    for locale in ("fr", "en"):
        strings = camp_strings(locale)
        for key in CAMP_KEYS:
            assert strings.get(key), f"missing kingdom.camp.{key} in {locale}"
        strings["seats_left"].format(2)
        strings["found_done"].format("Nilrem")
        strings["join_done"].format("Nilrem")
        strings["already_king_line"].format("Nilrem")
        strings["already_lord_line"].format("Nilrem")
        strings["error"].format("boom")
        strings["realms_pick_archived_label"].format(name="Roc")
        strings["realms_restore_confirm_hint"].format(name="Roc")
        strings["realms_restore_done"].format("Roc")
        # fonder-purge-v1 : chaque placeholder se formate SANS KeyError
        strings["found_refound_title"].format(new="Fois")
        strings["found_refound_hint"].format(name="Aegis", new="Fois")
        strings["found_refound_yes"].format(new="Fois")
        strings["found_refound_taken"].format(name="Fois")
        strings["found_refound_done"].format(name="Aegis", new="Fois")
        # the modal budget (rule: Label ≤45 chars)
        assert len(strings["modal_label"]) <= 45
        assert len(strings["modal_title"]) <= 45


def test_camp_custom_ids() -> None:
    """Every camp door is a restart-proof DynamicItem with its stable id."""
    from botforge.mods.kingdom.cogs.camp_beta import (
        CAMP_WINDOW_KEY,
        KingdomCampButton,
        KingdomCampFoundButton,
        KingdomCampJoinButton,
        KingdomCampJoinSelect,
        KingdomCampQueueButton,
        KingdomCampRealmSelect,
        KingdomCampRestoreButton,
        camp_dynamic_items,
    )

    assert CAMP_WINDOW_KEY == "panel:mod:kingdom:camp"
    assert KingdomCampButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:camp:open"
    )
    assert KingdomCampFoundButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:camp:found"
    )
    assert KingdomCampJoinButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:camp:join"
    )
    assert KingdomCampQueueButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:camp:queue"
    )
    assert KingdomCampJoinSelect("x").custom_id == "kingdom:camp:pick"
    from botforge.mods.kingdom.cogs.camp_beta import KingdomCampRefoundButton

    assert set(camp_dynamic_items()) == {
        KingdomCampButton,
        KingdomCampFoundButton,
        KingdomCampJoinButton,
        KingdomCampQueueButton,
        KingdomCampJoinSelect,
        KingdomCampRealmSelect,
        KingdomCampRestoreButton,
        KingdomCampRefoundButton,
    }
    # reset-joueurs-v1 : le réveil du fondateur est restart-proof aussi
    assert (
        KingdomCampRestoreButton(
            "-yes", "roc", "7", "x", None  # type: ignore[arg-type]
        ).custom_id
        == "kingdom:camp:restore-yes:roc:7"
    )
    # fonder-purge-v1 : le purge-pour-fonder est restart-proof AUSSI —
    # l'id de coquille porte un ":" (drain-coquilles-v1, Check 135) et
    # le template l'attrape ENTIÈR (ancré $, jamais tronqué)
    assert (
        KingdomCampRefoundButton(
            "-yes", "realm:aegis-123", "155", "x", None  # type: ignore[arg-type]
        ).custom_id
        == "kingdom:camp:refound-yes:realm:aegis-123:155"
    )


def test_beta_gate_off_without_a_season() -> None:
    """No service wired → the door never arms (a normal season shows nothing)."""
    import asyncio

    from botforge.mods.kingdom.cogs.camp_beta import beta_armed

    assert asyncio.run(beta_armed()) is False


def test_apply_panel_builds_without_service() -> None:
    """The Postuler panel still builds in CI (the camp row only rides a beta)."""
    import asyncio

    from botforge.mods.kingdom.cogs.apply_flow import build_apply_panel

    assert asyncio.run(build_apply_panel("123")) is not None


def test_season_door_opens_for_any_live_season() -> None:
    """camp-door-any-season (Drasah 20/11): the ⚔️ door shows when a
    season RUNS — classical or beta alike; the door's gate is the
    season's LIFE, no longer its weekend format."""
    import asyncio

    import botforge.mods.kingdom.cogs.camp_beta as cb

    class _Season:
        finished = False
        beta_name = None  # a CLASSICAL season

    class _Kingdom:
        async def current_season(self) -> object:
            return _Season()

    class _Stack:
        kingdoms = _Kingdom()

    def fake_wiring() -> object:
        return _Stack()

    original = cb.wiring
    cb.wiring = fake_wiring
    try:
        assert asyncio.run(cb.season_door_open()) is True
    finally:
        cb.wiring = original


def test_season_door_stays_closed_without_a_season() -> None:
    """No stack, no season or a FINISHED season: the door stays shut."""
    import asyncio

    import botforge.mods.kingdom.cogs.camp_beta as cb

    class _Season:
        finished = True
        beta_name = "now"

    class _Kingdom:
        async def current_season(self) -> object:
            return _Season()

    class _Stack:
        kingdoms = _Kingdom()

    def finished_wiring() -> object:
        return _Stack()

    original = cb.wiring
    cb.wiring = finished_wiring
    try:
        assert asyncio.run(cb.season_door_open()) is False
    finally:
        cb.wiring = original

        def empty_wiring() -> None:
            return None

        cb.wiring = empty_wiring
        assert asyncio.run(cb.season_door_open()) is False


# ---------------------------------------------------------------------------
# reset-joueurs-v1 (Drasah 22/11) — the founder wakes his archived home
# ---------------------------------------------------------------------------


def test_the_founders_archived_realm_leads_the_picker(monkeypatch) -> None:
    """⚔️ Choisir mon camp → Rejoindre un royaume : le royaume ARCHIVÉ du
    FONDATEUR apparaît EN PREMIER marqué « (archivé) » ; les archivés des
    AUTRES rois restent invisibles ; les vivants restent rejoignables."""
    import asyncio
    from types import SimpleNamespace

    import discord

    from botforge.mods.kingdom.cogs import camp_beta, common
    from botforge.mods.kingdom.cogs.camp_beta import _realms_join_window

    shells = [
        SimpleNamespace(
            id="r1", name="Vivante", slug="vivante", king_id="9",
            member_ids=[], archived_at=0,
        ),
        SimpleNamespace(
            id="r2", name="Roc", slug="roc", king_id="42",
            member_ids=[], archived_at=123,
        ),
        SimpleNamespace(
            id="r3", name="AutreBoite", slug="autre-boite", king_id="7",
            member_ids=[], archived_at=456,
        ),
    ]

    class _Realms:
        async def realms(self):
            return shells

    monkeypatch.setattr(camp_beta, "wiring", lambda: SimpleNamespace(realms=_Realms()))
    monkeypatch.setattr(common, "locale_of", lambda _i: "fr")

    def _options(node: object) -> list:
        found: list = []
        for child in getattr(node, "children", []) or []:
            if isinstance(child, discord.SelectOption):
                found.append(child)
            elif isinstance(child, discord.ui.Select):
                found.extend(child.options or [])
            else:
                found.extend(_options(child))
        return found

    me = SimpleNamespace(id=42)
    view = asyncio.run(_realms_join_window(SimpleNamespace(user=me)))
    labels = [str(o.label) for o in _options(view)]
    assert labels and "Roc" in labels[0] and "archivé" in labels[0], (
        "the founder's archived realm leads the picker"
    )
    assert any("Vivante" in l for l in labels[1:]), "living realms stay joinable"
    assert not any("AutreBoite" in l for l in labels), (
        "another king's archived realm stays invisible"
    )
