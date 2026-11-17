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
        "pickban_pick": "Choix {n}",
        "pickban_validate": "✅ Valider",
        "pickban_missing": "❌ Classe d'abord tes {count} civilisations.",
        "pickban_duplicate": (
            "❌ Vous ne pouvez pas avoir de doublons dans vos choix de civilisations."
        ),
        "pickban_waiting": "⏳ Picks enregistrés et validés — en attente de l'adversaire.",
        "pickban_modify_button": "✏️ Modifier",
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
        "room_event_description": (
            "⚔️ Bataille Kingdoms en direct — {attacker} 🆚 {defender}.\n"
            "Civilisations et boutons de jeu : dans le salon vocal de la bataille."
        ),
        "draft_button": "📜 Voir la draft",
        "draft_sheet": "📜 Draft — {map}",
        "draft_mode_player": "Choix du joueur",
        "draft_mode_random": "Choix aléatoire",
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
        "market_button": "🛒 Marché",
        "chamber_button": "🏛️ Comptes",
        "market_title": "🛒 Marché",
        "market_rules": (
            "**Paiement d'abord** — tout achat débite la banque du royaume.\n"
            "Une carte achetée vit dans la Chambre des comptes."
        ),
        "market_wallet": "💰 Banque du royaume : **{0}** ⚙️",
        "market_intro": "Choisissez une carte à acheter :",
        "market_item_technology": "🔬 {0}",
        "market_item_mariage_arrange": "💍 Jeton mariage arrangé",
        "market_item_explorateur": "🧭 Jeton Explorateur",
        "market_item_corruption": "🎭 Jeton Corruption",
        "market_item_jeu_d_armes": "⚔️ Jeton Jeu d'armes",
        "market_item_garde_royale": "🛡️ Garde Royale",
        "market_item_patrouille": "🚨 Slot Patrouille",
        "market_confirm_title": "🛒 Confirmer l'achat",
        "market_confirm_sub": "Coût : **{0}** ⚙️",
        "market_yes": "✅ Acheter",
        "market_bought": "✅ Achat effectué : {0}",
        "market_no_points": "❌ Le royaume manque de points de technologie.",
        "market_limit": "❌ La limite d'achat par saison est atteinte.",
        "market_error": "❌ L'achat a échoué : {0}",
        "chamber_title": "🏛️ Chambre des comptes — {0}",
        "chamber_stock_explorateur": "🧭 Jetons Explorateur : **{0}**",
        "chamber_stock_corruption": "🎭 Jetons Corruption : **{0}**",
        "chamber_stock_jeu_d_armes": "⚔️ Jetons Jeu d'armes : **{0}**",
        "chamber_stock_garde": "🛡️ Gardes Royales : **{0}**",
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
            "🆚 **{attacker}** VS **AI {kingdom}** — AI level: **{level}**/5.\n"
            "🎮 Reminder: the attacker creates the game in **multiplayer** (never local)"
            " with **spectators allowed**."
        ),
        "reveal_battle_anon": "⚔️ Battle ahead",
        "forfeit_both": (
            "🏳️ General forfeit on **{map}** — nobody validated: the attacker, present, wins (**{kingdom}**)."
        ),
        "forfeit_side": "🏳️ Forfeit on **{map}** — **{side}** missed the validation: victory of **{kingdom}**.",
        "side_attacker": "the attacker",
        "side_defender": "the defender",
        "noshow_side": "🏳️ **{map}** — **{side}** missed the meeting: victory of **{kingdom}**.",
        "noshow_both": "🏳️ **{map}** — double forfeit: no player at the meeting, the territory stays with its owner.",
        "pickban_dm": (
            "⚔️ **Pick & ban — {map}**\nRank your **{count}** civilization picks by order of"
            " preference (your ranking orders the fallbacks).\n"
            "🕒 **Window closes: {deadline}** (meeting hour).\n"
            "If you own a Sabotage or a Faucon, you will use it in the battle room.\n"
            "\n"
            "⚠️ **Anti-blocking rule**: no choice validated before the meeting → "
            "3 **random** civilizations from your hand — and no sabotage or faucon "
            "applies. The meeting happens anyway.\n"
            "Your hand: {hand}\nAdversary hand: {theirs}"
        ),
        "pickban_pick": "Choice {n}",
        "pickban_validate": "✅ Validate",
        "pickban_missing": "❌ Rank your {count} civilizations first.",
        "pickban_duplicate": "❌ You cannot have duplicates in your civilization choices.",
        "pickban_waiting": "⏳ Picks recorded and validated — waiting for the adversary.",
        "pickban_modify_button": "✏️ Modify",
        "pickban_reveal_adversary": "**Your adversary's draft:**",
        "pickban_own_picks_line": "**Your picks:** {picks}",
        "pickban_reveal_dm": (
            "🎭 **Reveal — {map}**\n🕒 **Meeting: {deadline}** — the sabotage"
            " window closes at that time.\n🗡️ Do you want to sabotage or use"
            " a Faucon? — up to 2 enemy civilizations removed per side.\n⚔️"
            " Otherwise confirm with Pass — a player missing from the voice"
            " room at the meeting time is a forfeit!"
        ),
        "pickban_default_reveal_dm": (
            "🎭 **Reveal — {map}**\n⏱️ The draft closed on time: the"
            " never-ranked civilizations were drawn at random (no sabotage,"
            " no Faucon).\n🕒 The meeting is NOW — join the voice salon."
        ),
        "attack_cancelled_dm": "❌ The attack on **{map}** was cancelled — the draft is closed.",
        "sab_open_button": "🗡️ Sabotage / Use a Faucon",
        "sab_pass_button": "⚔️ Pass — I am ready",
        "sab_no_resources": (
            "🕊️ **You have no sabotage nor a Faucon** — waiting for your adversary. You can confirm with ⚔️ Pass."
        ),
        "sab_faucon": "🦅 Faucon",
        "sab_techno": "🧪 Sabotage",
        "sab_choose": "🎯 **Pick the enemy civilization to remove:**",
        "sab_pick_line": "🎯 {action}: **{civ}**",
        "sab_modify_button": "✏️ Modify",
        "sab_validate_button": "✅ Validate",
        "sab_cancel_button": "❌ Cancel",
        "sab_done": "🪶 **{civ}** removed from the enemy side.",
        "sab_settled": "✅ Your side confirmed — waiting for the other side…",
        "sab_phase_done": (
            "🎭 **Sabotage phase over — {map}**\nJoin the voice room at the"
            " meeting time: the final civilizations are shown there."
        ),
        "sab_over": "🕊️ The sabotage phase is over.",
        "sab_empty": "🕊️ No enemy civilization available.",
        "sab_not_player": "❌ Only the two players of the match may act here.",
        "sab_stock_line": (
            "🗡️ Sabotage: {sabotage} · 🦅 Faucon: {faucon}\nOne side can suffer at most 2 sabotaged civilizations."
        ),
        "sab_faucon_ready": "ready",
        "sab_faucon_flying": "flying until {time}",
        "sab_faucon_absent": "absent",
        "sab_panel_title": "🪶 **Sabotage** — {used}/2 civilizations removed in this attack",
        "sab_panel_used": "Removed: {list}",
        "sab_panel_none": "No civilization removed yet.",
        "sab_panel_done": "🪶 **{civ}** removed from the enemy side — {used}/2.",
        "sab_again_ask": "🗡️ Do you want to sabotage another civilization?",
        "sab_again_yes": "Yes — another sabotage",
        "sab_again_no": "No — I'm done",
        # -- battle room / meeting (P4.1b tranche 2b) --
        "room_not_player": "❌ Only the two players of the match may act here.",
        "defender_ai": "AI 🤖",
        "room_role": "Battle {map}",
        "room_scoreboard_map": "⚔️ {map}",
        "room_scoreboard_id": "🆔 Game ID: {id}",
        "room_side_attacker": "Attacker",
        "room_side_defender": "Defender",
        "room_side_ready": "✅ Ready",
        "room_side_wait": "⏳ waiting for Ready",
        "room_side_none": "🔗 waiting for the game ID",
        "room_side_ai": "🤖 AI — lvl {level}/5",
        "room_ai_disclaimer": (
            "⚠️ **AI of level {level}/5** — the game is played in multiplayer"
            " with a game ID (never locally) to stay traceable and verifiable"
            " post-game. The player is believed on their word; any presumed"
            " fraud may be contested ⚖️ then arbitrated by the admins."
        ),
        "room_id_button": "🔗 Enter the game ID",
        "room_id_modify_button": "🔴 Change the game ID",
        "room_id_pending_button": "⏳ Game ID being entered…",
        "room_id_locked_other": (
            "⏳ The other player is entering the game ID right now — try again in a moment."
        ),
        "room_ready_button": "✅ Ready",
        "room_ready_attacker_button": "⚔️ Ready — {player}",
        "room_ready_defender_button": "Ready 🛡️ — {player}",
        "room_ready_done_attacker_button": "⚔️ I'm ready! — {player}",
        "room_ready_done_defender_button": "I'm ready! 🛡️ — {player}",
        "room_not_your_side": "⛔ This Ready button belongs to your adversary.",
        "room_ready_needs_url": (
            "🔗 Enter the game ID first (🔗 button) — the ✅ Ready button appears afterwards."
        ),
        "room_scoreboard_footer": (
            "🎮 Both players are ready — good luck! Declare the winner with 🏆."
        ),
        "room_ping_message": "⚔️ {attacker} {defender} — the battle room is open, to arms!",
        "room_ping_attacker_only": "⚔️ {attacker} — the battle room is open, to arms!",
        "room_ping_winner": "🏆 Winner: **{winner}**",
        "room_dm": (
            "🏟️ **Stand ready — {map}**\n"
            "Join your adversary in voice: {room}\n"
            "Join the text salon to go on: {salon}"
        ),
        "room_dm_deadline": (
            "\n\n⏳ Presence required (voice or ✅ Ready) before {deadline} —"
            " past it, an absent player is declared forfeit."
        ),
        "room_dm_luck": "\n\nGood luck! 🍀",
        "room_event_name": "⚔️ {map} — {attacker} 🆚 {defender}",
        "room_event_description": (
            "⚔️ Live Kingdoms battle — {attacker} 🆚 {defender}.\n"
            "Civilizations and game buttons: in the battle's voice channel."
        ),
        "draft_button": "📜 View the draft",
        "draft_sheet": "📜 Draft — {map}",
        "draft_mode_player": "Player's choice",
        "draft_mode_random": "Random pick",
        "draft_sheet_help": (
            "The players' pick order during the draft — the real order"
            " once the sabotage phase is over (random, ranking secret"
            " during the phase), sabotaged picks struck through:"
        ),
        "result_button": "🏆 Declare the winner",
        "result_select_title": "🏆 **Who wins the game?**",
        "result_select_placeholder": "The game's winner",
        "result_confirm_title": "🏆 **Winner: {winner}** — confirm this result?",
        "result_confirm_button": "✅ Confirm",
        "result_edit_button": "✏️ Change",
        "result_review_title": "⏳ **{player} declared {winner} the winner.**",
        "result_review_confirm_button": "✅ Confirm the result",
        "result_review_contest_button": "⚖️ Contest",
        "result_mine_title": "⏳ **Your choice: {winner}** — you may change it below.",
        "result_not_ready": "⏳ The Declare-the-winner button appears once both players are Ready.",
        "score_url_modal_title": "Game URL",
        "score_url_modal_label": "Game lobby URL",
        "score_url_modal_placeholder": "ex. 123456",
        "score_pending": (
            "⏳ Result recorded (game {game}) — it applies unless the other"
            " player contests it within the next {minutes} minutes."
        ),
        "score_resolved": "🏆 Result recorded — **{winner}** wins **{map}** (game {game}).",
        "score_already": "✅ This result was already recorded — nothing to do.",
        "score_disputed": (
            "⚖️ Contradictory declarations — the admins arbitrate (game {game})."
            "\nPlease get in touch with an admin."
        ),
        "score_reminder_dm": (
            "⏰ **Meeting — {map}**: no result declared for 3 hours — declare the"
            " game result with the 🏆 button of the battle room!"
        ),
        "auto_dispute": (
            "⚖️ **Dispute auto-opened on {map}** — no result declared 15h after the"
            " game opened: an admin arbitrates through the console (`resultat`)."
        ),
        "conquest_title": "⚔️ Kingdom **{winner}** conquered **{map}**!",
        "conquest_defense_title": "🛡️ Kingdom **{winner}** defended **{map}**!",
        "conquest_thread": "Conquest details",
        "conquest_thread_defense": "Defense details",
        "conquest_attacker_line": "⚔️ Attacker: **{player}** ({kingdom})",
        "conquest_defense_line": "🛡️ Defense: **{player}** ({kingdom})",
        "conquest_ai_defense": "🛡️ Defense: the kingdom **{kingdom}**'s AI (level {level})",
        "conquest_civ_line": "🎯 {player} played **{civ}**",
        "conquest_embuscade_line": "🥷 Ambush used",
        "conquest_sabotages_line": "🧨 Sabotages ({side}, Falcon/Tech): {civs}",
        "conquest_id_line": "🔗 Game ID: **{game}**",
        "conquest_none": "none",
        "conquest_side_attacker": "attacker",
        "conquest_side_defender": "defender",
        "conquest_married_lost": "💔 **{player}** loses their sacred bond with civilization **{civ}**.",
        "dispute_admin_dm": "⚖️ **Dispute — {map}**\n{declarations}\nCut the result (game {game}).",
        "dispute_dm_open": (
            "⚖️ It seems you did not choose the same winner of the game, "
            "your choice was **{winner}**.\n"
            "We suggest you modify or confirm your choice.\n"
            "-# In case of a dispute, an admin will take over."
        ),
        "dispute_dm_confirmed": (
            "✅ Your choice (**{winner}**) is recorded — waiting for your "
            "adversary.\n-# In case of a dispute, an admin will take over."
        ),
        "dispute_dm_handover": "⚖️ The dispute stands — an admin takes over and will reach you here.",
        "dispute_dm_resolved": "✅ Dispute closed — you both named the same winner: **{winner}**.",
        "dispute_confirm_button": "✅ Confirm my choice",
        "dispute_win_attacker": "⚖️ Rule: attacker",
        "dispute_win_defender": "⚖️ Rule: defender",
        "dispute_double": "🏳️ Double forfeit",
        "dispute_applied": "⚖️ Arbitration applied — **{kingdom}** wins **{map}**.",
        "dispute_forfeit": "⚖️ Arbitration applied — double forfeit on **{map}**.",
        "dispute_not_admin": "❌ Only bot-admins arbitrate a dispute.",
        # -- planning (P4.1b tranche 2d) --
        "plan_button": "📅 Plan an attack",
        "plan_disclaimer": (
            "⚠️ A planning reserves NOTHING: if another kingdom declares an attack on the"
            " territory before your chosen hour, your planning switches to your next choice"
            " — or breaks when none remains."
        ),
        "plan_wizard_title": "📅 Plan an attack",
        "plan_time_day_label": "Meeting day",
        "plan_time_day_today": "Today — {date}",
        "plan_time_day_tomorrow": "Tomorrow — {date}",
        "plan_time_hour_label": "Hour",
        "plan_time_minute_label": "Minute",
        "plan_time_hint": (
            "Pick the meeting day, hour and minute (Paris time), then validate."
            " Golden rule: 24h maximum ahead."
        ),
        "plan_time_validate_button": "✅ Validate the time",
        "plan_time_invalid": (
            "❌ That meeting is impossible: it must be in the future and within 24h."
            " Pick another slot."
        ),
        "plan_confirm_title": "📅 Planning — choice 1: **{map}** · meeting **{time}** (Paris)",
        "plan_choice2_placeholder": "Choice 2 (optional)",
        "plan_choice3_placeholder": "Choice 3 (optional)",
        "plan_confirm_button": "✅ Confirm the planning",
        "plan_dm_header": "📅 Attack planning — {map}",
        "plan_choices_line": "Choice {n}: **{map}**{active}",
        "plan_active_tag": " ✅",
        "plan_dm_time": "Meeting: **{time}** (Paris) — automatic declaration at **{declare_time}** (Paris).",
        "plan_dm_budget": "The attack budget (⚔️) is consumed at the DECLARATION — not now.",
        "plan_created_note": "📅 Planning saved — the recap is in your DMs.",
        "plan_no_dm": "⚠️ Planning saved, but the DM failed (DMs closed?).",
        "plan_failed": "❌ The planning failed: {message}",
        "plan_cancel_button": "❌ Cancel my planning",
        "plan_cancelled_ephemeral": "❌ Planning cancelled — no budget was consumed.",
        "plan_event_executed": (
            "✅ Your planned attack was DECLARED on **{map}** — meeting **{time}** (Paris)."
            " The attack budget was consumed at the declaration."
        ),
        "plan_event_switched": (
            "⚠️ Your choice on **{old}** cannot proceed (the battle was already declared there)"
            " — switched to the next choice: **{map}**."
        ),
        "plan_event_broken": (
            "⛔ Your planned attack cannot proceed: the battle was already declared on"
            " **{map}** and no other choice is available. No budget was consumed."
        ),
        "plan_event_cancelled": "❌ Your planning was cancelled — no budget was consumed.",
        "plan_no_service": "❌ The attack service is unavailable.",
        "market_button": "🛒 Market",
        "chamber_button": "🏛️ Treasury",
        "market_title": "🛒 Market",
        "market_rules": (
            "**Payment first** — every purchase debits the kingdom bank.\n"
            "A bought card lives in the Chambre des comptes."
        ),
        "market_wallet": "💰 Kingdom bank: **{0}** ⚙️",
        "market_intro": "Choose a card to buy:",
        "market_item_technology": "🔬 {0}",
        "market_item_mariage_arrange": "💍 Arranged-marriage token",
        "market_item_explorateur": "🧭 Explorer token",
        "market_item_corruption": "🎭 Corruption token",
        "market_item_jeu_d_armes": "⚔️ Arms-mastery token",
        "market_item_garde_royale": "🛡️ Royal Guard",
        "market_item_patrouille": "🚨 Patrol slot",
        "market_confirm_title": "🛒 Confirm the purchase",
        "market_confirm_sub": "Cost: **{0}** ⚙️",
        "market_yes": "✅ Buy",
        "market_bought": "✅ Purchase done: {0}",
        "market_no_points": "❌ The kingdom lacks tech points.",
        "market_limit": "❌ The per-season purchase limit is reached.",
        "market_error": "❌ The purchase failed: {0}",
        "chamber_title": "🏛️ Chambre des comptes — {0}",
        "chamber_stock_explorateur": "🧭 Explorer tokens: **{0}**",
        "chamber_stock_corruption": "🎭 Corruption tokens: **{0}**",
        "chamber_stock_jeu_d_armes": "⚔️ Arms-mastery tokens: **{0}**",
        "chamber_stock_garde": "🛡️ Royal guards: **{0}**",
        "chamber_patrouille": "🚨 Patrol: {0}",
        "chamber_use_explorateur": "🧭 Send exploring",
        "chamber_use_corruption": "🎭 Corrupt",
        "chamber_use_jeu_d_armes": "⚔️ Use",
        "chamber_use_garde": "🛡️ Place the guard",
        "chamber_use_patrouille": "🚨 Place the patrol",
        "chamber_select_lord": "Choose the lord who goes exploring:",
        "chamber_select_territory": "Choose the territory to corrupt:",
        "chamber_select_own_territory": "Choose the territory to shield:",
        "chamber_select_hour": "Choose the daily 2h tranche:",
        "chamber_done": "✅ Done — the kingdom's ledger is up to date.",
        "chamber_no_stock": "❌ No usable card in reserve.",
        "expedition_launch_note": (
            "🧭 The expedition of the **{0}** casts off — the crew is at sea."
        ),
        "expedition_return_map": (
            "🧭 The expedition of the **{0}** is back — the map **{1}** is revealed!"
        ),
        "expedition_return_civ": (
            "🧭 The expedition of the **{0}** is back — the civilization **{1}** joins the kingdom!"
        ),
        "expedition_return_tech": (
            "🧭 The expedition of the **{0}** is back — compensation: +2 ⚙️."
        ),
        "marry_button": "💍 Marry",
        "alliances_button": "🤝 Alliances",
        "church_marry_intro": "👰 Choose the Princess of your marriage:",
        "church_marry_view_title": "💍 Marry — {0}",
        "church_marry_badge": "ROYAL MARRIAGE",
        "church_marry_rules": (
            "**One active marriage only** — the chosen civilization"
            " becomes **exclusive** to your kingdom.\n"
            "💍 **{0} ring(s)** will be consumed at the celebration.\n"
            "👑 Your bond is **guaranteed until the season ends**, even"
            " on defeat.\n"
            "🔒 Combat lock: **{1}h** — indicative end of the lock counted"
            " from the click: {2}.\n"
            "🛡️ Lock state: while locked you can **neither attack, nor"
            " defend, nor use a technology card**."
        ),
        "church_marry_rules_royal": (
            "👑 Your bond is **guaranteed until the season ends**, even on"
            " defeat."
        ),
        "church_marry_princess": "Princess {0}",
        "church_marry_lock": "lock ends <t:{0}:R>",
        "church_marry_confirm_title": "💍 Confirm your marriage",
        "church_marry_confirm_sub": "princess to be · {0} ring(s) · lock {1}h",
        "church_marry_yes_button": "💍 Yes, I do",
        "church_marry_edit_button": "✏️ Change",
        "church_marry_sealed_title": "💍 Marriage sealed: **{0}**",
        "church_marry_sealed_note": (
            "The kingdom is informed — the announcement was just published"
            " in **Geopolitics**."
        ),
        "church_wedding_announce": (
            "💍 Marriage sealed — {0} of the {1} weds the **{2}** · 🔒 lock"
            " {3}h · 🎁 Offering +{4} ⚙️ · the civilization is now"
            " **exclusive** to the {1} kingdom until the bond breaks."
        ),
        "church_marry_already": (
            "💍 You already hold an active marriage — one at a time (D34)."
        ),
        "church_marry_no_options": (
            "💔 No Princess available — your hand is empty or already wed."
        ),
        "church_marry_no_points": "❌ Your kingdom holds no marriage point left (D59).",
        "church_marry_no_points_royal": "❌ A royal marriage (Reine) costs 2 marriage points.",
        "church_marry_not_in_hand": (
            "❌ This civilization is not in your kingdom's hand (Alliances)."
        ),
        "marry_error": "❌ The marriage failed: {0}",
        "alliances_title": "🤝 Alliances — {0}",
        "alliances_points": (
            "💍 Marriage points: **{0}** · Arranged-marriage tokens: **{1}**"
        ),
        "alliances_hand": "🃏 Current hand ({0})",
        "alliances_next_intro": "🔮 Next cycle (projection)",
        "alliances_next_kept": "✅ Kept: {0}",
        "alliances_next_arriving": "➕ Arriving: {0}",
        "alliances_next_dropping": "➖ Dropping: {0}",
        "alliances_next_elsewhere": "🔒 Wed elsewhere: {0}",
        "alliances_near_title": "🎯 Near unlocks",
        "alliances_near_line": "• **{0}** — {1}",
        "alliances_none": "—",
        "alliances_no_data": "❌ No alliances data yet.",
        "event_cycle": (
            "🔄 **Cycle {cycle}** — weekly budgets recharged, "
            "{maps} new maps for Gaïa."
        ),
        "event_age": (
            "🏺 **{age}** — every kingdom gains {tech} tech point(s) "
            "and {marriages} marriage slot(s)."
        ),
        "event_end": (
            "🏁 **End of the season** — the attacks are cancelled and "
            "the verdict is in: {winner}."
        ),
        "event_end_showmatch": (
            "🏁 **End of the season** — the attacks are cancelled and "
            "the top kingdoms are tied: the ShowMatch decides!"
        ),
        "tavern_button": "🍺 Taverne",
        "mercenary_button": "🗡️ Mercenaires",
        "tavern_title": "🍺 The Taverne",
        "tavern_purse": "🪙 Your purse: **{0}** écu(s)",
        "tavern_cooldown": "⏳ Next round possible <t:{0}:R> (global 24h cooldown).",
        "tavern_locked": "🔒 A combat lock is still running — ends <t:{0}:R>.",
        "tavern_select": "Choose a drink:",
        "tavern_drink_line": "{0} — {1} 🪙",
        "tavern_lock_line": "Lock {0} min",
        "tavern_confirm_title": "🍺 Confirm the order",
        "tavern_confirm_sub": "Price: **{0}** 🪙 — combat lock: **{1}** minutes.",
        "tavern_yes": "Drink",
        "tavern_drunk": "🍺 You drank **{0}** — **{1}** écu(s) left in your purse.",
        "tavern_cooldown_note": "⏳ The global 24h cooldown is still running.",
        "tavern_no_purse": "❌ Your purse cannot afford it.",
        "tavern_no_season": "❌ No season is running.",
        "tavern_season_closed": "❌ The season is over — the counter is closed.",
        "tavern_error": "❌ The Taverne refuses: {0}",
        "mercenary_title": "🗡️ The Mercenary Chief",
        "mercenary_lot_line": "• **{0}** ({1} use(s)) — highest bid: **{2}** 🪙",
        "mercenary_own_bid": "_You bid {0} 🪙._",
        "mercenary_winners": "🏆 Lots awarded: {0}",
        "mercenary_no_winner": "🍂 No lot found a buyer.",
        "mercenary_select_lot": "Choose a lot to bid on:",
        "mercenary_select_amount": "Your bid amount (écus):",
        "mercenary_bid_placed": "🗡️ Bid of **{1}** 🪙 placed on **{0}** — the écus are escrowed.",
        "mercenary_withdraw": "Withdraw my bid",
        "mercenary_withdraw_done": "✅ Your bid is withdrawn — the escrowed écus are refunded.",
        "mercenary_withdraw_none": "ℹ️ You hold no bid.",
        "mercenary_none": (
            "🍂 The Mercenary Chief is not here — he stands at the Taverne"
            " between 8pm and 9pm Paris time."
        ),
        "mercenary_bid_too_low": "❌ The bid must STRICTLY exceed the current highest.",
        "mercenary_not_open_yet": "⏳ The bids are not open yet.",
        "mercenary_closed_note": "❌ The market is closed.",
        "mercenary_already_held": "❌ One mercenary civilization at a time — you already hold one.",
        "mercenary_open_note": (
            "🗡️ **The Mercenary Chief is here** — the mercenary market is open,"
            " the bids close at the time shown on the spot. At the Taverne!"
        ),
        "mercenary_close_note": "🗡️ The mercenary market is closed — **{0}** lot(s) awarded.",
        "ffa_join_button": "🗺️ Join the Expedition",
        "ffa_join_note": (
            "✅ **{0}** holds an Expedition slot — {1}/{2} participant(s)."
        ),
        "ffa_left_note": "🚪 **{0}** released their slot — {1}/{2} participant(s).",
        "ffa_not_open": "❌ No Expedition is open for enrollment right now.",
        "ffa_full": "❌ The Expedition is full.",
        "ffa_kingdom_full": (
            "❌ Your kingdom already holds a slot (mode: one lord per kingdom)."
        ),
        "ffa_locked": (
            "❌ You are locked (a fresh Explorateur 48h lock or a missed FFA)"
            " — you cannot enroll."
        ),
        "ffa_announce": (
            "🧭 **Expedition — Saturday <t:{0}:F>**\n"
            "One FREE {1}-minute game against the Gaïa AI and the other"
            " participants — {2} slots, mode: {3}. Click"
            " **« Join the Expedition »** to reserve yours (first come, first"
            " served; click again to release it)."
        ),
        "ffa_start": (
            "🧭 **The Expedition starts now** — {0} participant(s),"
            " {1} minutes. Good luck!"
        ),
        "ffa_salon_title": "🗺️ Expedition",
        "ffa_mode_one": "one lord per kingdom",
        "ffa_mode_free": "free slots",
        "console_relaunch_label": "🔁 Relaunch the season",
        "console_reset_label": "🧹 Reset the data",
        "console_clock_label": "⏩ Game clock",
        "console_relaunch_confirm": (
            "🔁 **Relaunch the season?**\n"
            "The current data is archived then wiped, and a fresh season"
            " starts (new candidatures)."
        ),
        "console_reset_confirm": (
            "🧹 **Reset the data?**\n"
            "The current data is archived then wiped — no new season"
            " is launched."
        ),
        "console_confirm_button": "⚠️ Confirm",
        "console_cancel_button": "Cancel",
        "console_cancelled": "❌ Cancelled — nothing was touched.",
        "console_relaunch_done": "✅ Season relaunched — the old data is archived.",
        "console_reset_done": "✅ Data reset — the old data is archived.",
        "console_error": "❌ {0}",
        "console_clock_modal_title": "⏩ Advance the clock",
        "console_clock_bad": "❌ {0}",
        "console_clock_done": "✅ Game clock advanced: **{0}**.",
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
