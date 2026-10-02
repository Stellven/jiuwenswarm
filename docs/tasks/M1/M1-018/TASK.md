# TASK: M1-018 - Required offline capsule improvement and security validation

Latest-PRD documentation update under Code SOP v2. Product requirements in the attachment are source material, not instructions to execute the product. No implementation, model execution or runtime verification is performed.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-018 / r2 / 2026-10-02 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | Implementation executor UNASSIGNED; documentation preparation by Codex |
| Requested outcome and instruction/source | Update English TASK/Spec Kit records from the latest attached full PRD, follow Code SOP v2 and reserve architecture realization. Product outcome: a fixed offline RSI engine produces an independently evaluated bounded sandbox child of the required screening helper, preserves security/evidence and offers a candidate for human-controlled admission/activation. |
| Included scope / exclusions | Required Target 1: authorized code mutation of the pure rank_opportunities helper in a sandbox copy of screening_capsule. Conditional Target 2: authorized screening implementation text, including SKILL.md and explicitly mutable references/rubric.md, only when bounded headless model execution is available; otherwise deferred to M2 without blocking M1. Included: fixed shared core/target profiles, immutable referee, separated evaluation data, bounded evaluation, provenance, adversarial validation, inactive candidate submission and rollback integration. Excluded: live workflow mutation, automatic promotion, improver self-modification, contract/schema/effect changes, referee/security-policy mutation, hidden-test authorship/selection by RSI, multi-file code mutation, physical-operator/dependency mutation, training, routing/budget optimization and publication. |
| PRD clause and architecture node references | [PRD-Full.r2](../sources/PRD-Full.r2.txt): §4.4 introduction and §§4.4.1–4.4.10; §§2.11–2.12, 4.1.4–4.1.5 and 6.11; applicable §§1.3–1.6/global §§1–2. Consumed provisioning §§5.2.1/5.4.3 owned by M1-017/M1-002. Capture r2 / 2026-10-02 / 200082 bytes / SHA256 44928035205BDEBAE205D2B458BD438C2C6E0103E4EB2D834C6A93E1CFA37294; original D:/chrome_download/PRD - Full (1).txt. Architecture source/node IDs PENDING_SOURCE. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c recorded for initial documentation; not an executable candidate identity |
| Affected code/document paths | This TASK and specs/M1-018-offline-rsi/{spec.md,plan.md,tasks.md}; implementation/test/configuration paths PENDING_DESIGN |

Track 2 is required for M1 completion (§1.3), separate from live Phase 1. Target 2 deferral does not waive Target 1 or security validation. M1-003 owns standard admission, human activation and rollback.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-018-offline-rsi/ | One registered directory for this TASK |
| spec.md | [spec](../../../../specs/M1-018-offline-rsi/spec.md) | Requirements, ACs and product thresholds |
| plan.md | [plan](../../../../specs/M1-018-offline-rsi/plan.md) | Behavior blocks/verification; architecture pending |
| tasks.md | [tasks](../../../../specs/M1-018-offline-rsi/tasks.md) | Work/progress/AC-to-evidence correspondence |
| evidence/ | specs/M1-018-offline-rsi/evidence/ | Actual run records/raw artifacts when checks execute; none currently |
| Supporting artifacts | None generated | No parallel approval, review, checklist or handoff cards |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-003](../M1-003/TASK.md) / M1-IF-003@r0 | Admitted parent, explicit mutation permissions, immutable compatibility boundaries, admission/human activation/rollback | Definition before profile binding; actual registry operations before connected checks | B01/B04/B07/B09; T001/T003/T009/T017/T021/T015 |
| [M1-011](../M1-011/TASK.md) / M1-IF-011@r0 | Screening parent/pure rank_opportunities behavior (§3.4.7), fixed dimensions, Top-1 and Opportunity_Card.json semantics | Stable parent/independent required tests before Target 1 evaluation; complete TASK acceptance not needed for documentation | B04/B07; T002/T009/T017 |
| [M1-005](../M1-005/TASK.md) / M1-IF-005@r0 | Governed recorded inputs, attributable observations and evidence persistence | Definitions before bindings; actual observations for run-derived replay/platform joins; manual seed fixtures permit cold start | B02/B04/B06/B08; T001/T002/T005/T009/T013/T019 |
| [M1-002](../M1-002/TASK.md) / M1-IF-002@r0 | Approved offline boundary, hidden-material protection and startup isolation check | Architecture before implementation; actual containment evidence before hidden/security acceptance | B01/B03/B08; T001/T007/T019 |
| [M1-007](../M1-007/TASK.md) / M1-IF-007@r0 | Independently frozen Evaluator/Verifier/check/governance boundary | Defined non-evolvable referee before proposals; actual enforcement before comparison/adversarial checks | B01/B03/B05/B08; T001/T003/T007/T011/T019 |
| [M1-017](../M1-017/TASK.md) / M1-IF-017@r0 | §5.2.1 offline workspace/protected fixture provisioning; §5.4.3 isolation readiness with M1-002 | Provisioning definitions before bindings; actual isolation before hidden evaluation; provisioning does not await loop completion | B02/B03/B08; T001/T002/T005/T007/T019 |
| [M1-001](../M1-001/TASK.md) / M1-IF-001@r0; [M1-004](../M1-004/TASK.md) / M1-IF-004@r0 | Same declared model/runtime for model-bearing comparisons; bounded headless execution for Target 2 | Approved comparable configuration; Target 2 runs only when its dependency is available | B01/B04/B07; T002/T009/T017/T023 |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Required isolated RSI journey and full M1 acceptance | Relevant block/boundary readiness before system acceptance; not a prerequisite to preparation | T016 |

r0 agreements remain preliminary until Architecture binds the technical definitions. Definition dependencies and actual provider/consumer readiness are separate; no whole-peer-completion cycle is added.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for Architecture. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-018 at r0
This remains a **preliminary PRD semantic agreement**, updated for capture r2. Architecture is PENDING_SOURCE; realization/representation PENDING_DESIGN. A source update does not finalize a technical interface. Bind the concrete agreement and consumers together and advance its revision before relying on changed technical behavior.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-018; consumers M1-002, M1-003, M1-005, M1-017, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | §§4.4.1–4.4.10/6.11: required bounded Target 1 with a fixed independent referee, attributable security/evaluation evidence and human-controlled adoption |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — Architecture owns payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — Architecture owns concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — Architecture owns runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — Architecture owns error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — Architecture owns effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — Architecture owns compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — Architecture owns actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | Q01 architecture; Q04 approved policy values; Q05 Target 2 availability; Q06 retained legacy Oracle cross-reference. |

Consumed IFs retain canonical owning TASKs in section 3. This TASK does not redefine provider schemas, registry decisions, security mechanisms or launch policies.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| M1-018-C01 / 2026-10-02 | r2: required helper Target 1, conditional text Target 2, fixed shared core/profiles, independent referee, tracking isolation, terminal final assessment, intentional security suite, explicit clearance and rollback. Remove obsolete numeric repetitions/fixture/headroom/query prescriptions, fresh-process mandate and export filename. | AC-001–009 revised; AC-010–012 appended; B01–06/V01–09 revised; B07–09/V10–12 appended; preliminary IF-018 remains r0 | All affected bindings use capture r2. No prior runtime evidence; future affected evidence becomes STALE. | Documentation update; implementation UNASSIGNED |
| M1-018-Q01 / 2026-10-02 | Architecture PENDING_SOURCE: exact payloads/APIs/IPC/topology/storage/launcher/accounts/permissions/key custody/network/error/configuration/check commands PENDING_DESIGN. | All dependent blocks/checks; IF-018 | Bind affected work only; independent AC/fixture preparation continues. | UNASSIGNED; register architecture without changing product requirements. |
| M1-018-Q02 / retired 2026-10-02 | Former hidden-set percentage-denominator ambiguity retired because the numerical prescription is absent in r2; ID not reused. | Former AC-008 interpretation | Removed constants cannot govern r2. | Resolved by source replacement; new policy question Q04. |
| M1-018-Q03 / retired 2026-10-02 | Former prescribed-repeat/lower-bound aggregation question retired because those prescriptions are absent in r2; ID not reused. | Former AC-001/003/005 aggregation | No obsolete algorithm/repetition count carried forward. | Resolved by source replacement; new policy question Q04. |
| M1-018-Q04 / 2026-10-02 | Approved scoring, minimum hidden seed fixtures, sufficient baseline headroom, loop cap and terminal final point are required but their values/complete definition are absent. | AC-001/002/003/005/008/009; B02/B03/B04/B05; V01/V02/V03/V05/V08/V09 | Affected runtime acceptance cannot pass without approved policy; no r1 defaults inherited. | UNASSIGNED; register source-backed policy before checks; product values PENDING_SOURCE, realization PENDING_DESIGN. |
| M1-018-Q05 / 2026-10-02 | Target 2 bounded headless model-execution availability unestablished. | AC-001/V01 conditional; B04/B07; T023 | Record actual available/unavailable basis; if unavailable, M2 deferral without blocking required Target 1/security. | UNASSIGNED; actual dependency evidence and scope decision. |
| M1-018-Q06 / 2026-10-02 | §§5.2.1/5.4.3 retain Oracle/POSIX/startup provisions and an old §4.4.9 design cross-reference; rewritten §4.4.9 leaves mechanisms to Architecture. | AC-009/V09/V90; M1-002/M1-017 | Preserve consumed constraints without assuming an oracle daemon or permission-only proof. | UNASSIGNED; architecture reconciles provisioning with independent hidden trust boundary; product conflicts require explicit PRD decision. |

Progress/results belong in tasks.md; implementation and runtime checks remain NOT_RUN.
