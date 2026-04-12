#!/usr/bin/env bash
# provision GCE VM and deploy Airflow — manual equivalent of the deploy-vm CI job
# usage: ./deploy/deploy-vm.sh [PROJECT_ID] [REGION] [ZONE]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
for envfile in "${PROJECT_ROOT}/data-pipeline/.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done

PROJECT_ID="${1:-${GCP_PROJECT_ID:?GCP_PROJECT_ID not set}}"
REGION="${2:-${GCP_REGION:-us-central1}}"
ZONE="${3:-${REGION}-a}"
VM_NAME="calmai-airflow"
MACHINE_TYPE="e2-standard-4"
REPO_NAME="calmai-docker"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/calmai-airflow:latest"

echo "=== Provisioning GCE VM for Airflow ==="
echo "Project: ${PROJECT_ID}, Zone: ${ZONE}, Machine: ${MACHINE_TYPE}"

# create VM if it doesn't exist
if gcloud compute instances describe "${VM_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" &>/dev/null; then
  echo "VM '${VM_NAME}' already exists — ensuring it is running..."
  gcloud compute instances start "${VM_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" --quiet 2>/dev/null || true
else
  echo "Creating VM..."
  gcloud compute instances create "${VM_NAME}" \
    --project="${PROJECT_ID}" \
    --zone="${ZONE}" \
    --machine-type="${MACHINE_TYPE}" \
    --boot-disk-size=100GB \
    --boot-disk-type=pd-balanced \
    --image-family=ubuntu-2204-lts \
    --image-project=ubuntu-os-cloud \
    --scopes=cloud-platform \
    --tags=airflow \
    --metadata-from-file=startup-script="${SCRIPT_DIR}/vm-startup.sh"

  echo "VM created. Waiting for startup script (~3 min)..."
  sleep 180
fi

# ensure working directory exists
gcloud compute ssh "${VM_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --command="mkdir -p /home/ubuntu/calmai" \
  --strict-host-key-checking=no --quiet

# copy docker-compose.yaml
echo "Copying docker-compose.yaml to VM..."
gcloud compute scp "${PROJECT_ROOT}/data-pipeline/docker-compose.yaml" \
  "${VM_NAME}:/home/ubuntu/calmai/docker-compose.yaml" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --strict-host-key-checking=no --quiet

# copy .env
if [[ -f "${PROJECT_ROOT}/data-pipeline/.env" ]]; then
  echo "Copying .env to VM..."

  # inject AIRFLOW_IMAGE_NAME so docker compose pulls from Artifact Registry (not local build)
  cp "${PROJECT_ROOT}/data-pipeline/.env" /tmp/calmai-vm.env
  if ! grep -q "^AIRFLOW_IMAGE_NAME=" /tmp/calmai-vm.env; then
    echo "AIRFLOW_IMAGE_NAME=${IMAGE}" >> /tmp/calmai-vm.env
  fi

  gcloud compute scp /tmp/calmai-vm.env "${VM_NAME}:/home/ubuntu/calmai/.env" \
    --project="${PROJECT_ID}" --zone="${ZONE}" \
    --strict-host-key-checking=no --quiet
  rm /tmp/calmai-vm.env
fi

# copy GCS key
GCS_KEY="${GCS_KEY_FILE:-${PROJECT_ROOT}/data-pipeline/calm-ai-bucket-key.json}"
if [[ -f "${GCS_KEY}" ]]; then
  echo "Copying GCS key to VM..."
  gcloud compute scp "${GCS_KEY}" "${VM_NAME}:/home/ubuntu/calmai/calm-ai-bucket-key.json" \
    --project="${PROJECT_ID}" --zone="${ZONE}" \
    --strict-host-key-checking=no --quiet
fi

# configure docker auth and start Airflow
echo "Starting Airflow on VM..."
gcloud compute ssh "${VM_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --strict-host-key-checking=no \
  --command="
    set -e
    gcloud auth configure-docker ${REGION}-docker.pkg.dev --quiet
    cd ~/calmai
    sudo docker compose pull
    sudo docker compose up airflow-init --exit-code-from airflow-init 2>/dev/null || true
    sudo docker compose up -d --remove-orphans
    echo '=== Airflow services ==='
    sudo docker compose ps
  " \
  --quiet

VM_IP=$(gcloud compute instances describe "${VM_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)')

echo ""
echo "=== GCE VM ready ==="
echo "Airflow UI: http://${VM_IP}:8080  (admin / airflow)"
echo "SSH:        gcloud compute ssh ${VM_NAME} --project=${PROJECT_ID} --zone=${ZONE}"
