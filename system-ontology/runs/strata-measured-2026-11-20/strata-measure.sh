#!/bin/sh
# One measurement of Strata (built here from source) with the Qwen3.8-Flash-Next IQ3_S model downloaded into strata-data/.
#   strata-measure.sh NAME
# Starts Strata's server on port 8190 (this machine only, no browser), waits until it answers, measures twice with
# measure.py (prompts of about 2,000 tokens with 128 tokens out, as for the Muse runs; prompts of about 4,000 tokens
# with 256 tokens out, as in Strata's own table), records memory, and stops the server. Writes only into this folder.
D=/home/<spark-user>/system-ontology-run-20261119
. $D/strata-env.sh
NAME=$1
OUT=$D/strata-runs/$NAME
mkdir -p "$OUT"
PORT=8190
if pgrep -u "$(id -u)" -f "llama-server|serve/server.py|engine/strata" >/dev/null; then echo "an engine is already running; not starting another" | tee "$OUT/ABORTED"; exit 9; fi

mem() { awk '/MemTotal|MemAvailable|^Cached|MemFree/ {printf "%s %.1f GB; ", $1, $2/976562.5}' /proc/meminfo; echo; }
gpu() { nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | tr '\n' ';'; echo; }
tree_rss() { ps -u "$(id -u)" -o rss=,cmd= | awk '/engine\/strata|serve\/server.py/ {s+=$1} END {printf "%.2f GiB resident in the server and the engine", s/1048576}'; echo; }

cd $D/strata
{
echo "name: $NAME"; echo "started: $(date -Is)"
echo "command: .venv/bin/python serve/server.py --engine strata --config strata-iq3_s.json --host 127.0.0.1 --port $PORT"
echo "engine: $(cat engine/BUILD.json)"
echo "source revision: $(git rev-parse HEAD 2>/dev/null)"
echo "memory before start: $(mem)"
} > "$OUT/record.txt"

T0=$(date +%s)
setsid nohup .venv/bin/python serve/server.py --engine strata --config strata-iq3_s.json --host 127.0.0.1 --port $PORT \
  > "$OUT/server.log" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$OUT/server.pid"
READY=""
i=0
while [ $i -lt 1500 ]; do
  kill -0 $PID 2>/dev/null || break
  if curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '^200$'; then READY=$(( $(date +%s) - T0 )); break; fi
  sleep 3; i=$((i+3))
done
if [ -z "$READY" ]; then
  echo "server did not become ready (alive: $(kill -0 $PID 2>/dev/null && echo yes || echo no))" >> "$OUT/record.txt"
  kill -TERM $PID 2>/dev/null; sleep 5; pkill -u "$(id -u)" -f "engine/strata" 2>/dev/null
  tail -40 "$OUT/server.log" >> "$OUT/record.txt"; echo FINISHED >> "$OUT/record.txt"; exit 2
fi
curl -s -m 10 http://127.0.0.1:$PORT/health > "$OUT/health.json" 2>/dev/null
{
echo "ready after: ${READY} s"
echo "memory when ready: $(mem)"; echo "process when ready: $(tree_rss)"; echo "gpu when ready: $(gpu)"
} >> "$OUT/record.txt"

ART="Strata engine $(cat engine/BUILD.json) built from source revision $(git rev-parse --short HEAD 2>/dev/null) + Qwen3.8-Flash-Next IQ3_S; run configuration as written by its setup (strata-iq3_s.json)"
python3 "$D/measure/measure.py" --base-url http://127.0.0.1:$PORT/v1 --model qwen3.8-flash-next-iq3_s --name "$NAME-2k" \
  --artifact "$ART" --environment env/dgx-spark-measured-20261119 --prompts "$D/measure/prompts-2k.txt" --warmup 2 --runs 1 \
  --max-tokens 128 --extra-body '{"seed": 1234}' --timeout 1800 --out-dir "$OUT" > "$OUT/measure-2k.out" 2>&1
echo "measure 2k exit: $?; memory: $(mem); gpu: $(gpu)" >> "$OUT/record.txt"
python3 "$D/measure/measure.py" --base-url http://127.0.0.1:$PORT/v1 --model qwen3.8-flash-next-iq3_s --name "$NAME-4k" \
  --artifact "$ART" --environment env/dgx-spark-measured-20261119 --prompts "$D/measure/prompts-4k.txt" --warmup 2 --runs 1 \
  --max-tokens 256 --extra-body '{"seed": 1234}' --timeout 1800 --out-dir "$OUT" > "$OUT/measure-4k.out" 2>&1
echo "measure 4k exit: $?; memory: $(mem); gpu: $(gpu); $(tree_rss)" >> "$OUT/record.txt"
curl -s -m 10 http://127.0.0.1:$PORT/props > "$OUT/props.json" 2>/dev/null
cp strata-iq3_s.log "$OUT/engine.log" 2>/dev/null

kill -TERM $PID; j=0; while kill -0 $PID 2>/dev/null && [ $j -lt 90 ]; do sleep 1; j=$((j+1)); done
kill -0 $PID 2>/dev/null && kill -KILL $PID
sleep 2; pkill -u "$(id -u)" -f "engine/strata" 2>/dev/null
echo "server stopped: $(date -Is); still running: $(pgrep -u "$(id -u)" -f 'engine/strata|serve/server.py' | wc -l); memory after stop: $(mem)" >> "$OUT/record.txt"
echo FINISHED >> "$OUT/record.txt"
