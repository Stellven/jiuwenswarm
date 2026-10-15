# Verifier, check bundle and checking profile

`Tier 3 · Part of: [Reference](../README.md)`

This page owns the generic verifier CC (`research.verifier`), the `verifier_assessment` record, and the two records that assign checks to every other CC: `check_bundle` and `checking_profile`.

**Summary for reviewers**
- One generic verifier CC checks every work CC. It sees only the pinned declaration and the exact output. It never sees inputs, the Brief, observations or the review manifest.
- Mechanical checks that need inputs or runtime records run first, in the host, from a `check_bundle` pinned to the CC version.
- The verifier's fixed instructions and criteria come from a `checking_profile` pinned to the CC version. The model reply is untrusted. The host binds identity and validates the assessment.
- The Verifier owner owns bundles and profiles. CC owners propose per-CC criteria. RSI never edits either record.
- A CC with several outputs (Screening, Builder, Research Benchmark, Delivery) gets one verifier call per output artifact. Every call carries the same pinned declaration and the same profile.

## Purpose and place in the run

The verifier CC assesses one output of one CC invocation against that CC's declaration. It gives an assessment and never a decision. It is one CC, reused for all work CCs.

### End-to-end check sequence

1. The worker CC produces its output. The host captures the exact bytes.
2. The host runs the deterministic check bundle pinned to that CC version. These checks may read the output, the accepted inputs and runtime records. Each result follows the [deterministic check result](../schemas/deterministic-check-result.schema.json).
3. If a blocking check is not `PASS`, the verifier is not called. The gate halts.
4. The host calls `research.verifier` with two payload members: the pinned declaration and the output bytes (for a zip output, its [projection](#zip-output-projection)). The system instructions come from the checking profile pinned to the same CC version.
5. The model replies with findings, uncertainties, limitations and an optional correction. The reply is untrusted.
6. The host validates the reply against the profile, then assembles the [`verifier_assessment`](../schemas/verifier-assessment.schema.json). The host sets `subject_ref`, `review_context_ref`, `evidence_refs` and `verdict`.
7. The protected gate reads the deterministic result and the assessment, then accepts or halts.

### One call per output artifact

Some CCs have more than one output port. Screening has two outputs, Builder two, Research Benchmark three and Delivery two. The host runs steps 4 to 6 once for each output artifact. Every call carries the same pinned declaration and the same checking profile. Only `subject_output` differs. The host asks the criteria whose `target_port` is the port of that output, and every criterion whose `target_port` is null. Each call gives its own `verifier_assessment` with its own `subject_ref`. The gate writes one gate decision per output, each naming that output's assessment, so the gate decision schema does not change. The host releases the outputs together only when every per-output decision advances. The node gate aggregates them the same way it aggregates subnode decisions. A CC with one output has one call.

Fail-closed rules:

- A missing check result, a missing criterion finding or a duplicate of either is a failure.
- A blocking check or blocking criterion that is not `PASS` blocks release. `INCONCLUSIVE` and `ENVIRONMENT_BLOCKED` block the same way.
- A timeout, a malformed reply, an unknown criterion ID or an unsupported outcome means no assessment. The gate halts.
- A missing bundle or profile pin on a bound CC version fails binding before the run starts.

### How the binder attaches bundle and profile

Every admitted CC version carries two pins in its protected admission record: a `check_bundle` ref and a `checking_profile` ref. The binder reads the pins from the chosen CC version. This works the same for static and dynamically planned CCs. The Planner may suggest extra checks. It cannot add, drop or weaken a pinned bundle check or profile criterion. The binder checks that the CC name and version fall inside each record's target range. It then writes both refs into the bound check plan. The pin that the library snapshot and the run plan carry is `CheckPins` (see [library snapshot](../run-plan.md#library-snapshot)). It holds the `bundle_id`, `version` and SHA-256 of the exact `check_bundle` bytes, and the `profile_id`, `version` and SHA-256 of the exact `checking_profile` bytes, as defined in the two contracts below. It never uses another name for them. The host adds contract and policy checks on top. Both sources are mandatory.

### Ownership

| Record | Owner | Who proposes | Who records the pin |
|---|---|---|---|
| `check_bundle` | Verifier owner | CC owner proposes per-CC checks | Protected admission |
| `checking_profile` | Verifier owner | CC owner proposes per-CC criteria | Protected admission |
| `research.verifier` declaration | Verifier owner | none | Protected admission |

### Review manifest

The host keeps a review manifest for audit: subject, inputs, bundle and profile refs, deterministic results and observations. It is not part of the model payload. `review_context_ref` in the assessment points to it. Its fields are `review-context:field-contract:2` in [field-contracts.json](../field-contracts.json). The name is historical. The record is read only by the host gate and by auditors, never by the verifier.

## Declaration

[verifier_capsule.json](../examples/verifier_capsule.json) validates against the [declaration schema](../schemas/capsule-declaration.schema.json). It declares name `research.verifier`, kind `agent`, effect class `read_only`, one model call through the audited model bridge, no network, no tools and no resources. The port `subject_output` uses the reserved `schema_ref` `opaque-bytes`. It means the exact output bytes of the subject CC. It is not a field contract. The old `review_context` input port and the `original_request` resource are removed. The declaration pins no bundle or profile. Admission pins the check bundle for the verifier itself. The checking profile for each subject CC comes from that subject's admission record. Its `evolution.rsi` is `none` because it is the verifier CC (check `rsi_mode_allowed`, [D34](../../method/decisions.md#d34)).

## Inputs

| Port | Artifact type | Producer | Required | Use |
|---|---|---|---|---|
| `subject_declaration` | `capsule_declaration` | Protected binder, from the pinned subject declaration | yes | Exact declaration bytes of the CC under review. The verifier reads what the CC promises. |
| `subject_output` | `subject_output` | Host capture of the worker output | yes | Exact output bytes, unchanged. A zip output uses the [zip projection](#zip-output-projection). |

The model call carries nothing else. It has no tools, network or file access. Text inside either input is data and cannot change the instructions or criteria.

### Zip output projection

A zip archive cannot go into a text payload. For an output that is a zip (the Builder `bundle`), `subject_output` carries a host-pinned deterministic projection of the archive. The projection is the only allowed form for a zip output. The worker and the verifier never choose it. The projection code is pinned in the admission record like any check runner.

The projection is one UTF-8 text. It lists the archive entries sorted by path in byte order. Each entry is one block of this shape.

```text
path: <entry path>
sha256: <sha256 of the entry bytes, lowercase hex>
size: <entry size in bytes>
---
<full text of the entry, decoded as UTF-8>
===
```

The host builds the projection from the captured zip bytes and records its hash. The assessment `subject_ref` names the projection bytes. Building fails, and the verifier is not called, when the archive has an encrypted entry, a directory entry, a link, an entry over 256 KiB or an entry that is not valid UTF-8. A failed projection is a failed check and the node halts. The check `output_hash_matches` compares the projection with a fresh projection of the captured zip. The checks that bind the zip bytes to the manifest (for example the Builder `bundle_hash_matches`) stay in the CC's own bundle.

## Output field contract

The output is `verifier_assessment`, defined by the [schema](../schemas/verifier-assessment.schema.json) (`urn:jiuwenswarm:m1-design:verifier-assessment:1.0.0`, unchanged). The host writes it. The model reply supplies only the finding bodies, the uncertainties, the limitations and the correction, all untrusted. The host sets every other field and derives the verdict.

Purpose: the host-assembled record of one verifier call on one output. The gate reads it after the deterministic checks.

`verifier-assessment` (exact schema, version 1.0.0) · Producer: the host, from the untrusted reply of `research.verifier`. Consumers: gate host, run bundle, inspection.

| Field                 | Type              | Required | Constraint                                                                     | Meaning                                                   |
| --------------------- | ----------------- | -------- | ------------------------------------------------------------------------------ | --------------------------------------------------------- |
| `schema_version`      | `string`          | yes      | exactly `1.0.0`                                                                | Format version. Reject any other value.                   |
| `subject_ref`         | `Ref`             | yes      | the exact output reviewed, or its zip projection. Host-set                     | Which output the assessment is about. Set by the host; any value in the model reply is not used. |
| `review_context_ref`  | `Ref`             | yes      | the host review manifest. Host-set                                             | Audit pointer. The model never saw the manifest.          |
| `verdict`             | `string`          | yes      | enum, see below. Host-derived by the verdict rule                              | Overall result. Derived by the host from the findings with the verdict rule; the model does not set it. It is checking data only. The gate decides, never the verdict. |
| `findings`            | `Finding[]`       | yes      | at least 1. One per profile criterion asked for this output, no more, no fewer | Per-criterion results. The model supplies each finding body. The host checks coverage (`criterion_coverage_exact`). |
| `uncertainties`       | `string[]`        | yes      | may be empty                                                                   | Open questions the verifier could not settle, copied by the host from the model reply. Empty list means none. Any uncertainty rules out a `PASS` verdict. |
| `limitations`         | `string[]`        | yes      | may be empty                                                                   | Limits of this review, copied by the host from the model reply. Empty list means none stated. Recorded for readers. Limitations alone do not make a verdict `FAIL`. |
| `required_correction` | `nullable-string` | yes      | null unless a blocking criterion failed. Null for an advancing verdict         | Short description of what is wrong, copied by the host from the model reply, for the producer and reviewers. It is not replacement work. Null for an advancing verdict. |
| `ext`                 | `object`          | no       | Optional namespaced diagnostic properties. Each key must match `^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$`; values may be JSON values. | Carries extra debugging or tracing details that do not fit the assessment fields, such as producer-specific timing or diagnostic codes. Prefix keys with the owning component or namespace to avoid collisions. Do not put findings, evidence, corrections, permissions, or acceptance rules here. Consumers may ignore this object. It must not change the verdict, gate decision, or required behavior. |

**Finding**

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `criterion_id` | `string` | yes | a criterion ID of the pinned profile, once per assessment | Which criterion. |
| `outcome` | `string` | yes | enum, see below | Result for that criterion. Supplied by the model reply, which is untrusted. The verdict rule reads it. |
| `reason` | `string` | yes | at least 1 character. Names output fields | Short basis from the declaration and the output. Names output fields. Free text for people and audit. |
| `evidence_refs` | `Ref[]` | yes | at least 1. Host-set to the exact declaration and output | What was reviewed. Set by the host to the exact declaration and output bytes, never taken from the model reply. |

**Enum `verdict`**

| Value | Meaning |
|---|---|
| `PASS` | Every finding is `PASS` and there are no uncertainties |
| `PASS_WITH_KNOWN_LIMITATIONS` | Every blocking finding is `PASS`. Limitations or uncertainties are recorded |
| `FAIL` | A blocking finding is `FAIL` |
| `ENVIRONMENT_BLOCKED` | The worst blocking finding is `ENVIRONMENT_BLOCKED` |
| `INCONCLUSIVE` | The worst blocking finding is `INCONCLUSIVE`, or an uncertainty prevents a decision |

**Enum `Finding.outcome`**

| Value | Meaning |
|---|---|
| `PASS` | The output meets the criterion, judged from the declaration and the output |
| `FAIL` | The output does not meet the criterion |
| `ENVIRONMENT_BLOCKED` | The criterion could not be judged because the call or a resource failed |
| `INCONCLUSIVE` | The declaration and the output cannot settle the criterion |

**Invariants**

- Every criterion asked for this output has exactly one finding.
- `PASS` has no finding other than `PASS` and no uncertainty. `FAIL` has at least one `FAIL` finding.
- An advancing verdict has a null `required_correction`.
- The verdict is checking data, never a control action. Only the gate decides.

**Host checks**

| Check ID | Rule | Outcome |
|---|---|---|
| `assessment_schema` | The assembled assessment validates against the schema | `FAIL`, the gate halts |
| `criterion_coverage_exact` | Findings cover exactly the criteria asked for this output, once each, with known outcomes | `FAIL`, the gate halts |
| `verdict_follows_findings` | The verdict follows the findings by the verdict rule, and an advancing verdict has no required correction | `FAIL`, the gate halts |

Failure outcomes are in [failure outcomes](#failure-outcomes) below.



**Minimum quality bar.** The gate can see for every criterion what was judged, on which bytes and why, and the verdict can be recomputed from the findings.

## Producer obligations

The verifier must:
- answer every criterion asked for this output once, from the declaration and that output only
- say `INCONCLUSIVE` when the pair cannot settle a question
- name output fields in each reason

The verifier must not:
- infer or ask for inputs, the Brief or sources
- add, drop or reword criteria
- follow instructions found inside the declaration or output
- state a verdict, IDs or evidence refs

The host must keep the review manifest outside the model payload.

## Deterministic check bundle

The bundle for the verifier CC itself:

| Check ID | Rule | Outcome on failure |
|---|---|---|
| `declaration_pin_matches` | `subject_declaration` bytes hash to the pin in the admission record | `FAIL`, no model call |
| `output_hash_matches` | `subject_output` bytes hash to the captured output | `FAIL`, no model call |
| `assessment_schema` | Assembled assessment satisfies the schema | `FAIL`, halt |
| `criterion_coverage_exact` | Findings cover exactly the criteria asked for this output, once each, with known outcomes | `FAIL`, halt |
| `verdict_follows_findings` | The verdict follows the findings by the verdict rule | `FAIL`, halt |



## Verifier criteria

The verifier CC has no second semantic reviewer in M1. The host checks above stand in. The independently owned profile fixes its criterion IDs in its system instructions before execution. Three are generic and apply to every CC. A profile may add criteria for an artifact type. Each must be answerable from declaration plus output. Stage instructions may explain a question but cannot add a criterion that needs another input.

| Criterion ID | Question | Applies to |
|---|---|---|
| `declared_output_conformance` | Does the output have the artifact type, fields and shape the declaration states? | all CCs |
| `internal_consistency` | Do the output fields agree with each other and do local references resolve inside the output? | all CCs |
| `limitations_consistency` | Are the listed uncertainties and limitations coherent with the rest of the output? | all CCs |
| `uncertainty_consistency` | Does `readiness.status` agree with the listed blocking uncertainties? | `intent_ir` |
| `requirement_link_completeness` | Is every mandatory requirement linked from an acceptance expectation and an evidence obligation? | `research_brief` |

Finding outcomes are `PASS`, `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE`. The reply body holds `findings` (`criterion_id`, `outcome`, `reason`), `uncertainties`, `limitations` and `required_correction`. The host rejects missing, duplicate or unknown criteria and unsupported outcomes. It supplies every identity and reference field. An ambiguity the profile cannot resolve from the two artifacts is `INCONCLUSIVE`. The persisted record stays the `verifier_assessment` schema. The host review manifest keeps the inputs for audit only, and a reference in it is not evidence the model saw.

**What the host checks instead of the verifier ([D32](../../method/decisions.md#d32)).** PRD 4.2.6 asks Tier 2 to catch three faults. This design catches them at Tier 1 where a rule can decide them. The verifier never sees the evidence (D20), so it does not judge whether a conclusion matches it.

| PRD fault | Host check | Producer obligation |
|---|---|---|
| A conclusion that materially exceeds the evidence | `rule_recomputation` recomputes every finding and the classification from the payload and the registered thresholds. Delivery's `verdict_matches_evaluation` and `results_table_matches_payload` tie the report to the verdict and the payload. Every Delivery reference must pass `ref_hash_match` | Scientific Evaluation states only what the registered rules give. Delivery states no conclusion stronger than the verdict and cites only accepted refs |
| An artifact that contradicts its evidence | `ref_hash_match`, `values_match_empirical_results`, `arithmetic_consistent`, `results_table_matches_payload` | The producer copies numbers from the source artifact and never retypes them |
| An impossible value | `measurement_within_declared_range` checks every repeat against the `valid_min` and `valid_max` that the `hypothesis_blueprint` registered for the metric | Hypothesis registers the bounds from the metric's unit before the run |

## Gate rule

The gate accepts the outputs of a subject CC only when every blocking bundle check is `PASS`, the assessment is valid, every blocking criterion is `PASS`, and persistence succeeded. It halts otherwise. Advancing verdicts are `PASS` and `PASS_WITH_KNOWN_LIMITATIONS`. A `PASS` here means declaration and output conformance only. It does not show fidelity to inputs, source support or scientific validity. The host deterministic checks carry any input-dependent obligation.

## Failure outcomes

| Condition | Outcome | What is kept |
|---|---|---|
| Blocking bundle check not `PASS` | Halt, no verifier call | Check results, output |
| Model timeout or error | `ENVIRONMENT_BLOCKED`, halt | Check results, output, call record |
| Malformed reply, unknown or missing or duplicate criterion | No assessment, halt | Raw reply in the host record only |
| Blocking criterion `FAIL` | `FAIL`, halt | Assessment, output |
| Blocking criterion `INCONCLUSIVE` | `INCONCLUSIVE`, halt | Assessment, output |
| Zip projection cannot be built | Halt, no verifier call | Output zip, check results |
| Assessment not persisted | Halt | Assessment draft |

## `check_bundle` contract

`check-bundle:field-contract:1`. An immutable library record pinned by each admitted CC version. Producer: Verifier owner through protected admission. Consumers: binder, check runner, gate.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | const `1.0.0` | Format version. |
| `id` | string | yes | Unique, immutable | Record identity. |
| `bundle_id` | string | yes | Lowercase dotted snake_case | Stable bundle name across versions. |
| `version` | string | yes | Semver `x.y.z` | Bundle version. A change needs a new version. |
| `target_cc_name` | string | yes | Lowercase dotted `<area>.<capability>` | The one CC this bundle checks. |
| `target_cc_version_range` | string | yes | An exact version label or `<major>.x` | CC versions this bundle was recorded compatible with. |
| `checks` | BundleCheck[] | yes | min 1. `check_id` unique in the bundle. For every output port of the target CC, one blocking check with `check_id` `<port>_schema`, `target_port` that port and `reads` `["output"]` | The deterministic checks the host must run. |
| `owner_role` | string | yes | enum `verifier_owner` | Who may change it. |

`BundleCheck`:

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `check_id` | string | yes | Lowercase snake_case | Check name. It becomes the `check_id` in the result. |
| `target_port` | string | yes | Must be an output port of the target CC | The output this check is about. |
| `rule_summary` | string | yes | Length 1 to 300 | Plain statement of what must hold. |
| `runner_ref` | Ref | yes | Exact pinned code | Pinned code the host runs for this check. The CC under review never supplies or changes it. |
| `reads` | string[] | yes | min 1. Each in enum `output`, `inputs`, `runtime_records` | What the runner may read. Only the host runs checks that read `inputs` or `runtime_records`. |
| `blocking` | boolean | yes | none | If true, a result other than `PASS` blocks release. If false, the result is recorded and does not block. |

Result mapping: the host runs each check once and writes one entry in `results` of the [deterministic check result](../schemas/deterministic-check-result.schema.json). The entry `check_id` equals the bundle `check_id`. `outcome` is the runner outcome (`PASS`, `FAIL`, `ENVIRONMENT_BLOCKED`, `INCONCLUSIVE`). `reason` is the runner's short reason. `evidence_refs` list the output, input or runtime records read. The bound plan holds the bundle ref, so `check_plan_ref` ties the result to the bundle. A non-blocking check that is not `PASS` is recorded and does not block. A missing entry counts as `FAIL`.



## `checking_profile` contract

`checking-profile:field-contract:1`. The verifier instruction set pinned to one CC version. Producer: Verifier owner through protected admission. Consumers: binder, verifier host, gate.

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `schema_version` | string | yes | const `1.0.0` | Format version. |
| `id` | string | yes | Unique, immutable | Record identity. |
| `profile_id` | string | yes | Lowercase dotted snake_case | Stable profile name across versions. |
| `version` | string | yes | Semver `x.y.z` | Profile version. |
| `target_cc_name` | string | yes | Lowercase dotted `<area>.<capability>` | The CC this profile reviews. |
| `target_cc_version_range` | string | yes | Exact version label or `<major>.x` | Compatible CC versions. |
| `criteria` | Criterion[] | yes | min 3. `criterion_id` unique. Must include `declared_output_conformance`, `internal_consistency` and `limitations_consistency`, all with `blocking` true | The questions the verifier must answer. |
| `instruction_ref` | Ref | yes | Exact pinned text | Fixed system instructions. They do not come from the declaration text. |
| `model_call_limit` | integer | yes | 1 to 3 | Most verifier model calls per review. M1 uses 1. |
| `time_s` | integer | yes | 1 to 600 | Wall-clock limit for the whole review, in seconds. |
| `owner_role` | string | yes | enum `verifier_owner` | Who may change it. |

`Criterion`:

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `criterion_id` | string | yes | Lowercase snake_case. Must not mean fidelity, preservation, faithfulness or source support | Criterion name. It becomes `findings[].criterion_id`. |
| `question` | string | yes | Length 1 to 400. Answerable from declaration plus output | The question put to the model. |
| `blocking` | boolean | yes | none | If true, a non-`PASS` finding blocks release. |
| `answerable_from` | string | yes | enum `declaration_and_output` only | States that no other input is needed. |
| `target_port` | nullable-string | yes | Null, or an output port of the target CC | The output this criterion is asked about. Null means it is asked for every output of the CC. The generic criteria use null. A CC with several outputs sets it on its own criteria. |

Rule for per-CC criteria: a CC owner may propose extra criteria on that CC's page, each with a `target_port`. Each must be answerable from the declaration and the output. A question that needs inputs, the request or sources belongs in the CC's deterministic bundle. Admission rejects a profile that breaks this rule.

Generic criteria:

| Criterion ID | Question |
|---|---|
| `declared_output_conformance` | Does the output contain what the declaration says this CC produces, in the declared shape and ports? |
| `internal_consistency` | Does the output avoid contradicting itself? |
| `limitations_consistency` | Are the stated limitations and uncertainties consistent with the output and with the declaration's stated limits? |



## Examples

| File | Kind | Rejected by |
|---|---|---|
| [verifier_capsule.json](../examples/verifier_capsule.json) | valid declaration | |







## Future seams

- The Verifier owner may add alternate verifiers later as new profile versions or new verifier CCs. Records pin versions, so old runs stay valid.
- RSI never edits bundles or profiles. A change goes through the Verifier owner and admission.
- A later profile may widen `answerable_from` only through a new major contract version and a decision to change D20.

## M1 placement

The CC page above does not depend on where the verifier runs. In M1 the rules below apply.

- No plan holds the verifier, and the Planner never selects it. The scheduler creates a verifier subnode at dispatch, one for each output of the work CC, after the host deterministic checks pass and before the protected gate decision.
- Enforced by the scheduler and the protected binder check `library_membership`, which rejects a plan node that names it ([D42](../../method/decisions.md#d42)).
