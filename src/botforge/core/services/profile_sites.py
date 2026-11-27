"""Profile sites registry: typed URL formatting and parsing, per game.

Every external site that hosts a player's public profile page
(aoe2insights, aoe2.GG, ageofempires.com, ...) is declared once in
``config/games/<game_key>/profile_sites.yaml`` — never hard-coded, never
in the translations. This module owns the typed access:

- ``ProfileSite`` — one declared site (label, id kind, url template,
  parse pattern);
- ``ProfileSitesRegistry`` — loads the per-game declarations, builds
  every site's URL from a profile id (``format_url``), and extracts a
  profile id from a pasted URL (``parse_url``) so the profile-add flow
  accepts any known site's page.

Adding a site is a config change, never a deploy: the profile view,
the home accounts and the admin surfaces read this registry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ID_KIND_RELIC = "relic_id"
ID_KIND_SITE = "site_id"


@dataclass(frozen=True, slots=True)
class ProfileSite:
    """One declared profile site for a game."""

    key: str
    label: str
    id_kind: str
    url_template: str
    parse_pattern: re.Pattern[str]

    def format_url(self, profile_id: str) -> str:
        """Build the site's profile page URL from the platform profile id.

        The template's ``{relic_id}`` placeholder carries the platform's
        profile id; ``{profile_id}`` is accepted as an alias so templates
        stay readable. A site keyed by its own user id (``site_id``)
        cannot format from a relic id — it returns empty and the caller
        falls back to the other sites.
        """
        if self.id_kind == ID_KIND_SITE:
            return ""
        return self.url_template.format(relic_id=profile_id, profile_id=profile_id)

    def parse_url(self, url: str) -> str | None:
        """Extract the profile id a pasted URL of this site carries.

        Returns the id as a string, or None when the URL is not one of
        this site's profile pages.
        """
        match = self.parse_pattern.search(url)
        if match is None:
            return None
        return match.group("id")


class ProfileSitesRegistry:
    """The per-game registry of profile sites (config-loaded)."""

    def __init__(self) -> None:
        """Start empty; the games load their declarations on demand."""
        self._games: dict[str, dict[str, ProfileSite]] = {}
        self._defaults: dict[str, str] = {}

    def load_game(self, game_key: str, config_path: Path) -> None:
        """Load one game's site declarations from its YAML file."""
        sites: dict[str, ProfileSite] = {}
        default = ""
        if config_path.is_file():
            data = yaml.safe_load(config_path.read_text()) or {}
            if isinstance(data, dict):
                default = str(data.get("default_site", ""))
                for key, raw in (data.get("sites") or {}).items():
                    if not isinstance(raw, dict):
                        continue
                    pattern = str(raw.get("parse", ""))
                    try:
                        compiled = re.compile(pattern) if pattern else re.compile(r"$^")
                    except re.error:
                        continue
                    sites[str(key)] = ProfileSite(
                        key=str(key),
                        label=str(raw.get("label", key)),
                        id_kind=str(raw.get("id_kind", ID_KIND_RELIC)),
                        url_template=str(raw.get("url_template", "")),
                        parse_pattern=compiled,
                    )
        self._games[game_key] = sites
        if default in sites:
            self._defaults[game_key] = default
        elif sites:
            self._defaults[game_key] = next(iter(sites))

    def sites_for(self, game_key: str) -> list[ProfileSite]:
        """List a game's declared sites, in declaration order."""
        return list(self._games.get(game_key, {}).values())

    def default_site(self, game_key: str) -> ProfileSite | None:
        """Return the game's default site (declaration order fallback)."""
        key = self._defaults.get(game_key)
        if key is None:
            return None
        return self._games.get(game_key, {}).get(key)

    def site(self, game_key: str, site_key: str) -> ProfileSite | None:
        """Return one declared site; None when undeclared."""
        return self._games.get(game_key, {}).get(site_key)

    def format_url(self, game_key: str, profile_id: str, site_key: str = "") -> str:
        """Build the profile page URL on the chosen (or default) site."""
        site = self.site(game_key, site_key) if site_key else self.default_site(game_key)
        if site is None:
            return ""
        return site.format_url(profile_id)

    def format_all(self, game_key: str, profile_id: str) -> list[tuple[str, str, str]]:
        """Build every site's URL: (site_key, label, url) triples."""
        return [
            (site.key, site.label, site.format_url(profile_id))
            for site in self.sites_for(game_key)
            if site.format_url(profile_id)
        ]

    def parse_url(self, game_key: str, url: str) -> tuple[str, str] | None:
        """Extract (site_key, profile_id) from a pasted URL of any site."""
        for site in self.sites_for(game_key):
            profile_id = site.parse_url(url)
            if profile_id is not None:
                return site.key, profile_id
        return None


_REGISTRY = ProfileSitesRegistry()

# the per-game profile_link_template (config/games/<g>/game.yaml) -
# ONE hard place per game (owner 2026-11-27): every surface that
# shows a player's pseudo renders it, the unknown players fall back
# to it
_LINK_TEMPLATES: dict[str, str] = {}
_LABEL_RE = re.compile(r"^\[[^\]]*\]")
_URL_RE = re.compile(r"\]\(([^)]*)\)")


def profile_link_template(game_key: str) -> str:
    """Return the game's declared player-link template ('' undeclared).

    The template lives in ``config/games/<game_key>/game.yaml`` under
    ``profile_link_template`` - a full markdown link whose vars are
    the profile model's fields, prefixed (``{profile_id}``,
    ``{profile_name}``, ...).
    """
    if game_key in _LINK_TEMPLATES:
        return _LINK_TEMPLATES[game_key]
    template = ""
    path = _default_config_path(game_key).with_name("game.yaml")
    if path.is_file():
        try:
            data = yaml.safe_load(path.read_text()) or {}
            if isinstance(data, dict):
                template = str(data.get("profile_link_template") or "")
        except Exception:
            template = ""
    _LINK_TEMPLATES[game_key] = template
    return template


class _SafeVars(dict[str, str]):
    """A format mapping that renders the undeclared vars empty."""

    def __missing__(self, key: str) -> str:
        return ""


def format_profile_link(game_key: str, model: Any, label: str = "") -> str:
    """Render the game's player link from its profile model.

    Every model field injects prefixed (``profile_id``,
    ``profile_name``, ... - owner 2026-11-27: "injecte l'objet du
    model et préfixe les vars, ça sera plus évolutif"). A ``label``
    overrides the template's own label when the caller owns the
    display name; without one the template's label renders as
    declared.
    """
    template = profile_link_template(game_key)
    if not template:
        return ""
    fields: dict[str, str] = {}
    for key, value in dict(model or {}).items():
        # the model may already speak the prefixed names (profile_id)
        # or the bare ones (id) - both normalize to the prefixed vars
        bare = key[8:] if key.startswith("profile_") else key
        fields[f"profile_{bare}"] = "" if value is None else str(value)
    try:
        rendered = template.format_map(_SafeVars(fields))
    except Exception:
        return ""
    if label:
        rendered = _LABEL_RE.sub(lambda _m: f"[{label}]", rendered, count=1)
    return rendered


def format_profile_link_url(game_key: str, model: Any) -> str:
    """Extract the rendered template's URL (the href, label aside)."""
    rendered = format_profile_link(game_key, model)
    if not rendered:
        return ""
    match = _URL_RE.search(rendered)
    return match.group(1) if match else ""


def profile_sites_registry() -> ProfileSitesRegistry:
    """Return the process-wide registry, loading the known games once."""
    if not _REGISTRY.sites_for("aoe2"):
        _REGISTRY.load_game("aoe2", _default_config_path("aoe2"))
    return _REGISTRY


def _default_config_path(game_key: str) -> Path:
    """Resolve the game's config file from the repo layout."""
    return Path(__file__).resolve().parents[4] / "config" / "games" / game_key / "profile_sites.yaml"


def reset_registry_for_tests(config_dir: Path | None = None) -> None:
    """Reload the registry from an explicit config dir (tests)."""
    global _REGISTRY
    _REGISTRY = ProfileSitesRegistry()
    if config_dir is not None:
        base = config_dir / "games"
        for game_dir in base.iterdir() if base.is_dir() else []:
            if game_dir.is_dir():
                _REGISTRY.load_game(game_dir.name, game_dir / "profile_sites.yaml")


def format_profile_url(game_key: str, profile_id: str, site_key: str = "") -> str:
    """Format the profile page URL on the chosen (or default) site."""
    return profile_sites_registry().format_url(game_key, profile_id, site_key)


def parse_profile_url(game_key: str, url: str) -> tuple[str, str] | None:
    """Parse a pasted URL of any known site into (site_key, profile_id)."""
    return profile_sites_registry().parse_url(game_key, url)


def any_dict() -> dict[str, Any]:
    """Expose the registry's internal state (diagnostics, admin views)."""
    return {game: {k: s.label for k, s in sites.items()} for game, sites in _REGISTRY._games.items()}
