# TASK: M0-001 — standalone whole Intent Compiler

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M0-001 / r1 / 2026-10-08 |
| Parent TASKS | [M0 register](../TASKS.md) |
| Executor / collaborators | Codex; delegated source/spec, runtime, verification and browser/client collaborators under the same task. |
| Requested outcome and instruction/source | Execute [Code_prompt.txt](../source/Code_Prompt/Code_prompt.txt) with the explicitly invoked local Spec Kit adapter: plan, analyze, implement, converge, remediate and verify only the complete standalone Intention Compiler. |
| Included scope / exclusions | Qualified intake → Intention/checks/verifier/protected acceptance → Requirements/checks/verifier/protected acceptance → node release. Includes required binding/model/storage/control/image foundations, authenticated browser/headless benchmark interfaces and bounded test consumer. Excludes downstream research stages, DAG initialization, advanced dynamic/interactive compilation, RSI and sidecar. No questions, AGENTS/constitution changes, commits/pushes/merges/deployment. |
| PRD clause and architecture node references | [Register allocation](../TASKS.md#3-source-coverage-allocation); exact supplied PRD Main §4.7 and relevant PRD Context §§1.4,2,3.1,3.2,4.1–4.3,4.5–4.6,5,6.5; Architecture Main completion/node/foundations/browser/proof and required Architecture Context dependency links. Source identity receipt: [source-baseline.json](source-baseline.json). |
| Working checkout / branch / base | `D:/research/ai_for_research/tests_whether_we_need_spec_kit/test_with_spec_kit`; branch `ai4r_test_with_spec_kit`; base `5787575ac145386809ccde868cdc21ade224d9f4`. Pre-existing source edits and deleted architecture/Verification README remain preserved. |
| Affected code/document paths | `standalone/intent_compiler/` (isolated Python package, TypeScript browser frontend, tests, schemas and deployment); `docs/code/Missions/M0/TASKS.md`; this feature directory; supplied `source/Token/token_usage.json` measurement fields only; `.specify/feature.json` exact feature selection. |

The requested scope is already authorized. No separate approval/review card is introduced. Runtime control questions are output data for future product users; this one-shot coding task asks none.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `docs/code/Missions/M0/M0-001/` | One directory for M0-001; native commands explicitly select it. |
| spec.md | [spec.md](spec.md) | Requirements, ACs and threshold provenance. |
| plan.md | [plan.md](plan.md) | Technical blocks, dependencies and verification procedures. |
| tasks.md | [tasks.md](tasks.md) | Sole work/progress and acceptance-to-evidence correspondence. |
| evidence/ | `docs/code/Missions/M0/M0-001/evidence/` | Actual observed verification runs, exact candidates and raw artifacts. |
| Supporting artifacts | [source-baseline.json](source-baseline.json); implementation schemas/declarations in `standalone/intent_compiler/` | Exact source receipt and executable forms subordinate to TASK agreements and native authorities. |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| No predecessor TASK | One bounded task owns compiler-only verification. | Source registration/spec/plan/tasks/analyze precede coding. | B01..B04; exact native T IDs in tasks.md. |
| M0-IF-001@r1 definition | Authenticated ordinary client information and lifecycle. | This TASK is authoritative; concrete versioned routes implement it. | B04; connected B01/B02/B03. |
| M0-IF-002@r1 definition | Exact released Brief2 semantics. | Schema/binding/acceptance definition before consumer implementation; committed release before actual consumption. | B02/B03/B04. |
| M0-IF-003@r1 definition | Protected approved model bridge. | Frozen configured endpoint/owned invocation and truthful readiness before live dispatch. | B02; B03 verifier, system checks. |
| Approved model access, runtime capability and telemetry | Genuine configured-model work/review; no mock substitution. | Readiness confirms needed model/auth/owned process or provider adapter; absent capability blocks live checks. | B02; AC-011,012,022. |
| Container runtime and prepared pinned image dependencies | Image startup, same origin, loopback publication and recreation evidence. | Functional daemon/runtime available before container execution; image build preparation can continue independently. | B04; AC-020. |
| Enforced required authority, filesystem/storage and memory/time/call boundaries | A truthful eligible profile. | Unsupported mandatory enforcement is unavailable, not a pass. | B01/B02/B04; AC-010..015,020. |

Definition dependencies are complete here. Environment prerequisites must be inspected, not invented; independent implementation and fixture verification continue when live model/image checks cannot run.

## 4. Embedded cross-module agreements

### M0-IF-001 at r1
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M0-001 application; consumers M0-001 browser/headless clients and external ordinary benchmark client. External client implementation/scoring is out of scope. |
| Purpose / source requirement | Benchmark contract items 1–4; architecture `automation.md` Client contract and campaign behavior, `field-catalog.md` client-readiness/submission/status/retrieval/cancellation/error. One versioned authenticated client boundary serves UI, headless and benchmark traffic. |
| Inputs: fields, types, units, required/optional, validation | Exact original request string and permitted local documents/resources, approved profile/configuration ID, unique `client_request_id`, authenticated account/workspace scope and optional requested seed if supported. Protected intake qualifies before producing `client-submission:1.0.0` with all catalog fields. Supported resources use `reference_document`, `project_asset`, `validation_data`; no arbitrary config/gate-state mutation. IDs are nonempty; incompatible interface, wrong target, unauthorized scope, invalid request/path/type/size or unavailable required prerequisite yields structured rejection. Repeating the same client ID with different input is a conflict. |
| Outputs: fields, types, units, semantics, guarantees | `client-readiness:1.0.0` gives schema/client-contract versions, stable instance/build identity, operations and storage/auth/model/required-enforcement prerequisite states/reasons; extensions provide supported compiler-only profile and payload schema versions. Submission returns allocated run ID or `client-error:1.0.0`. Reconciliation by request identity returns the existing run. `client-status:1.0.0` has all catalog fields, monotonic revision, stage/status, candidates versus accepted refs, last gate reasons and bundle ref. Cancellation/retrieval use their catalog1 field contracts. Versioned export names exact readable records, hashes/audience/omissions. |
| States and invariants | One active run; queued/running/in-progress → completed, halted, cancelled or paused. Client disconnect affects transport only. Candidate presence never establishes acceptance. Only the protected committed node release exposes external Brief success. Readiness distinguishes liveness from execution eligibility. Browser/API same origin; loopback host publication by default. |
| Errors, timeout, retry, cancellation | Stable category/message with request/run identity and permitted evidence/correction; finite headless timeout and non-success for non-completion. Reconcile uncertain transport instead of duplicate submission. Explicit scoped cancellation stops new dispatch and contains current work, retaining effects/evidence. No implicit capsule retry, repair, replay or human wait. Restart pauses interrupted attempts; fresh corrected request is a linked new run. |
| Side effects and idempotency | Submit creates durable protected run/intake records and bounded fixed compilation; same authorized request ID/input returns one run, including after transport loss/restart. Retrieve/observe are read-only. Cancellation is attributable/idempotent and cannot undo observed external effects. Credentials never appear in prompts, returned URLs or evidence exports. |
| Compatibility and migration | Client interface version `1.0.0`; individual payload contracts follow catalog versions. Explicit incompatible versions/target/profile reject rather than coerce. New shared fields/revisions require TASK/register/native updates and affected evidence invalidation. |
| Machine-readable schema / source path | Canonical upstream field definitions: `../source/Architecture_context/design-package/reference/field-contracts.json`, `field-catalog.md`; implementation schemas carry `M0-IF-001@r1`. Concrete routes are implementation choices in plan/README. |
| Provider/consumer verification responsibilities | M0-001 owns all connected checks for AC-015..020,022,023; concrete qualified V IDs in [plan](plan.md), current evidence correspondence in [tasks](tasks.md). Benchmark expectation/scoring remains outside product. |
| Open agreement questions | None affecting definition. Actual model/container/enforcement readiness is an observed environment condition; unavailable prerequisite blocks dependent execution. |

### M0-IF-002 at r1
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M0-001 protected enclosing-node gate; consumer M0-001 bounded compatibility test consumer. Future static SwarmFlow/Leader consumers are contextual and not implemented. |
| Purpose / source requirement | PRD §4.7.5, Context §3.2.7; architecture completion boundary, `reference/intent-and-requirements.md` Research Brief, `reference/checking.md` Subnode versus node release; benchmark completion paragraph. |
| Inputs: fields, types, units, required/optional, validation | Consumer receives exact immutable `Research_Brief.json` reference plus authoritative accepted-output/node-gate record. Its prerequisite chain is accepted Intent1, qualified intake2, permitted context/resources and protected defaults. Producer candidate uses critical `research-brief:2.0.0` schema with all required fields and attributable origins; local IDs/obligation references, typed constraints, resource inventories and assumptions must resolve. |
| Outputs: fields, types, units, semantics, guarantees | Research Brief2 required objective/scope, mandatory/preference separation, typed constraints/user metrics, deliverables, acceptance/evidence obligations, attributed defaults/unresolved items/confirmation and intake/Intent/context/input resources. Qualitative targets remain qualitative. Only exact durable node accepted-output2 record grants external consumption; all candidate/assessment/decisions remain inspectable separately. |
| States and invariants | Intent acceptance is intermediate; Requirements acceptance is internal; enclosing node acceptance publishes the external Brief. Requirements consumes only exact accepted Intent. Three protected work/node decisions retain scope and internal references; final aggregation reuses Requirements assessment with zero additional semantic calls. File presence, overall verifier PASS and producer readiness grant no release. |
| Errors, timeout, retry, cancellation | Schema/identity/source/obligation mismatch, blocking uncertainty, missing criterion/evidence, invalid limits/defaults or uncommitted storage yields halt. No automatic rewrite or retry. Consumer rejects candidate/uncommitted refs and unsupported Brief version. Cancellation/storage fault/restart cannot create a release or replay. |
| Side effects and idempotency | Protected immutable capture and atomic durable acceptance only. Consumer validates/reads without planning or scientific execution. Acceptance is exact content/run/attempt/gate/commit identity and does not mutate past records. |
| Compatibility and migration | Brief2.0.0 external interface; Intent1.0.0 intermediate; node2.0.0/subnode1.0.0/gate2.0.0 accepted-output2.0.0 evidence per catalog. Old node1 is retired and cannot be treated as enclosing node2. Changes require revised agreement and revalidation. |
| Machine-readable schema / source path | `../source/Architecture_context/design-package/reference/schemas/research-brief.schema.json`, `common.schema.json`, `gate-decision.schema.json`; catalog/field-contracts define node2/accepted-output2. Implementation artifacts carry `M0-IF-002@r1`. |
| Provider/consumer verification responsibilities | M0-001 AC-006..009,013,021,022 boundary/system checks, with exact V procedures in plan and evidence links in tasks. Bounded consumer proves interface compatibility only. |
| Open agreement questions | None; no invented experimental protocol/quality threshold. Required external environment evidence remains separately blocked if unavailable. |

### M0-IF-003 at r1
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M0-001 protected audited model bridge; consumers M0-001 governed Intention, Intent verifier, Requirements and Requirements verifier subnodes. |
| Purpose / source requirement | Architecture Main foundations, `model-routing.md` all compiler-applicable sections, `placement.md` deployment/startup IPC, `reference/other-contracts.md` client/model boundary; PRD §§4.7.4 and relevant Context §4.3. |
| Inputs: fields, types, units, required/optional, validation | Protected invocation identity, exact admitted declaration/body/dependency/admission refs, one-CC subnode/parent contract, approved static endpoint/role/profile, permitted immutable task/context evidence, effective time/call/resource limits, optional requested seed. Effective authority is admission ∩ parent ∩ child ∩ run policy, with no permission pooling. Missing eligibility/access/disclosure/enforcement blocks dispatch. |
| Outputs: fields, types, units, semantics, guarantees | Actual response/error captured unchanged; requested/effective provider/model/configuration with identity basis; monotonic observed duration in seconds, actual model call count, available tokens/cost with explicit null/unavailable reasons; input/output/trace refs. Separate owned verifier invocation/context excludes producer conversation and supplies independently protected criteria. No model grants release. |
| States and invariants | Fixed order: Intention, Intent verifier if deterministic checks pass, Requirements only after durable Intent acceptance, Requirements verifier if checks pass. At most one work and one verifier call per stage, no third semantic node-finalization call. Endpoint choice is frozen for a run; static Codex fallback interface is retained without hidden switching. Mocks are explicit isolated smoke adapters and cannot establish live acceptance. |
| Errors, timeout, retry, cancellation | Missing/unauthenticated endpoint, unsupported capability, timeout, no output, malformed result or denied effect halts and captures real observation/failure receipt. No retry, repair, cache substitution, replay or in-flight endpoint replacement. Explicit cancellation contains owned invocation and prevents successor dispatch. |
| Side effects and idempotency | Only audited configured model disclosure and protected capture. Credentials/configuration and owned IPC stay outside CC permissions/exports; no public adapter TCP listener. Observations append rather than rewrite. A cancelled/failed invocation may have observed irreversible provider effects and unknown billing, recorded honestly. |
| Compatibility and migration | `model-route:1.0.0`, `invocation-observation:2.0.0`, critical capsule/subnode formats1 and node2; all pinned per catalog. Implementation bridge may use protected owned CLI/IPC or approved provider adapter. Unknown served identity is labelled, not asserted from config alone. |
| Machine-readable schema / source path | Upstream `reference/field-contracts.json`, `schemas/capsule-declaration.schema.json`, `schemas/subnode-execution-contract.schema.json`; implementation interfaces carry `M0-IF-003@r1`. |
| Provider/consumer verification responsibilities | M0-001 AC-010..012,014,022; fixture/real bridge and failure/timeout/cancellation checks in plan, current observations in tasks/evidence. Separate actual-model evidence required. |
| Open agreement questions | Approved model access/effective identity and reliable usage telemetry depend on protected operator configuration. Unsupported mandatory enforcement blocks the affected profile. No model identifier is fabricated. |

Consumed agreements: all three owned agreements are consumed internally at their canonical sections above; no external TASK interface prerequisite is introduced.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-08 | Whole compiler completion supersedes historical Intent-only slice; source `immediate-plan.md`. | All ACs / B01..B04 / all IFs | Future scope change invalidates relevant compiler journeys; no historical run is rewritten. | Codex; current registered whole-node scope. |
| D02 / 2026-10-08 | Fixed multi-pass D5 and container D6 explicit exceptions; register S01/S04. | AC-003..012,020 / IF-001,003 | Frozen limits, topology and deployment checks change together. | Codex; architecture authorizes exception. |
| D03 / 2026-10-08 | Protected hashes conflict with PRD Context §3.1.4 blacklist; register S02. | AC-002,013,018,023 / IF-001..003 | Current architecture/benchmark exact-hash proof governs this task; preserve source truth. | Codex; explicit current source requirement. |
| D04 / 2026-10-08 | Standalone code/frontend follows direct coding instruction instead of existing/native app reuse; register S03. | All ACs / B01..B04 | No existing app imports or copied existing implementation; exact candidate manifests cover only isolated execution inputs plus source contracts. | Codex; user instruction precedence. |
| D05 / 2026-10-08 | Protected model/container/memory-enforcement prerequisites may be absent. | AC-011,012,015,020,022 / IF-003 | Live checks remain BLOCKED until actual prerequisites exist; fixture passes do not fill gaps. | Codex; observe current environment. |
| D06 / 2026-10-08 | No prescribed production quality rate, numeric performance SLA or authoritative served-model list. | AC-012,022,023 | Freeze labelled expectations and implementation safety bounds before observations; record sampled outcomes/unavailable identity/telemetry. | Codex; plan provides explicit implementation configuration, no invented product claims. |

Progress and runtime results remain in tasks.md. Material source/interface changes update parent allocation, this TASK and affected native records, then invalidate matching evidence.
