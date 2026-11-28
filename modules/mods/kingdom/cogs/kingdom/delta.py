"""delta-lab-v1 (Drasah 28/11) — le 🌱 Delta, le labo BÊTA de l'atelier.

La décision (Drasah 28/11) : un tiroir DANS les paramètres, à droite du
bouton « 🛠️ Serveur », qui porte les features EN INCUBATION — et la
règle d'or : **Delta n'existe qu'en bêta**. Une saison classique ne
voit jamais le bouton (le rendu le gomme), un vieux message cliqué
après le retour au classique reçoit le refus (le clic re-vérifie).
Rien de Delta ne touche un geste officiel : si une feature déplaît,
l'officiel n'a jamais bougé ; si elle convainc, elle « diplôme ».

Les trois features v1 (les décisions verbatim de la discussion) :

1. **🧪 Fin de saison (nouveau flux)** — le flux qui faisait peur :
   le clic photographie l'équipage ENGAGÉ (roi + membres + coquilles)
   AVANT la fermeture (bouclage-rembarquement : la fin éjecte, la photo
   retient), joue la procédure de fin OFFICIELLE (le même seam
   ``_end_season``), puis pose la CÉRÉMONIE dans 🌍 géopolitique :
   verdict + podium + les DEUX portes de l'après — « 🔄 Boucler »
   (relance, la photo rembarque l'équipage) et « 🗄️ Archiver la
   saison » (palmarès déjà au Panthéon, salons de saison vierges).
   L'accusé éphémère part AVANT le travail (l'incident du spam), la
   cérémonie est une donnée d'état (un clic après un redémarrage
   retrouve sa photo).

2. **🪑 Réembarquer les royaumes** — la réparation isolée : chaque
   coquille en veille (standby, jamais archivée) rejoue la chaîne
   d'admission (``_reseat_one``, le même moteur que la boucle) dans
   la saison courante.

3. **👁️ La galerie des messages** — voir sans jouer : chaque message
   que Kingdom peut produire, rendu en éphémère avec des données
   d'exemple (le VRAI code de rendu, pas une capture). La templatisation
   (#395) à l'œil nu : un template + des paramètres, jamais de rendu
   ad hoc — et la fondation des annonces (#396).

Tout est DÉCLARÉ (views.yaml) et les ids vivent dans le namespace
``kingdom:delta:`` — jamais une collision avec les surfaces officielles
(la leçon de double-dispatch).
"""

from __future__ import annotations

import logging
import re
from typing import Any

import discord

from .common import mod_catalog, open_unique_ephemeral, strings_by_locale, surface, wiring

logger = logging.getLogger("kingdom.delta")

_NS = "kingdom:delta"
DELTA_WINDOW_KEY = "panel:mod:kingdom:admin:delta"
DELTA_END_VIEW_KEY = "panel:mod:kingdom:delta:end"
DELTA_GALLERY_VIEW_KEY = "panel:mod:kingdom:delta:gallery"
CEREMONY_STATE_KEY = "delta:end-ceremony"
CEREMONY_TTL_S = 7 * 24 * 3600


def delta_strings(locale: str) -> dict[str, str]:
    """The delta surfaces' strings (``kingdom.delta`` catalog section)."""
    return dict(mod_catalog().section("kingdom.delta", str(locale)[:2]))


def _locale_of(interaction: discord.Interaction) -> str:
    from .common import locale_of

    return locale_of(interaction)


def _state_cache(bot: Any) -> Any | None:
    """The mod's state door, degraded to None (never a raise)."""
    from botforge.core.services.mod_storage import ModStateCache

    state_service = getattr(bot, "state_service", None)
    return ModStateCache(state_service, "kingdom") if state_service is not None else None


# ---------------------------------------------------------------------------
# The beta gate — Delta only breathes in a beta season
# ---------------------------------------------------------------------------


async def delta_visible() -> bool:
    """Whether the Delta drawer exists at all (a BETA season runs).

    The ruling (Drasah 28/11) : « delta ne doit pas être disponible en
    version classique » — la nav le gomme au rendu, et le clic d'un
    vieux message re-vérifie ici.
    """
    from .camp_beta import beta_armed

    return await beta_armed()


async def _podium_snapshot(stack: Any) -> dict[str, Any]:
    """The territory podium as pure data (a capture, never a mutation).

    The engine's own end report shape (``winner_name`` + territories),
    read BEFORE the reset — the ceremony survives the wipe.
    """
    kingdoms = await stack.kingdoms.kingdoms()
    names = {
        str(kingdom.id): str(kingdom.name)
        for kingdom in kingdoms
        if not getattr(kingdom, "is_gaia", False)
    }
    counts: dict[str, int] = {}
    try:
        raw = await stack.territories.territory_count_by_kingdom()
        counts = {
            names.get(str(kid), str(kid)): int(count or 0)
            for kid, count in dict(raw or {}).items()
            if str(kid) in names
        }
    except Exception:  # noqa: BLE001 — a read, never a crash
        logger.warning("kingdom: the delta podium read failed", exc_info=True)
    ordered = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    winner = ordered[0][0] if ordered and (len(ordered) < 2 or ordered[0][1] > ordered[1][1]) else None
    return {"winner_name": winner, "territories": counts, "showmatch": winner is None}


async def read_ceremony(bot: Any) -> dict[str, Any] | None:
    """The stored end-ceremony record (None when nothing is pending)."""
    cache = _state_cache(bot)
    if cache is None:
        return None
    try:
        record = await cache.get(CEREMONY_STATE_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: the ceremony record read failed", exc_info=True)
        return None
    return dict(record) if isinstance(record, dict) and record else None


async def _store_ceremony(bot: Any, record: dict[str, Any]) -> bool:
    cache = _state_cache(bot)
    if cache is None:
        return False
    try:
        return bool(await cache.set(CEREMONY_STATE_KEY, record, ttl=CEREMONY_TTL_S))
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: the ceremony record write failed", exc_info=True)
        return False


async def _clear_ceremony(bot: Any) -> None:
    cache = _state_cache(bot)
    if cache is None:
        return
    try:
        await cache.delete(CEREMONY_STATE_KEY)
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: the ceremony record clear failed", exc_info=True)


# ---------------------------------------------------------------------------
# The drawer — Delta's front door (an ephemeral settings drawer)
# ---------------------------------------------------------------------------


async def delta_drawer(strings: dict[str, str], bot: Any | None, guild_id: str) -> Any:
    """Build the 🌱 Delta drawer (ephemeral, admin, beta-only)."""
    dstrings = delta_strings(
        "fr"  # the drawer reads the guild locale below when a bot exists
    )
    locale = "fr"
    if bot is not None and guild_id:
        try:
            from .panel import _guild_locale

            locale = await _guild_locale(guild_id)
            dstrings = delta_strings(locale)
        except Exception:  # noqa: BLE001 — the drawer never crashes
            logger.warning("kingdom: the delta drawer locale read failed", exc_info=True)
    if not await delta_visible():
        # an OLD pinned console clicked after the return to classic —
        # the button was already gone at render, the click says why
        container = discord.ui.Container(
            discord.ui.TextDisplay(f"# {dstrings['delta_title']}"),
            discord.ui.TextDisplay(str(dstrings["delta_classic_refused"])),
        )
        return surface(DELTA_WINDOW_KEY, container)
    rows = discord.ui.ActionRow()
    rows.add_item(
        DeltaActionButton("end-flow", str(dstrings["delta_end_button"]), discord.ButtonStyle.danger).item
    )
    rows.add_item(
        DeltaActionButton("reseat", str(dstrings["delta_reseat_button"]), discord.ButtonStyle.success).item
    )
    gallery_row = discord.ui.ActionRow()
    gallery_row.add_item(DeltaGallerySelect(locale).item)
    items: list[Any] = [
        discord.ui.TextDisplay(f"# {dstrings['delta_title']}"),
        discord.ui.TextDisplay(str(dstrings["delta_hint"])),
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {dstrings['delta_zone_end_label']}"),
        discord.ui.TextDisplay(str(dstrings["delta_zone_end_hint"])),
        rows,
        discord.ui.Separator(),
        discord.ui.TextDisplay(f"## {dstrings['delta_zone_gallery_label']}"),
        discord.ui.TextDisplay(str(dstrings["delta_zone_gallery_hint"])),
        gallery_row,
    ]
    container = discord.ui.Container(*items)
    return surface(DELTA_WINDOW_KEY, container)


def delta_dynamic_items() -> tuple:
    """Every restart-proof DynamicItem of the delta surfaces."""
    return (
        DeltaActionButton,
        DeltaGallerySelect,
        DeltaBouclerButton,
        DeltaArchiverButton,
    )


# ---------------------------------------------------------------------------
# The message gallery — one template + sample params, ephemeral previews
# ---------------------------------------------------------------------------


def gallery_entries(locale: str) -> list[dict[str, Any]]:
    """Every previewable message: key → label + text blocks (duck-typed).

    gallery-v1 (Drasah 28/11) : « en cliquant dessus je dois être
    capable de voir l'ensemble des messages potentiels de kingdom ».
    Chaque entrée est un template + des données d'exemple — le VRAI
    rendu (les mêmes strings que le live), jamais une capture.
    """
    dstrings = delta_strings(locale)
    astrings = strings_by_locale(locale)
    entries: list[dict[str, Any]] = []

    def _add(key: str, label: str, blocks: list[str]) -> None:
        entries.append(
            {"key": key, "label": label[:100], "description": blocks[0][:100], "blocks": blocks}
        )

    _add(
        "welcome",
        str(dstrings["gallery_welcome_label"]),
        [
            str(dstrings["gallery_welcome_body"]).format(
                season=dstrings["gallery_sample_season"],
                kingdoms=dstrings["gallery_sample_kingdoms"],
                count=4,
                calendar=dstrings["gallery_sample_calendar"],
            )
        ],
    )
    _add(
        "conquest",
        str(dstrings["gallery_conquest_label"]),
        [
            str(astrings["conquest_title"]).format(
                winner=dstrings["gallery_sample_winner"], map=dstrings["gallery_sample_map"]
            ),
            str(astrings["conquest_attacker_line"]).format(
                player=dstrings["gallery_sample_king"], kingdom=dstrings["gallery_sample_winner"]
            ),
            str(astrings["conquest_defense_line"]).format(
                player=dstrings["gallery_sample_lord"], kingdom=dstrings["gallery_sample_loser"]
            ),
            str(astrings["conquest_civ_line"]).format(
                player=dstrings["gallery_sample_king"], civ=dstrings["gallery_sample_civ"]
            ),
            str(astrings["conquest_id_line"]).format(game=dstrings["gallery_sample_game"]),
        ],
    )
    _add(
        "forfait",
        str(dstrings["gallery_forfait_label"]),
        [
            str(astrings["forfeit_geo_side"]).format(
                map=dstrings["gallery_sample_map"],
                side=str(astrings["side_attacker"]),
                winner=dstrings["gallery_sample_loser"],
            ),
            str(astrings["forfeit_geo_both"]).format(
                map=dstrings["gallery_sample_map"], winner=dstrings["gallery_sample_winner"]
            ),
        ],
    )
    _add(
        "cycle",
        str(dstrings["gallery_cycle_label"]),
        [str(astrings["event_cycle"]).format(cycle=3, maps=8)],
    )
    _add(
        "age",
        str(dstrings["gallery_age_label"]),
        [
            str(astrings["event_age"]).format(
                age=dstrings["gallery_sample_age"], tech=1, marriages=1
            )
        ],
    )
    _add(
        "end",
        str(dstrings["gallery_end_label"]),
        [
            str(astrings["event_end"]).format(winner=dstrings["gallery_sample_winner"]),
            str(astrings["event_end_podium_title"]),
            str(astrings["event_end_podium_line"]).format("🥇", dstrings["gallery_sample_winner"], 7),
            str(astrings["event_end_podium_line"]).format("🥈", dstrings["gallery_sample_loser"], 4),
        ],
    )
    _add(
        "end-showmatch",
        str(dstrings["gallery_end_showmatch_label"]),
        [str(astrings["event_end_showmatch"])],
    )
    _add(
        "sacree",
        str(dstrings["gallery_sacree_label"]),
        [
            str(astrings["sacree_verdict_note"]).format(
                dstrings["gallery_sample_winner"], dstrings["gallery_sample_map"]
            )
        ],
    )
    _add(
        "expedition",
        str(dstrings["gallery_expedition_label"]),
        [
            str(astrings["expedition_launch_note"]).format(dstrings["gallery_sample_winner"]),
            str(astrings["expedition_return_map"]).format(dstrings["gallery_sample_loser"], dstrings["gallery_sample_map"]),
            str(astrings["expedition_return_civ"]).format(dstrings["gallery_sample_king"], dstrings["gallery_sample_civ"]),
            str(astrings["expedition_return_tech"]).format(dstrings["gallery_sample_winner"]),
        ],
    )
    _add(
        "ffa",
        str(dstrings["gallery_ffa_label"]),
        [
            str(astrings["ffa_announce"]).format("14h00", 75, 3),
        ],
    )
    _add(
        "bouclage",
        str(dstrings["gallery_bouclage_label"]),
        [
            str(
                dict(mod_catalog().section("kingdom.beta_loop", str(locale)[:2]))[
                    "beta_loop_restarted"
                ]
            ).format(name=dstrings["gallery_sample_season"], count=2)
        ],
    )
    return entries


def gallery_preview(locale: str, key: str) -> list[Any]:
    """One gallery entry's CV2 blocks (a TextDisplay per block)."""
    entry = next((e for e in gallery_entries(locale) if e["key"] == key), None)
    if entry is None:
        return []
    return [discord.ui.TextDisplay(str(block)) for block in entry["blocks"]]


# ---------------------------------------------------------------------------
# The restart-proof DynamicItems (the ``kingdom:delta:`` namespace)
# ---------------------------------------------------------------------------


async def _delta_guard(interaction: discord.Interaction) -> bool:
    """Admin + beta at CLICK time — an old message never slips through."""
    from .settings_panel import _panel_guard

    if not await _panel_guard(interaction):
        return False
    if not await delta_visible():
        dstrings = delta_strings(_locale_of(interaction))
        await open_unique_ephemeral(interaction, content=str(dstrings["delta_classic_refused"]))
        return False
    return True


class DeltaActionButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:action:(?P<action>[a-z-]+)",
):
    """One Delta lab action (end-flow / reseat) — restart-proof, guarded."""

    def __init__(self, action: str, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:action:{action}"[:100],
                style=style,
            )
        )
        self.action = action

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "DeltaActionButton":
        locale = _locale_of(interaction)
        dstrings = delta_strings(locale)
        key = {
            "end-flow": "delta_end_button",
            "reseat": "delta_reseat_button",
        }.get(match["action"], "delta_title")
        style = (
            discord.ButtonStyle.danger
            if match["action"] == "end-flow"
            else discord.ButtonStyle.success
        )
        return cls(match["action"], str(dstrings.get(key) or "🌱"), style)

    async def callback(self, interaction: discord.Interaction) -> None:
        if self.action == "end-flow":
            await _delta_end_flow(interaction)
            return
        if self.action == "reseat":
            await _delta_reseat(interaction)
            return
        await open_unique_ephemeral(interaction, content="?")


class DeltaGallerySelect(
    discord.ui.DynamicItem[discord.ui.Select[Any]],
    template=rf"{_NS}:gallery:(?P<locale>[a-z]{{2}})",
):
    """The gallery picker — one message family per option, ephemeral."""

    def __init__(self, locale: str) -> None:
        dstrings = delta_strings(locale)
        options = [
            discord.SelectOption(
                label=str(entry["label"])[:100],
                value=str(entry["key"]),
                description=str(entry["description"])[:100],
            )
            for entry in gallery_entries(locale)
        ][:25]
        super().__init__(
            discord.ui.Select(
                placeholder=str(dstrings["gallery_placeholder"])[:100],
                custom_id=f"{_NS}:gallery:{str(locale)[:2]}",
                options=options or [discord.SelectOption(label="—", value="none")],
                min_values=1,
                max_values=1,
            )
        )
        self.locale = str(locale)[:2]

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "DeltaGallerySelect":
        return cls(_locale_of(interaction))

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await _delta_guard(interaction):
            return
        dstrings = delta_strings(self.locale)
        values = [str(v) for v in (self.item.values or [])]
        key = values[0] if values else ""
        blocks = gallery_preview(self.locale, key)
        if not blocks:
            await open_unique_ephemeral(interaction, content=str(dstrings["gallery_missing"]))
            return
        container = discord.ui.Container(
            discord.ui.TextDisplay(str(dstrings["gallery_preview_header"])),
            discord.ui.Separator(),
            *blocks,
            discord.ui.Separator(),
            discord.ui.TextDisplay(str(dstrings["gallery_preview_note"])),
        )
        await open_unique_ephemeral(
            interaction, view=surface(DELTA_GALLERY_VIEW_KEY, container)
        )


class DeltaBouclerButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:end:boucler",
):
    """The ceremony's « 🔄 Boucler » — relaunch + the crew photo re-seated."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:end:boucler"[:100],
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "DeltaBouclerButton":
        return cls(str(delta_strings(_locale_of(interaction))["ceremony_boucler_button"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from .settings_panel import _safe_send

        dstrings = delta_strings(_locale_of(interaction))
        # the spam lesson (Drasah 28/11) : the ack comes FIRST, the
        # work rides behind it — the click is never silent
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(str(dstrings["ceremony_boucler_ack"]), ephemeral=True)
        if not await _panel_guard_quiet(interaction):
            return
        record = await read_ceremony(interaction.client)
        if record is None:
            await _safe_send(interaction, str(dstrings["ceremony_gone"]))
            return
        stack = wiring()
        if stack is None:
            await _safe_send(interaction, str(dstrings["delta_no_service"]))
            return
        from .beta_loop import relaunch_beta

        summary = await relaunch_beta(
            interaction.client,
            stack,
            roster=list(record.get("roster") or []),
            beta_name=str(record.get("beta_name") or ""),
        )
        if summary is None:
            await _safe_send(interaction, str(dstrings["ceremony_gone"]))
            return
        await _clear_ceremony(interaction.client)
        count = len(record.get("roster") or [])
        await _safe_send(
            interaction, str(dstrings["ceremony_boucler_done"]).format(count=count)
        )


class DeltaArchiverButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:end:archiver",
):
    """The ceremony's « 🗄️ Archiver » — season salons wiped, Panthéon kept."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=label[:80],
                custom_id=f"{_NS}:end:archiver"[:100],
                style=discord.ButtonStyle.secondary,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Item[Any],
        match: re.Match[str],
        /,
    ) -> "DeltaArchiverButton":
        return cls(str(delta_strings(_locale_of(interaction))["ceremony_archiver_button"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        from .settings_panel import _safe_send

        dstrings = delta_strings(_locale_of(interaction))
        await interaction.response.defer(ephemeral=True)
        await interaction.followup.send(str(dstrings["ceremony_archiver_ack"]), ephemeral=True)
        if not await _panel_guard_quiet(interaction):
            return
        record = await read_ceremony(interaction.client)
        wiped = await _reset_season_salons(interaction)
        if record is not None:
            await _clear_ceremony(interaction.client)
        await _safe_send(
            interaction, str(dstrings["ceremony_archiver_done"]).format(count=wiped)
        )


async def _panel_guard_quiet(interaction: discord.Interaction) -> bool:
    """The admin check, silent refusal (the ack already answered)."""
    from .settings_panel import _panel_guard

    return await _panel_guard(interaction)


async def _reset_season_salons(interaction: discord.Interaction) -> int:
    """Delete then RE-PROVISION the season salons (salons-vierges-v1).

    « il faut pouvoir reprendre sur des salons vierges » : 🌍
    géopolitique et 🗺️ territoire disparaissent puis renaissent par le
    SEAM de provisioning (le stored id pointe dans le vide → le canal
    est recréé, les permissions re-posées par la déclaration) — jamais
    une écriture directe dans les collections de la plateforme. Le
    🏛️ Panthéon, vitrine hors saison, n'est JAMAIS touché.
    """
    guild = getattr(interaction, "guild", None)
    if guild is None:
        return 0
    from .battle import _geopolitics_channel
    from .common import slug

    territory = next(
        (
            channel
            for channel in getattr(guild, "text_channels", [])
            if "territoire" in slug(getattr(channel, "name", ""))
        ),
        None,
    )
    targets = [channel for channel in (_geopolitics_channel(guild), territory) if channel is not None]
    wiped = 0
    for channel in targets:
        try:
            await channel.delete(reason="kingdom: delta archiver la saison (salons vierges)")
            wiped += 1
        except Exception:  # noqa: BLE001 — one salon never stops the reset
            logger.warning(
                "kingdom: the season salon wipe failed (%s)",
                getattr(channel, "id", "?"),
                exc_info=True,
            )
    if wiped:
        try:
            from botforge.discord.mods_forum import provision_mod_channels

            await provision_mod_channels(
                interaction.client, str(guild.id), "kingdom"
            )
        except Exception:  # noqa: BLE001 — the 5-min self-heal catches up
            logger.warning("kingdom: the salons reprovision failed", exc_info=True)
    return wiped


# ---------------------------------------------------------------------------
# The end flow — capture, close, ceremony
# ---------------------------------------------------------------------------


async def _delta_end_flow(interaction: discord.Interaction) -> None:
    """🧪 The NEW end flow: photograph, close (the official seam), celebrate."""
    from .settings_panel import _end_season, _safe_send, settings_strings, _needs_stack

    locale = _locale_of(interaction)
    dstrings = delta_strings(locale)
    sstrings = settings_strings(locale)
    # the spam lesson : the ack FIRST (the fast-ack owns Discord's 3 s),
    # the heavy work rides behind — the click is never silent
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:  # noqa: BLE001 — an already-acked click
        logger.debug("kingdom: the delta end defer skipped", exc_info=True)
    await interaction.followup.send(str(dstrings["end_ack"]), ephemeral=True)
    if not await _panel_guard_quiet(interaction):
        return
    stack, busy = _needs_stack(sstrings)
    if busy:
        await _safe_send(interaction, busy)
        return
    season = None
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: the delta end season read failed", exc_info=True)
    if season is None or str(getattr(season, "phase", "")) not in ("started", "ended"):
        await _safe_send(interaction, str(dstrings["end_not_running"]))
        return
    if not getattr(season, "beta_name", None):
        await _safe_send(interaction, str(dstrings["delta_classic_refused"]))
        return
    if await read_ceremony(interaction.client) is not None:
        await _safe_send(interaction, str(dstrings["end_already_pending"]))
        return
    # (1) the crew PHOTOGRAPH — taken BEFORE the close (the ejection
    # lesson of the 02:26 incident : a reseat that reads AFTER finds
    # nobody, the photo never loses a kingdom)
    from .beta_loop import capture_engaged_roster

    roster = await capture_engaged_roster(getattr(stack, "realms", None))
    podium = await _podium_snapshot(stack)
    record: dict[str, Any] = {
        "season_id": str(getattr(season, "id", "")),
        "beta_name": str(getattr(season, "beta_name", "") or ""),
        "roster": roster,
        "winner_name": podium.get("winner_name"),
        "territories": podium.get("territories") or {},
        "showmatch": bool(podium.get("showmatch")),
    }
    if not await _store_ceremony(interaction.client, record):
        # without a record the follow-up buttons are dead — the flow
        # refuses rather than closing a season nobody can pilot after
        await _safe_send(interaction, str(dstrings["end_state_failed"]))
        return
    # (2) the official close — the SAME seam as the official button
    # (the ceremony adds nothing to the end itself, Delta only frames it)
    await _end_season(interaction, sstrings)
    # (3) the ceremony — verdict + podium + the two doors of the after
    await _post_ceremony(interaction, record, locale, dstrings)


async def _post_ceremony(
    interaction: discord.Interaction,
    record: dict[str, Any],
    locale: str,
    dstrings: dict[str, str],
) -> None:
    """Post the end ceremony in 🌍 géopolitique (verdict + the two doors)."""
    from .battle import _geopolitics_channel
    from .phases import _podium_text
    from .settings_panel import _safe_send

    astrings = strings_by_locale(locale)
    guild = getattr(interaction, "guild", None)
    channel = _geopolitics_channel(guild) if guild is not None else None
    if channel is None:
        await _safe_send(interaction, str(dstrings["end_no_channel"]))
        return
    report = {
        "kind": "end",
        "winner_name": record.get("winner_name"),
        "territories": record.get("territories") or {},
        "showmatch": bool(record.get("showmatch")),
    }
    if report["showmatch"] and not report["winner_name"]:
        verdict = str(astrings["event_end_showmatch"])
    else:
        verdict = str(astrings["event_end"]).format(
            winner=str(record.get("winner_name") or "?")
        )
    podium = _podium_text(astrings, report)
    text = (
        f"## {dstrings['ceremony_title']}\n"
        f"{dstrings['ceremony_beta_line'].format(name=str(record.get('beta_name') or '?'))}\n\n"
        f"{verdict}\n\n{podium}\n\n{dstrings['ceremony_after_hint']}"
    )
    row: Any = discord.ui.ActionRow()
    row.add_item(
        DeltaBouclerButton(str(dstrings["ceremony_boucler_button"])).item
    )
    row.add_item(
        DeltaArchiverButton(str(dstrings["ceremony_archiver_button"])).item
    )
    container = discord.ui.Container(
        discord.ui.TextDisplay(text),
        discord.ui.Separator(),
        row,
    )
    try:
        await channel.send(view=surface(DELTA_END_VIEW_KEY, container))
    except Exception:  # noqa: BLE001 — the end stands, the note says it
        logger.warning("kingdom: the delta ceremony post failed", exc_info=True)
        await _safe_send(interaction, str(dstrings["end_no_channel"]))
        return
    await _safe_send(
        interaction,
        str(dstrings["end_done"]).format(count=len(record.get("roster") or [])),
    )


async def _delta_reseat(interaction: discord.Interaction) -> None:
    """🪑 Réembarquer — every standby shell replays the admission chain."""
    from .beta_loop import _reseat_one, standby_shells
    from .settings_panel import _needs_stack, _safe_send, settings_strings

    locale = _locale_of(interaction)
    dstrings = delta_strings(locale)
    sstrings = settings_strings(locale)
    try:
        await interaction.response.defer(ephemeral=True)
    except Exception:  # noqa: BLE001
        logger.debug("kingdom: the reseat defer skipped", exc_info=True)
    await interaction.followup.send(str(dstrings["reseat_ack"]), ephemeral=True)
    if not await _panel_guard_quiet(interaction):
        return
    stack, busy = _needs_stack(sstrings)
    if busy:
        await _safe_send(interaction, busy)
        return
    season = None
    try:
        season = await stack.kingdoms.current_season()
    except Exception:  # noqa: BLE001
        logger.warning("kingdom: the reseat season read failed", exc_info=True)
    if season is None or str(getattr(season, "phase", "")) not in ("setup", "started"):
        await _safe_send(interaction, str(dstrings["reseat_not_running"]))
        return
    realms_service = getattr(stack, "realms", None)
    guild = getattr(interaction, "guild", None)
    shells = await standby_shells(realms_service)
    reseated = 0
    for shell in shells:
        try:
            fresh = await _reseat_one(stack, realms_service, guild, shell)
            if fresh is not None:
                reseated += 1
        except Exception:  # noqa: BLE001 — one shell never stops the pass
            logger.warning(
                "kingdom: the delta reseat failed (%s)",
                getattr(shell, "id", "?"),
                exc_info=True,
            )
    if shells and reseated == 0:
        logger.warning(
            "kingdom: the réembarquement re-seated NO shell (%d standby)",
            len(shells),
        )
    await _safe_send(
        interaction, str(dstrings["reseat_done"]).format(count=reseated)
    )


__all__ = [
    "CEREMONY_STATE_KEY",
    "DELTA_END_VIEW_KEY",
    "DELTA_GALLERY_VIEW_KEY",
    "DELTA_WINDOW_KEY",
    "DeltaActionButton",
    "DeltaArchiverButton",
    "DeltaBouclerButton",
    "DeltaGallerySelect",
    "delta_drawer",
    "delta_dynamic_items",
    "delta_strings",
    "delta_visible",
    "gallery_entries",
    "gallery_preview",
    "read_ceremony",
]
