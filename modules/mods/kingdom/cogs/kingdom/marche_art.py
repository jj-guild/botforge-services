"""The Marché card art resolver (Affaire 24, ported from the reference).

The TCG cards of the reference tree are NOT re-uploaded on this
branch (binary pushes are out of reach), so the resolver is
LOCAL-FIRST: an art file dropped in ``assets/marche/`` (the
perennial home, Drasah can upload the PNGs there any day) wins, and
the fallback streams the very same PNG from the reference branch's
raw URLs (local override, zero behaviour change). A missing PNG is
always cosmetic — the surfaces work with or without the art, and the
network failures degrade quietly.
"""

from __future__ import annotations

import logging
from pathlib import Path

from .civ_crests import (
    MOSAIC_CAPTION_Y,
    _crest_bytes,
    _decode_png_rgba,
    _draw_caption,
    _encode_png_rgba,
    _paste,
    _resample_rgba,
)

logger = logging.getLogger("kingdom.marche_art")

_ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "marche"

_RAW_BASE = (
    "https://raw.githubusercontent.com/jj-guild/botforge-services/"
    "vibe/drasah/main/src/kingdoms/mods/kingdoms/assets/marche"
)

_BANNER_URL = (
    "https://raw.githubusercontent.com/jj-guild/botforge-services/"
    "vibe/drasah/main/march%C3%A9.jpg"
)

# item key → the reference card filename (the raw upload names).
_CARDS: dict[str, str] = {
    "embuscade": "Embuscade.png",
    "traquenard": "Traquenard.png",
    "contre_espionnage": "Contre_Espionnage.png",
    "sabotage": "Sabotage.png",
    "jeu_d_armes": "Jeu_darme.png",
    "explorateur": "Explorateur.png",
    "corruption": "Corruption.png",
    "garde_royale": "Garde_Royale.png",
    "patrouille": "Patrouille.png",
    "mariage_arrange": "Mariage_Arrange.png",
}


def card_filename(item: str) -> str:
    """Return the filename one card travels under on the wire."""
    return _CARDS.get(item, f"{item}.png")


def resolve_card_path(item: str) -> Path | None:
    """Return the LOCAL card path of one market item (None = not local)."""
    name = _CARDS.get(item)
    if not name:
        return None
    candidate = _ASSET_DIR / name
    return candidate if candidate.is_file() else None


def card_url(item: str) -> str | None:
    """Return the render URL of one card.

    A local path never renders — the pinned CV2 message carries no
    attachments, so the art streams from the reference branch's raw
    URLs.
    """
    name = _CARDS.get(item)
    return f"{_RAW_BASE}/{name}" if name else None


def banner_url() -> str:
    """Return the merchant banner URL (the reference branch's root)."""
    return _BANNER_URL


async def card_bytes(item: str) -> bytes | None:
    """Return the PNG bytes of one card.

    A local file wins; the reference raw URL is the fallback, cached
    in memory through the crest seam so a stalled hand never
    re-downloads.
    """
    local = resolve_card_path(item)
    if local is not None:
        try:
            return local.read_bytes()
        except Exception:
            logger.warning("marche: local card read failed (%s)", item, exc_info=True)
    url = card_url(item)
    if url is None:
        return None
    return await _crest_bytes(url)


# ---------------------------------------------------------------------------
# The held-cards MOSAIC (Chambre des comptes) — one composite image, the
# pattern of the civ-crest mosaics: each card downscaled to a small tile
# with its X<stock> counter painted on the caption strip above it.
# ---------------------------------------------------------------------------

HELD_CARD_W = 256
"""Tile width of one held card (x2 of the v4 tiles, readable inline)."""

HELD_CARD_H = 360
"""Tile height: the 728x1024 cards keep their portrait ratio."""

HELD_STRIP_H = 40
"""The X<stock> strip height (the counter paints at 4x)."""

HELD_COLS = 2
"""Two tiles per row (kept readable at Discord's render width)."""

HELD_TILE_H = MOSAIC_CAPTION_Y + HELD_STRIP_H + 2 + HELD_CARD_H
"""Caption strip (margin + strip + gap) + the card art."""

_HELD_CACHE: dict[str, bytes] = {}
_HELD_CACHE_MAX = 32
_HELD_ART_CACHE: dict[str, bytes] = {}


def _held_tile_art(key: str, data: bytes | None) -> bytes | None:
    """Return the cached downscaled art of one card (None = cosmetic)."""
    art = _HELD_ART_CACHE.get(key)
    if art is not None:
        return art
    decoded = None
    if data is not None:
        try:
            decoded = _decode_png_rgba(data)
        except Exception:
            decoded = None
    if decoded is None:
        return None
    art_w, art_h, art_pixels = decoded
    art = _resample_rgba(art_w, art_h, art_pixels, HELD_CARD_W, HELD_CARD_H)
    if len(_HELD_ART_CACHE) >= _HELD_CACHE_MAX:
        _HELD_ART_CACHE.pop(next(iter(_HELD_ART_CACHE)))
    _HELD_ART_CACHE[key] = art
    return art


def _paint_held_tile(
    canvas: bytearray,
    canvas_w: int,
    index: int,
    key: str,
    stock: int,
    art: bytes | None,
) -> None:
    """Paint ONE mosaic tile: the (cached) art plus its X<stock> counter."""
    tile_x = (index % HELD_COLS) * HELD_CARD_W
    tile_y = (index // HELD_COLS) * HELD_TILE_H
    art_y = tile_y + MOSAIC_CAPTION_Y + HELD_STRIP_H + 2
    if art is not None:
        _paste(canvas, canvas_w, tile_x, art_y, HELD_CARD_W, HELD_CARD_H, art)
    _draw_caption(
        canvas,
        canvas_w,
        tile_x,
        tile_y,
        f"X{stock}",
        tile_w=HELD_CARD_W,
        strip_h=HELD_STRIP_H,
        scale=4,
    )


async def held_cards_mosaic_png(held: list[tuple[str, int]]) -> bytes | None:
    """Compose the held cards into ONE mosaic PNG (None = empty hand).

    ``held`` pairs each card key with its REMAINING stock; duplicates
    collapse to their first entry. Every tile carries the card's
    downscaled art plus its X<stock> counter on the caption strip. A
    missing or undecodable card keeps its tile (caption only) — the
    mosaic always goes out complete, and the encoded PNG is cached
    per fingerprint (an unchanged hand replays the previous bytes).
    """
    tiles: list[tuple[str, int]] = []
    seen: set[str] = set()
    for key, stock in held or ():
        card = str(key).strip()
        if not card or card in seen:
            continue
        seen.add(card)
        tiles.append((card, max(1, int(stock or 1))))
    if not tiles:
        return None
    fingerprint = "ledger-cards:" + ";".join(f"{k}={s}" for k, s in tiles)
    cached = _HELD_CACHE.get(fingerprint)
    if cached is not None:
        return cached
    rows = (len(tiles) + HELD_COLS - 1) // HELD_COLS
    canvas_w = HELD_COLS * HELD_CARD_W
    canvas_h = rows * HELD_TILE_H
    canvas = bytearray(canvas_w * canvas_h * 4)
    for index, (key, stock) in enumerate(tiles):
        if key not in _HELD_ART_CACHE:
            _held_tile_art(key, await card_bytes(key))
        _paint_held_tile(canvas, canvas_w, index, key, stock, _HELD_ART_CACHE.get(key))
    png = _encode_png_rgba(canvas_w, canvas_h, bytes(canvas))
    if len(_HELD_CACHE) >= _HELD_CACHE_MAX:
        _HELD_CACHE.pop(next(iter(_HELD_CACHE)))
    _HELD_CACHE[fingerprint] = png
    return png
