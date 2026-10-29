# Motifs de construction des questions

**as_of** : 2026-10-29 · Définitions résumées par Claude à partir du relevé de Souhail du 28/10/2026 (`journal-paa-agy/15-questions-exemple-format-et-difficulte.md`, dépôt `best businessman`, section « Motifs observés »). Aucun énoncé de question ici.

Un motif décrit **comment une question piège** : `question_writer` en choisit un ou deux pour construire une question, `valider_et_publier` refuse tout motif absent de cette liste.

| Motif | Définition |
|---|---|
| `natif-vs-sur-mesure` | Une solution sur mesure marche aussi, mais « minimum overhead » désigne le service géré par Google. |
| `natif-vs-generique` | Face à des produits réseau ou API généraux (Cloud Armor, Apigee, Service Mesh…), la brique propre à la plateforme d'agents l'emporte. |
| `nom-rassurant-mauvaise-menace` | Une vraie protection (VPC-SC, Model Armor, Shielded VM) appliquée à une menace qu'elle ne traite pas. |
| `service-detourne` | Un service réel présenté dans un rôle qui n'est pas le sien (Model Armor comme générateur de trafic ou validateur de format). |
| `concept-voisin` | Deux notions proches à distinguer (session vs mémoire à long terme). |
| `deux-temps` | Une contrainte élimine une paire d'options, une seconde départage la paire restante. |
| `exigences-en-tension` | L'énoncé demande deux choses opposées en apparence ; le piège principal en sacrifie une. |
| `etapes-multiples` | Chaque option enchaîne plusieurs actions ; une seule étape fausse disqualifie l'option. |
| `deploiement-progressif` | Pour surveiller d'abord : mode test (dry-run), lecture des journaux, puis application stricte. |
| `inversion` | Les deux bons services sont présents mais à la mauvaise place (MCP entre agents, A2A vers les outils). |
| `prevenir-vs-constater` | Un garde-fou « automatique à l'exécution » doit agir pendant l'exécution ; alertes et analyses après coup ne comptent pas. |
| `catalogue-acces-trafic` | Agent Registry = qui existe ; Agent Identity = qui a le droit ; Agent Gateway = ce qui passe. |
| `mcp-vs-a2a` | MCP relie un agent à des outils et données ; A2A relie des agents autonomes et opaques entre eux. |
| `determinisme` | Ordre fixé par le développeur (workflow séquentiel, parallèle, graphe) contre ordre décidé par le modèle. |
| `une-parade-par-probleme` | L'énoncé liste plusieurs failles ; la bonne option traite chacune avec le bon outil, au bon moment. |
| `ancrage-rag-gere` | Données internes → data store géré et outil de récupération ; jamais le web public ni tout le corpus dans le prompt. |
| `choix-du-runtime` | Agent Runtime (minimum d'infrastructure) vs GKE (contrôle maximal) vs Cloud Run (conteneur simple). |
| `temps-reel` | « Real-time » élimine tout ce qui agit sur des données au repos (journaux, buckets). |
| `correler-vs-journaliser` | Relier des journaux passe par un identifiant propagé (traceparent), pas par davantage de journaux. |
| `detail-temporel` | Un détail de temps (« newly developed ») rend impossible une option fondée sur l'historique. |
| `meme-famille-d-outils` | Quatre outils réels de la même famille ; un seul mot de l'énoncé choisit le bon. |
| `reponse-courte` | Les options longues empilent des services pour paraître complètes ; la plus courte peut être la bonne. |
