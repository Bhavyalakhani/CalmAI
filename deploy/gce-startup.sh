#!/usr/bin/env bash
# GCE VM startup script — installs Docker and pulls the Airflow pipeline
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# install docker
if ! command -v docker &>/dev/null; then
  apt-get update -qq
  apt-get install -y -qq apt-transport-https ca-certificates curl gnupg lsb-release
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
  systemctl enable docker
  systemctl start docker
fi

# allow the default user to run docker
usermod -aG docker "$(logname 2>/dev/null || echo ubuntu)" || true

# authenticate to Artifact Registry
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet 2>/dev/null || true

# create working directory
WORK_DIR="/home/$(logname 2>/dev/null || echo ubuntu)/calmai"
mkdir -p "${WORK_DIR}"

echo "=== GCE startup complete ==="
echo "Next: clone repo or copy docker-compose.yaml + .env to ${WORK_DIR}, then run:"
echo "  cd ${WORK_DIR} && docker compose up -d"
