# CC experiments of 10-28: cases, scripts, baseline results, and how to rerun them with RSI

This folder holds what produced the Capability Capsule (CC) numbers in the AI4R QA report (Part B, section 01, and appendix A5), and how to rerun those experiments with an RSI-improved capsule as an extra arm. The test cases, reference answers and scorers live in the bench folders next to this one. This folder adds:
- the run scripts;
- the rebuilt inputs for case B's other arm;
- the baseline results to compare against.

Code: run everything from the repo root of branch `ai4r_M1plus`. The reported runs used commit `a8d8fb89` (`71fc1759` for T1 and `5db04b50` for the luna slate; both are ancestors). Later commits only add opt-in options (the capsule-over-MCP arm, the `AI4R_BRIDGE_SYSTEM` bridge message, slate `t1` keys); with none of them set, the run path is the one the reported runs used. Each stored run records its commit in `run-meta/`.

## The goal for the RSI rerun

RSI improved two capsules: `utility.calculate` and `utility.table_normalize`. Those are the two tool families in experiment T1, "verified tools, live agent". So the clean test is:

> Same model, same tasks, same JiuwenSwarm image. Add a fourth arm that serves the RSI versions of the tools through the same capsule route. Compare with plain, careful and cc.

The comparison chain:
- **plain**: model + JiuwenSwarm (theirs).
- **cc**: model + JiuwenSwarm + capsules (ours).
- **rsi**: the same as cc, but the capsule serves the RSI-improved tool.

## Step by step (T1 with an RSI arm)

1. **Prerequisites.**
   - Docker.
   - A signed-in Codex CLI with a ChatGPT account. Check with `codex login status`.
   - The image: `sh scripts/ai4r-bench build-native --yes --out <dir>`. It builds `ai4r:ccbench-native` from `deploy/m1/Dockerfile.app`. The reported runs used `sha256:0d0941949c66...`.
2. **Put the RSI tool versions in one flat folder**, e.g. `C:/rsi-served/`. It must contain `calc_tool.py` (the RSI calculate) and `table_tool.py` (the RSI table_normalize).
   - Use the same file names and call interface as `benchmarks/ccbench/nativeadmit/items/calc_reference/public/calc_tool.py` and `.../table_reference/public/table_tool.py`.
   - A missing file stops the run; there is no silent fallback.
3. **Check the inputs without spending model calls:**
   ```
   DRY=1 sh benchmarks/ccbench/runs-20261028/run_t1.sh C:/t1-rsi C:/rsi-served
   ```
   This builds `cc-route/` (contract tests on every team tool), `cc-route/cc-live/` (the capsule-served inputs), `rsi-route/cc-live/` (the same, with your served versions) and `careful-inputs/`.
   - Sanity check: if you pass the two reference tools as the served folder, `rsi-route` comes out identical to `cc-route`.
4. **Run:**
   ```
   sh benchmarks/ccbench/runs-20261028/run_t1.sh C:/t1-rsi C:/rsi-served
   ```
   - Default: 8 items x 1 rep x 4 arms = 32 runs, about 1 minute each.
   - The arms take turns per item.
   - Settings: `REPS=2` for more repeats; `MODEL` and `EFFORT` (default gpt-6.1-sol, low); `ITEMS` for a subset.
   - Keep the output path free of spaces.
   - Rerunning the same command resumes; finished attempts are skipped.
5. **Read the result.** The script ends by printing `score/score-arms.md`: class counts and token cost per arm.
   - Compare with `baseline/T1-sol-low/score-arms.md`: CC 0 wrong of 8, plain 1, careful 2.
   - Scoring is model-free (`nativeadmit/score.py`).

### What the RSI arm can and cannot show
- **What changes.** The served version is used only on items whose team tool was rejected: the 6 broken ones in the default 8. On the 2 correct items, every arm uses the item's own tool.
- **Correctness.** It should stay at cc's level: 0 wrong. The RSI rule demands byte-identical output.
- **Speed.** It shows up in wall time, not in the answer. T1 records `wall_s` per run, but agent runs are dominated by model time. Do not expect the RSI speed-up to be visible here. The RSI speed claim belongs to the RSI bench.
- **The fair claim if rsi matches cc on correctness:** RSI-changed capsules keep the guarantees, and they go through the same capsule route without a code change.

## Other experiments and their RSI hooks

| Experiment (report case) | Rerun | RSI hook |
|---|---|---|
| A, larger set (12 tasks x 3 reps, theirs) | `as-run/A-full-collect.sh <repo> <out>` | none needed: ours there is the contract test, no model |
| A, our side, and C (contract tests before use) | `sh scripts/ai4r-bench nativeadmit cc_route --out OUT` · `sh scripts/ai4r-bench admission study --reps 10 --out OUT` | to test an RSI tool against the contract, put it in place of the reference tool in a scratch copy of the repo and run `cc_route` on that item: it must be admitted |
| B (faulty inputs, our checks) | `sh scripts/ai4r-bench trapcheck run --out OUT` with `AI4R_BENCH_DATA` pointing at the stored 10-26 sessions (in the evidence zip, `evidence/cc/bench-data/cc-sweep-20261026`; 543 MB, not in git) | the checks are product code: point `AI4R_CODE_ROOT` at an RSI checkout |
| B (theirs, rerun of JiuwenSwarm on the same fixtures) | `as-run/B-native-collect.sh <repo> <out>`, fixtures in `b-native-fixtures/fixtures/`, scorer `b-native-fixtures/score_native.py`; see `b-native-fixtures/RECONSTRUCTION.md` | none |
| D (gate for self-changes) | `sh scripts/ai4r-bench gatebench run --seeds 20 --out OUT` | this is a simulated RSI stream; real RSI proposals can be fed through the same gate |
| E (independent checker) and the luna work-in-progress benches | `sh scripts/ai4r-bench slate luna --out DIR` | `--arm NAME=CONFIG`; see `../LUNA-SLATE.md`. Heldout, contract, haltbench and the planner take no capsule library, so RSI has no entry point there |

## Baseline results (what the report shows)

`baseline/` holds the scored results of every reported experiment, plus `CHECK.md` and `all-runs.csv`, which recount every report number from the raw files. The raw runs themselves are about 1 GB: sessions, model trajectories and JiuwenSwarm logs. They are in the evidence zip that goes with the report (`evidence/cc/raw/`), not in git.

## Known pitfalls
- **One model job at a time.** Parallel jobs on one Codex account hit HTTP 429.
- **One ledger per attempt.** A ledger's wall budget covers one attempt; reusing it fails at setup with "insufficient ledger wall budget". `run_t1.sh` already makes a fresh ledger for every attempt.
- **No spaces in data paths.** The launcher passes them to `docker run`.
- **The codex account check can time out.** On 10-28 evening every run failed at setup with `TimeoutError` in `harbor_suite/value_host.py:account_pin`, while `codex login status` answered instantly. The cause was not found. If you see it, the failed attempts used no model calls; delete them and retry.
- **gpt-6-luna is not usable for T1.** It makes no tool calls under the native bridge.

## Files
- `run_t1.sh`: the portable T1 runner, with an optional RSI arm.
- `as-run/`: the exact scripts of the 10-28 runs, with this machine's paths. `t1low.sh` is T1; `queue2.sh` builds the careful inputs; `det.sh` covers B, C, D and A-cc; `modelbench.sh` is the luna benches.
- `b-native-fixtures/`: the 11 fixtures for B's JiuwenSwarm arm (8 faults + 3 clean), with their reconstruction notes and scorer.
- `baseline/`: scored results, `CHECK.md` and `all-runs.csv`.
