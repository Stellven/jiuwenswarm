# Hypothesis capsule (`research.hypothesis`)

`Tier 3 · Part of: [Reference](../README.md)`

Build page for one CC and its verifier assignment.

**Summary for human review**

- Input: one selected opportunity, the accepted Brief and two captured resources (baseline and validation data).
- Output: one `hypothesis_blueprint`. It states one testable claim, what changes, what is measured, and the numeric rules that decide success, failure and everything in between.
- The blueprint is frozen before any code or result exists. Builder, Benchmark and Evaluation read it and cannot change it. The host records its hash.
- The CC writes rules only. It never sees measurements and does no scientific judging. Scientific Evaluation applies the rules later.

## Purpose and place in the run

Hypothesis is PRD stage 3.5. It turns one selected opportunity into one testable hypothesis and an experimental design. It writes no code (PRD 3.5.5).

## Declaration

Declaration example: [hypothesis_capsule.json](../examples/hypothesis_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name | `research.hypothesis`, kind `agent` |
| Needs | model bridge, no network, no tools |
| Effect class | `read_only` (model call only) |
| Budget | 180 s wall, 1 invocation, hard |
| Pinned check bundle | The declaration pins `blueprint_schema`, `rules_reference_declared_metrics` and `boundaries_disjoint`. The protected binder adds the other mandatory host checks below. The Planner cannot drop or weaken any of them. |

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `brief` | `research_brief` (`research-brief:2.0.0`) | Requirement | yes | Target metrics, constraints and the user's comparison targets. Every Brief target metric must be measured. |
| `opportunity` | `opportunity_card` | Screening | yes | The one opportunity to turn into a claim. |
| `baseline_resource` | `resource_snapshot` | protected resolver | yes | The unmodified baseline to compare against. |
| `validation_resource` | `resource_snapshot` | protected resolver | yes | Fixed validation data. The CC may not invent or fetch data (PRD 3.5.2). |

Both resource snapshots must carry the same non-null `environment_ref`. The blueprint copies it.

## Output field contract

Artifact `hypothesis_blueprint`, contract `hypothesis-blueprint:field-contract:2`, version 2.0.0. The plain meaning and constraint define each field. Examples only illustrate.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | `string` | yes | exactly `2.0.0` | Format version. |
| `id` | `string` | yes | non-empty | Record identity, set by the Hypothesis CC. A label only: consumers find the blueprint by its Ref, never by this ID, and it grants nothing. |
| `brief_ref` | `Ref` | yes | resolves to the input Brief bytes | The accepted Brief this design answers. The CC copies the Ref of its `brief` input. Check `resource_refs_resolve` rejects a Ref that does not resolve. |
| `opportunity_ref` | `Ref` | yes | resolves to the input opportunity card | The selected opportunity. The CC copies the Ref of its `opportunity` input. Check `resource_refs_resolve` rejects a Ref that does not resolve. |
| `claim` | `string` | yes | one sentence, 20 to 300 characters | The single testable claim. It names the intervention, the measured effect and its size or direction. The CC writes it. The verifier checks that it agrees with the success rules (`claim_consistent_with_rules`). Frozen with the blueprint. |
| `mechanism` | `string` | yes | 10 to 500 characters | The causal reason the intervention should work. Explanation for readers and the verifier. No check or rule reads it as a number. |
| `independent_variable` | `string` | yes | non-empty | What the POC changes. Exactly one intervention. The Builder reads it to know what to build. It must match the intervention named in `claim`. |
| `dependent_variables` | `string[]` | yes | `min_items` 1, `max_items` 8. The set equals the `metric_id` set of `metrics`. | Names of everything Benchmark will measure. A copy of the `metric_id` values, written by the CC. Check `dependent_variables_match_metrics` rejects any difference. |
| `baseline_identity` | `BaselineIdentity` | yes | see type below | The exact unmodified baseline that treatment is compared with. |
| `validation_resource_ref` | `Ref` | yes | also appears in `resource_refs` | The fixed validation data, copied from the `validation_resource` input. The CC may not invent, fetch or swap data. |
| `resource_refs` | `Ref[]` | yes | `min_items` 2. Each resolves. Contains `baseline_identity.resource_ref` and `validation_resource_ref`. | All captured resources the experiment uses. The CC copies Refs from its two resource inputs. It adds no other resource. |
| `environment_ref` | `Ref` | yes | equals `environment_ref` of both resource snapshots | The prepared environment lock. The CC copies it from the resource snapshots and does not choose it. Check `environment_from_resources` rejects a null or different value. |
| `metrics` | `MetricDeclaration[]` | yes | `min_items` 1, `max_items` 8. `metric_id` unique. | Declares every metric once: what it is, how it is measured, and which way is better. The CC writes it before any run. Benchmark and Evaluation read it and cannot change it. |
| `outcome_rules` | `OutcomeRule[]` | yes | exactly one rule per declared `metric_id`, none for an undeclared metric | The pre-registered success, falsification and middle-region rules. The CC writes them before any run. Evaluation applies them to the measured values. Nothing changes them after the blueprint is frozen. |
| `repeat_count` | `integer` | yes | min 3, max 30 | Number of repetitions of each baseline and treatment measurement, counted per arm. Three is the M1 minimum so a median and a spread exist. The PRD sets no number. |
| `seed` | `integer` | yes | min 0, max 2147483647 | Registered random seed, a plain integer. The CC picks it before any run. Benchmark uses it in every repeat of both arms (see `seed_policy`). Not a secret. |
| `seed_policy` | `string` | yes | enum `fixed_same_for_all_runs` | Baseline and treatment use this same seed in every repeat. Other policies are future work. |
| `implementation_scope` | `ImplementationScope` | yes | see type below | Limits on what the Builder may write. |
| `constraints` | `string[]` | yes | `min_items` 0. Contains the text of every Brief constraint. | Constraints the experiment preserves. The CC copies the text of every Brief constraint without change (`constraints_carried`). An empty list means the Brief has none. |
| `verification_plan` | `string[]` | yes | `min_items` 1, `max_items` 12, each 5 to 300 characters | Ordered, checkable steps that show the experiment was fair and complete. Written by the CC for human and verifier review (`scope_bounded`). No rule or gate reads it as a number. |

Examples: [valid](../examples/hypothesis_blueprint.json)

### BaselineIdentity

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `resource_ref` | `Ref` | yes | one of `resource_refs` | The baseline resource snapshot. |
| `revision` | `string` | yes | equals the snapshot `revision` | Captured immutable revision of the baseline. Copied from the baseline snapshot, not chosen by the CC. Check `baseline_identity_resolves` compares it. |
| `entry_point` | `string` | yes | equals a `path` in that snapshot `files` | The file Benchmark runs as the baseline. A `path` from the baseline snapshot `files`, written as the snapshot records it. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `baseline_identity`)

### MetricDeclaration

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `metric_id` | `string` | yes | pattern `^[a-z][a-z0-9_]*$`, unique | Name used everywhere downstream. The CC chooses it. `outcome_rules`, `dependent_variables`, Benchmark values and verdict findings all refer to it by this exact string. |
| `unit` | `string` | yes | non-empty | Unit of the aggregate, for example `ms` or `fraction`. Thresholds (`offset`) are in this unit. The report copies it as a label. |
| `measurement` | `string` | yes | non-empty | Deterministic definition of how one repeat value is extracted. Text written by the CC before any run. It uses no judgement by a model. Benchmark measures as it says. |
| `direction` | `string` | yes | enum `higher_better`, `lower_better` | Which way is an improvement. Rules must agree with it (`rule_direction_consistent`). It is not a pass or fail by itself. |
| `aggregation` | `string` | yes | enum `median`, `mean`, `min`, `max` | How the repeats combine into one aggregate per arm. The aggregate is the baseline or treatment value that the outcome rules compare. |
| `target_id` | `nullable-string` | yes | when not null, an `id` in Brief `target_metrics` | Brief target this metric measures. Null for a metric the CC added. Check `brief_targets_covered` needs every Brief target to appear here. |
| `valid_min` | `nullable-number` | yes | finite; when both bounds are set, `valid_min` is below `valid_max` | Lowest value one repeat can physically take, in the metric unit, for example 0 for a time or a fraction. Null means no lower bound. The host check `measurement_within_declared_range` of Research Benchmark enforces it. A value outside the range is rejected there, so the Benchmark node stops and Evaluation never sees it. |
| `valid_max` | `nullable-number` | yes | finite | Highest value one repeat can physically take, in the metric unit, for example 1 for a fraction. Null means no upper bound. Enforced like `valid_min`. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `metrics`)

### OutcomeRule

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `metric_id` | `string` | yes | a declared `metric_id` | The metric the rule decides. |
| `success` | `ComparisonRule` | yes | comparator in the improvement family for `direction`: `lt` or `le` for `lower_better`, `gt` or `ge` for `higher_better` | Region where the metric counts as a success. The CC writes it. When the Brief target has a comparison, it must equal the converted target (`brief_comparison_consistent`). |
| `falsification` | `ComparisonRule` | yes | comparator in the opposite family | Region where the metric falsifies the claim. The CC writes it. It must not overlap `success` (`boundaries_disjoint`). Evaluation reports a falsified metric as `FAIL`. |
| `middle` | `string` | yes | enum `INCONCLUSIVE`, `CONDITIONALLY_ACCEPTABLE` | Classification for results in neither region. `INCONCLUSIVE` is the PRD default. Choose `CONDITIONALLY_ACCEPTABLE` only together with a `conditional_rule`. |
| `conditional_rule` | `nullable-ComparisonRule` | yes | not null exactly when `middle` is `CONDITIONALLY_ACCEPTABLE`. Its region lies outside both `success` and `falsification`. | The registered condition that makes a middle result acceptable. Any comparator. Null when `middle` is `INCONCLUSIVE`. Written before any run, so Evaluation cannot add one later. |
| `conditional_meaning` | `nullable-string` | yes | not null exactly when `conditional_rule` is not null. 10 to 300 characters. | Plain statement of what conditional acceptance means for the reader. Written by the CC for people. Null when `conditional_rule` is null. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `outcome_rules`)

### ComparisonRule

Shared type. This version adds the enums and factor rules.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `operand` | `string` | yes | enum `treatment` | The treatment aggregate is what gets compared. Always `treatment`. The baseline enters only through `reference`. |
| `comparator` | `string` | yes | enum `lt`, `le`, `eq`, `ge`, `gt` | The comparison. |
| `reference` | `string` | yes | enum `baseline`, `constant` | What the treatment aggregate is compared with: the baseline aggregate, or a fixed number given by `offset`. |
| `factor` | `number` | yes | finite. 0 when `reference` is `constant`. Greater than 0 when `baseline`. | Multiplier on the baseline aggregate. A plain ratio with no unit, for example 0.9 for "90% of baseline". Fixed at 0 for a `constant` reference. |
| `offset` | `number` | yes | finite | Added after the factor, in the metric unit. For a `constant` reference it is the threshold itself. |

The threshold is `factor * baseline_aggregate + offset` when `reference` is `baseline`, and `offset` when `reference` is `constant`. The rule holds when `treatment_aggregate comparator threshold` is true.

Examples: [valid](../examples/hypothesis_blueprint.json) (success and falsification rules)

### ImplementationScope

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `poc_change_scope` | `string[]` | yes | `min_items` 1, `max_items` 5 | What the POC may change. It is the POC's permitted change scope. The CC writes it and the Builder reads it. The Builder cannot widen it. It is unrelated to a declaration's `evolution.may_change`. |
| `must_not_change` | `string[]` | yes | contains `baseline`, `validation_data`, `measurement_functions`, `outcome_rules` | What stays immutable. The Builder must not touch these. The CC may add items but may not remove the four required ones. |
| `max_patch_files` | `integer` | yes | min 1, max 1 | Largest number of files the patch may touch. M1 allows one patch file. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `implementation_scope`)

### Comparison encoding

Two encodings exist and each has one job.

| Encoding | Where | Shape | Job |
|---|---|---|---|
| Brief comparison | `research_brief.target_metrics[].comparison` | `{comparator, reference, value}`, `reference` is `baseline` or `constant` | The user's wished-for target. Often null. |
| `ComparisonRule` | blueprint `outcome_rules` | `{operand, comparator, reference, factor, offset}` | The registered rule that Benchmark and Evaluation apply. Only this one is used after Hypothesis. |

Conversion applies when a Brief comparison is not null. The `success` rule must equal the converted target. `constant` gives `factor` 0 and `offset` equal to `value`. `baseline` gives `factor` equal to `value` and `offset` 0, so `value` 0.9 with `le` means "at most 90% of baseline". The Hypothesis CC may not loosen a Brief target. The CC chooses the falsification and middle rules.

## Producer obligations

- Write one claim and one mechanism. Do not write competing claims (PRD 3.5.1).
- Register `valid_min` and `valid_max` for every metric from its unit, before anything runs. Use null only where no bound exists.
- Define every metric, rule and boundary as a number before anything runs. Do not use statistical power analysis or p-values (PRD 3.5.4).
- Use only the supplied baseline and validation data. Do not propose synthetic or scraped data.
- Do not write code, and do not write thresholds that depend on results.
- Self-review before returning. Re-read the Brief and confirm each target metric has a declared metric. Confirm each Brief constraint text is in `constraints`. Confirm each rule agrees with `direction`. Confirm the success and falsification regions do not touch. Confirm the claim wording matches the success rule (for example "at least 10%" and factor 0.9).
- Do not compute or store the blueprint hash. The host records it.

## Deterministic check bundle

The host runs these before the verifier. Checks marked "Output" read only the blueprint. The others read inputs or run records.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `blueprint_schema` | Output. Matches the field contract: types, required fields, every enum and range above, ComparisonRule factor rules, finite numbers. | reject |
| `rules_reference_declared_metrics` | Output. Each `outcome_rules.metric_id` is a declared `metric_id`. Each declared metric has exactly one rule. | reject |
| `dependent_variables_match_metrics` | Output. `dependent_variables` equals the `metric_id` set. | reject |
| `rule_direction_consistent` | Output. Success and falsification comparators match `direction` as the OutcomeRule table says. | reject |
| `boundaries_disjoint` | Output. No value satisfies both `success` and `falsification` for a metric. Exact when both rules are constants. Otherwise test at baseline values 0.001, 1 and 1000. Touching boundaries pass only when one comparator is strict. | reject |
| `conditional_rule_in_middle` | Output. `conditional_rule` is null unless `middle` is `CONDITIONALLY_ACCEPTABLE`. When set, its region does not intersect `success` or `falsification` (same probe method). | reject |
| `brief_targets_covered` | Every Brief `target_metrics[].id` appears as some `target_id`. | reject |
| `brief_comparison_consistent` | For each Brief target with a non-null comparison, the success rule equals the conversion above. | reject |
| `resource_refs_resolve` | Every ref in `resource_refs`, `brief_ref` and `opportunity_ref` resolves to exact bytes. Resources have `availability` `available`. | reject |
| `baseline_identity_resolves` | `baseline_identity` matches the baseline snapshot revision and `entry_point` exists in its files. | reject |
| `environment_from_resources` | `environment_ref` equals the `environment_ref` of both snapshots and is not null. | reject |
| `constraints_carried` | Every Brief constraint `text` appears in `constraints`. | reject |
| `blueprint_frozen_hash_recorded` | After acceptance the host stores the blueprint SHA-256 in the run record. Later stages must present the same hash. The Builder manifest, the benchmark payload and the verdict each carry it in `blueprint_ref`. | halt the run if absent or changed |

## Verifier criteria

The verifier sees the pinned declaration and the exact blueprint only. Structure and arithmetic are in the check bundle above, not here. The verifier is a reduced-assurance reviewer. It cannot judge whether the claim fits the Brief.

| Criterion ID | Question | Blocking |
|---|---|---|
| `claim_testable_as_written` | Does the claim name one intervention, one measured effect and its direction or size, so that the outcome rules can decide it? | yes |
| `claim_consistent_with_rules` | Does the size or direction in the claim agree with the success rules of the metrics it names? | yes |
| `mechanism_distinct_from_claim` | Does the mechanism explain why the effect should occur, and is it more than a restatement of the claim? | no |
| `scope_bounded` | Do `implementation_scope` and `verification_plan` describe a bounded change and steps that a reader could check? | no |

## Gate rule

Accept when every deterministic check passes and no blocking criterion fails. Reject on any failed check or blocking criterion. M1 has no repair loop: a rejection stops the Hypothesis node and writes an escalation record for later human review. A missing resource or lock stops the node before the CC runs and writes an escalation record. The run does not wait.

## Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| Resource unavailable or no environment lock | Stop the Hypothesis node before dispatch and write an escalation record | inputs, halt reason |
| Check or blocking criterion fails | Reject the blueprint, stop the Hypothesis node and write an escalation record for later human review | blueprint, check results, verifier output |
| Blueprint hash differs later | halt at the detecting stage | both hashes |

## Examples

| File | Role |
|---|---|
| [hypothesis_blueprint.json](../examples/hypothesis_blueprint.json) | valid |


| [hypothesis_capsule.json](../examples/hypothesis_capsule.json) | declaration |

The synthetic scenario matches `lifecycle_research_brief.json` and `opportunity_card.json`.

## Future seams

- Several hypotheses and ranking: `claim` stays one per blueprint, so a list can wrap it later.
- Other seed policies and aggregates: extend the enums.
- Statistical tests: add rule kinds beside `ComparisonRule`. M1 keeps deterministic bounds.
- Search-based planning (MCTS) can propose blueprints. The checks stay the same.

## M1 placement

The CC page above does not depend on where Hypothesis runs. In M1 the rules below apply.

- It is a fixed node: one run, one opportunity, one hypothesis. Its input is the selected opportunity, so it runs after Screening. Builder reads its blueprint, so it runs before Builder.
- Every plan holds Hypothesis in exactly one node. The plan policy lists `research.hypothesis` in `required_stages` ([run plan](../run-plan.md#plan-policy)).
- Enforced by the plan policy and the protected binder checks `delivery_leaf_coverage` and `dependency_closure` ([D42](../../method/decisions.md#d42)).
