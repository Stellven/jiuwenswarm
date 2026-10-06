# TASK: M1-010 - Bounded literature search and evidence-grounded ideation

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.


Current user scope: update latest-PRD-derived documentation and a provisional TASK/Spec Kit breakdown only. No implementation, test execution, commit or deployment is requested by this card.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-010 / r3 / 2026-10-06 |
| Parent TASKS | [M1 register](../TASKS.md) |
| Executor / collaborators | Documentation executor: Codex; implementation executor: UNASSIGNED |
| Requested outcome and instruction/source | Prepare a bounded task and fill PRD-supported native artifacts under Code SOP v2; user request dated 2026-10-02. Product outcome: Bounded literature search and evidence-grounded ideation. |
| Included scope / exclusions | Admitted search_capsule generates a static query list, retrieves local and bounded academic evidence via allowlisted deepsearch, extracts verbatim query-linked text and produces 1–3 cited candidate ideas. Dynamic query reformulation, unconstrained web/browser scraping, parallel multi-agent search, authority/bias/geographic source evaluation, historical trend/cross-domain mapping, unsupported speculation and recursive search-coverage self-reflection are outside Phase 1. |
| PRD clause and architecture node references | [Current PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt), §3.3.1–§3.3.6; applicable §§1.3–1.6 and 2. Source SHA256 6bd528778f0fd362eeff8bdbc76e60ae202fbe99cb879dd7fe24fd3b41762839, 232489 bytes. Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; node/edge references: PENDING_DESIGN. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm; observed documentation branch ai4r_xiaoyang; observed HEAD d9fe483ea64c273ef831886bfa83819f6d5bb21c. These identify the preparation checkout, not a tested implementation candidate. |
| Affected code/document paths | This TASK and docs/code/Missions/M1/M1-010/{spec,plan,tasks}.md. Source/test/config implementation paths: PENDING_DESIGN. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | [docs/code/Missions/M1/M1-010/](.) | One registered directory for this TASK |
| spec.md | [spec](spec.md) | Source-derived requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Provisional behavioral blocks and verification procedures; technical design remains pending |
| tasks.md | [tasks](tasks.md) | Work/progress and acceptance-to-evidence correspondence |
| evidence/ | docs/code/Missions/M1/M1-010/evidence/ (create on actual runs) | Actual run records and raw artifacts; none exist for this TASK |
| Supporting artifacts | None | No parallel schema or review/handoff card is introduced |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| Architecture supplied; task-level realization remains with the coding agent | Apply current architecture; coding agents finalize task-level interfaces | Needed before implementation/schema/candidate-dependent checks; not needed for source-derived spec preparation | All blocks; T001–T002 |
| [M1-008](../M1-008/TASK.md), M1-IF-008@r0 | Canonical upstream run/configuration/resource or research artifact semantics | Definition can be linked now; actual provider is required for connected V90, not completion of all provider/system work | plan.md B01–B03; T001, T002, T002 |
| [M1-009](../M1-009/TASK.md), M1-IF-009@r0 | Canonical upstream run/configuration/resource or research artifact semantics | Definition can be linked now; actual provider is required for connected V90, not completion of all provider/system work | plan.md B01–B03; T001, T002, T002 |
| [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements) | Shared admitted CC execution, static route, run evidence, orchestration and authoritative Gate | Resolve definitions before wiring; actual connected services required for V90. Gate release policy is not owned here | All blocks; T001–T002, T002 |
| [M1-011](../M1-011/TASK.md); [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Consumer wiring and integrated candidate/journeys | Needed for relevant boundary/system checks, not a requirement that consumer/system TASKs already be fully verified | V90 / T002; T091 |

Definition dependency order is PRD semantics -> Architecture-backed agreements -> provider/consumer wiring -> boundary verification. References to consumers do not create a circular full-TASK completion dependency.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for task-level coding design. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-010 at r0
**Status: provisional PRD semantic allocation; NOT implementation-ready.** r0 records source responsibilities, not an approved payload schema, API or runtime architecture. Architecture must refine it into an implementation-ready revision while preserving PRD behavior.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-010; consumers M1-011, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | Bounded literature search and evidence-grounded ideation; §3.3.1–§3.3.6 |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — The coding agent defines payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — The coding agent defines concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — The coding agent defines runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — The coding agent defines error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — The coding agent defines effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — The coding agent defines compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — The coding agent defines actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | See Q entries in section 5. Technical schema, transport, ownership boundaries, implementation paths and compatibility mechanics await Architecture. |

Consumed agreements: [M1-IF-008@r0](../M1-008/TASK.md#4-embedded-cross-module-agreements); [M1-IF-009@r0](../M1-009/TASK.md#4-embedded-cross-module-agreements); [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-005@r0](../M1-005/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements). Canonical owners retain their definitions; no consumed schema is copied here.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-010-01 / 2026-10-01 | Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent: bind search/output/citation schemas, source-text normalization, connector interface/error policy and code/test paths. No connector availability has been verified by documentation work. | All blocks and IF M1-IF-010@r0 | Only dependent implementation/checks wait; all execution currently NOT_RUN. A resolved material change triggers AC/IF/candidate impact assessment. | UNASSIGNED; record supplied source/design decision in the owning native artifact and update source/IF references |
| Q-010-02 / 2026-10-01 | Record the designated academic connectors, permitted query bounds and adopted Top-K value before numeric/real-service checks; PRD's connector list and maximum 5 are examples. | AC-002 / B02 / V02,V90 | Only dependent implementation/checks wait; all execution currently NOT_RUN. A resolved material change triggers AC/IF/candidate impact assessment. | UNASSIGNED; record supplied source/design decision in the owning native artifact and update source/IF references |
| Q-010-03 / 2026-10-01 | Zero usable evidence/zero supportable ideas is not permission to invent one; exact stage outcome/diagnostic needs local specification using the shared fail-fast Gate policy. | AC-005–AC-007 / B03 / V05–V07,V90 | Only dependent implementation/checks wait; all execution currently NOT_RUN. A resolved material change triggers AC/IF/candidate impact assessment. | UNASSIGNED; record supplied source/design decision in the owning native artifact and update source/IF references |

| DOC-R2 / 2026-10-02 | Latest PRD capture r2 replaces the active r1 product baseline. Rebase clauses and preserve stable AC/IF identities; all technical agreement fields remain reserved for task-level coding design. | spec/plan/tasks r2; provisional M1-IF-010@r0 | No runtime evidence exists; affected future checks remain NOT_RUN. | UNASSIGNED; bind Architecture only before dependent realization |

Progress remains in [tasks.md](tasks.md). There is no separate reviewer or authorization gate.
