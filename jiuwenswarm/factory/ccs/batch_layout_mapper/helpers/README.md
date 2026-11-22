# Mapper validation helpers

Run these commands from the capsule directory using the factory Python (`python` from its virtualenv). Each tool has `--help`.

## Inspect saved server logs

```sh
python helpers/check_markers.py on.server.log \
  --name batch_layout_mapper --require active --require layout --require stats
```

The JSON report includes matching log lines and their line numbers, missing required marker kinds and the effective `load_tensors` modes. Use `--require inactive --require stats` for the multi-slot control and review the reason and counts. Use `--load-mode mmap` when mapped weights are required. Missing required markers or a missing or mismatched requested load mode make the command exit nonzero.

## Run a greedy parity smoke probe

In an authorized real shell with port 5175 available, pass binary directories for a matching stock and candidate build. Use the same `MODEL` and server flags for all three arms.

```sh
python helpers/parity.py --stock /path/to/stock/bin \
  --candidate /path/to/candidate/bin --out smoke -- -ngl 0 -b 13 -ub 8
```

This template invokes `$FACTORY_ONE_SHOT` (default `~/predemo/one_shot.sh`). It runs stock and candidate with the mapper gate unset, then candidate with the gate set. The wrapper starts and stops servers and saves `<prefix>.json` and `<prefix>.server.log` per arm. The tool appends `-lv 4` and compares decoded content bytes, ordered token IDs and stop type. Apply the marker checker to the gate-on log even when parity passes. The default wrapper supplies one fixed cold prompt. Use the contract harness or an adapted `--wrapper` that accepts the same arguments for token-exact priming, multi-slot or full acceptance runs. Run the unit test in a worker sandbox, where the wrapper is a synthetic script.

## Generate the prompt-length sweep

```sh
python helpers/prompt_sweep.py
python helpers/prompt_sweep.py --lengths 7 8 9 16
```

Each JSONL record gives the target prompt length and shared prefix length in engine tokens. Tokenize using the admitted tokenizer and verify the actual server input length after any special tokens are included. The default matrix contains 28 cold and primed targets.

For a gate-unset arm, use `check_markers.py LOG --name batch_layout_mapper
--expect-silent`. It exits nonzero for any line carrying the prefix, including
unrecognized marker kinds.
