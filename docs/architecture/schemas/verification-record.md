---
type: schema
id: cc.verification.v1
status: proposed
tags: [schema]
---

# Verification · `cc.verification.v1`

The gate's check of one capsule call's live output in a run: each check's result and the folded `decision`, `pass`, `fail` or `blocked`. The gate is its only writer (INV-3), and it writes one for every Observation with `caller: dispatch`. Judge calls and admission test calls get none. A `dispatch` Observation with no Verification is a call the gate skipped.

The gate runs the Binding's `checks`, then its own fixed checks from policy `gates`, and folds them as that section defines. What the workflow does after `fail` or `blocked` is not part of CC.

**Rules:** INV-3, INV-8, INV-10.

## Fields

Extends [common](common.md), with `scope.run_id`. Its `id` is the `verification_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `invocation_ref` | `Ref(observation)` | req | checked |  | The [Observation](observation.md) of the call. Its `binding_ref` gives the checks, the budget, the judge and the policy; its `outputs` are the Artifacts checked; its `outcome` and `cost` feed the gate's own checks |
| `results` | `list<object>` | req | checked |  | One entry per check run: the Binding's `checks` in order, then the gate's fixed checks. Judged checks the fold did not reach have no entry |
| `results[].check_id` | `id` | req | checked |  | Which check. Example: `text_not_empty` |
| `results[].source` | `reg(check_source)` | req | checked |  | `capsule`, `type` or `step` as the Binding says, or `gate` for the gate's fixed checks |
| `results[].result` | `enum(pass, fail, unknown)` | req | checked |  | `unknown` when it could not be evaluated; never counted as a pass (INV-8) |
| `results[].runner_sha256` | `sha256` | req | checked |  | Which runner code produced the result |
| `results[].evidence` | `list<EvidenceRef>` | opt | checked |  | What the check saw; for a judged check, the judge call's Observation |
| `results[].judge` | `object` | opt | checked |  | For judged checks: `{judge_decl_hash, model}`, where `judge_decl_hash` is the Binding's `verifier.decl_hash` |
| `decision` | `enum(pass, fail, blocked)` | req | checked |  | The fold of `results`, by policy `gates` |
| `labels` | `list<reg(label)>` | opt | checked |  | Why a pass is weaker than it looks, recorded when decided, because a judge's calibration changes later. Example: `["judge_unmeasured"]` |

## Elsewhere

The fold, blame and label rules: policy `gates`. Blame is not stored: it follows from `results[].source` and `result`, and a fit failure is recorded as a [Finding](finding.md). Admission's own test runs are recorded in the [Verdict](verdict.md), not here.

## Reuse

- `EvidenceRef` (agent-core `openjiuwen/symphony/models/evaluation.py:57`, pin `9e339019`): as is.
- `MetricStatus` (agent-core `openjiuwen/symphony/models/evaluation.py:22`, pin `9e339019`): `unknown` maps from `error`, `not_applicable` and `observed`, so a Symphony evaluator can feed a check.
- AI4Research `acceptance-verdict`, `requirement-trace`, `coverage-report`: not reused; they are aggregates, computed by query instead.
