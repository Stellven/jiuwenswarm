# contract: a declared output contract that is checked at the boundary

New bench (model in the loop, outcome uncertain). Shared helpers: `../modelbench.py`.

## What it tests

A data-analysis step produces a result that a later step or tool will consume, so units, rounding, types and required
fields matter at the boundary. The product declares output ports with types and checks them before the next step uses
the output. Here, 10 small CSV questions each carry a declared contract (typed ports with unit, decimals, min and max,
string pattern). The traps are the ones a downstream consumer breaks on: milliseconds versus seconds, cents versus
dollars, fraction versus percent, lb versus kg, F versus C, bytes versus GiB, missing cells, duplicate export rows,
integer versus float, extra keys.

Question: do replies that are both correct and contract-compliant go up when the bench validates the reply against the
declared ports and gives one retry with the violation list, compared with the same contract given as plain text?

## Arms (identical task text including the contract, same model, tool-free codex)

| arm | what happens | calls per unit |
|---|---|---|
| plain (theirs) | one call; the contract is in the prompt as the typed port JSON | 1 |
| verify (theirs, told to verify) | same, plus "check each value against the data and the contract (type, unit, decimals, range) and fix errors before you reply" | 1 |
| cc (ours) | one call as plain (byte-identical prompt); the validator checks exact keys, type, integer versus decimal, at most N decimals, min and max in the declared unit, string pattern; on any violation ONE retry carrying the violations | 1 to 2 |

Both theirs arms see the same contract bytes as cc. The only difference for cc is that the contract is enforced.

## Scoring (model-free, `contract.py`)

Per reply: each field is compared with the frozen gold (exact decimal after round half up; strings and booleans exact);
`correct` = all fields right; `compliant` = zero violations; primary metric `correct_and_compliant`. Denominator is
every case x rep; an unparseable or missing reply is a failure for every arm. The validator reads only the declared
ports, never the gold (asserted in `test_contract.py`). Gold is computed in `author_cases.py` with exact Decimal
arithmetic and re-derived from each case's CSV text in `test_contract.py`; `cases.json` is frozen in `MANIFEST.sha256`.

## CC mechanism and whether it is in product code

* Typed output ports, schema validation of outputs and PASS or FAIL checks with reasons at the node boundary: **in product**
  (capsule declarations with ports, `checks/engine.py`, `capsule_extensions/*/checks.py`, `gate.py`).
* One retry carrying the violations: **in product** only for the planner (`capsules/planner.py` repair generation).
  Here it is **bench-side**, for data answers.
* The validator itself (`contract.py`): **bench-side only**, a small stand-in for a declared port check.

## Where CC should not help (ties are expected and honest)

* A validator checks form, not truth. A wrong number inside the declared range passes. Correctness gains come only
  through a violation (for example a percent given for a fraction, which breaks the max) that triggers a retry.
* If the model reads the contract and complies the first time, cc equals plain. gpt-6.1-sol may do this on most cases.
  The preflight case (`orders`) was clean in all arms.
* Told-to-verify can fix the same slips without a checker. If verify equals cc, the gain is "has a checker".
* Rounding mistakes inside the allowed decimals (for example 12.34 versus 12.35) are not violations.

## Cost

Per model: 10 cases x 2 reps x 3 arms = 60 first calls plus at most 20 retries (cc) = at most 80 calls. 20 units per arm
per model, 40 across both models. Tokens and wall time per call in `run.json`, summed per arm in the score.

## Commands (repo root; host for model runs)

```sh
sh scripts/ai4r-bench selftest contract modelbench
sh scripts/ai4r-bench contract plan --out OUT
sh scripts/ai4r-bench contract run --host --execute --case orders --reps 1 --out OUT        # preflight, 3 calls
sh scripts/ai4r-bench contract score --host --out OUT
sh scripts/ai4r-bench contract run --host --execute --model gpt-6.1-sol --reps 2 --out OUT
sh scripts/ai4r-bench contract run --host --execute --model gpt-6-luna  --reps 2 --out OUT
sh scripts/ai4r-bench contract score --host --model gpt-6.1-sol --out OUT
sh scripts/ai4r-bench contract score --host --model gpt-6-luna  --out OUT
```

Output: `OUT/contract/<model>/<case>/<arm>-r<k>/` (prompt, reply and `run.json` per call, `reply1.txt`, `final.txt`,
`result.json`), `OUT/scores/contract-<model>.{json,md}`: correct+compliant, correct, compliant, field accuracy,
first-attempt rate, retry rate, rescued, broken, calls, tokens, wall time, identical reply across reps, paired counts.
Runs resume; use a fresh OUT for a fresh run.

## Known weaknesses

* The contract is also the prompt, so a model that follows instructions well rarely violates it. This bench measures the
  residual, and may show a tie on sol.
* "Downstream consumer" is simulated by the validator; no real next step consumes the output.
* 10 cases x 2 reps is small; variants of one trap (unit slips) dominate.
* Gold depends on stated rules (round half up, definitions in the notes); an alternative reading by the model scores wrong.
