#!/usr/bin/env bash
set -euo pipefail

model_name="${1:-qwen3:8b}"
container_name="sheily-ollama"

if [[ ! "${model_name}" =~ ^[A-Za-z0-9._:/-]+$ ]]; then
  echo "invalid model name" >&2
  exit 2
fi

docker compose -f deploy/local/docker-compose.yml up -d ollama
network_names="$(
  docker inspect "${container_name}" \
    --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}} {{end}}'
)"
read -r model_network extra_network <<<"${network_names}"
if [[ -z "${model_network}" || -n "${extra_network}" ]]; then
  echo "ollama must start on exactly one private network" >&2
  exit 1
fi
if [[ "$(docker network inspect "${model_network}" --format '{{.Internal}}')" != "true" ]]; then
  echo "ollama model network is not internal" >&2
  exit 1
fi
bridge_connected=0
model_disconnected=0
cleanup() {
  local cleanup_status=0
  if [[ "${bridge_connected}" == "1" ]]; then
    if docker network disconnect bridge "${container_name}" >/dev/null 2>&1; then
      bridge_connected=0
    else
      cleanup_status=1
    fi
  fi
  if [[ "${model_disconnected}" == "1" ]]; then
    if docker network connect --alias ollama "${model_network}" "${container_name}" \
      >/dev/null 2>&1; then
      model_disconnected=0
    else
      cleanup_status=1
    fi
  fi
  return "${cleanup_status}"
}
cleanup_on_exit() {
  local original_status=$?
  local cleanup_status=0
  set +e
  cleanup
  cleanup_status=$?
  trap - EXIT
  if [[ "${original_status}" != "0" ]]; then
    exit "${original_status}"
  fi
  exit "${cleanup_status}"
}
trap cleanup_on_exit EXIT

docker network disconnect "${model_network}" "${container_name}"
model_disconnected=1
docker network connect bridge "${container_name}"
bridge_connected=1
docker exec "${container_name}" ollama pull "${model_name}"
cleanup
trap - EXIT
echo "model ${model_name} is stored locally; temporary egress has been removed"
