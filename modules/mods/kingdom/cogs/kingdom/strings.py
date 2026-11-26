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
        "defend_cancelled": (
            "🏳️ Cette attaque a été annulée par son déclarant — elle n'attend plus de défense."
        ),
        "cancel_attack_defender_dm": (
            "🗡️ L'attaque que vous défendiez sur **{map}** a été annulée par son déclarant"
            " — votre budget de défense est intégralement remboursé."
        ),
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
        "reveal_cover": (
            "🕶️ Reveal — l'attaque sur **{map}** était menée par **{attacker}** du"
            " royaume **{attacker_kingdom}**, sous la couverture de **{cover}** du"
            " royaume **{cover_kingdom}**. La couverture tombe."
        ),
        "reveal_ai": (
            "🤖 Personne n'a défendu **{map}** — l'IA du royaume **{kingdom}** prend la défense"
            " (niveau **{level}**/5) !"
        ),
        "reveal_defense": "🛡️ La défense de **{map}** est verrouillée — RDV **{time}** (Paris).",
        "matchup_note": (
            "⚔️ **{attacker}** 🆚 **{defender}** — les deux drafts sont résolus : RDV à l'heure prévue."
        ),
        "matchup_v1": (
            "🆚 **{attacker}** VS **{defender}** — les deux drafts sont armés,"
            " la rencontre peut commencer !"
        ),
        "matchup_ai": (
            "🆚 **{attacker}** VS **IA {kingdom}** — niveau de l'IA : **{level}**/5.\n"
            "🎮 Rappel : l'attaquant crée la partie en **multijoueur** (jamais en local)"
            " avec **spectateurs autorisés**."
        ),
        "reveal_battle_anon": "⚔️ Bataille en vue",
        "forfeit_both": (
            "🏳️ Forfait général sur **{map}** — personne n'a validé : l'attaquant, présent, l'emporte (**{kingdom}**)."
        ),
        "forfeit_side": "🏳️ Forfait sur **{map}** — **{side}** a manqué la validation : victoire de **{kingdom}**.",
        "forfeit_geo_side": "🏳️ **{map}** : forfait de {side} — victoire de **{winner}** par forfait.",
        "forfeit_geo_both": (
            "🏳️ **{map}** : forfait général — aucun camp n'a validé, **{winner}** l'emporte par forfait."
        ),
        "side_attacker": "l'attaquant",
        "side_defender": "le défenseur",
        "noshow_side": "🏳️ **{map}** — **{side}** a manqué le RDV : victoire de **{kingdom}**.",
        "noshow_both": "🏳️ **{map}** — double forfait : aucun joueur au RDV, le territoire reste à son propriétaire.",
        "pickban_dm": (
            "⚔️ **Pick & ban — {map}**\nClasse tes **{count}** pick de civilisation par ordre de préférence "
            "(ton classement ordonne les replis).\n"
            "🕒 **Fermeture de la fenêtre : {deadline}** (heure du RDV).\n"
            "Si tu possèdes un Sabotage ou un Faucon, tu pourras en faire usage dans le salon de la bataille.\n"
            "\n"
            "⚠️ **Règle anti-blocage** : si tu ne valides aucun choix avant le RDV, "
            "3 civilisations seront tirées **au hasard** de ta main — et aucun "
            "sabotage ni faucon ne s'appliquera. Le RDV a lieu quoi qu'il arrive.\n"
            "Ta main : {hand}\nMain adverse : {theirs}"
        ),
        "pickban_dm_failed_sal": (
            "⚠️ <@{player}> — le DM de draft n'a pas pu t'être remis (messages "
            "privés fermés pour ce serveur ou pour ce bot). Vérifie tes réglages "
            "Discord **tout de suite** : sans classement avant le RDV, la draft "
            "sera tirée au hasard."
        ),
        "pickban_pick": "Choix {n}",
        "pickban_validate": "✅ Valider",
        "pickban_missing": "❌ Classe d'abord tes {count} civilisations.",
        "pickban_duplicate": (
            "❌ Vous ne pouvez pas avoir de doublons dans vos choix de civilisations."
        ),
        "pickban_waiting": "⏳ Picks enregistrés et validés — en attente de l'adversaire.",
        "pickban_modify_button": "♻️ Tout recommencer",
        "pickban_reveal_adversary": "**Draft de votre adversaire :**",
        "pickban_own_picks_line": "**Tes picks :** {picks}",
        "pickban_reveal_dm": (
            "🎭 **Reveal — {map}**\n🕒 **RDV : {deadline}** — la fenêtre de"
            " sabotage se ferme à cette heure.\n🗡️ Veux-tu saboter ou"
            " utiliser un Faucon ? — jusqu'à 2 civilisations adverses"
            " retirées par camp.\n⚔️ Sinon, valide avec Passer — un joueur"
            " absent du salon vocal à l'heure du RDV est déclaré forfait !"
        ),
        "pickban_default_reveal_dm": (
            "🎭 **Reveal — {map}**\n⏱️ Le draft a été clôturé à l'heure : les"
            " civilisations jamais classées ont été tirées au sort (aucun"
            " sabotage ni Faucon).\n🕒 Le RDV a lieu maintenant — rejoins le"
            " salon vocal."
        ),
        "attack_cancelled_dm": "❌ L'attaque sur **{map}** a été annulée — le draft est clos.",
        "sab_open_button": "🗡️ Saboter / Utiliser un Faucon",
        "sab_pass_button": "⚔️ Passer — je suis prêt",
        "sab_no_resources": (
            "🕊️ **Vous ne disposez pas de sabotage ni de Faucon** — en attente"
            " de ton adversaire. Tu peux valider avec ⚔️ Passer."
        ),
        "sab_faucon": "🦅 Faucon",
        "sab_techno": "🧪 Sabotage",
        "sab_choose": "🎯 **Choisis la civilisation adverse à retirer :**",
        "sab_pick_line": "🎯 {action} : **{civ}**",
        "sab_modify_button": "✏️ Modifier",
        "sab_validate_button": "✅ Valider",
        "sab_cancel_button": "❌ Annuler",
        "sab_done": "🪶 **{civ}** retirée du camp adverse.",
        "sab_settled": "✅ Ton camp a validé — en attente de l'autre camp…",
        "sab_phase_done": (
            "🎭 **Phase de sabotage terminée — {map}**\nRejoins le salon vocal à"
            " l'heure du RDV : les civilisations finales y seront affichées."
        ),
        "sab_over": "🕊️ La phase de sabotage est terminée.",
        "sab_empty": "🕊️ Aucune civilisation adverse disponible.",
        "sab_not_player": "❌ Seuls les deux joueurs du match peuvent agir ici.",
        "sab_stock_line": (
            "🗡️ Sabotage : {sabotage} · 🦅 Faucon : {faucon}\n"
            "Un camp ne peut subir que 2 civilisations sabotées maximum."
        ),
        "sab_faucon_ready": "dispo",
        "sab_faucon_flying": "en vol jusqu'à {time}",
        "sab_faucon_absent": "absent",
        "sab_panel_title": "🪶 **Sabotage** — {used}/2 civilisations retirées sur cette attaque",
        "sab_panel_used": "Retirées : {list}",
        "sab_panel_none": "Aucune civilisation retirée pour l'instant.",
        "sab_panel_done": "🪶 **{civ}** retirée du camp adverse — {used}/2.",
        "sab_again_ask": "🗡️ Veux-tu saboter une autre civilisation ?",
        "sab_again_yes": "Oui — un autre sabotage",
        "sab_again_no": "Non — j'ai fini",
        # -- battle room / meeting (P4.1b tranche 2b) --
        "room_not_player": "❌ Seuls les deux joueurs du match peuvent agir ici.",
        "defender_ai": "IA 🤖",
        "room_role": "Bataille {map}",
        "room_scoreboard_map": "⚔️ {map}",
        "room_scoreboard_id": "🆔 ID : {id}",
        "room_side_attacker": "Attaquant",
        "room_side_defender": "Défenseur",
        "room_side_ready": "✅ Prêt",
        "room_side_wait": "⏳ en attente du Prêt",
        "room_side_none": "🔗 en attente de l'ID",
        "room_side_ai": "🤖 IA — niv. {level}/5",
        "room_ai_disclaimer": (
            "⚠️ **IA de niveau {level}/5** — la partie se joue en multijoueur"
            " avec un ID (jamais en local) pour rester traçable et vérifiable"
            " post-game. Le joueur est cru sur parole ; toute fraude présumée"
            " peut être contestée ⚖️ puis arbitrée par les admins."
        ),
        "room_id_button": "🔗 Renseigner l'ID",
        "room_id_modify_button": "🔴 Modifier l'ID",
        "room_id_pending_button": "⏳ Saisie de l'ID en cours…",
        "room_id_locked_other": (
            "⏳ L'autre joueur saisit l'ID de la partie en ce moment — réessaie dans un instant."
        ),
        "room_ready_button": "✅ Prêt",
        "room_ready_attacker_button": "⚔️ Prêt — {player}",
        "room_ready_defender_button": "Prêt 🛡️ — {player}",
        "room_ready_done_attacker_button": "⚔️ Je suis prêt ! — {player}",
        "room_ready_done_defender_button": "Je suis prêt ! 🛡️ — {player}",
        "room_not_your_side": "⛔ Ce bouton Prêt est réservé à votre adversaire.",
        "room_ready_needs_url": (
            "🔗 Renseigne d'abord l'ID de la partie (bouton 🔗) — le bouton ✅ Prêt n'apparaît qu'après."
        ),
        "room_scoreboard_footer": (
            "🎮 Les deux joueurs sont prêts — bonne game ! Déclarez le vainqueur avec 🏆."
        ),
        "room_ping_message": (
            "⚔️ {attacker} {defender} — la salle de bataille est ouverte, à vos armes !"
        ),
        "room_ping_attacker_only": "⚔️ {attacker} — la salle de bataille est ouverte, à vos armes !",
        "room_ping_winner": "🏆 Vainqueur : **{winner}**",
        "room_dm": (
            "🏟️ **Tiens-toi prêt — {map}**\n"
            "Rejoins ton adversaire en vocal : {room}\n"
            "Rejoins le salon textuel pour continuer : {salon}"
        ),
        "room_dm_deadline": (
            "\n\n⏳ Présence obligatoire (vocal ou ✅ Prêt) avant {deadline} —"
            " passé ce délai, un absent est déclaré forfait."
        ),
        "room_dm_luck": "\n\nBonne chance ! 🍀",
        "room_event_name": "⚔️ {map} — {attacker} 🆚 {defender}",
        "room_vocal_ai": "l'IA",
        "room_event_description": (
            "⚔️ Bataille Kingdom en direct — {attacker} 🆚 {defender}.\n"
            "Civilisations et boutons de jeu : dans le salon vocal de la bataille."
        ),
        "draft_button": "📜 Voir la draft",
        "draft_sheet": "📜 Draft — {map}",
        "draft_mode_player": "Choix du joueur",
        "draft_mode_random": "Choix aléatoire",
        "draft_source_techno": "🗡️ Sabotage",
        "draft_source_faucon": "🦅 Faucon",
        "draft_sheet_help": (
            "Ordre des choix des joueurs durant la draft — ordre réel"
            " une fois la phase de sabotage terminée (aléatoire et"
            " classement secret pendant la phase), les sabotées barrées :"
        ),
        "result_button": "🏆 Déclarer le vainqueur",
        "result_select_title": "🏆 **Qui remporte la partie ?**",
        "result_select_placeholder": "Le vainqueur de la game",
        "result_confirm_title": "🏆 **Vainqueur : {winner}** — confirmer ce résultat ?",
        "result_confirm_button": "✅ Confirmer",
        "result_edit_button": "✏️ Modifier",
        "result_review_title": "⏳ **{player} a déclaré {winner} vainqueur.**",
        "result_review_confirm_button": "✅ Confirmer le résultat",
        "result_review_contest_button": "⚖️ Contester",
        "result_mine_title": "⏳ **Ton choix : {winner}** — tu peux le modifier ci-dessous.",
        "result_not_ready": (
            "⏳ Le bouton Déclarer le vainqueur apparaît une fois que les deux joueurs sont Prêts."
        ),
        "score_url_modal_title": "ID de la partie",
        "score_url_modal_label": "ID de la partie",
        "score_url_modal_placeholder": "ex. 123456",
        "score_pending": (
            "⏳ Résultat enregistré (game {game}) — il sera appliqué sauf"
            " contestation de l'autre joueur dans les {minutes} prochaines minutes."
        ),
        "score_resolved": "🏆 Résultat enregistré — **{winner}** remporte **{map}** (game {game}).",
        "score_already": "✅ Ce résultat était déjà enregistré — rien à faire.",
        "score_disputed": (
            "⚖️ Déclaration contradictoire — les admins arbitrent (game {game})."
            "\nVeuillez prendre contact avec un admin."
        ),
        "score_auto_dispute_open": (
            "⚖️ Litige ouvert automatiquement (délai dépassé, aucun résultat"
            " déclaré) — un admin tranche (game {game}). Patiente."
        ),
        "score_reminder_dm": (
            "⏰ **RDV — {map}** : aucun résultat déclaré depuis 3h — déclare le"
            " résultat de la game avec le bouton 🏆 du salon de la bataille !"
        ),
        "auto_dispute": (
            "⚖️ **Litige auto-ouvert sur {map}** — aucun résultat déclaré 15 h après"
            " l'ouverture de la partie : un admin tranche via la console (`resultat`)."
        ),
        "conquest_title": "⚔️ Le Royaume **{winner}** a conquis **{map}** !",
        "conquest_defense_title": "🛡️ Le Royaume **{winner}** a défendu **{map}** !",
        "conquest_thread": "Détail de la conquête",
        "conquest_thread_defense": "Détail de la défense",
        "conquest_attacker_line": "⚔️ Attaquant : **{player}** ({kingdom})",
        "conquest_defense_line": "🛡️ Défense : **{player}** ({kingdom})",
        "conquest_ai_defense": "🛡️ Défense : IA du royaume **{kingdom}** (niveau {level})",
        "conquest_civ_line": "🎯 {player} jouait **{civ}**",
        "conquest_embuscade_line": "🥷 Embuscade utilisée",
        "conquest_sabotages_line": "🧨 Sabotages ({side}, Faucon/Techno) : {civs}",
        "conquest_id_line": "🔗 ID de la partie : **{game}**",
        "conquest_none": "aucune",
        "conquest_side_attacker": "attaquant",
        "conquest_side_defender": "défenseur",
        "conquest_married_lost": "💔 **{player}** perd son lien sacré avec la civilisation **{civ}**.",
        "dispute_admin_dm": "⚖️ **Litige — {map}**\n{declarations}\nTranche le résultat (game {game}).",
        "dispute_dm_open": (
            "⚖️ Il semblerait que vous n'ayez pas choisi le même vainqueur de la "
            "partie, votre choix était **{winner}**.\n"
            "Nous vous proposons de modifier ou de confirmer votre choix.\n"
            "-# En cas de litige, un admin prendra le relais."
        ),
        "dispute_dm_confirmed": (
            "✅ Ton choix (**{winner}**) est enregistré — en attente de ton "
            "adversaire.\n-# En cas de litige, un admin prendra le relais."
        ),
        "dispute_dm_handover": (
            "⚖️ Le litige persiste — un admin prend le relais et vous contactera ici."
        ),
        "dispute_dm_resolved": (
            "✅ Litige clos — vous avez désigné le même vainqueur : **{winner}**."
        ),
        "dispute_confirm_button": "✅ Confirmer mon choix",
        "dispute_win_attacker": "⚖️ Tranche : attaquant",
        "dispute_win_defender": "⚖️ Tranche : défenseur",
        "dispute_double": "🏳️ Double forfait",
        "dispute_applied": "⚖️ Arbitrage appliqué — **{kingdom}** remporte **{map}**.",
        "dispute_forfeit": "⚖️ Arbitrage appliqué — double forfait sur **{map}**.",
        "dispute_not_admin": "❌ Seuls les bot-admins arbitrent un litige.",
        # -- decisions-admin-v1 (Drasah 25/11) : la boîte de réception
        # admin + la raison obligatoire + l'annonce aux royaumes --
        "dispute_cancel_button": "✖️ Annuler l'attaque",
        "decision_reason_modal_title": "⚖️ Décision admin",
        "decision_reason_label": "Raison (obligatoire, visible)",
        "decision_reason_placeholder": "ex. résultat non déclaré, aucun contre-élément…",
        "decision_reason_required": (
            "❌ La raison est OBLIGATOIRE — la décision n'a pas été appliquée."
        ),
        "decision_applied_cancel": (
            "✖️ Décision appliquée — **{map}** est annulée : aucun vainqueur, aucun point,"
            " verrou levé, slots libérés."
        ),
        "decision_announce_arbitrage": (
            "⚖️ **Décision admin** — l'attaque sur **{map}** (game {game}) est arbitrée :"
            " **{winner}** remporte la rencontre.\n"
            "Décidée par <@{admin}> — Raison : {reason}"
        ),
        "decision_announce_cancel": (
            "⚖️ **Décision admin** — l'attaque sur **{map}** (game {game}) est ANNULEE :"
            " aucun vainqueur, aucun point, les verrous sont levés.\n"
            "Décidée par <@{admin}> — Raison : {reason}"
        ),
        "decision_summary_arbitrage": "arbitrage — {winner} remporte {map}",
        "decision_summary_both": "double forfait — {map}",
        "decision_summary_cancel": "annulation — {map}",
        "decision_kind_auto": "Litige auto-ouvert (délai sans résultat).",
        "decision_kind_declarations": "Déclarations contradictoires des joueurs.",
        "decision_action_title": "⚖️ Décision admin",
        "decision_action_header": "Attaque sur **{map}** — tranche ou annule.",
        "decision_action_live_header": (
            "Attaque **en cours** sur **{map}** — l'annulation admin rembourse"
            " les budgets et ferme l'habitat sur place."
        ),
        "decision_state_declared": "siège (défense ouverte)",
        "decision_state_defended": "draft en cours",
        "decision_state_meeting": "RDV en cours",
        "decision_decide_button": "⚖️ Décider",
        # -- planning (P4.1b tranche 2d) --
        "plan_button": "📅 Planifier une attaque",
        "plan_disclaimer": (
            "⚠️ Une plannification ne réserve pas le territoire : si un autre royaume déclare"
            " une attaque dessus avant l'heure choisie, ta plannification basculera sur ton"
            " choix suivant — ou sera rompue s'il n'en reste aucun."
        ),
        "plan_wizard_title": "📅 Planifier une attaque",
        "plan_time_day_label": "Jour du RDV",
        "plan_time_day_today": "Aujourd'hui — {date}",
        "plan_time_day_tomorrow": "Demain — {date}",
        "plan_time_hour_label": "Heure",
        "plan_time_minute_label": "Minute",
        "plan_time_hint": (
            "Choisis le jour, l'heure et la minute du RDV (heure de Paris), puis valide."
            " Règle d'or : 24h maximum à l'avance."
        ),
        "plan_time_validate_button": "✅ Valider l'heure",
        "plan_time_invalid": (
            "❌ Ce RDV est impossible : il doit être dans le futur et dans les 24h."
            " Choisis un autre créneau."
        ),
        "plan_confirm_title": "📅 Planification — choix 1 : **{map}** · RDV **{time}** (Paris)",
        "plan_choice2_placeholder": "Choix 2 (facultatif)",
        "plan_choice3_placeholder": "Choix 3 (facultatif)",
        "plan_confirm_button": "✅ Confirmer la planification",
        "plan_dm_header": "📅 Plannification d'attaque — {map}",
        "plan_choices_line": "Choix {n} : **{map}**{active}",
        "plan_active_tag": " ✅",
        "plan_dm_time": "RDV : **{time}** (Paris) — déclaration automatique à **{declare_time}** (Paris).",
        "plan_dm_budget": "Le budget d'attaque (⚔️) sera consommé à la DÉCLARATION — pas maintenant.",
        "plan_created_note": "📅 Plannification enregistrée — le récap est dans tes messages privés.",
        "plan_no_dm": "⚠️ Plannification enregistrée, mais l'envoi du MP a échoué (MPs fermés ?).",
        "plan_failed": "❌ La plannification a échoué : {message}",
        "plan_cancel_button": "❌ Annuler ma plannification",
        "plan_cancelled_ephemeral": "❌ Plannification annulée — aucun budget n'a été consommé.",
        "plan_event_executed": (
            "✅ Ton attaque planifiée a été DÉCLARÉE sur **{map}** — RDV **{time}** (Paris)."
            " Le budget d'attaque a été consommé à la déclaration."
        ),
        "plan_event_switched": (
            "⚠️ Ton choix sur **{old}** ne peut aboutir (la bataille a déjà été déclarée dessus)"
            " — bascule sur le choix suivant : **{map}**."
        ),
        "plan_event_broken": (
            "⛔ Ton attaque planifiée ne peut aboutir : la bataille a déjà été déclarée"
            " sur **{map}** et aucun autre choix n'est disponible. Aucun budget n'a été consommé."
        ),
        "plan_event_cancelled": "❌ Ta plannification a été annulée — aucun budget n'a été consommé.",
        "plan_no_service": "❌ Le service des attaques est indisponible.",
        "market_button": "💰 Marché",
        "chamber_button": "🏛️ Comptes",
        "market_title": "💰 Marché du Royaume",
        "market_rules": (
            "**Paiement d'abord** — tout achat débite la banque du royaume.\n"
            "Une carte achetée vit dans la Chambre des comptes."
        ),
        "market_wallet": "💰 Banque du royaume : **{0}** ⚙️",
        # marche-reference-v1 (Affaire 24) : l'étal du marchand, ses
        # quatre rayons, ses cartes TCG — portés de la référence.
        "market_hint_panel": (
            "👑 Seul le Roi d'un royaume peut acheter — chaque achat débite "
            "immédiatement le trésor du royaume (coût affiché par article)."
        ),
        "market_section_ia": "🤖 Gestion de la défense / attaque IA",
        "market_section_defense": "🛡️ Défense du royaume",
        "market_section_attaque": "⚔️ Amélioration de l'attaque",
        "market_section_speciales": "✨ Actions spéciales",
        "market_tech": {  # type: ignore[dict-item]
            "embuscade": "🥷 Embuscade",
            "traquenard": "🪤 Traquenard",
            "contre_espionnage": "👀 Contre-espionnage",
            "sabotage": "🗡️ Sabotage",
            "jeu_d_armes": "⚔️ Jeu d'armes",
        },
        "market_action": {  # type: ignore[dict-item]
            "explorateur": "🧭 Explorateur",
            "corruption": "💰 Corruption",
            "garde_royale": "💂 Garde Royale",
            "patrouille": "👣 Patrouille",
            "mariage_arrange": "💐 Mariage arrangé",
        },
        "market_effect": {  # type: ignore[dict-item]
            "embuscade": (
                "Déclare une attaque exceptionnelle sans point d'attaque. "
                "Défendre une embuscade utilise aussi une défense "
                "exceptionnelle."
            ),
            "traquenard": (
                "À l'usage : l'IA affrontée devient Facile durant une "
                "fenêtre cumulée de 2h par activation, et les verrous "
                "vivants du royaume ciblé (mariages, exploration, boisson "
                "de taverne) prennent +2h en one-shot."
            ),
            "contre_espionnage": (
                "Lorsque vous attaquez, vous pouvez la déclarer au nom de "
                "n'importe quel autre seigneur, excepté un seigneur provenant "
                "du royaume que vous attaquez. Ton identité est révélée "
                "15 min avant la partie."
            ),
            "sabotage": (
                "Permet de retirer un choix de civilisation à votre adversaire "
                "lors d'une confrontation. Vous ne pouvez saboter que deux "
                "civilisations maximum par rencontre."
            ),
            "jeu_d_armes": (
                "Achète UN jeton Jeu d'armes. Utilise-le depuis la Chambre "
                "des comptes : +1 niveau d'IA permanent (jusqu'à la fin de "
                "saison) sur ton bot de défense — plafond 5, atteint : les "
                "Patrouilles deviennent Renforcées (3h). Le seigneur qui "
                "l'utilise réduit de 1h le délai de déclaration de sa "
                "prochaine attaque normale (pas d'embuscade) ; non "
                "cumulable — un seul Jeu d'armes actif par seigneur."
            ),
            "explorateur": (
                "Achète UN jeton Explorateur. Utilise-le depuis la Chambre "
                "des comptes : le seigneur choisi est verrouillé 48h (🔒 ni "
                "attaque ni défense) puis le royaume reçoit une map inédite. "
                "1 par saison."
            ),
            "corruption": (
                "Achète UN jeton Corruption. Utilise-le depuis la Chambre des "
                "comptes : transfert d'un territoire adverse vers ton royaume, "
                "sans combat. Bloquée si la map est sous Garde Royale. "
                "2 par saison."
            ),
            "garde_royale": (
                "Achète UNE Garde Royale en réserve (plusieurs gardes "
                "possibles, sans limite). Le Roi la pose ensuite depuis "
                "le salon Remparts : 12h d'immunité sur UNE map au choix."
            ),
            "patrouille": (
                "Débloque UN emplacement de patrouille (slot 1 puis slot 2). "
                "Le Roi pose le créneau quotidien de 2h depuis le salon "
                "Remparts — figé pour le cycle, redéfini le Jour du "
                "Seigneur (3h si Renforcée)."
            ),
            "mariage_arrange": (
                "Jeton 💰 à consommer à la Paroisse : mariage arrangé d'un "
                "seigneur de ton choix avec une civilisation non mariée "
                "(verrou 6h)."
            ),
        },
        "market_ledger_emoji": {  # type: ignore[dict-item]
            "embuscade": "🥷",
            "traquenard": "🪤",
            "contre_espionnage": "👀",
            "sabotage": "🗡️",
            "jeu_d_armes": "⚔️",
            "explorateur": "🧭",
            "corruption": "💰",
            "garde_royale": "💂",
            "patrouille": "👣",
            "mariage_arrange": "💐",
        },
        "market_fiche_effect": "**__EFFET :__**\n> {0}",
        "market_fiche_cost": "**__COÛT :__** {0} ⚙️",
        "market_fiche_wallet": "**__TRÉSORERIE ACTUELLE :__** {0} ⚙️",
        "market_fiche_left": "**__RESTE CETTE SAISON :__** {0}/{1}",
        "market_fiche_king_only": "*👑 Réservé au Roi — débité immédiatement du trésor.*",
        "market_buy_button": "✅ Acheter",
        "market_cancel_button": "❌ Annuler",
        "market_cancelled": "Achat annulé — la carte retourne sous l'étal du marchand.",
        "market_not_king": "Seuls les Rois peuvent acheter au marché.",
        "market_bought": "✅ Acheté : **{0}** — il reste {1} ⚙️ au trésor.",
        "market_bought_left": "\nReste cette saison : {0}/{1}.",
        # achat-recu-v1 (Affaire 25) : le reçu cumulatif et les échos
        # d'article — portés verbatim de la référence (30/10).
        "market_receipt_title": "🧾 Reçu — achats de la session",
        "market_receipt_ledger_help_named": (
            "🏛️ Retrouve l'ensemble de tes achats dans la Chambre des comptes "
            "— panneau **Le-Royaume** : {mention}"
        ),
        "market_receipt_ledger_help": (
            "🏛️ Retrouve l'ensemble de tes achats dans la Chambre des comptes "
            "— panneau **Le-Royaume** de ton royaume."
        ),
        "market_arranged_token_ok": (
            "💐 Mariage arrangé acheté — stock : {}. Consommez-le à la Paroisse."
        ),
        "market_garde_token_ok": (
            "🛡️ Garde Royale achetée — en réserve : {}. Pose-la depuis le salon 🧱 Remparts."
        ),
        "market_patrouille_slot_ok": (
            "🛡️ Emplacement de patrouille {} débloqué — pose le créneau depuis le salon 🧱 Remparts."
        ),
        "market_corruption_token_ok": (
            "💰 Jeton Corruption acheté — en réserve : {}. Utilise-le depuis "
            "la 🏛️ Chambre des comptes."
        ),
        "market_jeu_d_armes_token_ok": (
            "⚔️ Jeu d'armes acheté — en réserve : {}. Utilise-le depuis la "
            "🏛️ Chambre des comptes (+1 niveau d'IA)."
        ),
        "market_explorateur_token_ok": (
            "🛡️ Explorateur acheté — en réserve : {}. Utilise-le depuis la "
            "🏛️ Chambre des comptes."
        ),
        "market_ledger_summary": "Bilan de saison — dépensé : {0} ⚙️ · trésor : {1} ⚙️",
        "market_ledger_limits": "Limites — {0}",
        "market_ledger_empty": "Aucun achat pour le moment.",
        "market_ledger_purchases_title": "Achats",
        "market_ledger_line": "{0} {1} — {2} · {3} ⚙️ · {4}",
        "market_ledger_cards_title": "Cartes en main",
        "market_ledger_cards_empty": "Aucune carte en main pour le moment.",
        "market_ledger_card_line": "{0} **{1}** — x{2}",
        "market_no_points": "❌ Le royaume manque de points de technologie.",
        "market_limit": "❌ La limite d'achat par saison est atteinte.",
        "market_error": "❌ L'achat a échoué : {0}",
        "chamber_title": "🏛️ Chambre des comptes — {0}",
        "chamber_stock_explorateur": "🧭 Jetons Explorateur : **{0}**",
        "chamber_stock_corruption": "🎭 Jetons Corruption : **{0}**",
        "chamber_stock_jeu_d_armes": "⚔️ Jetons Jeu d'armes : **{0}**",
        "chamber_stock_garde": "🛡️ Gardes Royales : **{0}**",
        "chamber_stock_mariage": "💐 Jetons mariage arrangé : **{0}**",
        "chamber_patrouille": "🚨 Patrouille : {0}",
        "chamber_use_explorateur": "🧭 Envoyer explorer",
        "chamber_use_corruption": "🎭 Corrompre",
        "chamber_use_jeu_d_armes": "⚔️ Utiliser",
        "chamber_use_garde": "🛡️ Placer la garde",
        "chamber_use_patrouille": "🚨 Placer la patrouille",
        "chamber_select_lord": "Choisissez le seigneur qui part explorer :",
        "chamber_select_territory": "Choisissez le territoire à corrompre :",
        "chamber_select_own_territory": "Choisissez le territoire à protéger :",
        "chamber_select_hour": "Choisissez la tranche horaire (2h, tous les jours) :",
        "chamber_done": "✅ C'est fait — le registre du royaume est à jour.",
        "chamber_no_stock": "❌ Aucune carte utilisable en réserve.",
        "expedition_launch_note": (
            "🧭 L'expédition des **{0}** lève l'ancre — l'équipage est en mer."
        ),
        "expedition_return_map": (
            "🧭 L'expédition des **{0}** est de retour — la carte **{1}** est révélée !"
        ),
        "expedition_return_civ": (
            "🧭 L'expédition des **{0}** est de retour — la civilisation **{1}** rejoint le royaume !"
        ),
        "expedition_return_tech": (
            "🧭 L'expédition des **{0}** est de retour — compensation : +2 ⚙️."
        ),
        "sacree_verdict_note": (
            "⛪ Le chantier du Lieu Sacrée de **{0}** sur **{1}** a TENU —"
            " le territoire est SACRÉ à vie, immunisé contre tout."
        ),
        "marry_button": "💍 Se marier",
        "alliances_button": "🤝 Alliances",
        "church_marry_intro": "👰 Choisissez la Princesse de ton mariage :",
        "church_marry_view_title": "💍 Se marier — {0}",
        "church_marry_badge": "MARIAGE ROYAL",
        "church_marry_rules": (
            "**Un seul mariage actif** — la civilisation choisie devient"
            " **exclusive** à ton royaume.\n"
            "💍 **{0} bague(s)** seront consommées à la célébration.\n"
            "👑 Ton lien est **garanti jusqu'à la fin de la saison**, même"
            " en cas de défaite.\n"
            "🔒 Verrou de combat : **{1}h** — fin à titre indicatif du"
            " verrouillage au moment du clic : {2}.\n"
            "🛡️ État verrouillage : si tu es verrouillé, tu ne peux"
            " **ni attaquer, ni défendre, ni utiliser de carte"
            " technologique**."
        ),
        "church_marry_rules_royal": (
            "👑 Ton lien est **garanti jusqu'à la fin de la saison**, même"
            " en cas de défaite."
        ),
        "church_marry_princess": "Princesse {0}",
        "church_marry_lock": "fin du verrou <t:{0}:R>",
        "church_marry_confirm_title": "💍 Confirmer ton mariage",
        "church_marry_confirm_sub": "princesse pressentie · {0} bague(s) · verrou {1}h",
        "church_marry_yes_button": "💍 Oui, je le veux",
        "church_marry_edit_button": "✏️ Modifier",
        "church_marry_sealed_title": "💍 Mariage scellé : **{0}**",
        "church_marry_sealed_note": (
            "Le royaume en est informé — l'annonce vient d'être publiée"
            " dans **Géopolitique**."
        ),
        "church_wedding_announce": (
            "💍 Mariage scellé — {0} des {1} épouse les **{2}** · 🔒 verrou"
            " {3}h · 🎁 Offrande +{4} ⚙️ · la civilisation est désormais"
            " **exclusive** au royaume {1} jusqu'à brisure du lien."
        ),
        "church_marry_already": (
            "💍 Tu as déjà un mariage actif — un seul à la fois (D34)."
        ),
        "church_marry_no_options": (
            "💔 Aucune Princesse disponible — ta main est vide ou déjà épousée."
        ),
        "church_marry_no_points": "❌ Ton royaume n'a plus de point de mariage (D59).",
        "church_marry_no_points_royal": "❌ Un mariage royal (Reine) coûte 2 points de mariage.",
        "church_marry_not_in_hand": (
            "❌ Cette civilisation n'est pas dans la main de ton royaume (Alliances)."
        ),
        "marry_error": "❌ Le mariage a échoué : {0}",
        "alliances_title": "🤝 Alliances — {0}",
        "alliances_points": (
            "💍 Points de mariage : **{0}** · Jetons mariage arrangé : **{1}**"
        ),
        "alliances_hand": "🃏 Main actuelle ({0})",
        "alliances_next_intro": "🔮 Prochain cycle (projection)",
        "alliances_next_kept": "✅ Conservées : {0}",
        "alliances_next_arriving": "➕ Arrivantes : {0}",
        "alliances_next_dropping": "➖ Perdues : {0}",
        "alliances_next_elsewhere": "🔒 Épousées ailleurs : {0}",
        "alliances_near_title": "🎯 Presque déverrouillées",
        "alliances_near_line": "• **{0}** — {1}",
        "alliances_none": "—",
        "alliances_no_data": "❌ Aucune donnée d'alliance pour l'instant.",
        "event_cycle": (
            "🔄 **Cycle {cycle}** — budgets hebdomadaires rechargés, "
            "{maps} nouvelles cartes pour Gaïa."
        ),
        "event_age": (
            "🏺 **{age}** — chaque royaume gagne {tech} point(s) tech "
            "et {marriages} emplacement(s) de mariage."
        ),
        "event_end": (
            "🏁 **Fin de saison** — les attaques en cours sont annulées "
            "et le verdict est tombé : {winner}."
        ),
        "event_end_showmatch": (
            "🏁 **Fin de saison** — les attaques en cours sont annulées, "
            "les royaumes de tête sont à égalité : le ShowMatch tranche !"
        ),
        "tavern_button": "🍺 Taverne",
        "mercenary_button": "🗡️ Mercenaires",
        "tavern_title": "🍺 La Taverne",
        "tavern_purse": "🪙 Ta bourse : **{0}** écu(s)",
        "tavern_cooldown": "⏳ Prochain service possible <t:{0}:R> (cooldown global de 24h).",
        "tavern_locked": "🔒 Verrou de combat en cours — fin <t:{0}:R>.",
        "tavern_select": "Choisissez une boisson :",
        "tavern_drink_line": "{0} — {1} 🪙",
        "tavern_lock_line": "Verrou {0} min",
        "tavern_confirm_title": "🍺 Confirmer la commande",
        "tavern_confirm_sub": "Prix : **{0}** 🪙 — verrou de combat : **{1}** minutes.",
        "tavern_yes": "Boire",
        "tavern_drunk": "🍺 Tu as bu **{0}** — il te reste **{1}** écu(s).",
        "tavern_cooldown_note": "⏳ Le cooldown global de 24h n'est pas encore écoulé.",
        "tavern_no_purse": "❌ Ta bourse ne suffit pas.",
        "tavern_no_season": "❌ Aucune saison en cours.",
        "tavern_season_closed": "❌ La saison est terminée — le comptoir est fermé.",
        "tavern_error": "❌ La Taverne refuse : {0}",
        "mercenary_title": "🗡️ Le Chef Mercenaire",
        "mercenary_lot_line": "• **{0}** ({1} usage(s)) — plus haute offre : **{2}** 🪙",
        "mercenary_own_bid": "_Tu as misé {0} 🪙._",
        "mercenary_winners": "🏆 Lots remportés : {0}",
        "mercenary_no_winner": "🍂 Aucun lot n'a trouvé preneur.",
        "mercenary_select_lot": "Choisissez un lot pour enchérir :",
        "mercenary_select_amount": "Montant de ton offre (écus) :",
        "mercenary_bid_placed": "🗡️ Offre de **{1}** 🪙 placée sur **{0}** — les écus sont séquestrés.",
        "mercenary_withdraw": "Retirer mon offre",
        "mercenary_withdraw_done": "✅ Ton offre est retirée — les écus séquestrés sont remboursés.",
        "mercenary_withdraw_none": "ℹ️ Tu n'as aucune offre en cours.",
        "mercenary_none": (
            "🍂 Le Chef Mercenaire n'est pas là — il se tient à la Taverne"
            " entre 20h et 21h (heure de Paris)."
        ),
        "mercenary_bid_too_low": "❌ L'offre doit STRICTEMENT dépasser la plus haute en cours.",
        "mercenary_not_open_yet": "⏳ Les enchères ne sont pas encore ouvertes.",
        "mercenary_closed_note": "❌ Le marché est fermé.",
        "mercenary_already_held": "❌ Un seul peuple mercenaire à la fois — tu en tiens déjà un.",
        "mercenary_open_note": (
            "🗡️ **Le Chef Mercenaire est là** — la bourse aux mercenaires est ouverte,"
            " les enchères ferment à l'heure affichée sur place. À la Taverne !"
        ),
        "mercenary_close_note": "🗡️ La bourse aux mercenaires est close — **{0}** lot(s) attribué(s).",
        # Affaire 39 (branchement, Drasah 26/11) : le panneau épinglé de
        # la 🍺 Taverne (menu(effect) + renseignement) et le sommaire du
        # 📜 Scriptorium avec ses rubriques éphémères.
        "tavern_pin_title": "🍺 La Taverne",
        "tavern_pin_intro": (
            "La salle commune des seigneurs — la bourse est personnelle, en"
            " **écus**, et ne se dépense qu'ici."
        ),
        "tavern_pin_rules": (
            "• Une boisson **verrouille le combat** comme une bataille en cours"
            " : ni déclarer, ni planifier, ni défendre, ni embuscade pendant le"
            " verrou.\n• **24h** minimum entre deux boissons, quelle qu'elles"
            " soient.\n• Chaque seigneur paie avec **sa propre bourse**."
        ),
        "tavern_menu_button": "🍺 Demander à boire",
        "tavern_info_button": "🗣️ Demander un renseignement",
        "tavern_purse_button": "💰 Regarder sa bourse",
        "tavern_info_rp": (
            "Le tenancier essuie un gobelet sans lever les yeux, puis approche"
            " sa voix :\n« Ici, rien n'est gratuit, seigneur. Les"
            " renseignements coûtent cher… mais tu remarqueras que les langues"
            " ont tendance à se délier lorsqu'on boit. »"
        ),
        "tavern_info_header": "**Ce que chaque boisson fait réellement :**",
        "tavern_info_line": "• {0} — {1} · verrou {2} min",
        "tavern_effect_verre": "ouvre une fenêtre d'écoute des rumeurs les plus proches",
        "tavern_effect_vin": "révèle l'horaire des FFA",
        "tavern_effect_alcool": "force la prochaine map",
        "tavern_effect_generic": "les langues se délient",
        "tavern_purse_line": "💰 Ta bourse contient **{0}** écu(s).",
        "scriptorium_title": "📜 Scriptorium",
        "scriptorium_intro": "L'archive du royaume — consultez les rubriques ci-dessous.",
        "scriptorium_topic_cadastre": "🗺️ Cadastre",
        "scriptorium_topic_diplomatie": "🤝 Diplomatie",
        "scriptorium_topic_seigneurie": "🛡️ Seigneurie",
        "scriptorium_cadastre_title": "🗺️ Cadastre — territoires et leurs effets",
        "scriptorium_cadastre_intro": (
            "🗺️ **À quoi ça sert** : l'inventaire vivant des territoires du"
            " royaume. Choisis ta première terre à l'installation, repère le"
            " bonus de chaque terre (espionnage, contre-espionnage, "
            "ressources…) et prépare tes attaques en connaissance de cause."
        ),
        "scriptorium_cadastre_empty": "Le catalogue de maps est vide.",
        "scriptorium_diplomatie_title": "🤝 Diplomatie — civilisations et leurs conditions",
        "scriptorium_diplomatie_intro": (
            "🤝 **À quoi ça sert** : le registre des alliances. Chaque "
            "civilisation impose ses conditions (offrandes, territoire…). "
            "Consulte-les avant de proposer un pacte : ton choix conditionne "
            "tes bonus et tes ennemis."
        ),
        "scriptorium_diplomatie_empty": "Aucune civilisation déclarée pour le moment.",
        "scriptorium_condition_map": "posséder la map {maps}",
        "scriptorium_condition_map_count": "posséder au moins {count} de : {maps}",
        "scriptorium_condition_map_type": "posséder au moins {count} map(s) de type {types}",
        "scriptorium_condition_min_maps": "posséder au moins {count} map(s)",
        "scriptorium_condition_max_maps": "posséder au plus {count} map(s)",
        "scriptorium_condition_civ": "posséder la civilisation {civ}",
        "scriptorium_condition_pattern": "appartenir au royaume {pattern}",
        "scriptorium_condition_tech": "posséder au moins {count} point(s) technologique(s)",
        "scriptorium_condition_marriages": "avoir au moins {count} seigneur(s) marié(s)",
        "scriptorium_condition_civ_count": "posséder au moins {count} civilisation(s)",
        "scriptorium_seigneurie_title": "🛡️ Seigneurie — seigneurs et budgets restants",
        "scriptorium_seigneurie_intro": (
            "🛡️ **À quoi ça sert** : l'état des lieux des seigneurs — "
            "royaumes, rôles et fiches. Ouvre une fiche pour consulter le "
            "statut, le palier Paroisse et la chronique des faits d'armes."
        ),
        "scriptorium_seigneurie_empty": (
            "Aucun royaume pour le moment — les inscriptions sont ouvertes dans Postuler."
        ),
        "scriptorium_seigneurie_king": "Roi",
        "scriptorium_seigneurie_lords": "Seigneurs",
        "scriptorium_seigneurie_pending": "En attente d'un royaume",
        "scriptorium_fiche_choose": "🛡️ Quelle fiche de seigneur consulter ?",
        "scriptorium_fiche_title": "## 🛡️ Fiche — {name}",
        "scriptorium_fiche_identity": "👤 {name} · Insight : {insight} · {kingdom} ({role})",
        "scriptorium_fiche_status": "📊 Statut",
        "scriptorium_fiche_married": "💍 Civilisation mariée : {civ}",
        "scriptorium_fiche_secured": "🔒 Civilisations sécurisées : {civs}",
        "scriptorium_fiche_territories": "🗺️ Territoires détenus par le royaume : {count}",
        "scriptorium_fiche_parish": "⛪ Palier Paroisse : {tier}",
        "scriptorium_fiche_chronicle": "📜 Chronique des faits d'armes (3 dernières)",
        "scriptorium_fiche_chronicle_more": "… et {count} de plus dans l'historique complet.",
        "scriptorium_fiche_history": "📜 Chronique complète de {name}",
        "scriptorium_fiche_history_button": "📜 Historique complet",
        "scriptorium_fiche_tracked": (
            "👁️ Suivi par votre Corbeau — statut et chronique visibles pendant 24h."
        ),
        "scriptorium_fiche_gated": (
            "🔒 Seule l'identité est visible — un Corbeau `corbeau_track` (24h)"
            " ouvre le statut et la chronique."
        ),
        "scriptorium_unknown": "inconnu",
        "ffa_join_button": "🗺️ Partir en expédition",
        "ffa_join_note": (
            "✅ **{0}** tient un créneau de l'Expédition — {1}/{2} participant(s)."
        ),
        "ffa_left_note": "🚪 **{0}** a libéré son créneau — {1}/{2} participant(s).",
        "ffa_not_open": "❌ Aucune expédition n'est ouverte aux inscriptions pour le moment.",
        "ffa_full": "❌ L'expédition est complète.",
        "ffa_kingdom_full": (
            "❌ Ton royaume tient déjà un créneau (mode : 1 seigneur par royaume)."
        ),
        "ffa_locked": (
            "❌ Tu es verrouillé (verrou Explorateur 48h en cours ou FFA manqué)"
            " — inscription impossible."
        ),
        "ffa_announce": (
            "🧭 **Expédition — samedi <t:{0}:F>**\n"
            "Une partie GRATUITE de {1} minutes contre l'IA Gaïa et les autres"
            " participants — {2} places, mode : {3}. Clique sur"
            " **« Partir en expédition »** pour réserver ton créneau (1er arrivé,"
            " 1er servi ; re-clique pour le libérer)."
        ),
        "ffa_start": (
            "🧭 **L'expédition commence maintenant** — {0} participant(s),"
            " {1} minutes. Bonne chance !"
        ),
        "ffa_salon_title": "🗺️ Expédition",
        "ffa_mode_one": "1 seigneur par royaume",
        "ffa_mode_free": "places libres",
        "console_relaunch_label": "🔁 Relancer la saison",
        "console_reset_label": "🧹 Réinitialiser les données",
        "console_clock_label": "⏩ Horloge de jeu",
        "console_debug_status_label": "🐞 Statut debug",
        "console_bypass_on_label": "🐞 Bypass ON",
        "console_bypass_off_label": "🐞 Bypass OFF",
        "console_skip_event_label": "⏭️ Événement suivant",
        "console_service_not_ready": "❌ Le service Kingdom n'est pas prêt.",
        "console_debug_done": "✅ {0}",
        "console_relaunch_confirm": (
            "🔁 **Relancer la saison ?**\n"
            "Les données actuelles sont archivées puis effacées, et une nouvelle"
            " saison démarre (nouvelles candidatures)."
        ),
        "console_reset_confirm": (
            "🧹 **Réinitialiser les données ?**\n"
            "Les données actuelles sont archivées puis effacées — aucune"
            " nouvelle saison n'est lancée."
        ),
        "console_confirm_button": "⚠️ Confirmer",
        "console_cancel_button": "Annuler",
        "console_cancelled": "❌ Annulé — rien n'a été touché.",
        "console_relaunch_done": "✅ Saison relancée — les anciennes données sont archivées.",
        "console_reset_done": "✅ Données réinitialisées — les anciennes données sont archivées.",
        "console_error": "❌ {0}",
        "console_clock_modal_title": "⏩ Avancer l'horloge",
        "console_clock_duration_label": "Durée (90m, 2h, 3d…)",
        "console_clock_bad": "❌ {0}",
        "console_clock_done": "✅ Horloge de jeu avancée : **{0}**.",
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
        "defend_cancelled": (
            "🏳️ This attack was withdrawn by its declarant — it no longer awaits a defense."
        ),
        "cancel_attack_defender_dm": (
            "🗡️ The attack you were defending on **{map}** was withdrawn by its declarant"
            " — your defense budget is refunded in full."
        ),
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
        "reveal_cover": (
            "🕶️ Reveal — the attack on **{map}** was led by **{attacker}** of"
            " kingdom **{attacker_kingdom}**, under the cover of **{cover}** of"
            " kingdom **{cover_kingdom}**. The cover drops."
        ),
        "reveal_ai": (
            "🤖 Nobody defended **{map}** — kingdom **{kingdom}**'s AI takes the defense"
            " (level **{level}**/5)!"
        ),
        "reveal_defense": "🛡️ **{map}**'s defense is locked — meeting **{time}** (Paris).",
        "matchup_note": (
            "⚔️ **{attacker}** 🆚 **{defender}** — both drafts resolved: meeting at the planned hour."
        ),
        "matchup_v1": (
            "🆚 **{attacker}** VS **{defender}** — both drafts are locked,"
            " the match can begin!"
        ),
        "matchup_ai": (
