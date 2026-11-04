"""Kingdoms mod — the per-realm salon state views (v1, reference D70).

Every salon of a kingdom category is a **silent state view** (all
announcements go to géopolitique), except the Salle du Conseil —
the kingdom's only private discussion salon, which stays empty.

Each view is a Components V2 panel (Drasah's choice, 2026-10-10: same
visual language as the admin panels — container, accent colour,
separators), marked and re-deployed in place (the ``panel_messages``
contract): re-deploys, approvals and resets never duplicate.

Phase rule (Drasah's game design, 2026-10-10): while the season is in
``setup``, NOTHING random is revealed — the 🗺️ Territoire salon shows
a "distribution at season start" placeholder and the 📜 Alliances one
carries its own (in kingdom_realms). Once the admin starts the season
(``started``), the real content replaces the placeholders.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from kingdoms.mods.kingdoms.game_clock import game_now
from kingdoms.mods.kingdoms.panel_messages import (
    NO_MENTIONS,
    channel_messages,
    message_text,
    message_text_squashed,
    view_text,
)

if TYPE_CHECKING:
    import discord

logger = logging.getLogger("kingdoms.kingdom_realm_content")

VIEW_MARKER_PREFIX = "kingdoms:realm:view"

_PARIS_TZ = "Europe/Paris"


def _lock_until_label(until: int, strings: dict[str, str]) -> str:
    """Format one lock deadline as a readable Paris time (Drasah 2026-10-11).

    An end TIME never goes stale — unlike a remaining duration, the
    label stays true for ever, and it names the exact moment the lord
    can fight again.
    """
    stamp = datetime.fromtimestamp(until, tz=ZoneInfo(_PARIS_TZ))
    days = str(strings.get("lock_days", "")).split("|")
    day = days[stamp.weekday()] if stamp.weekday() < len(days) else ""
    return str(strings.get("lock_time_fmt", "{0} {1}h{2}")).format(
        day, f"{stamp.hour:02d}", f"{stamp.minute:02d}"
    )


def _strings(locale: str) -> dict[str, str]:
    """Return the FR/EN view strings (designer-authored pattern)."""
    if str(locale).lower().startswith("fr"):
        return {
            "overview_title": "🏰 {0}",
            "members": "Effectif",
            "members_line": "👑 {0} + **{1}** seigneur(s) — {2} membre(s)",
            "no_king": "Roi non enrôlé",
            "alliances_panel_title": "📜 Alliances — {0}",
            # alliances-panel-v4 (Drasah 26/10) : 🤝 « saison antérieure »
            # disparaît — après reset TOUT est défini et traçable (le 🤝 du
            # moteur reste un fallback silencieux pour les mains pré-registre).
            "alliances_panel_legend": (
                "Légende : 🎲 Draft starter · 🗺️ Condition · 💍 Mariage ·"
                " 👑 Royal · 📜 Mercenaire"
            ),
            "alliances_panel_badges": (
                "-# Chaque blason porte son NOM et l'🎲 🗺️ 💍 👑 📜 de sa provenance"
            ),
            "alliances_panel_hand": "-# main : {0}",
            "alliances_panel_signature": "main : {0}",
            "alliances_panel_intro_hand": (
                "Ici se trouve ta main — les civilisations que tu as le droit"
                " d'utiliser actuellement durant tes confrontations !"
            ),
            "alliances_panel_intro_rules": (
                "Tu commences avec **8 civilisations** distribuées aléatoirement,"
                " mais attention : tes alliances évoluent en fonction de tes conquêtes,"
                " de tes mariages et de tes contrats avec des mercenaires."
            ),
            "alliances_panel_intro_cycle": (
                "À chaque passage au prochain cycle, tes alliances s'actualisent !"
                " Le bouton 📅 Prochain cycle indique quand a lieu le prochain passage"
                " et projette ta main."
            ),
            "alliances_panel_married_line": "💍 {0} — {1}",
            "alliances_panel_merc_line": "⚔️ **{0}** — {1} ({2} usage(s) de draft)",
            "alliances_panel_empty": (
                "Aucune civilisation en main — les alliances arrivent par le jeu"
                " (conditions, mariages, Chef Mercenaire)."
            ),
            "alliances_panel_help": (
                "-# ❓ Conditions d'alliance : 📜 Scriptorium → rubrique Diplomatie."
            ),
            "alliances_panel_help_named": (
                "-# ❓ Conditions d'obtention des civilisations : {0} → rubrique « 🤝 Diplomatie »."
            ),
            "alliances_btn_cycle": "📅",
            "alliances_btn_next": "📅 Prochain cycle",
            "alliances_btn_locked": "🚫 Verrouillées",
            "alliances_btn_history": "📖 Historique",
            "alliances_btn_durations": "⏳ Durées",
            "alliances_btn_names": "🔤 Noms",
            "alliances_kingdom_none": "❌ Le royaume de ce salon est introuvable.",
            "alliances_no_data": "❌ Aucune donnée d'alliance disponible pour le moment.",
            "alliances_next_title": "🔭 Prochain cycle — {0}",
            "alliances_next_kept": "✅ Gardées : {0}",
            "alliances_next_arriving": "📥 Arrivent : {0}",
            "alliances_next_dropping": "📤 Quitteront la main : {0}",
            "alliances_next_elsewhere": "💍 Déjà mariée ailleurs : {0}",
            "alliances_next_intro": (
                "Projection de ta main au prochain cycle d'alliances — ce qui sera gardé, ce qui arrive, ce qui part."
            ),
            "alliances_cycle_title": "📅 Prochain cycle — {0}",
            "alliances_cycle_line": "Passage du prochain cycle dans **{0}**",
            "alliances_cycle_hint": (
                "-# À ce moment tes alliances s'actualisent — 🔭 Prochain cycle en donne la projection."
            ),
            "alliances_cycle_none": "❌ Aucune saison active — le prochain cycle n'est pas encore planifié.",
            "alliances_locked_title": "🚫 Verrouillées par les mariages des autres royaumes — {0}",
            "alliances_locked_line": "🚫 **{0}** — {1}",
            "alliances_locked_cond_maps": "cartes requises : {0}",
            "alliances_locked_cond_count": "{0} territoire(s) requis",
            "alliances_locked_cond_none": "condition non remplie",
            "alliances_locked_married": "mariée à un autre royaume (exclusivité)",
            "alliances_locked_none": "Aucune civilisation verrouillée — tout le catalogue est jouable.",
            "alliances_locked_intro": (
                "💍 Uniquement les civilisations mariées à d'autres royaumes —"
                " tes propres mariages restent à toi."
            ),
            "alliances_locked_none_married": (
                "Aucune civilisation verrouillée par mariage — tout le catalogue reste jouable."
            ),
            "alliances_history_title": "📖 Historique — {0}",
            "alliances_history_line": "{0} **{1}** — {2}",
            "alliances_history_none": "Aucune acquisition enregistrée pour le moment.",
            "alliances_history_none_lost": "Aucune civilisation perdue — la main est intacte.",
            "alliances_durations_title": "⏳ Durées — {0}",
            "alliances_durations_line": "{0} **{1}**",
            "alliances_durations_since": "détenue depuis {0}",
            "alliances_durations_none": "Aucune civilisation en main.",
            "alliances_names_title": "🔤 Noms — {0}",
            "alliances_names_line": "• **{0}** — techtree : {1}",
            "alliances_names_none": "Aucune civilisation en main.",
            "treasury": "Trésorerie",
            "territories": "Territoires",
            "civilizations": "Civilisations",
            "marriages": "Mariages actifs",
            "patrol": "Patrouille",
            "royal_guard": "Garde Royal",
            "parish": "Paroisse",
            "parish_placeholder": "⛪ Chapelle (palier 1/3) — paliers D64 à venir",
            "ledger_button": "🏛️ Chambre des comptes",
            "settings_button": "⚙️ Paramètres utilisateur",
            "settings_footer": "-# ⚙️ Réglages hors-jeu — ceci ne fait pas partie du jeu.",
            "yes": "oui",
            "no": "non",
            "none_f": "aucune",
            "none_m": "aucun",
            "unknown": "inconnu",
            "roster_title": "🎖️ Seigneurs — {0}",
            "roster_empty": "Aucun membre enrôlé pour le moment.",
            "left_badge": "❌ parti",
            "patrol_title": "🧱 Remparts — {0}",
            "patrol_window": (
                "🔄 Redéfinition des créneaux : uniquement pendant le Jour du"
                " Seigneur (dimanche 23h30 → lundi 10h00)."
            ),
            "patrol_slot": "{0:02d}h00 → {1:02d}h00 (chaque jour)",
            "remparts_state_missing": (
                "❌ Vous ne disposez pas de patrouille [{0}/2] —"
                " achat au Marché (2 ⚙️)"
            ),
            "remparts_state_unplaced": (
                "⚠️ Vous disposez d'une patrouille mais vous ne l'avez"
                " pas encore paramétrée"
            ),
            "remparts_state_active": (
                "⏲ Votre patrouille [{0}/2] est bien active entre"
                " {1:02d}h00 et {2:02d}h00"
            ),
            "remparts_info_button": "🔎 En savoir plus",
            "remparts_state_button": "✅ Compris",
            "remparts_guard": "Gardes Royaux",
            "remparts_guard_none": "aucune",
            "remparts_guard_line": "✅ {0} — protégée jusqu'à {1}",
            "remparts_guard_stock": "En réserve : {0}",
            "remparts_guard_button": "💂 Garde Royal",
            "remparts_patrouille_button": "👣 Patrouille {0}",
            "remparts_patrouille_hub_button": "👣 Patrouille",
            "remparts_patrouille_hub_text": "Choisis le créneau de patrouille à régler :",
            # patrouille-garde-fiche-v1 (Drasah 04/11) : la fiche-carte
            # Patrouille/Garde Royale (architecture Jeu d'armes).
            "patrouille_card_title": "👣 Patrouille",
            "patrouille_card_desc": (
                "**Effet :**\n"
                "Pose un créneau quotidien de patrouille de 2h permettant, "
                "durant ce laps de temps, d'être protégé de tout type "
                "d'attaque (Classique, Exceptionnel et Technologique).\n"
                "Le créneau est redéfinissable durant le Jour du Seigneur "
                "({lords_day}).\n"
                "Si le niveau de votre IA est au niveau max (Jeu d'armes), "
                "votre patrouille se renforce d'une heure, offrant 3h au "
                "lieu de 2h.\n\n"
                "Lorsqu'une patrouille est obtenue, elle est acquise pour "
                "toute la saison, ne se consomme pas et est limitée à deux "
                "par royaume.\n\n"
                "⚠ La patrouille n'annule pas une attaque déjà déclarée."
            ),
            "patrouille_use_button": "✅ Utiliser",
            # patrouille-fiche-v3 (Drasah 04/11) : cockpit 4 boutons (état +
            # ✏️ Modifier par créneau), confirmation ✅ Valider/❌ Annuler,
            # créneau EFFECTIF affiché (3h si Renforcée).
            "patrouille_modify_button": "✏️ Modifier",
            "patrouille_slot_status": "Patrouille [{0}/2] — {1}",
            "patrouille_slot_unset": "non réglée",
            "patrouille_slot_locked": "non débloquée (Marché)",
            "patrouille_confirm_text": (
                "Patrouille {0} — créneau {1:02d}h00 → {2:02d}h00 (chaque jour).\n"
                "Valide pour figer le créneau : il ne changera plus avant "
                "le prochain Jour du Seigneur."
            ),
            "patrouille_validate_button": "✅ Valider",
            "patrouille_cancel_button": "❌ Annuler",
            "patrouille_lords_day_closed": (
                "⏳ La fenêtre du Jour du Seigneur est terminée — le "
                "créneau ne peut plus être modifié."
            ),
            # patrouille-fiche-v2 (Drasah 04/11) : rappel dynamique de la
            # fenêtre du Jour du Seigneur greffé dans la fiche.
            "patrouille_lords_day_active": "fenêtre en cours, jusqu'au {0}",
            "patrouille_lords_day_next": "prochaine fenêtre : {0} → {1}",
            "patrouille_lords_day_beta": (
                "fenêtre courte ouverte après chaque bascule de cycle"
            ),
            "patrouille_lords_day_plain": (
                "la fenêtre hebdomadaire annoncée par le bot"
            ),
            "garde_card_title": "💂 Garde Royal",
            "garde_card_desc": (
                "**Effet :**\n"
                "Permet de protéger une map acquise à son Royaume durant 12h "
                "d'une attaque Classique, Exceptionnelle et Technologique.\n"
                "Il n'est pas possible d'annuler une déclaration d'attaque "
                "subie, et donc de poser un Garde Royal sur un territoire "
                "attaqué.\n\n"
                "💂 Garde Royal disponible : **{0}** (réserve)"
            ),
            "garde_use_button": "✅ Utiliser",
            "tech_card_cancel_button": "❌ Annuler",
            "remparts_place_guard_choose": "💂 Choisis la map à protéger :",
            "remparts_guard_wizard_stock": "💂 Garde Royal disponible : **{0}** (réserve)",
            "remparts_guard_wizard_line": "Choisis la map à protéger pour une durée de 12h :",
            "remparts_guard_wizard_chosen": "💂 Map choisie : **{0}**",
            "remparts_guard_validate_button": "✅ Valider",
            "remparts_guard_modify_button": "✏️ Modifier",
            "remparts_guard_cancel_button": "❌ Annuler",
            "remparts_guard_no_stock": "⚠️ Aucun Garde Royal en réserve — le Marché en vend.",
            "remparts_guard_placed": (
                "💂 Le Garde Royal protège **{0}** jusqu'au {1} (heure de Paris)."
            ),
            # garde-royale-fiche-v2 (Drasah 04/11) : refus explicite d'un
            # territoire sous attaque déclarée (💥 dans le sélecteur).
            "remparts_guard_attacked": (
                "💥 Vous ne pouvez pas protéger ce territoire "
                "actuellement : il est déclaré attaqué."
            ),
            "remparts_patrouille_placed": (
                "✅ Patrouille {0} posée : {1:02d}h00 → {2:02d}h00 (chaque jour)."
            ),
            "traquenard_button": "🪤 Utiliser un Traquenard",
            "traquenard_fiche_title": "🪤 Traquenard",
            "traquenard_fiche_desc": (
                "**Effet**\n"
                "À l'usage : choisissez un Royaume, l'IA affrontée devient **Très"
                " facile**"
                " durant un laps de temps de 2h au moment où Traquenard est activé"
                " (chaque activation cumulée repousse la fin de 2h).\n"
                "Augmente les délais de TOUS les verrouillages du royaume ciblé"
                " de **+2h** uniquement au moment où Traquenard est activé"
                " (mariages, exploration et boisson de la taverne)."
            ),
            "traquenard_forces_button": "👁️ Voir les forces IA",
            "traquenard_go_button": "🪤 Traquenard",
            "traquenard_activate_button": "⚔️ Activer",
            "traquenard_cancel_button": "❌ Annuler",
            "traquenard_forces_title": "👁️ Forces IA",
            # ia-base-zero-v1 (Drasah 03/11) : le moteur EST l'échelle
            # Drasah (base 0 — une IA neuve = « 0/5 Très facile », cinq
            # Jeux d'armes = « 5/5 Expert »), niveau EN TOUTES LETTRES
            # (0 Très facile · 1 Standard · 2 Intermédiaire · 3 Difficile
            # · 4 Plus difficile · 5 Expert), timer en heures+minutes.
            "traquenard_ai_levels": (
                "Très facile|Standard|Intermédiaire|Difficile|Plus difficile|Expert"
            ),
            "traquenard_forces_line": "🏰 **{name}** — IA : {level} {ai}/5",
            "traquenard_forces_active": "🪤 état affaibli — se termine dans {time}",
            "traquenard_forces_none": "Aucun royaume adverse à afficher.",
            "traquenard_choose_title": "Choisir le royaume sur lequel utiliser Traquenard",
            "traquenard_select_placeholder": "Sélectionner un royaume",
            "traquenard_selected": "🎯 Cible : **{name}** (IA : {ai})",
            "traquenard_validate_button": "✅ Valider",
            "traquenard_modify_button": "📝 Modifier",
            "traquenard_choose": "🪤 Contre quel royaume activer le Traquenard ?",
            "traquenard_hours": "heures",
            "traquenard_minutes": "minutes",
            "traquenard_done": (
                "🪤 Traquenard activé contre **{kingdom}** — l'IA de défense devient"
                " très facile (0/5) jusqu'à {time} (fenêtre cumulée de 2h) et les verrous"
                " vivants prennent {lock}."
            ),
            "traquenard_failed": "❌ {message}",
            "traquenard_no_target": "❌ Aucun royaume adverse à cibler.",
            # traquenard-note-v2 (Drasah 03/11) : « Votre Royaume a
            # utilisé un Traquenard contre le Royaume X — l'IA de
            # défense est très facile pour un délai {duration}. »
            "traquenard_channel_note": (
                "🪤 Votre Royaume a utilisé un Traquenard contre le Royaume"
                " **{target}** — l'IA de défense est très facile pour un délai"
                " {duration}."
            ),
            "traquenard_dm_tavern": (
                "🍺 Vous relevez un goût étrange dans votre boisson… Vous avez été"
                " drogué ! {lock} de verrouillage (Traquenard)."
            ),
            "traquenard_dm_marriage": (
                "💍 Une rumeur se fait entendre que vous seriez menacé d'assassinat"
                " par un malotru… Cela retarde votre mariage. {lock} de verrouillage"
                " (Traquenard)."
            ),
            "traquenard_dm_exploration": (
                "🧭 Des pirates font face à vous, vous ralentissant et vous forçant"
                " à être prudent. {lock} de verrouillage (Traquenard)."
            ),
            "remparts_ai_intro": (
                "🤖 **Bot de défense (IA):**\n"
                "Si aucun seigneur ne défend votre royaume, votre bot IA prend le"
                " relais de votre défense automatiquement. Vous pouvez augmenter le"
                " niveau de votre IA en l'entraînant via l'achat d'un Jeu d'armes au"
                " Marché ; lorsque votre IA est au niveau max, cela améliore votre"
                " Patrouille (Patrouilles Renforcées, créneaux de 3h)."
            ),
            "remparts_ai_level": "🤖 Niveau de votre IA : **{0}/5 {1}**",
            "remparts_reinforced": "💪 Patrouilles Renforcées (créneaux de 3h)",
            "remparts_patrouille_intro": (
                "🛡️ **Patrouille :**\n"
                "Permet de vous protéger d'une attaque normale, exceptionnelle et"
                " technologique, sur un créneau de 2h fixe dans une journée — cela"
                " s'applique donc tous les jours de la semaine. Si votre patrouille"
                " est améliorée, le créneau de protection passe à 3h. Limite de 2"
                " patrouilles par royaume, une patrouille est utilisable pour la"
                " durée de toute la saison."
            ),
            "remparts_garde_intro": (
                "💂 **Gardes Royaux :**\n"
                "Permet de protéger un territoire de toute attaque — normale,"
                " exceptionnelle et technologique — pour une durée de 12h. Le"
                " Garde Royal se consomme."
            ),
            "remparts_patrouille_title": "👣 **Patrouille :**",
            "remparts_patrouille_title_reinforced": "👣 **Patrouilles Renforcées :**",
            "remparts_garde_title": "💂 **Garde Royal :**",
            "remparts_garde_owned_one": "Vous disposez de {0} garde royal",
            "remparts_garde_owned_many": "Vous disposez de {0} gardes royaux",
            "remparts_garde_owned_none": "Vous ne disposez d'aucun Garde Royal",
            "roster_exploring": "🗺️ exploration jusqu'à {0}",
            "roster_marriage_lock": "🔒 verrou mariage jusqu'à {0}",
            "roster_ffa_lock": "🚫 FFA verrouillé jusqu'à {0}",
            "remparts_open_button": "🧱 Remparts",
            "not_lord": "Tu ne fais partie d'aucun royaume.",
            "seigneurie_open_button": "🛡️ Seigneurie",
            "territory_title": "🗺️ Territoire — {0}",
            "territory_count": "{0} territoire(s)",
            "territory_empty": "Aucun territoire pour le moment.",
            # restructuration-serveur-v1 c (Drasah 19/10): le salon
            # Patrouille disparaît — le niveau de l'IA vit ici.
            "gaia_ai_level": "🤖 Niveau de l'IA Gaïa : {0}/5",
            "territory_guard": "💂 protégée jusqu'à {0}",
            "territory_note": "La Corruption transfère le territoire de salon (D58).",
            "territory_pending_body": (
                "La carte reste secrète pour l'instant.\n"
                "Au démarrage de la saison, chaque royaume recevra ses "
                "territoires par tirage aléatoire."
            ),
            "church_title": "⛪ Paroisse — {0} · ⛪ {1} · 💍 {2} · 💰 {3}",
            "church_active": "Mariages actifs",
            "church_none": "Aucun mariage actif.",
            "church_badge_locked": "💍 {0} — {1} · 🔒 verrou jusqu'à {2}",
            "church_badge_free": "💍 {0} — {1} · ✅ verrou levé",
            "church_badge_royal_locked": "💍 {0} — 👑 Reine {1} · 🔒 verrou jusqu'à {2}",
            "church_badge_royal_free": "💍 {0} — 👑 Reine {1} · ✅ verrou levé",
            "church_singles": "Célibataires",
            "church_singles_none": "Aucun seigneur célibataire.",
            "church_tier_line": "Palier : {0} ({1}/{2}) — Offrande : {3} ⚙️",
            "church_lock_line": "Verrou mariage classique : {0}h",
            "church_royal_lock_line": "Verrou mariage royal (Roi) : {0}h",
            "church_marry_button": "💍 Se marier",
            "church_arrange_button": "💒 Mariage arrangé ({0})",
            "church_upgrade_button": "⛪ Améliorer → {0} ({1} ⚙️)",
            "church_upgrade_max": "⛪ Cathédrale — palier maximal",
            "parish_line": "{0} — palier {1}/{2}",
            "territory_chantier": "⏳ Lieu Sacrée — chantier jusqu'au {0}",
            "territory_sacred": "⛪ SACRÉ — à vie",
            "church_chantier_line": "⏳ Lieu Sacrée en chantier sur **{0}** — verdict le {1} (Paris)",
            "church_sacred_line": "⛪ Lieu Sacrée SACRÉ sur **{0}** — immunisé à vie",
            "church_household_palier": "✨ Notre {0}",
            "church_household": "💒 Les Fidèles du Royaume",
            "church_bachelor": "🎖️ {0} — célibataire · prêt à se marier 💍",
            "church_ladder_title": "🔭 Aperçu des paliers",
            "church_ladder_current": "●",
            "church_ladder_other": "▸",
            "church_ladder_line": "{0} {1} — {2} ⚙️ · verrou {3}h · offrande +{4} ⚙️",
            "church_ladder_sacree": " · ⛪ Lieu Sacrée",
            "church_legend_lock": (
                "-# 🔒 Verrou : un seigneur fraîchement marié ne peut ni"
                " attaquer ni défendre pendant quelques heures (24h · 12h · 6h"
                " selon le palier, doublé pour un mariage royal)."
            ),
            "church_legend_offering": (
                "-# 🕯️ Offrande : à chaque mariage célébré, la Paroisse verse"
                " des points de technologie au trésor du royaume."
            ),
            "church_legend_token": (
                "-# 💰 Jeton : acheté au Marché (3 ⚙️), permet un mariage"
                " arrangé sans consommer de point de mariage."
            ),
            "church_legend_sacree": (
                "-# ⛪ Lieu Sacrée (Cathédrale) : le royaume consacre un"
                " territoire — immunisé contre toute action technologique et"
                " insensible à la conquête pendant 72h ; seule une attaque"
                " classique peut le disputer."
            ),
            "lock_days": "lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche",
            "lock_time_fmt": "{0} {1}h{2}",
        }
    return {
        "overview_title": "🏰 {0}",
        "members": "Members",
        "members_line": "👑 {0} + **{1}** lord(s) — {2} member(s)",
        "no_king": "King not enrolled",
        "alliances_panel_title": "📜 Alliances — {0}",
        # alliances-panel-v4: 🤝 "earlier season" is gone — after a
        # reset everything is defined and traceable.
        "alliances_panel_legend": (
            "Legend: 🎲 Starter draft · 🗺️ Condition · 💍 Marriage ·"
            " 👑 Royal · 📜 Mercenary"
        ),
        "alliances_panel_badges": (
            "-# Every crest wears its NAME and its origin 🎲 🗺️ 💍 👑 📜"
        ),
        "alliances_panel_married_line": "💍 {0} — {1}",
        "alliances_panel_hand": "-# hand: {0}",
        "alliances_panel_signature": "hand: {0}",
        "alliances_panel_intro_hand": (
            "Here is your hand — the civilizations you may use right now"
            " in your confrontations!"
        ),
        "alliances_panel_intro_rules": (
            "You start with **8 civilizations** dealt at random, but beware:"
            " your alliances evolve with your conquests, your marriages and"
            " your mercenary contracts."
        ),
        "alliances_panel_intro_cycle": (
            "At every cycle switch your alliances refresh! The 📅 Next cycle"
            " button shows when the next switch lands and projects your hand."
        ),
        "alliances_panel_merc_line": "⚔️ **{0}** — {1} ({2} draft use(s))",
        "alliances_panel_empty": (
            "No civilization in hand — alliances arrive through play"
            " (conditions, marriages, Chief Mercenary)."
        ),
        "alliances_panel_help": "-# ❓ Alliance conditions: 📜 Scriptorium → Diplomatie rubric.",
        "alliances_panel_help_named": (
            "-# ❓ How to obtain the civilizations: {0} → « 🤝 Diplomatie » rubric."
        ),
        "alliances_btn_cycle": "📅",
        "alliances_btn_next": "📅 Next cycle",
        "alliances_btn_locked": "🚫 Locked",
        "alliances_btn_history": "📖 History",
        "alliances_btn_durations": "⏳ Durations",
        "alliances_btn_names": "🔤 Names",
        "alliances_kingdom_none": "❌ This salon's kingdom cannot be found.",
        "alliances_no_data": "❌ No alliance data available right now.",
        "alliances_next_title": "🔭 Next cycle — {0}",
        "alliances_next_kept": "✅ Kept: {0}",
        "alliances_next_arriving": "📥 Arriving: {0}",
        "alliances_next_dropping": "📤 Leaving the hand: {0}",
        "alliances_next_elsewhere": "💍 Married elsewhere: {0}",
        "alliances_next_intro": (
            "Projection of your hand at the next alliance cycle — kept, arriving, leaving."
        ),
        "alliances_cycle_title": "📅 Next cycle — {0}",
        "alliances_cycle_line": "Next cycle switch in **{0}**",
        "alliances_cycle_hint": (
            "-# At that moment your alliances refresh — 🔭 Next cycle shows the projection."
        ),
        "alliances_cycle_none": "❌ No active season — the next cycle is not scheduled yet.",
        "alliances_locked_title": "🚫 Locked by other kingdoms' marriages — {0}",
        "alliances_locked_line": "🚫 **{0}** — {1}",
        "alliances_locked_cond_maps": "required maps: {0}",
        "alliances_locked_cond_count": "{0} territory(/ies) required",
        "alliances_locked_cond_none": "condition not met",
        "alliances_locked_married": "married to another kingdom (exclusivity)",
        "alliances_locked_none": "No locked civilization — the whole catalogue is playable.",
        "alliances_locked_intro": (
            "💍 Only the civilizations married to other kingdoms — your own marriages stay yours."
        ),
        "alliances_locked_none_married": (
            "No civilization locked by marriage — the whole catalogue stays playable."
        ),
        "alliances_history_title": "📖 History — {0}",
        "alliances_history_line": "{0} **{1}** — {2}",
        "alliances_history_none": "No acquisition recorded yet.",
        "alliances_history_none_lost": "No lost civilization — the hand is intact.",
        "alliances_durations_title": "⏳ Durations — {0}",
        "alliances_durations_line": "{0} **{1}**",
        "alliances_durations_since": "held since {0}",
        "alliances_durations_none": "No civilization in hand.",
        "alliances_names_title": "🔤 Names — {0}",
        "alliances_names_line": "• **{0}** — techtree: {1}",
        "alliances_names_none": "No civilization in hand.",
        "treasury": "Treasury",
        "territories": "Territories",
        "civilizations": "Civilizations",
        "marriages": "Active marriages",
        "patrol": "Patrol",
        "royal_guard": "Royal Guard",
        "parish": "Parish",
        "parish_placeholder": "⛪ Chapel (tier 1/3) — D64 tiers coming soon",
        "ledger_button": "🏛️ Chambre des comptes",
        "settings_button": "⚙️ User settings",
        "settings_footer": "-# ⚙️ Out-of-game settings — this is not part of the game.",
        "yes": "yes",
        "no": "no",
        "none_f": "none",
        "none_m": "none",
        "unknown": "unknown",
        "roster_title": "🎖️ Lords — {0}",
        "roster_empty": "No member enrolled yet.",
        "left_badge": "❌ left",
        "patrol_title": "🧱 Remparts — {0}",
        "patrol_window": (
            "🔄 Window redefinition: only during the Lord's Day"
            " (Sunday 23:30 → Monday 10:00)."
        ),
        "patrol_slot": "{0:02d}:00 → {1:02d}:00 (daily)",
        "remparts_state_missing": (
            "❌ You have no patrol [{0}/2] — purchase one at the"
            " Market (2 ⚙️)"
        ),
        "remparts_state_unplaced": (
            "⚠️ You own a patrol but it is not configured yet"
        ),
        "remparts_state_active": (
            "⏲ Your patrol [{0}/2] is active between {1:02d}:00"
            " and {2:02d}:00"
        ),
        "remparts_info_button": "🔎 Learn more",
        "remparts_state_button": "✅ Got it",
        "remparts_guard": "Royal Guards",
        "remparts_guard_none": "none",
        "remparts_guard_line": "✅ {0} — shielded until {1}",
        "remparts_guard_stock": "In reserve: {0}",
        "remparts_guard_button": "💂 Royal Guard",
        "remparts_patrouille_button": "👣 Patrol {0}",
        "remparts_patrouille_hub_button": "👣 Patrol",
        "remparts_patrouille_hub_text": "Choose the patrol slot to set:",
        # patrouille-garde-fiche-v1 (Drasah 04/11): the Patrouille /
        # Garde Royale fiche-cards (Jeu d'armes architecture).
        "patrouille_card_title": "👣 Patrol",
        "patrouille_card_desc": (
            "**Effect:**\n"
            "Sets a daily 2h patrol window, during which the kingdom is "
            "protected from every attack type (Classic, Exceptional and "
            "Technological).\n"
            "The window can be redefined during the Lord's Day "
            "({lords_day}).\n"
            "If your AI is at max level (Jeu d'armes), the patrol is "
            "reinforced by one hour, offering 3h instead of 2h.\n\n"
            "Once obtained, a patrol is acquired for the whole season, is "
            "not consumed and is limited to two per kingdom.\n\n"
            "⚠ The patrol does not cancel an attack already declared."
        ),
        "patrouille_use_button": "✅ Use",
        # patrouille-fiche-v3 (Drasah 04/11): 4-button cockpit (status +
        # ✏️ Modify per slot), ✅ Confirm/❌ Cancel face, EFFECTIVE window
        # shown (3h when Reinforced).
        "patrouille_modify_button": "✏️ Modify",
        "patrouille_slot_status": "Patrol [{0}/2] — {1}",
        "patrouille_slot_unset": "not set",
        "patrouille_slot_locked": "not unlocked (Market)",
        "patrouille_confirm_text": (
            "Patrol {0} — window {1:02d}:00 → {2:02d}:00 (daily).\n"
            "Confirm to freeze the window: it will not change again "
            "before the next Lord's Day."
        ),
        "patrouille_validate_button": "✅ Confirm",
        "patrouille_cancel_button": "❌ Cancel",
        "patrouille_lords_day_closed": (
            "⏳ The Lord's Day window is closed — the window can no "
            "longer be changed."
        ),
        # patrouille-fiche-v2 (Drasah 04/11): dynamic Lord's Day window
        # reminder grafted into the card.
        "patrouille_lords_day_active": "window open until {0}",
        "patrouille_lords_day_next": "next window: {0} → {1}",
        "patrouille_lords_day_beta": (
            "short window opened after each cycle switch"
        ),
        "patrouille_lords_day_plain": (
            "the weekly window announced by the bot"
        ),
        "garde_card_title": "💂 Royal Guard",
        "garde_card_desc": (
            "**Effect:**\n"
            "Shields a map owned by your Kingdom for 12h against Classic,"
            " Exceptional and Technological attacks.\n"
            "A declared attack cannot be cancelled, so a Royal Guard"
            " cannot be placed on a territory under attack.\n\n"
            "💂 Royal Guard available: **{0}** (in reserve)"
        ),
        "garde_use_button": "✅ Use",
        "tech_card_cancel_button": "❌ Cancel",
        "remparts_place_guard_choose": "💂 Choose the map to shield:",
        "remparts_guard_wizard_stock": "💂 Royal Guard available: **{0}** (in reserve)",
        "remparts_guard_wizard_line": "Choose the map to shield for 12 hours:",
        "remparts_guard_wizard_chosen": "💂 Chosen map: **{0}**",
        "remparts_guard_validate_button": "✅ Confirm",
        "remparts_guard_modify_button": "✏️ Change",
        "remparts_guard_cancel_button": "❌ Cancel",
        "remparts_guard_no_stock": "⚠️ No Royal Guard in reserve — the Market sells them.",
        "remparts_guard_placed": (
            "💂 The Royal Guard shields **{0}** until {1} (Paris time)."
        ),
        # garde-royale-fiche-v2 (Drasah 04/11): explicit refusal for a
        # territory under a declared attack (💥 in the selector).
        "remparts_guard_attacked": (
            "💥 You cannot shield this territory right now: an attack"
            " is declared on it."
        ),
        "remparts_patrouille_placed": (
            "✅ Patrol {0} placed: {1:02d}:00 → {2:02d}:00 (daily)."
        ),
            "traquenard_button": "🪤 Use a Traquenard",
            "traquenard_fiche_title": "🪤 Traquenard",
            "traquenard_fiche_desc": (
                "**Effect**\n"
                "On use: choose a Kingdom, the opposing AI turns **Very easy**"
                " for a"
                " 2h lapse of time at the moment the Traquenard is activated"
                " (each stacked activation pushes the end 2h further).\n"
                "Adds **+2h** to EVERY lockout of the targeted kingdom, only at"
                " the moment the Traquenard is activated (marriages, exploration"
                " and tavern drink)."
            ),
            "traquenard_forces_button": "👁️ View AI forces",
            "traquenard_go_button": "🪤 Traquenard",
            "traquenard_activate_button": "⚔️ Activate",
            "traquenard_cancel_button": "❌ Cancel",
            "traquenard_forces_title": "👁️ AI forces",
            "traquenard_ai_levels": (
                "Very easy|Standard|Intermediate|Hard|Harder|Expert"
            ),
            "traquenard_forces_line": "🏰 **{name}** — AI: {level} {ai}/5",
            "traquenard_forces_active": "🪤 weakened — ends in {time}",
            "traquenard_forces_none": "No adversary kingdom to display.",
            "traquenard_choose_title": "Choose the kingdom to use the Traquenard on",
            "traquenard_select_placeholder": "Select a kingdom",
            "traquenard_selected": "🎯 Target: **{name}** (AI: {ai})",
            "traquenard_validate_button": "✅ Confirm",
            "traquenard_modify_button": "📝 Change",
            "traquenard_choose": "🪤 Against which kingdom should the Traquenard be activated?",
            "traquenard_hours": "hours",
            "traquenard_minutes": "minutes",
            "traquenard_done": (
                "🪤 Traquenard activated against **{kingdom}** — the defense AI turns"
                " very easy (0/5) until {time} (2h stacked window) and living locks gain {lock}."
            ),
            "traquenard_failed": "❌ {message}",
            "traquenard_no_target": "❌ No adversary kingdom to target.",
            "traquenard_channel_note": (
                "🪤 Your Kingdom has used a Traquenard against the Kingdom"
                " **{target}** — the defense AI is very easy for a duration of"
                " {duration}."
            ),
            "traquenard_dm_tavern": (
                "🍺 You notice a strange taste in your drink… You have been"
                " drugged! {lock} of lockout (Traquenard)."
            ),
            "traquenard_dm_marriage": (
                "💍 A rumour spreads that a knave is threatening to assassinate"
                " you… This delays your wedding. {lock} of lockout (Traquenard)."
            ),
            "traquenard_dm_exploration": (
                "🧭 Pirates stand in your way, slowing you down and forcing you"
                " to be careful. {lock} of lockout (Traquenard)."
            ),
            "remparts_ai_intro": (
                "🤖 **Defense bot (AI):**\n"
                "If no lord defends your kingdom, your AI bot automatically takes"
                " over your defense. You can raise your AI's level by training it —"
                " buy a Set of Arms at the Market; once your AI reaches its max"
                " level, it improves your Patrol (Reinforced Patrols, 3h slots)."
            ),
            "remparts_ai_level": "🤖 Your AI level: **{0}/5 {1}**",
            "remparts_reinforced": "💪 Reinforced Patrols (3h slots)",
            "remparts_patrouille_intro": (
                "🛡️ **Patrol:**\n"
                "Shields your kingdom from a normal, exceptional and technological"
                " attack on a fixed 2h slot each day — every day of the week. An"
                " improved patrol widens the protection slot to 3h. Limit of 2"
                " patrols per kingdom, usable for the whole season."
            ),
            "remparts_garde_intro": (
                "💂 **Royal Guards:**\n"
                "Shields one territory from every attack — normal, exceptional"
                " and technological — for 12 hours. The Royal Guard is consumed."
            ),
            "remparts_patrouille_title": "👣 **Patrol:**",
            "remparts_patrouille_title_reinforced": "👣 **Reinforced Patrols:**",
            "remparts_garde_title": "💂 **Royal Guard:**",
            "remparts_garde_owned_one": "You own {0} Royal Guard",
            "remparts_garde_owned_many": "You own {0} Royal Guards",
            "remparts_garde_owned_none": "You do not own any Royal Guard",
            "roster_exploring": "🗺️ exploring until {0}",
            "roster_marriage_lock": "🔒 marriage lock until {0}",
            "roster_ffa_lock": "🚫 FFA locked until {0}",
            "remparts_open_button": "🧱 Ramparts",
            "seigneurie_open_button": "🛡️ Lordship",
            "not_lord": "You are not part of any kingdom.",
        "territory_title": "🗺️ Territory — {0}",
        "territory_count": "{0} territor(y|ies)",
        "territory_empty": "No territory yet.",
        # restructuration-serveur-v1 c (Drasah 19/10): the Patrouille
        # salon disappears — the AI level lives here.
        "gaia_ai_level": "🤖 Gaïa AI level: {0}/5",
        "territory_guard": "💂 shielded until {0}",
        "territory_note": "Corruption moves the territory across salons (D58).",
        "territory_pending_body": (
            "The map stays secret for now.\n"
            "At the season start, each kingdom will receive its "
            "territories through a random draw."
        ),
        "church_title": "⛪ Parish — {0} · ⛪ {1} · 💍 {2} · 💰 {3}",
        "church_active": "Active marriages",
        "church_none": "No active marriage.",
        "church_badge_locked": "💍 {0} — {1} · 🔒 locked until {2}",
        "church_badge_free": "💍 {0} — {1} · ✅ lock lifted",
        "church_badge_royal_locked": "💍 {0} — 👑 Queen {1} · 🔒 locked until {2}",
        "church_badge_royal_free": "💍 {0} — 👑 Queen {1} · ✅ lock lifted",
        "church_singles": "Bachelors",
        "church_singles_none": "No bachelor lord.",
        "church_tier_line": "Tier: {0} ({1}/{2}) — Offering: {3} ⚙️",
        "church_lock_line": "Standard marriage lock: {0}h",
        "church_royal_lock_line": "Royal marriage lock (King): {0}h",
        "church_marry_button": "💍 Marry",
        "church_arrange_button": "💒 Arranged marriage ({0})",
        "church_upgrade_button": "⛪ Upgrade → {0} ({1} ⚙️)",
        "church_upgrade_max": "⛪ Cathedral — top tier",
        "parish_line": "{0} — tier {1}/{2}",
        "territory_chantier": "⏳ Lieu Sacrée — chantier until {0}",
        "territory_sacred": "⛪ SACRED — forever",
        "church_chantier_line": "⏳ Lieu Sacrée chantier on **{0}** — verdict on {1} (Paris)",
        "church_sacred_line": "⛪ SACRED Lieu Sacrée on **{0}** — immune forever",
        "church_household_palier": "✨ Our {0}",
        "church_household": "💒 The Kingdom's Faithful",
        "church_bachelor": "🎖️ {0} — bachelor · ready to marry 💍",
        "church_ladder_title": "🔭 Tier ladder",
        "church_ladder_current": "●",
        "church_ladder_other": "▸",
        "church_ladder_line": "{0} {1} — {2} ⚙️ · lock {3}h · offering +{4} ⚙️",
        "church_ladder_sacree": " · ⛪ Sacred Site",
        "church_legend_lock": (
            "-# 🔒 Lock: a freshly married lord can neither attack nor"
            " defend for a few hours (24h · 12h · 6h depending on the tier,"
            " doubled for a royal marriage)."
        ),
        "church_legend_offering": (
            "-# 🕯️ Offering: at every celebrated marriage, the Parish pays"
            " technology points into the kingdom's treasury."
        ),
        "church_legend_token": (
            "-# 💰 Token: bought at the Market (3 ⚙️), allows one arranged"
            " marriage without spending a marriage point."
        ),
        "church_legend_sacree": (
            "-# ⛪ Sacred Site (Cathedral): the kingdom consecrates a"
            " territory — immune to every technology action and safe from"
            " conquest for 72h; only a classic attack can dispute it."
        ),
        "lock_days": "Mon|Tue|Wed|Thu|Fri|Sat|Sun",
        "lock_time_fmt": "{0} {1}:{2}",
    }


async def _season_phase(kingdoms_service: Any) -> str:
    """Return the season phase ('started' when unknown/legacy/no service)."""
    if kingdoms_service is None:
        return "started"
    try:
        season = await kingdoms_service.current_season()
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: season read failed", exc_info=True)
        return "started"
    if season is None:
        return "started"
    return str(getattr(season, "phase", "started") or "started")


def _build_alliances_panel(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> Any:
    """Build the 📜 Alliances panel (alliances-lisibilite-v1 T3, Drasah 25/10).

    ONE unified view: the blasons ride a single MOSAIC attachment
    (crest + origin badge per tile, painted in pure Python) instead of
    N full-size attachments, every crest tile wears its ORIGIN EMOJI
    badge (mosaic-emoji-badge: Twemoji glyph composited in pure
    Python, colour-square fallback offline), the written names stay the written names stay one 🔤 Noms click away, the married
    holders and the live mercenary contracts read as compact lines, and
    the help line points at the Scriptorium's Diplomatie rubric — a
    REAL clickable mention when the salon resolves (alliances-
    panel-v2, Drasah 26/10). Four ephemeral buttons ride the panel
    (🔤 Noms is gone — the names ride the crests), the signature
    hides in a SPOILER on the « main » line, and the answers stay
    read-only, the cycle recalculation alone decides the truth.
    """
    import discord

    from kingdoms.mods.kingdoms.kingdom_alliances_panel import (
        KingdomAlliancesDurationsButton,
        KingdomAlliancesHistoryButton,
        KingdomAlliancesLockedButton,
        KingdomAlliancesNextButton,
    )

    civ_names = state.get("civ_names", {})
    hand = [str(civ) for civ in getattr(kingdom, "civilizations", []) or []]
    mercenary: list[str] = []
    for member in state.get("members", []):
        # alliances-panel-v3 : la ligne 💍 mariée disparaît du panneau —
        # la légende + l'emoji de la mosaïque suffisent (retour Drasah).
        merc_civ = getattr(member, "mercenary_civilization", None)
        merc_uses = int(getattr(member, "mercenary_uses_left", 0) or 0)
        if merc_civ and merc_uses > 0:
            mercenary.append(
                strings["alliances_panel_merc_line"].format(
                    getattr(member, "display_name", getattr(member, "id", "?")),
                    civ_names.get(str(merc_civ), str(merc_civ)),
                    merc_uses,
                )
            )
    # alliances-panel-v4 (Drasah 26/10) : l'ordre demandé —
    # 1. l'intro pédagogique, 2. l'aide ❓, 3. la légende, 4. la signature.
    lines: list[str] = [
        strings["alliances_panel_intro_hand"],
        strings["alliances_panel_intro_rules"],
        strings["alliances_panel_intro_cycle"],
    ]
    if not hand and not mercenary:
        lines.append(strings["alliances_panel_empty"])
    lines.extend(mercenary)
    mention = state.get("scriptorium_mention")
    help_line = (
        strings["alliances_panel_help_named"].format(mention)
        if mention
        else strings["alliances_panel_help"]
    )
    # alliances-panel-v4 : la signature garde le MARQUEUR mais perd les
    # NOMS des civilisations (inutiles au joueur) ; la garde d'identité a
    # encore besoin que le texte change quand la MAIN change (sinon edit
    # court-circuité → mosaïque périmée) → une EMPREINTE silencieuse de 8
    # hex (sha1 de la main) remplace la liste.
    import hashlib

    fingerprint = hashlib.sha1(", ".join(hand).encode("utf-8")).hexdigest()[:8]
    signature = f"-# ||{VIEW_MARKER_PREFIX}:alliances-panel · {fingerprint}||"
    body = "\n".join(
        [
            *lines,
            "",
            help_line,
            "",
            strings["alliances_panel_legend"],
            strings["alliances_panel_badges"],
            signature,
        ]
    )
    # alliances-panel-v5 : 📅+🔭 FUSIONNÉS en un seul bouton « 📅 Prochain
    # cycle » (compte à rebours + projection dans la même éphémère),
    # Drasah 26/10 ; 📖 reste dernier.
    buttons: list[Any] = [
        KingdomAlliancesNextButton(strings["alliances_btn_next"]),
        KingdomAlliancesLockedButton(strings["alliances_btn_locked"]),
        KingdomAlliancesDurationsButton(strings["alliances_btn_durations"]),
        KingdomAlliancesHistoryButton(strings["alliances_btn_history"]),
    ]
    return _panel_view_with_buttons(
        strings["alliances_panel_title"].format(getattr(kingdom, "name", "")),
        body,
        "",  # alliances-panel-v2 : la signature vit en spoiler dans le corps
        discord.Colour.dark_embed(),
        buttons,
        # blasons-en-bas-v1 (Drasah 03/11, live report) : la mosaïque
        # ne doit PLUS rendre au-dessus du panel — le slot ``media``
        # est le slot TOP (illustration-top-v1) ; elle bascule sur
        # ``extra_medias`` (la galerie SOUS le conteneur, le même rail
        # que le blason de l'alliance ciblée du conseil).
        extra_medias=["attachment://alliances.png"] if hand else None,
    )


async def _sweep_legacy_mercenary_rubric(channel: Any) -> None:
    """Sweep the standalone ⚔️ mercenary rubric (merged in T3).

    alliances-lisibilite-v1 T3 (Drasah 25/10): the mercenary contracts
    now ride the unified Alliances panel — the old marked message of
    the T2c rubric must never survive a refresh. The PANEL marker
    embeds the rubric marker, so the panel message itself is exempt.
    """
    rubric_marker = f"{VIEW_MARKER_PREFIX}:alliances"
    panel_marker = f"{VIEW_MARKER_PREFIX}:alliances-panel"
    for message in await channel_messages(channel):
        text = message_text(message)
        if rubric_marker in text and panel_marker not in text:
            try:
                await message.delete()
            except Exception:
                logger.warning(
                    "KINGDOM REALM CONTENT: legacy mercenary rubric sweep failed",
                    exc_info=True,
                )


async def deploy_realm_content(
    guild: discord.Guild,
    kingdom: Any,
    wiring: Any,
    locale: str = "fr",
) -> dict[str, bool]:
    """Deploy every realm state view of one kingdom (idempotent).

    Returns the per-salon outcome; each view fails alone (best-effort,
    like every provisioning path — a broken view never blocks the
    others). While the season is in ``setup``, the Territoire salon
    shows the distribution placeholder instead of the territories.
    """
    from kingdoms.mods.kingdoms.kingdom_realms import REALM_SALONS, _find_realm_category
    from kingdoms.mods.kingdoms.kingdom_setup import _slug

    category = _find_realm_category(guild, getattr(kingdom, "name", ""))
    if category is None:
        return {}
    # The salon data keys (e.g. ``eglise``) map to display names
    # (``Paroisse``); match channels by the slug of the display name.
    salon_slugs = {key: _slug(display) for key, display in REALM_SALONS}
    channels: dict[str, Any] = {}
    for channel in getattr(category, "channels", []):
        channels[_slug(getattr(channel, "name", ""))] = channel

    phase = await _season_phase(getattr(wiring, "kingdoms_service", None))
    state = await _gather_state(kingdom, wiring)
    # alliances-panel-v2 : la ligne d'aide cite le salon Scriptorium
    # réel (mention cliquable) quand il existe.
    try:
        from kingdoms.mods.kingdoms.kingdom_scriptorium import find_scriptorium_channel

        scriptorium = find_scriptorium_channel(guild)
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: scriptorium lookup failed", exc_info=True)
        scriptorium = None
    if scriptorium is not None:
        state["scriptorium_mention"] = f"<#{getattr(scriptorium, 'id', '')}>"
    strings = _strings(locale)
    # Drasah 19/10 (restructuration-serveur-v1): seigneurs/patrouille/
    # pigeon-voyageur are no longer salons — Remparts and Seigneurie
    # open from the Le-Royaume buttons (ephemeral), the carrier had no
    # wiring at all.
    # alliances-lisibilite-v1 T3 (Drasah 25/10): ONE unified panel
    # rides the 🤝 salon — the standalone mercenary rubric is merged
    # into it and its old marked message is swept below.
    salon_keys: dict[str, str] = {"alliances-panel": "alliances"}
    builders: dict[str, Any] = {
        "le-royaume": _build_overview,
        "territoire": _build_territory if phase != "setup" else _build_territory_pending,
        # retrait-paroisse-salon-v1 (Drasah 03/11): the ⛪ Paroisse
        # salon is retired from the structure — the lieu view lives on
        # via the 🏰 Le-Royaume hub button, the salon panel no longer
        # has a channel to ride (the builder is simply not scheduled).
        # alliances-lisibilite-v1 T3 (Drasah 25/10): the unified hand
        # view — one crest MOSAIC (origin badge per tile) + the legend,
        # the married holders and the live mercenary contracts as
        # compact lines, plus the five ephemeral clarity buttons.
        "alliances-panel": _build_alliances_panel,
    }
    results: dict[str, bool] = {}
    for key, builder in builders.items():
        channel = channels.get(salon_slugs.get(salon_keys.get(key, key)))
        if channel is None:
            results[key] = False
            continue
        try:
            view = builder(strings, kingdom, state)
            # défaut blasons (T3): the panel wears ONE composite mosaic
            # of the hand's crests — every tile carries its origin
            # badge, the page fits again.
            files = None
            if key == "le-royaume":
                # lieux-et-conseil-v1: the canary hub wears the castle
                # illustration (the sheet's MediaGallery references it).
                from kingdoms.mods.kingdoms.kingdom_lieux import (
                    hub_file,
                    is_canary_realm,
                )

                if is_canary_realm(kingdom):
                    castle = hub_file()
                    files = [castle] if castle is not None else None
            if key == "alliances-panel":
                from kingdoms.mods.kingdoms.civ_crests import civ_crest_mosaic_file

                await _sweep_legacy_mercenary_rubric(channel)
                # alliances-single-message-v1 (Drasah 29/10): ONE message
                # in Alliances — the panel is the single source; sweep the
                # retired standalone draft starter (always) and the setup
                # placeholder (once the season is launched).
                from kingdoms.mods.kingdoms.kingdom_realms import (
                    sweep_standalone_alliances_messages,
                )

                await sweep_standalone_alliances_messages(
                    channel, include_pending=phase != "setup"
                )
                ledger = dict(getattr(kingdom, "civilization_acquisitions", None) or {})
                hand = [str(civ) for civ in getattr(kingdom, "civilizations", []) or []]
                mosaic = await civ_crest_mosaic_file(
                    [
                        (
                            civ,
                            (ledger.get(civ) or {}).get("origin") or "",
                            state.get("civ_names", {}).get(civ, civ),
                        )
                        for civ in hand
                    ]
                )
                files = [mosaic] if mosaic is not None else None
            results[key] = await _upsert_view(channel, key, view, files)
        except Exception:
            logger.warning("KINGDOM REALM CONTENT: view %s failed", key, exc_info=True)
            results[key] = False
    return results


def _catalog_names(service: Any, attribute: str) -> dict[str, str]:
    """Return the key → display-name map of a config catalog."""
    catalog = getattr(getattr(service, "config", None), attribute, None) or ()
    return {
        str(getattr(entry, "key", entry)): str(getattr(entry, "display_name", entry))
        for entry in catalog
    }


async def _read_members(service: Any, kid: str) -> list[Any]:
    """Return the kingdom's active members (empty on failure)."""
    if service is None:
        return []
    try:
        lords = await service.lords()
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: lords read failed", exc_info=True)
        return []
    return [
        lord
        for lord in lords
        if getattr(lord, "kingdom_id", None) == kid and not getattr(lord, "left", False)
    ]


async def _read_territories(service: Any, kid: str) -> list[Any]:
    """Return the kingdom's owned territories (empty on failure)."""
    try:
        territories = await service.territories()
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: territories read failed", exc_info=True)
        return []
    return [
        territory
        for territory in territories
        if str(getattr(territory, "owner_kingdom_id", "")) == kid
    ]


async def _read_wallet(service: Any, kid: str, fallback: int) -> int:
    """Return the kingdom wallet, falling back to the bank on failure."""
    try:
        return int(await service.wallet(kid))
    except Exception:
        return fallback


async def _read_purchases(service: Any, kid: str) -> dict[str, int]:
    """Return the kingdom's purchase counters (empty on failure)."""
    try:
        tech = await service.technology_state(kid)
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: technology read failed", exc_info=True)
        return {}
    return dict(getattr(tech, "purchases", {}) or {})


async def _gather_state(kingdom: Any, wiring: Any) -> dict[str, Any]:
    """Collect the kingdom's live data behind defensive lookups."""
    service = getattr(wiring, "kingdoms_service", None)
    kid = str(getattr(kingdom, "id", ""))
    bank = int(getattr(kingdom, "tech_points_bank", 0) or 0)
    territories_service = getattr(wiring, "territories_service", None)
    economy_service = getattr(wiring, "economy_service", None)
    attacks_service = getattr(wiring, "attacks_service", None)
    state: dict[str, Any] = {
        "members": await _read_members(service, kid),
        "territories": (
            await _read_territories(territories_service, kid)
            if territories_service is not None
            else []
        ),
        "wallet": (
            await _read_wallet(economy_service, kid, bank)
            if economy_service is not None
            else bank
        ),
        "purchases": (
            await _read_purchases(attacks_service, kid) if attacks_service is not None else {}
        ),
        "civ_names": _catalog_names(service, "civilizations") if service is not None else {},
        "map_names": _catalog_names(service, "maps") if service is not None else {},
        "attack_budget": _budget_limit(service, "attacks_per_week"),
        "defense_budget": _budget_limit(service, "defenses_per_week"),
        "parish": _parish_state(kingdom, service),
    }
    state["defense_ai"] = None
    if attacks_service is not None and hasattr(attacks_service, "defense_ai_level"):
        try:
            state["defense_ai"] = await attacks_service.defense_ai_level(kid)
        except Exception:
            state["defense_ai"] = None
    state["reinforced"] = state["defense_ai"] is not None and int(state["defense_ai"]) >= 5
    return state


def _parish_state(kingdom: Any, service: Any) -> dict[str, Any]:
    """Collect the Paroisse slice (palier, points, stock, offrande, lock)."""
    config = getattr(service, "config", None) if service is not None else None
    settings = getattr(config, "parish", None)
    tier = max(1, int(getattr(kingdom, "parish_tier", 1) or 1))
    if settings is None:
        # defensive default: the config seam is unavailable (tests)
        fallback = (
            ("Chapelle", 0, 24, 0),
            ("Église", 2, 12, 1),
            ("Cathédrale", 4, 6, 2),
        )
        ladder = [
            {
                "name": name,
                "cost": cost,
                "lock_hours": lock,
                "offering": offering,
            }
            for name, cost, lock, offering in fallback
        ]
        entry = ladder[tier - 1]
        return {
            "tier": tier,
            "name": entry["name"],
            "cost": ladder[tier]["cost"] if tier < len(ladder) else 0,
            "next_name": ladder[tier]["name"] if tier < len(ladder) else "",
            "offering": entry["offering"],
            "lock_hours": entry["lock_hours"],
            "max_tier": len(ladder),
            "ladder": ladder,
        }
    tiers = settings.tiers
    entry = settings.tier(tier)
    next_entry = tiers[tier] if tier < len(tiers) else None
    ladder = [
        {
            "name": str(item.display_name),
            "cost": int(item.cost),
            "lock_hours": int(item.marriage_lock_hours),
            "offering": int(item.offering),
        }
        for item in tiers
    ]
    return {
        "tier": tier,
        "name": str(entry.display_name),
        "cost": int(next_entry.cost) if next_entry is not None else 0,
        "next_name": str(next_entry.display_name) if next_entry is not None else "",
        "offering": int(entry.offering),
        "lock_hours": int(entry.marriage_lock_hours),
        "max_tier": len(tiers),
        "ladder": ladder,
    }


def _budget_limit(service: Any, key: str) -> int:
    """Return the configured weekly attack/defense budget (default 1).

    Drasah 15/10: the roster shows the budgets each lord still holds,
    so the panel needs the season's per-lord ceilings.
    """
    attacks = getattr(getattr(service, "config", None) if service is not None else None, "attacks", None)
    if attacks is None:
        return 1
    try:
        return max(0, int(getattr(attacks, key, 1) or 0))
    except Exception:
        return 1


def _panel_view(
    title: str,
    body: str,
    marker: str,
    accent: discord.Colour,
) -> discord.ui.LayoutView:
    """Build one Components V2 state panel (title / body / marker)."""
    import discord

    view = discord.ui.LayoutView(timeout=None)
    view.add_item(
        discord.ui.Container(
            discord.ui.TextDisplay(f"# {title}"),
            discord.ui.Separator(),
            discord.ui.TextDisplay(body),
            discord.ui.Separator(),
            discord.ui.TextDisplay(f"-# {marker}"),
            accent_colour=accent,
        )
    )
    return view


def _parish_overview_line(state: dict[str, Any], strings: dict[str, str]) -> str:
    """Render the Paroisse slice of the overview (lieu-sacree-v1: real tier).

    A state gathered without the parish slice (partial test states)
    falls back to the former placeholder line.
    """
    parish = state.get("parish") or {}
    name = parish.get("name")
    if name:
        return strings["parish_line"].format(
            name, parish.get("tier", 1), parish.get("max_tier", 3)
        )
    return strings["parish_placeholder"]


def _overview_body(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> str:
    """The realm stats block (lieux-et-conseil-v1: it moved to the Council)."""
    members = state["members"]
    king = next((m for m in members if str(getattr(m, "role", "")) == "king"), None)
    king_name = getattr(king, "display_name", None) or strings["no_king"]
    subjects = [m for m in members if m is not king]
    slots = _patrol_slots(state)
    married = [m for m in members if getattr(m, "married_civilization", None)]
    patrol = (
        ", ".join(strings["patrol_slot"].format(s, s + 2) for s in slots)
        if slots
        else strings["none_f"]
    )
    return "\n".join(
        [
            f"**{strings['members']}** : "
            f"{strings['members_line'].format(king_name, len(subjects), len(members))}",
            f"**{strings['treasury']}** : {state['wallet']} ⚙️",
            f"**{strings['territories']}** : {len(state['territories'])}",
            f"**{strings['civilizations']}** : {len(getattr(kingdom, 'civilizations', []) or [])}",
            f"**{strings['marriages']}** : {len(married)}",
            f"**{strings['patrol']}** : {patrol}",
            f"**{strings['royal_guard']}** : "
            f"{strings['yes'] if state['purchases'].get('garde_royale') else strings['no']}",
            f"**{strings['parish']}** : "
            f"{_parish_overview_line(state, strings)}",
        ]
    )


def _build_overview(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> Any:
    """Build the 🏰 Le-Royaume pinned sheet.

    lieux-et-conseil-v1 (Drasah 01/11): the canary kingdoms render the
    CASTLE HUB — the stats move into the ⚔️ Salle du conseil, the five
    doors open the realm's places, the castle illustration rides the
    sheet. The player kingdoms keep the classic sheet while the gate
    is active (canary-gate-v1: the declaration wins, never the live
    state).
    """
    import discord

    from kingdoms.mods.kingdoms.kingdom_lieux import is_canary_realm

    media = None
    if is_canary_realm(kingdom):
        from kingdoms.mods.kingdoms.kingdom_lieux import _strings as _lieux_strings
        from kingdoms.mods.kingdoms.kingdom_lieux import hub_entree_button

        lieu_locale = "fr" if strings.get("yes") == "oui" else "en"
        body = _lieux_strings(lieu_locale)["hub_flavor"]
        # entree-v1 (Drasah 01/11): the hub carries ONE door — 🏰 Entrée.
        # The five places moved into its ephemeral chooser « Où
        # souhaitez-vous vous rendre ? » (fenetre-unique-v2 rides it).
        buttons: list[Any] = [hub_entree_button(lieu_locale)]
        media = "attachment://royaume.png"
    else:
        body = _overview_body(strings, kingdom, state)
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            KingdomMarketLedgerButton,
            KingdomTraquenardButton,
        )
        from kingdoms.mods.kingdoms.kingdom_voliere_panel import KingdomVoliereButton
        from kingdoms.mods.kingdoms.kingdom_voliere_panel import (
            _strings as _voliere_strings,
        )

        buttons = [KingdomMarketLedgerButton(strings["ledger_button"])]
        # The Traquenard button only exists when the kingdom holds a charge
        # (same rule as the cover proposal of the declare flow).
        if int(state.get("purchases", {}).get("traquenard", 0) or 0) > 0:
            buttons.append(KingdomTraquenardButton(strings))
        # exploration-expedition-v1 (Drasah 30/10): the 🧭 Exploration
        # button exists ONLY while the kingdom holds an unused Explorateur
        # token (the launch consumes it, the view refresh drops the button).
        from kingdoms.mods.kingdoms.kingdom_expedition_panel import (
            KingdomExpeditionOpenButton,
            _strings as _expedition_strings,
        )

        if int(state.get("purchases", {}).get("explorateur_stock", 0) or 0) > 0:
            expe_locale = "fr" if strings.get("yes") == "oui" else "en"
            buttons.append(
                KingdomExpeditionOpenButton(
                    _expedition_strings(expe_locale)["open_button"]
                )
            )
        # Volière (voliere-v1): always visible — the Féodal gate lives in the
        # service (VoliereLockedError), so the view stays simple.
        voliere_locale = "fr" if strings.get("yes") == "oui" else "en"
        buttons.append(
            KingdomVoliereButton(_voliere_strings(voliere_locale)["voliere_button"])
        )
        # Drasah 19/10 (restructuration-serveur-v1): Remparts and Seigneurie
        # leave the salon world — they open as ephemeral views from here.
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            KingdomRempartsOpenButton,
            KingdomSeigneurieOpenButton,
        )

        buttons.append(KingdomRempartsOpenButton(strings["remparts_open_button"]))
        buttons.append(KingdomSeigneurieOpenButton(strings["seigneurie_open_button"]))
    # kingdom-test-v1 (Drasah 01/11): the Nilrem realm carries its
    # admin-only controls — on the canary hub they ride the second row,
    # on the classic sheet they close the action rows (data untouched).
    from kingdoms.mods.kingdoms.service import is_test_kingdom

    if is_test_kingdom(kingdom):
        from kingdoms.mods.kingdoms.kingdom_test import (
            KingdomTestDestructButton,
            KingdomTestRefreshButton,
            _strings as _test_strings,
        )

        test_strings = _test_strings("fr" if strings.get("yes") == "oui" else "en")
        buttons.append(KingdomTestDestructButton(test_strings["destruct_button"]))
        buttons.append(KingdomTestRefreshButton(test_strings["refresh_button"]))
    view = _panel_view_with_buttons(
        strings["overview_title"].format(getattr(kingdom, "name", "")),
        body,
        f"{VIEW_MARKER_PREFIX}:le-royaume",
        discord.Colour.gold(),
        buttons,
        media=media,
    )
    # immersion-v1 (Drasah 20/10): the user-settings button lives in its
    # OWN footer container, visually detached from the game buttons —
    # the player must read it as out-of-game, not as a game action.
    from kingdoms.mods.kingdoms.kingdom_immersion import KingdomUserSettingsButton

    # (buttons ride a list[Any] like the game row — the DynamicItem's
    # Button[Any] typevar is not LayoutView-typed, mypy-wise)
    footer_buttons: list[Any] = [KingdomUserSettingsButton(strings["settings_button"])]
    footer: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.Separator(),
        discord.ui.TextDisplay(strings["settings_footer"]),
        discord.ui.ActionRow(*footer_buttons),
    )
    view.add_item(footer)
    return view


def _build_roster(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> Any:
    """Build the 🎖️ Seigneurs private roster."""
    import discord

    members = state["members"]
    if not members:
        lines = [strings["roster_empty"]]
    else:
        lines = []
        for member in members:
            role = str(getattr(member, "role", ""))
            icon = "👑" if role == "king" else "🎖️"
            line = f"• {icon} **{getattr(member, 'display_name', strings['unknown'])}**"
            civ = getattr(member, "married_civilization", None)
            if civ:
                line += f" — 💍 {state['civ_names'].get(str(civ), str(civ))}"
            attack_budget = int(state.get("attack_budget", 1) or 1)
            defense_budget = int(state.get("defense_budget", 1) or 1)
            attack_left = max(0, attack_budget - int(getattr(member, "attack_used", 0) or 0))
            defense_left = max(0, defense_budget - int(getattr(member, "defense_used", 0) or 0))
            line += (
                f" — ⚔️ {attack_left}/{attack_budget}"
                f" · 🛡️ {defense_left}/{defense_budget}"
            )
            exploring = int(getattr(member, "exploration_locked_until", 0) or 0)
            if exploring > int(game_now().timestamp()):
                line += f" {strings['roster_exploring'].format(_lock_until_label(exploring, strings))}"
            # Drasah 19/10 (restructuration-serveur-v1): the roster shows
            # the public locks too — marriage and FFA no-show. The Corbeau
            # « suivi » is NEVER displayed (espionnage secret).
            marriage_lock = int(getattr(member, "marriage_locked_until", 0) or 0)
            if marriage_lock > int(game_now().timestamp()):
                line += f" {strings['roster_marriage_lock'].format(_lock_until_label(marriage_lock, strings))}"
            ffa_lock = int(getattr(member, "ffa_locked_until", 0) or 0)
            if ffa_lock > int(game_now().timestamp()):
                line += f" {strings['roster_ffa_lock'].format(_lock_until_label(ffa_lock, strings))}"
            if getattr(member, "left", False):
                line += f" {strings['left_badge']}"
            lines.append(line)
    return _panel_view(
        strings["roster_title"].format(getattr(kingdom, "name", "")),
        "\n".join(lines),
        f"{VIEW_MARKER_PREFIX}:seigneurs",
        discord.Colour.blue(),
    )


def _patrol_slots(state: dict[str, Any]) -> list[int]:
    """Return the bought patrol slots (sorted slot starts)."""
    from kingdoms.mods.kingdoms.attacks import PATROUILLE_SLOT_KEYS

    slots: list[int] = []
    for key in PATROUILLE_SLOT_KEYS:
        value = state["purchases"].get(key)
        if isinstance(value, int):
            slots.append(value)
    return sorted(slots)


def _build_patrol(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
    media: str | None = None,
    rows: list[list[Any]] | None = None,
    mode: str = "state",
) -> Any:
    """Build the 🧱 Remparts view (remparts-etats-v1, Drasah 03/11).

    TWO faces: mode="state" (default) shows ONLY the live states
    (IA level, ❌/⚠️/⏲ patrouille per slot, ✅ Gardes + reserve);
    mode="info" shows the EXPLANATIONS (the IA training loop, the
    Patrouille and Garde Royale descriptions, the Lord's-Day
    redefinition note) — the 🔎 En savoir plus / ✅ Compris buttons
    toggle between the two faces, in place.
    """
    import discord

    purchases = dict(state.get("purchases") or {})
    span = 3 if state.get("reinforced") else 2
    now = game_now()
    now_ts = int(now.timestamp())
    lines: list[str] = []
    if mode == "info":
        # remparts-etats-v1 (Drasah 03/11): the EXPLANATION face —
        # the pedagogical IA block (no defender -> the IA defends, a
        # Jeu d'armes raises it, the max level improves the
        # Patrouille), the Patrouille and Gardes descriptions, and
        # the Lord's-Day redefinition note LIVES HERE now.
        lines.append(strings["remparts_ai_intro"])
        if state.get("reinforced"):
            lines.append(strings["remparts_reinforced"])
        # remparts-etats-aeration (Drasah 03/11 soir): one blank line
        # between each block; the Lord's-Day note stays GLUED to the
        # Patrouille block (it is about placing the slots).
        lines.append("")
        lines.append(strings["remparts_patrouille_intro"])
        lines.append(strings["patrol_window"])
        lines.append("")
        lines.append(strings["remparts_garde_intro"])
        body = "\n".join(lines)
        return _panel_view_with_buttons(
            strings["patrol_title"].format(getattr(kingdom, "name", "")),
            body,
            f"{VIEW_MARKER_PREFIX}:patrouille",
            discord.Colour.teal(),
            [],
            media=media,
            rows=rows or [],
        )
    if state.get("defense_ai") is not None:
        # remparts-etats-v1: the STATE face keeps ONLY the live
        # level line (the explanations moved to the info face).
        from kingdoms.mods.kingdoms.kingdom_persistent import (
            _traquenard_ai_display,
        )

        display, level_name = _traquenard_ai_display(
            int(state["defense_ai"]), strings
        )
        lines.append(strings["remparts_ai_level"].format(display, level_name))
        lines.append("")
    # remparts-etats-titres-fix (Drasah 03/11 live report): the
    # 👣 Patrouille section title rides BEFORE its status lines —
    # the live view rendered the two slot lines above the title.
    lines.append(
        strings["remparts_patrouille_title_reinforced"]
        if state.get("reinforced")
        else strings["remparts_patrouille_title"]
    )
    # remparts-etats-v1 (Drasah 03/11): one STATUS line per slot —
    # ❌ not owned (market hint), ⚠️ owned but not configured,
    # ⏲ active with its real window ([x/2] on ❌ and ⏲ only).
    for slot_no in (1, 2):
        unlock_key = f"patrouille_unlock_{slot_no}"
        slot_key = f"patrouille_slot_{slot_no}"
        if slot_key in purchases:
            start = int(purchases[slot_key])
            line = strings["remparts_state_active"].format(
                slot_no, start, start + span
            )
        elif unlock_key in purchases:
            line = strings["remparts_state_unplaced"]
        else:
            line = strings["remparts_state_missing"].format(slot_no)
        lines.append(line)
    # Gardes Royales — one line per shielded map + the owned count.
    guard_lines: list[str] = []
    for territory in state["territories"]:
        guard_key = f"garde_royale_until:{getattr(territory, 'id', '')}"
        until_ts = int(purchases.get(guard_key, 0) or 0)
        if until_ts <= now_ts:
            continue
        key = str(getattr(territory, "map_key", ""))
        guard_lines.append(
            strings["remparts_guard_line"].format(
                state["map_names"].get(key, key), _lock_until_label(until_ts, strings)
            )
        )
    guard_block = "\n".join(guard_lines) or strings["remparts_guard_none"]
    lines.append("")
    # remparts-etats-titres: 🛡️ Garde Royale — the owned counter
    # REPLACES « En réserve » (Drasah's tranche: none/one/many), then
    # the ✅ lines follow; the pedagogical intro lives in info only.
    lines.append(strings["remparts_garde_title"])
    stock = int(purchases.get("garde_royale_stock", 0) or 0)
    if stock <= 0:
        lines.append(strings["remparts_garde_owned_none"])
    elif stock == 1:
        lines.append(strings["remparts_garde_owned_one"].format(stock))
    else:
        lines.append(strings["remparts_garde_owned_many"].format(stock))
    lines.append(guard_block)
    body = "\n".join(lines)
    from kingdoms.mods.kingdoms.kingdom_attack_panel import (
        KingdomAttackManagerButton,
        KingdomDefenseManagerButton,
    )
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomRempartsGuardButton,
        KingdomRempartsPatrouilleHubButton,
        KingdomRempartsInfoButton,
    )

    return _panel_view_with_buttons(
        strings["patrol_title"].format(getattr(kingdom, "name", "")),
        body,
        f"{VIEW_MARKER_PREFIX}:patrouille",
        discord.Colour.teal(),
        [
            KingdomRempartsGuardButton(strings),
            KingdomRempartsPatrouilleHubButton(strings),
            KingdomRempartsInfoButton(strings),
            # Drasah 18/10: la vue privée du royaume défenseur — qui
            # défend quoi, l'effet de surprise restant public-board-free.
            KingdomDefenseManagerButton(strings.get("defense_manager_button", "🛡️ Gestion de la défense")),
            # planification-attaque-v1 (Drasah 23/10): ⚔️ Gestion
            # d'attaque — les déclarations en cours + les
            # plannifications du royaume (3 choix visibles).
            KingdomAttackManagerButton(
                strings.get("attack_manager_button", "⚔️ Gestion d'attaque")
            ),
        ],
        media=media,
        rows=rows,
    )


def _build_territory(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> Any:
    """Build the 🗺️ Territoire state view (guarded maps wear 🛡️ + end)."""
    import discord

    now = game_now()
    lines = [strings["territory_count"].format(len(state["territories"]))]
    if not state["territories"]:
        lines.append(strings["territory_empty"])
    for territory in state["territories"]:
        key = str(getattr(territory, "map_key", ""))
        line = f"• **{state['map_names'].get(key, key)}**"
        until = getattr(territory, "protected_until", None)
        if until is not None and until > now:
            # marche-v2 article 7: the shielded map shows its 🛡️ and the
            # protection END TIME next to its name.
            line += f" {strings['territory_guard'].format(_lock_until_label(int(until.timestamp()), strings))}"
        # lieu-sacree-v1: the real chantier (⏳ end Paris) and SACRED (⛪)
        # states show next to the map name — never a stale placeholder.
        cathedral_until = getattr(territory, "cathedral_until", None)
        if bool(getattr(territory, "sacred", False)):
            line += f" {strings['territory_sacred']}"
        elif cathedral_until is not None and cathedral_until > now:
            line += (
                f" {strings['territory_chantier'].format(
                    _lock_until_label(int(cathedral_until.timestamp()), strings)
                )}"
            )
        lines.append(line)
    lines.append(strings["territory_note"])
    return _panel_view(
        strings["territory_title"].format(getattr(kingdom, "name", "")),
        "\n".join(lines),
        f"{VIEW_MARKER_PREFIX}:territoire",
        discord.Colour.green(),
    )


def _build_territory_pending(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
) -> Any:
    """Build the 🗺️ setup-phase placeholder (nothing revealed yet)."""
    import discord

    return _panel_view(
        strings["territory_title"].format(getattr(kingdom, "name", "")),
        strings["territory_pending_body"],
        f"{VIEW_MARKER_PREFIX}:territoire",
        discord.Colour.dark_grey(),
    )


def _build_gaia_territory(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
    ai_level: int,
) -> Any:
    """Build the Gaïa 🗺️ Territoire view (restructuration-serveur-v1 c).

    The Gaïa category keeps ONE salon: the retired « Patrouille » info
    (the AI level) is integrated here — Drasah 19/10, the level is read
    LIVE from the season epoch (D18 scale, fallback 1), never hardcoded.
    The territories carry the same guard/chantier/sacred badges as the
    player-kingdom views.
    """
    import discord

    now = game_now()
    lines = [strings["gaia_ai_level"].format(int(ai_level))]
    lines.append(strings["territory_count"].format(len(state["territories"])))
    if not state["territories"]:
        lines.append(strings["territory_empty"])
    for territory in state["territories"]:
        key = str(getattr(territory, "map_key", ""))
        line = f"• **{state['map_names'].get(key, key)}**"
        until = getattr(territory, "protected_until", None)
        if until is not None and until > now:
            line += f" {strings['territory_guard'].format(_lock_until_label(int(until.timestamp()), strings))}"
        if bool(getattr(territory, "sacred", False)):
            line += f" {strings['territory_sacred']}"
        else:
            cathedral_until = getattr(territory, "cathedral_until", None)
            if cathedral_until is not None and cathedral_until > now:
                line += (
                    f" {strings['territory_chantier'].format(
                        _lock_until_label(int(cathedral_until.timestamp()), strings)
                    )}"
                )
        lines.append(line)
    lines.append(strings["territory_note"])
    return _panel_view(
        strings["territory_title"].format(getattr(kingdom, "name", "") or "Gaïa"),
        "\n".join(lines),
        f"{VIEW_MARKER_PREFIX}:territoire-gaia",
        discord.Colour.green(),
    )


async def deploy_gaia_content(
    guild: discord.Guild,
    wiring: Any,
    locale: str = "fr",
) -> dict[str, bool]:
    """Deploy the Gaïa territory view (the Territoire salon, c).

    restructuration-serveur-v1 c (Drasah 19/10): the Gaïa category drops
    to ONE salon — the AI level lives in the Territoire view and the
    FFA lives in its ephemeral salon. restructuration-gaia-v1
    (Drasah 24/10): the retired Gaïa category's Territoire salon now
    lives inside the renamed Kingdoms-Gaia structure category — the
    lookup goes through it (the realm-category path is gone with the
    category). Best effort: a missing category, salon or kingdom simply
    reports False, never raises.
    """
    from kingdoms.mods.kingdoms.kingdom_setup import _find_category, _slug

    category = _find_category(guild, "Kingdoms-Gaia") or _find_category(guild, "Kingdoms")
    if category is None:
        return {}
    service = getattr(wiring, "kingdoms_service", None)
    if service is None:
        return {}
    try:
        kingdoms = await service.kingdoms()
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: gaia kingdom read failed", exc_info=True)
        return {}
    kingdom = next((k for k in kingdoms if getattr(k, "is_gaia", False)), None)
    if kingdom is None:
        return {}
    # The AI level is the LIVE season epoch's (D18 scale, fallback 1) —
    # the same source as the attackers' Itinéraire/defense checks.
    ai_level = 1
    attacks_service = getattr(wiring, "attacks_service", None)
    if attacks_service is not None:
        try:
            ai_level = int(await attacks_service.base_ai_level())
        except Exception:
            logger.warning("KINGDOM REALM CONTENT: gaia ai level read failed", exc_info=True)
    channel = next(
        (
            c
            for c in getattr(category, "channels", [])
            if _slug(getattr(c, "name", "")) == "territoire"
        ),
        None,
    )
    if channel is None:
        return {"territoire-gaia": False}
    state = await _gather_state(kingdom, wiring)
    strings = _strings(locale)
    try:
        view = _build_gaia_territory(strings, kingdom, state, ai_level)
        return {"territoire-gaia": await _upsert_view(channel, "territoire-gaia", view)}
    except Exception:
        logger.warning("KINGDOM REALM CONTENT: gaia territory view failed", exc_info=True)
        return {"territoire-gaia": False}



def _build_church(
    strings: dict[str, str],
    kingdom: Any,
    state: dict[str, Any],
    media: str | None = None,
    rows: list[list[Any]] | None = None,
) -> Any:
    """Build the ⛪ Paroisse state view (D64 paliers + marriages, v3).

    Live data only: palier, points de mariage and jetons in the title
    (Drasah's 2026-10-11 header), one line per Fidèle with their
    marriage and their lock END TIME (never a stale remaining
    duration), the palier ladder with the Cathédrale's Lieu Sacrée,
    and a small legend (verrou, offrande, jeton, sacrée). The buttons
    (marry / arranged / upgrade) are restart-proof DynamicItems.
    """
    import time as _time

    import discord

    from kingdoms.mods.kingdoms.diplomacy import _pick_promise

    parish = state["parish"]
    members = [m for m in state["members"] if not getattr(m, "left", False)]
    now = int(_time.time())
    married = [m for m in members if getattr(m, "married_civilization", None)]
    singles = [
        m for m in members if getattr(m, "married_civilization", None) is None
    ]

    # ✨ Palier block
    lines = [
        f"## {strings['church_household_palier'].format(parish['name'])}",
        strings["church_tier_line"].format(
            parish["name"], parish["tier"], parish["max_tier"], parish["offering"]
        ),
        strings["church_lock_line"].format(parish["lock_hours"]),
        strings["church_royal_lock_line"].format(parish["lock_hours"] * 2),
        "",
        # 💒 Les Fidèles du Royaume — one line per member with their state
        f"## {strings['church_household']}",
    ]
    if not members:
        lines.append(strings["church_none"])
    for member in married:
        civ = str(getattr(member, "married_civilization", ""))
        civ_display = state["civ_names"].get(civ, civ)
        # Drasah 2026-10-12: the badge shows the promise herself —
        # « 💍 Luc — Atotoztli (Aztèques) » — never a lone civ key.
        promise = _pick_promise(f"{member.id}:{civ_display}", civ_display)
        civ_label = f"{promise} ({civ_display})" if promise else civ_display
        until = int(getattr(member, "marriage_locked_until", 0) or 0)
        royal = bool(getattr(member, "royal_marriage", False))
        base = "church_badge_royal" if royal else "church_badge"
        key = f"{base}_locked" if until > now else f"{base}_free"
        lines.append(
            strings[key].format(
                getattr(member, "display_name", strings["unknown"]),
                civ_label,
                _lock_until_label(until, strings) if until > now else "",
            )
        )
    for member in singles:
        lines.append(
            strings["church_bachelor"].format(
                getattr(member, "display_name", member.id)
            )
        )
    # 🔭 Aperçu des paliers — every tier visible with cost and perks
    lines += [
        "",
        f"## {strings['church_ladder_title']}",
    ]
    for index, step in enumerate(parish.get("ladder") or [], start=1):
        marker = strings["church_ladder_current"] if index == parish["tier"] else strings["church_ladder_other"]
        line = strings["church_ladder_line"].format(
            marker,
            step["name"],
            step["cost"],
            step["lock_hours"],
            step["offering"],
        )
        if index == parish["max_tier"]:
            line += strings["church_ladder_sacree"]
        lines.append(line)
    # lieu-sacree-v1: the REAL Lieu Sacrée state — every chantier
    # (⏳ verdict end, Paris) and every SACRED territory of the kingdom.
    now_dt = game_now()
    chantiers = [
        item
        for item in state["territories"]
        if getattr(item, "cathedral_until", None) is not None
        and item.cathedral_until > now_dt
    ]
    sacreds = [
        item for item in state["territories"] if bool(getattr(item, "sacred", False))
    ]
    if chantiers or sacreds:
        lines += [""]
        for item in chantiers:
            lines.append(
                strings["church_chantier_line"].format(
                    str(getattr(item, "map_key", "")),
                    _lock_until_label(
                        int(item.cathedral_until.timestamp()), strings
                    ),
                )
            )
        for item in sacreds:
            lines.append(
                strings["church_sacred_line"].format(str(getattr(item, "map_key", "")))
            )
    # 📖 la légende — verrou, offrande, jeton, lieu sacrée
    lines += [
        "",
        strings["church_legend_lock"],
        strings["church_legend_offering"],
        strings["church_legend_token"],
        strings["church_legend_sacree"],
    ]
    body = "\n".join(lines)

    buttons = rows if rows is not None else _church_buttons(strings, kingdom, state)
    return _panel_view_with_buttons(
        strings["church_title"].format(
            getattr(kingdom, "name", ""),
            parish["name"],
            int(getattr(kingdom, "marriage_points", 0) or 0),
            int(getattr(kingdom, "arranged_marriage_stock", 0) or 0),
        ),
        body,
        f"{VIEW_MARKER_PREFIX}:eglise",
        discord.Colour.purple(),
        buttons,
        media=media,
        rows=rows,
    )


def _church_buttons(strings: dict[str, str], kingdom: Any, state: dict[str, Any]) -> list[Any]:
    """Build the restart-proof Paroisse buttons of the current palier."""
    from kingdoms.mods.kingdoms.kingdom_persistent import (
        KingdomChurchArrangeButton,
        KingdomChurchConsecrateButton,
        KingdomChurchMarryButton,
        KingdomChurchUpgradeButton,
    )

    parish = state["parish"]
    arranged = int(getattr(kingdom, "arranged_marriage_stock", 0) or 0)
    buttons: list[Any] = [KingdomChurchMarryButton(strings)]
    if parish["tier"] >= 2:
        buttons.append(KingdomChurchArrangeButton(strings, arranged))
    if parish["tier"] < parish["max_tier"]:
        buttons.append(
            KingdomChurchUpgradeButton(strings, parish["next_name"], parish["cost"])
        )
    else:
        buttons.append(KingdomChurchUpgradeButton(strings, "", 0))
        # lieu-sacree-v1: at the Cathédrale palier the King may
        # consecrate a Lieu Sacrée (3 ⚙️, 72h chantier).
        buttons.append(KingdomChurchConsecrateButton(strings))
    return buttons


def _panel_view_with_buttons(
    title: str,
    body: str,
    marker: str,
    accent: discord.Colour,
    buttons: list[Any],
    media: str | None = None,
    rows: list[list[Any]] | None = None,
    extra_medias: list[str] | None = None,
) -> discord.ui.LayoutView:
    """Build one Components V2 state panel with an action row of buttons.

    mosaic-render-fix (T3b, Drasah 25/10): Components V2 messages do
    NOT render unreferenced file attachments — an optional top-level
    ``MediaGallery`` referencing the mosaic attachment makes the
    blasons visible under the panel container.
    """
    import discord

    view = discord.ui.LayoutView(timeout=None)
    container: discord.ui.Container[discord.ui.LayoutView] = discord.ui.Container(
        discord.ui.TextDisplay(f"# {title}"),
        discord.ui.Separator(),
        discord.ui.TextDisplay(body),
        discord.ui.Separator(),
        accent_colour=accent,
    )
    if rows:
        # lieux-rows-v1 (Drasah 01/11): the lieu views lay their own
        # rows — line 1 = the place's default actions (green) + Sortir
        # (red) last, line 2 = the technology cards (gray/disabled
        # while out of stock, green while held). Every sublist is the
        # CALLER's responsibility (max 5 children per row).
        for row in rows:
            if row:
                container.add_item(discord.ui.ActionRow(*row))
    elif buttons:
        # overview-rows-v1 (Drasah 31/10, live incident HeN): Discord
        # caps an ActionRow at FIVE children — the Le-Royaume sheet
        # reached SIX buttons (ledger, traquenard, exploration,
        # volière, remparts, seigneurie) and every deploy crashed with
        # ValueError, SILENTLY leaving the realm salon empty (only the
        # kingdoms holding the extra cards were hit). The helper now
        # chunks the buttons into rows of five (up to 5 rows = 25
        # buttons, far beyond any surface).
        for offset in range(0, len(buttons), 5):
            container.add_item(discord.ui.ActionRow(*buttons[offset:offset + 5]))
    if marker:
        container.add_item(discord.ui.TextDisplay(f"-# {marker}"))
    # illustration-top-v1 (Drasah 01/11): the illustration is FIXED and
    # TOP — the image of the place the reader stands in rides above the
    # panel, never under it (the hub castle, a lieu's own picture).
    # ⚠️ the item class is TOP-LEVEL discord.MediaGalleryItem — the
    # deployed discord.py 2.7.1 has NO discord.ui.MediaGalleryItem
    # (live crash 01/11 15:31, Nilrem's Le-Royaume empty since entree-v1).
    if media:
        view.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(media=media)))
    view.add_item(container)
    # conseil-objectif-v2 (Drasah 01/11): extra referenced attachments
    # (the targeted alliance's blason) render UNDER the panel.
    for media_url in extra_medias or ():
        view.add_item(discord.ui.MediaGallery(discord.MediaGalleryItem(media=media_url)))
    return view



async def _upsert_view(
    channel: Any, key: str, view: Any, files: list[Any] | None = None
) -> bool:
    """Edit the marked panel in place, or send it once (never duplicate).

    vues-silencieuses-v1 (Drasah 19/10): the marked message is now edited in
    place instead of delete+send, with an identity guard so an unchanged view
    costs zero API calls. Duplicates are purged, and a failed edit falls back
    to a fresh send.
    """
    marker = f"{VIEW_MARKER_PREFIX}:{key}"
    marked: list[Any] = [
        message
        for message in await channel_messages(channel)
        if marker in message_text(message)
    ]
    if marked:
        for duplicate in marked[1:]:
            try:
                await duplicate.delete()
            except Exception:
                logger.warning(
                    "KINGDOM REALM CONTENT: view %s duplicate purge failed", key, exc_info=True
                )
        existing = marked[0]
        if message_text_squashed(existing) == view_text(view) and (
            files is None or getattr(existing, "attachments", None)
        ):
            return True
        try:
            await existing.edit(view=view, **({"attachments": files} if files else {}))
            return True
        except Exception:
            logger.warning(
                "KINGDOM REALM CONTENT: view %s edit failed, resending", key, exc_info=True
            )
    await channel.send(view=view, **({"files": files} if files else {}), allowed_mentions=NO_MENTIONS)
    return True
