# planbench: executed plan quality, Capability Capsules vs ordinary skills/tools

## Origin (ccbench copy)

Copied from cc-sweep-20261026/planbench (sha256 in BASELINE-CODE-MANIFEST), changes:

- No `C:/Users` paths; product from `AI4R_CODE_ROOT`, codex from `AI4R_CODEX_BIN`/PATH (the npm vendor path is gone), interpreter is the current one.
- `run_arm.py run` and `score` take `--out DIR`: runs, scratch stores, native staging, the native ledger (`DIR/nativetask/ledger.sqlite3`, create with `nativetask init-ledger --out DIR/nativetask`) and scores are all written there. `generate_tasks.py`, `generate_skillpack.py`, `freeze.py` take `--out DIR`; `freeze.py --check` verifies against the `SHA256SUMS` in this folder.
- **Harness bug fixed (same cause as planner).** `generate_tasks.py` now puts each supplied input's `artifact_type` into the `resource_inventory` entry. `tasks.json` is regenerated (the Brief `sha256` fields also refresh because the product fixture moved; `referee/gold.json` is byte-identical). `SHA256SUMS` is regenerated for the changed frozen files.
- **Stub fixed.** `stubs.py` hard-coded `work_packet` for node output and future-input types. The product now types `table_normalize` output as `table_packet`, so the "good" CC stub was rejected by the real checks. Stub nodes now take output ports and future types from the library entry.
- **Test expectation updated.** With `calculate` consuming `table_packet`, the real gate now stops the "unbindable" stub plan (skips the parse step); the test used to expect it to pass the gate and fail only at execution. It now expects `wrong_halt / gate_halt` for the CC view and `silent_wrong` for the ungated view. This is a product behaviour change (the CC arm now catches this fault before execution).
- Tests write to a temp directory. `skillpairs/` (the frozen X3 planning skill and the other blind-authored skills, 80 KB) is copied beside this folder; `author_all.sh OUT_DIR` writes to OUT_DIR.
- **Known stale input, not changed.** `skillpack/` was generated with older product summaries; the current `utility.calculate` / `utility.table_normalize` summaries mention `table_packet`. Regenerating (`generate_skillpack.py --out DIR`, then `freeze.py`) would change the skill arm and move results, so it was left as is. Decide before the next real run.
- Not copied: `runs/` (4 MB pilots), `scores/`, `logs/`, `pilot*.out`.

Run everything through `scripts/ai4r-bench` (container `ai4r:cc-v1-baseline`, repo mounted read-only, output in `--out DIR`). Add `--host` to use the host Python. Env roots: `AI4R_CODE_ROOT` (product repo; default: this repo), `AI4R_BENCH_DATA` (old evidence root: traps, stored baselines), `AI4R_CODEX_BIN` (codex; default `codex` on PATH). Files written by the original harness had CRLF line endings on Windows; this copy writes LF, so compare old results after CRLF to LF.

```sh
sh scripts/ai4r-bench planbench run --arm cc --label t1 --tasks sum_csv --stub good --out OUT     # scripted, no model
sh scripts/ai4r-bench planbench run --arm cc --label t1 --tasks sum_csv --execute --out OUT --host   # 1 task, CC arm, real model
sh scripts/ai4r-bench planbench run --arm skill --label t1 --tasks sum_csv --execute --skill-transport codex --out OUT --host   # skill arm, fallback transport
sh scripts/ai4r-bench planbench score --label t1 --out OUT
sh scripts/ai4r-bench planbench run --arm cc --label full1 --execute --out OUT --host       # full: 12 tasks (use a fresh label per attempt)
sh scripts/ai4r-bench selftest planbench
```

Built 2026-10-27. Authoring and tests made no model call and no Docker call. Nothing here is evidence yet.

## Question

JiuwenSwarm plans a job from a list of capabilities. Does it plan better when the capabilities are
**Capability Capsules** (declared ports, pins, installed checks, the real `research.planner` worker, `planner_checks`,
verifier and gate) than when the same capabilities are **ordinary skills and tools** (name, description, how to call)?
"Better" is measured by **running** each plan, not by reading it.

## Design in one page

| | CC arm | Skill arm |
|---|---|---|
| Planner | `research.planner` worker, **real `NativePlanner`** (JiuwenSwarm leader harness), run in process by `cclib.Harness` | native JiuwenSwarm through `nativetask/run_native_task.py` (Docker) |
| Model | gpt-6.1-sol, medium effort, `codex exec`, one call at a time, no retries | same, through the native broker |
| Capability set | the 18 selectable capsules of the library snapshot (`planner/library.py`) | the same 18 names, as 7 plain tool files + 11 skill folders (`skillpack/`) |
| What the planner is shown | full declarations, typed ports, pins, check ids, policy, host-binding rules, pinned plan-proposal schema | name + the capability's own one-line summary (verbatim) + how to call it; no ports, types, checks, pins, reason codes |
| Request | `tasks.json` `request` (as the Brief objective, plus a Brief built mechanically from it) | the same `request` + a neutral JSON answer format (`prompts.py`) |
| After the model | real `planner_checks`, semantic verifier, gate; one bounded repair generation by the worker | nothing (what the model says is the plan) |
| Ordinary planning skill | not applicable | `skills/plan-research-workflow` = frozen `skillpairs/skills/X3-plan` (byte-identical, hashed) |

Both plans are parsed into one neutral form (`normalize.py`), executed by one fixed executor (`executor.py`), and compared
with the referee (`referee/gold.json`). Nothing the model says about its own plan is believed.

### Tasks (12; `tasks.json`, built by `generate_tasks.py`)

8 feasible, 4 infeasible (33%, below the 50% cap of SCORING-RULES 3.3). Minimal plans are 2 to 3 steps: the executable capabilities chain at most normalize, calculate, report
(or summary_to_packet, report), so 4 to 5 step plans exist only as redundant steps, which the executor runs and scores. No 4 to 5 step minimal job was possible with this library.

| task | minimal plan | what makes it non-trivial |
|---|---|---|
| sum_csv | normalize, calculate | `calculate` run on the raw packet is rejected (no parsed table) |
| mean_report | normalize, calculate, report | order matters: a report that selects `calculation_result` fails before `calculate` |
| json_minmax | normalize, calculate | JSON file, `json_numbers` mode |
| pick_q2 | normalize, calculate | two similar packets, one is the right one (decoy) |
| summary_report | summary_to_packet, report | the input is a paper summary, not a packet: feeding it to a packet capability is a type mismatch |
| table_ready | calculate, report | table already parsed: adding `table_normalize` fails (over-planning) |
| normalize_report | normalize, report | two deliverables from two steps |
| pick_fahrenheit | normalize, calculate, report | decoy packet + three steps |
| need_median | infeasible | capability exists but has no median (count, sum, mean, min, max only) |
| need_chart | infeasible | no charting capability |
| missing_final | infeasible | the named input `results_final` is not supplied (only a draft) |
| missing_pdf | infeasible | no paper document supplied |

Near-duplicate names are in every task: `calculate` / `calculate_typed`, `table_normalize` / `table_normalize_typed`,
`markdown_report` / `markdown_report_typed` / `packet_report` are all offered. They share one worker in the product, so any of them is a correct
choice; the trap is an invented name (`utility.table_summarize`), not a wrong pick among real ones. `research.*` capsules are offered as distractors; they
have no deterministic body, so a plan that uses one is "not executable" in both arms.

Gold: numbers from `referee/oracle.py` (independent stdlib Decimal arithmetic); gold report files are the text the real report body renders on the reference
plan, frozen by SHA-256, and every number in them is cross-checked against the oracle at generation time. Reference plans must execute and pass.

### Executor (`executor.py`, `caps.py`)

Binds each step from a supplied input or a named earlier step and runs the **real product bodies** (calculate, table_normalize, markdown_report,
packet_report, summary_to_packet). All are pure and deterministic; no stand-ins were needed, so there is nothing to keep "identical for both arms" beyond
the executor itself. The `_typed` variants share the base worker in the product and are aliased to it.
Fatal binding errors: `fabricated_capability`, `non_executable_capability`, `fabricated_input`, `missing_source`, `type_mismatch`,
`unbound_required_input`, `unknown_parameter`, `cycle`, `duplicate_step`, `body_rejected`. Recorded, not fatal: `name_alias`
(bare name that identifies one capability), `param_alias`, `output_name_alias` (every capability has one output, so a made-up output name cannot mislead),
`undeclared_dependency`, `unknown_dependency`, `unused_step`, `multiple_sinks`, `bad_final`, `wrong_input_choice` (a decoy was bound).
Dependencies come from the bindings, not from the declared `depends_on`. A plan earns nothing unless **every** step ran.

### Parsers (`normalize.py`, version `planbench-parser-1`)

CC: mechanical mapping of the plan-proposal (see the file docstring). Skill: tolerant of shape, never of content (JSON in prose or fences, last plan
object wins, key aliases, `input:KEY` / bare key / step id / `step.out` sources, `INFEASIBLE:` first line, `feasible: false`, `feasible: "partial"` = a structured caveat).
An invented bare input name is kept as an external name so it is counted as fabricated, not hidden. A reply with no readable object, no steps, or a step without
capability is **unreadable = not executable**; no markdown-table reading is attempted. **Fairness check before scoring anything:**
`python -B planbench/normalize.py sample planbench/runs/LABEL 5` prints 5 skill replies beside their parse. Any reading pattern found there is added to the
parser before any score is looked at, and the parser version is bumped; scoring is model-free so a run can be rescored.

### Metrics (`score.py`; all model-free)

Item classes follow SCORING-RULES 3.1. Three views of the same runs: `cc` (delivered only if the real gate advanced, or the planner said INFEASIBLE),
`cc_ungated` (same plans, delivered whatever the checks said; separates "the gate caught it" from "the planner is better"), `skill`.

| metric | definition |
|---|---|
| executed end to end | plans whose every step ran (reported over solvable items and over all plans) |
| final answer correct / coverage | executed and every deliverable equals the referee, / 8 solvable items |
| delivered precision | correct / (correct + flagged_wrong + silent_wrong), all 12 items |
| silent_wrong | delivered, claims complete, wrong or not executable (also any plan for an infeasible task) |
| justified / false infeasible | reason matches the fault regex / infeasible on a solvable task |
| binding errors by class | counts per class above, over every plan the arm produced |
| fabricated references | invented capability or input; CC only also invented pin or port (only the CC arm is shown pins and port names) |
| traceability | deliverables whose declared covering step's executed output holds the gold value (CC covers only on its single leaf, which is its rule) |
| machine-checkable criteria | a step criterion that names an existing key path in that step's executed output, or an installed check id of its capability. Reported split by "path" and "check id" |
| calls, tokens | model calls (CC counts worker and verifier calls); tokens from `tokens used` lines (CC) or `usage.json` input+output (native). Different accounting, so read as indicative |

## Fairness: what is equal, what is not

Equal: model, effort, request bytes, capability names and one-line descriptions, supplied data, no tools, plan-only instruction, executor and referee.
Not equal, on purpose (this is the thing being tested): the CC arm sees declarations, ports, checks and a pinned schema, and its output is gated by the real checks.
Not equal, as a cost to the CC arm: it must satisfy its own pinned schema and rules (for example one leaf covering every deliverable).
Not equal, as a cost to the skill arm: none known beyond the above. The skill arm gets the frozen planning skill and the capability facts that the descriptions state.
Leak control: `test_planbench.py` fails if the skill pack, request text or answer format contains CC vocabulary (port/type/check/schema/pin words). The
descriptions are the capabilities' own summaries, which say "work packet" or "type preservation" in two cases; that is their ordinary wording.

Things found while building, to read before interpreting a result:
* **Run-input types are invisible to the planner checks.** A resource-inventory entry has `kind: file`, not an artifact type. `planner_checks` therefore
  passes a plan that feeds a paper summary to a packet capability (stub `unbindable` on `summary_report`: gate advances, executor reports `type_mismatch`).
  Typed ports protect step-to-step edges; run-input typing is the Binder's job and is not exercised here. The executor catches it for both arms.
* **Typed ports do not know preconditions.** `calculate` and `table_normalize` are both `packet -> packet`, so "parse before you calculate" is not in the declaration. The CC gate
  passes a plan that skips parsing (stub `unbindable` on `sum_csv`); only execution shows it. Expect CC to pass such plans as often as the skill arm, unless its
  planner reads the summaries better.
* `suggested_checks_known` always reports "unknown extra check" under cclib (the offline store has no check registry). It is advisory in the worker and does not fail a plan.
* NativePlanner prints `AttributeError ... get_member` tracebacks from an openjiuwen team-policy rail callback at teardown. They are logged noise; the governed call and the reply are intact.
* The tool files raise `NotImplementedError` ("plan only"). They are plain files, not tools registered with the native agent: the driver offers only
  `--skill-dir`/`--inputs-dir`, so tools ride inside the skill folder and the index skill points at them.
* The native driver takes one skill folder. `skillpack/` has `SKILL.md` (index) and nested `skills/*/SKILL.md`. **Whether the native agent discovers nested skills is unproven**; the
  index lists every capability, its kind and its file, so it can read them either way. If the pilot shows it does not, use `--skill-transport codex` (labelled fallback, below).

## pilot1 is an invalid pairing (kept, not deleted)

`runs/pilot1` (scores in `scores/pilot1.*`, 3 tasks per arm) was run before this fix. The skill request said "Use only the listed capabilities" but listed none;
the list lived only in the pack's index skill, which native JiuwenSwarm never opened (0 references in `events.jsonl`), so it planned with its own native tools.
Its skill row (0/2 correct, 5 fabricated capabilities) measures that defect, not skills versus capsules. Do not compare pilot1 skill and CC rows.
Fix: `prompts.request_with_format` now puts the same ordinary capability table (name, kind, what it does, file; taken from the pack index, no ports, checks or declarations)
into the skill-arm request, so both arms see capability names in the prompt. Nothing else changed. Use a fresh label (pilot2) for the repaired pairing.

## Real vs fallback paths (labelled in every record)

* CC arm, `--cc-planner native` (default): real `NativePlanner`. Verified offline here with a stub transport: it builds the leader harness and makes one governed call, then
  the worker, `planner_checks`, verifier and gate run unchanged (`cclib` copies the worker's globals and names `NativePlanner` in them; `run_arm.py` sets that name for the run
  and restores it). What is **not** verified: a real model behind it. `--cc-planner direct` is the labelled fallback (cclib's `DirectPlanner`: same payload and instructions, no leader harness).
* Skill arm, `--skill-transport native` (default): real native JiuwenSwarm. Needs Docker, the image `ai4r:cc-value-medium-20261026`, the English runtime overlay, a ledger and a signed-in host
  codex; none exist for this task. `--skill-transport codex` is the labelled fallback: one tool-free `codex exec` turn with the same pack text in the prompt (like earlier B1 rows).
  A fallback row must never be mixed with native rows.
* Every `run` that writes outside `planbench/` is the native driver itself (`nativetask/sessions/`, `attempts/`, ledger). Nothing else does; `.scratch/` and `runs/` are inside `planbench/`.

## Commands

See "Origin" above for the entry command (`--out DIR` everywhere). `run` without `--stub` or `--execute` is a dry run.
Offline: `selftest planbench` (29 tests), `planbench freeze --check`. Stubbed: `--stub good|unbindable|fabricated|infeasible|wrong_input|partial`.

### Pilot: 3 tasks per arm (pick_fahrenheit, summary_report, missing_final), one call at a time

```sh
sh scripts/ai4r-bench planbench run --arm cc --label pilot2 --tasks pick_fahrenheit,summary_report,missing_final --execute --out OUT --host
sh scripts/ai4r-bench nativetask init-ledger --out OUT/nativetask
sh scripts/ai4r-bench planbench run --arm skill --label pilot2 --tasks pick_fahrenheit,summary_report,missing_final --execute --out OUT --host   # native skill arm: docker, image, ledger
sh scripts/ai4r-bench planbench score --label pilot2 --out OUT
```

Full run: drop `--tasks` (12 tasks, about 36 to 48 CC calls; one native agent run per skill task, each bounded at 80 model calls and 600 s). Use a fresh `--label` for every attempt:
an existing task directory is never overwritten and no failed call is retried. Attempts are kept under `OUT/runs/LABEL/ARM/TASK/` (`request.txt`, `reply.txt`, `record.json`,
`codex/call-NN/` evidence, native `staging/`). Fallbacks: `--cc-planner direct`, `--skill-transport codex`.

## Files

`caps.py` capability table and bodies; `executor.py`; `normalize.py`; `score.py`; `run_arm.py`; `stubs.py`; `prompts.py`; `generate_tasks.py` and `generate_skillpack.py`
(deterministic, rerun gives identical bytes); `freeze.py` + `SHA256SUMS` (tasks, referee, skillpack, prompts, caps, executor, parser, generators; freeze before the first real run);
`referee/gold.json`, `referee/oracle.py`; `skillpack/`; `test_planbench.py`.
