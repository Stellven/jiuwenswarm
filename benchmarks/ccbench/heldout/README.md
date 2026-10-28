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

## Spec-trap case set (`cases-trap.json`)

A second, separate case set with its own `MANIFEST-trap.sha256`. `cases.json` and `MANIFEST.sha256` are untouched. Every
command takes `--cases cases-trap.json` (default `cases.json`); `run` checks the matching manifest and `score` reads the
same file. Run it with the same `--out` for `run` and `score`, and use a fresh `--out` (the case ids differ, so units never collide).

Why it exists. On gpt-6-luna the only case CC won was `parse_duration`: the spec allowed terms with no space between
them, and every other arm, including the self-test arm, read it as required. The thing to measure is: **an independent
check catches a model's systematic misreading of a spec; a self-check shares it.** These 8 cases each carry one such rule:

| case | rule a model may misread or default wrongly |
|---|---|
| `parse_size` | number and unit may touch (`'1KB'`) or have any spaces between |
| `bucket_counts` | bins are half-open, but the last bin includes its upper edge |
| `competition_rank` | ties share one rank and the next rank skips (1, 2, 2, 4) |
| `consistent_groups` | an empty list is NOT consistent, unlike `all([])`; zero breaks the sign |
| `is_anagram` | NFKC then `casefold()` (so `ß` is `ss`), not `lower()` |
| `to_cents` | ties round half to even on the exact decimal, not half up |
| `format_delta` | a value that formats as zero (`-0.0`, `-0.04`) has no sign |
| `collapse_adjacent` | only adjacent equal items collapse; apart ones are kept |

Authoring rule (`author_trap_cases.py`, `reference_trap.py`), in this order for each case:

1. Write the spec first. It must be unambiguous to a careful reader; the trap is a misreading, not a trick.
2. Write the reference implementation (`reference_trap.py`), never shown to a model.
3. Write the tests: a `gate` of 4 (what CC runs and may quote in its retry) and a `score` of 6 to 10 (never shown to any arm).
   Both suites test the trap rule, on different inputs. No (args, expect) pair is shared and no score input appears in the gate.
   The spec examples shown to the model are also not test inputs. `test_heldout.py` asserts all of this, that the reference
   passes every suite, and that one natural misreading per case fails both the gate and the score suite.

What this does and does not prove. One author wrote the spec, the reference, the gate and the score suite. So the gate is
independent of the WORKER (it was fixed before any model call and never sees the worker's reading of the spec). It is not
independent of the case author: if the author misreads their own spec, the gate and the score suite share that misreading.
Also, the gate and the score suite share the trap rule by design, so a retry that quotes a gate input can teach the rule.
That is a real effect of an independent check, not leakage of a score input, but it means the result measures "an outside
check that knows the rule" and not "a check that finds unknown bugs". Eight cases and two reps is small; read paired counts.

```sh
sh scripts/ai4r-bench heldout plan --cases cases-trap.json --out OUT
sh scripts/ai4r-bench heldout run --host --execute --model gpt-6-luna --reps 2 --cases cases-trap.json --out OUT
sh scripts/ai4r-bench heldout score --host --model gpt-6-luna --cases cases-trap.json --out OUT
```

`author_trap_cases.py --out DIR` regenerates `cases-trap.json`; after a deliberate change run
`run_heldout.py freeze --cases cases-trap.json`. Do not change either file after a run.
