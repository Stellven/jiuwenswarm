---
type: schema
id: cc.check.v1
status: proposed
tags: [schema]
---

# Check, test case and test suite · `cc.check.v1`

A **check** is one runnable test of one target. A **test case** is one input and its expected result. A **test suite** is a hashed set of test cases, visible to the builder or sealed from them. One check shape serves capsules, port types and call sites, so the gate runs them alike; stored cases let a child version re-run its parent's tests; sealed suites keep a capsule from judging itself (INV-10).

**Rules:** INV-8, INV-9, INV-10.

## Fields

**Check.** The Check shape is defined once, on the [Declaration](../capsule/fields.md#checks-one-runnable-test-each), with where a Check may be written in full.

**Test case** (`cc.check.case.v1`). Extends [common](common.md), `scope.library`. Its `id` is the `test_id`; tests are re-run by it. **Written only by admission**, from a Candidate's `tests`, since only admission is trusted to compute `interface_hash`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `check_id` | `id` | req | checked |  | The check it exercises |
| `interface_hash` | `sha256` | req | checked |  | The interface it was written against, so it still applies after code changes |
| `inputs` | `map<string, Ref(artifact)>` | req | checked |  | Input port name to its Artifact |
| `expected` | `json` | req | checked |  | The expected output, or a judged check's rubric. Example: `{"text": {"min_chars": 1}}` |
| `fixtures` | `list<Ref(artifact)>` | opt | checked |  | Outside state the test needs, e.g. files in the workspace |
| `negative_control` | `boolean` | opt | unchecked | certification | `true` when the case must fail, proving the check can fail |

**Test suite** (`cc.check.suite.v1`). Extends [common](common.md), `scope.library`. Its `id` is the `test_suite_id`. **Written only by admission**: one visible suite per admission from the Candidate's tests. A sealed suite is written by someone other than the builder; how it reaches admission is a known gap.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `capsule_name` | `string` | req | checked |  | The capsule tested. Example: `doc.pdf_to_text` |
| `interface_hash` | `sha256` | req | checked |  | The interface its cases target; a version with the same one runs them unchanged |
| `tests` | `list<Ref(test_case)>` | req | checked |  | Its cases in order, each pinned, so the suite's hash pins every case |
| `access` | `enum(visible, sealed)` | opt | unchecked | certification | Default `visible`. `sealed` suites return only pass or fail, and builders cannot read them |
| `inherited_from_hash` | `sha256?` | opt | unchecked | RSI | The parent's `decl_hash`, when a child inherits its parent's suite |

**Every type's check.** `check.value_matches_type.v1` is a registry check (`deterministic`, `applies_at: node`, `over: outputs`) that passes when the value matches its type's `value_schema` and, for a `json` port, the port's `Port.value_schema`.

**Latest tests.** The name's newest Standing entry gives `verdict_ref`; the Verdict gives `test_suites`; each suite gives `tests`. A version with a matching `interface_hash` runs them unchanged; otherwise it needs new cases and keeps the parent's suite only as `inherited_from_hash`. For a retired or revoked capsule, the previous entry's `verdict_ref` gives its last tests.

## Elsewhere

Policy: which anchors may fail a gate (`blocking`); who may write a certifying check (`levels`). A judge's measured error is a [Finding](finding.md) of kind `verifier_audit`. A judge's model is recorded per call in the judge call's Observation `model`. A check is held out exactly when its cases are in sealed suites.

## Reuse

- AI4Research's 43-check registry (`harness/config/evaluation-checks.v1.json`): entries become registry checks; `mode: semantic` becomes `anchor: judged`, `implementation_ref` becomes `runner`. Its 20 semantic checks need a judge runner.
- The Check shape: v2.10b `guarantees.checks`. Test case and test suite are new.
- `Evaluator`, `MetricResult` (agent-core `openjiuwen/symphony/evaluation/base.py:139`, `openjiuwen/symphony/models/evaluation.py:223`, pin `9e339019`): a runner may be one.
- `EvaluationCase` and `EvaluationSuite` (agent-core `openjiuwen/symphony/models/evaluation.py:125`, `openjiuwen/symphony/evaluation/suite.py:83`, pin `9e339019`): not reused; one mixes a test with its output, the other groups evaluators, not cases.
