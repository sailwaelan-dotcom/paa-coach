"""Point d'entrée principal des agents et de l'application ADK paa-coach."""

from __future__ import annotations

import logging
from typing import Any

from google.adk.agents import LlmAgent, LoopAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.tools import McpToolset
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.mcp_tool.mcp_toolset import StreamableHTTPConnectionParams
from google.genai.types import HttpRetryOptions

from . import config, prompts
from .callbacks import apres_generation_question, avant_generation_question
from .tools import auditer_code_adk, chercher_exemples, enregistrer_reponse, valider_et_publier

logger = logging.getLogger(__name__)

# Modèle Gemini unifié avec politique de retry automatique sur 429 (Resource Exhausted)
adk_model = Gemini(
    model=config.PAA_MODEL,
    retry_options=HttpRetryOptions(
        attempts=5,
        initial_delay=2.0,
        max_delay=30.0,
        exp_base=2.0,
        http_status_codes=[429, 503],
    ),
)


def _mcp_header_provider(readonly_ctx: Any) -> dict[str, str]:
    """Fournit dynamiquement les en-têtes d'authentification pour le serveur MCP."""
    headers: dict[str, str] = {"User-Agent": "paa-coach/1.0"}
    if config.DEVELOPER_KNOWLEDGE_API_KEY:
        headers["X-Goog-Api-Key"] = config.DEVELOPER_KNOWLEDGE_API_KEY
    else:
        try:
            import google.auth
            import google.oauth2.credentials
            from google.auth.transport.requests import Request
            creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            if not creds.valid:
                creds.refresh(Request())
            if creds.token:
                headers["Authorization"] = f"Bearer {creds.token}"
            # Identifiants utilisateur (usage local) : l'API exige un projet de quota,
            # sinon chaque recherche échoue. Inutile pour le compte de service Cloud Run.
            quota_project = getattr(creds, "quota_project_id", None) or config.GOOGLE_CLOUD_PROJECT
            if isinstance(creds, google.oauth2.credentials.Credentials) and quota_project:
                headers["x-goog-user-project"] = quota_project
        except Exception as e:
            logger.debug("Aucun jeton ADC généré pour MCP: %s", e)
    return headers


def _build_mcp_toolset() -> McpToolset | None:
    """Initialise le toolset MCP pour le serveur Google Developer Knowledge officiel."""
    try:
        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(
                url="https://developerknowledge.googleapis.com/mcp",
            ),
            header_provider=_mcp_header_provider,
            tool_filter=["search_documents", "get_documents"],
        )
    except Exception as exc:
        logger.warning("Serveur MCP Developer Knowledge non disponible: %s", exc)
        return None


# 1. Configuration des outils MCP
mcp_toolset = _build_mcp_toolset()
writer_tools: list[Any] = [chercher_exemples]
checker_tools: list[Any] = [valider_et_publier]
reviewer_tools: list[Any] = [auditer_code_adk]

if mcp_toolset is not None:
    writer_tools.append(mcp_toolset)
    checker_tools.append(mcp_toolset)
    reviewer_tools.append(mcp_toolset)

# 2. Sous-agents de génération de question (scenario_challenger)
question_writer = LlmAgent(
    name="question_writer",
    description="Rédige une question d'architecture PAA inédite au format JSON pour une section et un motif donnés.",
    model=adk_model,
    instruction=prompts.QUESTION_WRITER_INSTRUCTION,
    tools=writer_tools,
)

question_checker = LlmAgent(
    name="question_checker",
    description="Valide la pertinence technique d'une question PAA et appelle valider_et_publier.",
    model=adk_model,
    instruction=prompts.QUESTION_CHECKER_INSTRUCTION,
    tools=checker_tools,
    output_key="temp:critique",
)

scenario_challenger = LoopAgent(
    name="scenario_challenger",
    description="Génère et valide une question d'architecture PAA inédite en boucle (3 itérations maximum).",
    sub_agents=[question_writer, question_checker],
    max_iterations=3,
)

# 3. Coach d'entraînement interactif
coach_agent = LlmAgent(
    name="coach_agent",
    description="Entraîne Souhail avec des questions d'architecture PAA, valide ses réponses et suit ses progrès.",
    model=adk_model,
    instruction=prompts.COACH_INSTRUCTION,
    tools=[
        AgentTool(agent=scenario_challenger),
        enregistrer_reponse,
    ],
    before_tool_callback=avant_generation_question,
    after_tool_callback=apres_generation_question,
)

# 4. Expert relecteur de code ADK
code_reviewer = LlmAgent(
    name="code_reviewer",
    description="Audite et relit du code Google ADK Python (labs pratiques) selon les critères de qualité et d'architecture.",
    model=adk_model,
    instruction=prompts.CODE_REVIEWER_INSTRUCTION,
    tools=reviewer_tools,
)

# 5. Agent de triage racine
triage_agent = LlmAgent(
    name="triage_agent",
    description="Agent d'accueil racine, résume l'avancement et oriente vers le coach d'examen ou la revue de code.",
    model=adk_model,
    instruction=prompts.TRIAGE_INSTRUCTION,
    sub_agents=[coach_agent, code_reviewer],
)

# Racine exportée pour ADK
root_agent = triage_agent

# 6. Configuration de l'App ADK avec Model Armor si activé
app_plugins: list[Any] = []
if config.PAA_MODEL_ARMOR_PROMPT_TEMPLATE:
    try:
        from google.adk.integrations.model_armor import ModelArmorConfig, ModelArmorPlugin
        armor_cfg = ModelArmorConfig(
            prompt_template_name=config.PAA_MODEL_ARMOR_PROMPT_TEMPLATE,
            response_template_name=config.PAA_MODEL_ARMOR_RESPONSE_TEMPLATE,
        )
        app_plugins.append(ModelArmorPlugin(config=armor_cfg))
        logger.info("ModelArmorPlugin configuré avec succès.")
    except Exception as err:
        logger.warning("Impossible d'activer ModelArmorPlugin: %s", err)

app = App(
    name="paa_coach",
    root_agent=root_agent,
    plugins=app_plugins,
)
