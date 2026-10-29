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


def _q(qid: str, source: str, section: str) -> dict:
    return {"id": qid, "source": source, "section": section, "enonce": qid, "options": {}, "motifs": []}


def test_chercher_exemples_priorise_les_questions_officielles(monkeypatch: pytest.MonkeyPatch) -> None:
    base = [_q(f"com-{i}", "github-vishal-bulbule", "3.1") for i in range(6)]
    base += [_q("off-1", "google-officiel", "3.1"), _q("off-2", "google-officiel", "3.2")]
    monkeypatch.setattr("paa_coach.tools.references._load_reference_data", lambda _d: base)
    for _ in range(10):
        ids = {ex["id"] for ex in chercher_exemples(section="3", limite=3)["exemples"]}
        assert {"off-1", "off-2"} <= ids


def test_chercher_exemples_ajoute_une_ancre_officielle(monkeypatch: pytest.MonkeyPatch) -> None:
    base = [_q(f"com-{i}", "github-vishal-bulbule", "2.1") for i in range(5)]
    base += [_q("off-5", "google-officiel", "5.1")]
    monkeypatch.setattr("paa_coach.tools.references._load_reference_data", lambda _d: base)
    res = chercher_exemples(section="2.1", limite=3)
    assert res["count"] == 3
    ancres = [ex for ex in res["exemples"] if ex.get("ancre_style")]
    assert [ex["id"] for ex in ancres] == ["off-5"]


def test_chercher_exemples_sans_question_officielle(monkeypatch: pytest.MonkeyPatch) -> None:
    base = [_q(f"com-{i}", "github-vishal-bulbule", "2.1") for i in range(5)]
    monkeypatch.setattr("paa_coach.tools.references._load_reference_data", lambda _d: base)
    res = chercher_exemples(section="2.1", limite=3)
    assert res["count"] == 3
    assert not any(ex.get("ancre_style") for ex in res["exemples"])
