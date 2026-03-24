#!/usr/bin/env bash
# provision GCE VM for Airflow data pipeline
# usage: ./deploy/deploy-gce.sh [PROJECT_ID] [REGION] [ZONE]
set -euo pipefail

# load env vars from data-pipeline/.env (finds it relative to project root)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
for envfile in "${PROJECT_ROOT}/data-pipeline/.env" "${PROJECT_ROOT}/.env"; do
    if [[ -f "$envfile" ]]; then set -a; source "$envfile"; set +a; break; fi
done

PROJECT_ID="${1:-${GCP_PROJECT_ID:?GCP_PROJECT_ID not set}}"
REGION="${2:-us-central1}"
ZONE="${3:-${REGION}-a}"
VM_NAME="calmai-airflow"
MACHINE_TYPE="e2-standard-4"

echo "=== Provisioning GCE VM for Airflow ==="
echo "Project: ${PROJECT_ID}, Zone: ${ZONE}, Machine: ${MACHINE_TYPE}"

# create the VM if it doesn't exist
if gcloud compute instances describe "${VM_NAME}" --project="${PROJECT_ID}" --zone="${ZONE}" &>/dev/null; then
  echo "VM '${VM_NAME}' already exists"
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
    --metadata-from-file=startup-script=deploy/gce-startup.sh

  echo "VM created. Waiting for startup script to complete (~3-5 min)..."
  sleep 60
fi

# ensure the calmai directory exists on the VM before copying files
echo "Ensuring /home/${USER:-jaina}/calmai directory exists on VM..."
gcloud compute ssh "${VM_NAME}" \
  --project="${PROJECT_ID}" --zone="${ZONE}" \
  --command="mkdir -p /home/${USER:-jaina}/calmai" \
  --strict-host-key-checking=no

# copy the .env file if it exists
if [ -f "data-pipeline/.env" ]; then
  echo "Copying .env to VM..."
  gcloud compute scp data-pipeline/.env "${VM_NAME}:/home/${USER:-jaina}/calmai/.env" \
    --project="${PROJECT_ID}" --zone="${ZONE}" \
    --strict-host-key-checking=no
fi

# copy GCS key file if it exists
GCS_KEY="${GCS_KEY_FILE:-data-pipeline/calm-ai-bucket-key.json}"
if [ -f "${GCS_KEY}" ]; then
  echo "Copying GCS key to VM..."
  gcloud compute scp "${GCS_KEY}" "${VM_NAME}:/home/${USER:-jaina}/calmai/calm-ai-bucket-key.json" \
    --project="${PROJECT_ID}" --zone="${ZONE}" \
    --strict-host-key-checking=no
fi

echo "=== GCE VM ready ==="
echo "SSH: gcloud compute ssh ${VM_NAME} --project=${PROJECT_ID} --zone=${ZONE}"
echo "Airflow UI: http://$(gcloud compute instances describe ${VM_NAME} --project=${PROJECT_ID} --zone=${ZONE} --format='value(networkInterfaces[0].accessConfigs[0].natIP)'):8080"
