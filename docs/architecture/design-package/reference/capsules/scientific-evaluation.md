# Scientific Evaluation capability capsule (`research.evaluation`)

`Tier 3 · Part of: [Reference](../README.md)`

Naming note: this CC judges the science of one research run. It is not the infrastructure verifier, and it is not the platform benchmark that tests the AI4Research system.

**Summary for reviewers**

- The CC applies the success and falsification rules that the blueprint registered before any run. It compares each metric's measured values to those rules and records one finding per metric.
- One fixed aggregation rule turns the per-metric findings into the overall `PASS`, `FAIL`, `INCONCLUSIVE` or `CONDITIONALLY_ACCEPTABLE`. The rule is in section 4.2.
- The classification and every finding are recomputed by a deterministic host check from the blueprint and the payload. A model cannot move a verdict by wording.
- A valid scientific `FAIL` or `INCONCLUSIVE` is a deliverable result. It is not a pipeline failure and it goes to Delivery unchanged.

## 1. Purpose and place in the run

The CC reads the accepted benchmark payload and the frozen blueprint and records a verdict. It has one output, so the verifier runs once. It reads, interprets and records. It never reruns code, patches code or changes any rule.

## 2. Declaration

Example: [scientific_evaluation_capsule.json](../examples/scientific_evaluation_capsule.json). It validates against the [declaration schema](../schemas/capsule-declaration.schema.json). Its `evolution.rsi` is `none` because its output is gate evidence (check `rsi_mode_allowed`, [D34](../../method/decisions.md#d34)).

| Item | Value |
|---|---|
| Name and kind | `research.evaluation`, `agent` |
| Inputs | `hypothesis_blueprint`, `benchmark_payload`, `brief` |
| Output | `evaluation_verdict` |
| Effect class | `read_only`. The one effect is a model call through the audited bridge. |
| Network | none |
| Budget | 180 s wall, 1 invocation, hard. |
| Pinned checks | The check bundle in section 6 and the criteria in section 7, assigned by the protected binder. |

## 3. Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `hypothesis_blueprint` | `hypothesis_blueprint` (`hypothesis-blueprint:field-contract:2`) | Hypothesis | yes | Source of every rule. The CC may apply these rules and may not change or add to them. |
| `benchmark_payload` | `benchmark_payload` (`benchmark-payload:field-contract:2`) | Research Benchmark | yes | The only source of measured values. |
| `brief` | `research_brief` | Requirement | yes | Context for residual risks and follow-ups, such as the stated constraints. It cannot change a rule or a classification. |

The blueprint rules used here are `outcome_rules[].success`, `falsification`, `middle` and `conditional_rule` (`hypothesis-blueprint:field-contract:2`). The metric `aggregation` and `unit` come from `metrics`. A rule holds when `treatment.value <comparator> threshold`. The threshold is `factor * baseline.value + offset` when `reference` is `baseline`. It is `offset` when `reference` is a constant and `factor` is 0. The comparator is one of `lt`, `le`, `eq`, `ge`, `gt`. `eq` uses relative tolerance 1e-9. A conditional result is possible only where `middle` is `CONDITIONALLY_ACCEPTABLE` and `conditional_rule` is set. The blueprint is frozen before results, so this is the only way a conditional result can exist.

## 4. Output field contract

### 4.1 `evaluation_verdict` (`evaluation-verdict:field-contract:2`)

File `evaluation_verdict.json`. This is the single settled field table. It replaces the earlier text that listed completeness, plausibility and residual risks and the earlier table that listed only limitations and blockers. `limitations` is removed. Its content moves to `residual_risks`.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | `2.0.0` | Format version. |
| `id` | string | yes | `evaluation_verdict` | Artifact identity. |
| `brief_ref` | Ref | yes | Equals the input brief's Ref | The brief the run served. Copied from the `brief` input. Check `refs_match_inputs` rejects any other Ref. |
| `blueprint_ref` | Ref | yes | Equals the input blueprint's Ref and `benchmark_payload.blueprint_ref` | The registered rules applied. Copied from the `hypothesis_blueprint` input. Check `refs_match_inputs` rejects any other Ref. |
| `benchmark_ref` | Ref | yes | Equals the input payload's Ref | The measurements judged. Copied from the `benchmark_payload` input. Check `refs_match_inputs` rejects any other Ref. |
| `classification` | string | yes | enum `PASS`, `FAIL`, `INCONCLUSIVE`, `CONDITIONALLY_ACCEPTABLE`. Must equal the result of section 4.2 | The overall scientific result. The CC proposes it. The host recomputes it from the findings and rejects any difference (`rule_recomputation`). Delivery reports it unchanged. Wording cannot move it. |
| `aggregation_rule` | string | yes | enum `m1_conjunctive_v1` | Names the rule in section 4.2 used to combine findings. A fixed label in M1, not a free choice. |
| `findings` | MetricVerdictFinding[] | yes | min 1. Exactly one finding per blueprint metric, in blueprint order | Per-metric comparison of measurement to rule. The CC writes it from the blueprint rules and the payload values only. The host recomputes every finding. |
| `completeness` | CompletenessReview | yes | none | Whether every registered measurement exists. Describes the payload. It never softens a finding. |
| `plausibility` | PlausibilityReview | yes | none | Whether the measured values are physically and computationally believable. Never use it to rescue a `FAIL`. An `implausible` status makes the overall result `INCONCLUSIVE`. |
| `blockers` | string[] | yes | Non-empty exactly when a finding has `rule_applied` `unmeasured` or `plausibility.status` is `implausible`. Each item is under 300 characters | What blocks a firm classification. Text for readers. Empty exactly when no finding is unmeasured and plausibility is not `implausible`. Delivery copies each item verbatim into its limitations section. |
| `residual_risks` | string[] | yes | Each item under 300 characters. May be empty | Interpretive limits and operational risks that remain, such as noise, narrow data or one hardware type. Text for readers, never a rule or a threshold. An empty list means the CC names none. Delivery copies each item verbatim. |
| `followups` | string[] | yes | Each item under 300 characters. Recommendations only. No item is an instruction to rerun a node or change code | Suggested future work, to be authorized separately. Text only. Nothing acts on it automatically. Delivery copies each item verbatim into its recommendations section. |

`MetricVerdictFinding`

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `metric_id` | string | yes | Equals a blueprint `metric_id`. Unique across findings | The metric judged. Copied from the blueprint as the exact string. |
| `classification` | string | yes | enum `PASS`, `FAIL`, `INCONCLUSIVE`, `CONDITIONALLY_ACCEPTABLE` | Result for this metric under section 4.2 step 1. The host recomputes it from the two values and the registered rule. |
| `rule_applied` | string | yes | enum `success`, `falsification`, `conditional`, `middle`, `unmeasured` | Which registered rule decided it. `middle` means no region matched and no conditional rule held. `unmeasured` means a side has no value. |
| `rule_text` | string | yes | 1 to 300 characters. Restates the registered comparator, factor and offset of the rule applied, or says that no region matched | The rule in words so a reader can check it. Text for readers. It restates a registered rule and adds no new threshold (`registered_rule_only`). |
| `baseline_value` | nullable-number | yes | Equals the payload's baseline `value` for this metric | Baseline aggregate used, in the metric unit. Copied from the payload, never recomputed. Null when the baseline has no value, which makes the finding `unmeasured`. |
| `treatment_value` | nullable-number | yes | Equals the payload's treatment `value` for this metric | Treatment aggregate used, in the metric unit. Copied from the payload, never recomputed. Null when the treatment has no value, which makes the finding `unmeasured`. |
| `threshold` | nullable-number | yes | Non-null exactly when `rule_applied` is `success`, `falsification` or `conditional`. Then equals the registered threshold computed from `baseline_value` | The number the treatment was compared with, in the metric unit. Null when no rule applied. The host recomputes it from the registered rule and `baseline_value`. |
| `rationale` | string | yes | 1 to 600 characters. Names the values, the threshold and the outcome | Measurement-to-rule explanation. Text for readers and the verifier. No gate parses it. |

`CompletenessReview`: `status` (enum `complete`, `incomplete`. `incomplete` exactly when some metric side is unmeasured) and `notes` (string[], each under 300 characters).

`PlausibilityReview`: `status` (enum `plausible`, `implausible`, `not_assessable`) and `notes` (string[], at least one note when status is not `plausible`). `implausible` flags an execution anomaly, such as an impossible speedup or negative memory.

Examples: [valid](../examples/evaluation_verdict.json)

### 4.2 Aggregation rule `m1_conjunctive_v1`

M1 treats the registered metrics as one conjunctive claim. Every blueprint metric is required. The rule has two steps. Both run in code in the host check, and the CC must reach the same result.

Step 1, per metric:

1. If the baseline or treatment `value` is null, the finding is `INCONCLUSIVE` with `rule_applied` `unmeasured`.
2. Otherwise test the success rule and the falsification rule. If both hold, the blueprint is defective and the input check `blueprint_rules_disjoint` halts the node before evaluation.
3. Success only: `PASS`, rule `success`.
4. Falsification only: `FAIL`, rule `falsification`.
5. Neither, `middle` is `CONDITIONALLY_ACCEPTABLE` and `conditional_rule` holds: `CONDITIONALLY_ACCEPTABLE`, rule `conditional`.
6. Neither, otherwise: `INCONCLUSIVE`, rule `middle`.

Step 2, overall, first match wins:

| Order | Condition | Overall classification |
|---|---|---|
| 1 | `plausibility.status` is `implausible` | `INCONCLUSIVE` |
| 2 | Any finding is `FAIL` | `FAIL` |
| 3 | Any finding is `INCONCLUSIVE` | `INCONCLUSIVE` |
| 4 | Any finding is `CONDITIONALLY_ACCEPTABLE` | `CONDITIONALLY_ACCEPTABLE` |
| 5 | Every finding is `PASS` | `PASS` |

A falsified metric outranks a missing one. The claim is already falsified by measured evidence. This matches the PRD rules: `PASS` only when all success conditions hold, `FAIL` when falsification holds, `INCONCLUSIVE` for the gap or for insufficient evidence, and `CONDITIONALLY_ACCEPTABLE` only when registered before execution.

## 5. Producer obligations

The CC must:

1. Take every rule only from the blueprint. Add no threshold, no metric and no new classification.
2. Take every value only from the payload.
3. Follow section 4.2 in order and set `aggregation_rule` to `m1_conjunctive_v1`.
4. Write one rationale per metric that names the values, the threshold and the outcome.
5. Judge plausibility in one qualitative pass. Flag `implausible` only for values that are impossible or clearly an execution anomaly. Never use plausibility to rescue a `FAIL`.
6. Conclude nothing the registered rules do not give. Never word a result as support when the classification is `FAIL` or `INCONCLUSIVE`. A value outside the metric's declared `valid_min` or `valid_max` never reaches Evaluation: Research Benchmark rejects it (`measurement_within_declared_range`).
7. Record follow-ups as recommendations. Never trigger a rerun, a patch or a node.

Self-review before emitting: recompute each finding by hand from the two input values and the registered rule. Recompute the overall classification from the findings with the table above. Confirm every blueprint metric has one finding. Confirm `blockers` is non-empty exactly when required. Confirm no rule appears that the blueprint lacks.

## 6. Deterministic check bundle

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `evaluation_verdict_schema` | Output matches the field table, enums, ranges and string lengths above. | reject |
| `refs_match_inputs` | `brief_ref`, `blueprint_ref` and `benchmark_ref` equal the input Refs. The payload's `blueprint_ref` equals the blueprint. | reject |
| `blueprint_rules_disjoint` | Input check. For every metric the success and falsification rules do not both hold on the payload values, and every `conditional_rule` region lies outside both. The Hypothesis checks already enforce this. This check is a second line of defence. | node fails (blueprint defect), escalation record |
| `rule_recomputation` | The host recomputes every finding and the overall classification from the blueprint and the payload using section 4.2. It also recomputes `threshold`, `completeness.status`, and the blocker condition. All must equal the output. | reject |
| `finding_coverage` | One finding per blueprint metric, none extra, none duplicated. | reject |
| `registered_rule_only` | A finding cites `conditional` only where the blueprint registered a `conditional_rule` for that metric. `CONDITIONALLY_ACCEPTABLE` appears only with `conditional`. Every `rule_text` restates a registered rule. | reject |

`rule_recomputation` replaces the old criterion `registered_rule_applied`. That criterion needs the blueprint and the payload, which the semantic verifier never sees. So it is a host check and no checking profile lists it. [science_checking_profile.json](../examples/science_checking_profile.json) lists the three generic criteria and the criteria of section 7.

## 7. Verifier criteria

The verifier sees only the declaration and the exact verdict. Reduced assurance applies: it cannot confirm the rule or the values are right, only that the verdict is coherent.

| Criterion ID | Question | Blocking |
|---|---|---|
| `classification_consistent_with_findings` | Does `classification` equal what the `aggregation_rule` named in the verdict gives for the listed findings and the plausibility status? | yes |
| `finding_names_metric` | Does every finding name a distinct `metric_id`? | yes |
| `finding_consistent_with_values` | For each finding, do `classification`, `rule_applied`, the two values, `threshold` and `rule_text` agree with each other? | yes |
| `rationale_states_values_and_rule` | Does each rationale name the values, the threshold or rule, and the outcome that its finding states? | yes |
| `blockers_match_findings` | Are blockers present exactly when a finding is unmeasured or plausibility is implausible, and do they say why? | yes |
| `followups_are_recommendations` | Is every follow-up a recommendation, not an instruction to rerun a node or change code? | no |
| `no_unregistered_criteria` | Does the verdict avoid new success or failure thresholds that its `rule_text` fields do not state? | no |

## 8. Gate rule

Accept when every host check passes and no blocking criterion fails. The accepted classification goes to Delivery unchanged, whatever its value. `FAIL`, `INCONCLUSIVE` and `CONDITIONALLY_ACCEPTABLE` are valid accepted results. Reject only when the output is not a correct application of the registered rules. A rejection halts the node. Nothing retries it. A blueprint defect also fails the node with an escalation record.

## 9. Failure outcomes

| Condition | Outcome | Kept |
|---|---|---|
| Scientific `FAIL` or `INCONCLUSIVE` supported by the rules | Accepted. Delivery proceeds. | Verdict |
| Unmeasured metric in the payload | Accepted as `INCONCLUSIVE` with blockers | Verdict |
| `rule_recomputation` mismatch | Reject. The node halts (dispatch outcome `rejected`) and nothing retries it | Rejected output, check result |
| Blueprint rules overlap or `middle` invalid | Node fails, escalation record | Inputs, check result |

## 10. Examples

| File | Role | Rejected by |
|---|---|---|
| [evaluation_verdict.json](../examples/evaluation_verdict.json) | valid (`FAIL`: latency falsified, quality preserved) | none |


| [scientific_evaluation_capsule.json](../examples/scientific_evaluation_capsule.json) | declaration | none |

The older `evaluation_capsule.json` is removed. The science node examples (`science_node_contract.json`, `science_subnode_contract.json`, `science_subnode_template.json`) now use `scientific_evaluation_capsule.json`.

## 11. Future seams

- Richer conditional logic is a blueprint change (`conditional_rule` already exists). A new rule kind would extend the `rule_applied` enum. Existing verdicts stay valid.
- Non-conjunctive claims or weighted metrics would be a new `aggregation_rule` value, not a change to `m1_conjunctive_v1`.
- Statistical tests over repeats can add finding fields once the blueprint registers them.
- The Router can pick any model for this CC. The classification does not depend on the model because the host recomputes it.

## M1 placement

The CC page above does not depend on where Scientific Evaluation runs. In M1 the rules below apply.

- It consumes the benchmark payload after the protected gate has accepted it, and Delivery consumes its verdict. Ports decide the order.
- Exactly one ancestor of the Delivery leaf runs `research.evaluation`. The protected binder enforces this in `delivery_leaf_coverage` ([D42](../../method/decisions.md#d42)).
