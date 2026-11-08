"""CLI pour piloter le mode d'entraînement paa-coach en local.

Permet de :
1. Consulter le statut (historique, lacunes, modules validés).
2. Valider et publier une question générée (contrôles déterministes : anti-copie, équilibre de longueur, remappage A-D, etc.).
3. Enregistrer et noter la réponse d'un candidat avec persistance dans paa_coach_sessions.db.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

# Permettre l'import de paa_coach depuis la racine
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from paa_coach.tools.questions import enregistrer_reponse, valider_et_publier

DB_PATH = Path("paa_coach_sessions.db")
APP_NAME = "paa_coach"
USER_ID = "user"


class MockActions:
    def __init__(self) -> None:
        self.escalate = False


class MockToolContext:
    def __init__(self, state: dict[str, Any]) -> None:
        self.state = state
        self.actions = MockActions()


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_session_and_user(conn: sqlite3.Connection) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Récupère ou initialise la session et l'état utilisateur."""
    # 1. État utilisateur
    cur = conn.cursor()
    cur.execute(
        "SELECT state FROM user_states WHERE app_name = ? AND user_id = ?",
        (APP_NAME, USER_ID),
    )
    row = cur.fetchone()
    if row:
        user_state = json.loads(row["state"])
    else:
        user_state = {"historique": [], "weak_areas": [], "validated_modules": []}
        now = time.time()
        cur.execute(
            "INSERT INTO user_states (app_name, user_id, state, update_time) VALUES (?, ?, ?, ?)",
            (APP_NAME, USER_ID, json.dumps(user_state), now),
        )
        conn.commit()

    # 2. Session courante
    cur.execute(
        "SELECT id, state FROM sessions WHERE app_name = ? AND user_id = ? ORDER BY update_time DESC LIMIT 1",
        (APP_NAME, USER_ID),
    )
    row = cur.fetchone()
    if row:
        session_id = row["id"]
        session_state = json.loads(row["state"])
    else:
        session_id = f"local-session-{int(time.time())}"
        session_state = {"derniere_question": None, "question_publique": None}
        now = time.time()
        cur.execute(
            "INSERT INTO sessions (app_name, user_id, id, state, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?)",
            (APP_NAME, USER_ID, session_id, json.dumps(session_state), now, now),
        )
        conn.commit()

    return session_id, session_state, user_state


def cmd_status() -> None:
    conn = _get_connection()
    try:
        session_id, session_state, user_state = _ensure_session_and_user(conn)
        pending = bool(session_state.get("derniere_question"))
        output = {
            "session_id": session_id,
            "historique_count": len(user_state.get("historique", [])),
            "weak_areas": user_state.get("weak_areas", []),
            "validated_modules": user_state.get("validated_modules", []),
            "has_pending_question": pending,
            "question_publique": session_state.get("question_publique") if pending else None,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    finally:
        conn.close()


def cmd_publish(question_json_str: str) -> None:
    conn = _get_connection()
    try:
        session_id, session_state, user_state = _ensure_session_and_user(conn)
        ctx = MockToolContext(state=dict(session_state))
        ctx.state["user:bonne_plus_longue"] = user_state.get("bonne_plus_longue", [])

        res = valider_et_publier(question_json_str, ctx)
        if res.get("status") == "ok":
            # Sauvegarder dans la session SQLite
            session_state["derniere_question"] = ctx.state["derniere_question"]
            session_state["question_publique"] = ctx.state["question_publique"]
            now = time.time()
            user_state["bonne_plus_longue"] = ctx.state["user:bonne_plus_longue"]
            conn.execute(
                "UPDATE user_states SET state = ?, update_time = ? WHERE app_name = ? AND user_id = ?",
                (json.dumps(user_state), now, APP_NAME, USER_ID),
            )
            conn.execute(
                "UPDATE sessions SET state = ?, update_time = ? WHERE app_name = ? AND user_id = ? AND id = ?",
                (json.dumps(session_state), now, APP_NAME, USER_ID, session_id),
            )
            conn.commit()

        print(json.dumps(res, indent=2, ensure_ascii=False))
    finally:
        conn.close()


def cmd_answer(letter: str) -> None:
    conn = _get_connection()
    try:
        session_id, session_state, user_state = _ensure_session_and_user(conn)
        derniere_q = session_state.get("derniere_question")
        if not derniere_q:
            print(json.dumps({"status": "error", "message": "Aucune question en attente."}, ensure_ascii=False))
            return

        # Préparer le contexte avec le state combiné
        ctx_state = dict(session_state)
        ctx_state["user:historique"] = user_state.get("historique", [])
        ctx_state["user:weak_areas"] = user_state.get("weak_areas", [])
        ctx_state["user:validated_modules"] = user_state.get("validated_modules", [])

        ctx = MockToolContext(state=ctx_state)
        res = enregistrer_reponse(letter, ctx)

        if res.get("status") == "ok":
            # Persister l'état utilisateur mis à jour
            updated_user_state = {
                **user_state,
                "historique": ctx.state.get("user:historique", []),
                "weak_areas": ctx.state.get("user:weak_areas", []),
                "validated_modules": ctx.state.get("user:validated_modules", []),
            }
            now = time.time()
            conn.execute(
                "UPDATE user_states SET state = ?, update_time = ? WHERE app_name = ? AND user_id = ?",
                (json.dumps(updated_user_state), now, APP_NAME, USER_ID),
            )
            # Effacer derniere_question dans la session
            session_state["derniere_question"] = None
            session_state["question_publique"] = None
            conn.execute(
                "UPDATE sessions SET state = ?, update_time = ? WHERE app_name = ? AND user_id = ? AND id = ?",
                (json.dumps(session_state), now, APP_NAME, USER_ID, session_id),
            )
            conn.commit()

            # Ajouter le bilan actualisé au retour
            res["user_weak_areas"] = updated_user_state["weak_areas"]
            res["user_validated_modules"] = updated_user_state["validated_modules"]

        print(json.dumps(res, indent=2, ensure_ascii=False))
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Bridge d'entraînement paa-coach local.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Commande status
    subparsers.add_parser("status", help="Consulter le statut d'avancement")

    # Commande publish
    publish_parser = subparsers.add_parser("publish", help="Valider et publier une question JSON")
    publish_parser.add_argument("--file", type=Path, help="Fichier contenant le JSON")
    publish_parser.add_argument("--json", type=str, help="Chaîne JSON brute")

    # Commande answer
    answer_parser = subparsers.add_parser("answer", help="Enregistrer une réponse")
    answer_parser.add_argument("letter", help="Lettre choisie (A-D), ou 2 lettres pour 'Choose two' (ex. AC)")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status()
    elif args.command == "publish":
        if args.file:
            content = args.file.read_text(encoding="utf-8")
        elif args.json:
            content = args.json
        else:
            print("Erreur: --file ou --json requis", file=sys.stderr)
            sys.exit(1)
        cmd_publish(content)
    elif args.command == "answer":
        cmd_answer(args.letter)


if __name__ == "__main__":
    main()
