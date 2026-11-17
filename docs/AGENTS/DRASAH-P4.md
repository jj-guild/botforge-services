# Prompt de tâche — porter Kingdoms P4 sur la nouvelle base

## Le contexte

Le mod Kingdoms est en cours de réimplémentation sur la nouvelle
plateforme (l'épic #362). Ce qui est DÉJÀ livré et mergé sur main
(tranches P0→P3) : le squelette du mod, la structure (salons,
rôles, provisionnement), et le cycle saison complet — création,
machine à états (préparation → inscriptions → attente → ouverte →
fermée), inscriptions/désistements, validation admin privée, rôles
candidat/joueur, listes candidats/participants.

## Ta mission

Récupérer le travail FONCTIONNEL de la branche `vibe/drasah/main` et
le porter sur la branche `vibe/mod-kingdom` (créée depuis main).
C'est la tranche **P4 — les boucles de gameplay** de l'issue #368 :

- Attaques : déclaration, défense, RDV, drafts pick&ban, planning
- Diplomatie : mariages, traités
- Marché : cartes, sabotage
- Taverne : bourse, boissons, verrous, rumeurs, enchères mercenaires
- Expédition FFA

Puis P5→P7 suivront (UX, outillage admin, validation) — une PR par
tranche.

## Drasah est LA référence

`vibe/drasah/main` contient le mod original — la vérité
fonctionnelle appartient à Drasah. Chaque mécanique se PORTE depuis
cette branche, adaptée aux seams de la plateforme — jamais
redesignée sans son GO explicite. Quand tu hésites sur un
comportement, NE DEVINE PAS : demande-lui. Il teste sur l'env test
(`/deploy test`) et valide chaque palier avant que tu ne déroules
le suivant. L'env drasah garde l'ancienne version — la migration se
valide sur l'env test.

## La méthode par mécanique

1. Lis le code de référence sur `vibe/drasah/main`
2. Décris à Drasah ce que tu as compris du comportement (il
   confirme ou corrige — c'est sa vérité)
3. Cherche le seam plateforme qui doit la porter (core) ; étends-le
   si nécessaire — le mod ne fait que déclarer et spécialiser
4. Porte la mécanique sur `vibe/mod-kingdom`, avec ses tests de
   non-régression
5. CI verte, PR, déploiement env test, rapport à Drasah, son GO
   avant la mécanique suivante

## Les garde-fous

- Les règles globales de l'agent s'appliquent (la cible
  micro-service, la mutualisation dans le core, les surfaces
  Discord, les ids, l'i18n, la CI) — relis `DRASAH-GLOBAL.md`.
- Une mécanique dupliquée entre core et mod va au seam (issue
  #365) ; les surfaces respectent la conformité (issue #367).
- Ne touche PAS au cycle saison P3 (livré, testé) — étends-le, ne
  le réécris pas.
- Le travail provider (elo, matchs) est fait à part — n'attends pas
  dessus.
