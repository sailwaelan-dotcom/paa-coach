#!/usr/bin/env bash
# ==============================================================================
# deploy.sh — Déploiement de paa-coach sur Google Cloud Run avec IAP et Traces
# ==============================================================================
# 1. Prépare les données locales (prepare_data.py)
# 2. Déploie via 'adk deploy cloud_run' avec Web UI, télémétrie OTel et compte SA
# 3. Restreint l'accès via IAP (Identity-Aware Proxy) au seul utilisateur autorisé
# ==============================================================================

set -euo pipefail

# 1. Charger la configuration .env si disponible
if [[ -f .env ]]; then
    echo "Chargement de .env..."
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
    echo "ERREUR: GOOGLE_CLOUD_PROJECT n'est pas défini." >&2
    exit 1
fi

CLOUD_RUN_REGION="${CLOUD_RUN_REGION:-europe-west1}"
VERTEX_LOCATION="${GOOGLE_CLOUD_LOCATION:-global}"
SERVICE_NAME="paa-coach"
APP_NAME="paa_coach"
SA_EMAIL="paa-coach-run@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"
MODEL_NAME="${PAA_MODEL:-gemini-3.5-flash}"

echo "=== Déploiement de paa-coach sur Cloud Run ==="
echo "Projet         : ${GOOGLE_CLOUD_PROJECT}"
echo "Région Run     : ${CLOUD_RUN_REGION}"
echo "Région Vertex  : ${VERTEX_LOCATION}"
echo "Service        : ${SERVICE_NAME}"
echo "Modèle         : ${MODEL_NAME}"
echo "Compte SA      : ${SA_EMAIL}"
echo "=============================================="

# 2. Préparation des données d'index et de questions
echo ""
echo "-> Étape 1 : Préparation des données (scripts/prepare_data.py)..."
python scripts/prepare_data.py

# 3. Assembler les options d'environnement ADK
ADK_ENV_ARGS=(
    "--env" "PAA_MODEL=${MODEL_NAME}"
    "--env" "GOOGLE_CLOUD_PROJECT=${GOOGLE_CLOUD_PROJECT}"
    "--env" "GOOGLE_CLOUD_LOCATION=${VERTEX_LOCATION}"
    "--env" "GOOGLE_GENAI_USE_VERTEXAI=TRUE"
)

if [[ -n "${PAA_MODEL_ARMOR_PROMPT_TEMPLATE:-}" ]]; then
    ADK_ENV_ARGS+=("--env" "PAA_MODEL_ARMOR_PROMPT_TEMPLATE=${PAA_MODEL_ARMOR_PROMPT_TEMPLATE}")
fi

if [[ -n "${PAA_MODEL_ARMOR_RESPONSE_TEMPLATE:-}" ]]; then
    ADK_ENV_ARGS+=("--env" "PAA_MODEL_ARMOR_RESPONSE_TEMPLATE=${PAA_MODEL_ARMOR_RESPONSE_TEMPLATE}")
fi

if [[ -n "${DEVELOPER_KNOWLEDGE_API_KEY:-}" ]]; then
    ADK_ENV_ARGS+=("--env" "DEVELOPER_KNOWLEDGE_API_KEY=${DEVELOPER_KNOWLEDGE_API_KEY}")
fi

# 4. Déploiement via ADK CLI
echo ""
echo "-> Étape 2 : Déploiement Cloud Run via adk deploy cloud_run..."
adk deploy cloud_run \
    --project="${GOOGLE_CLOUD_PROJECT}" \
    --region="${CLOUD_RUN_REGION}" \
    --service_name="${SERVICE_NAME}" \
    --app_name="${APP_NAME}" \
    --with_ui \
    --otel_to_cloud \
    "${ADK_ENV_ARGS[@]}" \
    ./paa_coach \
    -- \
    --quiet \
    --no-allow-unauthenticated \
    --service-account="${SA_EMAIL}" \
    --max-instances=1 \
    --timeout=300

# 5. Activation d'IAP et autorisations d'accès
echo ""
echo "-> Étape 3 : Activation d'IAP et autorisations d'accès..."
echo "  - Activation d'IAP sur le service Cloud Run..."
gcloud run services update "${SERVICE_NAME}" \
    --project="${GOOGLE_CLOUD_PROJECT}" \
    --region="${CLOUD_RUN_REGION}" \
    --iap \
    --quiet >/dev/null

PROJECT_NUMBER=$(gcloud projects describe "${GOOGLE_CLOUD_PROJECT}" --format="value(projectNumber)")
IAP_SA="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"

# L'agent de service IAP doit pouvoir invoquer Cloud Run
echo "  - Attribution du rôle roles/run.invoker à l'agent de service IAP..."
gcloud run services add-iam-policy-binding "${SERVICE_NAME}" \
    --project="${GOOGLE_CLOUD_PROJECT}" \
    --region="${CLOUD_RUN_REGION}" \
    --member="${IAP_SA}" \
    --role="roles/run.invoker" \
    --quiet >/dev/null

# L'utilisateur autorisé reçoit l'accès IAP (politique IAP, pas celle du service Cloud Run)
if [[ -n "${PAA_ALLOWED_MEMBER:-}" ]]; then
    echo "  - Attribution de roles/iap.httpsResourceAccessor à ${PAA_ALLOWED_MEMBER}..."
    gcloud iap web add-iam-policy-binding \
        --project="${GOOGLE_CLOUD_PROJECT}" \
        --resource-type=cloud-run \
        --service="${SERVICE_NAME}" \
        --region="${CLOUD_RUN_REGION}" \
        --member="${PAA_ALLOWED_MEMBER}" \
        --role="roles/iap.httpsResourceAccessor" \
        --quiet >/dev/null
else
    echo "AVERTISSEMENT: PAA_ALLOWED_MEMBER n'est pas défini dans .env."
    echo "Vous devez accorder le rôle roles/iap.httpsResourceAccessor manuellement à votre compte Google."
fi

# 6. Affichage de l'URL finale et des consignes de vérification
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --project="${GOOGLE_CLOUD_PROJECT}" \
    --region="${CLOUD_RUN_REGION}" \
    --format="value(status.url)")

echo ""
echo "================================================================================"
echo "DÉPLOIEMENT TERMINÉ AVEC SUCCÈS !"
echo "================================================================================"
echo "URL du service Cloud Run : ${SERVICE_URL}"
echo ""
echo "Procédure de test de sécurité (Critère 4) :"
echo "1. Accès refusé pour les utilisateurs anonymes :"
echo "   curl -I ${SERVICE_URL}"
echo "   -> Doit renvoyer HTTP 302 (redirection vers la connexion Google par IAP)."
echo ""
echo "2. Accès nominal pour Souhail :"
echo "   Ouvrez ${SERVICE_URL} dans votre navigateur connecté avec ${PAA_ALLOWED_MEMBER:-votre compte Google autorisé}."
echo "   -> L'interface ADK Web UI doit s'afficher après authentification Google."
echo ""
echo "3. Vérification des traces :"
echo "   Après une interaction dans l'UI, consultez la console Google Cloud :"
echo "   Opérations > Cloud Trace > Explorateur de traces"
echo "   -> Les spans d'exécution ADK et les appels Vertex AI doivent apparaître."
echo "================================================================================"
