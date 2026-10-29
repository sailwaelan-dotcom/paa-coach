"""Tests des callbacks qui transmettent au coach la question exacte, sans corrigé."""

from __future__ import annotations

import json
from types import SimpleNamespace

from paa_coach.callbacks import apres_generation_question, avant_generation_question
from paa_coach.tools.questions import valider_et_publier
from tests.conftest import MockToolContext
from tests.test_questions import _creer_question_valide

CHALLENGER = SimpleNamespace(name="scenario_challenger")
AUTRE_OUTIL = SimpleNamespace(name="enregistrer_reponse")


def test_valider_et_publier_publie_la_question_sans_corrige(
    mock_tool_context: MockToolContext
) -> None:
    valider_et_publier(json.dumps(_creer_question_valide()), mock_tool_context)

    publique = mock_tool_context.state["question_publique"]
    complete = mock_tool_context.state["derniere_question"]
    assert publique["options"] == complete["options"]
    assert publique["enonce"] == complete["enonce"]
    assert "reponse" not in publique
    assert "pieges" not in publique
    assert "explication" not in publique


def test_avant_generation_efface_la_question_precedente() -> None:
    ctx = MockToolContext({"question_publique": {"id": "ancienne"}})
    assert avant_generation_question(tool=CHALLENGER, args={}, tool_context=ctx) is None
    assert ctx.state["question_publique"] is None


def test_apres_generation_remplace_le_resume_par_la_question_exacte() -> None:
    question = {"id": "q1", "enonce": "E", "options": {"A": "a", "B": "b", "C": "c", "D": "d"}}
    ctx = MockToolContext({"question_publique": question})
    res = apres_generation_question(
        tool=CHALLENGER,
        args={},
        tool_context=ctx,
        tool_response={"result": "Résumé du vérificateur, option correcte : C"},
    )
    assert res == {"status": "ok", "question": question}


def test_apres_generation_signale_un_echec_sans_question() -> None:
    ctx = MockToolContext({"question_publique": None})
    res = apres_generation_question(
        tool=CHALLENGER, args={}, tool_context=ctx, tool_response={"result": "..."}
    )
    assert res is not None
    assert res["status"] == "echec"


def test_callbacks_ignorent_les_autres_outils() -> None:
    ctx = MockToolContext({"question_publique": {"id": "q1"}})
    assert avant_generation_question(tool=AUTRE_OUTIL, args={}, tool_context=ctx) is None
    assert ctx.state["question_publique"] == {"id": "q1"}
    assert apres_generation_question(
        tool=AUTRE_OUTIL, args={}, tool_context=ctx, tool_response={"status": "ok"}
    ) is None
