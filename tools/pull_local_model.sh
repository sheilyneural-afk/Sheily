#!/usr/bin/env bash
set -euo pipefail

model_name="${1:-qwen3:8b}"
container_name="sheily-ollama"

if [[ ! "${model_name}" =~ ^[A-Za-z0-9._:/-]+$ ]]; then
  echo "invalid model name" >&2
  exit 2
fi

docker compose -f deploy/local/docker-compose.yml up -d ollama
connected=0
cleanup() {
  if [[ "${connected}" == "1" ]]; then
    docker network disconnect bridge "${container_name}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

if docker network connect bridge "${container_name}" 2>/dev/null; then
  connected=1
fi
docker exec "${container_name}" ollama pull "${model_name}"
echo "model ${model_name} is stored locally; temporary egress has been removed"
