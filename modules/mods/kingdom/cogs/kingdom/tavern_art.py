"""Kingdom mod — the 🍺 Taverne artwork resolver (taverne-v1, Drasah 28/11).

The three Taverne visuals live on the REFERENCE branch
(``vibe/drasah/main``) under ``assets/taverne/`` — the port serves
them as MediaGallery URLs. The resolver honours the reference's README
contract: canonical names first (``taverne-entree.png``…), uploaded
aliases (the raw image-generation file names) as fallback — the
canonical name wins as soon as the file is renamed by hand.
"""

from __future__ import annotations

import os
from pathlib import Path

_ASSET_DIR = Path(__file__).resolve().parent.parent / "assets" / "taverne"

_RAW_BASE = (
    "https://raw.githubusercontent.com/jj-guild/botforge-services/"
    "vibe/drasah/main/src/kingdoms/mods/kingdoms/assets/taverne"
)

_CANONICAL: dict[str, str] = {
    "entree": "taverne-entree.png",
    "comptoir": "taverne-comptoir.png",
    "mercenaire": "taverne-mercenaire.png",
}

# The uploaded aliases (raw image-generation file names of the
# reference branch) — the raw URL serves them as-is.
_FALLBACKS: dict[str, tuple[str, ...]] = {
    "entree": ("image.png",),
    "comptoir": ("9c1b722d-2dba-4783-99dc-ee977bbf2357.jpg",),
    "mercenaire": ("fd9e7f9c-5c61-46c9-aae2-67e0ba606757.jpg",),
}


def resolve_art(which: str) -> Path | None:
    """Return a LOCAL artwork path when one exists (canonical first)."""
    if os.environ.get("BOTFORGE_KINGDOM_TAVERN_ART", "").lower() in {"off", "0", "false"}:
        return None
    for name in (_CANONICAL.get(which, ""), *_FALLBACKS.get(which, ())):
        if not name:
            continue
        candidate = _ASSET_DIR / name
        if candidate.is_file():
            return candidate
    return None


def taverne_art_url(which: str) -> str | None:
    """The artwork's URL (the reference branch's raw URL — the pinned
    panels render MediaGallery URLs; ``resolve_art`` stays ready for
    the day the art lands in this repo and panels carry files)."""
    if os.environ.get("BOTFORGE_KINGDOM_TAVERN_ART", "").lower() in {"off", "0", "false"}:
        return None
    if resolve_art(which) is not None:
        # A local copy exists — serve the canonical remote name so the
        # rename-by-hand contract holds on both sides.
        return f"{_RAW_BASE}/{_CANONICAL.get(which, '')}"
    for name in (_CANONICAL.get(which, ""), *_FALLBACKS.get(which, ())):
        if not name:
            continue
        return f"{_RAW_BASE}/{name}"
    return None


def taverne_art_item(which: str) -> "discord.MediaGalleryItem | None":
    """One MediaGallery item for the artwork, or None when unknown."""
    import discord

    url = taverne_art_url(which)
    if url is None:
        return None
    return discord.MediaGalleryItem(url)


__all__ = ["resolve_art", "taverne_art_item", "taverne_art_url"]
