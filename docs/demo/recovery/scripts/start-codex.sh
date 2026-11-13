#!/usr/bin/env bash
set -euo pipefail
package_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"
cd /home/muk/projects/jiuwenswarm
exec /home/muk/.local/bin/codex "Read the project continuation instructions at $package_dir/AUTONOMOUS.md and START HERE.md. Inspect current state before acting. Default to zero inference experiments. Do not write Danta."
