#!/usr/bin/env bash
# deploy backend to Cloud Run
# usage: ./deploy/deploy-backend.sh [PROJECT_ID] [REGION]
set -euo pipefail

# load env vars from data-pipeline/.env (finds it relative to project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
for envfile in "${PROJECT_ROOT}/data-pipeline/.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done

PROJECT_ID="${1:-${GCP_PROJECT_ID:?GCP_PROJECT_ID not set}}"
REGION="${2:-us-central1}"
SERVICE_NAME="calmai-backend"
REPO="calmai-docker"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"

echo "=== Deploying ${SERVICE_NAME} to Cloud Run ==="
echo "Project: ${PROJECT_ID}, Region: ${REGION}"

# authenticate docker with artifact registry using gcloud token
echo "Authenticating Docker with Artifact Registry..."
gcloud auth print-access-token --project="${PROJECT_ID}" | \
  docker login -u oauth2accesstoken --password-stdin "${REGION}-docker.pkg.dev"

# build and push
echo "Building Docker image..."
docker build \
  -t "${IMAGE}:latest" \
  -f backend/Dockerfile \
  backend/

echo "Pushing to Artifact Registry..."
docker push "${IMAGE}:latest"

# deploy to cloud run
echo "Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --image="${IMAGE}:latest" \
  --platform=managed \
  --allow-unauthenticated \
  --port=8000 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=5 \
  --set-env-vars="MONGODB_URI=${MONGODB_URI:-}" \
  --set-env-vars="MONGODB_DATABASE=${MONGODB_DATABASE:-calm_ai}" \
  --set-env-vars="GEMINI_API_KEY=${GEMINI_API_KEY:-}" \
  --set-env-vars="GEMINI_MODEL=${GEMINI_MODEL:-gemini-2.5-flash}" \
  --set-env-vars="JWT_SECRET=${JWT_SECRET:-}" \
  --set-env-vars="FRONTEND_URL=${FRONTEND_URL:-*}" \
  --set-env-vars="USE_EMBEDDING_SERVICE=${USE_EMBEDDING_SERVICE:-false}" \
  --set-env-vars="EMBEDDING_SERVICE_URL=${EMBEDDING_SERVICE_URL:-}" \
  --set-env-vars="EMBEDDING_DIM=${EMBEDDING_DIM:-384}"

URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)')

echo "=== Backend deployed ==="
echo "URL: ${URL}"
echo "Health: ${URL}/health"
