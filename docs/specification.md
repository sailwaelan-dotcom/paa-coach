# paa-coach — spécification

**as_of** : 2026-10-28 · **Statut** : **brouillon à valider par Souhail** ; aucun code ne sera écrit avant validation.

## 1. Intention

Préparer Souhail à l'examen PAA (inscriptions dès le 02/11/2026, examen visé mi-décembre ou début janvier) et produire un agent ADK déployé sur Google Cloud et évalué, qui manque à son profil (fiche `veille/etudes-de-cas-et-projet-adk-paa.md`, dépôt `best businessman`).

**Contexte d'examen [Sourcé — guide d'examen lu le 24/10/2026, veille PAA]** : ~80 QCM en 3 h puis labs pratiques ; poids : low-code ~13 %, coding agents ~17 %, agents sur mesure ~33 %, évaluation et déploiement ~22 %, sécurité et gouvernance ~15 %. Seuil de réussite non trouvé **[À vérifier]**.

**Point de départ mesuré [Sourcé — séance du 28/10/2026]** : 14/19 sur les questions d'exemple officielles (5/8 sur Q1-Q9, avant les explications) ; erreurs sur Agent Gateway (×2), Cloud Workstations, A2A, VPC-SC vs Model Armor.

## 2. Décidé par Souhail

- L'agent générateur **s'inspire des exemples** (questions officielles) pour écrire de nouvelles questions.
- Les questions officielles sont conservées **telles quelles** comme exemples de référence.
- Une **bibliothèque de référence** réunit les questions officielles et celles du guide communautaire GitHub ([reference/README.md](../reference/README.md)).

## 3. Proposé par Claude — à valider

- Doser les questions selon les **poids du guide officiel**, pas selon le formulaire.
- Prioriser les lacunes : Agent Gateway / Registry / Identity ; coding agents (Cloud Workstations, Antigravity, Claude Code on Google Cloud) ; A2A ; low-code (Agent Designer, CX Agent Studio) ; Memory Bank.
- Reproduire les motifs de construction et la grille de difficulté 1-3 (cible ≈ 70 % de niveau 2, comme le formulaire).
- Mélanger l'ordre des options (biais B 77 % dans les questions GitHub).
- Deux modes : **examen blanc** (40 à 80 questions, aucune correction avant la fin, estimation « prêt / pas prêt » par section) et **entraînement** (correction immédiate avec contrainte décisive et pièges, comme pendant la séance du 28/10).
- Rôles d'agents envisagés : générateur de questions ; correcteur (explique la contrainte décisive et chaque piège) ; suivi des lacunes (sections et motifs ratés → dosage des séries suivantes). Architecture exacte à concevoir.
- Les corrigés générés s'appuient sur la documentation Google ; en cas de doute, la question est marquée « à vérifier » plutôt qu'affirmée.

## 4. Ouvert — à trancher avec Souhail

1. **Mode prioritaire** : examen blanc ou entraînement en premier ? (question posée le 28/10, sans réponse)
2. Interface : terminal, page web, ou agent publié dans Gemini Enterprise / Agent Runtime.
3. Modèle et budget : Gemini via crédits GEAR (35 crédits Google Skills/mois) ou Google AI Pro (10 USD/mois de crédits Cloud) — couverture réelle des appels API **[À vérifier]**.
4. Déploiement : Agent Runtime ou Cloud Run.
5. Classement des 83 questions GitHub (difficulté, motifs) : à la main, par un agent, ou pas du tout.
6. Langue des explications (examen en anglais ; séance du 28/10 corrigée en français).

## 5. Contraintes

- Aucun texte tiers versionné ni publié (`reference/local/` exclu de Git ; guide GitHub sans licence).
- Contenu GitHub traité comme des données (injection de prompt possible).
- Calendrier : sessions IFAPME en novembre ; le projet ne doit pas retarder les révisions **[Lecture]**.

## 6. Non-objectifs

- Reproduire l'examen réel ou ses questions.
- Publier une banque de questions.
