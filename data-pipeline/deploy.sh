#!/usr/bin/env bash
# deploy.sh — one-script GCP deployment for CalmAI data pipeline
#
# Prerequisites:
#   1. gcloud CLI installed and authenticated (gcloud auth login)
#   2. A GCP project with billing enabled
#   3. .env file with GCP_PROJECT_ID set
#
# Usage:
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

# load env vars from .env if present
if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

PROJECT_ID="${GCP_PROJECT_ID:?ERROR: Set GCP_PROJECT_ID in .env or environment}"
REGION="${GCP_REGION:-us-central1}"
REPO_NAME="calmai-docker"
BUCKET_NAME="${MODEL_REGISTRY_BUCKET:-}"

echo "========================================"
echo " CalmAI GCP Deployment"
echo "========================================"
echo " Project:  $PROJECT_ID"
echo " Region:   $REGION"
echo " Repo:     $REPO_NAME"
echo " Bucket:   ${BUCKET_NAME:-<not set>}"
echo "========================================"
echo ""

# 1. set project
gcloud config set project "$PROJECT_ID"

# 2. enable required APIs
echo "[1/6] Enabling GCP APIs..."
gcloud services enable \
    artifactregistry.googleapis.com \
    cloudbuild.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com \
    run.googleapis.com \
    compute.googleapis.com \
    --quiet

# 3. create artifact registry docker repo (idempotent)
echo "[2/6] Creating Artifact Registry repo..."
if ! gcloud artifacts repositories describe "$REPO_NAME" \
    --location="$REGION" --format="value(name)" 2>/dev/null; then
    gcloud artifacts repositories create "$REPO_NAME" \
        --repository-format=docker \
        --location="$REGION" \
        --description="CalmAI Docker images"
    echo "  Created: $REPO_NAME"
else
    echo "  Already exists: $REPO_NAME"
fi

# 4. configure docker auth for artifact registry
echo "[3/6] Configuring Docker auth..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# 5. create GCS bucket for model artifacts (if configured)
if [[ -n "$BUCKET_NAME" ]]; then
    echo "[4/6] Creating GCS bucket..."
    if ! gsutil ls "gs://$BUCKET_NAME" 2>/dev/null; then
        gsutil mb -l "$REGION" "gs://$BUCKET_NAME"
        echo "  Created: gs://$BUCKET_NAME"
    else
        echo "  Already exists: gs://$BUCKET_NAME"
    fi
else
    echo "[4/6] Skipping GCS bucket (MODEL_REGISTRY_BUCKET not set)"
fi

# 6. create firewall rule for airflow UI (idempotent)
echo "[5/6] Creating firewall rule for Airflow UI..."
if ! gcloud compute firewall-rules describe allow-airflow-ui --format="value(name)" 2>/dev/null; then
    gcloud compute firewall-rules create allow-airflow-ui \
        --direction=INGRESS \
        --action=ALLOW \
        --rules=tcp:8080 \
        --target-tags=airflow \
        --source-ranges=0.0.0.0/0 \
        --description="Allow Airflow web UI access on port 8080" \
        --quiet
    echo "  Created: allow-airflow-ui"
else
    echo "  Already exists: allow-airflow-ui"
fi

# 7. submit cloud build
TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "manual")
echo "[6/6] Submitting Cloud Build (tag: $TAG)..."
gcloud builds submit \
    --config cloudbuild.yaml \
    --substitutions="_REGION=$REGION,_REPO=$REPO_NAME,_TAG=$TAG" \
    .

echo ""
echo "========================================"
echo " Deployment Complete"
echo "========================================"
echo ""
echo "Docker image pushed to:"
echo "  ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/calmai-airflow:latest"
echo ""
echo "Next steps (run from project root):"
echo "  1. Deploy backend:   ./deploy/deploy-backend.sh"
echo "  2. Deploy frontend:  BACKEND_URL=<backend-url> ./deploy/deploy-frontend.sh"
echo "  3. Deploy GCE VM:    ./deploy/deploy-gce.sh"
echo "  4. Deploy embedding: EMBEDDING_MODEL=jainam02/qwen3-8b-mh-st3-merged ./deploy/deploy-embedding-endpoint.sh up"
echo ""
