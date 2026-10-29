# heldout: held-out check plus one retry with the reason

New bench (model in the loop, outcome uncertain). Not a copy of an older bench. Shared helpers: `../modelbench.py`.

## What it tests

A worker writes a small Python function from a spec. Does a check that was written separately from the worker, with
one retry that carries the failure reason, give more hidden-test passes than the model alone, than the model told to
verify, and than the model checking itself with its own tests?

The spec for each of the 10 functions is exact but has traps (touching intervals, 1.0 equals 1.0.0, ties rounded away
from zero, multi-digit run lengths, a half-open date range, escapes inside string literals). Gold = two disjoint suites
per case in `cases.json`, written by hand from the spec sentence before any model call:

* `gate` (4 tests): what the CC arm's check runs and may quote in its retry.
* `score` (6 to 10 tests): never shown to any arm and never used by any check. The final pass or fail is decided here.

`reference.py` (independent implementations, never shown to a model) must pass all of both suites; `test_heldout.py`
asserts it. `cases.json` is frozen with `MANIFEST.sha256`; `run` refuses to start if it differs.

## Arms (same task text, same model, tool-free codex, empty directory)

| arm | what happens | calls per unit |
|---|---|---|
| plain (theirs) | one call: write the function | 1 |
| verify (theirs, told to verify) | same, plus "check your function against the spec and its edge cases and fix errors before you answer" | 1 |
| selftest (theirs, any checker) | the model returns the function and its own assert script; the bench runs the model's script; on failure ONE retry carrying the model's own failure text | 1 to 2 |
| cc (ours) | one call as plain; the bench runs the separate gate suite; on any failure ONE retry carrying the failing inputs, expected and actual values (up to 3) | 1 to 2 |

The cc first prompt is byte-identical to plain. All arms get the same retry budget (one) where they have a checker.
The final answer is the retry answer even if it is worse (a retry can break a correct first answer; `broken` counts it).

## CC mechanism and whether it is in product code

* Separately written deterministic checks run on a worker output, with PASS or FAIL and a reason: **in product**
  (`jiuwenswarm/research/checks/engine.py`, per-capsule `checks.py`, for example `capsule_extensions/calculate_v3/checks.py`
  recomputes the result from the original values).
* One repair generation that carries the validation errors: **in product** for the planner only
  (`capsules/planner.py`, "Two generations inside one work invocation", `repair={'previous_candidate','validation_errors'}`).
* Running such a check on model-written Python functions, with an inline gate suite: **bench-side only**
  (`checker.py`, `run_heldout.py`). Not a product capsule.

## Where CC should not help (ties are expected and honest)

* Easy functions that the model gets right the first time. A gate that never fails never retries; cc then equals plain.
  On gpt-6.1-sol several of these 10 may be solved by every arm. The preflight case (`round_half_up`) was.
* The gate can only help if the worker is wrong in a way the gate tests catch. A bug outside the gate suite is not
  caught and the retry reason does not mention it.
* A strong model told to verify may fix the same bugs without a checker. That is the verify control. If verify equals cc,
  "having a checker" is not CC.
* The retry shows gate expected values, which leaks part of the answer. The score suite is disjoint to limit this,
  but a retry that learns a rule from the gate examples is a real effect of the check, not noise.

Expected shape: little to see on gpt-6.1-sol; more room on gpt-6-luna (the check does not depend on the model, the
model's own vigilance does).

## Cost

Per model, full collection: 10 cases x 2 reps x 4 arms = 80 first calls plus at most 40 retries (cc, selftest) = at most
120 calls. Cases x reps per arm: 20 per model, 40 for both models. Tokens and wall seconds are recorded per call
(`run.json`) and summed per arm in the score table.

## Commands (run from the repo root; model runs use the host: `--host`, codex login, `AI4R_CODEX_BIN` or `codex` on PATH)

```sh
sh scripts/ai4r-bench selftest heldout modelbench                       # no model
sh scripts/ai4r-bench heldout plan --out OUT                            # prompt digests, no model
# one case, one rep per arm (preflight): at most 6 calls
sh scripts/ai4r-bench heldout run --host --execute --case round_half_up --reps 1 --out OUT
sh scripts/ai4r-bench heldout score --host --out OUT
# full collection, both models (resumes: finished units are skipped; use a fresh OUT for a fresh run)
sh scripts/ai4r-bench heldout run --host --execute --model gpt-6.1-sol --reps 2 --out OUT
sh scripts/ai4r-bench heldout run --host --execute --model gpt-6-luna  --reps 2 --out OUT
sh scripts/ai4r-bench heldout score --host --model gpt-6.1-sol --out OUT
sh scripts/ai4r-bench heldout score --host --model gpt-6-luna  --out OUT
```

`run` writes `OUT/heldout/<model>/<case>/<arm>-r<k>/` (prompt, reply and `run.json` per call, `attempt1.py`, `final.py`,
`result.json`) and `OUT/run-meta/`. `score` re-executes the saved final code on the never-shown score suite and writes
`OUT/scores/heldout-<model>.{json,md}`: case pass rate, test pass rate, first-attempt pass rate, retry rate, rescued
(first attempt failed, final passed), broken (reverse), calls, tokens, wall time, same outcome across reps, and paired
cc-only versus other-only counts. Denominator: every case x rep; a missing, banned or crashing answer is a failure for
every arm.

`freeze` (authoring only, writes beside the source) rewrites `MANIFEST.sha256`. `author_cases.py --out DIR` regenerates
`cases.json` in DIR; do not overwrite the frozen file after a run.

## Known weaknesses

* Model-written code runs on the host in a `python -I` child with a timeout and a banned-import filter. It is a guard
  for pure functions, not a sandbox.
* 10 cases x 2 reps is small. Treat differences of one or two units as noise; use the paired counts.
* The selftest arm gets a different prompt (two blocks) and so a slightly different first attempt.
* One retry is a design choice, not a tuned value.
* Specs and gold are by one author; the reference solutions were written by the same author (consistency check, not independence).
