#!/usr/bin/env bash
# SAMPLE: probe, project, then the full run. Read argv from a verified recipe; adapt paths and limits.
set -euo pipefail
RECIPE=${1:?recipe.json}; GRANT=${2:?disk grant bytes}; OUT_DIR=${3:?output directory}
argv() {  # NUL-separated argv of the full run ("argv") or the probe ("probe")
  python3 -c 'import json,sys; r=json.load(open(sys.argv[1])); k=sys.argv[2]
sys.stdout.write("\0".join(r["argv"] if k == "argv" else r[k]["argv"]))' "$RECIPE" "$1"; }

# 1. probe: layers 0..L only (the recipe prunes the rest)
mapfile -d '' PROBE < <(argv probe)
/usr/bin/time -v nice -n 10 ionice -c3 "${PROBE[@]}" > probe.log 2>&1
python3 - "$RECIPE" probe.log <<'PY'
import json, re, sys
r = json.load(open(sys.argv[1]))["probe"]
s = re.search(r"Elapsed \(wall clock\) time.*: (?:(\d+):)?(\d+):([\d.]+)", open(sys.argv[2]).read())
sec = int(s[1] or 0) * 3600 + int(s[2]) * 60 + float(s[3])
print(f"probe {sec:.0f}s -> full ~{sec * r['total_routed_layers'] / r['converted_routed_layers']:.0f}s")
PY
rm -f "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["probe"]["output"])' "$RECIPE")"

# 2. full run with a disk watch that stops the tool before the grant is exceeded
mapfile -d '' FULL < <(argv argv)
nice -n 10 ionice -c3 "${FULL[@]}" > quantize.log 2>&1 & PID=$!
while kill -0 $PID 2>/dev/null; do
  used=$(du -sb "$OUT_DIR" | cut -f1)
  if (( used > GRANT )); then kill $PID; echo "disk grant exceeded: $used > $GRANT"; exit 2; fi
  sleep 30
done
wait $PID
! grep -q "falling back to" quantize.log   # any fallback means the recipe was wrong
