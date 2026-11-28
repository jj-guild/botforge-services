"""Kingdom mod — the 🪶 volière panel (voliere-v2 port, Drasah 28/11).

PORTAGE of the reference branch's ``kingdom_voliere_panel.py``
(vibe/drasah/main) : la fenêtre 🏗️ Volière des lieux héberge les lignes
et les rangées du MOTEUR (``stack.voliere``) — l'emplacement ouvert, le
choix de l'oiseau, et les 9 boutons d'action par oiseau possédé
(disabled pendant l'envol). Le vol de Corbeau porte DEUX vues
persistantes (restart-proof DynamicItems) : l'alarme 🛡️ Contester chez
le royaume volé, le prompt 🛑/➡️ chez le voleur.

House rules du portage :
- chaque clic sur la fenêtre illustrée (v2) DEFER puis passe par la
  fenêtre éphémère UNIQUE — jamais de réponse brute contre un message
  v2 ; les flows internes (selects/modals) vivent leur propre bulle ;
- l'anonymat est joueur-seulement : chaque action journalise le
  seigneur agissant pour l'admin (anti-abus, arbitrage Drasah) ;
- les données passent UNIQUEMENT par les seams du moteur
  (``stack.voliere``), jamais par le modèle directement.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

import discord

from botforge.mods.kingdom import chronicle
from botforge.mods.kingdom.game_clock import game_now
from botforge.mods.kingdom.voliere import BIRDS

from .common import lord_of, open_unique_ephemeral, wiring

logger = logging.getLogger("kingdom.voliere")

_NS = "kingdom:voliere"

BIRD_NAME: dict[str, str] = {"corbeau": "Corbeau", "faucon": "Faucon", "pigeon": "Pigeon"}
BIRD_EMOJI: dict[str, str] = {"corbeau": "🐦‍⬛", "faucon": "🦅", "pigeon": "🕊️"}

BIRD_LABEL = {"corbeau_civ": "Corbeau", "pigeon_civ": "Pigeon"}

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "voliere_button": "🪶 Develop the volière",
        "voliere_title": "# 🪶 Volière of {kingdom}",
        "voliere_line": "Free from the Feudal Age — cooldowns shared by the whole kingdom.",
        "beta_line": "🧪 **BETA** — every volière delay lands in **5 minutes**.",
        "ready_in": "ready in {hours}h",
        "ready": "ready",
        "slot_button": "🪶 Choose a bird",
        "slot_choose": "🪶 A slot is open — which bird lands in your volière?",
        "espace_title": "{bird} — the space",
        "espace_ready": "**{bird}** — on its perch, ready",
        "espace_flying": "**{bird}** — flying, back <t:{ts}:R>",
        "back_button": "↩️ Back to the volière",
        "state_ready": "{bird} ready",
        "state_flying": "{bird} back <t:{ts}:R>",
        "slot_open": "🕳️ Slot to fill — **choose a bird**.",
        "slot_next": "🔒 Next slot at the **{age}** age.",
        "bird_chosen": "🪶 The **{bird}** lands in your volière!",
        "bird_ready": "🪶 **{bird}** — on its perch, ready",
        "bird_flying": "🕊️ **{bird}** — flying, back <t:{ts}:R>",
        "bird_not_owned": "❌ The {bird} is not in your volière — choose it in a slot first.",
        "act_corbeau_civ": "🐦‍⬛ Steal tech points",
        "act_corbeau_verify": "🐦‍⬛ Verify an attack",
        "act_corbeau_track": "🐦‍⬛ Track a lord",
        "act_faucon_territory": "🦅 Draw a territory",
        "act_faucon_sabotage": "🦅 Sabotage a meeting",
        "act_faucon_release": "🦅 Release the faucon",
        "act_pigeon_civ": "🕊️ Draw a civilization",
        "act_pigeon_question": "🕊️ Anonymous question",
        "act_pigeon_dm": "🕊️ Anonymous MP",
        "civ_drawn": "🎲 The {bird} draws the civilization **{civ}**.",
        "territory_drawn": "🎲 The faucon draws the territory **{map}** — it joins your kingdom.",
        "verify_choose": "🐦‍⬛ Which attack should the Corbeau inspect?",
        "verify_result": (
            "🐦‍⬛ The real attacker of **{map}** is **{name}**.\n"
            "🗡️ His civilizations: **{civs}**.\n"
            "♟️ Edge: the defender sets his 3 civilizations AFTER."
        ),
        "verify_no_target": "❌ No ongoing attack targets your kingdom.",
        "track_choose": "🐦‍⬛ Which lord should the Corbeau track?",
        "track_done": "🐦‍⬛ **{name}** is tracked — every attack he declares leaves delayed for the window.",
        "track_no_target": "❌ No trackable lord (another player kingdom).",
        "sabotage_choose": "🦅 Which meeting should the Faucon sabotage?",
        "sabotage_civ_choose": "🦅 Which civilization to sabotage (limit 2)?",
        "sabotage_done": "🦅 The Faucon sabotages **{civ}** on **{map}**.",
        "sabotage_no_target": "❌ No attack in its pick & ban phase involves your kingdom.",
        "sabotage_no_civ": "❌ The adversary holds no civilization to sabotage.",
        "release_done": "🦅 The faucon is released — your kingdom suffers NO adverse technology effect during the window.",
        "question_title": "🕊️ Anonymous question",
        "question_input": "Your question (anonymous)",
        "question_sent": "🕊️ The question landed in the Question salon — nobody sees the sender.",
        "question_no_channel": "❌ The Question salon is absent.",
        "dm_choose": "🕊️ Which kingdom should receive the anonymous MP?",
        "dm_title": "🕊️ Anonymous MP to {kingdom}",
        "dm_input": "Your message (anonymous)",
        "dm_sent": "🕊️ The MP reached every lord of **{kingdom}** — nobody sees the sender.",
        "dm_no_target": "❌ No other player kingdom.",
        "dm_failed": "❌ The MP could not reach any lord.",
        "theft_choose": "🐦‍⬛ Which kingdom should the Corbeau raid?",
        "theft_sent": (
            "🐦‍⬛ The Corbeau flies to **{kingdom}** — the theft executes "
            "<t:{ts}:R> (alarm + contest window there)."
        ),
        "theft_no_target": "❌ No other player kingdom.",
        "theft_contest_button": "🛡️ Contest",
        "theft_continue_button": "➡️ Continue (2nd ⚙️)",
        "theft_stop_button": "🛑 Stop (keep the 1st ⚙️)",
        "theft_stopped": "🐦‍⬛ The Corbeau flies home safe with **{points} ⚙️**.",
        "theft_continuing": (
            "🐦‍⬛ The Corbeau goes for the 2nd ⚙️ — nobody contests before "
            "<t:{ts}:R> and it leaves with **{points} ⚙️**."
        ),
        "theft_contested": (
            "🛡️ CONTEST WON — the Corbeau dies, **{points} ⚙️** refunded to the bank. "
            "The thief's Corbeau slot is lost (buyable again at the next Age)."
        ),
        "theft_not_yours": "❌ This theft does not involve your kingdom.",
        "failed": "❌ {message}",
        "no_service": "❌ The volière service is unavailable.",
        "not_a_lord": "❌ You belong to no kingdom of the current season.",
        "unknown": "unknown",
        # The events loop's two bells (theft alarms).
        "alarm": (
            "🐦‍⬛ **CORBEAU ALARM** — {thief} steals **{points} ⚙️** from the bank! "
            "You may CONTEST until <t:{ts}:R> ({minutes}-minute window). "
            "The thief may go for a 2nd ⚙️ — a contest kills the Corbeau and refunds EVERYTHING."
        ),
        "prompt": (
            "🐦‍⬛ The Corbeau steals **{points} ⚙️** from **{target}**! Continue?\n"
            "🛑 STOP = fly home safe with the 1st ⚙️; ➡️ CONTINUE = go for the 2nd "
            "(a contest before <t:{ts}:R> kills the Corbeau and you leave with NOTHING). "
            "No answer = automatic safe return with the 1st ⚙️."
        ),
    },
    "fr": {
        "voliere_button": "🪶 Développer la volière",
        "voliere_title": "# 🪶 Volière de {kingdom}",
        "voliere_line": "Gratuite dès l'Âge Féodal — cooldowns partagés par tout le royaume.",
        "beta_line": "🧪 **BÊTA** — chaque délai de la volière tombe dans **5 minutes**.",
        "ready_in": "prêt dans {hours}h",
        "ready": "prêt",
        "slot_button": "🪶 Choisir un oiseau",
        "slot_choose": "🪶 Un emplacement est ouvert — quel oiseau atterrit dans ta volière ?",
        "espace_title": "{bird} — l'espace",
        "espace_ready": "**{bird}** — posé sur son perchoir, prêt",
        "espace_flying": "**{bird}** — envolé, revient <t:{ts}:R>",
        "back_button": "↩️ Retour à la volière",
        "state_ready": "{bird} prêt",
        "state_flying": "{bird} revient <t:{ts}:R>",
        "slot_open": "🕳️ Emplacement à remplir — **choisis un oiseau**.",
        "slot_next": "🔒 Prochain emplacement à l'âge **{age}**.",
        "bird_chosen": "🪶 Le **{bird}** atterrit dans ta volière !",
        "bird_ready": "🪶 **{bird}** — posé sur son perchoir, prêt",
        "bird_flying": "🕊️ **{bird}** — envolé, il revient <t:{ts}:R>",
        "bird_not_owned": "❌ Le {bird} n'est pas dans ta volière — choisis-le dans un emplacement d'abord.",
        "act_corbeau_civ": "🐦‍⬛ Voler des points technologiques",
        "act_corbeau_verify": "🐦‍⬛ Vérifier une attaque",
        "act_corbeau_track": "🐦‍⬛ Cibler un seigneur",
        "act_faucon_territory": "🦅 Piocher un territoire",
        "act_faucon_sabotage": "🦅 Sabotage en rencontre",
        "act_faucon_release": "🦅 Lâcher de faucon",
        "act_pigeon_civ": "🕊️ Piocher une civilisation",
        "act_pigeon_question": "🕊️ Question anonyme",
        "act_pigeon_dm": "🕊️ MP anonyme",
        "civ_drawn": "🎲 Le {bird} pioche la civilisation **{civ}**.",
        "territory_drawn": "🎲 Le faucon pioche le territoire **{map}** — il rejoint ton royaume.",
        "verify_choose": "🐦‍⬛ Quelle attaque le Corbeau doit-il inspecter ?",
        "verify_result": (
            "🐦‍⬛ Le véritable attaquant de **{map}** est **{name}**.\n"
            "🗡️ Ses civilisations : **{civs}**.\n"
            "♟️ Avantage : le défenseur définit ses 3 civilisations APRÈS."
        ),
        "verify_no_target": "❌ Aucune attaque en cours ne vise ton royaume.",
        "track_choose": "🐦‍⬛ Quel seigneur le Corbeau doit-il cibler ?",
        "track_done": "🐦‍⬛ **{name}** est suivi — toutes ses déclarations d'attaque partent avec le délai pendant la fenêtre.",
        "track_no_target": "❌ Aucun seigneur ciblable (d'un autre royaume).",
        "sabotage_choose": "🦅 Quelle rencontre le Faucon doit-il saboter ?",
        "sabotage_civ_choose": "🦅 Quelle civilisation saboter (limite 2) ?",
        "sabotage_done": "🦅 Le Faucon sabote **{civ}** sur **{map}**.",
        "sabotage_no_target": "❌ Aucune attaque en phase pick & ban n'implique ton royaume.",
        "sabotage_no_civ": "❌ L'adversaire ne détient aucune civilisation à saboter.",
        "release_done": "🦅 Le faucon est lâché — pendant la fenêtre ton royaume ne subit AUCUN effet de technologie adverse.",
        "question_title": "🕊️ Question anonyme",
        "question_input": "Ta question (anonyme)",
        "question_sent": "🕊️ La question a atterri dans le salon Question — personne ne voit l'expéditeur.",
        "question_no_channel": "❌ Le salon Question est absent.",
        "dm_choose": "🕊️ Quel royaume doit recevoir le MP anonyme ?",
        "dm_title": "🕊️ MP anonyme à {kingdom}",
        "dm_input": "Ton message (anonyme)",
        "dm_sent": "🕊️ Le MP est parvenu à chaque seigneur de **{kingdom}** — personne ne voit l'expéditeur.",
        "dm_no_target": "❌ Aucun autre royaume.",
        "dm_failed": "❌ Le MP n'a pu atteindre aucun seigneur.",
        "theft_choose": "🐦‍⬛ Quel royaume le Corbeau doit-il piller ?",
        "theft_sent": (
            "🐦‍⬛ Le Corbeau s'envole vers **{kingdom}** — le vol s'exécute "
            "<t:{ts}:R> (alarme + fenêtre de contestation là-bas)."
        ),
        "theft_no_target": "❌ Aucun autre royaume.",
        "theft_contest_button": "🛡️ Contester",
        "theft_continue_button": "➡️ Continuer (2e ⚙️)",
        "theft_stop_button": "🛑 STOP (garder le 1er ⚙️)",
        "theft_stopped": "🐦‍⬛ Le Corbeau repart sain et sauf avec **{points} ⚙️**.",
        "theft_continuing": (
            "🐦‍⬛ Le Corbeau tente le 2e ⚙️ — personne ne conteste avant "
            "<t:{ts}:R> et il repart avec **{points} ⚙️**."
        ),
        "theft_contested": (
            "🛡️ CONTESTATION RÉUSSIE — le Corbeau meurt, **{points} ⚙️** restitués "
            "à la banque. Le slot Corbeau du voleur est perdu (rachetable à l'Âge suivant)."
        ),
        "theft_not_yours": "❌ Ce vol n'implique pas ton royaume.",
        "failed": "❌ {message}",
        "no_service": "❌ Le service volière est indisponible.",
        "not_a_lord": "❌ Tu n'appartiens à aucun royaume de la saison en cours.",
        "unknown": "inconnu",
        # Les deux cloches de la boucle (alarmes du vol).
        "alarm": (
            "🐦‍⬛ **ALARME CORBEAU** — {thief} vole **{points} ⚙️** dans la banque ! "
            "Vous pouvez CONTESTER jusqu'à <t:{ts}:R> (fenêtre de {minutes} min). "
            "Le voleur peut tenter un 2e ⚙️ — une contestation tue le Corbeau et restitue TOUT."
        ),
        "prompt": (
            "🐦‍⬛ Le Corbeau vole **{points} ⚙️** à **{target}** ! Continuer ?\n"
            "🛑 STOP = repartir sain et sauf avec le 1er ⚙️ ; ➡️ CONTINUER = tenter le 2e "
            "(une contestation avant <t:{ts}:R> tue le Corbeau et vous repartez sans rien). "
            "Sans réponse, il repart automatiquement avec le 1er ⚙️."
        ),
    },
}


def voliere_strings(locale: Any) -> dict[str, str]:
    """The volière catalog (fr default, like every mod surface)."""
    raw = str(getattr(locale, "value", locale) or "fr")
    return _STRINGS["fr"] if raw.lower().startswith("fr") else _STRINGS["en"]


def _locale_of(interaction: discord.Interaction) -> str:
    return str(getattr(interaction, "locale", "fr") or "fr")


def _now() -> datetime:
    """The wall clock of every panel action (hookable in tests)."""
    return game_now()


# ---------------------------------------------------------------------------
# The engine state (through the seams only)
# ---------------------------------------------------------------------------


async def voliere_beta_on(stack: Any, now: datetime | None = None) -> bool:
    """Whether the LIVE season runs an armed, started beta (5-min delays)."""
    voliere = getattr(stack, "voliere", None)
    if voliere is None:
        return False
    try:
        return await voliere._beta_armed(now or _now())
    except Exception:  # noqa: BLE001
        return False


async def voliere_state(kingdom: Any) -> dict[str, Any] | None:
    """The kingdom's slot snapshot through the seam (None = no engine)."""
    stack = wiring()
    voliere = getattr(stack, "voliere", None)
    if stack is None or voliere is None or kingdom is None:
        return None
    try:
        state = await voliere.slot_state(str(kingdom.id))
        state["beta"] = await voliere_beta_on(stack)
        return state
    except Exception:  # noqa: BLE001
        logger.info("kingdom volière: slot state read failed", exc_info=True)
        return None


async def voliere_extra_lines(strings: dict[str, str], state: dict[str, Any] | None) -> list[str]:
    """The sommaire's engine lines (empty when no engine).

    voliere-espaces-v1 (Drasah 28/11) : UNE ligne d'état au-dessus de la
    rangée horizontale des espaces — chaque oiseau possédé y figure
    DANS L'ORDRE de son bouton. Le timer n'apparaît QUE si l'oiseau est
    envolé (Drasah : un oiseau disponible n'affiche JAMAIS de timer).
    """
    if not state:
        return []
    lines: list[str] = []
    now_ts = int(_now().timestamp())
    statuses: list[str] = []
    for bird in (state.get("chosen") or []):
        ready_at = int((state.get("cooldowns") or {}).get(bird, 0) or 0)
        if ready_at > now_ts:
            # le SEUL cas qui porte un timer : l'oiseau est parti
            statuses.append(
                str(strings["state_flying"]).format(
                    bird=f"{BIRD_EMOJI.get(bird, '')} {BIRD_NAME.get(bird, bird)}",
                    ts=ready_at,
                )
            )
        else:
            statuses.append(
                str(strings["state_ready"]).format(
                    bird=f"{BIRD_EMOJI.get(bird, '')} {BIRD_NAME.get(bird, bird)}"
                )
            )
    if statuses:
        lines.append(" · ".join(statuses))
    if int(state.get("open") or 0) > 0:
        lines.append(str(strings["slot_open"]))
    elif state.get("next_age"):
        lines.append(str(strings["slot_next"]).format(age=state["next_age"]))
    if bool(state.get("beta")):
        lines.append(str(strings["beta_line"]))
    return lines


async def voliere_rows(strings: dict[str, str], state: dict[str, Any] | None) -> list[list[Any]]:
    """The sommaire's rows — ONE horizontal row of the three SPACES
    (grey + disabled when the bird is not in the volière, never hidden)
    plus the slot button when an emplacement is open. The 3 actions of
    a bird live in ITS space, not here (voliere-espaces-v1)."""
    rows: list[list[Any]] = []
    if not state:
        return rows
    row: list[Any] = []
    for bird in BIRDS:
        row.append(
            discord.ui.Button(
                label=(
                    f"{BIRD_EMOJI.get(bird, '')} {BIRD_NAME.get(bird, bird)}"
                )[:80],
                custom_id=f"{_NS}:espace:{bird}",
                style=discord.ButtonStyle.secondary,
                disabled=bird not in (state.get("chosen") or []),
            )
        )
    if int(state.get("open") or 0) > 0 and (state.get("available") or []):
        row.append(
            discord.ui.Button(
                label=str(strings["slot_button"])[:80],
                custom_id=f"{_NS}:slot",
                style=discord.ButtonStyle.success,
            )
        )
    rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# voliere-espaces-v1 (Drasah 28/11) : les ESPACES
# ---------------------------------------------------------------------------

ESPACE_SURFACE = "panel:mod:kingdom:lieux:voliere:espace"
"""#395 : UN seul template d'espace, instancié par paramètre (l'oiseau)."""

ACTIONS_BY_BIRD: dict[str, list[str]] = {
    "corbeau": ["corbeau_civ", "corbeau_verify", "corbeau_track"],
    "faucon": ["faucon_territory", "faucon_sabotage", "faucon_release"],
    "pigeon": ["pigeon_civ", "pigeon_question", "pigeon_dm"],
}


def espace_view(
    strings: dict[str, str],
    state: dict[str, Any] | None,
    bird: str,
    *,
    note: str = "",
) -> "discord.ui.LayoutView":
    """UN template d'espace, paramétré par l'oiseau (#395).

    Le timer vit en tête, AU-DESSUS de la rangée horizontale des 3
    actions — et il n'apparaît QUE si l'oiseau est envolé (Drasah :
    un oiseau disponible n'affiche jamais de timer).
    """
    from .common import surface

    emoji = BIRD_EMOJI.get(bird, "")
    name = BIRD_NAME.get(bird, bird)
    title = str(strings["espace_title"]).format(bird=f"{emoji} {name}")
    now_ts = int(_now().timestamp())
    ready_at = int(((state or {}).get("cooldowns") or {}).get(bird, 0) or 0)
    flying = ready_at > now_ts
    status = (
        str(strings["espace_flying"]).format(bird=f"{emoji} {name}", ts=ready_at)
        if flying
        else str(strings["espace_ready"]).format(bird=f"{emoji} {name}")
    )
    items: list[Any] = [discord.ui.TextDisplay(f"# {title}")]
    if note:
        items.append(discord.ui.TextDisplay(str(note)))
    items.append(discord.ui.TextDisplay(status))
    actions = [
        discord.ui.Button(
            label=str(strings[f"act_{action}"])[:80],
            custom_id=f"{_NS}:act:{action}",
            style=discord.ButtonStyle.secondary,
            disabled=flying,
        )
        for action in ACTIONS_BY_BIRD.get(bird, [])
    ]
    if actions:
        items.append(discord.ui.ActionRow(*actions))
    items.append(
        discord.ui.ActionRow(
            discord.ui.Button(
                label=str(strings["back_button"])[:80],
                custom_id=f"{_NS}:back",
                style=discord.ButtonStyle.grey,
            )
        )
    )
    return surface(ESPACE_SURFACE, *items)


async def _back_to_sommaire(
    interaction: discord.Interaction, kingdom: Any, *, note: str = ""
) -> None:
    """Transformer la bulle en place : retour au SOMMAIRE illustré,
    le résultat de l'action collé sous le titre (une seule bulle,
    jamais d'empilement — la fenêtre unique referme la précédente)."""
    from .lieux import _voliere_window, lieux_strings

    locale = _locale_of(interaction)
    try:
        view, files = await _voliere_window(
            lieux_strings(locale), kingdom, locale, note=note
        )
        await open_unique_ephemeral(interaction, view=view, files=files or None)
    except Exception:  # noqa: BLE001 — never block a done action
        logger.warning("kingdom volière: return to sommaire failed", exc_info=True)
        if note:
            await open_unique_ephemeral(interaction, content=note)


class VoliereEspaceButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:espace:(?P<bird>[a-z]+)",
):
    """Le bouton d'un ESPACE du sommaire — restart-proof. La bulle unique
    se transforme en place : le sommaire ferme, l'espace s'ouvre."""

    def __init__(self, bird: str, label: str, held: bool) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:espace:{bird}",
                style=discord.ButtonStyle.secondary,
                disabled=not held,
            )
        )
        self.bird = str(bird)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        bird = str(match["bird"])
        strings = voliere_strings(_locale_of(interaction))
        label = f"{BIRD_EMOJI.get(bird, '')} {BIRD_NAME.get(bird, bird)}"
        return cls(bird, label, False)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = voliere_strings(_locale_of(interaction))
        lord, kingdom, stack = await _require_lord(interaction, strings)
        if kingdom is None:
            return
        state = await voliere_state(kingdom)
        if state is None or self.bird not in (state.get("chosen") or []):
            await open_unique_ephemeral(interaction, content=strings["bird_not_owned"].format(bird=BIRD_NAME.get(self.bird, self.bird)))
            return
        await open_unique_ephemeral(
            interaction, view=espace_view(strings, state, self.bird)
        )


class VoliereBackButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:back"
):
    """↩️ Retour à la volière — la bulle redevient le sommaire illustré."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:back",
                style=discord.ButtonStyle.grey,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(voliere_strings(_locale_of(interaction))["back_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = voliere_strings(_locale_of(interaction))
        lord, kingdom, stack = await _require_lord(interaction, strings)
        if kingdom is None:
            return
        await _back_to_sommaire(interaction, kingdom)


# ---------------------------------------------------------------------------
# The shared panel helpers
# ---------------------------------------------------------------------------


async def _require_lord(
    interaction: discord.Interaction, strings: dict[str, str]
) -> tuple[Any, Any, Any]:
    """Resolve (lord, kingdom, stack) — answers the refusal notes itself."""
    stack = wiring()
    if stack is None or getattr(stack, "voliere", None) is None:
        await open_unique_ephemeral(interaction, content=strings["no_service"])
        return None, None, None
    lord = await lord_of(stack.kingdoms, str(interaction.user.id), interaction)
    kingdom_id = getattr(lord, "kingdom_id", None)
    if lord is None or kingdom_id is None:
        await open_unique_ephemeral(interaction, content=strings["not_a_lord"])
        return None, None, None
    kingdom = next(
        (k for k in await stack.kingdoms.kingdoms() if str(k.id) == str(kingdom_id)),
        None,
    )
    if kingdom is None:
        await open_unique_ephemeral(interaction, content=strings["not_a_lord"])
        return None, None, None
    return lord, kingdom, stack


async def _record_action(stack: Any, lord: Any, action: str, **params: str) -> None:
    """Chronicle one volière action on the acting lord (best-effort)."""
    try:
        await chronicle.record(
            lord,
            chronicle.KIND_VOLIERE_ACTION,
            now=_now(),
            store=getattr(stack, "_store", None) or getattr(stack, "store", None),
            action=action,
            **params,
        )
    except Exception:  # noqa: BLE001
        logger.info("kingdom volière: chronicle record skipped", exc_info=True)


async def _failed(interaction: discord.Interaction, strings: dict[str, str], exc: Exception) -> None:
    """Answer the localized failure in the unique ephemeral window."""
    message = str(getattr(exc, "message", "") or exc)
    content = strings["failed"].format(message=message)
    try:
        await open_unique_ephemeral(interaction, content=content)
    except Exception:  # noqa: BLE001
        logger.info("kingdom volière: failure note skipped", exc_info=True)


# ---------------------------------------------------------------------------
# The slot flow — choose a bird in an open slot
# ---------------------------------------------------------------------------


async def slot_flow(interaction: discord.Interaction, strings: dict[str, str]) -> None:
    """Open the bird-select for one empty volière slot (ALREADY deferred —
    the click lands on the illustrated v2 window, so every answer goes
    through the unique ephemeral window, never a raw response)."""
    lord, kingdom, stack = await _require_lord(interaction, strings)
    if kingdom is None:
        return
    state = await voliere_state(kingdom)
    available = [str(bird) for bird in ((state or {}).get("available") or [])]
    if int((state or {}).get("open") or 0) <= 0 or not available:
        await open_unique_ephemeral(interaction, content=strings["voliere_line"])
        return
    await open_unique_ephemeral(
        interaction,
        view=_bird_select_view(interaction, strings, stack, lord, kingdom, available),
    )


def _bird_select_view(
    interaction: discord.Interaction,
    strings: dict[str, str],
    stack: Any,
    lord: Any,
    kingdom: Any,
    available: list[str],
) -> discord.ui.View:
    """The in-session bird select (classic view — its own bubble)."""

    async def on_pick(target: discord.Interaction[Any]) -> None:
        values = [str(v) for v in (getattr(target, "data", None) or {}).get("values", [])]
        if not values:
            return
        try:
            await stack.voliere.choose_bird(str(kingdom.id), values[0], now=_now())
        except Exception as exc:  # noqa: BLE001
            await _failed(target, strings, exc)
            return
        logger.info("kingdom volière: %s chooses the bird %s (admin trace)", lord.id, values[0])
        try:
            await chronicle.record(
                lord,
                chronicle.KIND_BIRD_CHOSEN,
                now=_now(),
                store=getattr(stack, "_store", None) or getattr(stack, "store", None),
                bird=values[0],
            )
        except Exception:  # noqa: BLE001
            logger.info("kingdom volière: bird chronicle skipped", exc_info=True)
        await _back_to_sommaire(
            target,
            kingdom,
            note=strings["bird_chosen"].format(bird=BIRD_NAME.get(values[0], values[0])),
        )

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"{_NS}:slot:pick",
        placeholder=strings["slot_choose"][:100],
        options=[
            discord.SelectOption(label=BIRD_NAME.get(bird, bird)[:100], value=bird[:100])
            for bird in available[:25]
        ],
    )
    select.callback = on_pick  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    return view


class VoliereSlotButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]], template=rf"{_NS}:slot"
):
    """🪶 Choisir un oiseau — restart-proof (the lieux window's button)."""

    def __init__(self, label: str) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:slot",
                style=discord.ButtonStyle.success,
            )
        )

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        return cls(voliere_strings(_locale_of(interaction))["slot_button"])

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        await slot_flow(interaction, voliere_strings(_locale_of(interaction)))


# ---------------------------------------------------------------------------
# The action flows
# ---------------------------------------------------------------------------


async def _draw_action(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    action: str,
    lord: Any,
) -> None:
    """The three one-shot draws: civ (Pigeon), territory, release (Faucon)."""
    voliere = stack.voliere
    if action == "pigeon_civ":
        try:
            drawn = await voliere.pick_civilization(str(kingdom.id), action, now=_now())
        except Exception as exc:  # noqa: BLE001
            await _failed(interaction, strings, exc)
            return
        await _record_action(stack, lord, action, civ=str(drawn))
        await _back_to_sommaire(
            interaction,
            kingdom,
            note=strings["civ_drawn"].format(
                bird=BIRD_LABEL.get(action, action),
                civ=str(drawn),
            ),
        )
        return
    if action == "faucon_territory":
        try:
            map_key = await voliere.pick_territory(str(kingdom.id), now=_now())
        except Exception as exc:  # noqa: BLE001
            await _failed(interaction, strings, exc)
            return
        await _record_action(stack, lord, action, map=str(map_key))
        await _back_to_sommaire(
            interaction,
            kingdom,
            note=strings["territory_drawn"].format(map=str(map_key)),
        )
        return
    if action == "faucon_release":
        try:
            await voliere.release_faucon(str(kingdom.id), now=_now())
        except Exception as exc:  # noqa: BLE001
            await _failed(interaction, strings, exc)
            return
        await _record_action(stack, lord, action)
        await _back_to_sommaire(interaction, kingdom, note=strings["release_done"])
        return
    logger.info("kingdom volière: unknown draw action %s", action)


async def _verify_flow(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    lord: Any,
) -> None:
    """Corbeau — inspect one attack against the kingdom."""
    attacks = [
        a
        for a in await stack.attacks.attacks()
        if str(a.defender_kingdom_id) == str(kingdom.id)
        and str(getattr(a, "state", "")) not in ("finished", "cancelled")
    ]
    if not attacks:
        await open_unique_ephemeral(interaction, content=strings["verify_no_target"])
        return

    async def on_pick(target: discord.Interaction[Any]) -> None:
        values = [str(v) for v in (getattr(target, "data", None) or {}).get("values", [])]
        if not values:
            return
        attack = next((a for a in attacks if str(a.id) == values[0]), None)
        if attack is None:
            return
        try:
            inspection = await stack.voliere.inspect_attack(
                str(kingdom.id), str(attack.id), now=_now()
            )
        except Exception as exc:  # noqa: BLE001
            await _failed(target, strings, exc)
            return
        await _record_action(stack, lord, "corbeau_verify", map=str(inspection["map_key"]))
        await _back_to_sommaire(
            target,
            kingdom,
            note=strings["verify_result"].format(
                map=str(inspection["map_key"]),
                name=str(inspection["attacker_name"]),
                civs=", ".join(inspection["attacker_civs"]) or strings["unknown"],
            ),
        )

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"{_NS}:verify:pick",
        placeholder=strings["verify_choose"][:100],
        options=[
            discord.SelectOption(
                label=str(getattr(a, "map_key", a.id))[:100], value=str(a.id)[:100]
            )
            for a in attacks[:25]
        ],
    )
    select.callback = on_pick  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    await open_unique_ephemeral(interaction, view=view)


async def _track_flow(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    lord: Any,
) -> None:
    """Corbeau — mark one lord « suivi » (delayed declarations)."""
    targets = [
        other
        for other in await stack.kingdoms.lords()
        if not other.left
        and str(getattr(other, "kingdom_id", "")) != str(kingdom.id)
        and getattr(other, "kingdom_id", None) is not None
    ]
    if not targets:
        await open_unique_ephemeral(interaction, content=strings["track_no_target"])
        return

    async def on_pick(target: discord.Interaction[Any]) -> None:
        values = [str(v) for v in (getattr(target, "data", None) or {}).get("values", [])]
        if not values:
            return
        victim = next((other for other in targets if str(other.id) == values[0]), None)
        if victim is None:
            return
        try:
            await stack.voliere.track_lord(str(kingdom.id), str(victim.id), now=_now())
        except Exception as exc:  # noqa: BLE001
            await _failed(target, strings, exc)
            return
        await _record_action(stack, lord, "corbeau_track", lord_name=str(victim.display_name))
        await _back_to_sommaire(
            target,
            kingdom,
            note=strings["track_done"].format(name=str(victim.display_name)),
        )

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"{_NS}:track:pick",
        placeholder=strings["track_choose"][:100],
        options=[
            discord.SelectOption(
                label=str(getattr(other, "display_name", other.id))[:100],
                value=str(other.id)[:100],
            )
            for other in targets[:25]
        ],
    )
    select.callback = on_pick  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    await open_unique_ephemeral(interaction, view=view)


async def _sabotage_flow(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    lord: Any,
) -> None:
    """Faucon — sabotage one civilization of an ongoing attack."""
    attacks = [
        a
        for a in await stack.attacks.attacks()
        if str(kingdom.id) in (str(a.attacker_kingdom_id), str(a.defender_kingdom_id))
        and bool((a.pickban or {}).get("sent"))
        and not bool((a.pickban or {}).get("room_revealed"))
    ]
    if not attacks:
        await open_unique_ephemeral(interaction, content=strings["sabotage_no_target"])
        return

    async def on_attack(target: discord.Interaction[Any]) -> None:
        values = [str(v) for v in (getattr(target, "data", None) or {}).get("values", [])]
        if not values:
            return
        attack = next((a for a in attacks if str(a.id) == values[0]), None)
        if attack is None:
            return
        other_id = (
            str(attack.defender_kingdom_id)
            if str(attack.attacker_kingdom_id) == str(kingdom.id)
            else str(attack.attacker_kingdom_id)
        )
        other = next(
            (k for k in await stack.kingdoms.kingdoms() if str(k.id) == other_id), None
        )
        civs = [str(civ) for civ in ((other.civilizations if other else []) or [])]
        if not civs:
            await _back_to_sommaire(target, kingdom, note=strings["sabotage_no_civ"])
            return

        async def on_civ(civ_target: discord.Interaction[Any]) -> None:
            civ_values = [
                str(v) for v in (getattr(civ_target, "data", None) or {}).get("values", [])
            ]
            if not civ_values:
                return
            civ = civ_values[0]
            try:
                await stack.voliere.faucon_sabotage(
                    str(kingdom.id), str(attack.id), civ, now=_now()
                )
            except Exception as exc:  # noqa: BLE001
                await _failed(civ_target, strings, exc)
                return
            await _record_action(stack, lord, "faucon_sabotage", civ=civ)
            await _back_to_sommaire(
                civ_target,
                kingdom,
                note=strings["sabotage_done"].format(
                    civ=civ, map=str(getattr(attack, "map_key", ""))
                ),
            )

        civ_select: discord.ui.Select[Any] = discord.ui.Select(
            custom_id=f"{_NS}:sabotage:civ",
            placeholder=strings["sabotage_civ_choose"][:100],
            options=[
                discord.SelectOption(label=civ[:100], value=civ[:100]) for civ in civs[:25]
            ],
        )
        civ_select.callback = on_civ  # type: ignore[method-assign, assignment]
        civ_view = discord.ui.View(timeout=600)
        civ_view.add_item(civ_select)
        await target.response.edit_message(
            content=strings["sabotage_civ_choose"], view=civ_view
        )

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"{_NS}:sabotage:pick",
        placeholder=strings["sabotage_choose"][:100],
        options=[
            discord.SelectOption(
                label=str(getattr(a, "map_key", a.id))[:100], value=str(a.id)[:100]
            )
            for a in attacks[:25]
        ],
    )
    select.callback = on_attack  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    await open_unique_ephemeral(interaction, view=view)


async def _question_modal(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    lord: Any,
) -> None:
    """Pigeon — one anonymous question, posted in the Question salon."""
    try:
        await stack.voliere.spend_action(str(kingdom.id), "pigeon_question", now=_now())
    except Exception as exc:  # noqa: BLE001
        await _failed(interaction, strings, exc)
        return

    question_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
        label=strings["question_input"][:45],
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )
    modal = discord.ui.Modal(title=strings["question_title"][:45])
    modal.add_item(question_input)

    async def on_submit(target: discord.Interaction[Any]) -> None:
        guild = target.guild
        question = str(getattr(question_input, "value", "") or "")
        channel = next(
            (
                c
                for c in getattr(guild, "channels", [])
                if _slug(getattr(c, "name", "")) in ("question", "questions")
            ),
            None,
        )
        if channel is None:
            await target.response.send_message(
                strings["question_no_channel"], ephemeral=True
            )
            return
        logger.info(
            "kingdom volière: anonymous question by %s (admin trace)", lord.id
        )
        await _record_action(stack, lord, "pigeon_question")
        try:
            await channel.create_thread(name=question[:90], content=question)
        except Exception:
            try:
                await channel.send(question)
            except Exception:  # noqa: BLE001
                logger.warning("kingdom volière: anonymous question post failed", exc_info=True)
                await target.response.send_message(
                    strings["question_no_channel"], ephemeral=True
                )
                return
        await target.response.send_message(strings["question_sent"], ephemeral=True)

    modal.on_submit = on_submit  # type: ignore[method-assign]
    await interaction.response.send_modal(modal)


def _slug(name: str) -> str:
    """The reference's channel slug (lowercase, accents folded)."""
    import unicodedata

    text = "".join(
        char
        for char in unicodedata.normalize("NFD", str(name))
        if unicodedata.category(char) != "Mn"
    )
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


async def _dm_flow(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    lord: Any,
) -> None:
    """Pigeon — select the kingdom, then one anonymous modal per lord."""
    kingdoms = [
        k
        for k in await stack.kingdoms.kingdoms()
        if not getattr(k, "is_gaia", False) and str(k.id) != str(kingdom.id)
    ]
    if not kingdoms:
        await open_unique_ephemeral(interaction, content=strings["dm_no_target"])
        return

    async def on_choose(target: discord.Interaction[Any]) -> None:
        values = [str(v) for v in (getattr(target, "data", None) or {}).get("values", [])]
        if not values:
            return
        target_kingdom = next((k for k in kingdoms if str(k.id) == values[0]), None)
        if target_kingdom is None:
            return
        dm_input: discord.ui.TextInput[Any] = discord.ui.TextInput(
            label=strings["dm_input"][:45],
            style=discord.TextStyle.paragraph,
            max_length=1000,
        )
        modal = discord.ui.Modal(
            title=strings["dm_title"].format(kingdom=str(target_kingdom.name))[:45]
        )
        modal.add_item(dm_input)

        async def on_submit(submit_target: discord.Interaction[Any]) -> None:
            text = str(getattr(dm_input, "value", "") or "")
            try:
                await stack.voliere.spend_action(str(kingdom.id), "pigeon_dm", now=_now())
            except Exception as exc:  # noqa: BLE001
                await _failed(submit_target, strings, exc)
                return
            logger.info(
                "kingdom volière: anonymous MP by %s to %s (admin trace)",
                lord.id,
                target_kingdom.id,
            )
            await _record_action(
                stack, lord, "pigeon_dm", kingdom=str(target_kingdom.name)
            )
            sent = await _dm_kingdom_lords(
                stack, submit_target, str(target_kingdom.id), text
            )
            if sent == 0:
                await submit_target.response.send_message(
                    strings["dm_failed"], ephemeral=True
                )
                return
            await submit_target.response.send_message(
                strings["dm_sent"].format(kingdom=str(target_kingdom.name)),
                ephemeral=True,
            )

        modal.on_submit = on_submit  # type: ignore[method-assign]
        await target.response.send_modal(modal)

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"{_NS}:dm:choose",
        placeholder=strings["dm_choose"][:100],
        options=[
            discord.SelectOption(label=str(k.name)[:100], value=str(k.id)[:100])
            for k in kingdoms[:25]
        ],
    )
    select.callback = on_choose  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    await open_unique_ephemeral(interaction, view=view)


async def _dm_kingdom_lords(
    stack: Any, interaction: discord.Interaction, kingdom_id: str, text: str
) -> int:
    """Send one anonymous DM to every active lord of the kingdom."""
    bot = getattr(interaction, "client", None)
    sent = 0
    for recipient in await stack.kingdoms.lords():
        if recipient.left or str(recipient.kingdom_id) != str(kingdom_id):
            continue
        try:
            user = getattr(bot, "get_user", lambda _id: None)(recipient.id)
            if user is None and bot is not None:
                user = await bot.fetch_user(int(recipient.id))
            if user is not None:
                await user.send(text)
                sent += 1
        except Exception:  # noqa: BLE001
            logger.info("kingdom volière: DM failed (%s)", recipient.id, exc_info=True)
    return sent


async def _theft_flow(
    interaction: discord.Interaction,
    stack: Any,
    strings: dict[str, str],
    kingdom: Any,
    lord: Any,
) -> None:
    """Corbeau — send the theft against one target kingdom's bank."""
    kingdoms = [
        k
        for k in await stack.kingdoms.kingdoms()
        if not getattr(k, "is_gaia", False) and str(k.id) != str(kingdom.id)
    ]
    if not kingdoms:
        await open_unique_ephemeral(interaction, content=strings["theft_no_target"])
        return

    async def on_pick(target: discord.Interaction[Any]) -> None:
        values = [str(v) for v in (getattr(target, "data", None) or {}).get("values", [])]
        if not values:
            return
        victim = next((k for k in kingdoms if str(k.id) == values[0]), None)
        if victim is None:
            return
        try:
            theft = await stack.voliere.send_corbeau_theft(
                str(kingdom.id), str(victim.id), str(lord.id), now=_now()
            )
        except Exception as exc:  # noqa: BLE001
            await _failed(target, strings, exc)
            return
        await _record_action(
            stack, lord, "corbeau_civ", kingdom=str(victim.name)
        )
        await _back_to_sommaire(
            target,
            kingdom,
            note=strings["theft_sent"].format(
                kingdom=str(victim.name), ts=int(theft.get("execute_at", 0) or 0)
            ),
        )

    select: discord.ui.Select[Any] = discord.ui.Select(
        custom_id=f"{_NS}:theft:pick",
        placeholder=strings["theft_choose"][:100],
        options=[
            discord.SelectOption(label=str(k.name)[:100], value=str(k.id)[:100])
            for k in kingdoms[:25]
        ],
    )
    select.callback = on_pick  # type: ignore[method-assign, assignment]
    view = discord.ui.View(timeout=600)
    view.add_item(select)
    await open_unique_ephemeral(interaction, view=view)


async def run_action(interaction: discord.Interaction, action: str) -> None:
    """Execute one volière action (simple, select or modal flows).

    The click lands on the illustrated v2 window → defer, then every
    answer flows through the UNIQUE ephemeral window (the house
    pattern, never a raw response against a v2 message). The ONE
    exception: the Pigeon question OPENS A MODAL — the response must
    stay free for ``send_modal`` (no defer on that path)."""
    if action != "pigeon_question":
        await interaction.response.defer(ephemeral=True)
    strings = voliere_strings(_locale_of(interaction))
    lord, kingdom, stack = await _require_lord(interaction, strings)
    if kingdom is None:
        return
    logger.info("kingdom volière: %s runs %s (admin trace)", lord.id, action)
    if action == "corbeau_civ":
        await _theft_flow(interaction, stack, strings, kingdom, lord)
        return
    if action in ("pigeon_civ", "faucon_territory", "faucon_release"):
        await _draw_action(interaction, stack, strings, kingdom, action, lord)
        return
    if action == "corbeau_verify":
        await _verify_flow(interaction, stack, strings, kingdom, lord)
        return
    if action == "corbeau_track":
        await _track_flow(interaction, stack, strings, kingdom, lord)
        return
    if action == "faucon_sabotage":
        await _sabotage_flow(interaction, stack, strings, kingdom, lord)
        return
    if action == "pigeon_question":
        await _question_modal(interaction, stack, strings, kingdom, lord)
        return
    if action == "pigeon_dm":
        await _dm_flow(interaction, stack, strings, kingdom, lord)
        return
    logger.info("kingdom volière: unknown action %s", action)


class VoliereActionButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"{_NS}:act:(?P<action>[a-z_]+)",
):
    """One volière action button — restart-proof (the lieux window)."""

    def __init__(self, action: str, label: str, style: discord.ButtonStyle) -> None:
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"{_NS}:act:{action}",
                style=style,
            )
        )
        self.action = str(action)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        action = str(match["action"])
        strings = voliere_strings(_locale_of(interaction))
        return cls(action, strings.get(f"act_{action}", action), discord.ButtonStyle.secondary)

    async def callback(self, interaction: discord.Interaction) -> None:
        await run_action(interaction, self.action)


# ---------------------------------------------------------------------------
# The theft bells — restart-proof views (events loop + panel)
# ---------------------------------------------------------------------------


def theft_alarm_view(locale: str) -> discord.ui.View:
    """The robbed kingdom's persistent 🛡️ Contester view (no closure)."""
    strings = voliere_strings(locale)
    view = discord.ui.View(timeout=None)
    view.add_item(VoliereTheftButton("contest", "", strings["theft_contest_button"]))
    return view


def theft_prompt_view(locale: str, theft_id: str) -> discord.ui.View:
    """The thief's persistent « Continuer ? » view (no closure)."""
    strings = voliere_strings(locale)
    view = discord.ui.View(timeout=None)
    view.add_item(VoliereTheftButton("continue", theft_id, strings["theft_continue_button"]))
    view.add_item(VoliereTheftButton("stop", theft_id, strings["theft_stop_button"]))
    return view


class VoliereTheftButton(
    discord.ui.DynamicItem[discord.ui.Button[Any]],
    template=rf"kingdom:corbeau:theft:(?P<action>contest|continue|stop):(?P<theft_id>[^:]*)",
):
    """The restart-proof theft button (corbeau-v3, Drasah 15/10).

    ``contest`` lives on the ROBBED side's alarm message; ``continue``
    and ``stop`` live on the thief's prompt message. The theft id rides
    the custom id; the server side re-checks the theft's target before
    any transfer (theft_not_yours otherwise).
    """

    def __init__(self, action: str, theft_id: str, label: str) -> None:
        style = (
            discord.ButtonStyle.danger
            if action == "contest"
            else (
                discord.ButtonStyle.primary
                if action == "continue"
                else discord.ButtonStyle.secondary
            )
        )
        super().__init__(
            discord.ui.Button(
                label=str(label)[:80],
                custom_id=f"kingdom:corbeau:theft:{action}:{str(theft_id)}",
                style=style,
            )
        )
        self.action = str(action)
        self.theft_id = str(theft_id)

    @classmethod
    async def from_custom_id(cls, interaction, item, match, /):  # type: ignore[no-untyped-def]
        strings = voliere_strings(_locale_of(interaction))
        action = str(match["action"])
        label = strings.get(
            f"theft_{action}_button", strings["theft_contest_button"]
        )
        return cls(action, str(match["theft_id"]), label)

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        strings = voliere_strings(_locale_of(interaction))
        lord, kingdom, stack = await _require_lord(interaction, strings)
        if kingdom is None:
            return
        try:
            if self.action == "contest":
                result = await stack.voliere.contest_theft(
                    self.theft_id, str(kingdom.id), now=_now()
                )
                content = strings["theft_contested"].format(points=result["refunded"])
            elif self.action == "continue":
                result = await stack.voliere.continue_theft(
                    self.theft_id, str(kingdom.id), True, now=_now()
                )
                content = strings["theft_continuing"].format(
                    ts=int(result.get("contest_until", 0) or 0),
                    points=int(result.get("stolen", 0) or 0),
                )
            else:  # stop
                result = await stack.voliere.continue_theft(
                    self.theft_id, str(kingdom.id), False, now=_now()
                )
                content = strings["theft_stopped"].format(
                    points=int(result.get("stolen", 0) or 0)
                )
        except Exception as exc:  # noqa: BLE001
            await _failed(interaction, strings, exc)
            return
        from .realm_content import refresh_alliance_panels

        try:
            await refresh_alliance_panels(interaction.client, [str(kingdom.id)])
        except Exception:  # noqa: BLE001
            logger.info("kingdom volière: alliance refresh skipped", exc_info=True)
        await open_unique_ephemeral(interaction, content=content)


def voliere_dynamic_items() -> tuple:
    """The module's restart-proof items (registered by the cog)."""
    return (
        VoliereSlotButton,
        VoliereEspaceButton,
        VoliereBackButton,
        VoliereActionButton,
        VoliereTheftButton,
    )


__all__ = [
    "VoliereActionButton",
    "VoliereBackButton",
    "VoliereEspaceButton",
    "VoliereSlotButton",
    "VoliereTheftButton",
    "run_action",
    "slot_flow",
    "theft_alarm_view",
    "theft_prompt_view",
    "voliere_dynamic_items",
    "voliere_extra_lines",
    "voliere_rows",
    "voliere_state",
    "voliere_strings",
]
