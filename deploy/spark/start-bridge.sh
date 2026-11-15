#!/bin/sh
set -eu
root=${FACTORY_SPARK_ROOT:-/home/user2/software-factory-spark-20261113}
repo=$root/sources/cc-dgx-spark
mkdir -p "$root/port-ipc"
rm -f "$root/port-ipc/STOP"
export PYTHONPATH=$repo
export FACTORY_JOBQ_BIN=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source/bin/jobq
export JOBQ_DIR=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq
export DOCKER_PREFIX=''
export PATH=/home/user2/strata-baseline/Strata/.venv-build/bin:/usr/local/cuda/bin:/usr/bin:/bin
exec /usr/bin/python3 -m jiuwenswarm.factory.bridge --workspace "$root" --queue "$JOBQ_DIR" --jobq "$FACTORY_JOBQ_BIN" --inbox "$root/port-ipc" --seconds 10800
