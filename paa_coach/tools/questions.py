"""Outils de validation, de publication et de suivi des réponses aux questions."""

from __future__ import annotations

import difflib
import json
import logging
import random
import time
from typing import Any
from urllib.parse import urlparse

from google.adk.tools.tool_context import ToolContext

from .. import config
from .references import _load_reference_data

logger = logging.getLogger(__name__)


def _verifier_anti_copie(enonce: str) -> tuple[bool, str | None]:
    """Vérifie si l'énoncé est trop proche d'une question existante de la bibliothèque."""
    try:
        ref_dir = config.PAA_REFERENCE_DIR
        reference_items = _load_reference_data(ref_dir)
        enonce_clean = enonce.strip().lower()
        matcher = difflib.SequenceMatcher(None, enonce_clean, "")

        for item in reference_items:
            ref_enonce = item.get("enonce", "").strip().lower()
            if not ref_enonce:
                continue
            matcher.set_seq2(ref_enonce)
            ratio = matcher.ratio()
            if ratio > config.ANTI_COPIE_MAX_RATIO:
                return False, f"Énoncé trop proche de l'exemple '{item.get('id')}' (similarité: {ratio:.2f} > {config.ANTI_COPIE_MAX_RATIO})"
        return True, None
    except Exception as exc:
        logger.warning("Erreur lors de la vérification anti-copie: %s", exc)
        return True, None


def _valider_domaines_sources(sources_doc: Any) -> bool:
    """Vérifie que les sources documentaires proviennent bien des domaines officiels Google autorisés."""
    if not isinstance(sources_doc, list) or len(sources_doc) == 0:
        return False
    for url in sources_doc:
        if not isinstance(url, str):
            return False
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            # Supprimer un éventuel numéro de port
            if ":" in netloc:
                netloc = netloc.split(":")[0]
            if netloc not in config.ALLOWED_DOC_DOMAINS:
                return False
        except Exception:
            return False
    return True


def valider_et_publier(question_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Valide une question d'examen générée et la publie dans l'état de session si elle est conforme.

    Effectue des contrôles déterministes stricts :
    1. Structure JSON, présence des 4 options (A-D distinctes), pièges pour chaque mauvaise option.
    2. Motifs conformes au vocabulaire officiel de motifs.md.
    3. Contrôle anti-copie contre les énoncés de la bibliothèque (seuil SequenceMatcher <= 0.6).
    4. Validation des sources Google Docs officielles (force a_verifier à True si non conforme).
    5. Mélange aléatoire des options et remappage de la bonne réponse et des pièges.
    6. Arrêt de la boucle de génération via actions.escalate = True.

    Args:
        question_json: La question sérialisée en JSON.
        tool_context: Contexte d'outils ADK pour interagir avec le state et le flux.

    Returns:
        Un dictionnaire status 'ok' avec la question sans corrigé, ou 'rejected' avec la liste des erreurs.
    """
    try:
        try:
            data = json.loads(question_json)
        except json.JSONDecodeError as err:
            return {"status": "rejected", "errors": [f"Syntaxe JSON invalide: {err}"]}

        if not isinstance(data, dict):
            return {"status": "rejected", "errors": ["La question doit être un objet JSON."]}

        errors: list[str] = []

        # 1. Vérification des champs requis
        required_fields = [
            "section", "motifs", "difficulte", "enonce",
            "options", "reponse", "explication", "pieges", "sources_doc"
        ]
        for field in required_fields:
            if field not in data:
                errors.append(f"Champ obligatoire manquant: '{field}'")

        if errors:
            return {"status": "rejected", "errors": errors}

        # 2. Validation des types et valeurs
        section = str(data["section"]).strip()
        if not section:
            errors.append("Le champ 'section' ne peut être vide.")

        motifs = data["motifs"]
        if not isinstance(motifs, list) or len(motifs) == 0:
            errors.append("Le champ 'motifs' doit être une liste non vide.")
        else:
            for m in motifs:
                if m not in config.MOTIFS_AUTORISES:
                    errors.append(f"Motif non autorisé: '{m}' (doit appartenir au vocabulaire de motifs.md).")

        difficulte = data["difficulte"]
        if not isinstance(difficulte, int) or difficulte not in (1, 2, 3):
            errors.append("Le champ 'difficulte' doit être un entier valant 1, 2 ou 3.")

        enonce = str(data["enonce"]).strip()
        if not enonce:
            errors.append("Le champ 'enonce' ne peut être vide.")

        options = data["options"]
        if not isinstance(options, dict) or set(options.keys()) != {"A", "B", "C", "D"}:
            errors.append("Le champ 'options' doit être un dictionnaire avec exactement les clés A, B, C et D.")
        else:
            opt_values = [str(v).strip() for v in options.values()]
            if any(not v for v in opt_values):
                errors.append("Aucune option ne peut être vide.")
            if len(set(opt_values)) != 4:
                errors.append("Les 4 options doivent être distinctes les unes des autres.")

        reponse = str(data["reponse"]).strip().upper()
        if reponse not in {"A", "B", "C", "D"}:
            errors.append("Le champ 'reponse' doit être une lettre parmi A, B, C ou D.")

        pieges = data["pieges"]
        if isinstance(options, dict) and reponse in {"A", "B", "C", "D"}:
            mauvaises_options = {"A", "B", "C", "D"} - {reponse}
            if not isinstance(pieges, dict) or set(pieges.keys()) != mauvaises_options:
                errors.append(f"Le dictionnaire 'pieges' doit expliquer exactement les 3 mauvaises options: {sorted(mauvaises_options)}.")
            else:
                for k, v in pieges.items():
                    if not str(v).strip():
                        errors.append(f"L'explication du piège pour l'option {k} ne peut être vide.")

        explication = str(data["explication"]).strip()
        if not explication:
            errors.append("Le champ 'explication' ne peut être vide.")

        # 3. Contrôle anti-copie
        if enonce:
            est_original, msg_anti_copie = _verifier_anti_copie(enonce)
            if not est_original:
                errors.append(msg_anti_copie or "Énoncé trop similaire à un exemple existant.")

        if errors:
            return {"status": "rejected", "errors": errors}

        # 4. Vérification documentaire des sources (§ 6.5)
        sources_valides = _valider_domaines_sources(data["sources_doc"])
        a_verifier = bool(data.get("a_verifier", False))
        if not sources_valides:
            a_verifier = True

        # 5. Mélange de l'ordre des options et remappage
        option_letters = ["A", "B", "C", "D"]
        correct_text = options[reponse]
        trap_by_text = {options[letter]: pieges[letter] for letter in options if letter != reponse}

        shuffled_texts = list(options.values())
        random.shuffle(shuffled_texts)

        new_options: dict[str, str] = {
            letter: text for letter, text in zip(option_letters, shuffled_texts)
        }
        new_reponse = next(k for k, v in new_options.items() if v == correct_text)
        new_pieges: dict[str, str] = {
            k: trap_by_text[v] for k, v in new_options.items() if k != new_reponse
        }

        # 6. Attribuer un ID unique et enregistrer dans l'état
        q_id = f"gen-{int(time.time() * 1000)}"
        full_question = {
            "id": q_id,
            "section": section,
            "motifs": motifs,
            "difficulte": difficulte,
            "enonce": enonce,
            "options": new_options,
            "reponse": new_reponse,
            "explication": explication,
            "pieges": new_pieges,
            "sources_doc": data["sources_doc"],
            "a_verifier": a_verifier,
        }

        # Publication dans le state de session
        tool_context.state["derniere_question"] = full_question

        # Interrompre la boucle LoopAgent
        tool_context.actions.escalate = True

        # Question publique renvoyée (sans corrigé)
        public_question = {
            "id": q_id,
            "section": section,
            "motifs": motifs,
            "difficulte": difficulte,
            "enonce": enonce,
            "options": new_options,
            "sources_doc": data["sources_doc"],
            "a_verifier": a_verifier,
        }

        return {"status": "ok", "question": public_question}

    except Exception as exc:
        logger.exception("Erreur inattendue dans valider_et_publier")
        return {"status": "rejected", "errors": [f"Erreur interne de validation: {exc}"]}


def enregistrer_reponse(reponse: str, tool_context: ToolContext) -> dict[str, Any]:
    """Enregistre la réponse de l'utilisateur, compare avec la bonne réponse et met à jour l'historique.

    Met à jour dans l'état persistant utilisateur :
    - `user:historique` : 200 derniers résultats avec identifiant, section, motifs et succès.
    - `user:weak_areas` : 10 sections et motifs les plus ratés, ordonnés par échecs décroissants.
    - `user:validated_modules` : sections validées (au moins 5 tentatives et 80% de succès sur les 5 dernières).

    Args:
        reponse: Lettre choisie par l'utilisateur (A, B, C ou D).
        tool_context: Contexte d'outils ADK.

    Returns:
        Dictionnaire avec statut, succès, bonne réponse, explication, pièges et sources.
    """
    try:
        derniere_question = tool_context.state.get("derniere_question")
        if not derniere_question or not isinstance(derniere_question, dict):
            return {
                "status": "error",
                "message": "Aucune question n'est en attente de réponse.",
            }

        lettre = reponse.strip().upper()
        if lettre not in {"A", "B", "C", "D"}:
            return {
                "status": "error",
                "message": f"Réponse invalide '{reponse}'. La réponse doit être A, B, C ou D.",
            }

        bonne_reponse = derniere_question["reponse"]
        est_juste = (lettre == bonne_reponse)

        q_id = derniere_question.get("id", "inconnu")
        section = derniere_question.get("section", "inconnue")
        motifs = derniere_question.get("motifs", [])

        # 1. Mise à jour de user:historique (borné à 200 entrées)
        historique: list[dict[str, Any]] = list(tool_context.state.get("user:historique", []))
        historique.append({
            "id": q_id,
            "section": section,
            "motifs": motifs,
            "correct": est_juste,
            "reponse_donnee": lettre,
            "timestamp": time.time(),
        })
        if len(historique) > 200:
            historique = historique[-200:]
        tool_context.state["user:historique"] = historique

        # 2. Mise à jour de user:weak_areas (Top 10 des faiblesses)
        echecs_par_section: dict[str, int] = {}
        echecs_par_motif: dict[str, int] = {}

        for h in historique:
            if not h.get("correct", False):
                sec = h.get("section")
                if sec:
                    echecs_par_section[sec] = echecs_par_section.get(sec, 0) + 1
                for m in h.get("motifs", []):
                    echecs_par_motif[m] = echecs_par_motif.get(m, 0) + 1

        weak_areas: list[dict[str, Any]] = []
        for sec, cnt in echecs_par_section.items():
            weak_areas.append({"type": "section", "nom": sec, "echecs": cnt})
        for m, cnt in echecs_par_motif.items():
            weak_areas.append({"type": "motif", "nom": m, "echecs": cnt})

        # Trier par nombre d'échecs décroissant et borner à 10
        weak_areas.sort(key=lambda x: x["echecs"], reverse=True)
        tool_context.state["user:weak_areas"] = weak_areas[:10]

        # 3. Mise à jour de user:validated_modules (>= 5 réponses et >= 80% sur les 5 dernières)
        sections_vues = {h["section"] for h in historique if "section" in h}
        modules_valides: list[str] = []

        for sec in sorted(sections_vues):
            rep_sec = [h for h in historique if h.get("section") == sec]
            if len(rep_sec) >= 5:
                dernieres_5 = rep_sec[-5:]
                reussites = sum(1 for h in dernieres_5 if h.get("correct", False))
                if (reussites / 5.0) >= 0.8:
                    modules_valides.append(sec)

        tool_context.state["user:validated_modules"] = modules_valides

        # La question est consommée : empêche un double comptage et une notation sur une question périmée
        tool_context.state["derniere_question"] = None

        return {
            "status": "ok",
            "correct": est_juste,
            "bonne_reponse": bonne_reponse,
            "reponse_donnee": lettre,
            "explication": derniere_question.get("explication", ""),
            "pieges": derniere_question.get("pieges", {}),
            "sources_doc": derniere_question.get("sources_doc", []),
            "a_verifier": derniere_question.get("a_verifier", False),
        }

    except Exception as exc:
        logger.exception("Erreur inattendue dans enregistrer_reponse")
        return {"status": "error", "message": f"Erreur interne: {exc}"}
