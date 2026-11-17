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
