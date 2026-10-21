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

compose=(docker compose -p ai4r-web-play -f deploy/m1/compose.yaml)
if [[ "$AI4R_LOCAL_RESEARCH" == 1 ]]; then
  export AI4R_EXECUTOR_CGROUP_HOST
  AI4R_EXECUTOR_CGROUP_HOST="$(bash deploy/m1/prepare-local-executor.sh)"
  compose+=(-f deploy/m1/compose.local-research.yaml)
fi
"${compose[@]}" up -d --no-build --pull never app
printf '\nOpen the newest complete login URL below in Chrome or Edge. You can bookmark it.\n'
printf 'Your local input workspace is initialized automatically; upload documents, repository ZIPs and datasets in the composer.\n'
printf 'Sign in with ChatGPT, type a message and send. Local chat requires GPT-6.1 Sol; no API key is needed.\n'
printf 'Selected reference documents can be included in chat.\n\n'
container_id="$("${compose[@]}" ps -q app)"
if [[ "$AI4R_LOCAL_RESEARCH" == 1 ]]; then
  printf 'Preparing exact built-in research Capsules for local development; qualification is NOT_RUN.\n'
  printf 'Startup makes no model calls. Each research request still runs its checks, verifiers and gates.\n\n'
  # Wait only for the protected IPC owner to exist, not for subscription login
  # or a qualification batch. Installation itself performs no model calls.
  deadline=$((SECONDS + 60))
  while (( SECONDS < deadline )); do
    if "${compose[@]}" exec -T --user 10001:10001 app sh -c \
      'test -S /run/ai4r/model.sock && test -S /run/ai4r-executor/executor.sock' >/dev/null 2>&1; then break; fi
    if ! docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null | grep -qx true; then
      printf 'The app stopped during startup. Inspect docker logs before retrying.\n' >&2; exit 2
    fi
    sleep 1
  done
  "${compose[@]}" exec -T --user 10001:10001 app /opt/venv/bin/python \
    -m jiuwenswarm.research.initialize --json
  # Activation changes immutable library selection and installs a captured
  # science runtime. Recreate only the app; account/upload/state volumes stay.
  "${compose[@]}" up -d --force-recreate --no-build --pull never app
  container_id="$("${compose[@]}" ps -q app)"
  printf '\nLocal development research is installed. Sign in with ChatGPT in Settings, then choose the CPU research example in the normal chat.\n'
  printf 'The built-in Capsules are unqualified development assets; this startup claims no qualification PASS.\n'
fi
docker logs --tail 20 -f "$container_id"
