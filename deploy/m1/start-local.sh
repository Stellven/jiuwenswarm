#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
profile="${AI4R_OPERATOR_PROFILE:-$HOME/.local/share/ai4r/operator.json}"
build=0
for option in "$@"; do
  case "$option" in
    --build) build=1 ;;
    --research) : ;;
    *) printf 'Usage: %s [--build] [--research]\n' "$0" >&2; exit 2 ;;
  esac
done
python3 "$script_dir/ai4r.py" --profile "$profile" setup
if [[ "$build" == 1 ]]; then
  output="$(dirname -- "$profile")/builds/$(date +%Y%m%dT%H%M%S)-$$"
  mkdir -p -- "$(dirname -- "$output")"
  python3 "$script_dir/ai4r.py" --profile "$profile" build --output "$output"
fi
python3 "$script_dir/ai4r.py" --profile "$profile" start
