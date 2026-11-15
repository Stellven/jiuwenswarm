#!/bin/sh
set -eu
base=ai4r-hybrid-runner:20261026
expected=sha256:754ba564cad9bfb5b8196c16721f14fb8b0ba201c272d81aef341cde2fd167c3
actual=$(docker image inspect --format '{{.Id}}' "$base")
[ "$actual" = "$expected" ] || { echo 'Factory base identity mismatch' >&2; exit 1; }
docker build --pull=false --target runtime -f deploy/spark/Factory.Dockerfile -t factory/cli:cc-dgx-spark .
docker build --pull=false --target validation -f deploy/spark/Factory.Dockerfile -t factory/cli-test:cc-dgx-spark .
