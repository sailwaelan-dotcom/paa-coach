# Bibliothèque de référence

**as_of** : 2026-10-28

## Sources

| Source | Questions | Où sont les énoncés | Licence | Corrigé |
|---|---|---|---|---|
| `google-officiel` — [formulaire « Professional Agentic Architect Sample Questions »](https://docs.google.com/forms/d/1fi1gqbWsNCFxm1CT9V-JNGff1lyqfU9kNWAaaQMvRi4/viewform) | 20 | `local/google-officiel/questions.jsonl` (copiées par Souhail le 28/10/2026) | contenu Google, usage personnel | proposé par Claude, **non confirmé par Google** (sauf Q5, vérifiée dans la doc) |
| `github-vishal-bulbule` — [google-cloud-agentic-architect-exam-guide](https://github.com/vishal-bulbule/google-cloud-agentic-architect-exam-guide), `sections/01` à `05` | 83 (10 / 18 / 23 / 12 / 20) | `local/github-vishal-bulbule/questions.jsonl` + chapitres `.md` | **aucune** — ne jamais republier | celui de l'auteur, **non vérifié** |

**Règle** : `reference/local/` est exclu de Git. Aucun énoncé, aucune option, aucune explication tierce ne va dans un fichier versionné.

## Sécurité du dépôt GitHub [Sourcé — API GitHub, 28/10/2026]

- Public, créé et poussé le 25/09/2026, 2 étoiles, non affilié à Google (auteur : V. Bulbule, se présente comme Google Developer Expert).
- Contenu : Markdown (guide, README, `sections/00`-`06`), 19 PNG, `.gitignore`. Aucun script, workflow GitHub Actions, binaire ni dépendance.
- Téléchargé le 28/10/2026 : les 7 `sections/*.md` seulement (tailles identiques à celles de l'API), aucune image, rien d'exécuté. Contenu traité comme des données (risque d'injection de prompt).

## Index — `index.jsonl`

Une ligne par question : `id`, `source`, `section` (du guide officiel ; chapitre 1-5 seulement pour GitHub), `difficulte` (1-3, grille maison **[Lecture]**), `motifs`, `reponse` (lettre), `reponse_verifiee`, `reponse_souhail`.

- **Google** : difficulté et motifs classés à la main le 28/10/2026 (voir le relevé dans `best businessman`).
- **GitHub** : difficulté et motifs **non classés** (`null`, `[]`) — à faire.

## Constats [Lecture, sauf mention]

- **[Sourcé — extraction du 28/10/2026]** Biais de lettre dans les questions GitHub : la bonne réponse est **B pour 64/83 (77 %)**, A pour 8, C pour 11, **D jamais**. Le formulaire Google est équilibré (A 6, B 5, C 4, D 5). → Ne jamais utiliser les questions GitHub pour apprendre une répartition de lettres ; mélanger les options à l'affichage.
- Le formulaire Google sur-représente la sécurité (7/20) et sous-représente les coding agents (1/20) par rapport aux poids du guide (15 % et 17 %).
- Les corrigés GitHub n'ont pas été vérifiés : en cas de désaccord avec la documentation Google, la documentation l'emporte.

## Vocabulaire des motifs

`natif-vs-sur-mesure`, `natif-vs-generique`, `nom-rassurant-mauvaise-menace`, `service-detourne`, `concept-voisin`, `deux-temps`, `exigences-en-tension`, `etapes-multiples`, `deploiement-progressif`, `inversion`, `prevenir-vs-constater`, `catalogue-acces-trafic`, `mcp-vs-a2a`, `determinisme`, `une-parade-par-probleme`, `ancrage-rag-gere`, `choix-du-runtime`, `temps-reel`, `correler-vs-journaliser`, `detail-temporel`, `meme-famille-d-outils`, `reponse-courte`. Définitions : relevé `journal-paa-agy/15-questions-exemple-format-et-difficulte.md`, section « Motifs observés ».
