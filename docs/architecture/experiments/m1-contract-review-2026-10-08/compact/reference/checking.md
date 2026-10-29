# Checking and protected decision fields

**Reading level: AI reference.** [Guard design](../guard-design.md) owns the mechanism; [Intent detail](../intent-design.md) explains its application. Runtime metadata comes from protected capture, not producer assertions.

## Deterministic result

Producer: protected check runner. Consumers: review-context builder and gate. [Schema](schemas/deterministic-check-result.schema.json).

Required fields: `schema_version`, exact `subject_ref`, `check_plan_ref`, nonempty `results`. Each result has `check_id`, `outcome`, `reason`, `evidence_refs`. All assigned mandatory deterministic IDs must appear exactly once. `PASS` requires actual supported checks; `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE` prevents semantic dispatch when mandatory. Absent required checks never pass.

## Verifier assessment

Producer: independently assigned read-only verifier CC. Consumer: protected host gate. [Schema](schemas/verifier-assessment.schema.json).

Required fields: `schema_version`, exact `subject_ref`, `review_context_ref`, `verdict`, nonempty `findings`, `uncertainties`, `limitations`, nullable `required_correction`. Each finding has `criterion_id`, `outcome`, `reason`, nonempty `evidence_refs`. Cover every required criterion exactly once. Findings identify the obligation and evidence, not replacement work.

Assessment verdicts use the PRD outcome vocabulary: `PASS`, `PASS_WITH_KNOWN_LIMITATIONS`, `FAIL`, `ENVIRONMENT_BLOCKED`, `INCONCLUSIVE`. They are checking data, not control actions. Mandatory failure or unresolved uncertainty cannot accompany an advancing assessment. Known limitations can advance only when no mandatory obligation is unsatisfied. Missing required evidence means unavailable/inconclusive, not inferred success.

The protected review context binds subject, original/accepted inputs, node contract, CC/dependency pins, assigned criteria/profile, policy, deterministic results, observations and allowed evidence audience. Producer narratives are untrusted diagnostics. The verifier does not obtain hidden RSI data or mutate outputs. For Intent it evaluates the submitted IR's usefulness and fidelity, not a second independently authored response to the prompt.

## Gate decision

Producer: protected gate host. Consumers: durable run-state, scheduler and inspection/export. [Schema](schemas/gate-decision.schema.json).

| Required fields | Meaning |
|---|---|
| `schema_version`, `id`, `recorded_at` | Record identity and UTC timestamp |
| `run_id`, `node_id`, `attempt_id` | Exact invocation/aggregate context |
| `contract_ref`, `invocation_refs` | Node Execution Contract and all participating observed invocations |
| `policy_ref`, `check_plan_ref` | Fixed authority/obligations; bound plan pins profile/check definitions and participating CC/dependencies |
| `input_refs`, `output_refs` | Exact accepted inputs and captured reviewed subjects |
| `deterministic_result_ref`, `assessment_ref` | Checking records; assessment is null when Tier 1 prevented review |
| `verdict`, `reasons` | Protected interpretation and criterion/evidence explanations |
| `action`, `accepted_refs` | `advance` only for permitted verdict plus durable acceptance; `halt` publishes no accepted references |

The host validates assessment structure, source/subject/context binding, criterion coverage and consistency with deterministic results. Every mandatory obligation must pass. Advancing verdicts are only `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`; all other outcomes halt. Producer/verifier readiness, instructions or a matching JSON shape grant no control authority.

Accepted references must be the exact reviewed output subset fulfilling required node outputs. Persist immutable artifacts and decision before the accepted-output commit becomes scheduler readiness. A proposed decision file is not a successful database commit. Persistence failure keeps readiness blocked, even if an assessment passed. New attempts/policy/subjects need new decisions.

Scientific `Evaluation_Verdict.json` has its own classification and measurement-to-criterion rationale. It is never copied into the gate verdict as an automatic halt. Valid scientific `FAIL` can be reviewed as conformant and yield infrastructure `PASS` for Delivery.
