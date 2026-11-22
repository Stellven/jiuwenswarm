#!/usr/bin/env bash
# om_run.sh — guarded over-memory engine run on jetson-arm.
# usage: om_run.sh OUTDIR IMAGE "ENV_FLAGS" TOOL ARGS...
#   e.g. om_run.sh experiments/jetson/OM/b1-r1 campaign/llamacpp:jetson-c1-p03 "" llama-bench -m /om/model.gguf -lm mmap -ngl 99 -cmoe -p 64 -n 32 -r 2
# Model dir ~/models/campaign/qwen36-35b-a3b is mounted read-only at /om. Watchdog kills ONLY this container
# when MemAvailable < OM_MIN_AVAIL_MIB (default 700) or zram swap used > OM_MAX_SWAP_MIB (default 1536).
set -u
OUT=$1; IMG=$2; ENVF=$3; TOOL=$4; shift 4
R=$(cd "$(dirname "$0")/../.." && pwd); mkdir -p "$OUT"
NAME="om-$(date +%s)-$$"
MODELDIR=${OM_MODELDIR:-$HOME/models/campaign/qwen36-35b-a3b}
DATADIR=$HOME/models/campaign/data/wikitext/wikitext-2-raw
DP=${DOCKER_CMD_PREFIX:-}
dk(){ if [ -n "$DP" ]; then $DP "docker $*"; else docker "$@"; fi; }
printf '%s\n' "$IMG" "$ENVF" "$TOOL $*" > "$OUT/cmd.txt"
# OM_NSYS=1: run the engine under Nsight Systems (mounted read-only from the host install).
# Traced runs perturb timing; use them for breakdowns only, never as speed evidence.
NSYS_MOUNT=""; NSYS_PREFIX=""
if [ "${OM_NSYS:-0}" = 1 ]; then
    NSYS_DIR=${OM_NSYS_DIR:-/opt/nvidia/nsight-systems/2024.5.4}
    [ -x "$NSYS_DIR/target-linux-tegra-armv8/nsys" ] || { echo "NSYS_MISSING $NSYS_DIR" > "$OUT/status"; exit 2; }
    NSYS_MOUNT="-v $NSYS_DIR:/nsys:ro -v $(cd "$OUT" && pwd):/prof"
    NSYS_PREFIX="/nsys/target-linux-tegra-armv8/nsys profile -t cuda,nvtx,osrt --cuda-graph-trace=node --sample=none --cpuctxsw=none -f true -o /prof/nsys"
fi
# Host-only page-cache protocol; unset means carryover (measure without warming).
# OM_CACHE_MODEL overrides host model path inference from -m/--model under /om/.
# warm uses OM_CACHE_WARM_RANGES (host JSON) or OM_CACHE_WARM_BYTES (prefix).
OM_CACHE_ARGV=("$@")
om_cache_record(){ python3 "$R/cc/page_cache/run_protocol.py" "$1" "$OUT" "$MODELDIR" "${OM_CACHE_ARGV[@]}"; }
CG=
om_cleanup(){
    if [ -n "$CG" ]; then kill "$CG" 2>/dev/null; wait "$CG" 2>/dev/null; fi
    om_cache_record end || echo "page-cache end recording failed" >&2
}
trap om_cleanup EXIT
om_cache_record start || { echo "CACHE_PROTOCOL_FAIL" > "$OUT/status"; exit 2; }
# Take the first snapshot before engine startup; stop sampling as soon as it exits.
rm -f "$OUT/contention.json"
if [ "${OM_CONTENTION_GUARD:-1}" != 0 ]; then
    python3 "$R/cc/om_run/contention.py" "$OUT/contention.json" "$$" & CG=$!
    while [ ! -s "$OUT/contention.json" ] && kill -0 "$CG" 2>/dev/null; do sleep .02; done
fi
dk run -d --name "$NAME" --runtime nvidia --network none --label campaign=c1 --label om=1 $ENVF \
   -v "$MODELDIR":/om:ro -v "$DATADIR":/d:ro $NSYS_MOUNT "$IMG" $NSYS_PREFIX /app/$TOOL "$@" > "$OUT/container.id" || { echo "START_FAIL" > "$OUT/status"; exit 2; }
if [ "${OM_THREADS:-0}" = 1 ]; then
    python3 "$R/cc/thread_sampler/thread_sampler.py" --container "$NAME" --hz "${OM_THREADS_HZ:-100}" \
        --out "$OUT/threads.jsonl" --summary "$OUT/threads.summary.json" \
        >"$OUT/threads.log" 2>&1 & TS=$!
fi
if [ -n "$DP" ]; then KILLCMD="$DP 'docker kill $NAME'"; else KILLCMD="docker kill $NAME"; fi
python3 "$R/cc/resource_observe/resource_observe.py" watchdog --min-available-mib ${OM_MIN_AVAIL_MIB:-600} \
   --max-swap-used-mib ${OM_MAX_SWAP_MIB:-2560} --max-swap-rate-mibs ${OM_MAX_SWAP_RATE:-1000} --interval-ms 250 --kill-cmd "$KILLCMD" --out "$OUT/watchdog.jsonl" & WD=$!
python3 "$R/cc/resource_observe/resource_observe.py" sample --backends io,proc,tegrastats --path "$MODELDIR" --interval-ms 500 \
   --duration-s ${OM_MAX_S:-1800} --out "$OUT/telemetry.jsonl" >/dev/null 2>&1 & SM=$!
T0=$(date +%s.%N)
RC=$(dk wait "$NAME"); T1=$(date +%s.%N)
if [ -n "$CG" ]; then kill "$CG" 2>/dev/null; wait "$CG" 2>/dev/null; CG=; fi
kill $WD $SM 2>/dev/null; wait $WD 2>/dev/null; WDRC=$?
dk logs "$NAME" > "$OUT/stdout.txt" 2> "$OUT/stderr.txt"
if [ "${OM_THREADS:-0}" = 1 ]; then
    wait "$TS" || echo "thread sampler failed; see threads.log" >&2
    if [ -s "$OUT/threads.jsonl" ]; then
        python3 "$R/cc/thread_sampler/thread_sampler.py" --summarize "$OUT/threads.jsonl" \
            --stderr "$OUT/stderr.txt" --summary "$OUT/threads.summary.json" \
            >>"$OUT/threads.log" 2>&1 || echo "thread summary failed; see threads.log" >&2
    fi
fi
if [ "${OM_NSYS:-0}" = 1 ]; then
    # nsys appends its own progress text to the engine's stdout; move it out so the output check sees only the engine.
    python3 - "$OUT" <<'PY'
import sys
o=sys.argv[1]; s=open(o+"/stdout.txt","rb").read(); i=s.find(b"Collecting data...")
if i >= 0:
    open(o+"/nsys.stdout.txt","wb").write(s[i:]); open(o+"/stdout.txt","wb").write(s[:i])
PY
fi
if [ "${OM_NSYS:-0}" = 1 ] && [ -s "$OUT/nsys.nsys-rep" ]; then
    # Flat CSV summaries next to the other run files; the SQLite export is regenerable and large.
    nsys stats -q -r cuda_gpu_kern_sum,cuda_api_sum,osrt_sum,cuda_gpu_mem_time_sum --format csv \
        -o "$OUT/nsys" "$OUT/nsys.nsys-rep" > "$OUT/nsys.log" 2>&1 || echo "nsys stats failed; see nsys.log" >&2
    rm -f "$OUT/nsys.sqlite"
fi
OOM=$(dk inspect "$NAME" --format '{{.State.OOMKilled}}')
dk rm "$NAME" > /dev/null
TRIP=$(grep -c watchdog_trip "$OUT/watchdog.jsonl" 2>/dev/null); TRIP=${TRIP:-0}
python3 - "$OUT" "$RC" "$T0" "$T1" "$OOM" "$TRIP" "$IMG" "$ENVF" "$TOOL" "$@" <<'PY'
import json,sys,os,socket
o,rc,t0,t1,oom,trip,image,env,*argv=sys.argv[1:]
code=int(rc.strip() or -1)
tripped=int(trip)>0
if tripped and code in (137, -9):
    status="watchdog_tripped_killed"
elif tripped and code == 0:
    status="watchdog_tripped_survived"
elif oom.strip()=="true":
    status="oom_killed"
else:
    status="ok" if code == 0 else "failed"
try:
    with open(next((q for q in map(os.path.expanduser, ("~/.config/jiuwenswarm-factory/host_id", "~/.config/siminfeng/host_id")) if os.path.exists(q)), os.path.expanduser("~/.config/jiuwenswarm-factory/host_id"))) as f:
        host_id=f.read().strip() or socket.gethostname()
except OSError:
    host_id=socket.gethostname()
json.dump(dict(exit_code=code,wall_s=round(float(t1)-float(t0),2),
  oom_killed=oom.strip()=="true",watchdog_trips=int(trip),status=status,
  host_id=host_id,image=image,env=env,argv=argv),open(o+"/result.json","w"),indent=1)
print(open(o+"/result.json").read())
PY
