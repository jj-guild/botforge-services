"""Boot-registration guard — register-crash-v1 (Drasah 20/11).

The incident: an import placed BELOW its first use made ``register()``
die on UnboundLocalError at the seigneurerie pin, and the boot swallowed
it — every pin declared AFTER the crash (console, time-machine,
distributor, market, validation) silently never registered, and the
admin salons stayed empty forever (no refresher, no reset pass, no
diagnostic could see a pin the bot does not know). This guard executes
the REAL register() on a fake bot and fails loudly the moment one
declared pin goes missing — the class of bug can never reach an image
again.
"""

from __future__ import annotations

_EVERY_DECLARED_PIN = {
    "panel:mod:kingdom:attack",
    "panel:mod:kingdom:apply",
    "panel:mod:kingdom:register",
    "panel:mod:kingdom:seigneurerie",
    "panel:mod:kingdom:console",
    "panel:mod:kingdom:time-machine",
    "panel:mod:kingdom:distributor",
    "panel:mod:kingdom:validation",
    "panel:mod:kingdom:market",
}


def test_boot_register_lands_every_declared_pin() -> None:
    from botforge.discord.static_pins import registered_static_pins

    from botforge.mods.kingdom.cogs import register

    class _BootBot:
        message_registry = None
        guilds: list[object] = []

    register(_BootBot(), None)

    keys = {
        spec.key
        for spec in registered_static_pins()
        if str(spec.scope or "").startswith("mod/kingdom")
    }
    missing = _EVERY_DECLARED_PIN - keys
    assert not missing, (
        "register() died mid-flow — these pins never registered "
        f"(an import below its use? a wiring crash?): {sorted(missing)}"
    )


def test_boot_register_lands_every_dynamic_item() -> None:
    """Affaire 21bis (« n'a pas répondu à temps ») : a DynamicItem the
    register loop never lands is a button Discord clicks into the
    void — the drawer rendered it, but the bot had no handler. The
    guard executes the REAL register() on a recording bot and fails
    loudly the moment one declared dynamic class goes missing (the
    dynamic items live in setup_hook, the boot's second pass)."""
    from botforge.mods.kingdom.cogs import setup_hook
    from botforge.mods.kingdom.cogs.decisions import DecisionActButton, DecisionOpenButton

    landed: list[object] = []

    class _RecordingBot:
        def add_dynamic_items(self, item: object) -> None:
            landed.append(item)

    setup_hook(_RecordingBot())
    missing = {DecisionOpenButton, DecisionActButton} - set(landed)
    assert not missing, (
        "register() never landed these dynamic items — their clicks "
        f"silently die ('n'a pas répondu à temps'): {sorted(c.__name__ for c in missing)}"
    )
