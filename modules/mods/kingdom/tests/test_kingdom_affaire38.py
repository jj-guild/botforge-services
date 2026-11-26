"""Affaire 38 / kingdom-report-v1 (Drasah 26/11) — « 🚩 Signaler ».

Acté Drasah 26/11 : la porte du signalement vit À DROITE de « 🏰
Entrée » dans le hub du royaume, MEMBRES du royaume (Roi inclus) —
catégorie (bug de jeu, litige de score, comportement, autre) puis
texte libre, la ligne atterrit dans le journal admin 📜 logs.

Le flux ne crée AUCUN moteur : le bouton et le menu sont des
DynamicItem restart-proof, la ligne part par le seam admin (kind
``report``, l'emoji est une rangée de DONNÉES), l'anti-spam est une
mémoire vive de process (10 minutes par membre).
"""

from __future__ import annotations

import time as _time
from types import SimpleNamespace
from typing import Any
import pytest


def _strings() -> dict[str, str]:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    return realm_strings("fr")


def _realm() -> Any:
    return SimpleNamespace(
        name="PLOP", slug="plop", join_request=None,
        king_id="42", member_ids=[42, 43], engagement=None,
    )


def _wires(view: Any) -> list[str]:
    wires: list[str] = []
    pending = list(getattr(view, "children", []) or [])
    rows: list[list[str]] = []
    while pending:
        item = pending.pop(0)
        kids = getattr(item, "children", None)
        if kids:
            pending.extend(list(kids))
            rows.append([str(getattr(k, "custom_id", "") or "") for k in kids])
        else:
            rid = str(getattr(item, "custom_id", "") or "")
            if rid:
                wires.append(rid)
    setattr(view, "_rows_for_test", rows)  # type: ignore[attr-defined]
    return wires


# ---------------------------------------------------------------------------
# La porte du hub — à droite de l'Entrée, les deux états
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_the_hub_carries_the_report_door_right_of_the_entry() -> None:
    """🚩 vit dans la rangée 1, juste APRÈS 🏰 Entrée — dormant et vivant."""
    from botforge.mods.kingdom.cogs.realms import hub_layout

    for dormant in (True, False):
        view = hub_layout(_realm(), _strings(), dormant=dormant)
        wires = _wires(view)
        assert "kingdom:realm:report" in wires, f"dormant={dormant}"
        rows = getattr(view, "_rows_for_test")  # type: ignore[attr-defined]
        row_ids = next(r for r in rows if "kingdom:realm:home:plop" in r)
        home_at = row_ids.index("kingdom:realm:home:plop")
        assert row_ids[home_at + 1] == "kingdom:realm:report", (
            "à droite de l'Entrée, acté Drasah 26/11"
        )


@pytest.mark.asyncio
async def test_the_report_window_lists_the_four_natures() -> None:
    """La fenêtre porte le menu des 4 natures, restart-proof par custom_id."""
    from botforge.mods.kingdom.cogs import report

    strings = _strings()
    view = report.report_window(strings)
    wires = _wires(view)
    assert "kingdom:realm:report:cat" in wires
    select = report.RealmReportCategorySelect(report._category_options(strings))
    values = [str(o.value) for o in select.item.options]
    assert values == ["bug", "score", "behavior", "other"]


# ---------------------------------------------------------------------------
# La ligne du journal — categorie + texte libre, kind « report »
# ---------------------------------------------------------------------------


class _FakeInteraction(SimpleNamespace):
    class _Response:
        def __init__(self) -> None:
            self.sent: list[tuple[str, dict[str, Any]]] = []

        async def defer(self, *_a: Any, **_k: Any) -> None:
            self.sent.append(("defer", {}))

        async def send_message(self, *a: Any, **k: Any) -> None:
            self.sent.append(("send_message", {"args": a, "kwargs": k}))

    def __init__(self) -> None:
        response = self._Response()
        super().__init__(
            guild_id="77", user=SimpleNamespace(id="42"),
            locale="fr", response=response,
        )


@pytest.mark.asyncio
async def test_the_modal_posts_one_admin_line_and_cools_down(monkeypatch: Any) -> None:
    """Une soumission = UNE ligne administrateur (kind report) + garde posée."""
    from botforge.mods.kingdom.cogs import report

    posted: list[dict[str, Any]] = []

    async def fake_log(interaction: Any, kind: str, action: str) -> None:
        posted.append({"kind": kind, "action": action})

    monkeypatch.setattr(report, "log_admin_action_on_interaction", fake_log)
    report._LAST_REPORT.clear()

    strings = _strings()
    modal = report.ReportModal(strings, "bug")
    modal.body = SimpleNamespace(value="Le score de la partie 3 est faux.")
    interaction = _FakeInteraction()
    await modal.on_submit(interaction)

    assert len(posted) == 1, "one line per report, the seam takes it"
    assert posted[0]["kind"] == "report"
    assert "Bug de jeu" in posted[0]["action"]
    assert "Le score de la partie 3 est faux." in posted[0]["action"]
    assert any(
        name == "send_message" and payload["kwargs"].get("ephemeral") is True
        for name, payload in interaction.response.sent
    ), "the member gets his ✅ note"
    # the anti-spam guard is armed for THIS member only
    assert report._LAST_REPORT.get("77:42") is not None
    assert report._cooldown_left("77", "42", _time.time() + 1) >= 1
    assert report._cooldown_left("77", "43", _time.time() + 1) == 0


@pytest.mark.asyncio
async def test_an_empty_description_never_post(monkeypatch: Any) -> None:
    from botforge.mods.kingdom.cogs import report

    posted: list[Any] = []

    async def fake_log(interaction: Any, kind: str, action: str) -> None:
        posted.append((kind, action))

    monkeypatch.setattr(report, "log_admin_action_on_interaction", fake_log)
    report._LAST_REPORT.clear()

    modal = report.ReportModal(_strings(), "other")
    modal.body = SimpleNamespace(value="   ")
    await modal.on_submit(_FakeInteraction())
    assert not posted, "an empty report never reaches the journal"


def test_the_anti_spam_window_is_ten_minutes() -> None:
    from botforge.mods.kingdom.cogs import report

    assert report._COOLDOWN_SECONDS == 600
    now = _time.time()
    assert report._cooldown_left("g1", "u1", now) == 0  # jamais signalé
    report._LAST_REPORT["g1:u1"] = now - 90
    assert report._cooldown_left("g1", "u1", now) == 9  # 600-90 s → 9 min
    report._LAST_REPORT["g1:u1"] = now - 601
    assert report._cooldown_left("g1", "u1", now) == 0  # gardien expiré


@pytest.mark.asyncio
async def test_the_registration_and_the_kind_row() -> None:
    """Le bouton/menu sont restart-proof ET l'emoji est une rangée de DONNÉES."""
    from botforge.mods.kingdom.cogs import report
    from botforge.mods.kingdom.cogs.admin_logs import KIND_EMOJI
    from botforge.mods.kingdom.cogs.realms import realm_dynamic_items

    items = realm_dynamic_items()
    assert report.RealmReportButton in items
    assert report.RealmReportCategorySelect in items
    assert KIND_EMOJI["report"] == "🚩"


@pytest.mark.asyncio
async def test_the_catalog_parity_fr_en() -> None:
    from botforge.mods.kingdom.cogs.realm_strings import realm_strings

    fr = realm_strings("fr")
    en = realm_strings("en")
    for key in (
        "report_button", "report_intro", "report_hint",
        "report_cat_bug", "report_cat_score", "report_cat_behavior", "report_cat_other",
        "report_modal_title", "report_text_label", "report_text_placeholder",
        "report_empty_note", "report_done_note", "report_cooldown_note", "report_log_line",
    ):
        assert fr.get(key), f"fr misses {key}"
        assert en.get(key), f"en misses {key}"
    assert fr["report_log_line"].count("{") == en["report_log_line"].count("{")
    assert fr["report_cooldown_note"].count("{") == en["report_cooldown_note"].count("{")


@pytest.mark.asyncio
async def test_the_realm_error_fallback_still_open(monkeypatch: Any) -> None:
    """Une fenêtre du hub plantée ne quitte jamais sans réponse (le pattern)."""
    from botforge.mods.kingdom.cogs import report

    strings = _strings()
    button = report.RealmReportButton(strings["report_button"])
    interaction = _FakeInteraction()
    report._LAST_REPORT.clear()  # la porte s'ouvre, pas la note cooldown
    monkeypatch.setattr(report, "report_window", lambda s: (_ for _ in ()).throw(RuntimeError("boom")))
    await button.callback(interaction)
    assert any(name in ("defer", "send_message") for name, _ in interaction.response.sent)
