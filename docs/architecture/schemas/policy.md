---
type: schema
id: cc.policy.v1
status: proposed
tags: [schema, foundation]
prd: [4.1.2, 4.2.8]
level: detail
---

# Policy: every "how" in one place · `cc.policy.v1`

PRD: 4.1.2, 4.2.8

A named policy document, an **epoch**, holding every *how*: required fields, rules, defaults, thresholds, mappings, and the values of every open list. Every admission (its Verdict) and every run (its [Bindings](binding.md#term-binding)) pins exactly one epoch with `policy_ref {epoch, sha256}`. Several epochs may be current at once, e.g. a stricter one on trial beside the default. An epoch is never edited; a change is a new epoch whose `supersedes` names its predecessor (INV-2, INV-17). A new epoch is a reviewed change.

**Rules:** INV-4, INV-13, INV-17.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-policy"></a>**Policy** (also: policy) | A named policy document holding every "how": required fields, rules, defaults, thresholds, mappings and the values of every open list. Records hold facts; thresholds and settings live here. |
| <a id="term-epoch"></a>**epoch** (also: policy epoch, epochs) | One immutable version of the Policy. Every Verdict and every run Binding pins exactly one epoch, and a change is a new epoch that names the one it supersedes. |
| <a id="term-registry"></a>**registry** (also: registries) | An open list of allowed values for a `reg(...)` field, kept in the Policy. A new value is a new row, not a schema change, and a reader that switches on it refuses an unknown value. |
| <a id="term-reason-code"></a>**reason code** (also: reason_code, reason codes) | An `UPPER_SNAKE` code, such as `CARRIER_CHANGED`, that says why something failed or moved. Each code has one source (runtime, capsule and so on), so a halt names whose fault it is. |

## Fields

Extends [common](common.md), with `scope.library: true`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `epoch` | `string` | req | checked |  | The name records cite, unique. Example: `e1` |
| `supersedes` | `string?` | req | checked |  | The epoch this one was derived from; lineage only, it does not retire it. Null for the first. Example: `e1` for `e2` |
| `sections` | `map<string, json>` | req | checked |  | One entry per section below, keyed by section name |

The document's hash (INV-15) is what records pin.

Schema: `cc policy publish <epoch.json>` is `tools-v1.schema.json#policy_publish_request`; its result (published, unchanged or refused) is `tools-v1.schema.json#policy_publish_result`.

## Sections, with proposed values for the first epoch

| Section | Read by | Proposed value |
|---|---|---|
| `required` | author kit, admission | Extra fields required of **authored** records only (Req, in the [invariants](invariants.md)), and only checked ones. First epoch, the [Declaration](../capsule/fields.md#term-declaration) needs: `identity.name`, `kind`, `summary`, exactly one of `carrier` or `body`, `ports.outputs` (at least 1) each with `check_id`, `changes.effect_class`, `guarantees.checks` (at least 1), `evolution.rsi`, and every capability it calls listed in `needs.external`. Later epochs may require more |
| `rules` | author kit, admission | Each is `{id, applies_to, reason_code}`. Core M1 rules: effect/effect-class consistency; one code source; named closed wired [ports](../capsule/fields.md#term-port); every output checked; predicates evaluable; complete admitted dependency/check/rubric/profile closure; no self-judging; referee has `evolution.rsi: none`; [RSI](../rsi.md#term-rsi) changes stay within the parent's mutation boundary; failure codes are distinct from system reason codes. `every_step_gated` requires one [Gate](../verification.md#term-gate) [capsule](../capsule/capsule.md#term-capability-capsule) and one `gate_profile_ref` for every governed step, with independently authored semantic criteria for every research capability; mechanical helpers run inside the enclosing stage. Suite-count rules apply to `tested_admission`; [Puppet admission](../capsule/admission.md#term-puppet-admission) instead requires an exact-hash developer allowlist. Only a failed rule/check rejects; `unknown` defers. Detailed executable rules are versioned in the policy artifact and summarized by their owning design pages |
| `defaults` | precondition evaluator, librarian | `on_unknown: defer` (the other value is `fail`); `max_age_s: 300`. *Unchecked (RSI):* `dep_update_min_interval_s`, the shortest time between two re-pins of one capsule's dependencies, except for a security fix |
| `blocking` | gate | Which check anchors may fail a gate. First epoch: a failing `deterministic`, `reference` or `judged` check fails it. Because judges are not yet calibrated, a judged `fail` is meant for a person to review, not to end work on its own; what happens next is the workflow's choice |
| `levels` | admission, gate, Binding writer | `provisional`: tested admission ran required visible suites and [checks](../capsule/fields.md#term-check). `certified` is disabled post-M1 assurance. `exempt`: exact-hash developer Puppet allowlist after mandatory validation; every governed call retains a real runtime Gate. `accepts` lists compatible earlier epochs. `admission_judge` has no M1 caller |
| `profiles` | admission, freeze, supervisor, Gate, process hosts | Immutable admission, Gate, retry and execution profiles defined by [profiles](profiles.md). Bindings and [Verdicts](verdict.md#term-verdict) pin exact ProfileRefs; missing or mismatched profiles are `POLICY_UNRESOLVED` |
| `gates` | gate | See [Gates](#gates) below |
| `mappings` | runner, permission layer | How these reach jiuwenswarm's permission engine, `file_guard` and the sandbox: [permissions](../capsule/permissions.md). `effect_class` to agent-core `ToolCard` flags (scheduling, not permission): `pure` gives parallel_safe, stateless and [idempotent](../contracts/principles.md#term-idempotency); `read_only` gives parallel_safe and idempotent; `idempotent` gives idempotent; `compensable`, `nonrepeatable_effect` and `irreversible` give none. `effect_class` to `PermissionLevel`: `pure` and `read_only` ALLOW; `idempotent` and `compensable` ALLOW inside the run's workspace, otherwise ASK; `nonrepeatable_effect` ALLOW only for a policy-authorized bounded empirical operation through its validated process service and exact reserved Binding/attempt; denied otherwise. It never authorizes automatic repetition or arbitrary irreversible effects. `irreversible` ASK, DENY when unattended. `effects[]` set the lowest `effect_class` allowed, in the order `pure`, `read_only`, `idempotent`, `compensable`, `irreversible`: an effect with `reversibility: none` needs `irreversible`; any other effect needs at least `idempotent` when its `idempotent` is true, else at least `compensable`; with no external state effects, `pure` or `read_only` is allowed. `nonrepeatable_effect` is a separate empirical dispatch category rather than another position in the reversibility order; its declared state effects still satisfy that order, its process profile/effect scope must be pinned, and a duplicate reservation attaches to the original operation. Only explicit human-reviewed restart authorizes a new attempt |
| `budgets` | freeze | Budgets that Bindings pin. First epoch: `budget.time_s` only. A call's budget is the capsule's `needs.resources.timeout_s` when set, else the default, and never more than the cap: default 600, cap 1800; a judge or gate call's budget is the gate capsule's `timeout_s`, never over 120. `tokens` and `money` are set once `cost.tokens` and `cost.money` are measured (unchecked: budgets), with the currency of `cost.money`. The policy never selects a model; Model Routing decides endpoint and model choice within the fixed production or isolated experiment route |
| `intent` | `research.compile_intent` | `max_repairs`: the most repair turns one intent call may take after the first compile. Default 1, hard cap 4 (decided). Tuning the default after the intent [fixtures](../system/test-surfaces.md#term-fixture) exist is the only open point. See [intent compile](../capabilities/intent-compile.md) |
| `runner` | runner, [check runner](../capsule/gate-host.md#term-check-runner) | *Proposed, 2026-10-01.* `max_skill_turns: 8`, the most [model turns](../system/model-bridge.md#term-model-turn) one skill call may take; `max_inline_file_bytes: 200000`, the largest file whose text the runner puts into a prompt; `check_timeout_s: 60`, the longest one deterministic or reference check may run. `max_bundle_bytes: 200000`, the largest [evidence bundle](../types/evidence-bundle.md#term-evidence-bundle) the gate host sends a judge. `max_intake_text_bytes: 8000000`, the most extracted document text one intake may hold, so it always fits a tool host frame. See [runner](../capsule/runner.md) and [checks](checks.md#calling-convention) |
| `librarian` | librarian | Fixed: a Finding may only move a Standing toward less authority, in the order of the [Standing](standing.md) states. A person may ask for any move, including a revert to an admitted version and the activation of an `admitted_inactive` one; the librarian writes it with an `_BY_OWNER` reason or `REVERTED`. Nothing leaves `revoked`. Judge calibration, quality windows and when a capsule becomes `suspect`: unchecked (librarian) |
| `hashing` | every tool | SHA-256 over RFC 8785 canonical JSON (INV-15) |
| `registries` | every tool | The values of every open list; the table below |

### Gates

**Fixed checks**, source `gate`, run after the Binding's: `check.call_ok.v1` and `check.within_budget.v1`, both `deterministic` registry checks in the [port type vocabulary](port-types.md).

**Fold**, in order:
1. A non-ok [Observation](observation.md#term-observation) with demonstrated capsule, conformance, prohibited-effect or declared-budget fault gives check.call_ok.v1 fail and decision fail. Unavailable runtime/dependency/mandatory capture gives unknown and ENVIRONMENT_BLOCKED; other insufficient evidence gives unknown and INCONCLUSIVE. Source ownership, not unchecked failure_modes.retriable, determines the category. There is no autonomous retry at M1.
2. Deterministic and reference checks: any `fail` gives `fail`; any `unknown` gives `blocked`. If this step decides, judged checks are not run.
3. Judged checks, folded the same way; a judge error gives `blocked`.
4. Otherwise `pass`.

A finished call over its `budget` fails `check.within_budget.v1`.

The fold writes the durable PRD 4.2.8 gate_result on [Verification](verification-record.md#term-verification) before release. Only PASS/PASS_WITH_KNOWN_LIMITATIONS map to [routing_action](../capsule/gate-host.md#term-routing-action) ADVANCE; other verdicts route to human triage. ESCALATE_TO_HUMAN is not a verdict. This is the new proposed M1 epoch behavior; old epoch outcomes are not reinterpreted during replay.

**Blame.** A failing `capsule` check blames the capsule; a failing `step` check with passing `capsule` checks is a `fit_failure`.

**Labels.** `judge_unmeasured` when a judged check's judge has no calibration; `exempt` on outputs of `exempt` capsules.

**Visibility.** A Finding or Verification that would reveal a sealed suite's cases is `builder_hidden`.

## Registries

The values of every `reg(...)` type. A new value is a new row here (INV-16), not a schema change. A reader that switches on a registry (`capsule_kind`, `check_anchor`, `caller`, `check_source`, `standing_state`) refuses a value it does not know; other readers ignore it.

| Registry | Values in the first epoch | Used by |
|---|---|---|
| `capsule_kind` | `tool`, `skill`, `prompt_section`; unchecked: `mcp`, `a2a` (remote capsules), `subagent`, `agent_template` (agents), `composite` (composer) | [Declaration](../capsule/fields.md) |
| `predicate_op` | `present`, `absent`, `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `matches` | [Declaration](../capsule/fields.md) |
| `check_anchor` | `deterministic`, `reference`, `judged` | [Check](checks.md) |
| `check_source` | `capsule`, `type`, `step`, `gate` | [Binding](binding.md), [Verification](verification-record.md) |
| `caller` | `dispatch`, `gate`, `admission`, `nested` | [Observation](observation.md) |
| `label` | `judge_unmeasured`, `exempt` | [Verification](verification-record.md) |
| `finding_kind` | `gap`, `fit_failure`, `use_outcome`, `drift`, `audit_violation`, `verifier_audit`, `measurement`, `invalidation`, `build_decision`, `build_failed`, `dependency_update` | [Finding](finding.md) |
| `standing_state` | `admitted`, `admitted_inactive`, `deprecated`, `suspect`, `retired`, `revoked` | [Standing](standing.md) |
| `submitter_kind` | `author`, `rsi`, `importer`, `composer` | [Candidate](candidate.md) |
| `constraint_category` | `limit`, `scope`, `prohibition`, `format`, `temporal`, `preference`, `content` | [`intent_ir`](../types/intent-ir.md) |
| `unknown_kind` | `design_parameter`, `selection_decision`, `discoverable_fact` | [`intent_ir`](../types/intent-ir.md) |
| `reason_code` | `SCHEMA_NONCONFORMANT`, `HASH_MISMATCH`, `CARRIER_CHANGED`, `CHECK_FAILED`, `CHECK_MISSING`, `CHECK_UNTESTED`, `CHECK_UNKNOWN`, `EFFECT_CLASS_INCONSISTENT`, `SUMMARY_NAMES_TASK`, `VOCAB_UNKNOWN_NAME`, `PRECONDITION_DEFERRED`, `PRECONDITION_FAILED`, `PORT_MISMATCH`, `PERMISSION_DENIED`, `PERMISSION_UNENFORCEABLE`, `BINDING_MISSING`, `OPERATOR_NOT_ADMITTED`, `DEPENDENCY_UNAVAILABLE`, `DEPENDENCY_UNPINNED`, `RSI_NOT_PERMITTED`, `REFEREE_RSI_PERMITTED`, `CAPSULE_ERROR`, `RUNTIME_UNAVAILABLE`, `TIMEOUT`, `ADMITTED`, `NOT_DEVELOPER_ALLOWED`, `SUITE_FAILED`, `SUSPECT_DRIFT`, `REVOKED_SECURITY`, `RETIRED_ON_EVIDENCE`, `REVERTED`, `BUDGET_EXCEEDED`, `PORT_TYPE_MISMATCH`, `SUSPENDED_BY_OWNER`, `DEPRECATED_BY_OWNER`, `RETIRED_BY_OWNER`, `REVOKED_BY_OWNER`, `ACTIVATED_BY_OWNER`, `JUDGE_IS_SELF`, `GATE_MISSING`, `GATE_RUBRIC_MISMATCH`, `EXTERNAL_UNAVAILABLE`, `CAPSULE_RAISED_UNDECLARED`, `INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE`, `INPUT_CONTRADICTORY`, `STORE_NOT_FOUND`, `STORE_CORRUPT`, `STORE_UNAVAILABLE`, `STORE_CONFLICT`, `RUN_BUSY`, `REQUEST_CONFLICT`, `CONFIG_INVALID`, `POLICY_UNRESOLVED`, `MEASUREMENT_PROTOCOL_ERROR`, `BOUNDARY_VIOLATION`, `UNSUPPORTED_SECURITY_PROFILE`, `NO_ELIGIBLE_OPPORTUNITY`, `RSI_SECURITY_CLEARANCE_REQUIRED`, `AUTH_PROFILE_IN_USE`, `AUTH_RELOGIN_REQUIRED`, `LOGIN_METHOD_UNAVAILABLE`, `MODEL_UNAVAILABLE`, `INVALID_REFERENCE`, `TYPE_MISMATCH`, `TRACK_FEATURE_FORBIDDEN`, `EXPERIMENT_UNAVAILABLE`, `RUN_NOT_FOUND`, `RUN_NOT_SEALED`, `ARTIFACT_NOT_FOUND`, `CONTENT_CORRUPT`, `CAPTURE_MISSING`, `WORKSTATION_BUSY`, `INTAKE_CONTENT_MISMATCH`, `NO_COMPATIBLE_ENDPOINT`, `IDEMPOTENCY_CONFLICT`, `IN_PROGRESS`, `LIMIT_EXCEEDED`, `CHILD_SANDBOX_VIOLATION`, `IMPORT_NOT_ALLOWED`, `LOG_CHAIN_BROKEN`, `QUERY_CAP_EXCEEDED`, `FINAL_SET_LOCKED`, `CANARY_HIT`, `RSI_FROZEN_PATH`, `SUITE_NOT_SEALED`, `HONEYPOT_TOUCHED`, `MODEL_MISMATCH`, `LOOP_SET_RETIRED` | every `Reason`; Observation and Standing `reason` |

**Reason code sources.** Every reason code has one source, so a halt says whose fault it is and nothing is blamed on the wrong party. `runtime`: `RUNTIME_UNAVAILABLE`, `TIMEOUT` (the runtime hung or went away), `EXTERNAL_UNAVAILABLE` (an outside service a capsule declares it reaches could not answer; proposed). `capsule`: `CAPSULE_ERROR`, `CAPSULE_RAISED_UNDECLARED`, `BUDGET_EXCEEDED` (the capsule ran past its own budget), `CHECK_FAILED`. `refusal`: `BINDING_MISSING`, `CARRIER_CHANGED`, `PORT_MISMATCH`, `PORT_TYPE_MISMATCH`, `PERMISSION_DENIED`, `PRECONDITION_FAILED`, `PRECONDITION_DEFERRED`, `LIMIT_EXCEEDED` (a frame, inline input or message over its size limit). `judge`: `CHECK_UNKNOWN`. `input`: `INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE`, `INPUT_CONTRADICTORY`. The others are admission and library codes and are never the reason of a call. The RSI boundary codes added with the attack suite (`CHILD_SANDBOX_VIOLATION`, `IMPORT_NOT_ALLOWED`, `LOG_CHAIN_BROKEN`, `QUERY_CAP_EXCEEDED`, `FINAL_SET_LOCKED`, `CANARY_HIT`, `RSI_FROZEN_PATH`, `SUITE_NOT_SEALED`, `HONEYPOT_TOUCHED`, `MODEL_MISMATCH`, `LOOP_SET_RETIRED`; see [RSI attacks](../capsule/rsi-attacks.md)) are `refusal` codes raised by the admission and the RSI guard; they are never the reason of a capsule call. A new code names its source when it is added.

A new section is a new key in `sections` (v1.x for this page).

## Reuse

- `policy-m1.json` (`capsule-openjiuwen/merged/`): becomes the `required` section of the first epoch.
- skillhub pins a review's `policy_version` (`plugins_market/models/market_assets.py:163`): the same pattern.
- AI4Research kept policy apart from requirements (`schemas/compiler/requirement-semantic-contract.v3.json:41-48`; hard-coded budgets in `lib/requirement_compiler/semantic.py:140-163`): the lesson, and some starting values.

## System failure sources

AuthProvider raises AUTH_PROFILE_IN_USE/AUTH_RELOGIN_REQUIRED/LOGIN_METHOD_UNAVAILABLE; model adapter raises MODEL_UNAVAILABLE; plan/track [validator](../system/planner.md#term-plan-validator) raises INVALID_REFERENCE/TYPE_MISMATCH/TRACK_FEATURE_FORBIDDEN/EXPERIMENT_UNAVAILABLE; benchmark adapter raises RUN_NOT_FOUND/RUN_NOT_SEALED/ARTIFACT_NOT_FOUND/CONTENT_CORRUPT/CAPTURE_MISSING/WORKSTATION_BUSY; intake qualification raises INTAKE_CONTENT_MISMATCH; routing raises NO_COMPATIBLE_ENDPOINT/IDEMPOTENCY_CONFLICT/IN_PROGRESS; [private oracle](../capsule/fixture-oracle.md#term-fixture-oracle) raises RSI_SECURITY_CLEARANCE_REQUIRED. Public adapter aliases project their domain errors and never change the underlying stored Reason or Gate decision.

Store raises STORE_NOT_FOUND/CORRUPT/UNAVAILABLE/CONFLICT; supervisor raises RUN_BUSY/REQUEST_CONFLICT; configuration raises CONFIG_INVALID; policy resolution raises POLICY_UNRESOLVED; research protocol raises MEASUREMENT_PROTOCOL_ERROR; security service raises BOUNDARY_VIOLATION. Missing required transport/store/config/security is infrastructure blocking; immutable bytes/pin mismatches and denied effects never advance. MEASUREMENT_PROTOCOL_ERROR is a workload contract failure. No generic retriable flag permits automatic replay. [Lifecycle](../system/lifecycle.md) defines explicit recovery.
