#!/usr/bin/env bash
set -euo pipefail

repo="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
dist="${R8_ENGINE_DIST:-$HOME/muse-demo/r8-final/site}"
replay="${R8_ENGINE_REPLAY:-$HOME/muse-demo/r8-final/curated-replay}"
log="${R8_SITE_LOG:-$HOME/muse-demo/bridge/r8-site.log}"
python="${R8_SITE_PYTHON:-$HOME/predemo-spark/jiuwenswarm/.venv/bin/python}"
session="${R8_SITE_SESSION:-r8-site}"

if [[ "${1:-}" == --serve ]]; then
  cd -- "$repo"
  exec >>"$log" 2>&1
  exec "$python" -m scripts.spark.r8_engine_site --dist "$dist" --replay "$replay"
fi

if [[ ! -f "$dist/index.html" ]]; then
  printf 'Missing engine build %s\n' "$dist/index.html" >&2
  exit 1
fi

launcher="$repo/scripts/spark/restart_r8_site.sh"
if tmux has-session -t "=$session" 2>/dev/null; then
  window="$(tmux list-windows -t "=$session" -F '#{window_name} #{window_id}' | awk '$1 == "r8-site" {print $2; exit}')"
  if [[ -n "$window" ]]; then
    tmux respawn-pane -k -t "$window" env R8_ENGINE_DIST="$dist" R8_ENGINE_REPLAY="$replay" R8_SITE_LOG="$log" R8_SITE_PYTHON="$python" "$launcher" --serve
  else
    tmux new-window -d -t "=$session:" -n r8-site env R8_ENGINE_DIST="$dist" R8_ENGINE_REPLAY="$replay" R8_SITE_LOG="$log" R8_SITE_PYTHON="$python" "$launcher" --serve
  fi
else
  tmux new-session -d -s "$session" -n r8-site env R8_ENGINE_DIST="$dist" R8_ENGINE_REPLAY="$replay" R8_SITE_LOG="$log" R8_SITE_PYTHON="$python" "$launcher" --serve
fi
