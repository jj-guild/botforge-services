# Arena — the permanent example mod

Always on: a global enrollment (no season), a validation through the
admin channel's messages, suspend/resume, the section's Synchroniser.

- **Declaration**: `mod.yaml` — channel groups (public + admin-only),
  an announce channel, the player/admin roles, the enrollment settings
  (`manual` + `requires_profile`).
- **Code**: `src/arena/__init__.py` — ONE `register` line wiring the
  platform's generic surfaces (`kingdoms.discord.mod_surfaces`).
- **Surfaces**: `/arena` (the player panel: s'inscrire, se désinscrire,
  les inscrits), the admin channel validation (Accepter/Refuser on the
  candidate's message), the admin panel (suspendre/reprendre,
  synchroniser).
- **Tests**: `tests/test_arena.py`.

Reference: kingdoms-services#267 (chantier 4).
