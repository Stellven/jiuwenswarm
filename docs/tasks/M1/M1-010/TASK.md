# TASK: M1-010 - Bounded literature search and evidence-grounded ideation

Current user scope: prepare PRD-derived documentation and a provisional TASK/Spec Kit breakdown only. No implementation, test execution, commit or deployment is requested by this card.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-010 / r1 / 2026-10-01 |
| Parent TASKS | [M1 register](../TASKS.md) |
| Executor / collaborators | Documentation executor: Codex; implementation executor: UNASSIGNED |
| Requested outcome and instruction/source | Prepare a bounded task and fill PRD-supported native artifacts under Code SOP v2; user request dated 2026-10-01. Product outcome: Bounded literature search and evidence-grounded ideation. |
| Included scope / exclusions | Admitted search_capsule generates a static query list, retrieves local and bounded academic evidence via allowlisted deepsearch, extracts verbatim query-linked text and produces 1–3 cited candidate ideas. Dynamic query reformulation, unconstrained web/browser scraping, parallel multi-agent search, authority/bias/geographic source evaluation, historical trend/cross-domain mapping, unsupported speculation and recursive search-coverage self-reflection are outside Phase 1. |
| PRD clause and architecture node references | [PRD-Full.r1](../sources/PRD-Full.r1.txt), §3.3.1–§3.3.6 (lines 578–632); applicable §§1.3–1.6 and 2. Source SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes. Architecture: PENDING_SOURCE; node/edge references: PENDING_DESIGN. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm; observed documentation branch ai4r_xiaoyang; observed HEAD a8f36245a83358a606bf00f83a64b3353a41c4cd. These identify the preparation checkout, not a tested implementation candidate. |
| Affected code/document paths | This TASK and specs/M1-010-search-ideation/{spec,plan,tasks}.md. Source/test/config implementation paths: PENDING_DESIGN. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | [specs/M1-010-search-ideation/](../../../../specs/M1-010-search-ideation/) | One registered directory for this TASK |
| spec.md | [spec](../../../../specs/M1-010-search-ideation/spec.md) | Source-derived requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-010-search-ideation/plan.md) | Provisional behavioral blocks and verification procedures; technical design remains pending |
| tasks.md | [tasks](../../../../specs/M1-010-search-ideation/tasks.md) | Work/progress and acceptance-to-evidence correspondence |
| evidence/ | specs/M1-010-search-ideation/evidence/ (create on actual runs) | Actual run records and raw artifacts; none exist for this TASK |
| Supporting artifacts | None | No parallel schema or review/handoff card is introduced |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| Architecture source: PENDING_SOURCE | Technical realization of PRD semantics and final interface revision | Needed before implementation/schema/candidate-dependent checks; not needed for source-derived spec preparation | All blocks; T001–T002 |
| [M1-008](../M1-008/TASK.md), M1-IF-008@r0 | Canonical upstream run/configuration/resource or research artifact semantics | Definition can be linked now; actual provider is required for connected V90, not completion of all provider/system work | plan.md B01–B03; T001, T002, T090 |
| [M1-009](../M1-009/TASK.md), M1-IF-009@r0 | Canonical upstream run/configuration/resource or research artifact semantics | Definition can be linked now; actual provider is required for connected V90, not completion of all provider/system work | plan.md B01–B03; T001, T002, T090 |
| [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Shared admitted CC execution, static route, run evidence, orchestration and authoritative Gate | Resolve definitions before wiring; actual connected services required for V90. Gate release policy is not owned here | All blocks; T001–T002, T090 |
| [M1-011](../M1-011/TASK.md); [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Consumer wiring and integrated candidate/journeys | Needed for relevant boundary/system checks, not a requirement that consumer/system TASKs already be fully verified | V90 / T090; T091 |

Definition dependency order is PRD semantics -> Architecture-backed agreements -> provider/consumer wiring -> boundary verification. References to consumers do not create a circular full-TASK completion dependency.

## 4. Embedded cross-module agreements
### M1-IF-010 at r0
**Status: provisional PRD semantic allocation; NOT implementation-ready.** r0 records source responsibilities, not an approved payload schema, API or runtime architecture. Architecture must refine it into an implementation-ready revision while preserving PRD behavior.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider M1-010; consumers M1-011, M1-007 (artifact/evidence review), M1-005 (evidence preservation) and M1-SYSTEM (journey verification) |
| Purpose / source requirement | Bounded literature search and evidence-grounded ideation; §3.3.1–§3.3.6 (lines 578–632) |
| Inputs: fields, types, units, required/optional, validation | Accepted Research Brief and ingested local reference buffer; admitted search_capsule.md contract and approved deepsearch connectors/bounds. Typed query/result/citation schemas and connector APIs: PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Candidate_Set.json containing 1–3 candidate ideas with mapped explicit document-title/author/local-filename citations; query-grouped verbatim grounding chunks and retrieval evidence are retained for Gate. Output requires independent schema/resource/evidence verification before screening. |
| States and invariants | Fixed Phase 1 research responsibility; run/stage/capsule attribution; governed advancement only after an advancing durable Gate record; no silent upstream-artifact modification, manufactured evidence or autonomous self-repair. Scientific conclusion ownership stays with M1-015. |
| Errors, timeout, retry, cancellation | Source-defined invalid/inadmissible outputs halt autonomous advancement and preserve available evidence. Shared runner/Gate enforce applicable budgets and human failure handling. No autonomous retry/replanning loop is added. Exact error types, timeout propagation, cancellation and explicit-restart representation: PENDING_DESIGN. |
| Side effects and idempotency | Only contract-declared artifact/evidence writes and permitted tools/resources. Bounded allowlisted academic requests are permitted; arbitrary crawling is not. Idempotency keys, duplicate submission and replay handling: PENDING_DESIGN; no exactly-once guarantee is invented. |
| Compatibility and migration | Initial r0 semantics only. Architecture changes require a new IF revision, consumer alignment and updated TASKS allocation/index; field changes cannot silently change PRD behavior. |
| Machine-readable schema / source path | None; PENDING_DESIGN. Future generated schemas must reference this canonical IF revision rather than define competing semantics. |
| Provider/consumer verification responsibilities | M1-010/V01–V07 cover provider behavior in plan.md; M1-010/V90 connects actual upstream/shared/downstream boundaries. Consumer-native checks and M1-SYSTEM verify their owned behavior; final system evidence is separate. |
| Open agreement questions | See Q entries in section 5. Technical schema, transport, ownership boundaries, implementation paths and compatibility mechanics await Architecture. |

Consumed agreements: [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Canonical owners retain their definitions; no consumed schema is copied here.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-010-01 / 2026-10-01 | Architecture PENDING_SOURCE: bind search/output/citation schemas, source-text normalization, connector interface/error policy and code/test paths. No connector availability has been verified by documentation work. | All blocks and IF M1-IF-010@r0 | Only dependent implementation/checks wait; all execution currently NOT_RUN. A resolved material change triggers AC/IF/candidate impact assessment. | UNASSIGNED; record supplied source/design decision in the owning native artifact and update source/IF references |
| Q-010-02 / 2026-10-01 | Record the designated academic connectors, permitted query bounds and adopted Top-K value before numeric/real-service checks; PRD's connector list and maximum 5 are examples. | AC-002 / B02 / V02,V90 | Only dependent implementation/checks wait; all execution currently NOT_RUN. A resolved material change triggers AC/IF/candidate impact assessment. | UNASSIGNED; record supplied source/design decision in the owning native artifact and update source/IF references |
| Q-010-03 / 2026-10-01 | Zero usable evidence/zero supportable ideas is not permission to invent one; exact stage outcome/diagnostic needs local specification using the shared fail-fast Gate policy. | AC-005–AC-007 / B03 / V05–V07,V90 | Only dependent implementation/checks wait; all execution currently NOT_RUN. A resolved material change triggers AC/IF/candidate impact assessment. | UNASSIGNED; record supplied source/design decision in the owning native artifact and update source/IF references |

Progress remains in [tasks.md](../../../../specs/M1-010-search-ideation/tasks.md). There is no separate reviewer or authorization gate.

