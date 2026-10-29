#!/usr/bin/env bash
# ==============================================================================
# setup_gcp.sh — Préparation idempotente de l'environnement Google Cloud
# ==============================================================================
# Configure les API nécessaires, le compte de service dédié à moindre privilège
# paa-coach-run et ses rôles IAM, et amorce la configuration Model Armor et IAP.
# ==============================================================================

set -euo pipefail

# 1. Charger les variables d'environnement depuis .env si présent
if [[ -f .env ]]; then
    echo "Chargement de la configuration depuis .env..."
    # Exporter les variables non commentées de .env
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
    echo "ERREUR: GOOGLE_CLOUD_PROJECT n'est pas défini dans l'environnement ni dans .env" >&2
    exit 1
fi

LOCATION="${GOOGLE_CLOUD_LOCATION:-europe-west1}"
SA_NAME="paa-coach-run"
SA_EMAIL="${SA_NAME}@${GOOGLE_CLOUD_PROJECT}.iam.gserviceaccount.com"

echo "=== Préparation Google Cloud pour paa-coach ==="
echo "Projet   : ${GOOGLE_CLOUD_PROJECT}"
echo "Région   : ${LOCATION}"
echo "Compte SA: ${SA_EMAIL}"
echo "==============================================="

# 2. Activation des APIs Google Cloud requises
echo ""
echo "-> Activation des API Google Cloud requises..."
APIS=(
    "run.googleapis.com"
    "cloudbuild.googleapis.com"
    "artifactregistry.googleapis.com"
    "aiplatform.googleapis.com"
    "modelarmor.googleapis.com"
    "iap.googleapis.com"
    "cloudtrace.googleapis.com"
    "logging.googleapis.com"
    "developerknowledge.googleapis.com"
)

gcloud services enable "${APIS[@]}" --project="${GOOGLE_CLOUD_PROJECT}"

# 3. Création du compte de service dédié (moindre privilège)
echo ""
echo "-> Vérification / Création du compte de service ${SA_NAME}..."
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${GOOGLE_CLOUD_PROJECT}" &>/dev/null; then
    gcloud iam service-accounts create "${SA_NAME}" \
        --project="${GOOGLE_CLOUD_PROJECT}" \
        --display-name="Compte de service Cloud Run pour paa-coach" \
        --description="Exécution de paa-coach avec accès restreint à Vertex AI, Model Armor et Trace"
    echo "Compte de service ${SA_EMAIL} créé."
else
    echo "Le compte de service ${SA_EMAIL} existe déjà."
fi

# 4. Attribution des rôles IAM stricts (moindre privilège)
echo ""
echo "-> Attribution des rôles IAM minimaux au compte de service..."
ROLES=(
    "roles/aiplatform.user"       # Inférence Vertex AI (Gemini Flash)
    "roles/modelarmor.user"       # Filtrage des prompts et réponses Model Armor
    "roles/logging.logWriter"     # Écriture des journaux Cloud Logging
    "roles/cloudtrace.agent"      # Envoi des traces distribuées OpenTelemetry
)

for role in "${ROLES[@]}"; do
    echo "  - Attribution de ${role}..."
    gcloud projects add-iam-policy-binding "${GOOGLE_CLOUD_PROJECT}" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="${role}" \
        --condition=None \
        --quiet >/dev/null
done

# 5. Obtention du numéro de projet pour l'agent de service IAP
echo ""
echo "-> Configuration de l'agent de service IAP..."
PROJECT_NUMBER=$(gcloud projects describe "${GOOGLE_CLOUD_PROJECT}" --format="value(projectNumber)")
IAP_SA="service-${PROJECT_NUMBER}@gcp-sa-iap.iam.gserviceaccount.com"
echo "Numéro de projet : ${PROJECT_NUMBER}"
echo "Agent de service IAP : ${IAP_SA}"

# 6. Modèles Model Armor (Templates)
echo ""
echo "-> Modèles Model Armor :"
echo "Pour créer les templates de filtrage Model Armor dans la région ${LOCATION} :"
echo "1. Dans la console Google Cloud : Sécurité > Model Armor > Modèles (Templates) > Créer"
echo "   - Template prompt   : 'paa-prompt-filter' (filtres: Injection de prompt, CSAM, Toxicité)"
echo "   - Template réponse  : 'paa-response-filter' (filtres: Fuite de données sensibles / PII)"
echo "   Notez les chemins générés : projects/${GOOGLE_CLOUD_PROJECT}/locations/${LOCATION}/templates/<nom>"
echo "   Renseignez-les dans votre .env : PAA_MODEL_ARMOR_PROMPT_TEMPLATE et PAA_MODEL_ARMOR_RESPONSE_TEMPLATE"

# 7. Résumé des étapes manuelles indispensables
echo ""
echo "================================================================================"
echo "ACTIONS MANUELLES À EFFECTUER SUR GOOGLE CLOUD PAR SOUHAIL :"
echo "================================================================================"
echo "1. Activation d'IAP (Identity-Aware Proxy) pour compte personnel :"
echo "   - Rendez-vous sur la console Google Cloud : Sécurité > Identity-Aware Proxy."
echo "   - Si ce n'est pas fait, configurez l'écran de consentement OAuth (Type Externe pour un compte @gmail.com personnel, ajoutez votre email en Utilisateur test)."
echo "   - Activez la bascule IAP sur le service Cloud Run après son premier déploiement."
echo ""
echo "2. Alerte de budget Google Cloud :"
echo "   - Facturation > Gestion des budgets et alertes > Créer un budget."
echo "   - Nom : 'Alerte paa-coach' | Montant cible : ${PAA_BUDGET_EUR:-20} EUR."
echo "   - Seuils : 50%, 90%, 100% avec notification email."
echo "================================================================================"
echo "Configuration Google Cloud terminée avec succès."
