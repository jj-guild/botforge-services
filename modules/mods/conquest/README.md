# Conquest — the seasonal example mod

Runs as a season: a per-season enrollment (the candidates apply
against the active season), a map pool attachable to each season
(rotation = a new season with another pool), inscriptions opening 7
days before the season's start.

- **Declaration**: `mod.yaml` — channel groups (royaumes, conscription,
  admin-only), an announce channel, the per-season player role, the
  enrollment settings (`manual` + `opens_before_start: 7d` +
  `requires_profile`).
- **Code**: `src/conquest/__init__.py` — ONE `register` line wiring the
  platform's generic surfaces (`kingdoms.discord.mod_surfaces`).
- **Surfaces**: `/conquest` (the player panel), the admin channel
  validation, the admin panel (suspendre/reprendre, nouvelle saison /
  démarrer / terminer, synchroniser).
- **Tests**: `tests/test_conquest.py`.

Reference: kingdoms-services#267 (chantier 4).
