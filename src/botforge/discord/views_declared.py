"""The platform's declared views — loaded from ``config/views.yaml``.

The YAML is the single source of truth (docs/DEVELOPMENT/VIEWS.md in
the botforge repo renders it for humans): every menu, panel, button
and navigation target is declared there, and this loader turns it
into the runtime registry. Adding a menu is YAML lines, zero code —
the menu builder, the pins and the router all render from the
registry.

An action button (``action: <action-id>``) references a behavior the
code wires at boot (``wire_action``); an unwired action renders
disabled, never dead.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from botforge.discord.views_registry import (
    KIND_MENU,
    KIND_PANEL,
    KIND_SURFACE,
    ButtonDecl,
    ViewDecl,
    register_view,
)

logger = logging.getLogger("botforge.views.declared")

VIEWS_CONFIG = Path("config/views.yaml")


def load_views_config(config_dir: Path | str | None = None) -> dict[str, Any]:
    """Read and parse the views YAML (anchors and aliases resolve here)."""
    path = Path(config_dir) / "views.yaml" if config_dir else VIEWS_CONFIG
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or not isinstance(data.get("views"), dict):
        raise ValueError(f"{path}: the views config must carry a 'views' mapping")
    views: dict[str, Any] = data["views"]
    return views


def _parse_button(view_id: str, raw: dict[str, Any]) -> ButtonDecl:
    """Turn one YAML button entry into a ButtonDecl (fail loudly)."""
    if not isinstance(raw, dict):
        raise ValueError(f"views config: {view_id}: a button must be a mapping, got {raw!r}")
    button = ButtonDecl(
        target=str(raw.get("target", "") or ""),
        label_key=str(raw.get("label", "") or ""),
        emoji=str(raw.get("emoji", "") or ""),
        admin=bool(raw.get("admin", False)),
        sync=bool(raw.get("sync", False)),
        disabled=bool(raw.get("disabled", False)),
        action=str(raw.get("action", "") or ""),
    )
    return button


def declare_views_from_config(config_dir: Path | str | None = None) -> None:
    """Load every declared view into the registry.

    The platform's ``views.yaml`` first, then every enabled mod's own
    ``config/mods/<mod>/views.yaml`` — a mod's navigation lives with
    the mod (botforge#179: a mod's files never scatter), and the
    merged registry validates cross-references both ways.
    """
    views = load_views_config(config_dir)
    views.update(_load_mod_views(config_dir))
    for view_id, raw in views.items():
        if not isinstance(raw, dict):
            raise ValueError(f"views config: {view_id}: a view must be a mapping")
        kind = str(raw.get("kind", ""))
        if kind not in (KIND_MENU, KIND_PANEL, KIND_SURFACE):
            raise ValueError(f"views config: {view_id}: kind must be menu, panel or surface, got {kind!r}")
        buttons = tuple(_parse_button(view_id, b) for b in raw.get("buttons", []) or ())
        if kind == KIND_SURFACE and buttons:
            raise ValueError(
                f"views config: {view_id}: a surface never carries buttons — "
                "it anchors, it does not navigate"
            )
        register_view(
            ViewDecl(
                id=str(view_id),
                kind=kind,
                scope=str(raw.get("scope", "") or ""),
                title_emoji=str(raw.get("title_emoji", "") or ""),
                admin_surface=bool(raw.get("admin_surface", False)),
                buttons=buttons,
            )
        )
    logger.info("VIEWS declared from config: %d views", len(views))


def declare_platform_views(config_dir: Path | str | None = None) -> None:
    """Declare every platform view (compatibility name, boot-time)."""
    declare_views_from_config(config_dir)




def _load_mod_views(config_dir: Path | str | None = None) -> dict[str, Any]:
    """Merge every enabled mod's views declaration (best-effort each).

    A mod ships ``config/mods/<mod>/views.yaml`` next to its main
    declaration; a missing file is normal (a mod without its own
    navigation), a broken one fails loudly (the registry is the
    single navigation source — a half-loaded menu tree is a bug).
    """
    from botforge.core.services.mod_layout import ModLayout, default_repo_root
    from botforge.core.services.mod_registry import load_mod_definitions

    base = Path(config_dir) if config_dir else VIEWS_CONFIG.parent
    repo_root = default_repo_root()
    try:
        definitions = load_mod_definitions(base, repo_root=repo_root)
    except Exception:
        logger.warning("VIEWS: mod declarations unreadable — mod views skipped", exc_info=True)
        return {}
    layouts: dict[str, ModLayout] = {}
    if repo_root is not None:
        from botforge.core.services.mod_layout import discover_mods

        layouts = discover_mods(Path(repo_root))
    merged: dict[str, Any] = {}
    for name in definitions:
        # the legacy declarations live flat (config/mods/<mod>.yaml) and a
        # legacy mod's views ride <mod>.views.yaml next to it; the
        # modular §7 mods ship their views in their OWN conf directory
        # (botforge#179/#221: a mod's files never scatter) —
        # conf/views.yaml next to the declaration.
        candidates = [base / "mods" / f"{name}.views.yaml"]
        layout = layouts.get(name)
        if layout is not None:
            candidates.insert(0, layout.declaration.parent / "views.yaml")
        mod_views = next((path for path in candidates if path.is_file()), None)
        if mod_views is None:
            continue
        with open(mod_views, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if data is None:
            continue
        if not isinstance(data, dict) or not isinstance(data.get("views"), dict):
            raise ValueError(f"{mod_views}: a mod views config must carry a 'views' mapping")
        # R9: a mod's view ids follow the naming contract —
        # panel:mod:<name>:… / menu:mod:<name>:… of its OWN mod. A legacy
        # view:/surface: id is drift: it is skipped (loudly), never
        # registered — the architecture test pins the rule.
        contract = re.compile(rf"^(?:panel|menu):mod:{re.escape(str(name))}(?::|$)")
        accepted = 0
        for view_id, spec in data["views"].items():
            if not contract.match(str(view_id)):
                logger.error(
                    "VIEWS: mod %s declares a non-contract id %r — skipped "
                    "(a mod's view ids are panel:mod:%s:… or menu:mod:%s:…)",
                    name, view_id, name, name,
                )
                continue
            merged[str(view_id)] = spec
            accepted += 1
        logger.info("VIEWS declared by mod %s: %d views", name, accepted)
    return merged


__all__ = ["declare_platform_views", "declare_views_from_config", "load_views_config"]
