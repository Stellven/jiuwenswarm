# Checking and protected decision fields

**Reading level: AI reference.** [Guard design](../guard-design.md) owns the mechanism; [Intent detail](../intent-design.md) explains its application. Runtime metadata comes from protected capture, not producer assertions.

## Deterministic result

Producer: protected check runner. Consumers: review-context builder and gate. [Schema](schemas/deterministic-check-result.schema.json).

Required fields: `schema_version`, exact `subject_ref`, `check_plan_ref`, nonempty `results`. Each result has `check_id`, `outcome`, `reason`, `evidence_refs`. The bound plan resolves the exact admitted CC-version/check-bundle associations and adds all applicable contract/policy checks; all assigned mandatory deterministic IDs must appear exactly once. `PASS` requires actual supported checks; `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE` prevents semantic dispatch when mandatory. Absent required checks never pass. This clarification does not change the persisted result schema.

## Verifier assessment

Semantic source: independently assigned read-only verifier CC. Assessment producer/consumer: trusted host gate. [Schema](schemas/verifier-assessment.schema.json) remains the persisted record; no schema change is implied.

The semantic model receives exactly two reviewed artifacts—the pinned subject CC declaration and exact output bytes—plus fixed verifier instructions. It receives no worker input, request-specific context, conversation, review manifest, profile/criteria record, runtime observation, predecessor artifact or evidence-fetch capability. Its reply is untrusted finding/uncertainty/limitation content only; it does not supply trusted identity, evidence references or gate authority. The host validates the required criterion set and assembles this existing persisted record from that reply and protected records.

The unchanged persisted record requires `schema_version`, exact `subject_ref`, `review_context_ref`, `verdict`, nonempty `findings`, `uncertainties`, `limitations`, nullable `required_correction`. Each finding has `criterion_id`, `outcome`, `reason`, nonempty `evidence_refs`. Cover every required criterion exactly once. The host owns identity/context refs, evidence refs, and verdict; references attached by the host must not imply that hidden evidence was semantically reviewed. Findings identify the declaration/output basis and limitations, not replacement work. No new public reply schema is introduced.

Assessment verdicts use the PRD outcome vocabulary: `PASS`, `PASS_WITH_KNOWN_LIMITATIONS`, `FAIL`, `ENVIRONMENT_BLOCKED`, `INCONCLUSIVE`. They are checking data, not control actions. Mandatory failure or unresolved uncertainty cannot accompany an advancing assessment. Known limitations can advance only when no mandatory obligation is unsatisfied. Missing required evidence means unavailable/inconclusive, not inferred success.

The host-only review manifest binds subject, original/accepted inputs, owning node and subject subnode contracts, CC/dependency pins, assigned criteria/profile, policy, deterministic results, observations and allowed evidence audience. It is retained for deterministic checking, provenance and gate assembly, but is not sent to the semantic model. The verifier cannot access any of those records beyond the two-artifact projection and cannot fetch evidence or mutate outputs. For Intent it can check only declaration/output conformance; request usefulness and fidelity are not established by semantic Tier 2.

## Gate decision

Producer: protected gate host. Consumers: durable run-state, scheduler and inspection/export. [Schema](schemas/gate-decision.schema.json).

| Required fields | Meaning |
|---|---|
| `schema_version`, `id`, `recorded_at` | Record identity and UTC timestamp |
| `run_id`, `node_id`, `subnode_id`, `attempt_id`, `scope_kind` | Explicit node/subnode invocation or aggregate context |
| `contract_ref`, `node_contract_ref`, `invocation_refs`, `internal_decision_refs` | Checked node/subnode contract, owning node, observed invocations and internal acceptance decisions |
| `policy_ref`, `check_plan_ref` | Fixed authority/obligations; bound plan pins profile/check definitions, exact CC/check-bundle associations and participating dependencies |
| `input_refs`, `output_refs` | Exact accepted inputs and captured reviewed subjects |
| `deterministic_result_ref`, `assessment_ref` | Checking records; assessment is null when Tier 1 prevented review |
| `verdict`, `reasons` | Protected interpretation and criterion/evidence explanations |
| `action`, `accepted_refs` | `advance` only for permitted verdict plus durable acceptance; `halt` publishes no accepted references |

The host validates assessment structure, source/subject/context binding, criterion coverage and consistency with deterministic results. Every mandatory obligation must pass. Advancing verdicts are only `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`; all other outcomes halt. Producer/verifier readiness, instructions or a matching JSON shape grant no control authority.

Accepted references must be the exact reviewed output subset fulfilling required node outputs. Persist immutable artifacts and decision before the accepted-output commit becomes scheduler readiness. A proposed decision file is not a successful database commit. Persistence failure keeps readiness blocked, even if an assessment passed. New attempts/policy/subjects need new decisions.

Scientific `Evaluation_Verdict.json` has its own classification and measurement-to-criterion rationale. It is never copied into the gate verdict as an automatic halt. Valid scientific `FAIL` can be reviewed as conformant and yield infrastructure `PASS` for Delivery.

## Subnode versus node release

Gate `2.0.0` explicitly names `scope_kind` (`subnode` or `node`), owning `node_contract_ref` and nullable `subnode_id`. Subnode gates review work under a concrete Subnode Execution Contract; final node release reviews the external Brief and required internal acceptance. `internal_decision_refs` connects the two scopes. No second interpretation or extra semantic call is required for final aggregation. Trusted records bind the producing/subject scope; schemas alone cannot establish authorship.

A halt may have empty output/invocation inventories when no output or dispatch occurred. Its deterministic subject is the protected failure receipt/checking manifest, with real reasons and evidence, not a fabricated candidate. Advancing decisions still need actual output, observations, complete checks/assessment and durable acceptance. A cancelled/missing verifier on a mandatory branch cannot release work.
