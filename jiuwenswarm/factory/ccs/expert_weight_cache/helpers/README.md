# Expert weight cache helpers

From the repository root, set the Python and helper paths.

```bash
PY="$HOME/predemo/venv-factory/bin/python"
H=jiuwenswarm/factory/ccs/expert_weight_cache/helpers
```

Inspect a captured `-lv 4` log in either shell. The first command reports
every active, inactive and stats line, plus the loader modes. Use
`--require-active` for the positive mmap case. The stats checker expects a
single context's log and compares peak bytes with the admitted ledger budget.
Use `--expect bypass` for a native-cache or non-mmap fallback.

```bash
"$PY" -B "$H/check_markers.py" run.server.log --name expert_weight_cache --require-active
"$PY" -B "$H/check_cache_stats.py" run.server.log --name expert_weight_cache \
  --admitted-bytes 67108864 --expect reuse
```

In an authorized real shell with built binaries and port 5175 available, run
the one-shot script sequentially for stock, candidate gate unset and candidate
gate enabled. The script starts and stops its own server for each capture.
Supply the same model and placement to all three calls. The example uses a
GPU offload configuration. Choose the contract's placement and use a separate
output directory for each configuration.

```bash
"$PY" -B "$H/run_parity.py" --one-shot "$HOME/predemo/one_shot.sh" \
  --stock /path/to/stock/bin --candidate /path/to/candidate/bin \
  --model /path/to/model.gguf --output captures \
  -- -lv 4 -lm mmap -ngl 99 -cmoe
"$PY" -B "$H/check_markers.py" captures/candidate_on.server.log \
  --name expert_weight_cache --require-active
```

The parity helper compares returned token IDs, content and stop type. For
formal acceptance compare the contract's captured greedy stdout byte for
byte. Retain the candidate-on activation line for engagement evidence.

Each helper supports `--help`. Run the three offline helper tests with
`"$PY" -B -m unittest discover -s "$H/../tests" -p test_helpers.py -v`.

For a gate-unset arm, use `check_markers.py LOG --name expert_weight_cache
--expect-silent`. It exits nonzero for any line carrying the prefix, including
unrecognized marker kinds.
