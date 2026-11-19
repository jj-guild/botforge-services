"""machine-temps-v3 + distributeur-v1 (Drasah 19/11) — wiring smoke tests.

The ⏱️ time machine and the 🎁 distributor are pinned declared
surfaces riding the platform admin guard and the service seams; the
tests pin the contract down: the view ids, the restart-proof custom
ids (incl. the kingdom id riding the injector's), the FR/EN parity,
the locale rendering of the console ops, and the snapshot engine.
"""

from __future__ import annotations

FR_MACHINE_KEYS = (
    "title",
    "help",
    "clock_line",
    "phase_line",
    "running_line",
    "paused_line",
    "paused_set_line",
    "resumed_line",
    "offset_line",
    "next_cycle_line",
    "next_age_line",
    "verdict_line",
    "snapshots_line",
    "snapshots_empty",
    "refresh_button",
    "refresh_done",
    "pause_button",
    "resume_button",
    "snapshot_button",
    "snapshot_done",
    "restore_button",
    "restore_title",
    "restore_help",
    "restore_row",
    "restore_do_button",
    "restore_done",
    "setup_button",
    "setup_confirm_title",
    "setup_confirm_hint",
    "setup_confirm_button",
    "setup_cancel_button",
    "setup_done",
    "d1_button",
    "d3_button",
    "d7_button",
    "jump_done",
    "freejump_button",
    "freejump_modal_title",
    "freejump_label",
    "freejump_done",
    "bad_input",
    "clockzero_button",
    "clockzero_done",
    "next_cycle_button",
    "next_age_button",
    "end_button",
    "switch_cycle_done",
    "switch_age_done",
    "end_done",
    "prev_cycle_button",
    "prev_age_button",
    "prev_age_done",
    "prev_snapshot_none",
    "lords_open_button",
    "lords_close_button",
    "lords_open_done",
    "lords_closed",
    "cancelled",
    "no_service",
    "error",
)

FR_DISTRIBUTOR_KEYS = (
    "title",
    "help",
    "test_exists_line",
    "open_button",
    "test_kingdom_button",
    "test_kingdom_done",
    "destruct_button",
    "destruct_confirm_title",
    "destruct_confirm_hint",
    "destruct_confirm_button",
    "destruct_cancel_button",
    "destruct_done",
    "window_title",
    "window_help",
    "no_kingdoms",
    "select_placeholder",
    "select_hint",
    "kingdom_header",
    "hand_line",
    "points_button",
    "territory_button",
    "civ_button",
    "points_done",
    "territory_done",
    "civ_done",
    "no_free_map",
    "no_free_civ",
    "test_option",
    "test_hint",
    "cancelled",
    "no_service",
    "error",
)


def test_machine_and_distributor_surfaces_are_declared() -> None:
    """The pinned panels + windows appear in conf/views.yaml (#381 ruling 1)."""
    from pathlib import Path

    views = (
        Path(__file__).resolve().parents[1] / "conf" / "views.yaml"
    ).read_text(encoding="utf-8")
    for view_id in (
        "panel:mod:kingdom:settings",
        "panel:mod:kingdom:time-machine",
        "panel:mod:kingdom:time-machine:restore",
        "panel:mod:kingdom:distributor",
        "panel:mod:kingdom:distributor:window",
    ):
        assert view_id in views, f"{view_id} must be declared in conf/views.yaml"


def test_machine_and_distributor_strings_parity() -> None:
    """Every machine/distributor string exists in BOTH locales."""
    from botforge.mods.kingdom.cogs.kingdom.distributor import distributor_strings
    from botforge.mods.kingdom.cogs.kingdom.time_machine import machine_strings

    for locale in ("fr", "en"):
        machine = machine_strings(locale)
        for key in FR_MACHINE_KEYS:
            assert machine.get(key), f"missing kingdom.machine.{key} in {locale}"
        distributor = distributor_strings(locale)
        for key in FR_DISTRIBUTOR_KEYS:
            assert distributor.get(key), f"missing kingdom.distributor.{key} in {locale}"
        machine["clock_line"].format("01/01 12:00")
        machine["phase_line"].format("setup")
        machine["offset_line"].format("+2h")
        machine["snapshots_line"].format(3, "a · b · c")
        machine["restore_row"].format("snapshot-manual-1", "01/01 12:00")
        machine["jump_done"].format(1)
        distributor["kingdom_header"].format("Nilrem")
        distributor["points_done"].format("Nilrem", 10)


def test_machine_custom_ids() -> None:
    """Every machine button is a restart-proof DynamicItem with its stable id."""
    from botforge.mods.kingdom.cogs.kingdom.time_machine import (
        MACHINE_VIEW_KEY,
        MachineClockZeroButton,
        MachineFreeJumpButton,
        MachineJumpButton,
        MachineLordsButton,
        MachinePauseButton,
        MachineRefreshButton,
        MachineRestoreButton,
        MachineRestorePickButton,
        MachineRollbackButton,
        MachineSetupButton,
        MachineSnapshotButton,
        MachineSwitchButton,
    )

    assert MACHINE_VIEW_KEY == "panel:mod:kingdom:time-machine"
    assert MachineRefreshButton("x").custom_id == "kingdom:machine:refresh"
    assert MachinePauseButton("x").custom_id == "kingdom:machine:pause"
    assert MachineSnapshotButton("x").custom_id == "kingdom:machine:snapshot"
    assert MachineRestoreButton("x").custom_id == "kingdom:machine:restore"
    assert MachineRestorePickButton("x", "snapshot-manual-1").custom_id == (
        "kingdom:machine:restore:snapshot-manual-1"
    )
    assert MachineSetupButton("x").custom_id == "kingdom:machine:setup"
    assert MachineJumpButton(3, "x").custom_id == "kingdom:machine:jump:3"
    assert MachineFreeJumpButton("x").custom_id == "kingdom:machine:freejump"
    assert MachineClockZeroButton("x").custom_id == "kingdom:machine:clockzero"
    assert MachineSwitchButton("cycle", "x").custom_id == "kingdom:machine:switch:cycle"
    assert MachineRollbackButton("age", "x").custom_id == "kingdom:machine:rollback:age"
    assert MachineLordsButton("open", "x").custom_id == "kingdom:machine:lords:open"


def test_distributor_custom_ids() -> None:
    """The distributor's doors + the injector's kingdom-carrying ids are stable."""
    from botforge.mods.kingdom.cogs.kingdom.distributor import (
        DISTRIBUTOR_VIEW_KEY,
        DistributorDestructButton,
        DistributorGiveButton,
        DistributorKingdomSelect,
        DistributorOpenButton,
        DistributorTestKingdomButton,
    )

    assert DISTRIBUTOR_VIEW_KEY == "panel:mod:kingdom:distributor"
    assert DistributorOpenButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:distributor:open"
    )
    assert DistributorTestKingdomButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:distributor:test-kingdom"
    )
    assert DistributorDestructButton("x", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:distributor:destruct"
    )
    assert DistributorGiveButton("x", "k-nilrem", "points").custom_id == (
        "kingdom:distributor:give:k-nilrem:points"
    )
    assert DistributorKingdomSelect("x").custom_id == "kingdom:distributor:pick"


def test_machine_and_distributor_panels_build_without_service() -> None:
    """The pinned panels render even with no service wired (holes, not raises)."""
    import asyncio

    from botforge.mods.kingdom.cogs.kingdom.distributor import build_distributor_panel
    from botforge.mods.kingdom.cogs.kingdom.time_machine import build_time_machine_panel

    assert asyncio.run(build_time_machine_panel("123")) is not None
    assert asyncio.run(build_distributor_panel("123")) is not None


def test_console_buttons_render_in_the_guild_locale() -> None:
    """Recette 19/11: the panel's console ops read in FR, not the EN defaults."""
    import re

    from botforge.mods.kingdom.cogs.kingdom.settings_panel import console_buttons
    from botforge.mods.kingdom.cogs.kingdom.common import strings_by_locale

    ops = console_buttons(strings_by_locale("fr"))
    labels = [str(b.item.label) for b in ops]
    assert any("Relancer la saison" in label for label in labels)
    assert any("Horloge" in label for label in labels)
    ids = [str(b.item.custom_id) for b in ops]
    assert sorted(ids) == [
        "kingdom:console:clock",
        "kingdom:console:relaunch",
        "kingdom:console:reset",
    ]
    # the settings actions' template must never fullmatch these ids
    from botforge.mods.kingdom.cogs.kingdom.settings_panel import SettingsActionButton

    template = re.compile(SettingsActionButton.__discord_ui_compiled_template__.pattern)
    assert not any(template.fullmatch(i) for i in ids)


def test_the_laboratoire_is_gone_from_the_declaration() -> None:
    """laboratoire-v3: the Labo group and its salons left the declaration."""
    from pathlib import Path

    import yaml

    data = yaml.safe_load(
        (Path(__file__).resolve().parents[1] / "conf" / "mod.yaml").read_text(encoding="utf-8")
    )
    groups = [str(g["key"]) for g in data.get("channel_groups") or []]
    keys = [str(c["key"]) for c in data.get("channels") or []]
    assert "laboratoire" not in groups
    assert "lab" not in keys and "lab_original" not in keys and "lab_travaux" not in keys
    # the new settings salon pins the console panel
    assert "settings" in keys


def test_snapshot_round_trip_on_a_fake_store() -> None:
    """snapshot → wipe → restore replays the data and freezes the season."""
    import asyncio

    from botforge.mods.kingdom.service import KingdomService

    class _Store:
        def __init__(self) -> None:
            self.db: dict[str, dict[str, dict]] = {}
            self.archives: list[dict] = []

        async def _find(self, name: str) -> list[dict]:
            return list(self.db.get(name, {}).values())

        async def find_seasons(self) -> list[dict]:
            return await self._find("seasons")

        async def find_kingdoms(self) -> list[dict]:
            return await self._find("kingdoms")

        async def find_lords(self) -> list[dict]:
            return await self._find("lords")

        async def find_territories(self) -> list[dict]:
            return await self._find("territories")

        async def find_technologies(self) -> list[dict]:
            return await self._find("technologies")

        async def find_attacks(self) -> list[dict]:
            return await self._find("attacks")

        async def find_showmatches(self) -> list[dict]:
            return await self._find("showmatches")

        async def find_ffas(self) -> list[dict]:
            return await self._find("ffas")

        async def find_plans(self) -> list[dict]:
            return await self._find("plans")

        async def upsert(self, name: str, doc: dict) -> None:
            self.db.setdefault(name, {})[doc["_id"]] = dict(doc)

        async def upsert_season(self, doc: dict) -> None:
            await self.upsert("seasons", doc)

        async def upsert_kingdom(self, doc: dict) -> None:
            await self.upsert("kingdoms", doc)

        async def upsert_lord(self, doc: dict) -> None:
            await self.upsert("lords", doc)

        async def upsert_territory(self, doc: dict) -> None:
            await self.upsert("territories", doc)

        async def upsert_technology(self, doc: dict) -> None:
            await self.upsert("technologies", doc)

        async def upsert_attack(self, doc: dict) -> None:
            await self.upsert("attacks", doc)

        async def upsert_showmatch(self, doc: dict) -> None:
            await self.upsert("showmatches", doc)

        async def upsert_ffa(self, doc: dict) -> None:
            await self.upsert("ffas", doc)

        async def upsert_plan(self, doc: dict) -> None:
            await self.upsert("plans", doc)

        async def wipe_season_data(self) -> None:
            self.db.clear()

        async def upsert_season_archive(self, doc: dict) -> None:
            self.archives.append(dict(doc))

        async def find_season_archives(self) -> list[dict]:
            return list(self.archives)

    class _Config:
        pass

    store = _Store()
    svc = KingdomService(store, _Config())  # type: ignore[arg-type]

    async def _scenario() -> None:
        # one photographed season, one kingdom
        await store.upsert_season(
            {
                "_id": "s1",
                "started_at": __import__("datetime").datetime(2026, 11, 1, tzinfo=__import__("datetime").timezone.utc),
                "weeks": 4,
                "current_cycle": 2,
                "current_age_key": "dark_age",
                "phase": "started",
                "frozen": False,
            }
        )
        await store.upsert_kingdom({"_id": "k-1", "name": "Royaume A", "type": "player"})
        snapshot_id = await svc.snapshot("manual")
        assert snapshot_id.startswith("snapshot-manual-")
        # the operator wipes everything, then rewinds
        await store.wipe_season_data()
        assert not await store.find_kingdoms()
        await svc.restore_snapshot(snapshot_id)
        seasons = await store.find_seasons()
        kingdoms = await store.find_kingdoms()
        assert {s["_id"] for s in seasons} == {"s1"}
        assert {k["_id"] for k in kingdoms} == {"k-1"}
        # the restore leaves the season FROZEN (never re-advanced at once)
        assert all(bool(s.get("frozen")) for s in seasons)
        # the rewind itself was photographed (the undo can be undone)
        assert any(str(doc.get("_id", "")).startswith("archive-") for doc in store.archives)

    asyncio.run(_scenario())
