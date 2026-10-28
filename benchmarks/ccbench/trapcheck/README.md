# trapcheck: faulty research inputs, integrity checks replayed on stored native runs

## Origin (ccbench copy)

Copied from cc-sweep-20261026/trapcheck (sha256 in BASELINE-CODE-MANIFEST), changes:

- New README; `run.py` copied. `PRODUCT` path is now `AI4R_CODE_ROOT`; the traps folder is read from `AI4R_BENCH_DATA/traps` (848 MB, not copied; the 11 sessions it reads are under `traps/sessions/`).
- `run.py --out DIR` writes `results.json` there (it already wrote only that file, with bytes and LF). Output equals the old `trapcheck/results.json` byte for byte.
- The old `RESULTS.md` is not copied (it names the product commit `8f812400` and the old baseline; it stays with the evidence).
- There is no unit test for this bench; the stored `results.json` is the regression check.

Run everything through `scripts/ai4r-bench` (container `ai4r:cc-v1-baseline`, repo mounted read-only, output in `--out DIR`). Add `--host` to use the host Python. Env roots: `AI4R_CODE_ROOT` (product repo; default: this repo), `AI4R_BENCH_DATA` (old evidence root: traps, stored baselines), `AI4R_CODEX_BIN` (codex; default `codex` on PATH). Files written by the original harness had CRLF line endings on Windows; this copy writes LF, so compare old results after CRLF to LF.

```sh
sh scripts/ai4r-bench trapcheck --out OUT        # replay on the stored native runs; no model, same size at 1x1 and full
```

Runs the product's integrity checks (`jiuwenswarm.research.checks.integrity`: pin_matches, baseline_consistent,
units_consistent, no_stale_duplicate, bound_feasible, split_disjoint) and `checks.delivery_evidence.numbers_in`
on the 11 stored native JiuwenSwarm trap runs (`traps/sessions/`), and records which check stops which planted fault.
No model call, no docker. Reads `AI4R_BENCH_DATA/traps` and never writes there.

It answers whether the checks as they are in the product now still catch the faults the native agent missed or reported.
The checks come from whatever `AI4R_CODE_ROOT` holds, so the result moves when the product moves.
