"""Script de préparation des données pour le déploiement.

Copie reference/index.jsonl et les questions.jsonl locales vers paa_coach/data/.
Ce dossier paa_coach/data/ est exclu de Git (.gitignore).
"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def prepare_data() -> None:
    root_dir = Path(__file__).resolve().parent.parent
    ref_dir = root_dir / "reference"
    data_dir = root_dir / "paa_coach" / "data"

    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. Copier index.jsonl
    src_index = ref_dir / "index.jsonl"
    dst_index = data_dir / "index.jsonl"
    if src_index.exists():
        shutil.copy2(src_index, dst_index)
        logger.info("Copié: %s -> %s", src_index, dst_index)
    else:
        logger.warning("Fichier introuvable: %s", src_index)

    # 2. Consolider tous les questions.jsonl trouvés dans reference/local/
    dst_questions = data_dir / "questions.jsonl"
    total_questions = 0
    questions_map: dict[str, dict] = {}

    for q_path in ref_dir.rglob("questions.jsonl"):
        logger.info("Lecture des questions depuis: %s", q_path)
        with open(q_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    q_data = json.loads(line)
                    q_id = q_data.get("id")
                    if q_id:
                        questions_map[q_id] = q_data
                        total_questions += 1
                except json.JSONDecodeError:
                    continue

    if questions_map:
        with open(dst_questions, "w", encoding="utf-8") as out:
            for q_id, q_data in questions_map.items():
                out.write(json.dumps(q_data, ensure_ascii=False) + "\n")
        logger.info(
            "Consolidé %d questions uniques dans %s",
            len(questions_map),
            dst_questions,
        )
    else:
        logger.warning("Aucune question trouvée dans les sous-dossiers de référence.")


if __name__ == "__main__":
    prepare_data()
