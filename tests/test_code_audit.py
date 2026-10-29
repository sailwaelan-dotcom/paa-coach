"""Tests unitaires pour l'audit statique de code ADK."""

from __future__ import annotations

from pathlib import Path
import pytest

from paa_coach.tools.code_audit import auditer_code_adk


def test_audit_code_valide() -> None:
    code = '''"""Module agent conforme."""
from google.adk.agents import LlmAgent
from google.adk.tools.tool_context import ToolContext

def mon_outil(param: str, tool_context: ToolContext) -> dict:
    """Outil d'exemple bien annoté."""
    return {"status": "ok"}

root_agent = LlmAgent(name="mon_agent", instruction="...")
'''
    res = auditer_code_adk(code)
    assert res["status"] == "ok"
    assert len(res["problemes"]) == 0
    assert "respecte les standards" in res["resume"]


def test_audit_syntax_error() -> None:
    code = "def fonction_invalide(: pass"
    res = auditer_code_adk(code)
    assert res["status"] == "ok"
    assert len(res["problemes"]) == 1
    assert res["problemes"][0]["regle"] == "syntax_error"


def test_audit_code_trop_long() -> None:
    code = "a = 1\n" * 15_000  # > 50 000 caractères
    assert len(code) > 50_000
    res = auditer_code_adk(code)
    assert res["status"] == "error"
    assert "dépasse la limite" in res["problemes"][0]["message"]


def test_audit_preuve_code_non_execute(tmp_path: Path) -> None:
    piege_fichier = tmp_path / "danger_execute.txt"
    # Ce code contient une écriture disque et une exception fatale :
    # Si le code était exécuté (via eval, exec ou import), le fichier existerait ou une erreur surviendrait.
    code = f'''
with open(r"{piege_fichier}", "w") as f:
    f.write("FAIL")
raise RuntimeError("Ce code a été exécuté !")
'''
    # L'audit ne doit pas lever d'erreur ni créer le fichier
    res = auditer_code_adk(code)
    assert res["status"] == "ok"
    assert not piege_fichier.exists(), "Sécurité violée : le code soumis a été exécuté !"


def test_audit_regle_absence_root_agent() -> None:
    code = '''
def ma_fonction() -> None:
    """Docstring."""
    pass
'''
    res = auditer_code_adk(code)
    regles = [p["regle"] for p in res["problemes"]]
    assert "module_root_agent" in regles


def test_audit_regle_annotations_manquantes() -> None:
    code = '''
root_agent = None

def f_sans_retour(x: int):
    """Doc."""
    pass

def f_sans_arg(x) -> int:
    """Doc."""
    return 1
'''
    res = auditer_code_adk(code)
    problemes = [p for p in res["problemes"] if p["regle"] == "type_annotations"]
    assert len(problemes) == 2


def test_audit_regle_docstring_publique_manquante() -> None:
    code = '''
root_agent = None

def publique(x: int) -> int:
    return x

def _privee(x: int) -> int:
    return x
'''
    res = auditer_code_adk(code)
    problemes = [p for p in res["problemes"] if p["regle"] == "public_docstring"]
    assert len(problemes) == 1
    assert "publique" in problemes[0]["message"]


def test_audit_regle_nommage_tool_context() -> None:
    code = '''
root_agent = None
from google.adk.tools.tool_context import ToolContext

def mauvais_outil(ctx: ToolContext) -> dict:
    """Doc."""
    return {}
'''
    res = auditer_code_adk(code)
    problemes = [p for p in res["problemes"] if p["regle"] == "tool_context_naming"]
    assert len(problemes) == 1
    assert "tool_context" in problemes[0]["message"]


def test_audit_regle_loop_agent_sans_max_iterations() -> None:
    code = '''
from google.adk.agents import LoopAgent
root_agent = LoopAgent(name="mon_loop")
'''
    res = auditer_code_adk(code)
    problemes = [p for p in res["problemes"] if p["regle"] == "loop_agent_max_iterations"]
    assert len(problemes) == 1


def test_audit_regle_agent_name_invalide() -> None:
    code = '''
from google.adk.agents import LlmAgent
root_agent = LlmAgent(name="mon-agent-avec-tirets", instruction="...")
'''
    res = auditer_code_adk(code)
    problemes = [p for p in res["problemes"] if p["regle"] == "agent_name_validity"]
    assert len(problemes) == 1
