"""The persistent realm's strings (royaume-persistant-v1) — fr/en parity.

Data rules: the artwork URL and every player-facing line are DATA
(#369 — season 2 tunes them without touching code). The hub flavor is
the designer's 20/11 capture, verbatim for fr.
"""

from __future__ import annotations

_Strings = dict[str, str]

_REALM_STRINGS: dict[str, _Strings] = {
    "fr": {
        # the hub's illustration (the mod's Lieux artwork, data — the
        # designer's 21/11 ask; swap the URL, never the code)
        "realm_artwork": (
            "https://raw.githubusercontent.com/jj-guild/botforge-services/"
            "c76f4aa07a82c8d75292a628315fb60d21fa9265/modules/mods/kingdom/"
            "assets/lieux/Royaume.png"
        ),
        "realm_hub_title": "🏰 {0}",
        "realm_hub_flavor": (
            "Les portes du château s'ouvrent — chaque lieu du royaume vit "
            "derrière sa porte. L'état du royaume siège en Salle du conseil."
        ),
        "realm_hub_dormant_note": (
            "-# Le royaume est hors saison — ses salles se rouvriront à "
            "l'entrée en saison."
        ),
        "realm_enter_button": "🏰 Entrée",
        # hub-dormant-actions (Drasah 21/11): à droite de l'Entrée, le
        # royaume endormi porte sa saison — la vue + l'acte du Roi
        "realm_hub_join_button": "⚔️ Inscrire son royaume",
        "realm_hors_jeu_zone": "⚙️ Réglages hors-jeu — ceci ne fait pas partie du jeu",
        "realm_user_settings_button": "⚙️ Paramètres utilisateur",
        "realm_gone_note": "Ce royaume n'existe plus.",
        "realm_error_note": "Une panne passagère — la porte s'est refermée, retente dans un instant.",
        "home_title": "🏰 {0} — chez soi",
        "home_intro": "Royaume de **{king}** · {count}",
        "home_members_line": "{count} membre(s)",
        "home_presentation_excerpt": "📝 {0}",
        "home_join_pending": "📬 Une demande d'entrée en saison est en attente de validation.",
        "home_not_member": "Seuls les membres du royaume peuvent entrer chez eux.",
        "seigneurie_button": "🛡️ Ma seigneurie",
        "seigneurie_title": "Ma seigneurie — {0}",
        "seigneurie_foundation": "📜 Fondé le {when} par **{king}**",
        "seigneurie_crown_hint": "Transfert de couronne — choisis le nouveau Roi :",
        "seigneurie_crown_placeholder": "👑 Le nouveau Roi",
        "crown_done": "👑 La couronne est transmise — le royaume change de Roi.",
        "crown_error": "❌ Transfert refusé : seul le Roi tranche, vers un membre.",
        "presentation_button": "📝 Présentation",
        "presentation_title": "📝 Présentation — {0}",
        "presentation_empty": "_Aucune présentation pour l'instant — le Roi peut écrire ici._",
        "presentation_king_hint": "-# Réservée au Roi : la vitrine du royaume pour « Joindre un Royaume ».",
        "presentation_edit_button": "✏️ Modifier",
        "presentation_modal_title": "📝 La présentation du royaume",
        "presentation_saved": "✅ Présentation enregistrée.",
        "presentation_error": "❌ Seul le Roi peut écrire la présentation.",
        "season_button": "📺 Voir la saison",
        "season_title": "📺 Voir la saison",
        "season_none": (
            "Pas de saison en cours — un admin doit lancer la saison depuis le cockpit ⚙️. "
            "Dès qu'elle existe (et si le sas est ouvert), le bouton « S'inscrire à la saison » apparaîtra ici."
        ),
        "season_running": "Une saison est en cours (démarrée le {when}).",
        "season_join_hint": (
            "Le royaume peut demander son entrée dans la saison — un admin "
            "acceptera ou refusera (la draft starter est l'acte d'entrée)."
        ),
        "season_join_button": "S'inscrire à la saison",
        "season_join_closed": (
            "⛔ Le sas des inscriptions à la saison est fermé pour le "
            "moment (la régie du serveur décide)."
        ),
        "season_join_requested": "📬 Demande d'entrée en saison envoyée — un admin la validera.",
        "season_join_pending": "📬 Une demande d'entrée en saison est déjà en attente.",
        "season_join_error": "❌ La demande a échoué : seul le Roi peut l'envoyer.",
        "season_engaged_line": "🏆 Le royaume joue la saison **{season}** — royaume moteur : **{kingdom}**. Les salons sont ouverts.",
        "palmares_button": "🏆 Palmarès",
        "palmares_title": "🏆 Palmarès — {0}",
        "palmares_empty": "Le royaume n'a pas encore joué de saison.",
        "palmares_line": "• **{season}** {note}",
        "quit_button": "🚪 Quitter le royaume",
        "quit_done": "🚪 Tu as quitté le royaume — à bientôt.",
        "quit_error": "❌ Le Roi ne peut pas quitter son royaume (transfert ou dissolution).",
    },
    "en": {
        "realm_artwork": (
            "https://raw.githubusercontent.com/jj-guild/botforge-services/"
            "c76f4aa07a82c8d75292a628315fb60d21fa9265/modules/mods/kingdom/"
            "assets/lieux/Royaume.png"
        ),
        "realm_hub_title": "🏰 {0}",
        "realm_hub_flavor": (
            "The castle gates open — every place of the realm lives behind "
            "its door. The realm's state sits in the Council chamber."
        ),
        "realm_hub_dormant_note": (
            "-# The realm is off-season — its halls reopen on season entry."
        ),
        "realm_enter_button": "🏰 Enter",
        # hub-dormant-actions (Drasah 21/11): beside the door, the
        # dormant realm carries its season — the view + the King's act
        "realm_hub_join_button": "⚔️ Enroll the realm",
        "realm_hors_jeu_zone": "⚙️ Out-of-game settings — this is not part of the game",
        "realm_user_settings_button": "⚙️ User settings",
        "realm_gone_note": "This realm no longer exists.",
        "realm_error_note": "A passing glitch — the door closed on its own, try again in a moment.",
        "home_title": "🏰 {0} — home",
        "home_intro": "Realm of **{king}** · {count}",
        "home_members_line": "{count} member(s)",
        "home_presentation_excerpt": "📝 {0}",
        "home_join_pending": "📬 A season entry request is awaiting validation.",
        "home_not_member": "Only the realm's members may enter their home.",
        "seigneurie_button": "🛡️ My lordship",
        "seigneurie_title": "My lordship — {0}",
        "seigneurie_foundation": "📜 Founded on {when} by **{king}**",
        "seigneurie_crown_hint": "Crown transfer — pick the next King:",
        "seigneurie_crown_placeholder": "👑 The next King",
        "crown_done": "👑 The crown is handed over — the realm has a new King.",
        "crown_error": "❌ Transfer refused: only the King may hand the crown to a member.",
        "presentation_button": "📝 Presentation",
        "presentation_title": "📝 Presentation — {0}",
        "presentation_empty": "_No presentation yet — the King may write here._",
        "presentation_king_hint": "-# King only: the realm's showcase for « Join a Realm ».",
        "presentation_edit_button": "✏️ Edit",
        "presentation_modal_title": "📝 The realm's presentation",
        "presentation_saved": "✅ Presentation saved.",
        "presentation_error": "❌ Only the King may write the presentation.",
        "season_button": "📺 Watch the season",
        "season_title": "📺 Watch the season",
        "season_none": (
            "No season running — an admin must launch the season from the cockpit ⚙️. "
            "As soon as it exists (and the sas is open), the « Join the season » button appears here."
        ),
        "season_running": "A season is running (started {when}).",
        "season_join_hint": (
            "The realm may request its season entry — an admin will "
            "accept or refuse (the starter draft IS the act of entry)."
        ),
        "season_join_button": "Sign up for the season",
        "season_join_closed": (
            "⛔ The season-entry sas is closed right now (the server's "
            "régie decides)."
        ),
        "season_join_requested": "📬 Season entry request sent — an admin will validate it.",
        "season_join_pending": "📬 A season entry request is already pending.",
        "season_join_error": "❌ The request failed: only the King may send it.",
        "season_engaged_line": "🏆 The realm plays season **{season}** — engine kingdom: **{kingdom}**. The halls are open.",
        "palmares_button": "🏆 Records",
        "palmares_title": "🏆 Records — {0}",
        "palmares_empty": "The realm has not played a season yet.",
        "palmares_line": "• **{season}** {note}",
        "quit_button": "🚪 Leave the realm",
        "quit_done": "🚪 You left the realm — see you soon.",
        "quit_error": "❌ The King cannot leave his realm (transfer or dissolution).",
    },
}


def realm_strings(locale: str) -> _Strings:
    """The realm strings for one locale (fr default)."""
    base = _REALM_STRINGS["fr"] if str(locale).lower().startswith("fr") else _REALM_STRINGS["en"]
    return dict(base)


__all__ = ["realm_strings"]
