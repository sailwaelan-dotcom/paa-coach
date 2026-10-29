#!/usr/bin/env bash
# ==============================================================================
# run_evals.sh — Évaluation des agents paa-coach avec adk eval (appels Vertex AI)
# ==============================================================================
# 1. trajectoires : routage et appels d'outils attendus (tool_trajectory_avg_score)
# 2. qualite      : règles pédagogiques et de sécurité, notées par Gemini juge
#                   (rubric_based_final_response_quality_v1)
#
# Model Armor est désactivé ici : son client gRPC se lie à la première boucle
# asyncio, et adk eval en change entre les cas, ce qui fait échouer le filtrage
# et bloquer toutes les réponses (block_on_screening_failure). Model Armor est
# vérifié séparément, par appel direct à l'API.
# ==============================================================================

set -euo pipefail

if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi
unset PAA_MODEL_ARMOR_PROMPT_TEMPLATE PAA_MODEL_ARMOR_RESPONSE_TEMPLATE
# Sinon adk recharge .env (override=True) et réactive Model Armor
export ADK_DISABLE_LOAD_DOTENV=1

for evalset in trajectoires qualite; do
    echo "=== Évaluation : ${evalset} ==="
    adk eval paa_coach "evals/${evalset}.evalset.json" \
        --config_file_path "evals/${evalset}.config.json" \
        --print_detailed_results
done
