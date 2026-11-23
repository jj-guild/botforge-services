"""R9 — a mod's view ids follow the naming contract.

Every view id a mod declares (``modules/mods/<name>/conf/views.yaml``)
or renders (string literals in its cogs) starts with ``panel:mod:<name>``
or ``menu:mod:<name>`` and belongs to its own mod. The legacy
``view:mod:`` / ``surface:mod:`` prefixes are drift: the registry and
the router speak ``panel:``/``menu:`` (the mod console is
``panel:mod:<name>:admin:console``, auto-declared by the SDK).
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
MODS = REPO / "modules" / "mods"

_ALLOWED = re.compile(r"^(panel|menu):mod:[a-z0-9_-]+(:[a-z0-9_-]+)*$")
_LEGACY_LITERAL = re.compile(r'["\'](?:view|surface):mod:')


def _mod_dirs() -> list[Path]:
    """Every modular mod shipping a conf/views.yaml."""
    if not MODS.is_dir():
        return []
    return sorted(p for p in MODS.iterdir() if (p / "conf" / "views.yaml").is_file())


def test_every_declared_mod_view_id_matches_the_contract() -> None:
    """Declared ids: panel:mod:<name>:… or menu:mod:<name>:… — own mod only."""
    offenders: list[str] = []
    for mod_dir in _mod_dirs():
        name = mod_dir.name
        data = yaml.safe_load((mod_dir / "conf" / "views.yaml").read_text(encoding="utf-8")) or {}
        for view_id in (data.get("views") or {}):
            view_id = str(view_id)
            own_mod = f":mod:{name}:" in view_id or view_id == f"menu:mod:{name}"
            if not _ALLOWED.match(view_id) or not own_mod:
                offenders.append(f"{name}: {view_id}")
    assert not offenders, (
        "mod view ids must be panel:mod:<name>:… / menu:mod:<name>:… of their OWN mod — "
        + "; ".join(offenders)
    )


def test_no_legacy_view_or_surface_prefix_in_mod_code() -> None:
    """No view:/surface: literal left in a mod's python — panel:/menu: only."""
    offenders: list[str] = []
    for mod_dir in _mod_dirs():
        for path in sorted(mod_dir.rglob("*.py")):
            if "__pycache__" in str(path):
                continue
            for match in _LEGACY_LITERAL.finditer(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(REPO)}:{match.start()}: {match.group(0)}…")
    assert not offenders, (
        "legacy view:/surface: id literals in mod code — use panel:mod:<name>:/menu:mod:<name>: — "
        + "; ".join(offenders[:10])
    )
