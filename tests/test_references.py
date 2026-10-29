"""Tests unitaires pour l'outil chercher_exemples."""

from __future__ import annotations

from pathlib import Path
import pytest

from paa_coach import config
from paa_coach.tools.references import chercher_exemples


@pytest.fixture(autouse=True)
def setup_reference_dir(fixtures_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure PAA_REFERENCE_DIR vers le dossier de fixtures pour les tests."""
    monkeypatch.setattr(config, "PAA_REFERENCE_DIR", fixtures_dir)


def test_chercher_exemples_filtre_section_prefixe() -> None:
    # '3' doit trouver 3.1 et 3.2
    res = chercher_exemples(section="3", limite=10)
    assert res["status"] == "ok"
    assert res["count"] == 2
    ids = {ex["id"] for ex in res["exemples"]}
    assert ids == {"fixture-q01", "fixture-q02"}


def test_chercher_exemples_filtre_section_exacte() -> None:
    res = chercher_exemples(section="3.1", limite=10)
    assert res["status"] == "ok"
    assert res["count"] == 1
    assert res["exemples"][0]["id"] == "fixture-q01"
    assert res["exemples"][0]["section"] == "3.1"


def test_chercher_exemples_filtre_motif_exact() -> None:
    res = chercher_exemples(section="3", motif="concept-voisin")
    assert res["status"] == "ok"
    assert res["count"] == 1
    assert res["exemples"][0]["id"] == "fixture-q01"


def test_chercher_exemples_relachement_difficulte() -> None:
    # fixture-q01 est difficulte 2 avec motif concept-voisin.
    # On demande difficulte 3 (inexistante avec ce motif) -> doit relâcher la difficulté
    res = chercher_exemples(section="3.1", motif="concept-voisin", difficulte=3)
    assert res["status"] == "ok"
    assert res["count"] == 1
    assert res["exemples"][0]["id"] == "fixture-q01"
    assert res["filtre_applique"].get("difficulte_relachee") is True


def test_chercher_exemples_relachement_motif_et_difficulte() -> None:
    # Motif inexistant dans la section 3.1
    res = chercher_exemples(section="3.1", motif="motif-inexistant", difficulte=3)
    assert res["status"] == "ok"
    # Doit relâcher le motif et renvoyer ce qui correspond à la section
    assert res["count"] == 1
    assert res["exemples"][0]["id"] == "fixture-q01"
    assert res["filtre_applique"].get("motif_relache") is True


def test_chercher_exemples_section_inconnue() -> None:
    res = chercher_exemples(section="99.9")
    assert res["status"] == "ok"
    assert res["count"] == 0
    assert res["exemples"] == []


def test_chercher_exemples_limite() -> None:
    res = chercher_exemples(section="3", limite=1)
    assert res["status"] == "ok"
    assert res["count"] == 1
    assert len(res["exemples"]) == 1


def test_chercher_exemples_reponse_verifiee_fidele() -> None:
    # fixture-q01 a reponse_verifiee=false, fixture-q02 a reponse_verifiee=true
    res = chercher_exemples(section="3", limite=10)
    assert res["status"] == "ok"
    by_id = {ex["id"]: ex for ex in res["exemples"]}
    assert by_id["fixture-q01"]["reponse_verifiee"] is False
    assert by_id["fixture-q02"]["reponse_verifiee"] is True
