"""Configuration centralisée pour paa-coach.

Toutes les variables sont paramétrables via l'environnement.
Aucune valeur secrète ni identifiant personnel n'est codé en dur.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

# Modèle par défaut sur Vertex AI
# Source : https://cloud.google.com/vertex-ai/generative-ai/docs/learn/models
# gemini-3.5-flash est le modèle Flash stable de référence combinant raisonnement hybride,
# latence ultra-faible et capacités d'outils (Function Calling) validées sur Vertex AI.
DEFAULT_MODEL: Final[str] = "gemini-3.5-flash"

PAA_MODEL: str = os.getenv("PAA_MODEL", DEFAULT_MODEL)
GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "global")

# Forcer Vertex AI pour le SDK google-genai / ADK
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")

# Model Armor Templates (projets/<projet>/locations/<région>/templates/<nom>)
PAA_MODEL_ARMOR_PROMPT_TEMPLATE: str | None = os.getenv("PAA_MODEL_ARMOR_PROMPT_TEMPLATE")
PAA_MODEL_ARMOR_RESPONSE_TEMPLATE: str | None = os.getenv("PAA_MODEL_ARMOR_RESPONSE_TEMPLATE")

# Clé optionnelle Developer Knowledge API (si authentification statique plutôt qu'ADC)
DEVELOPER_KNOWLEDGE_API_KEY: str | None = os.getenv("DEVELOPER_KNOWLEDGE_API_KEY")

# Contrôle d'accès et gouvernance
PAA_ALLOWED_MEMBER: str = os.getenv("PAA_ALLOWED_MEMBER", "")
PAA_BUDGET_EUR: int = int(os.getenv("PAA_BUDGET_EUR", "20"))

# Répertoire des sources de référence
# Par défaut paa_coach/data/ si présent, sinon reference/
_ROOT_DIR = Path(__file__).resolve().parent.parent
_DEFAULT_DATA_DIR = _ROOT_DIR / "paa_coach" / "data"
_FALLBACK_REF_DIR = _ROOT_DIR / "reference"

PAA_REFERENCE_DIR: Path = Path(
    os.getenv(
        "PAA_REFERENCE_DIR",
        str(_DEFAULT_DATA_DIR if _DEFAULT_DATA_DIR.exists() else _FALLBACK_REF_DIR),
    )
)

# Poids officiels du guide d'examen PAA
# Source : https://services.google.com/fh/files/misc/professional_agentic_architect_exam_guide_english.pdf
POIDS_SECTIONS: Final[dict[str, float]] = {
    "1": 0.13,  # Low-code
    "2": 0.17,  # Coding agents
    "3": 0.33,  # Agents sur mesure
    "4": 0.22,  # Évaluation et déploiement
    "5": 0.15,  # Sécurité et gouvernance
}

SOUS_SECTIONS: Final[dict[str, str]] = {
    "1.1": "Configuring agentic workflows and behavior using low-code tools",
    "1.2": "Connecting enterprise data to Gemini Enterprise",
    "2.1": "Using coding agents effectively",
    "2.2": "Customizing coding agents for enterprise workflows",
    "3.1": "Designing and building agentic workflows in code",
    "3.2": "Integrating enterprise domain knowledge",
    "3.3": "Orchestrating and coordinating agentic workflows",
    "4.1": "Evaluating agents in development and in production",
    "4.2": "Deploying and scaling production workloads",
    "5.1": "Configuring agent security and governance",
    "5.2": "Implementing secure agent behavior and execution",
}

# Lacunes initiales mesurées le 28/10/2026 (14/19 sur l'échantillon officiel)
LACUNES_INITIALES: Final[dict[str, list[str]]] = {
    "sections": ["5.1", "5.2", "2.1", "3.3"],
    "sujets": [
        "Agent Gateway",
        "Agent Registry / Identity",
        "Cloud Workstations",
        "A2A",
        "VPC-SC vs Model Armor",
    ],
}

# Vocabulaire des motifs autorisés (définis dans reference/motifs.md)
MOTIFS_AUTORISES: Final[frozenset[str]] = frozenset({
    "natif-vs-sur-mesure",
    "natif-vs-generique",
    "nom-rassurant-mauvaise-menace",
    "service-detourne",
    "concept-voisin",
    "deux-temps",
    "exigences-en-tension",
    "etapes-multiples",
    "deploiement-progressif",
    "inversion",
    "prevenir-vs-constater",
    "catalogue-acces-trafic",
    "mcp-vs-a2a",
    "determinisme",
    "une-parade-par-probleme",
    "ancrage-rag-gere",
    "choix-du-runtime",
    "temps-reel",
    "correler-vs-journaliser",
    "detail-temporel",
    "meme-famille-d-outils",
    "reponse-courte",
})

# Domaines autorisés pour la documentation officielle Google
ALLOWED_DOC_DOMAINS: Final[frozenset[str]] = frozenset({
    "docs.cloud.google.com",
    "cloud.google.com",
    "adk.dev",
    "google.github.io",
    "ai.google.dev",
    "developers.google.com",
})

# Seuil anti-copie (difflib SequenceMatcher ratio maximal autorisé)
ANTI_COPIE_MAX_RATIO: Final[float] = 0.6

# Source des questions d'exemple officielles Google, prioritaires comme modèles de style
SOURCE_OFFICIELLE: Final[str] = "google-officiel"

# Longueur maximale de la bonne réponse, relativement au piège le plus long
LONGUEUR_OPTION_MAX_RATIO: Final[float] = 1.4
