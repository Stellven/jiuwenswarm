#!/bin/sh
set -eu
umask 077
export JIUWENSWARM_M1_PROFILE=1
exec jiuwenswarm-start "$@"
