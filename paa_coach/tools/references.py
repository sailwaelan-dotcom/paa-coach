"""Outil de recherche d'exemples dans la bibliothèque de référence."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

from .. import config

logger = logging.getLogger(__name__)


def _matches_section(target_sec: str, entry_sec: str) -> bool:
    """Vérifie la correspondance de section (exacte ou par préfixe)."""
    target = target_sec.strip()
    entry = entry_sec.strip()
    return target == entry or entry.startswith(target) or target.startswith(entry)


def _load_reference_data(ref_dir: Path) -> list[dict[str, Any]]:
    """Charge l'index et fusionne avec les questions détaillées disponibles."""
    index_file = ref_dir / "index.jsonl"
    if not index_file.exists():
        # Essayer sous reference/ si ref_dir ne contient pas directement index.jsonl
        alt_index = ref_dir / "reference" / "index.jsonl"
        if alt_index.exists():
            index_file = alt_index
            ref_dir = alt_index.parent
        else:
            return []

    index_entries: dict[str, dict[str, Any]] = {}
    with open(index_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                q_id = entry.get("id")
                if q_id:
                    index_entries[q_id] = entry
            except json.JSONDecodeError:
                continue

    # Chercher tous les questions.jsonl dans ref_dir et ses sous-dossiers
    detailed_questions: dict[str, dict[str, Any]] = {}
    for q_path in ref_dir.rglob("questions.jsonl"):
        try:
            with open(q_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    q_data = json.loads(line)
                    q_id = q_data.get("id")
                    if q_id:
                        detailed_questions[q_id] = q_data
        except Exception as e:
            logger.warning("Erreur de lecture de %s: %s", q_path, e)

    # Fusionner
    merged: list[dict[str, Any]] = []
    for q_id, idx in index_entries.items():
        q_det = detailed_questions.get(q_id, {})
        merged.append({
            "id": q_id,
            "source": idx.get("source", ""),
            "section": idx.get("section", ""),
            "difficulte": idx.get("difficulte"),
            "motifs": idx.get("motifs") or [],
            "reponse": idx.get("reponse") or q_det.get("reponse"),
            "reponse_verifiee": bool(idx.get("reponse_verifiee", False)),
            "enonce": q_det.get("enonce", ""),
            "options": q_det.get("options", {}),
            "explication": q_det.get("explication", ""),
        })

    return merged


def chercher_exemples(
    section: str,
    motif: str | None = None,
    difficulte: int | None = None,
    limite: int = 3,
) -> dict[str, Any]:
    """Recherche des exemples de questions dans la bibliothèque de référence.

    Cette fonction filtre la base selon la section d'examen demandée, et optionnellement
    selon un motif de question et un niveau de difficulté. Si aucun exemple ne correspond
    à tous les critères, les filtres sont relâchés progressivement (d'abord la difficulté,
    puis le motif).

    Args:
        section: Code de la section PAA (ex. '3', '3.1', '5.2').
        motif: Nom du motif recherché (ex. 'concept-voisin', 'natif-vs-sur-mesure').
        difficulte: Niveau de difficulté souhaité (1, 2 ou 3).
        limite: Nombre maximal d'exemples à retourner (par défaut 3).

    Returns:
        Un dictionnaire contenant le statut, les exemples trouvés et les détails du filtre.
    """
    try:
        ref_dir = Path(config.PAA_REFERENCE_DIR)
        all_questions = _load_reference_data(ref_dir)
        if not all_questions:
            return {
                "status": "ok",
                "exemples": [],
                "count": 0,
                "message": f"Aucune donnée trouvée dans {ref_dir}",
            }

        # Étape 1 : section obligatoire
        candidates_section = [
            q for q in all_questions
            if _matches_section(section, str(q.get("section", "")))
        ]

        if not candidates_section:
            return {
                "status": "ok",
                "exemples": [],
                "count": 0,
                "message": f"Aucun exemple correspondant à la section {section}",
            }

        filtre_actif = {"section": section}
        selected = candidates_section

        # Filtrage avec relâchement progressif
        # Tentative 1 : avec motif et difficulté si fournis
        if motif and difficulte is not None:
            matches = [
                q for q in selected
                if motif in (q.get("motifs") or []) and q.get("difficulte") == difficulte
            ]
            if matches:
                selected = matches
                filtre_actif.update({"motif": motif, "difficulte": difficulte})
            else:
                # Relâcher difficulte, garder motif
                matches_motif = [q for q in selected if motif in (q.get("motifs") or [])]
                if matches_motif:
                    selected = matches_motif
                    filtre_actif.update({"motif": motif, "difficulte_relachee": True})
                else:
                    # Relâcher motif également
                    filtre_actif.update({"motif_relache": True, "difficulte_relachee": True})
        elif motif:
            matches_motif = [q for q in selected if motif in (q.get("motifs") or [])]
            if matches_motif:
                selected = matches_motif
                filtre_actif.update({"motif": motif})
            else:
                filtre_actif.update({"motif_relache": True})
        elif difficulte is not None:
            matches_diff = [q for q in selected if q.get("difficulte") == difficulte]
            if matches_diff:
                selected = matches_diff
                filtre_actif.update({"difficulte": difficulte})
            else:
                filtre_actif.update({"difficulte_relachee": True})

        # Tirage au sort borné par limite, questions officielles d'abord : elles donnent
        # le niveau de l'examen (choix d'architecture), le guide communautaire est plus technique
        officielles = [q for q in selected if q.get("source") == config.SOURCE_OFFICIELLE]
        autres = [q for q in selected if q.get("source") != config.SOURCE_OFFICIELLE]
        random.shuffle(officielles)
        random.shuffle(autres)
        echantillon = (officielles + autres)[:max(limite, 0)]

        # Sans question officielle dans la sélection, une officielle d'une autre section
        # sert d'ancre de style
        ancre_id: str | None = None
        if echantillon and not officielles:
            ancres = [q for q in all_questions if q.get("source") == config.SOURCE_OFFICIELLE]
            if ancres:
                ancre = random.choice(ancres)
                ancre_id = ancre["id"]
                echantillon = echantillon[:max(limite - 1, 0)] + [ancre]

        # Formater les exemples en recopiant fidèlement reponse_verifiee
        resultats: list[dict[str, Any]] = []
        for q in echantillon:
            resultats.append({
                "id": q["id"],
                "enonce": q.get("enonce", ""),
                "options": q.get("options", {}),
                "reponse": q.get("reponse"),
                "section": q.get("section"),
                "motifs": q.get("motifs", []),
                "source": q.get("source"),
                "reponse_verifiee": q.get("reponse_verifiee", False),
                "ancre_style": q["id"] == ancre_id,
            })

        return {
            "status": "ok",
            "exemples": resultats,
            "count": len(resultats),
            "filtre_applique": filtre_actif,
        }

    except Exception as exc:
        logger.exception("Erreur inattendue dans chercher_exemples")
        return {"status": "error", "message": f"Erreur interne: {exc}"}
