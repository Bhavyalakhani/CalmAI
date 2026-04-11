#!/usr/bin/env bash
# deploy/undeploy the Qwen embedding model on Vertex AI Online Prediction Endpoint
# usage:
#   ./deploy/deploy-embedding-endpoint.sh up   [PROJECT_ID] [REGION]               # build, push, deploy
#   ./deploy/deploy-embedding-endpoint.sh up   [PROJECT_ID] [REGION] --no-build    # skip build/push (image already in registry)
#   ./deploy/deploy-embedding-endpoint.sh down  [PROJECT_ID] [REGION]              # undeploy (stops GPU billing)
set -euo pipefail

# load env vars from data-pipeline/.env (finds it relative to project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
for envfile in "${PROJECT_ROOT}/data-pipeline/.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done

ACTION="${1:?Usage: $0 up|down [PROJECT_ID] [REGION] [--no-build]}"
PROJECT_ID="${2:-${GCP_PROJECT_ID:?GCP_PROJECT_ID not set}}"
REGION="${3:-us-central1}"
SKIP_BUILD=false
for arg in "$@"; do
  if [[ "$arg" == "--no-build" ]]; then SKIP_BUILD=true; fi
done
REPO="calmai-docker"
IMAGE_NAME="calmai-embedding-server"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${IMAGE_NAME}"
ENDPOINT_NAME="calmai-embedding-endpoint"
MODEL_NAME="calmai-qwen-embedding"
EMBEDDING_MODEL="${EMBEDDING_MODEL:-sentence-transformers/all-MiniLM-L6-v2}"

case "${ACTION}" in
  up)
    echo "=== Deploying embedding endpoint ==="
    echo "Project: ${PROJECT_ID}, Region: ${REGION}"
    echo "Model: ${EMBEDDING_MODEL}"

    if [ "${SKIP_BUILD}" = false ]; then
      # authenticate docker with artifact registry
      echo "Authenticating Docker with Artifact Registry..."
      gcloud auth print-access-token --project="${PROJECT_ID}" | \
        docker login -u oauth2accesstoken --password-stdin "${REGION}-docker.pkg.dev"

      # 1. build and push the serving container
      echo "Building embedding server image..."
      docker build \
        --build-arg EMBEDDING_MODEL="${EMBEDDING_MODEL}" \
        -t "${IMAGE}:latest" \
        -f "${SCRIPT_DIR}/embedding_server/Dockerfile" \
        "${SCRIPT_DIR}/embedding_server/"

      echo "Pushing to Artifact Registry..."
      docker push "${IMAGE}:latest"
    else
      echo "Skipping build/push (--no-build flag set)"
      echo "Assuming image already exists: ${IMAGE}:latest"
    fi

    # 2. upload model to Vertex AI Model Registry (with custom container)
    echo "Registering model in Vertex AI..."
    MODEL_ID=$(gcloud ai models upload \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --display-name="${MODEL_NAME}" \
      --container-image-uri="${IMAGE}:latest" \
      --container-ports=8080 \
      --container-health-route="/health" \
      --container-predict-route="/embed" \
      --format='value(name)' 2>/dev/null) || true

    if [ -z "${MODEL_ID}" ]; then
      # model may already exist — find the latest version
      MODEL_ID=$(gcloud ai models list \
        --project="${PROJECT_ID}" \
        --region="${REGION}" \
        --filter="displayName=${MODEL_NAME}" \
        --sort-by=~createTime \
        --limit=1 \
        --format='value(name)')
    fi
    echo "Model: ${MODEL_ID}"

    # 3. create endpoint if it doesn't exist
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

    # 4. deploy model to endpoint on L4 GPU
    echo "Deploying model to endpoint (L4 GPU)..."
    gcloud ai endpoints deploy-model "${ENDPOINT_ID}" \
      --project="${PROJECT_ID}" \
      --region="${REGION}" \
      --model="${MODEL_ID}" \
      --display-name="${MODEL_NAME}-deployed" \
      --machine-type=g2-standard-8 \
      --accelerator=type=nvidia-l4,count=1 \
      --min-replica-count=1 \
      --max-replica-count=1

    echo "=== Embedding endpoint deployed ==="
    echo "Endpoint ID: ${ENDPOINT_ID}"
    echo ""
    echo "Set these env vars on your VM and backend:"
    echo "  USE_EMBEDDING_SERVICE=true"
    echo "  EMBEDDING_SERVICE_URL=${ENDPOINT_ID}"
    echo "  EMBEDDING_DIM=4096"
    echo ""
    echo "IMPORTANT: Run '$0 down' when done testing to stop GPU billing (~\$0.90/hr)"
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

    # get deployed model ID
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
    echo "Endpoint preserved (no cost when no models deployed)"
    echo "Run '$0 up' to redeploy when needed"
    ;;

  *)
    echo "Usage: $0 up|down [PROJECT_ID] [REGION]"
    exit 1
    ;;
esac
