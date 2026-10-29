"""Outil d'audit statique de code Google ADK Python (critères d'architecture et de qualité)."""

from __future__ import annotations

import ast
import logging
from typing import Any

logger = logging.getLogger(__name__)

MAX_CODE_LENGTH = 50_000
KNOWN_AGENT_CLASSES = frozenset({
    "Agent", "LlmAgent", "LoopAgent", "SequentialAgent",
    "ParallelAgent", "Workflow", "BaseAgent"
})


def _is_tool_context_annotation(annotation: ast.AST | None) -> bool:
    """Détermine si une annotation de type fait référence à ToolContext."""
    if annotation is None:
        return False
    if isinstance(annotation, ast.Name):
        return annotation.id == "ToolContext"
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "ToolContext"
    if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
        return "ToolContext" in annotation.value
    return False


def auditer_code_adk(code: str) -> dict[str, Any]:
    """Audite statiquement du code Python ADK sans jamais l'exécuter.

    Vérifie les bonnes pratiques ADK et les exigences de développement :
    - Syntaxe Python valide.
    - Annotations de types sur tous les arguments et retours de fonctions.
    - Docstrings sur toutes les fonctions publiques (PEP 257).
    - Nommage strict du paramètre 'tool_context' pour les outils ADK.
    - Présence d'un 'name' valide (identifiant Python) et d'une 'description' sur les agents.
    - Définition de 'max_iterations' sur les LoopAgent.
    - Présence d'un 'root_agent' défini au niveau racine du module.

    Args:
        code: Le code source Python à analyser (longueur <= 50 000 caractères).

    Returns:
        Un dictionnaire contenant la liste des anomalies trouvées et un résumé.
    """
    if len(code) > MAX_CODE_LENGTH:
        return {
            "status": "error",
            "message": f"Code trop volumineux ({len(code)} caractères, maximum autorisé: {MAX_CODE_LENGTH}).",
            "problemes": [{
                "ligne": 1,
                "regle": "max_length_exceeded",
                "message": f"Le code dépasse la limite autorisée de {MAX_CODE_LENGTH} caractères.",
            }],
        }

    problemes: list[dict[str, Any]] = []

    # 1. Analyse syntaxique via ast (sans aucune exécution)
    try:
        tree = ast.parse(code)
    except SyntaxError as err:
        return {
            "status": "ok",
            "problemes": [{
                "ligne": err.lineno or 1,
                "regle": "syntax_error",
                "message": f"Erreur de syntaxe Python: {err.msg}",
            }],
            "resume": "1 erreur de syntaxe empêchant l'analyse statique.",
        }

    has_root_agent = False

    # 2. Analyse des affectations racine pour root_agent
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == "root_agent":
                    has_root_agent = True
        elif isinstance(stmt, ast.AnnAssign):
            if isinstance(stmt.target, ast.Name) and stmt.target.id == "root_agent":
                has_root_agent = True

    if not has_root_agent:
        problemes.append({
            "ligne": 1,
            "regle": "module_root_agent",
            "message": "Absence de 'root_agent' défini au niveau du module.",
        })

    # 3. Parcours complet de l'AST pour les fonctions et instanciations d'agents
    for node in ast.walk(tree):
        # A. Vérification des fonctions
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Docstring pour fonctions publiques
            if not node.name.startswith("_"):
                doc = ast.get_docstring(node)
                if not doc or not doc.strip():
                    problemes.append({
                        "ligne": node.lineno,
                        "regle": "public_docstring",
                        "message": f"La fonction publique '{node.name}' n'a pas de docstring.",
                    })

            # Annotation de retour
            if node.returns is None:
                problemes.append({
                    "ligne": node.lineno,
                    "regle": "type_annotations",
                    "message": f"La fonction '{node.name}' n'a pas d'annotation de type de retour.",
                })

            # Annotations des arguments
            for arg in node.args.args:
                if arg.arg in ("self", "cls"):
                    continue
                if arg.annotation is None:
                    problemes.append({
                        "ligne": node.lineno,
                        "regle": "type_annotations",
                        "message": f"L'argument '{arg.arg}' de la fonction '{node.name}' n'a pas d'annotation de type.",
                    })

                # Outils ADK : ToolContext nommé obligatoirement tool_context
                if _is_tool_context_annotation(arg.annotation) and arg.arg != "tool_context":
                    problemes.append({
                        "ligne": node.lineno,
                        "regle": "tool_context_naming",
                        "message": f"L'argument de type ToolContext dans '{node.name}' doit être nommé exactement 'tool_context' (trouvé: '{arg.arg}').",
                    })

        # B. Vérification des instanciations d'agents
        if isinstance(node, ast.Call):
            func_name = ""
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                func_name = node.func.attr

            if func_name in KNOWN_AGENT_CLASSES:
                # Récupérer les arguments nommés
                kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}

                # Vérifier 'name'
                if "name" not in kwargs:
                    problemes.append({
                        "ligne": node.lineno,
                        "regle": "agent_name",
                        "message": f"L'agent {func_name} doit avoir un argument 'name'.",
                    })
                else:
                    name_node = kwargs["name"]
                    if isinstance(name_node, ast.Constant) and isinstance(name_node.value, str):
                        if not name_node.value.isidentifier():
                            problemes.append({
                                "ligne": node.lineno,
                                "regle": "agent_name_validity",
                                "message": f"Le nom d'agent '{name_node.value}' n'est pas un identifiant Python valide.",
                            })

                # Si LoopAgent, vérifier max_iterations
                if func_name == "LoopAgent":
                    if "max_iterations" not in kwargs:
                        problemes.append({
                            "ligne": node.lineno,
                            "regle": "loop_agent_max_iterations",
                            "message": "LoopAgent doit obligatoirement définir 'max_iterations'.",
                        })
                    else:
                        iter_val = kwargs["max_iterations"]
                        if isinstance(iter_val, ast.Constant) and iter_val.value is None:
                            problemes.append({
                                "ligne": node.lineno,
                                "regle": "loop_agent_max_iterations",
                                "message": "LoopAgent ne doit pas avoir 'max_iterations=None'.",
                            })

                # Vérifier la présence de 'description' si l'agent a des sub_agents ou est dans une liste
                if "sub_agents" in kwargs:
                    sub_list = kwargs["sub_agents"]
                    if isinstance(sub_list, ast.List):
                        for sub_item in sub_list.elts:
                            if isinstance(sub_item, ast.Call):
                                sub_kwargs = {kw.arg: kw.value for kw in sub_item.keywords if kw.arg}
                                if "description" not in sub_kwargs:
                                    problemes.append({
                                        "ligne": sub_item.lineno,
                                        "regle": "subagent_description",
                                        "message": "Un sous-agent déclaré dans 'sub_agents' doit avoir une 'description' pour permettre le routage.",
                                    })

    resume = f"{len(problemes)} problème(s) identifié(s)." if problemes else "Aucun problème détecté. Le code respecte les standards ADK."

    return {
        "status": "ok",
        "problemes": problemes,
        "resume": resume,
    }
