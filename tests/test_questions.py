"""Tests unitaires pour les outils de validation, publication et réponse aux questions."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from paa_coach import config
from paa_coach.tools.questions import enregistrer_reponse, valider_et_publier
from tests.conftest import MockToolContext


@pytest.fixture(autouse=True)
def setup_reference_dir(fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure PAA_REFERENCE_DIR pour pointer vers les fixtures de test."""
    monkeypatch.setattr(config, "PAA_REFERENCE_DIR", fixtures_dir)


def _creer_question_valide(
    enonce: str = "A completely brand new original architecture question about Agent Gateway and VPC-SC",
    motifs: list[str] | None = None,
    sources_doc: list[str] | None = None,
) -> dict:
    return {
        "section": "3.1",
        "motifs": motifs or ["concept-voisin"],
        "difficulte": 2,
        "enonce": enonce,
        "options": {
            "A": "Option Alpha distinctive answer",
            "B": "Option Beta distinctive answer",
            "C": "Option Gamma correct distinctive answer",
            "D": "Option Delta distinctive answer",
        },
        "reponse": "C",
        "explication": "Option C is correct because of specific reason.",
        "pieges": {
            "A": "Trap Alpha details",
            "B": "Trap Beta details",
            "D": "Trap Delta details",
        },
        "sources_doc": sources_doc or ["https://cloud.google.com/vertex-ai/docs/agent-architecture"],
        "a_verifier": False,
    }


# ============================================================================
# Tests pour valider_et_publier
# ============================================================================

def test_valider_et_publier_succes(mock_tool_context: MockToolContext) -> None:
    q = _creer_question_valide()
    payload = json.dumps(q)

    res = valider_et_publier(payload, mock_tool_context)
    assert res["status"] == "ok"
    assert "question" in res
    published = res["question"]

    # Pas de réponse ni d'explication dans la question publique
    assert "reponse" not in published
    assert "explication" not in published
    assert "pieges" not in published
    assert published["enonce"] == q["enonce"]

    # Doit avoir mis à jour derniere_question dans le state
    assert "derniere_question" in mock_tool_context.state
    full_saved = mock_tool_context.state["derniere_question"]
    assert full_saved["enonce"] == q["enonce"]
    assert full_saved["reponse"] in {"A", "B", "C", "D"}

    # Doit avoir activé escalate
    assert mock_tool_context.actions.escalate is True


def test_valider_et_publier_melange_et_remappage(mock_tool_context: MockToolContext) -> None:
    q = _creer_question_valide()
    correct_text = q["options"]["C"]
    payload = json.dumps(q)

    res = valider_et_publier(payload, mock_tool_context)
    assert res["status"] == "ok"

    saved = mock_tool_context.state["derniere_question"]
    new_rep_letter = saved["reponse"]
    new_options = saved["options"]
    new_pieges = saved["pieges"]

    # Le texte de la bonne réponse doit correspondre à la nouvelle lettre
    assert new_options[new_rep_letter] == correct_text

    # Les pièges doivent couvrir exactement les 3 autres options
    mauvaises_lettres = {"A", "B", "C", "D"} - {new_rep_letter}
    assert set(new_pieges.keys()) == mauvaises_lettres

    # Les pièges doivent correspondre aux bons textes originaux
    for bad_letter in mauvaises_lettres:
        bad_text = new_options[bad_letter]
        orig_letter = next(k for k, v in q["options"].items() if v == bad_text)
        assert new_pieges[bad_letter] == q["pieges"][orig_letter]


def test_valider_et_publier_json_invalide(mock_tool_context: MockToolContext) -> None:
    res = valider_et_publier("{invalide json syntax", mock_tool_context)
    assert res["status"] == "rejected"
    assert "Syntaxe JSON invalide" in res["errors"][0]
    assert mock_tool_context.actions.escalate is not True


def test_valider_et_publier_champs_manquants(mock_tool_context: MockToolContext) -> None:
    q = _creer_question_valide()
    del q["options"]
    del q["reponse"]
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "rejected"
    assert any("options" in err for err in res["errors"])
    assert any("reponse" in err for err in res["errors"])


def test_valider_et_publier_motif_invalide(mock_tool_context: MockToolContext) -> None:
    q = _creer_question_valide(motifs=["motif-totalement-invente"])
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "rejected"
    assert any("Motif non autorisé" in err for err in res["errors"])


def test_valider_et_publier_options_doublons(mock_tool_context: MockToolContext) -> None:
    q = _creer_question_valide()
    q["options"]["B"] = q["options"]["A"]  # Doublon
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "rejected"
    assert any("distinctes" in err for err in res["errors"])


def test_valider_et_publier_difficulte_hors_bornes(mock_tool_context: MockToolContext) -> None:
    q = _creer_question_valide()
    q["difficulte"] = 5
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "rejected"
    assert any("difficulte" in err for err in res["errors"])


def test_valider_et_publier_anti_copie_rejet(mock_tool_context: MockToolContext) -> None:
    # L'énoncé de fixture-q01 est : "Synthetic architecture question for unit test fixture 01"
    copie = "Synthetic architecture question for unit test fixture 01 and slight variation"
    q = _creer_question_valide(enonce=copie)
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "rejected"
    assert any("trop proche" in err for err in res["errors"])


def test_valider_et_publier_domaine_sources_externe_force_a_verifier(
    mock_tool_context: MockToolContext
) -> None:
    # URL sur domaine non Google autorisé (ex. example.com)
    q = _creer_question_valide(sources_doc=["https://example.com/unauthorized-doc"])
    q["a_verifier"] = False
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "ok"
    assert res["question"]["a_verifier"] is True
    assert mock_tool_context.state["derniere_question"]["a_verifier"] is True


# ============================================================================
# Tests pour enregistrer_reponse
# ============================================================================

def test_enregistrer_reponse_sans_question_en_attente(
    mock_tool_context: MockToolContext
) -> None:
    res = enregistrer_reponse("A", mock_tool_context)
    assert res["status"] == "error"
    assert "Aucune question" in res["message"]


def test_enregistrer_reponse_lettre_invalide(mock_tool_context: MockToolContext) -> None:
    mock_tool_context.state["derniere_question"] = {
        "id": "q1",
        "reponse": "B",
        "section": "3.1",
    }
    res = enregistrer_reponse("Z", mock_tool_context)
    assert res["status"] == "error"
    assert "Réponse invalide" in res["message"]


def test_enregistrer_reponse_juste_et_casse(mock_tool_context: MockToolContext) -> None:
    mock_tool_context.state["derniere_question"] = {
        "id": "q1",
        "reponse": "B",
        "section": "3.1",
        "motifs": ["concept-voisin"],
        "explication": "Bravo",
        "pieges": {"A": "P1", "C": "P2", "D": "P3"},
        "sources_doc": ["https://cloud.google.com"],
        "a_verifier": False,
    }
    # Test avec espaces et minuscule
    res = enregistrer_reponse("  b  ", mock_tool_context)
    assert res["status"] == "ok"
    assert res["correct"] is True
    assert res["bonne_reponse"] == "B"
    assert res["explication"] == "Bravo"

    # Vérifier mise à jour de l'historique
    historique = mock_tool_context.state["user:historique"]
    assert len(historique) == 1
    assert historique[0]["correct"] is True
    assert historique[0]["id"] == "q1"


def test_enregistrer_reponse_faux_et_maj_weak_areas(
    mock_tool_context: MockToolContext
) -> None:
    mock_tool_context.state["derniere_question"] = {
        "id": "q2",
        "reponse": "C",
        "section": "5.1",
        "motifs": ["service-detourne", "nom-rassurant-mauvaise-menace"],
    }
    res = enregistrer_reponse("A", mock_tool_context)
    assert res["status"] == "ok"
    assert res["correct"] is False
    assert res["bonne_reponse"] == "C"

    weak_areas = mock_tool_context.state["user:weak_areas"]
    noms = {w["nom"] for w in weak_areas}
    assert "5.1" in noms
    assert "service-detourne" in noms


def test_enregistrer_reponse_regle_80_pourcent_validation(
    mock_tool_context: MockToolContext
) -> None:
    # Simuler 4 réponses justes pour la section 2.1
    mock_tool_context.state["user:historique"] = [
        {"id": f"q_{i}", "section": "2.1", "motifs": [], "correct": True}
        for i in range(4)
    ]
    mock_tool_context.state["derniere_question"] = {
        "id": "q_5",
        "reponse": "A",
        "section": "2.1",
        "motifs": [],
    }

    # 5ème réponse juste (5/5 = 100% >= 80%) -> 2.1 doit être validée
    enregistrer_reponse("A", mock_tool_context)
    assert "2.1" in mock_tool_context.state["user:validated_modules"]

    # Ajouter 2 réponses fausses : les 5 dernières deviennent [True, True, True, False, False] = 3/5 = 60%
    # -> 2.1 doit perdre sa validation
    for i in range(6, 8):
        mock_tool_context.state["derniere_question"] = {
            "id": f"q_{i}",
            "reponse": "A",
            "section": "2.1",
            "motifs": [],
        }
        enregistrer_reponse("B", mock_tool_context)  # Fausses réponses

    assert "2.1" not in mock_tool_context.state["user:validated_modules"]


def test_enregistrer_reponse_question_consommee_une_seule_fois(
    mock_tool_context: MockToolContext
) -> None:
    mock_tool_context.state["derniere_question"] = {
        "id": "q1",
        "reponse": "B",
        "section": "3.1",
        "motifs": [],
    }
    assert enregistrer_reponse("B", mock_tool_context)["status"] == "ok"

    # Une seconde réponse à la même question ne doit pas être comptée
    res = enregistrer_reponse("B", mock_tool_context)
    assert res["status"] == "error"
    assert "Aucune question" in res["message"]
    assert len(mock_tool_context.state["user:historique"]) == 1


def test_valider_et_publier_rejette_bonne_reponse_nettement_plus_longue(
    mock_tool_context: MockToolContext
) -> None:
    q = _creer_question_valide()
    q["options"]["C"] = (
        "Option Gamma correct answer with many extra architecture details that"
        " make it stand out from every other choice"
    )
    res = valider_et_publier(json.dumps(q), mock_tool_context)
    assert res["status"] == "rejected"
    assert any("plus longue" in err for err in res["errors"])
    assert "derniere_question" not in mock_tool_context.state


def test_valider_et_publier_accepte_longueurs_comparables(
    mock_tool_context: MockToolContext
) -> None:
    # La bonne réponse est la plus longue, mais dans la marge tolérée
    res = valider_et_publier(json.dumps(_creer_question_valide()), mock_tool_context)
    assert res["status"] == "ok"
