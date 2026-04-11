#!/usr/bin/env bash
# GCE VM startup script — runs once at first boot as root
# Installs Docker and configures Artifact Registry auth for the ubuntu user
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

# add ubuntu user to docker group so it can run docker without sudo
usermod -aG docker ubuntu

# configure Artifact Registry auth for the ubuntu user
# (VM has cloud-platform scope so gcloud works without explicit login)
sudo -u ubuntu gcloud auth configure-docker us-central1-docker.pkg.dev --quiet 2>/dev/null || true

# create working directory owned by ubuntu
mkdir -p /home/ubuntu/calmai
chown ubuntu:ubuntu /home/ubuntu/calmai

echo "=== GCE startup complete ==="
