#!/usr/bin/env bash
# Start the local web application from a Linux/WSL checkout.
set -euo pipefail

repo_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_dir"
unset DOCKER_CONTEXT DOCKER_TLS_VERIFY DOCKER_CERT_PATH
export DOCKER_HOST=unix:///var/run/docker.sock
export AI4R_APP_IMAGE="${AI4R_APP_IMAGE:-ai4r-m1-app:local}"
export AI4R_OPERATOR_CONFIG="${AI4R_OPERATOR_CONFIG:-$HOME/.local/share/ai4r/config.yaml}"
export AI4R_JOB_ID=web-play
export AI4R_REUSABLE_LOGIN=1
export AI4R_LOCAL_WORKSPACE=1
export AI4R_LOCAL_CHAT=1
export AI4R_LOCAL_RESEARCH="${AI4R_LOCAL_RESEARCH:-0}"
export AI4R_BIND_ADDRESS=127.0.0.1
export JIUWENSWARM_M1_ORIGIN=http://127.0.0.1:5173

build=0
for option in "$@"; do
  case "$option" in
    --build) build=1 ;;
    --research) export AI4R_LOCAL_RESEARCH=1 ;;
    *) printf 'Usage: %s [--build] [--research]\n' "$0" >&2; exit 2 ;;
  esac
done
docker info >/dev/null
if [[ "$build" == 1 ]] || ! docker image inspect "$AI4R_APP_IMAGE" >/dev/null 2>&1; then
  docker build --progress=plain --platform linux/amd64 \
    -f deploy/m1/Dockerfile.app --target production -t "$AI4R_APP_IMAGE" .
fi

if [[ ! -e "$AI4R_OPERATOR_CONFIG" ]]; then
  mkdir -p -- "$(dirname -- "$AI4R_OPERATOR_CONFIG")"
  (umask 022; set -o noclobber; printf '{}\n' > "$AI4R_OPERATOR_CONFIG")
fi

docker compose -p ai4r-web-play -f deploy/m1/compose.yaml up -d --no-build --pull never app
printf '\nOpen the newest complete login URL below in Chrome or Edge. You can bookmark it.\n'
printf 'Your local input workspace is initialized automatically; upload documents, repository ZIPs and datasets in the composer.\n'
printf 'Sign in with ChatGPT, type a message and send. Local chat requires GPT-6.1 Sol; no API key is needed.\n'
printf 'Selected reference documents can be included in chat. Full research runs still require operator/runtime resources.\n\n'
if [[ "$AI4R_LOCAL_RESEARCH" == 1 ]]; then
  printf 'Local research policy and bindings are captured explicitly. Settings > Agent shows actual Capsule admission and runtime prerequisites.\n'
  printf 'This selection does not manufacture checking qualifications, scientific resources or credentials.\n\n'
fi
container_id="$(docker compose -p ai4r-web-play -f deploy/m1/compose.yaml ps -q app)"
docker logs --tail 20 -f "$container_id"
