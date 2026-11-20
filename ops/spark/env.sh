# Source from the Spark worktree; no model is started by this file.
SPARK_REPO="${SPARK_REPO:-$HOME/predemo-spark/jiuwenswarm}"
export FACTORY_JOBQ_BIN="$SPARK_REPO/ops/spark/vendor/jobq"
export JOBQ_DIR="$HOME/predemo-spark/OPS/jobq-cpu"
if [[ "${SPARK_OWNER_BUILD:-}" == placement-tier ]]; then
    export JOBQ_DIR="$HOME/predemo-spark/OPS/jobq-cpu-c2"
fi
export JOBQ_RUN_OP="$SPARK_REPO/ops/spark/bin/cpu-run-op"
export PATH="/usr/local/cuda/bin:$SPARK_REPO/.venv/bin:$PATH"
export FACTORY_YIELD_ON_JOBS=1
