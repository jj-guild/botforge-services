"""The ADMIN BYPASS seam (P4.1 port of the admin-debug-v1 toolkit).

Drasah's testing surface: a process-wide flag that lets the REAL
player buttons run their full normal flow past the gate checks (age,
slot, cooldown, budget, locks, parish tier). Everything is logged —
every skipped gate names itself, the test sessions stay auditable.

The full /kingdoms-admin debug subgroup (the surgical-mutation toolkit)
is P6 admin tooling; the services import only ``bypass_guard`` from
here, so the seam ships alone (it was referenced by the P3
``upgrade_parish`` budget check — the import previously pointed at a
module that did not exist yet on this base).
"""

from __future__ import annotations

import logging

logger = logging.getLogger("kingdom.admin_debug")

_BYPASS = False


def admin_bypass_enabled() -> bool:
    """Whether the player-button gate checks are bypassed (test mode)."""
    return _BYPASS


def set_admin_bypass(enabled: bool, *, source: str = "runtime") -> None:
    """Flip the ADMIN BYPASS flag (logged — test vs production marker)."""
    global _BYPASS
    if _BYPASS != bool(enabled):
        logger.warning(
            "kingdom ADMIN BYPASS %s by %s",
            "armed" if enabled else "disarmed",
            source,
        )
    _BYPASS = bool(enabled)


def bypass_guard(label: str) -> bool:
    """Log one ADMIN BYPASS when a gate check is being skipped.

    Returns True when the caller must SKIP its raise (the bypass is
    active): every skipped gate names itself in the logs — the test
    sessions stay auditable.
    """
    if not _BYPASS:
        return False
    logger.warning("kingdom ADMIN BYPASS: gate skipped — %s", label)
    return True


__all__ = ["admin_bypass_enabled", "bypass_guard", "set_admin_bypass"]
