#!/usr/bin/env bash
# deploy/undeploy the embedding model on Vertex AI Online Prediction Endpoint
# image must already be in Artifact Registry (built and pushed by CI deploy.yml)
#
# usage:
#   ./deploy/deploy-embedding-endpoint.sh up   [PROJECT_ID] [REGION]
#   ./deploy/deploy-embedding-endpoint.sh down [PROJECT_ID] [REGION]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
for envfile in "${PROJECT_ROOT}/data-pipeline/.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done

ACTION="${1:?Usage: $0 up|down [PROJECT_ID] [REGION]}"
PROJECT_ID="${2:-${GCP_PROJECT_ID:?GCP_PROJECT_ID not set}}"
REGION="${3:-${GCP_REGION:-us-central1}}"
REPO="calmai-docker"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/calmai-embedding-server:latest"
ENDPOINT_NAME="calmai-embedding-endpoint"
MODEL_NAME="calmai-qwen-embedding"

case "${ACTION}" in
  up)
    echo "=== Deploying embedding endpoint ==="
    echo "Project: ${PROJECT_ID}, Region: ${REGION}"
    echo "Image: ${IMAGE}"

    # 1. register model in Vertex AI Model Registry
    echo "Registering model in Vertex AI..."
    MODEL_ID=$(gcloud ai models upload \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --display-name="${MODEL_NAME}" \
      --container-image-uri="${IMAGE}" \
      --container-ports=8080 \
      --container-health-route="/health" \
      --container-predict-route="/embed" \
      --format='value(name)' 2>/dev/null) || true

    if [ -z "${MODEL_ID}" ]; then
      # already registered — reuse latest version
      MODEL_ID=$(gcloud ai models list \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --filter="displayName=${MODEL_NAME}" \
        --sort-by=~createTime \
        --limit=1 \
        --format='value(name)')
    fi
    echo "Model: ${MODEL_ID}"

    # 2. create endpoint if it doesn't exist
    ENDPOINT_ID=$(gcloud ai endpoints list \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --filter="displayName=${ENDPOINT_NAME}" \
      --limit=1 \
      --format='value(name)' 2>/dev/null) || true

    if [ -z "${ENDPOINT_ID}" ]; then
      echo "Creating endpoint..."
      ENDPOINT_ID=$(gcloud ai endpoints create \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --display-name="${ENDPOINT_NAME}" \
        --format='value(name)')
    fi
    echo "Endpoint: ${ENDPOINT_ID}"

    # 3. deploy model to endpoint on L4 GPU
    echo "Deploying model to endpoint (L4 GPU — billing starts now)..."
    gcloud ai endpoints deploy-model "${ENDPOINT_ID}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --model="${MODEL_ID}" \
      --display-name="${MODEL_NAME}-deployed" \
      --machine-type=g2-standard-8 \
      --accelerator=type=nvidia-l4,count=1 \
      --min-replica-count=1 \
      --max-replica-count=1

    echo ""
    echo "=== Embedding endpoint deployed ==="
    echo "Endpoint ID: ${ENDPOINT_ID}"
    echo ""
    echo "Set these on your backend and VM .env:"
    echo "  USE_EMBEDDING_SERVICE=true"
    echo "  EMBEDDING_SERVICE_URL=${ENDPOINT_ID}"
    echo "  EMBEDDING_DIM=4096"
    echo ""
    echo "IMPORTANT: Run '$0 down' when done to stop GPU billing (~\$0.90/hr)"
    ;;

  down)
    echo "=== Undeploying embedding endpoint ==="

    ENDPOINT_ID=$(gcloud ai endpoints list \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --filter="displayName=${ENDPOINT_NAME}" \
      --limit=1 \
      --format='value(name)' 2>/dev/null) || true

    if [ -z "${ENDPOINT_ID}" ]; then
      echo "No endpoint found with name '${ENDPOINT_NAME}'"
      exit 0
    fi

    DEPLOYED_MODEL_ID=$(gcloud ai endpoints describe "${ENDPOINT_ID}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --format='value(deployedModels[0].id)' 2>/dev/null) || true

    if [ -n "${DEPLOYED_MODEL_ID}" ]; then
      echo "Undeploying model ${DEPLOYED_MODEL_ID}..."
      gcloud ai endpoints undeploy-model "${ENDPOINT_ID}" \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --deployed-model-id="${DEPLOYED_MODEL_ID}"
      echo "Model undeployed — GPU billing stopped"
    else
      echo "No models currently deployed on endpoint"
    fi

    echo "=== Embedding endpoint stopped ==="
    echo "Endpoint preserved. Run '$0 up' to redeploy when needed."
    ;;

  *)
    echo "Usage: $0 up|down [PROJECT_ID] [REGION]"
    exit 1
    ;;
esac
