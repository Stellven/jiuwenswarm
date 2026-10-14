# Hypothesis capsule (`research.hypothesis`)

**Reading level: AI reference.** Build page for one CC and its verifier assignment.

**Summary for human review**

- Input: one selected opportunity, the accepted Brief and two captured resources (baseline and validation data).
- Output: one `hypothesis_blueprint`. It states one testable claim, what changes, what is measured, and the numeric rules that decide success, failure and everything in between.
- The blueprint is frozen before any code or result exists. Builder, Benchmark and Evaluation read it and cannot change it. The host records its hash.
- The CC writes rules only. It never sees measurements and does no scientific judging. Scientific Evaluation applies the rules later.

## Purpose and place in the run

Hypothesis is stage 3.5. It follows Screening and precedes Builder in the static template. The Planner does not select it. It is a fixed node: one run, one opportunity, one hypothesis. It writes the experimental design and does not write code (PRD 3.5.5).

## Declaration

Declaration example: [hypothesis_capsule.json](../examples/hypothesis_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json).

| Item | Value |
|---|---|
| Name | `research.hypothesis`, kind `agent` |
| Needs | model bridge, no network, no tools |
| Effect class | `read_only` (model call only) |
| Budget | 180 s wall, 1 invocation, hard |
| Pinned check bundle | The declaration pins `output_structure`, `rules_reference_declared_metrics` and `boundaries_disjoint`. The protected binder adds the other mandatory host checks below. The Planner cannot drop or weaken any of them. |

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
| `id` | `string` | yes | non-empty | Record identity. |
| `brief_ref` | `Ref` | yes | resolves to the input Brief bytes | The accepted Brief this design answers. |
| `opportunity_ref` | `Ref` | yes | resolves to the input opportunity card | The selected opportunity. |
| `claim` | `string` | yes | one sentence, 20 to 300 characters | The single testable claim. It names the intervention, the measured effect and its size or direction. |
| `mechanism` | `string` | yes | 10 to 500 characters | The causal reason the intervention should work. |
| `independent_variable` | `string` | yes | non-empty | What the POC changes. Exactly one intervention. |
| `dependent_variables` | `string[]` | yes | `min_items` 1, `max_items` 8. The set equals the `metric_id` set of `metrics`. | Names of everything Benchmark will measure. |
| `baseline_identity` | `BaselineIdentity` | yes | see type below | The exact unmodified baseline that treatment is compared with. |
| `validation_resource_ref` | `Ref` | yes | also appears in `resource_refs` | The fixed validation data. |
| `resource_refs` | `Ref[]` | yes | `min_items` 2. Each resolves. Contains `baseline_identity.resource_ref` and `validation_resource_ref`. | All captured resources the experiment uses. |
| `environment_ref` | `Ref` | yes | equals `environment_ref` of both resource snapshots | The prepared environment lock. |
| `metrics` | `MetricDeclaration[]` | yes | `min_items` 1, `max_items` 8. `metric_id` unique. | Declares every metric once: what it is, how it is measured, and which way is better. |
| `outcome_rules` | `OutcomeRule[]` | yes | exactly one rule per declared `metric_id`, none for an undeclared metric | The pre-registered success, falsification and middle-region rules. |
| `repeat_count` | `integer` | yes | min 3, max 30 | Repetitions of each baseline and treatment measurement. Three is the M1 minimum so a median and a spread exist. The PRD sets no number. |
| `seed` | `integer` | yes | min 0, max 2147483647 | Registered random seed. |
| `seed_policy` | `string` | yes | enum `fixed_same_for_all_runs` | Baseline and treatment use this same seed in every repeat. Other policies are future work. |
| `implementation_scope` | `ImplementationScope` | yes | see type below | Limits on what the Builder may write. |
| `constraints` | `string[]` | yes | `min_items` 0. Contains the text of every Brief constraint. | Constraints the experiment preserves. |
| `verification_plan` | `string[]` | yes | `min_items` 1, `max_items` 12, each 5 to 300 characters | Ordered, checkable steps that show the experiment was fair and complete. |

Examples: [valid](../examples/hypothesis_blueprint.json) · rejected by `rules_reference_declared_metrics`: [hypothesis_blueprint_invalid_undeclared_metric](../examples/hypothesis_blueprint_invalid_undeclared_metric.json) · rejected by `boundaries_disjoint`: [hypothesis_blueprint_invalid_overlapping_boundaries](../examples/hypothesis_blueprint_invalid_overlapping_boundaries.json)

### BaselineIdentity

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `resource_ref` | `Ref` | yes | one of `resource_refs` | The baseline resource snapshot. |
| `revision` | `string` | yes | equals the snapshot `revision` | Captured immutable revision of the baseline. |
| `entry_point` | `string` | yes | equals a `path` in that snapshot `files` | The file Benchmark runs as the baseline. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `baseline_identity`)

### MetricDeclaration

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `metric_id` | `string` | yes | pattern `^[a-z][a-z0-9_]*$`, unique | Name used everywhere downstream. |
| `unit` | `string` | yes | non-empty | Unit of the aggregate, for example `ms` or `fraction`. |
| `measurement` | `string` | yes | non-empty | Deterministic definition of how one repeat value is extracted. |
| `direction` | `string` | yes | enum `higher_better`, `lower_better` | Which way is an improvement. Rules must agree with it. |
| `aggregation` | `string` | yes | enum `median`, `mean`, `min`, `max` | How the repeats combine into one aggregate per arm. |
| `target_id` | `nullable-string` | yes | when not null, an `id` in Brief `target_metrics` | Brief target this metric measures. Null for a metric the CC added. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `metrics`)

### OutcomeRule

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `metric_id` | `string` | yes | a declared `metric_id` | The metric the rule decides. |
| `success` | `ComparisonRule` | yes | comparator in the improvement family for `direction`: `lt` or `le` for `lower_better`, `gt` or `ge` for `higher_better` | Region where the metric counts as a success. |
| `falsification` | `ComparisonRule` | yes | comparator in the opposite family | Region where the metric falsifies the claim. Must not overlap `success`. |
| `middle` | `string` | yes | enum `INCONCLUSIVE`, `CONDITIONALLY_ACCEPTABLE` | Classification for results in neither region. `INCONCLUSIVE` is the PRD default. |
| `conditional_rule` | `nullable-ComparisonRule` | yes | not null exactly when `middle` is `CONDITIONALLY_ACCEPTABLE`. Its region lies outside both `success` and `falsification`. | The registered condition that makes a middle result acceptable. Any comparator. |
| `conditional_meaning` | `nullable-string` | yes | not null exactly when `conditional_rule` is not null. 10 to 300 characters. | Plain statement of what conditional acceptance means for the reader. |

Examples: [valid](../examples/hypothesis_blueprint.json) (field `outcome_rules`) · rejected by `boundaries_disjoint`: [hypothesis_blueprint_invalid_overlapping_boundaries](../examples/hypothesis_blueprint_invalid_overlapping_boundaries.json)

### ComparisonRule

Shared type. This version adds the enums and factor rules.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `operand` | `string` | yes | enum `treatment` | The treatment aggregate is what gets compared. |
| `comparator` | `string` | yes | enum `lt`, `le`, `eq`, `ge`, `gt` | The comparison. |
| `reference` | `string` | yes | enum `baseline`, `constant` | What the treatment aggregate is compared with. |
| `factor` | `number` | yes | finite. 0 when `reference` is `constant`. Greater than 0 when `baseline`. | Multiplier on the baseline aggregate. |
| `offset` | `number` | yes | finite | Added after the factor, in the metric unit. |

The threshold is `factor * baseline_aggregate + offset` when `reference` is `baseline`, and `offset` when `reference` is `constant`. The rule holds when `treatment_aggregate comparator threshold` is true.

Examples: [valid](../examples/hypothesis_blueprint.json) (success and falsification rules)

### ImplementationScope

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `may_change` | `string[]` | yes | `min_items` 1, `max_items` 5 | What the POC may change. |
| `must_not_change` | `string[]` | yes | contains `baseline`, `validation_data`, `measurement_functions`, `outcome_rules` | What stays immutable. |
| `max_patch_files` | `integer` | yes | min 1, max 1 | M1 allows one patch file. |

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
- Define every metric, rule and boundary as a number before anything runs. Do not use statistical power analysis or p-values (PRD 3.5.4).
- Use only the supplied baseline and validation data. Do not propose synthetic or scraped data.
- Do not write code, and do not write thresholds that depend on results.
- Self-review before returning. Re-read the Brief and confirm each target metric has a declared metric. Confirm each Brief constraint text is in `constraints`. Confirm each rule agrees with `direction`. Confirm the success and falsification regions do not touch. Confirm the claim wording matches the success rule (for example "at least 10%" and factor 0.9).
- Do not compute or store the blueprint hash. The host records it.

## Deterministic check bundle

The host runs these before the verifier. Checks marked "Output" read only the blueprint. The others read inputs or run records.

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `output_structure` | Output. Matches the field contract: types, required fields, every enum and range above, ComparisonRule factor rules, finite numbers. | reject |
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
| `blueprint_frozen_hash_recorded` | After acceptance the host stores the blueprint SHA-256 in the run record. Later stages must present the same hash. | halt the run if absent or changed |

## Verifier criteria

The verifier sees the pinned declaration and the exact blueprint only. Structure and arithmetic are in the check bundle above, not here. The verifier is a reduced-assurance reviewer. It cannot judge whether the claim fits the Brief.

| Criterion ID | Question | Blocking |
|---|---|---|
| `claim_testable_as_written` | Does the claim name one intervention, one measured effect and its direction or size, so that the outcome rules can decide it? | yes |
| `claim_consistent_with_rules` | Does the size or direction in the claim agree with the success rules of the metrics it names? | yes |
| `mechanism_distinct_from_claim` | Does the mechanism explain why the effect should occur, and is it more than a restatement of the claim? | no |
| `scope_bounded` | Do `implementation_scope` and `verification_plan` describe a bounded change and steps that a reader could check? | no |

## Gate rule

Accept when every deterministic check passes and no blocking criterion fails. Reject on any failed check or blocking criterion. M1 has no repair loop, so a rejection halts to the human session. A missing resource or lock halts before the CC runs.

## Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| Resource unavailable or no environment lock | halt before dispatch | inputs, halt reason |
| Check or blocking criterion fails | reject and halt to human | blueprint, check results, verifier output |
| Blueprint hash differs later | halt at the detecting stage | both hashes |

## Examples

| File | Role |
|---|---|
| [hypothesis_blueprint.json](../examples/hypothesis_blueprint.json) | valid |
| [hypothesis_blueprint_invalid_undeclared_metric.json](../examples/hypothesis_blueprint_invalid_undeclared_metric.json) | rejected by `rules_reference_declared_metrics` |
| [hypothesis_blueprint_invalid_overlapping_boundaries.json](../examples/hypothesis_blueprint_invalid_overlapping_boundaries.json) | rejected by `boundaries_disjoint` |
| [hypothesis_capsule.json](../examples/hypothesis_capsule.json) | declaration |

The synthetic scenario matches `lifecycle_research_brief.json` and `opportunity_card.json`.

## Future seams

- Several hypotheses and ranking: `claim` stays one per blueprint, so a list can wrap it later.
- Other seed policies and aggregates: extend the enums.
- Statistical tests: add rule kinds beside `ComparisonRule`. M1 keeps deterministic bounds.
- Search-based planning (MCTS) can propose blueprints. The checks stay the same.
