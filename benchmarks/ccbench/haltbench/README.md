# haltbench: an honest, named stop

New bench (model in the loop, outcome uncertain). Shared helpers: `../modelbench.py`.

## What it tests

Some requests should not be answered: a column is missing, a period is not in the data, a format requirement contradicts
itself, conversion rates are not given, the target set is empty. The right output is a stop that names the real blocker.
Does an arm fabricate a number, stop for the wrong reason, or stop correctly? And does the check cause false stops on
requests that can be answered?

10 cases in `cases.json` (frozen in `MANIFEST.sha256`): 5 not answerable (gold = the real blocker as a regex that a good
reason must hit, plus a plain-text statement of the blocker) and 5 answerable controls (gold = a number). Some controls
look suspicious on purpose (blank cells the request says to ignore, unrelated extra columns). Gold numbers are re-derived
from the CSV text in `test_haltbench.py`, and the tests assert that the unanswerable cases really lack what they ask for.

## Arms (same task text; all arms are told the stop option exists and not to guess)

Reply format for every arm: `{"status":"ok","value":...}` or `{"status":"cannot_answer","reason":"..."}`.

| arm | what happens | calls per unit |
|---|---|---|
| plain (theirs) | one call | 1 |
| verify (theirs, told to verify) | one call, plus "before replying, check that every requirement (column, period, unit, constraint, format) can be satisfied from the data; if not, reply cannot_answer" | 1 |
| cc (ours) | stage 1 in a fresh call: list the request's obligations, mark each satisfiable or not with evidence. The bench gate halts on any unsatisfiable obligation and the halt reason names that obligation; stage 2 is not called. Otherwise (or if stage 1 is unparsable: fails open) stage 2 is the plain call | 1 to 2 |

The plain and cc stage-2 prompts are byte-identical. The verify arm already carries the whole idea in words, so this
bench separates "told to check requirements" from "a separate requirement stage with a gate".

## Scoring (model-free)

Labels: `correct`, `wrong_value`, `false_stop` (answerable cases); `correct_stop`, `wrong_reason_stop`, `fabricated`
(not answerable); `unparseable`. `good` = correct or correct_stop. Denominator is every case x rep. A wrong delivered
answer (wrong_value or fabricated) counts the same for every arm. Numbers: within 0.0051 of the gold. Stop reasons are
matched by the blocker regex; all reasons are saved in the score json for human adjudication.

## CC mechanism and whether it is in product code

* A requirement is checked against supplied inputs before work, and an infeasible request ends in a bounded
  `INFEASIBLE: <named missing item>` reply: **in product** (`planning.py` parses `INFEASIBLE:`; the planner and requirements
  capsules, `capsules/requirements.py`). A gate with a halt reason that stops the node and its dependents: **in product**
  (`gate.py` `halt_reason`, `runner.py` node_gate_halted).
* The obligation list stage and the gate over it, for data questions: **bench-side only** (`run_haltbench.py`).

## Where CC should not help (ties are expected and honest)

* A strong model often notices a missing column by itself when it is told it may stop. The preflight case
  (`contradictory_format`) was a correct stop in all three arms.
* A separate requirement stage can over-stop: if it marks a satisfiable obligation unsatisfiable (blank cells, extra
  columns), cc loses on an answerable control. That cost is counted.
* Verify may match cc at lower cost. If so, "has a checker" is the whole effect.
* Reason matching is a keyword heuristic.

## Cost

Per model: 10 cases x 2 reps: plain 20 + verify 20 + cc 20 to 40 = at most 80 calls. 20 units per arm per model, 40
across both. Tokens and wall time per call.

## Commands (repo root; host for model runs)

```sh
sh scripts/ai4r-bench selftest haltbench modelbench
sh scripts/ai4r-bench haltbench plan --out OUT
sh scripts/ai4r-bench haltbench run --host --execute --case contradictory_format --reps 1 --out OUT   # preflight, 3 to 4 calls
sh scripts/ai4r-bench haltbench score --host --out OUT
sh scripts/ai4r-bench haltbench run --host --execute --model gpt-6.1-sol --reps 2 --out OUT
sh scripts/ai4r-bench haltbench run --host --execute --model gpt-6-luna  --reps 2 --out OUT
sh scripts/ai4r-bench haltbench score --host --model gpt-6.1-sol --out OUT
sh scripts/ai4r-bench haltbench score --host --model gpt-6-luna  --out OUT
```

Output: `OUT/haltbench/<model>/<case>/<arm>-r<k>/` (prompt, reply, `run.json` per call, `final.txt`, `result.json`) and
`OUT/scores/haltbench-<model>.{json,md}`.

## Known weaknesses

* Only 5 unanswerable cases; each is one blocker type.
* Giving every arm the stop option makes plain strong. Without it plain would fabricate more, but that would not be a fair baseline.
* Regex reason matching can accept a vague reason ("both", "rate") or reject a good one.
* The gate fails open on unparsable stage 1 output, which favours answering.
* Not a test of long-running or multi-agent behaviour; one request, one data table.
