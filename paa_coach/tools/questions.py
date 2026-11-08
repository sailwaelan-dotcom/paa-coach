"""Outils de validation, de publication et de suivi des réponses aux questions."""

from __future__ import annotations

import difflib
import json
import logging
import random
import re
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


_EXIGENCE_NUMEROTEE = re.compile(r"\((\d)\)|^\s*(\d)[.)]\s", re.MULTILINE)


def _verifier_format_enonce(enonce: str) -> list[str]:
    """Vérifie que l'énoncé garde le format des questions officielles Google.

    Les questions officielles font de 33 à 105 mots et posent deux exigences numérotées
    au plus. Une longue liste d'exigences permet d'éliminer les pièges en les comparant
    point par point, sans connaître le sujet.
    """
    erreurs: list[str] = []
    nb_mots = len(enonce.split())
    if nb_mots > config.ENONCE_MAX_MOTS:
        erreurs.append(
            f"Énoncé trop long ({nb_mots} mots, {config.ENONCE_MAX_MOTS} au plus) : "
            "garde une ou deux contraintes, comme les questions officielles."
        )
    numeros = {a or b for a, b in _EXIGENCE_NUMEROTEE.findall(enonce)}
    if len(numeros) > config.ENONCE_MAX_EXIGENCES_NUMEROTEES:
        erreurs.append(
            f"L'énoncé liste {len(numeros)} exigences numérotées "
            f"({config.ENONCE_MAX_EXIGENCES_NUMEROTEES} au plus) : garde une ou deux contraintes."
        )
    return erreurs


_LETTRES_PAR_FORMAT: dict[int, list[str]] = {
    1: ["A", "B", "C", "D"],  # 1 bonne réponse parmi 4
    2: ["A", "B", "C", "D", "E"],  # 2 bonnes réponses parmi 5 ('Choose two')
}


def _bonne_reponse_se_repere(options: dict[str, Any], bonnes: list[str]) -> bool:
    """Indique si les bonnes réponses sont plus longues que tous les pièges, options inégales."""
    longueurs = {k: len(str(v).strip()) for k, v in options.items()}
    longueur_max_pieges = max(n for k, n in longueurs.items() if k not in bonnes)
    equilibrees = (
        max(longueurs.values()) <= config.OPTIONS_EQUILIBREES_MAX_RATIO * min(longueurs.values())
    )
    return min(longueurs[b] for b in bonnes) > longueur_max_pieges and not equilibrees


def valider_et_publier(question_json: str, tool_context: ToolContext) -> dict[str, Any]:
    """Valide une question d'examen générée et la publie dans l'état de session si elle est conforme.

    Effectue des contrôles déterministes stricts :
    1. Structure JSON : 1 bonne réponse parmi 4 options A-D, ou 2 bonnes réponses parmi 5 options
       A-E (format 'Choose two') ; pièges pour chacune des 3 mauvaises options.
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
        errors.extend(_verifier_format_enonce(enonce))

        # Format : 1 bonne réponse parmi 4 (A-D) ou 2 bonnes réponses parmi 5 (A-E)
        reponse_brute = data["reponse"]
        if isinstance(reponse_brute, list):
            bonnes = sorted({str(r).strip().upper() for r in reponse_brute})
            if len(bonnes) != 2 or len(reponse_brute) != 2:
                errors.append(
                    "Une question à réponses multiples attend exactement 2 lettres distinctes "
                    "dans 'reponse' (format 'Choose two', 5 options A-E)."
                )
        else:
            bonnes = [str(reponse_brute).strip().upper()]
        lettres = _LETTRES_PAR_FORMAT.get(len(bonnes), _LETTRES_PAR_FORMAT[1])

        options = data["options"]
        if not isinstance(options, dict) or set(options.keys()) != set(lettres):
            errors.append(
                f"Le champ 'options' doit être un dictionnaire avec exactement les clés "
                f"{', '.join(lettres)} ({len(lettres)} options pour {len(bonnes)} bonne(s) réponse(s))."
            )
        else:
            opt_values = [str(v).strip() for v in options.values()]
            if any(not v for v in opt_values):
                errors.append("Aucune option ne peut être vide.")
            if len(set(opt_values)) != len(lettres):
                errors.append(f"Les {len(lettres)} options doivent être distinctes les unes des autres.")

        if not set(bonnes) <= set(lettres):
            errors.append(f"Le champ 'reponse' doit désigner des lettres parmi {', '.join(lettres)}.")

        pieges = data["pieges"]
        mauvaises_options = set(lettres) - set(bonnes)
        if isinstance(options, dict) and set(bonnes) <= set(lettres):
            if not isinstance(pieges, dict) or set(pieges.keys()) != mauvaises_options:
                errors.append(f"Le dictionnaire 'pieges' doit expliquer exactement les 3 mauvaises options: {sorted(mauvaises_options)}.")
            else:
                for k, v in pieges.items():
                    if not str(v).strip():
                        errors.append(f"L'explication du piège pour l'option {k} ne peut être vide.")

        # Les bonnes réponses ne doivent pas se repérer à leur longueur
        serie: list[bool] = []
        if not errors:
            longueur_bonne = max(len(str(options[b]).strip()) for b in bonnes)
            longueur_max_pieges = max(len(str(options[k]).strip()) for k in mauvaises_options)
            se_repere = _bonne_reponse_se_repere(options, bonnes)
            # Sur les dernières publications, la plus longue ne doit pas être la bonne trop souvent
            serie = list(tool_context.state.get("user:bonne_plus_longue", []))
            serie = (serie + [se_repere])[-config.BONNE_PLUS_LONGUE_FENETRE:]
            part = sum(serie) / len(serie)
            if longueur_bonne > config.LONGUEUR_OPTION_MAX_RATIO * longueur_max_pieges:
                errors.append(
                    f"Une bonne réponse est nettement plus longue que les pièges "
                    f"({longueur_bonne} contre {longueur_max_pieges} caractères au plus) : "
                    "équilibre la longueur et le niveau de détail des options."
                )
            elif se_repere and part > config.BONNE_PLUS_LONGUE_MAX_PART:
                errors.append(
                    "Les bonnes réponses sont plus longues que tous les pièges : avec cette question, ce "
                    f"serait le cas dans {sum(serie)} des {len(serie)} dernières questions publiées "
                    f"({round(config.BONNE_PLUS_LONGUE_MAX_PART * 100)} % au plus). Raccourcis une bonne "
                    "réponse ou allonge un piège, pour que la longueur ne trahisse pas la réponse."
                )

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
        correct_texts = {options[b] for b in bonnes}
        trap_by_text = {options[letter]: pieges[letter] for letter in mauvaises_options}

        shuffled_texts = [options[letter] for letter in lettres]
        random.shuffle(shuffled_texts)

        new_options: dict[str, str] = dict(zip(lettres, shuffled_texts))
        # Réponse stockée comme chaîne : "C", ou "AC" pour 2 bonnes réponses (lettres triées)
        new_reponse = "".join(k for k, v in new_options.items() if v in correct_texts)
        new_pieges: dict[str, str] = {
            k: trap_by_text[v] for k, v in new_options.items() if v not in correct_texts
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
            "nb_reponses": len(bonnes),
            "explication": explication,
            "pieges": new_pieges,
            "sources_doc": data["sources_doc"],
            "a_verifier": a_verifier,
        }

        # Publication dans le state de session
        tool_context.state["derniere_question"] = full_question
        tool_context.state["user:bonne_plus_longue"] = serie

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
            "nb_reponses": len(bonnes),
            "sources_doc": data["sources_doc"],
            "a_verifier": a_verifier,
        }
        # Lue par le callback du coach : la question affichée est celle qui sera notée
        tool_context.state["question_publique"] = public_question

        return {"status": "ok", "question": public_question}

    except Exception as exc:
        logger.exception("Erreur inattendue dans valider_et_publier")
        return {"status": "rejected", "errors": [f"Erreur interne de validation: {exc}"]}


FENETRE_LACUNES: int = 5
"""Nombre de derniers essais par section ou motif pris en compte pour les lacunes."""


def _calculer_lacunes(historique: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Calcule les lacunes récentes à partir de l'historique pris en compte.

    Pour chaque section et chaque motif, seuls les `FENETRE_LACUNES` derniers essais
    comptent : une erreur ancienne, suivie de réponses justes, sort de la liste.

    Args:
        historique: Réponses prises en compte, de la plus ancienne à la plus récente.

    Returns:
        Au plus 10 lacunes `{"type", "nom", "echecs", "essais"}`, triées par échecs
        récents décroissants puis par erreur la plus récente.
    """
    essais: dict[tuple[str, str], list[tuple[int, bool]]] = {}
    for i, h in enumerate(historique):
        correct = bool(h.get("correct", False))
        cles = [("motif", m) for m in h.get("motifs", [])]
        if h.get("section"):
            cles.insert(0, ("section", h["section"]))
        for cle in cles:
            essais.setdefault(cle, []).append((i, correct))

    lacunes: list[tuple[int, int, dict[str, Any]]] = []
    for (type_, nom), liste in essais.items():
        recents = liste[-FENETRE_LACUNES:]
        echecs = [i for i, correct in recents if not correct]
        if echecs:
            entree = {"type": type_, "nom": nom, "echecs": len(echecs), "essais": len(recents)}
            lacunes.append((len(echecs), max(echecs), entree))

    lacunes.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return [entree for _, _, entree in lacunes[:10]]


def enregistrer_reponse(reponse: str, tool_context: ToolContext) -> dict[str, Any]:
    """Enregistre la réponse de l'utilisateur, compare avec la bonne réponse et met à jour l'historique.

    Met à jour dans l'état persistant utilisateur :
    - `user:historique` : 200 derniers résultats avec identifiant, section, motifs et succès.
    - `user:weak_areas` : 10 sections et motifs avec au moins une erreur sur leurs 5 derniers essais,
      ordonnés par échecs récents décroissants.
    - `user:validated_modules` : sections validées (au moins 5 tentatives et 80% de succès sur les 5 dernières).

    Args:
        reponse: Lettre choisie (A à D), ou les 2 lettres choisies pour une question 'Choose two'
            (A à E, par exemple "AC" ou "A, C"). Toutes les bonnes lettres sont exigées.
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

        nb_reponses = int(derniere_question.get("nb_reponses", 1))
        lettres_valides = _LETTRES_PAR_FORMAT.get(nb_reponses, _LETTRES_PAR_FORMAT[1])
        # Accepte "b", "A,C", "a c", "AC" : seules les lettres comptent
        choisies = sorted({c for c in reponse.upper() if c.isalpha()})
        if len(choisies) != nb_reponses or not set(choisies) <= set(lettres_valides):
            attendu = (
                "une lettre parmi A, B, C ou D" if nb_reponses == 1
                else f"{nb_reponses} lettres distinctes parmi {', '.join(lettres_valides)} (Choose two)"
            )
            return {
                "status": "error",
                "message": f"Réponse invalide '{reponse}'. Cette question attend {attendu}.",
            }
        lettre = "".join(choisies)

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

        # 2. Mise à jour de user:weak_areas (Top 10 des faiblesses récentes)
        # Exclut les questions de la série d'échauffement ou marquées non incluses
        historique_calcule = [h for h in historique if h.get("inclus_calcul", True) is not False]
        tool_context.state["user:weak_areas"] = _calculer_lacunes(historique_calcule)

        # 3. Mise à jour de user:validated_modules (>= 5 réponses et >= 80% sur les 5 dernières)
        sections_vues = {h["section"] for h in historique_calcule if "section" in h}
        modules_valides: list[str] = []

        for sec in sorted(sections_vues):
            rep_sec = [h for h in historique_calcule if h.get("section") == sec]
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
