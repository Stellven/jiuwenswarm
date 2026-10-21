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
  printf 'Research setup uses a captured CPU example, the real subscription, independent Capsule guards and confined execution.\n'
  printf 'Sign in with ChatGPT if needed. First-time guard initialization runs once for the exact installed release.\n\n'
  # Let a first-time user see the browser login link while the private services
  # start. Repeated launches reuse exact captured calibration/admission records.
  announced=0
  ready=0
  deadline=$((SECONDS + 300))
  while (( SECONDS < deadline )); do
    if [[ "$announced" == 0 ]]; then
      login_line="$(docker logs --tail 40 "$container_id" 2>/dev/null | sed -n '/^Open JiuwenSwarm:/p' | tail -1)"
      if [[ -n "$login_line" ]]; then printf '%s\n' "$login_line"; announced=1; fi
    fi
    if ! docker inspect --format '{{.State.Running}}' "$container_id" 2>/dev/null | grep -qx true; then
      printf 'The app stopped during startup. Inspect docker logs before retrying.\n' >&2
      exit 2
    fi
    if "${compose[@]}" exec -T --user 10001:10001 app /opt/venv/bin/python -c '
import asyncio
from jiuwenswarm.research.native_ports import _session, APP_UID, STATUS_PROTOCOL
from jiuwenswarm.research.private_rpc import PrivateRPCClient
async def check():
    try:
        client=PrivateRPCClient("/run/ai4r/agent-status.sock", protocol=STATUS_PROTOCOL, peer_uid=APP_UID, **_session("/run/ai4r", APP_UID))
        status=await client.call("subscription_status", {}, timeout_s=3)
        return status.get("state")=="ready"
    except Exception:
        return False
raise SystemExit(0 if asyncio.run(check()) else 2)
' >/dev/null 2>&1; then ready=1; break; fi
    sleep 3
  done
  if [[ "$ready" != 1 ]]; then
    printf 'ChatGPT sign-in is still required. The app remains running; sign in and rerun with --research.\n' >&2
    exit 2
  fi
  printf '\nActivating the exact installed research Capsules through their real checking owners...\n'
  "${compose[@]}" exec -T --user 10001:10001 app /opt/venv/bin/python \
    -m jiuwenswarm.research.initialize --json --calibrate --concurrency 3
  # Activation changes immutable library selection and installs a captured
  # science runtime. Recreate only the app; account/upload/state volumes stay.
  "${compose[@]}" up -d --force-recreate --no-build --pull never app
  container_id="$("${compose[@]}" ps -q app)"
  printf '\nResearch is activated. Open the app and choose the CPU research example in the normal chat.\n'
fi
docker logs --tail 20 -f "$container_id"
