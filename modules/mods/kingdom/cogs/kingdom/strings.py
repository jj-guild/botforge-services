"""The attack panel's player-facing strings (FR/EN, P4.1b tranche 1).

The defaults live HERE (the ported reference wording, verbatim); the
repo's ``config/locales/<locale>.yaml`` ``kingdom.attack`` section
overrides them key by key when present — the catalog wins, the code
fallback keeps every surface alive without it.
"""

from __future__ import annotations

DEFAULTS: dict[str, dict[str, str]] = {
    "fr": {
        "panel_title": "⚔️ Champ de bataille — Attaquer",
        "panel_help": (
            "Déclarez une attaque sur un territoire adverse — le RDV est fixé à l'heure affichée.\n"
            "Déroulé : **Siège** (la défense s'ouvre dès la déclaration, dans le salon de l'attaque)"
            " → **Draft** (pick & ban en MP) → **RDV** (confirmez votre présence) → **Score**"
            " (la game, déclarez le résultat)."
        ),
        "panel_pointer": (
            "↳ Chaque attaque déclarée ouvre son PROPRE salon de bataille juste sous ce"
            " panel — défense, reveal et résultats y vivent."
        ),
        "declare_button": "⚔️ Déclarer une attaque",
        "history_button": "📜 Historique des confrontations",
        "attack_info_button": "⚔️ Information attaque / défense",
        "history_title": "📜 **Historique des confrontations**",
        "history_empty": "🕊️ Aucune confrontation terminée pour l'instant.",
        "history_line": "• **{date}** — **{map}** · {attacker} ⚔️ {defender} — {outcome}",
        "history_outcome_win": "victoire de **{kingdom}**",
        "history_outcome_cancelled": "🏳️ attaque annulée",
        "history_outcome_double": "🏳️ double forfait",
        "history_outcome_expired": "⏳ expirée sans issue",
        "history_page": "Page {page}/{pages}",
        "itinerary_line": "⚔️ Itinéraire : exécution dans **{minutes} min** après la déclaration.",
        "itinerary_note": (
            "⚔️ Attaque déclarée sur **{map}** — itinéraire : exécution dans **{delay} min**"
            " — RDV {time}."
        ),
        "cancel_attack_button": "❌ Annuler l'attaque",
        "cancel_attack_done": (
            "🏳️ **Attaque annulée** — budget d'attaque remboursé"
            " (défense remboursée aussi si elle était enregistrée). Le salon de l'attaque disparaît."
        ),
        "cancel_attack_embuscade_done": (
            "🏳️ **Embuscade annulée** — mais le jeton Embuscade reste **consommé** :"
            " il n'est jamais remboursé, même en cas d'annulation. Le salon de l'attaque disparaît."
        ),
        "cancel_attack_cover_refunded": (
            "🕵️ La couverture (Contre-espionnage) est rendue au stock du royaume."
        ),
        "defend_wrong_kingdom": "❌ Vous ne pouvez défendre ce territoire.",
        "defend_button": "🛡️ Défendre",
        "defend_already": "❌ Le royaume est déjà défendu.",
        "gaia_join_button": "🦅 Rejoindre la bataille",
        "gaia_join_note": (
            "🦅 Tu as rejoint la bataille sur **{map}** ({count} combattants) —"
            " RDV **{time}** (heure de Paris)."
        ),
        "gaia_join_announce": "🦅 **{lord}** rejoint la bataille sur **{map}** ({count} combattants) !",
        "gaia_gone": "❌ Cette bataille n'accepte plus de participants.",
        "announce_v1_gaia": (
            "\n🦅 D'autres seigneurs peuvent rejoindre la bataille via le bouton"
            " **Rejoindre** du panel Attaquer (jusqu'à {max} combattants) !"
        ),
        "announce_v1": (
            "⚔️ {attacker} du royaume {kingdom} a lancé une attaque sur le royaume"
            " {defender} !\n📅 RDV {time}\nBonne chance aux combattants ! 🍀"
        ),
        "announce_v1_traquenard": (
            "\n🪤 Un Traquenard est actif — l'IA du royaume défenseur est Facile (fenêtre 6h) !"
        ),
        "lord_engaged": (
            "⛔ Tu es engagé dans une bataille en cours — attends son issue avant"
            " d'attaquer, planifier, embusquer ou défendre."
        ),
        "lord_tavern_locked": (
            "⛔ Tu es sous l'effet d'une boisson de la Taverne — attends la fin du verrou"
            " avant d'attaquer, planifier, embusquer ou défendre."
        ),
        "defense_done": "🛡️ **{map}** — tu portes la défense de ton royaume ! RDV **{time}** (Paris).",
        "failed": "❌ {message}",
        "not_a_lord": "❌ Tu n'es pas un seigneur actif d'un royaume.",
        "no_service": "❌ Le service des attaques est indisponible.",
        "no_target": "❌ Aucun royaume adverse attaquable pour le moment.",
        "choose_kingdom": "🎯 **Choisis le royaume à attaquer :**",
        "declare_step_one": "▪️ **Étape 1/2**",
        "declare_step_two": "▪️ **Étape 2/2**",
        "declare_step_chosen": "✅ Royaume ciblé : {kingdom}",
        "protected_line": "🛡️ Sous patrouille (impossible d'attaquer) : {kingdoms}",
        "patrol_kingdom": "**{name}** jusqu'à {end}h00",
        "ai_level_desc": "IA de défense : {level}/5 · {count} territoire(s)",
        "choose_territory": "🗺️ **Choisis le territoire de {kingdom} à attaquer :**",
        "mode_choose": "⚔️ **Déclarer une attaque — choisis ton itinéraire :**",
        "mode_classic_button": "⚔️ Attaque classique — {delay} itinéraire",
        "mode_embuscade_button": "🥷 Utiliser une embuscade — {delay} itinéraire",
        "embuscade_armed_line": (
            "🥷 **Embuscade armée** ({count} restant) — attaque exceptionnelle, hors budget hebdo."
        ),
        "embuscade_warning_line": (
            "⚠️ Le jeton Embuscade est consommé à la déclaration — une annulation"
            " ne le rembourse **jamais**."
        ),
        "embuscade_choose": (
            "🎯 **Embuscade — choisis le territoire cible :**"
            " (attaque exceptionnelle, hors budget hebdo)"
        ),
        "embuscade_note": (
            "🎯 **Embuscade déclarée sur {map}** — itinéraire **{delay} min**, rendez-vous"
            " {time}. La défense ne consomme PAS le point hebdo."
        ),
        "traquenard_hint": (
            "🪤 Info : un royaume peut activer un Traquenard sur son adversaire — l'IA de"
            " défense devient Facile pendant 6h et les mariages scellés prennent +2h de verrou."
        ),
        "cover_question": (
            "🕶️ Utiliser un contre-espionnage ? (1 charge — l'attaque sera annoncée sous"
            " le pseudo d'un autre seigneur — de ton royaume ou d'un autre —"
            " démasqué à la fin du Siège)"
        ),
        "cover_yes_button": "🕶️ OUI — bluffer",
        "cover_no_button": "❌ NON — à visage découvert",
        "choose_cover": (
            "🕶️ Sous l'identité de quel seigneur déclarer l'attaque ?"
            " (tous royaumes, sauf le royaume attaqué)"
        ),
        "when_hm": "{hour}h{minute}",
        "when_today": "aujourd'hui à {time}",
        "when_tomorrow": "demain à {time}",
        "when_other": "le {date} à {time}",
        "thread_body": (
            "📜 **Déroulé de l'attaque & droits du défenseur**\n"
            "• **Siège** — la défense reste ouverte ; à la fin du Siège (reveal), le bluff"
            " (s'il y en a un) tombe et sans défenseur l'IA du royaume prend la défense.\n"
            "• **Draft** — le pick & ban part en MP : 3 civilisations classées de votre"
            " main, validation des deux côtés (les civs partent au salon de la bataille).\n"
            "• **RDV** — un salon vocal de bataille s'ouvre à l'heure du RDV : une absence"
            " au vocal est un forfait.\n"
            "• **Score** — la game : déclarez le résultat avec l'ID de la game.\n"
            "🛡️ N'importe quel seigneur du royaume défenseur peut défendre via le"
            " bouton du panel **Déclarer une attaque**.\n"
            "🪤 Un royaume peut activer un Traquenard sur son adversaire : l'IA de"
            " défense devient Facile pendant 6h et les mariages scellés prennent +2h"
            " de verrou."
        ),
    },
    "en": {
        "panel_title": "⚔️ Battlefield — Attack",
        "panel_help": (
            "Declare an attack on an adversary territory — the meeting is set at the displayed time.\n"
            "Flow: **Siege** (the defense opens at the declaration, in the attack's own salon)"
            " → **Draft** (DM pick & ban) → **Meeting** (confirm your presence) → **Score**"
            " (the game, declare the result)."
        ),
        "panel_pointer": (
            "↳ Every declared attack opens its OWN battle salon right under this"
            " panel — defense, reveal and results live there."
        ),
        "declare_button": "⚔️ Declare an attack",
        "history_button": "📜 History of confrontations",
        "attack_info_button": "⚔️ Attack / defense information",
        "history_title": "📜 **History of confrontations**",
        "history_empty": "🕊️ No finished confrontation yet.",
        "history_line": "• **{date}** — **{map}** · {attacker} ⚔️ {defender} — {outcome}",
        "history_outcome_win": "victory of **{kingdom}**",
        "history_outcome_cancelled": "🏳️ attack cancelled",
        "history_outcome_double": "🏳️ double forfeit",
        "history_outcome_expired": "⏳ expired with no outcome",
        "history_page": "Page {page}/{pages}",
        "itinerary_line": "⚔️ Itinerary: execution **{minutes} min** after the declaration.",
        "itinerary_note": (
            "⚔️ Attack declared on **{map}** — itinerary: execution in **{delay} min**"
            " — meeting {time}."
        ),
        "cancel_attack_button": "❌ Cancel the attack",
        "cancel_attack_done": (
            "🏳️ **Attack cancelled** — attack budget refunded"
            " (the defense refunded too when one was recorded). The attack salon disappears."
        ),
        "cancel_attack_embuscade_done": (
            "🏳️ **Ambush cancelled** — but the Ambush token stays **consumed**:"
            " it is never refunded, even on a cancellation. The attack salon disappears."
        ),
        "cancel_attack_cover_refunded": (
            "🕵️ The cover (Counter-espionage) returns to the kingdom's stock."
        ),
        "defend_wrong_kingdom": "❌ You cannot defend this territory.",
        "defend_button": "🛡️ Defend",
        "defend_already": "❌ The kingdom is already defended.",
        "gaia_join_button": "🦅 Join the battle",
        "gaia_join_note": (
            "🦅 You joined the battle on **{map}** ({count} fighters) —"
            " meeting **{time}** (Paris time)."
        ),
        "gaia_join_announce": "🦅 **{lord}** joins the battle on **{map}** ({count} fighters)!",
        "gaia_gone": "❌ This battle no longer accepts participants.",
        "announce_v1_gaia": (
            "\n🦅 Other lords may join the battle through the **Join** button of"
            " the Attack panel (up to {max} fighters)!"
        ),
        "announce_v1": (
            "⚔️ {attacker} of the kingdom {kingdom} launched an attack on the kingdom"
            " {defender}!\n📅 Meeting {time}\nGood luck to the fighters! 🍀"
        ),
        "announce_v1_traquenard": (
            "\n🪤 A Traquenard is active — the defending kingdom's AI is Easy (6h window)!"
        ),
        "lord_engaged": (
            "⛔ You are engaged in an ongoing battle — wait for its outcome before"
            " attacking, planning, ambushing or defending."
        ),
        "lord_tavern_locked": (
            "⛔ You are under a tavern drink's effect — wait for the lock to end before"
            " attacking, planning, ambushing or defending."
        ),
        "defense_done": "🛡️ **{map}** — you carry your kingdom's defense! Meeting **{time}** (Paris).",
        "failed": "❌ {message}",
        "not_a_lord": "❌ You are no active lord of a kingdom.",
        "no_service": "❌ The attack service is unavailable.",
        "no_target": "❌ No attackable adversary kingdom for now.",
        "choose_kingdom": "🎯 **Pick the kingdom to attack:**",
        "declare_step_one": "▪️ **Step 1/2**",
        "declare_step_two": "▪️ **Step 2/2**",
        "declare_step_chosen": "✅ Targeted kingdom: {kingdom}",
        "protected_line": "🛡️ Under patrol (impossible to attack): {kingdoms}",
        "patrol_kingdom": "**{name}** until {end}:00",
        "ai_level_desc": "Defense AI: {level}/5 · {count} territory(ies)",
        "choose_territory": "🗺️ **Pick the territory of {kingdom} to attack:**",
        "mode_choose": "⚔️ **Declare an attack — pick your itinerary:**",
        "mode_classic_button": "⚔️ Classic attack — {delay} itinerary",
        "mode_embuscade_button": "🥷 Use an ambush — {delay} itinerary",
        "embuscade_armed_line": (
            "🥷 **Ambush armed** ({count} left) — exceptional attack, outside the weekly budget."
        ),
        "embuscade_warning_line": (
            "⚠️ The Ambush token is consumed at the declaration — a cancellation"
            " never refunds it."
        ),
        "embuscade_choose": (
            "🎯 **Ambush — pick the target territory:**"
            " (exceptional attack, outside the weekly budget)"
        ),
        "embuscade_note": (
            "🎯 **Ambush declared on {map}** — itinerary **{delay} min**, meeting"
            " {time}. The defense does NOT consume the weekly point."
        ),
        "traquenard_hint": (
            "🪤 Info: a kingdom may activate a Traquenard on its adversary — the defense"
            " AI becomes Easy for 6h and sealed marriages take a +2h lock."
        ),
        "cover_question": (
            "🕶️ Use a counter-espionage? (1 charge — the attack is announced under"
            " another lord's name — yours or a foreign one — unmasked at the end of the Siege)"
        ),
        "cover_yes_button": "🕶️ YES — bluff",
        "cover_no_button": "❌ NO — open-faced",
        "choose_cover": (
            "🕶️ Under which lord's identity do you declare the attack?"
            " (every kingdom, except the attacked one)"
        ),
        "when_hm": "{hour}:{minute}",
        "when_today": "today at {time}",
        "when_tomorrow": "tomorrow at {time}",
        "when_other": "on {date} at {time}",
        "thread_body": (
            "📜 **Attack rundown & the defender's rights**\n"
            "• **Siege** — the defense stays open; at the end of the Siege (reveal), the"
            " bluff (when there is one) falls and without a defender the kingdom's AI"
            " takes the defense.\n"
            "• **Draft** — the pick & ban goes to the DMs: 3 civilizations ranked from your"
            " hand, validation on both sides (the civs go to the battle salon).\n"
            "• **Meeting** — a battle voice salon opens at the meeting hour: an absence"
            " at the voice is a forfeit.\n"
            "• **Score** — the game: declare the result with the game id.\n"
            "🛡️ Any lord of the defending kingdom may defend through the button of the"
            " **Declare an attack** panel.\n"
            "🪤 A kingdom may activate a Traquenard on its adversary: the defense AI"
            " becomes Easy for 6h and sealed marriages take a +2h lock."
        ),
    },
}


def strings(locale: str) -> dict[str, str]:
    """The attack strings for one locale (defaults + catalog overrides)."""
    base = dict(DEFAULTS["fr"] if str(locale).lower().startswith("fr") else DEFAULTS["en"])
    try:
        from botforge.core.services.i18n import MessageCatalog

        section = MessageCatalog("config").section("kingdom.attack", str(locale)[:2])
        base.update({key: value for key, value in section.items() if value})
    except Exception:
        pass
    return base


__all__ = ["DEFAULTS", "strings"]
