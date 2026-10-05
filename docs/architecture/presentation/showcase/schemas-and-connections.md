# Schemas and connections

[Start here](README.md) · Generated contract inventory · Field meanings remain at owners

## Rules for joining components

- Producer and consumer use the exact pinned port type/version. An explicit pinned adapter is required for a mismatch; the binder cannot silently coerce data. [Run plan](../../types/run-plan.md) and [Declaration](../../capsule/fields.md) own this rule.
- Released versions are immutable. Draft changes update the owner and all affected consumers together; release changes require a new version and migration decision. Controlled `ext` data does not allow unknown core fields. [Policies](../../policies.md) owns release control.
- [Research ports](capsules.md#research-ports-to-reconcile) and the [23-binding research baseline](../../archive/information-flow-fixed-research-2026-10-05.md) are retained baseline contracts. [Current M1 control flow](../../m1/control-flow.md) requires intent capsule/Gate ports, accepted requirement entry and planner/binder callers to be reconciled before coding handoff.
- Artifact references identify stored immutable evidence, not caller-selected filesystem paths. Validation includes existence, schema version, hash and authorization. [Storage](../../system/storage.md) owns resolution.

## Payload and record versions

Existing schema baseline generated from the [export manifest](../../exports/manifest.json). The version column uses each owner's vocabulary: numeric payload versions and named record versions are not interchangeable. Generated JSON schemas define shape; owner prose defines meaning and failure behavior.

<!-- generated:showcase-schemas -->
| Definition | Exact version | Owning field table | Generated schema |
|---|---|---|---|
| `benchmark_payload` | `2` | [owner](../../types/benchmark-payload.md) | [schema](../../exports/schemas/types/benchmark-payload.schema.json) |
| `code_hits` | `1` | [owner](../../types/code-hits.md) | [schema](../../exports/schemas/types/code-hits.schema.json) |
| `dependency_assessment` | `1` | [owner](../../types/dependency-assessment.md) | [schema](../../exports/schemas/types/dependency-assessment.schema.json) |
| `dependency_requirement` | `1` | [owner](../../types/dependency-requirement.md) | [schema](../../exports/schemas/types/dependency-requirement.schema.json) |
| `evaluation_verdict` | `2` | [owner](../../types/evaluation-verdict.md) | [schema](../../exports/schemas/types/evaluation-verdict.schema.json) |
| `evidence_bundle` | `1` | [owner](../../types/evidence-bundle.md) | [schema](../../exports/schemas/types/evidence-bundle.schema.json) |
| `hypothesis_blueprint` | `2` | [owner](../../types/hypothesis-blueprint.md) | [schema](../../exports/schemas/types/hypothesis-blueprint.schema.json) |
| `idea_set` | `1` | [owner](../../types/idea-set.md) | [schema](../../exports/schemas/types/idea-set.schema.json) |
| `intake` | `2` | [owner](../../types/intake.md) | [schema](../../exports/schemas/types/intake.schema.json) |
| `intent_ir` | `1` | [owner](../../types/intent-ir.md) | [schema](../../exports/schemas/types/intent-ir.schema.json) |
| `opportunity_card` | `2` | [owner](../../types/opportunity-card.md) | [schema](../../exports/schemas/types/opportunity-card.schema.json) |
| `poc_bundle` | `2` | [owner](../../types/poc-bundle.md) | [schema](../../exports/schemas/types/poc-bundle.schema.json) |
| `research_brief` | `1` | [owner](../../types/research-brief.md) | [schema](../../exports/schemas/types/research-brief.schema.json) |
| `research_report` | `2` | [owner](../../types/research-report.md) | [schema](../../exports/schemas/types/research-report.schema.json) |
| `resource_snapshot` | `1` | [owner](../../types/resource-snapshot.md) | [schema](../../exports/schemas/types/resource-snapshot.schema.json) |
| `run_plan` | `1` | [owner](../../types/run-plan.md) | [schema](../../exports/schemas/types/run-plan.schema.json) |
| `screening_assessments` | `2` | [owner](../../types/screening-assessments.md) | [schema](../../exports/schemas/types/screening-assessments.schema.json) |
| `search_hits` | `1` | [owner](../../types/search-hits.md) | [schema](../../exports/schemas/types/search-hits.schema.json) |
| `source_text` | `1` | [owner](../../types/source-text.md) | [schema](../../exports/schemas/types/source-text.schema.json) |
| `verifier_assessment` | `1` | [owner](../../types/verifier-assessment.md) | [schema](../../exports/schemas/types/verifier-assessment.schema.json) |
| `artifact` | `cc.artifact.v1` | [owner](../../schemas/artifact.md) | [schema](../../exports/schemas/records/artifact.schema.json) |
| `binding` | `cc.binding.v1` | [owner](../../schemas/binding.md) | [schema](../../exports/schemas/records/binding.schema.json) |
| `candidate` | `cc.candidate.v1` | [owner](../../schemas/candidate.md) | [schema](../../exports/schemas/records/candidate.schema.json) |
| `checks` | `cc.check.v1` | [owner](../../schemas/checks.md) | [schema](../../exports/schemas/records/checks.schema.json) |
| `finding` | `cc.finding.v1` | [owner](../../schemas/finding.md) | [schema](../../exports/schemas/records/finding.schema.json) |
| `observation` | `cc.observation.v1` | [owner](../../schemas/observation.md) | [schema](../../exports/schemas/records/observation.schema.json) |
| `port-types` | `cc.types.v1` | [owner](../../schemas/port-types.md) | [schema](../../exports/schemas/records/port-types.schema.json) |
| `standing` | `cc.standing.v1` | [owner](../../schemas/standing.md) | [schema](../../exports/schemas/records/standing.schema.json) |
| `verdict` | `cc.verdict.v1` | [owner](../../schemas/verdict.md) | [schema](../../exports/schemas/records/verdict.schema.json) |
| `verification-record` | `cc.verification.v1` | [owner](../../schemas/verification-record.md) | [schema](../../exports/schemas/records/verification-record.schema.json) |
| `declaration` | `cc.declaration.v1` | [owner](../../capsule/fields.md) | [schema](../../exports/schemas/records/declaration.schema.json) |
<!-- /generated:showcase-schemas -->

## Services and profiles

| Boundary | Shape owner | Behavior and callers |
|---|---|---|
| Runner, Binding, Observation and checks | [Record/schema index](../../schemas/schemas.md) | [Runner](../../capsule/runner.md), [toolchain](../../capsule/toolchain.md) |
| Gate evidence, criteria profiles and Verification | [Evidence bundle](../../types/evidence-bundle.md), [Verification](../../schemas/verification-record.md) | [Gate host](../../capsule/gate-host.md), [research Gates](../../m1/research-gates.md) |
| Model bridge, routing, authentication and call reservations | [Services v1](../../contracts/services-v1.schema.json) | [Authentication](../../system/model-auth.md), [routing](../../model-routing/README.md) |
| Planner request/proposal, validation and experiment profiles | [Services v1](../../contracts/services-v1.schema.json), [run plan](../../types/run-plan.md) | [Planner](../../system/planner.md), [experiments](../../system/experiments.md) |
| Benchmark request, handles, exports and profiles | [Services v1](../../contracts/services-v1.schema.json) | [Benchmark export](../../system/benchmark-export.md) |
| Retry, duplicates and recovery | [Services v1](../../contracts/services-v1.schema.json) | [Lifecycle](../../system/lifecycle.md) |
| Library snapshots, admission and activation | [Candidate](../../schemas/candidate.md), [Standing](../../schemas/standing.md), [Verdict](../../schemas/verdict.md) | [Library](../../capsule/library.md), [admission](../../capsule/admission.md) |

For exact invocation arguments and expected refusal records, follow the behavior owner, then its schema and [verification hooks](../../system/verification.md). The presentation is a navigation layer, not another field table.

[Next: validation and development](validation-and-development.md)
