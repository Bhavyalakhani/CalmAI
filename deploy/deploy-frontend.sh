#!/usr/bin/env bash
# deploy frontend to Cloud Run
# usage: ./deploy/deploy-frontend.sh [PROJECT_ID] [REGION]
set -euo pipefail

# load env vars from data-pipeline/.env (finds it relative to project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
for envfile in "${PROJECT_ROOT}/data-pipeline/.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done

PROJECT_ID="${1:-${GCP_PROJECT_ID:?GCP_PROJECT_ID not set}}"
REGION="${2:-us-central1}"
SERVICE_NAME="calmai-frontend"
REPO="calmai-docker"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE_NAME}"

# auto-detect backend URL from the already-deployed backend service
if [[ -z "${BACKEND_URL:-}" ]]; then
    BACKEND_URL=$(gcloud run services describe calmai-backend \
      --project="${PROJECT_ID}" --region="${REGION}" \
      --format='value(status.url)' 2>/dev/null || true)
fi
BACKEND_URL="${BACKEND_URL:?Backend not deployed yet — run deploy-backend.sh first}"

echo "=== Deploying ${SERVICE_NAME} to Cloud Run ==="
echo "Project: ${PROJECT_ID}, Region: ${REGION}"
echo "Backend URL: ${BACKEND_URL}"

# authenticate docker with artifact registry using gcloud token
echo "Authenticating Docker with Artifact Registry..."
gcloud auth print-access-token --project="${PROJECT_ID}" | \
  docker login -u oauth2accesstoken --password-stdin "${REGION}-docker.pkg.dev"

# build and push
echo "Building Docker image..."
docker build \
  --build-arg NEXT_PUBLIC_API_URL="${BACKEND_URL}" \
  -t "${IMAGE}:latest" \
  -f frontend/Dockerfile \
  frontend/

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
  --port=3000 \
  --memory=512Mi \
  --cpu=1 \
  --min-instances=0 \
  --max-instances=3

URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --format='value(status.url)')

echo "=== Frontend deployed ==="
echo "URL: ${URL}"
