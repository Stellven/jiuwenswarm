#!/bin/sh
# Model-in-the-loop CC benches (heldout, contract, haltbench): 10 cases x 2 reps per arm, sol and luna. Host codex, no Docker.
set -u
C=/c/Users/m50066326/huawei/AI4Research-Development/ai4r-bench-clean2; W='C:\Users\m50066326\huawei\outputs\rebench-20261028\modelbench'
cd "$C"; export AI4R_PYTHON=python
for B in heldout contract haltbench; do
  for M in gpt-6.1-sol gpt-6-luna; do
    sh scripts/ai4r-bench $B run --host --execute --model $M --reps 1 --out "$W\$B" > "/c/Users/m50066326/huawei/outputs/rebench-20261028/mb-$B-$M.log" 2>&1; echo "$B $M run=$?"
    sh scripts/ai4r-bench $B score --host --model $M --out "$W\$B" >> "/c/Users/m50066326/huawei/outputs/rebench-20261028/mb-$B-$M.log" 2>&1; echo "$B $M score=$?"
  done
done
