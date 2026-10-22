# TASK: M1-007 - Isolated API model router

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-007 / r5 / 2026-10-20 |
| Parent TASKS | [M1 register](../TASKS.md) |
| Executor / collaborators | Codex; read-only source reviewers collaborate under the same scope |
| Requested outcome and instruction/source | Separate router process/catalog/selection implementation, bounded IPC decision only, bridge-owned dispatch and fixed Codex fallback; [invoked user prompt](../source/Code/prompt.txt) |
| Included scope / exclusions | Phase 3 implementation required; full external integration non-blocking for core release. No commit, push, merge or deployment is implied. Broader statistical benchmark campaigns and automatic live RSI activation are excluded. |
| PRD clause and architecture node references | PRD 4.3, 6.12; architecture side-systems/router-design.md, model-catalog.md, reference/model-routing-contract.md, D44. Exact bytes: [source baseline](../source-baseline.json). |
| Working checkout / branch / base | D:/research/ai_for_research/runs/jiuwenswarm / ai4r_M1 / 3f8cc21cb4b497b844821dfec10a4b9e7140f9a4; supplied Code and QA were initially untracked |
| Affected code/document paths | jiuwenswarm/research_router/, tests/unit_tests/research_router/, tests/integration/research/router/; this TASK's native artifacts |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-007/ | One directory for this TASK |
| spec.md | [spec.md](spec.md) | r3; existing authority/IDs retained, I032 consumer compatibility and evidence correspondence |
| plan.md | [plan.md](plan.md) | r4; existing authority/IDs retained, I032 consumer compatibility and evidence correspondence |
| tasks.md | [tasks.md](tasks.md) | r4; existing authority/IDs retained, I032 consumer compatibility and evidence correspondence |
| evidence/ | evidence/ | Actual runs only; no runtime acceptance from registration |
| Supporting artifacts | [Program source baseline](../source-baseline.json) | Source identity; subordinate to registered authorities |

Native artifacts are created only during their corresponding Spec Kit phases. spec.md r3 and reviewed plan.md r2 now exist; tasks.md r2 now records the ordered implementation/verification work and evidence matrices. Canonical consumed revisions follow TASKS; the owned M1-IF-008 remains r1. Registration or a specification does not establish implementation or acceptance.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| M1-001 RouterPort definition; M1-002 selected-Capsule producer; real API qualification only when exercising such routes | Adopt the supplied contracts with one owning TASK per interface | Definitions before dependent plan; real implementation/resources before boundary/system verification | Plan blocks: M1-007/B01, M1-007/B02, M1-007/B03, M1-007/B04, M1-007/B05; native work IDs and AC/V evidence correspondence: tasks.md |

Contract-definition order is distinct from implementation order. Define M1-006's minimal client boundary and M1-001/002 shared seams early; full shell integration does not gate independent compiler/research preparation.

## 4. Embedded cross-module agreements

### M1-IF-008 at r1 - Separate API-router selection implementation

This TASK adopts the exact frozen referenced field/schema contracts by reference as its canonical agreement. Required fields, types, units, validation and compatibility are those pinned definitions plus the explicit amendments below; this is not a parallel paraphrased schema. Generated schemas will implement this IF/revision during the ordered planning/implementation phases.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | M1-007 -> M1-001 RouterPort only; authorized router audit inspection |
| Purpose / source requirement | side-systems/router-design.md; model-catalog.md; routing-acceptance.md; reference/model-routing-contract.md; exact file bytes and versions are pinned by [source-baseline.json](../source-baseline.json). Locators above are relative to the supplied source/Architecture_Design package unless explicitly QA. |
| Inputs: fields, types, units, required/optional, validation | Protected verified request/context, approved enabled profile, frozen qualified catalog/development aggregates, compatible budget/resource/access facts and authenticated execution identity. Adopted type/version set: The shared selected-Capsule/request/model-route records are owned by M1-IF-001; this IF owns process/catalog/profile eligibility, execution claim and router event semantics from the frozen router design. |
| Outputs: fields, types, units, semantics, guarantees | Eligible compatible choice with exclusions and immutable router audit, or source-defined halt/failure; no provider result, accepted output or bridge route record. |
| States and invariants | Separate killable credential-free selection process; no hot-path imports. Zero selection-model calls in development_profile; bounded_llm_ablation refused inM1. Protect reservations and qualification scope; registry entry alone is not enabled access. |
| Errors, timeout, retry, cancellation | Independent30s deadline/ready validity; unapproved/invalid/missing/error/timeout/no-route gets source-prescribed response to M1-IF-001. Atomic execution claim reconciles duplicates and forbids cross-user/changed-content reuse. Alternate at most once before freeze within original eligibility; no after-start replay. |
| Side effects and idempotency | Router writes its decisions/events before reply. Audit failure is attributed failure/fallback; it performs no provider invocation or credential access. Request cancellation ends selection/claim ownership without duplicating dispatch. |
| Compatibility and migration | Preserve exact catalog/profile/adapter qualification identities and M1-IF-001 shared versions. No quality/cost claim from source shortlist, mock endpoints or uncovered measurements. |
| Machine-readable schema / source path | [Critical schema catalog](../source/Architecture_Design/reference/catalog.json) and [field contracts](../source/Architecture_Design/reference/field-contracts.json), with referenced owning pages; generated implementation schemas are not created yet. Sidecar records use their owning benchmark-runner tables. |
| Provider/consumer verification responsibilities | Provider and consumer procedures are mapped to qualified V IDs in plan.md Verification Design. tasks.md owns their AC-to-work/evidence correspondence. No runtime PASS is established by design. |
| Open agreement questions | No unresolved product-intent question. Actual endpoint/credential/hardware/custody availability remains an execution prerequisite only for the paths that require it. Internal implementation/framing is selected in plan without widening this agreement. |

Consumed agreements: [M1-IF-001@r1](../M1-001/TASK.md#4-embedded-cross-module-agreements), [M1-IF-002@r2](../M1-002/TASK.md#4-embedded-cross-module-agreements), [M1-IF-003@r1](../M1-002/TASK.md#4-embedded-cross-module-agreements).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-C003 / 2026-10-16 | Invoked prompt supplies full-M1 snapshot and all-phases implementation plus separate four-case QA scope; supersedes earlier compiler-only assignment for this request | Current TASK scope and parent source allocation | Historical AI4R-001/DEVTOOLS results unchanged; no acceptance reused | Codex / current user request |
| M1-I001 / 2026-10-16 | Source-resolved implementation binding: Fixed-call authorization. Consume M1-001 M1-I001 and M1-IF-001@r1: fixed Codex audit authorization is distinct from external router configuration. No external API profile/catalog is required for CodexRouter and no API RouteDecision is fabricated. Source: M1-001/TASK.md M1-I001; reference/model-routing-contract.md | Owning spec and IF r1; affected blocks/checks and work/evidence correspondence are mapped in plan.md/tasks.md | No prior M1 runtime evidence; consumers adopt this same canonical binding | Codex / source-specific reconciliation, not a fabricated new user approval |

Progress belongs in tasks.md when generated. Registration is not implementation, integration or verification.

C008 consumer revision reconciliation (2026-10-16): this TASK/spec r3 and plan/tasks r2 consume the existing canonical M1-IF-002@r2 aggregate Library limits. M1-IF-008@r1, all FR/AC/block/V/T identities, source bytes and behavior are unchanged. This corrects stale consumer metadata; old observed evidence retains its original pins and is not promoted.


### M1-I032 versioned scientific start/inspection consumer reconciliation

IF001r2 preserves this consumer's existing model/router/call fields, fixed Phase1 Codex, frozen choice/fallback and historical r1 provenance. Router returns a choice only and has no role in resource preparation, worker-start CAS, live owner authorization or lease release. No route, CC name, model tool budget or selected declaration label grants scientific effects. Captured snapshot eligibility timing remains original; explicit deferred deployment readiness/cancel/deadline predicates are enforced by their owners. An uncertain native scientific activation cannot be retried as a model dispatch.

The single field/behavior authorities are [M1-001 IF001r2](../M1-001/TASK.md#4-embedded-cross-module-agreements), [M1-002 IF003r3/IF016r2](../M1-002/TASK.md#4-embedded-cross-module-agreements). This consumer adds no parallel protocol fields, owning IF revision, public source field or authorization. Source allocation is TASKS I032; exact original sources: reference/model-routing-contract.md110-112; existing Capsule-model-routing shared boundary; owning001 IF001r2. Definitions may be prepared independently; dependent code follows current owner/neutral/consumer Analyze and independent RED, actual connected acceptance follows both implementations/resources.


2026-10-20 existing-function technical refinement: TASK r5, plan r4, tasks r4, unchanged spec r3. Owning004 captures fresh ordinary request/reference-document resources through the already allocated host intake boundary; original per-run bindings and exact source joins govern consumers. Owning001/007 optional router installation preserves fixed Codex and call-time integrity while supplying no unavailable API authority. Procedures and current source progress remain in registered native records. No public/source schema, interface identity, AC or work/check ID changes; C010 leaves current runtime acceptance NOT_RUN.
