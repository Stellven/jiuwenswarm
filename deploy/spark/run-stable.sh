#!/bin/bash
set -euo pipefail
root=${FACTORY_SPARK_ROOT:-/home/user2/software-factory-spark-20261113}
repo=$root/sources/cc-dgx-spark
if [ "$#" -eq 0 ]; then echo "Usage: $0 'your prompt'" >&2; exit 2; fi
# Serialize convenience invocations; the shared host queue still owns GPU exclusivity.
exec 9>"$root/stable-launch.lock"
flock 9
bridge_pid=
cleanup() {
  if [ -n "$bridge_pid" ] && kill -0 "$bridge_pid" 2>/dev/null; then
    touch "$root/port-ipc/STOP"
    wait "$bridge_pid" || true
  fi
}
trap cleanup EXIT
cd "$repo"
deploy/spark/start-bridge.sh >"$root/results/stable-launch-bridge-$$.log" 2>&1 &
bridge_pid=$!
sleep 0.2
# If another owned bridge already holds its lock, use it and leave its lifecycle alone.
deploy/spark/factory-container.sh deploy/spark/stable-llama.py run --prompt "$*" --wait
