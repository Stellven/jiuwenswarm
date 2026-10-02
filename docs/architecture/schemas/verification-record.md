---
type: schema
id: cc.verification.v1
status: proposed
tags: [schema]
---

# Verification · `cc.verification.v1`

The gate's check of one capsule call's live output in a run: each check's result and the folded `decision`, `pass`, `fail` or `blocked`. The gate is its only writer (INV-3), and it writes one for every Observation with `caller: dispatch`. Judge calls and admission test calls get none, and neither does a `dispatch` call cancelled by a pause or stop (its Observation has `ext.runner.cancelled: true`). Any other `dispatch` Observation with no Verification is a call the gate skipped.

The gate runs the Binding's `checks`, then its own fixed checks from policy `gates`, and folds them as that section defines. What the workflow does after `fail` or `blocked` is not part of CC.

**Rules:** INV-3, INV-8, INV-10.

## Fields

Extends [common](common.md), with `scope.run_id`. Its `id` is the `verification_id`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `invocation_ref` | `Ref(observation)` | req | checked |  | The [Observation](observation.md) of the call. Its `binding_ref` gives the checks, the budget, the judge and the policy; its `outputs` are the Artifacts checked; its `outcome` and `cost` feed the gate's own checks |
| `results` | `list<object>` | req | checked |  | One entry per check run: the deterministic and reference entries in the Binding's order, then the gate's fixed checks, then the judged entries in the Binding's order ([gate host](../capsule/gate-host.md)). Judged checks the fold did not reach have no entry |
| `results[].check_id` | `id` | req | checked |  | Which check. Example: `text_not_empty` |
| `results[].source` | `reg(check_source)` | req | checked |  | `capsule`, `type` or `step` as the Binding says, or `gate` for the gate's fixed checks |
| `results[].result` | `enum(pass, fail, unknown)` | req | checked |  | `unknown` when it could not be evaluated; never counted as a pass (INV-8) |
| `results[].runner_sha256` | `sha256` | req | checked |  | Which runner code produced the result |
| `results[].evidence` | `list<EvidenceRef>` | opt | checked |  | What the check saw; for a judged check, the judge call's Observation |
| `results[].judge` | `object` | opt | checked |  | For judged checks: `{judge_decl_hash, model}`, where `judge_decl_hash` is the Binding's `verifier.decl_hash` |
| `decision` | `enum(pass, fail, blocked)` | req | checked |  | The fold of `results`, by policy `gates` |
| `gate_result` | `object` | req | checked |  | The durable PRD 4.2.8 decision snapshot, computed once from this fold and frozen evidence; this record is its only authority |
| `gate_result.run_id` | `id` | req | checked |  | Equals scope.run_id; external Gate JSON requires this alias |
| `gate_result.stage_id` | `id` | req | checked |  | Equals the invocation Binding's step_id |
| `gate_result.gate_verdict` | `enum(PASS, PASS_WITH_KNOWN_LIMITATIONS, FAIL, ENVIRONMENT_BLOCKED, INCONCLUSIVE)` | req | checked |  | Detailed runtime Gate verdict; scientific classification is separate |
| `gate_result.normalized_verdict` | `enum(PASS, FAIL, BLOCKED, INCONCLUSIVE)` | req | checked |  | PASS_WITH_KNOWN_LIMITATIONS maps to PASS; ENVIRONMENT_BLOCKED maps to BLOCKED; other verdicts retain their spelling |
| `gate_result.routing_action` | `enum(ADVANCE, HALT, ESCALATE_TO_HUMAN)` | req | checked |  | Only PASS and PASS_WITH_KNOWN_LIMITATIONS advance. M1's other outcomes require attributable human triage |
| `gate_result.tier_1` | `object` | req | checked |  | Mechanical tier summary |
| `gate_result.tier_1.status` | `enum(PASS, FAIL, BLOCKED)` | req | checked |  | Result of the fixed Tier 1 fold |
| `gate_result.tier_1.checks` | `list<id>` | req | checked |  | Check ids indexing this record's results; check outputs are not copied |
| `gate_result.tier_2` | `object` | req | checked |  | Independent semantic tier summary |
| `gate_result.tier_2.status` | `enum(PASS, FAIL, INCONCLUSIVE, NOT_RUN)` | req | checked |  | NOT_RUN when Tier 1 blocks or an approved mechanical-only gate applies |
| `gate_result.tier_2.reasons` | `list<Reason>` | req | checked |  | Attributable semantic or reviewer-runtime reasons |
| `gate_result.tier_2.evidence_refs` | `list<EvidenceRef>` | req | checked |  | Judge capture and assessment refs; no hidden fixture contents |
| `gate_result.failed_checks` | `list<id>` | req | checked |  | Failing check ids from results |
| `gate_result.warnings` | `list<text>` | req | checked |  | Non-blocking warnings at decision time |
| `gate_result.known_limitations` | `list<text>` | req | checked |  | Recorded output issues propagated downstream |
| `gate_result.evidence_refs` | `list<EvidenceRef>` | req | checked |  | Complete stage capture manifest and supporting committed records |
| `gate_result.timestamp` | `time` | req | checked |  | Equals the Verification envelope at; PRD projection requires the alias |
| `labels` | `list<reg(label)>` | opt | checked |  | Why a pass is weaker than it looks, recorded when decided, because a judge's calibration changes later. Example: `["judge_unmeasured"]` |

## Elsewhere

Issue 46 is implemented by extending this one existing record, not adding a competing decision writer. `gate_result` is a required product snapshot under [INV-5](invariants.md); aliases and normalized/routing values must equal their canonical source at commit. Gate calls use deterministic record identity from invocation obs_id; exact repeats return the stored result and different bytes conflict. The supervisor verifies this committed record before release ([lifecycle](../system/lifecycle.md)).

The fold, blame and label rules: policy `gates`. Blame is not stored: it follows from `results[].source` and `result`, and a fit failure is recorded as a [Finding](finding.md). Admission's own test runs are recorded in the [Verdict](verdict.md), not here.

## Reuse

- `EvidenceRef` (agent-core `openjiuwen/symphony/models/evaluation.py:57`, pin `9e339019`): as is.
- `MetricStatus` (agent-core `openjiuwen/symphony/models/evaluation.py:22`, pin `9e339019`): `unknown` maps from `error`, `not_applicable` and `observed`, so a Symphony evaluator can feed a check.
- AI4Research `acceptance-verdict`, `requirement-trace`, `coverage-report`: not reused; they are aggregates, computed by query instead.
