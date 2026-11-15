#!/bin/sh
set -eu
root=${FACTORY_SPARK_ROOT:-/home/user2/software-factory-spark-20261113}
repo=$root/sources/cc-dgx-spark
exec docker run --rm --network=none --read-only --user "$(id -u):$(id -g)" \
  --cap-drop ALL --security-opt no-new-privileges --pids-limit 256 --cpus 2 --memory 1g --memory-swap 1g \
  --tmpfs /tmp:rw,nosuid,nodev,size=128m \
  --mount "type=bind,src=$root,dst=$root" \
  --mount "type=bind,src=$repo,dst=/factory,readonly" \
  --mount type=bind,src=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq,dst=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq,readonly \
  --mount type=bind,src=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source,dst=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source,readonly \
  --env FACTORY_HOME="$root/port-store" --env FACTORY_BRIDGE_DIR="$root/port-ipc" \
  --env FACTORY_HOST_PYTHON=/usr/bin/python3 \
  --env FACTORY_JOBQ_BIN=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source/bin/jobq \
  --env FACTORY_BUILD_RECIPE=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source/builds/llamacpp-jetson/Dockerfile \
  --env JOBQ_DIR=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/jobq \
  --env SIMINFENG_ROOT=/home/user2/rsi-expert-streaming-spark-002/paired-retry-001/lab-source \
  --env PYTHONPATH=/factory --env DOCKER_PREFIX= --env HOME=/tmp --env FACTORY_TASK_ID=spark-deepseek-port \
  --entrypoint python3 "${FACTORY_CLI_IMAGE:-factory/cli:cc-dgx-spark}" "$@"
