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
    "phase_setup",
    "rhythm_cycle",
    "rhythm_age",
    "rhythm_season",
    "rhythm_verdict",
    "rhythm_beta",
    "length_line",
    "length_one_week",
    "length_weeks",
    "length_beta",
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
    "menu_title",
    "back_button",
    "civ_placeholder",
    "cat_alliance_add",
    "cat_alliance_remove",
    "cat_treasury",
    "cat_parish",
    "cat_territories",
    "cat_lord",
    "cat_tech",
    "cat_status",
    "civ_add_title",
    "civ_remove_title",
    "civ_status_free",
    "civ_status_hand",
    "civ_status_married",
    "civ_secured",
    "civ_add_done",
    "civ_remove_done",
    "prev_page",
    "next_page",
    "treasury_title",
    "treasury_set",
    "treasury_field",
    "tr_plus5_button",
    "tr_plus1_button",
    "tr_minus1_button",
    "tr_minus5_button",
    "treasury_set_done",
    "value_modal_title",
    "value_modal_label",
    "value_modal_bad",
    "parish_title",
    "parish_tier_set",
    "terr_title",
    "terr_line",
    "terr_shielded",
    "terr_give_button",
    "terr_transfer_button",
    "terr_retire_button",
    "terr_replace_button",
    "terr_shield_button",
    "terr_unshield_button",
    "terr_pick_line",
    "terr_give_pick_line",
    "terr_pick_kingdom_line",
    "terr_none",
    "terr_maps_none",
    "terr_give_done",
    "terr_transfer_done",
    "terr_retire_done",
    "terr_replace_done",
    "terr_shield_done",
    "terr_unshield_done",
    "lord_title",
    "lord_line",
    "lord_role_king",
    "lord_role_lord",
    "lord_none",
    "lord_action_title",
    "lord_budgets_button",
    "lord_unlock_button",
    "lord_lock_button",
    "lord_budgets_done",
    "lord_unlock_done",
    "lord_lock_done",
    "tech_title",
    "tech_line",
    "tech_plus_button",
    "tech_minus_button",
    "tech_done",
    "status_title",
    "status_parish",
    "status_hand",
    "status_secured",
    "status_lord",
    "status_married_none",
    "status_lock_line",
    "status_territories",
    "status_purchases",
    "status_purchases_none",
)


def test_machine_and_distributor_surfaces_are_declared() -> None:
    """The pinned panels + windows appear in conf/views.yaml (#381 ruling 1)."""
    from pathlib import Path

    views = (
        Path(__file__).resolve().parents[1] / "conf" / "views.yaml"
    ).read_text(encoding="utf-8")
    for view_id in (
        "panel:mod:kingdom:console",
        "panel:mod:kingdom:time-machine",
        "panel:mod:kingdom:time-machine:restore",
        "panel:mod:kingdom:distributor",
        "panel:mod:kingdom:distributor:window",
    ):
        assert view_id in views, f"{view_id} must be declared in conf/views.yaml"


def test_machine_and_distributor_strings_parity() -> None:
    """Every machine/distributor string exists in BOTH locales."""
    from botforge.mods.kingdom.cogs.distributor import distributor_strings
    from botforge.mods.kingdom.cogs.time_machine import machine_strings

    for locale in ("fr", "en"):
        machine = machine_strings(locale)
        for key in FR_MACHINE_KEYS:
            assert machine.get(key), f"missing kingdom.machine.{key} in {locale}"
        distributor = distributor_strings(locale)
        for key in FR_DISTRIBUTOR_KEYS:
            assert distributor.get(key), f"missing kingdom.distributor.{key} in {locale}"
        machine["clock_line"].format("01/01 12:00")
        machine["phase_line"].format("setup")
        machine["phase_setup"].format("cycle chaque dimanche 23h30")
        machine["rhythm_cycle"].format("dimanche 23h30")
        machine["rhythm_age"].format("mercredi 00h00")
        machine["rhythm_season"].format("3 semaines")
        machine["rhythm_verdict"].format("dimanche 23h59")
        machine["rhythm_beta"].format("T0+4h", "T0+10h et T0+34h", "T0+52h")
        machine["length_line"].format("3 semaines")
        machine["length_weeks"].format(3)
        machine["length_beta"].format(52)
        machine["offset_line"].format("+2h")
        machine["snapshots_line"].format(3, "a · b · c")
        machine["restore_row"].format("snapshot-manual-1", "01/01 12:00")
        machine["jump_done"].format(1)
        distributor["kingdom_header"].format("Nilrem")
        distributor["points_done"].format("Nilrem", 10)
        distributor["menu_title"].format("Nilrem")
        distributor["civ_add_title"].format("Nilrem", 1, 2)
        distributor["civ_remove_title"].format("Nilrem", 1, 2)
        distributor["civ_status_married"].format("Lord A")
        distributor["treasury_title"].format("Nilrem", 10)
        distributor["treasury_set_done"].format(distributor["treasury_field"], 10)
        distributor["parish_title"].format("Nilrem", 2, "Église")
        distributor["terr_title"].format("Nilrem", 2)
        distributor["terr_line"].format("megarandom", "")
        distributor["terr_pick_line"].format("Nilrem")
        distributor["terr_pick_kingdom_line"].format("megarandom")
        distributor["terr_give_done"].format("megarandom", "Nilrem")
        distributor["lord_title"].format("Nilrem")
        distributor["lord_line"].format("👑 Roi", 1, 0)
        distributor["lord_action_title"].format("Lord A")
        distributor["tech_title"].format("Nilrem")
        distributor["tech_line"].format(2)
        distributor["tech_done"].format("embuscade", "Nilrem", 2)
        distributor["status_title"].format("Nilrem", "approved")
        distributor["status_parish"].format("Chapelle", 4)
        distributor["status_hand"].format(2, "A, B")
        distributor["status_lord"].format("👑", "King A", "Francs", 1, 0, "")
        distributor["status_lock_line"].format("01/01 12:00")
        distributor["status_territories"].format(2, "A, B")
        distributor["status_purchases"].format("embuscade×2")


def test_machine_custom_ids() -> None:
    """Every machine button is a restart-proof DynamicItem with its stable id."""
    from botforge.mods.kingdom.cogs.time_machine import (
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
    from botforge.mods.kingdom.cogs.distributor import (
        DISTRIBUTOR_VIEW_KEY,
        DistributorCatButton,
        DistributorCivPageButton,
        DistributorCivSelect,
        DistributorDestructButton,
        DistributorGiveButton,
        DistributorKingdomSelect,
        DistributorKingdomTargetSelect,
        DistributorLordActionButton,
        DistributorLordSelect,
        DistributorMapSelect,
        DistributorMenuButton,
        DistributorOpenButton,
        DistributorParishButton,
        DistributorTerritoryButton,
        DistributorTerritorySelect,
        DistributorTestKingdomButton,
        DistributorTechSelect,
        DistributorTreasuryButton,
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
    assert DistributorMenuButton("x", "k-nilrem").custom_id == "kingdom:distributor:menu:k-nilrem"
    assert DistributorCatButton("x", "k-nilrem", "treasury").custom_id == (
        "kingdom:distributor:cat:k-nilrem:treasury"
    )
    assert DistributorCivPageButton("x", "k-nilrem", "add", 0, "next").custom_id == (
        "kingdom:distributor:civpage:k-nilrem:add:0:next"
    )
    assert DistributorCivSelect("x", "k-nilrem", "add", 0).custom_id == (
        "kingdom:distributor:civsel:k-nilrem:add:0"
    )
    assert DistributorTreasuryButton("x", "k-nilrem", "p5", None).custom_id == (  # type: ignore[arg-type]
        "kingdom:distributor:tr:k-nilrem:p5"
    )
    assert DistributorParishButton("x", "k-nilrem", 3).custom_id == (
        "kingdom:distributor:par:k-nilrem:3"
    )
    assert DistributorTerritoryButton("x", "k-nilrem", "shield").custom_id == (
        "kingdom:distributor:terr:k-nilrem:shield"
    )
    assert DistributorMapSelect("x", "k-nilrem").custom_id == (
        "kingdom:distributor:mapsel:k-nilrem"
    )
    assert DistributorTerritorySelect("x", "k-nilrem", "retire").custom_id == (
        "kingdom:distributor:tsel:k-nilrem:retire"
    )
    assert DistributorKingdomTargetSelect("x", "k-nilrem", "megarandom").custom_id == (
        "kingdom:distributor:ksel:k-nilrem:megarandom"
    )
    assert DistributorLordSelect("x", "k-nilrem").custom_id == (
        "kingdom:distributor:lsel:k-nilrem"
    )
    assert DistributorLordActionButton("x", "k-nilrem", "123", "budgets").custom_id == (
        "kingdom:distributor:lact:k-nilrem:123:budgets"
    )
    assert DistributorTechSelect("x", "k-nilrem", "plus").custom_id == (
        "kingdom:distributor:techsel:k-nilrem:plus"
    )


def test_machine_and_distributor_panels_build_without_service() -> None:
    """The pinned panels render even with no service wired (holes, not raises)."""
    import asyncio

    from botforge.mods.kingdom.cogs.distributor import build_distributor_panel
    from botforge.mods.kingdom.cogs.time_machine import build_time_machine_panel

    assert asyncio.run(build_time_machine_panel("123")) is not None
    assert asyncio.run(build_distributor_panel("123")) is not None


def test_console_buttons_render_in_the_guild_locale() -> None:
    """Recette 19/11: the panel's console ops read in FR, not the EN defaults."""
    import re

    from botforge.mods.kingdom.cogs.settings_panel import console_buttons
    from botforge.mods.kingdom.cogs.common import strings_by_locale

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
    from botforge.mods.kingdom.cogs.settings_panel import SettingsActionButton

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
    assert "console" in keys


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


def test_settings_pin_falls_back_to_the_declared_salon_name() -> None:
    """settings-pin-fallback-v1: an empty Admin > Paramètres heals by name."""
    from botforge.mods.kingdom.cogs.common import channel_id_by_flattened_name

    class _Channel:
        def __init__(self, name: str, cid: int) -> None:
            self.name = name
            self.id = cid

    class _Guild:
        def __init__(self, channels: list[_Channel]) -> None:
            self.channels = channels

    class _Bot:
        def __init__(self, guild: _Guild | None) -> None:
            self._guild = guild

        def get_guild(self, gid: int) -> _Guild | None:
            return self._guild if int(gid) == 42 else None

    # the accented declared name (the migrated salon) heals the pin
    guild = _Guild(
        [
            _Channel("royaumes", 111),
            _Channel("🛠️ ᴘᴀʀᴀᴍᴇᴛʀᴇs", 222),
        ]
    )
    assert channel_id_by_flattened_name(_Bot(guild), "42", ("console", "parametres", "settings")) == "222"
    # an uncached guild or a miss resolves to nothing (the pin simply waits)
    assert channel_id_by_flattened_name(_Bot(None), "42", ("parametres",)) == ""
    assert channel_id_by_flattened_name(_Bot(guild), "7", ("parametres",)) == ""


def test_official_season_is_three_weeks() -> None:
    """machine-temps-v4: the official season lasts THREE weeks (calibrage)."""
    from botforge.mods.kingdom.config import default_season_config

    assert default_season_config().weeks == 3


def test_machine_rhythm_labels_derive_from_the_active_preset() -> None:
    """machine-temps-v4: cycle/age/verdict labels come from the crons, the
    season length from the ACTIVE preset — never a hardcoded count."""
    from types import SimpleNamespace

    from botforge.mods.kingdom.beta_weekend import BETA_PLAN_OFFSETS
    from botforge.mods.kingdom.cogs.time_machine import (
        season_length_label,
        setup_rhythm_phrase,
        verdict_slot_label,
        weekly_slot_label,
    )
    from botforge.mods.kingdom.config import default_season_config

    config = default_season_config()
    no_beta = SimpleNamespace(beta_name=None)

    # the weekly slot labels mirror the declared crons
    assert weekly_slot_label(config.events.cycle_cron, "fr") == "dimanche 23h30"
    assert weekly_slot_label(config.events.age_cron, "fr") == "mercredi 00h00"
    assert weekly_slot_label(config.events.cycle_cron, "en") == "Sunday 23:30"
    # the verdict label = the cycle slot + 29 minutes (verdict_slot)
    assert verdict_slot_label(config.events.cycle_cron, "fr") == "dimanche 23h59"

    # the official length reads config.weeks
    assert season_length_label("fr", config, no_beta) == "3 semaines"
    assert season_length_label("en", config, no_beta) == "3 weeks"

    # the setup rhythm sentence carries every derived piece
    phrase = setup_rhythm_phrase("fr", config, no_beta)
    assert "cycle chaque dimanche 23h30" in phrase
    assert "âge chaque mercredi 00h00" in phrase
    assert "saison de 3 semaines" in phrase
    assert "verdict le dernier dimanche 23h59" in phrase

    # a beta-armed season reads the compressed plan's real data
    beta = SimpleNamespace(beta_name="now")
    end = int(BETA_PLAN_OFFSETS["end_hours"])
    assert season_length_label("fr", config, beta) == f"{end}h (beta compressée)"
    beta_phrase = setup_rhythm_phrase("fr", config, beta)
    assert "T0+4h" in beta_phrase
    assert "T0+52h" in beta_phrase
    assert "3 semaines" not in beta_phrase


def test_machine_refresher_pass_ensures_only_the_machine_pin() -> None:
    """machine-temps-v4 alias: no spec, no guild — a cheap no-op."""
    import asyncio

    from botforge.discord.static_pins import reset_static_pins
    from botforge.mods.kingdom.cogs.time_machine import (
        MACHINE_VIEW_KEY,
        REFRESH_MINUTES,
        run_machine_refresh_pass,
    )

    assert REFRESH_MINUTES == 5

    class _Bot:
        guilds = []

    # no registered spec + no guild: the pass is a cheap no-op, never a raise
    reset_static_pins()
    assert asyncio.run(run_machine_refresh_pass(_Bot())) == 0
    assert MACHINE_VIEW_KEY == "panel:mod:kingdom:time-machine"


def test_machine_refresher_loop_stays_out_of_the_test_journeys() -> None:
    """The env gate keeps the loop out of the journeys (both vars)."""
    import os

    from botforge.discord.static_pins import reset_static_pins
    from botforge.mods.kingdom.cogs.time_machine import start_machine_refresher

    class _Bot:
        guilds = []

    for var in ("BOTFORGE_KINGDOM_MACHINE_REFRESHER", "BOTFORGE_KINGDOM_PIN_REFRESHER"):
        saved = {k: os.environ.get(k) for k in ("BOTFORGE_KINGDOM_MACHINE_REFRESHER", "BOTFORGE_KINGDOM_PIN_REFRESHER")}
        reset_static_pins()
        os.environ[var] = "off"
        try:
            start_machine_refresher(_Bot())  # must return without starting a loop
        finally:
            for k, v in saved.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v


def test_the_refresher_pass_ensures_every_kingdom_pin() -> None:
    """pins-heal-v1 (Drasah 20/11): « le salon existe mais rien à
    l'intérieur » — a boot pin can be lost to the provisioning's API
    storm; the 5-minute pass re-ensures EVERY pin of the mod's scope,
    so a lost panel heals within one cycle."""
    import asyncio
    from types import SimpleNamespace

    import botforge.discord.static_pins as static_pins
    from botforge.discord.static_pins import reset_static_pins
    from botforge.mods.kingdom.cogs.time_machine import run_mod_pin_refresh_pass

    ensured: list[tuple[str, str]] = []

    async def fake_ensure(bot, spec, guild_id):
        ensured.append((spec.key, guild_id))

    async def fake_resolve_channel(guild_id):
        return "1"

    def _spec(key, scope):
        return SimpleNamespace(key=key, scope=scope, resolve_channel=fake_resolve_channel)

    specs = [
        _spec("panel:mod:kingdom:console", "mod/kingdom"),
        _spec("panel:mod:kingdom:time-machine", "mod/kingdom"),
        _spec("panel:mod:kingdom:distributor", "mod/kingdom"),
        # OTHER scopes never ride the kingdom pass
        _spec("panel:mod:other:thing", "mod/other"),
        _spec("view:aoe2:whatever", "games/aoe2"),
    ]

    bot = SimpleNamespace(guilds=[SimpleNamespace(id=42)])

    reset_static_pins()
    orig = static_pins.registered_static_pins
    static_pins.registered_static_pins = lambda: specs
    orig_ensure = static_pins.ensure_static_pin
    static_pins.ensure_static_pin = fake_ensure
    try:
        touched = asyncio.run(run_mod_pin_refresh_pass(bot))
    finally:
        static_pins.registered_static_pins = orig
        static_pins.ensure_static_pin = orig_ensure

    # every mod/kingdom pin once per guild; the foreign scopes stay out
    assert sorted(ensured) == [
        ("panel:mod:kingdom:console", "42"),
        ("panel:mod:kingdom:distributor", "42"),
        ("panel:mod:kingdom:time-machine", "42"),
    ]
    assert touched == 3
