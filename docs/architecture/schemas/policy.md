---
type: schema
id: cc.policy.v1
status: proposed
tags: [schema, foundation]
---

# Policy: every "how" in one place · `cc.policy.v1`

A named policy document, an **epoch**, holding every *how*: required fields, rules, defaults, thresholds, mappings, and the values of every open list. Every admission (its Verdict) and every run (its Bindings) pins exactly one epoch with `policy_ref {epoch, sha256}`. Several epochs may be current at once, e.g. a stricter one on trial beside the default. An epoch is never edited; a change is a new epoch whose `supersedes` names its predecessor (INV-2, INV-17). A new epoch is a reviewed change.

**Rules:** INV-4, INV-13, INV-17.

## Fields

Extends [common](common.md), with `scope.library: true`.

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `epoch` | `string` | req | checked |  | The name records cite, unique. Example: `e1` |
| `supersedes` | `string?` | req | checked |  | The epoch this one was derived from; lineage only, it does not retire it. Null for the first. Example: `e1` for `e2` |
| `sections` | `map<string, json>` | req | checked |  | One entry per section below, keyed by section name |

The document's hash (INV-15) is what records pin.

## Sections, with proposed values for the first epoch

| Section | Read by | Proposed value |
|---|---|---|
| `required` | author kit, admission | Extra fields required of **authored** records only (Req, in the [invariants](invariants.md)), and only checked ones. First epoch, the Declaration needs: `identity.name`, `kind`, `summary`, exactly one of `carrier` or `body`, `ports.outputs` (at least 1) each with `check_id`, `changes.effect_class`, `guarantees.checks` (at least 1), and every capability it calls listed in `needs.external`. Later epochs may require more |
| `rules` | author kit, admission | Each is `{id, applies_to, reason_code}`: `effect_class_matches_effects` (`EFFECT_CLASS_INCONSISTENT`); `json_port_has_schema` (`SCHEMA_NONCONFORMANT`); `at_least_one_test`, a Candidate has at least one test case (`CHECK_UNTESTED`); `one_test_per_admission_check`, a test case for every `admission` or `both` check (`CHECK_UNTESTED`); `summary_names_no_task` (`SUMMARY_NAMES_TASK`); `no_any_type` (`VOCAB_UNKNOWN_NAME`); `every_output_has_check` (`CHECK_MISSING`); `predicates_evaluable`, every `needs.when` entry has a known `op` (`SCHEMA_NONCONFORMANT`); `operators_admitted_and_pinned`, every capsule in `needs.external` is admitted, and a pinned one names an admitted `decl_hash` (`OPERATOR_NOT_ADMITTED`). *Unchecked (RSI):* `parent_suites_pass`, a Candidate with `lineage.parent_hash` whose `interface_hash` equals the parent's also runs the parent Verdict's `test_suites` (`CHECK_FAILED`). *Proposed:* `failure_modes_additive`, a version keeps every `failure_modes` code its parent declared (`FAILURE_MODE_REMOVED`); `failure_codes_distinct`, no `failure_modes` code is a `reason_code` registry value (`SCHEMA_NONCONFORMANT`). Only a failed check or a broken rule rejects; an `unknown` defers (`CHECK_UNKNOWN`) |
| `defaults` | precondition evaluator | `on_unknown: defer` (the other value is `fail`); `max_age_s: 300` |
| `blocking` | gate | Which check anchors may fail a gate. First epoch: a failing `deterministic`, `reference` or `judged` check fails it. Because judges are not yet calibrated, a judged `fail` is meant for a person to review, not to end work on its own; what happens next is the workflow's choice |
| `levels` | admission, gate, Binding writer | `provisional`: the candidate has at least one test case, and every check run on its test calls passes, including its `node` and `both` checks. `certified` (unchecked: certification): also a sealed suite passes, written by someone other than the builder. `exempt` (unchecked: exempt agents): for capabilities that cannot be checked in advance, granted by capsule name in this section; every call needs a `trajectory_ref`. `accepts`: the other epochs whose Verdicts a run under this epoch may bind; first epoch: none |
| `gates` | gate | See [Gates](#gates) below |
| `mappings` | runner | `effect_class` to agent-core `ToolCard` flags: `pure` gives parallel_safe, stateless and idempotent; `read_only` gives parallel_safe and idempotent; `idempotent` gives idempotent; `compensable` and `irreversible` give none. `effect_class` to `PermissionLevel`: `pure` and `read_only` ALLOW; `idempotent` and `compensable` ALLOW inside the run's workspace, otherwise ASK; `irreversible` ASK, DENY when unattended. `effects[]` set the lowest `effect_class` allowed, in the order `pure`, `read_only`, `idempotent`, `compensable`, `irreversible`: an effect with `reversibility: none` needs `irreversible`; any other effect needs at least `idempotent` when its `idempotent` is true, else at least `compensable`; with no effects, `pure` or `read_only` is allowed |
| `budgets` | workflow runtime | Budgets that Bindings pin. First epoch: `budget.time_s` only, 600 per call and 120 per judge call. `tokens` and `money` are set once `cost.tokens` and `cost.money` are measured (unchecked: budgets), with the currency of `cost.money`. The policy never picks a model: that is each capsule author's choice |
| `librarian` | librarian | Fixed: a Finding may only move a Standing toward less authority, in the order of the [Standing](standing.md) states. Judge calibration, quality windows and when a capsule becomes `suspect`: unchecked (librarian) |
| `hashing` | every tool | SHA-256 over RFC 8785 canonical JSON (INV-15) |
| `registries` | every tool | The values of every open list; the table below |

### Gates

**Fixed checks**, source `gate`, run after the Binding's: `check.call_ok.v1` and `check.within_budget.v1`, both `deterministic` registry checks in the [port type vocabulary](port-types.md).

**Fold**, in order:
1. When the Observation's `outcome` is not `ok`, `check.call_ok.v1` gives `unknown` and the decision is `blocked`. *Proposed* (INV-19): for an `error` with a declared failure mode, `check.call_ok.v1` gives `fail`, and the decision is `fail` when the mode is not `retriable`, else `blocked`; `CAPSULE_RAISED_UNDECLARED` is always `blocked`.
2. Deterministic and reference checks: any `fail` gives `fail`; any `unknown` gives `blocked`. If this step decides, judged checks are not run.
3. Judged checks, folded the same way; a judge error gives `blocked`.
4. Otherwise `pass`.

A finished call over its `budget` fails `check.within_budget.v1`.

**Blame.** A failing `capsule` check blames the capsule; a failing `step` check with passing `capsule` checks is a `fit_failure`.

**Labels.** `judge_unmeasured` when a judged check's judge has no calibration; `exempt` on outputs of `exempt` capsules.

**Visibility.** A Finding or Verification that would reveal a sealed suite's cases is `builder_hidden`.

## Registries

The values of every `reg(...)` type. A new value is a new row here (INV-16), not a schema change. A reader that switches on a registry (`capsule_kind`, `check_anchor`, `caller`, `check_source`, `standing_state`) refuses a value it does not know; other readers ignore it.

| Registry | Values in the first epoch | Used by |
|---|---|---|
| `capsule_kind` | `tool`, `skill`, `prompt_section`; unchecked: `mcp`, `a2a` (remote capsules), `subagent`, `agent_template` (agents), `composite` (composer) | [Declaration](declaration.md) |
| `predicate_op` | `present`, `absent`, `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `not_in`, `matches` | [Declaration](declaration.md) |
| `check_anchor` | `deterministic`, `reference`, `judged` | [Check](checks.md) |
| `check_source` | `capsule`, `type`, `step`, `gate` | [Binding](binding.md), [Verification](verification-record.md) |
| `caller` | `dispatch`, `gate`, `admission` | [Observation](observation.md) |
| `label` | `judge_unmeasured`, `exempt` | [Verification](verification-record.md) |
| `finding_kind` | `gap`, `fit_failure`, `use_outcome`, `drift`, `audit_violation`, `verifier_audit`, `measurement`, `invalidation`, `build_decision`, `build_failed` | [Finding](finding.md) |
| `standing_state` | `admitted`, `admitted_inactive`, `deprecated`, `suspect`, `retired`, `revoked` | [Standing](standing.md) |
| `submitter_kind` | `author`, `rsi`, `importer` | [Candidate](candidate.md) |
| `reason_code` | `SCHEMA_NONCONFORMANT`, `HASH_MISMATCH`, `CARRIER_CHANGED`, `CHECK_FAILED`, `CHECK_MISSING`, `CHECK_UNTESTED`, `CHECK_UNKNOWN`, `EFFECT_CLASS_INCONSISTENT`, `SUMMARY_NAMES_TASK`, `VOCAB_UNKNOWN_NAME`, `PRECONDITION_DEFERRED`, `PRECONDITION_FAILED`, `PORT_MISMATCH`, `PERMISSION_DENIED`, `BINDING_MISSING`, `OPERATOR_NOT_ADMITTED`, `CAPSULE_ERROR`, `RUNTIME_UNAVAILABLE`, `TIMEOUT`, `ADMITTED`, `SUSPECT_DRIFT`, `REVOKED_SECURITY`, `RETIRED_ON_EVIDENCE`, `REVERTED`; proposed: `CAPSULE_RAISED_UNDECLARED`, `FAILURE_MODE_REMOVED`, `INPUT_AMBIGUOUS`, `INPUT_INCOMPLETE`, `INPUT_CONTRADICTORY` | every `Reason`; Observation and Standing `reason` |

A new section is a new key in `sections` (v1.x for this page).

## Reuse

- `policy-m1.json` (`capsule-openjiuwen/merged/`): becomes the `required` section of the first epoch.
- skillhub pins a review's `policy_version` (`plugins_market/models/market_assets.py:163`): the same pattern.
- AI4Research kept policy apart from requirements (`schemas/compiler/requirement-semantic-contract.v3.json:41-48`; hard-coded budgets in `lib/requirement_compiler/semantic.py:140-163`): the lesson, and some starting values.
