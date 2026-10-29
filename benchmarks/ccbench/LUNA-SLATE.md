# Luna test slate

Model + JiuwenSwarm (theirs: `plain`, `careful`) against model + JiuwenSwarm + AI4Research capsules (ours: `cc`), all on `gpt-6-luna`.

## The one command

```sh
sh scripts/ai4r-bench slate luna --out DIR                                  # everything, serial
sh scripts/ai4r-bench slate luna --out DIR --only T1,T2                     # some tests
sh scripts/ai4r-bench slate luna --out DIR --doctor-only                    # check the machine and the selftests, then stop
sh scripts/ai4r-bench slate luna --out DIR --arm rsi=rsi.json               # add an arm (RSI) next to the existing ones
```

What it does, in order:

1. **Doctor.** Codex binary (`AI4R_CODEX_BIN` or `codex` on PATH), Docker, image `ai4r:ccbench-native`, the T2 fixtures (`AI4R_T2_FIXTURES`), then the selftests of the selected tests. It stops with the exact fix.
2. **Preflight.** One unit per test and arm (first case, 1 rep). A failure stops the slate before any long block.
3. **Blocks, one model job at a time** (parallel jobs on one codex account hit HTTP 429): T1 nativeadmit (12 items x 2 reps), T2 inputguard (11 fixtures), T3 heldout then contract, T4 haltbench, T5 planner with `--skill-detail full`. `--reps 1` everywhere except T1.
4. **Score.** `DIR/SUMMARY.md` and `DIR/summary.json`: per test and arm the correct, wrong, stopped and false-stop counts; mean input, output and total tokens; calls; wall time; tokens per correct answer; commit, image id and model.

Rerun the same command to resume: a unit with an attempt record or result file is skipped. T1 uses the folder names of the luna T1 that is already running (`A-native-luna` plain, `A-verify-luna` careful, `A-cclive-luna` cc, inputs in `A-verify-inputs` and `A-cc`). Point `--out` at `rebench-20261028` and those finished sessions are adopted, not rerun.

Logs: `DIR/logs/NNN-label.log`, one per command.

## One line per bench (the individual commands)

Arms: T1 plain / careful / cc; T2 plain / careful / cc; T3 and T4 plain / verify / (selftest) / cc; T5 A (declared capsules) / B (skill files).
RSI line = the same command pointed at the RSI library or code. `$R` is the repo, `$O` the output folder.

| Bench | Run | RSI arm |
|---|---|---|
| T1 nativeadmit | per item and rep: `sh scripts/ai4r-bench nativetask run --task-file I/task.txt --inputs-dir I --ledger L/ledger.sqlite3 --attempt-id ITEM-rN --model gpt-6-luna --image ai4r:ccbench-native --execute --out $O/A-NAME` with `I` = `nativeadmit/items/ITEM/public` (plain), `$O/A-verify-inputs/ITEM` (careful), `$O/A-cc/cc-live/ITEM` (cc). Build the cc inputs with `python -B benchmarks/ccbench/nativeadmit/cc_route.py --out $O/A-cc` then `python -B benchmarks/ccbench/nativeadmit/cc_live_inputs.py --out $O/A-cc`. | `cc_route.py --out $O/A-rsi`, then `cc_live_inputs.py --out $O/A-rsi --served SERVED_DIR`, then the same run with `I` = `$O/A-rsi/cc-live/ITEM` and `--out $O/A-rsi-run`. `SERVED_DIR` holds `calc_tool.py` and `table_tool.py` (the served versions). Slate: `{"t1": {"served": "SERVED_DIR"}}`. |
| T1 score | `python -B benchmarks/ccbench/nativeadmit/score_arms.py --arm plain=$O/A-native-luna --arm careful=$O/A-verify-luna --arm cc=$O/A-cclive-luna --out $O/T1/score` | add `--arm rsi=$O/A-rsi-run` |
| T2 inputguard | `python -B benchmarks/ccbench/inputguard/prepare.py --out $O/T2` then `sh benchmarks/ccbench/inputguard/collect.sh $R $O/T2` (env `MODEL`, `ARMS`, `FIXTURES`) | `ARMS="rsi=cc" CODE_ROOT=/path/to/rsi/checkout sh benchmarks/ccbench/inputguard/collect.sh $R $O/T2`. The guard is product code, so the hook is the code root (`--code-root` of `run_guard.py`; `AI4R_CODE_ROOT` does the same). Slate: `{"t2": {"code_root": "CHECKOUT"}}`. |
| T2 score | `python -B benchmarks/ccbench/inputguard/score.py --arm plain=$O/T2/plain --arm careful=$O/T2/careful --arm cc=$O/T2/cc --out $O/T2/score` | add `--arm rsi=$O/T2/rsi` |
| T3 heldout | `sh scripts/ai4r-bench heldout run --execute --reps 1 --model gpt-6-luna --host --out $O/modelbench/heldout`, then `... heldout score --model gpt-6-luna --host --out ...` | none (see below) |
| T3 contract | `sh scripts/ai4r-bench contract run --execute --reps 1 --model gpt-6-luna --host --out $O/modelbench/contract`, then `score` | none |
| T4 haltbench | `sh scripts/ai4r-bench haltbench run --execute --reps 1 --model gpt-6-luna --host --out $O/modelbench/haltbench`, then `score` | none |
| T5 planner | `sh scripts/ai4r-bench planner run --model gpt-6-luna --repeats 1 --skill-detail full --resume --execute --host --out $O/T5`, then `planner score --model gpt-6-luna --host --out $O/T5` | none |

### Why heldout, contract, haltbench and the planner take no `--arm-config`

Their arms are fixed prompt and check code, and the check material (gate suites, output contracts, obligation list) is in the frozen `cases.json`, hashed in `MANIFEST.sha256`. They load no capsule library or served folder, so an RSI-changed capsule library has nothing to enter through. A new arm there would be a new bench stand-in, which is a code and gold change, not a setting. The slate refuses those keys and says so. If RSI changes a gate or a contract itself, give it its own frozen cases file and its own bench run; do not hide that behind a flag.

## Token split

- nativetask sessions: `cost.session_usage(session)` reads `usage.json` (else the broker receipts) into input, output, total, calls and wall time. Real shape checked on `ccbench-20261028/A-full`.
- heldout, contract, haltbench, planner: `modelbench.parse_usage` records `input_tokens` and `output_tokens` per call **only when codex prints them**. The codex 0.162.1 output in the saved runs prints only `tokens used` and a total. So today those benches record the total and leave the split `null`. Nothing is derived from the total. If codex gains a split line (`input tokens: N`, `output tokens: N`), it is picked up with no change. `call_cost` sums the split only when every call has it.
- Tokens per correct answer = all tokens of the arm / correct deliveries. It is `null` when any run of the arm has no total (the table then shows a labelled partial figure).

## T5 `--skill-detail full`

`names` (default) is byte-identical to the old arm B prompt. `full` adds, after the skill listing, the text of one skillpack file per library capability (`planbench/skillpack`):

- `utility.calculate` and the other tool-style `utility.*` capabilities map to `tools/utility_<name>.py`.
- Other capabilities map to `skills/<name with . and _ turned into ->/SKILL.md` (for example `research.paper_summary` to `skills/research-paper-summary/SKILL.md`).
- The pack index and the planning skill are not added. A capability with no file stops the run.

Important limit: the skillpack was generated from the same one-line summaries. Its tool files are stubs that raise `NotImplementedError`, and its skill files are a few lines each. `full` adds about 9.6 KB to arm B (15.8 KB to 25.4 KB), against about 300 KB for the declared arm A. It is not "whole tool code". Report it as "skill files as packaged".

`--resume` (new) lets one `--out` hold a preflight task and then the full run: it keeps the run folder and runs only units without a `run.json`.

## T2 limits

The guard is `jiuwenswarm/research/checks/integrity.py`, loaded read-only by file path (stdlib only, so no product store is needed). On the 11 fixtures it halts 5 (pin, units x2, stale, bound). It cannot halt on `baselinedef-cb69e06d` (needs the baseline replay output), `conflicts-e6830418` and `overreach-1fdc5eaf` (no check exists), or `clean-7fb8e068`, whose baseline pin mismatch is only visible in a run. The score treats `clean-7fb8e068` as a fault fixture (cause `baseline_pin_mismatch`); delivering on it counts as wrong. Those misses stay in the table.
