"""Callbacks du coach : transmettre la question exacte, sans corrigé, après génération.

AgentTool ne renvoie au coach que le dernier texte de scenario_challenger, un résumé
rédigé par le vérificateur : options absentes ou reformulées, bonne lettre parfois
divulguée. Ces callbacks remplacent ce résumé par la question publiée dans le state.
"""

from __future__ import annotations

from typing import Any

from google.adk.tools.base_tool import BaseTool
from google.adk.tools.tool_context import ToolContext

_GENERATEUR = "scenario_challenger"


def avant_generation_question(
    tool: BaseTool, args: dict[str, Any], tool_context: ToolContext
) -> dict[str, Any] | None:
    """Efface la question publique précédente pour ne jamais présenter une question périmée."""
    if tool.name == _GENERATEUR:
        tool_context.state["question_publique"] = None
    return None


def apres_generation_question(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> dict[str, Any] | None:
    """Remplace le résumé du générateur par la question validée, sans corrigé."""
    if tool.name != _GENERATEUR:
        return None
    question = tool_context.state.get("question_publique")
    if not question:
        return {
            "status": "echec",
            "message": "Aucune question n'a pu être validée après 3 essais.",
        }
    return {"status": "ok", "question": question}
