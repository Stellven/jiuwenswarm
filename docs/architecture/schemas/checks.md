---
type: schema
id: cc.check.v1
status: proposed
tags: [schema]
prd: [4.2.1, 4.2.2]
level: detail
---

# Check, test case and test suite · `cc.check.v1`

PRD: 4.2.1, 4.2.2

A **check** is one runnable test of one target. A **test case** is one input and its expected result. A **test suite** is a hashed set of test cases, visible to the builder or sealed from them. One check shape serves [capsules](../capsule/capsule.md#term-capability-capsule), [port types](port-types.md#term-port-type) and call sites, so the gate [runs](../system/lifecycle.md#term-run) them alike; stored cases let a child version re-run its parent's tests; sealed suites keep a capsule from judging itself (INV-10).

**Rules:** INV-8, INV-9, INV-10.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-test-case"></a>**test case** (also: test cases) | One input and its expected result, written only by admission from a Candidate's tests. A child version re-runs its parent's cases through the shared `interface_hash`. |
| <a id="term-test-suite"></a>**test suite** (also: test suites) | A hashed set of test cases, visible to the builder or sealed from them. Sealed suites keep a capsule from judging itself. |

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
| `model_replies` | `list<text>` | opt | checked |  | *Proposed.* The Candidate's recorded model replies for this case, in [turn](../system/model-bridge.md#term-model-turn) order |
| `negative_control` | `boolean` | opt | unchecked | certification | `true` when the case must fail, proving the check can fail |

**Test suite** (`cc.check.suite.v1`). Extends [common](common.md), `scope.library`. Its `id` is the `test_suite_id`. **Written only by admission**: one visible suite per admission from the Candidate's tests. A sealed suite is written by someone other than the builder; how it reaches admission is a known gap.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `capsule_name` | `string` | req | checked |  | The capsule tested. Example: `doc.pdf_to_text` |
| `interface_hash` | `sha256` | req | checked |  | The interface its cases target; a version with the same one runs them unchanged |
| `tests` | `list<Ref(test_case)>` | req | checked |  | Its cases in order, each pinned, so the suite's hash pins every case |
| `access` | `enum(visible, sealed)` | opt | unchecked | certification | Default `visible`. `sealed` suites return only pass or fail, and builders cannot read them |
| `inherited_from_hash` | `sha256?` | opt | unchecked | [RSI](../rsi.md#term-rsi) | The parent's `decl_hash`, when a child inherits its parent's suite |

**Every type's check.** `check.value_matches_type.v1` is a registry check (`deterministic`, `applies_at: node`, `over: outputs`) that passes when the value matches its type's `value_schema` and, for a `json` port, the port's `Port.value_schema`.

**Latest tests.** The name's newest Standing entry gives `verdict_ref`; the Verdict gives `test_suites`; each suite gives `tests`. A version with a matching `interface_hash` runs them unchanged; otherwise it needs new cases and keeps the parent's suite only as `inherited_from_hash`. For a retired or revoked capsule, the previous entry's `verdict_ref` gives its last tests.

## Calling convention

*Proposed, 2026-10-01.* This is the one API between check code and the [check runner](../capsule/gate-host.md#term-check-runner) (M10a). Every `deterministic` and `reference` check's `runner` is a Python function with this signature, whoever writes it: a capsule author, a type's author, or the gate.

```python
def check(*, inputs: dict[str, Any], outputs: dict[str, Any],
          observation: dict | None, expected: Any | None, context: dict) -> dict: ...
```

Schema: the arguments are `tools-v1.schema.json#check_call`.

| Argument | Holds |
|---|---|
| `inputs` | input port name to value, when the check is `over: inputs_and_outputs`; otherwise `{}` |
| `outputs` | output port name to value, when the check is `over: outputs` or `inputs_and_outputs`; otherwise `{}` |
| `observation` | the call's [Observation](observation.md#term-observation) as a dict, when the check is `over: each_call`; otherwise `None` |
| `expected` | the test case's `expected`, when M10a runs the check at admission on a test call; otherwise `None` |
| `context` | what the check is checking against, filled by M10a: `{"target_port": str or None, "port_type": str or None, "value_schema": dict or None, "budget": dict or None, "runner_limits": dict}`. `target_port` and `port_type` come from the check's `target`; `value_schema` is the port type's schema from the pinned vocabulary, merged with the port's `Port.value_schema` for a `json` port; `budget` is the [Binding](binding.md#term-binding)'s `budget` (or `verifier.budget` for a judge call), for `check.within_budget.v1`; `runner_limits` is the pinned policy's `runner` section, so a check never copies a policy value |

**A type check sees only its own type.** M10a runs a type check once per output port of that type, with `outputs` holding that one port and `context.target_port` naming it. A capsule or step check receives every output.

Values follow the runner's [values table](../capsule/runner-handlers.md#values-how-each-port-type-travels): inline types as JSON values, `file` as a read-only path.

**It returns a `CheckResult`** (Schema: `tools-v1.schema.json#check_result`):

```json
{"result": "pass", "message": "every quote found in its source", "evidence": []}
```

| Key | Type | Meaning |
|---|---|---|
| `result` | `enum(pass, fail, unknown)` | `unknown` when the check cannot evaluate its target |
| `message` | `text` | one line a person can act on; required on `fail` and `unknown` |
| `evidence` | `list<EvidenceRef>` | optional: what the check looked at |

**Rules.**

- A check that raises, returns anything else, or runs past policy `runner.check_timeout_s` gives `unknown`, never `pass` (INV-8).
- A check runs in the same [kind](../capsule/capsule.md#term-capsule-kind) of child process as a `tool` capsule, with no broker: it makes no nested calls and no model calls. A check that needs a model is a `judged` check, and its runner is a rubric file instead ([`evidence_bundle`](../types/evidence-bundle.md)).
- A check is pure: it reads only its arguments and its own pinned file.
- M10a records `runner_sha256` and `result` in the [Verification](verification-record.md#term-verification). It writes `message` as the first entry of `results[].evidence`, an `EvidenceRef` `{evidence_type: "check_message", reference: <check_id>, description: <message>}`, followed by the check's own `evidence`.

## Elsewhere

Policy: which anchors may fail a gate (`blocking`); who may write a certifying check (`levels`). A judge's measured error is a [Finding](finding.md) of kind `verifier_audit`. A judge's model is recorded per call in the judge call's Observation `models`. A check is held out exactly when its cases are in sealed suites.

## Reuse

- AI4Research's 43-check registry (`harness/config/evaluation-checks.v1.json`): entries become registry [checks](../capsule/fields.md#term-check); `mode: semantic` becomes `anchor: judged`, `implementation_ref` becomes `runner`. Its 20 semantic checks need a judge runner.
- The Check shape: v2.10b `guarantees.checks`. Test case and test suite are new.
- `Evaluator`, `MetricResult` (agent-core `openjiuwen/symphony/evaluation/base.py:139`, `openjiuwen/symphony/models/evaluation.py:223`, pin `9e339019`): a runner may be one.
- `EvaluationCase` and `EvaluationSuite` (agent-core `openjiuwen/symphony/models/evaluation.py:125`, `openjiuwen/symphony/evaluation/suite.py:83`, pin `9e339019`): not reused; one mixes a test with its output, the other groups evaluators, not cases.
