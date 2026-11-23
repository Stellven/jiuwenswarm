#!/bin/sh
# One measurement of the Muse model files in ~/ifbench (read only) with a llama-server of our own.
#   muse-measure.sh NAME PROMPTS WARMUP [extra llama-server arguments]
# Starts the server on port 8189 with the configuration the bench uses plus the extra arguments, waits until it
# answers, measures with measure.py, records memory, and stops the server. Writes only into this folder.
D=$HOME/system-ontology-run-20261119
[ -d "$D" ] || D=/home/<spark-user>/system-ontology-run-20261119
NAME=$1; PROMPTS=$2; WARMUP=$3; shift 3
OUT=$D/muse-runs/$NAME
mkdir -p "$OUT"
MODEL=/home/<spark-user>/ifbench/models/muse/UD-IQ2_XXS/Muse-Spark-Open-816B-A42B-UD-IQ2_XXS-00001-of-00006.gguf
SERVER=/home/<spark-user>/llama.cpp/build/bin/llama-server
PORT=8189
if pgrep -u "$(id -u)" -f "llama-server" >/dev/null; then echo "a llama-server is already running; not starting another" | tee "$OUT/ABORTED"; exit 9; fi

mem() { awk '/MemTotal|MemAvailable|^Cached|MemFree/ {printf "%s %.1f GB; ", $1, $2/1048576*1.073741824}' /proc/meminfo; echo; }
proc() { [ -r /proc/$1/smaps_rollup ] && awk '/^Rss:|^Pss:|^Anonymous:|^Pss_File:|^Pss_Anon:|^Shared_Clean:|^Private_Clean:/ {printf "%s %.2f GiB; ", $1, $2/1048576}' /proc/$1/smaps_rollup; echo; }
gpu() { nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader 2>/dev/null | tr '\n' ';'; echo; }

{
echo "name: $NAME"; echo "started: $(date -Is)"
echo "command: $SERVER -m $MODEL --alias muse-own --host 127.0.0.1 --port $PORT -c 20480 -np 1 --metrics --slots --jinja --log-verbosity 4 --load-mode mmap -ngl 999 --cpu-moe -b 2048 -ub 2048 $*"
echo "memory before start: $(mem)"
} > "$OUT/record.txt"

T0=$(date +%s)
setsid nohup "$SERVER" -m "$MODEL" --alias muse-own --host 127.0.0.1 --port $PORT -c 20480 -np 1 --metrics --slots --jinja \
  --log-verbosity 4 --load-mode mmap -ngl 999 --cpu-moe -b 2048 -ub 2048 "$@" > "$OUT/server.log" 2>&1 < /dev/null &
PID=$!
echo "$PID" > "$OUT/server.pid"
READY=""
i=0
while [ $i -lt 1200 ]; do
  kill -0 $PID 2>/dev/null || break
  if curl -s -m 2 http://127.0.0.1:$PORT/health 2>/dev/null | grep -q '"ok"'; then READY=$(( $(date +%s) - T0 )); break; fi
  sleep 2; i=$((i+2))
done
if [ -z "$READY" ]; then
  echo "server did not become ready (alive: $(kill -0 $PID 2>/dev/null && echo yes || echo no))" >> "$OUT/record.txt"
  kill -TERM $PID 2>/dev/null; tail -30 "$OUT/server.log" >> "$OUT/record.txt"; exit 2
fi
{
echo "ready after: ${READY} s"
echo "memory when ready: $(mem)"; echo "process when ready: $(proc $PID)"; echo "gpu when ready: $(gpu)"
} >> "$OUT/record.txt"

python3 "$D/measure/measure.py" --base-url http://127.0.0.1:$PORT/v1 --model muse-own --name "$NAME" \
  --artifact "llama.cpp $($SERVER --version 2>&1 | head -1) + Muse-Spark-Open-816B-A42B UD-IQ2_XXS (six files in ~/ifbench, read only); extra arguments: $*" \
  --environment env/dgx-spark-measured-20261119 --prompts "$PROMPTS" --warmup "$WARMUP" --runs 1 --max-tokens 128 \
  --extra-body '{"cache_prompt": false, "seed": 1234}' --timeout 3600 --out-dir "$OUT" > "$OUT/measure.out" 2>&1
RC=$?
{
echo "measure.py exit: $RC"
echo "memory after: $(mem)"; echo "process after: $(proc $PID)"; echo "gpu after: $(gpu)"
} >> "$OUT/record.txt"
curl -s -m 10 http://127.0.0.1:$PORT/metrics > "$OUT/metrics.txt" 2>/dev/null
curl -s -m 10 http://127.0.0.1:$PORT/props > "$OUT/props.json" 2>/dev/null
kill -TERM $PID; j=0; while kill -0 $PID 2>/dev/null && [ $j -lt 60 ]; do sleep 1; j=$((j+1)); done
kill -0 $PID 2>/dev/null && kill -KILL $PID
echo "server stopped: $(date -Is); memory after stop: $(mem)" >> "$OUT/record.txt"
echo FINISHED >> "$OUT/record.txt"
