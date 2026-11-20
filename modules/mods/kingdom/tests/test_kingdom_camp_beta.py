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
    from botforge.mods.kingdom.cogs.kingdom.camp_beta import camp_strings

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
        # the modal budget (rule: Label ≤45 chars)
        assert len(strings["modal_label"]) <= 45
        assert len(strings["modal_title"]) <= 45


def test_camp_custom_ids() -> None:
    """Every camp door is a restart-proof DynamicItem with its stable id."""
    from botforge.mods.kingdom.cogs.kingdom.camp_beta import (
        CAMP_WINDOW_KEY,
        KingdomCampButton,
        KingdomCampFoundButton,
        KingdomCampJoinButton,
        KingdomCampJoinSelect,
        KingdomCampQueueButton,
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
    assert set(camp_dynamic_items()) == {
        KingdomCampButton,
        KingdomCampFoundButton,
        KingdomCampJoinButton,
        KingdomCampQueueButton,
        KingdomCampJoinSelect,
    }


def test_beta_gate_off_without_a_season() -> None:
    """No service wired → the door never arms (a normal season shows nothing)."""
    import asyncio

    from botforge.mods.kingdom.cogs.kingdom.camp_beta import beta_armed

    assert asyncio.run(beta_armed()) is False


def test_apply_panel_builds_without_service() -> None:
    """The Postuler panel still builds in CI (the camp row only rides a beta)."""
    import asyncio

    from botforge.mods.kingdom.cogs.kingdom.apply_flow import build_apply_panel

    assert asyncio.run(build_apply_panel("123")) is not None
