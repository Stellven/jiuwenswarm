# TASK: M1-005 - Evidence foundations and run exports

**Current baseline (2026-10-06):** [Latest verbatim PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt) and [architecture decisions D1–D15](../../../../architecture/build-package/principles.md#decisions-and-source-amendments) apply to this task. Preserve existing AC/IF/work IDs; coding agents choose detailed schemas, APIs, code paths and checks in the native records. Delivery Phase 1 is the research baseline, Phase 2 is required offline RSI, and Phase 3 is expected dynamic integration: attempt available capabilities and record BLOCKED/INCOMPLETE dependencies; core-demo success does not complete all M1 work. Account identity/profile lifetime is distinct from local execution/workspace lifetime. Runtime evidence remains NOT_RUN.


## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-005 / r3 / 2026-10-06 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI. |
| Included scope / exclusions | Included: Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI. Excluded: No raw benchmark/telemetry logs in agent memory, external/vector/distributed stores, multi-user separation, trace redaction/deduplication, live telemetry dashboards or host CPU/GPU monitoring; no synthetic run generation or live writeback from offline experiments. All §4.5.5 extended graph management is deferred. Includes Effective Run Manifest and joinable local Observation/model-call records; requested settings alone are insufficient reproduction evidence. |
| PRD clause and architecture node references | [Registered PRD](../../../../architecture/build-package/sources/product/prd-m1-current-2026-10-06.txt): current PRD (2026-10-02), SHA256 6bd528778f0fd362eeff8bdbc76e60ae202fbe99cb879dd7fe24fd3b41762839, 232489 bytes; §4.5, §4.5.1, §4.5.2, §4.5.3, §4.5.4; §4.5.5 explicitly excluded; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; architecture nodes are not invented. Also §4.3.3, §5.3.1 and §5.6.5 govern joinable observations and actual effective-state/seed evidence. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / d9fe483ea64c273ef831886bfa83819f6d5bb21c; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/code/Missions/M1/M1-005/TASK.md; docs/code/Missions/M1/M1-005/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | docs/code/Missions/M1/M1-005/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | docs/code/Missions/M1/M1-005/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
| Supporting artifacts | None | No parallel cards or invented schemas; future support remains subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| [M1-003](../M1-003/TASK.md) / M1-IF-003@r0 | Capsule identity/hash/ports/effects and invocation observations | Definition before records; runner connection later | B02/B03; T001 and applicable boundary work |
| [M1-004](../M1-004/TASK.md) / M1-IF-004@r0 | Route/role/timing/failure and optional usage observations | Definition then real audit input; not full route-task completion | B02/B03; T001 and applicable boundary work |
| [M1-006](../M1-006/TASK.md) / M1-IF-006@r0 | Run/stage lifecycle and workspace evidence hooks | Definition before storage; actual integration later, not a Harness-completion prerequisite | B02; T001 and applicable boundary work |
| [M1-007](../M1-007/TASK.md) / M1-IF-007@r0 | Tier evidence and final gate records | Define persistence semantics before Gate/Harness integration | B02; T001 and applicable boundary work |
| [M1-018](../M1-018/TASK.md) / M1-IF-018@r0 | Offline consumer of frozen exports | Later consumption only; live evidence storage does not await full RSI implementation | B04; T001 and applicable boundary work |
| Master architecture / PENDING_SOURCE | Actual technical boundaries and implementation/check paths | Required only before affected implementation/real boundary checks; independent PRD preparation continues | T001 and unresolved technical work |
| [M1-SYSTEM](../M1-SYSTEM/TASK.md) | Candidate-wide journey verification | Final integration; not a prerequisite for block definitions or isolated checks | System contribution work in tasks.md |

Definition dependencies do not require a fully VERIFIED peer TASK. Define capsule/provider/evidence/gate semantics first; connect their implemented blocks later. This avoids treating runner -> Gate -> reviewer -> capsule as a circular sequence of whole-task completion.

## 4. Embedded cross-module agreements

All seven [minimum architecture inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt) remain reserved for task-level coding design. Source acceptance stays in spec.md; this section records provisional document allocation and leaves technical design unfilled.

### M1-IF-005 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provisional document allocation: provider M1-005; consumers M1-001, M1-002, M1-003, M1-004, M1-006, M1-007, M1-008, M1-009, M1-010, M1-011, M1-012, M1-013, M1-014, M1-015, M1-016, M1-017, M1-018, M1-019, M1-SYSTEM. Actual module/process/API topology is PENDING_DESIGN (minimum inputs 1–2). |
| Purpose / source requirement | Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI. Source: §4.5, §4.5.1, §4.5.2, §4.5.3, §4.5.4; §4.5.5 explicitly excluded; sequencing §6.4. |
| Inputs: fields, types, units, required/optional, validation | PENDING_DESIGN — The coding agent defines payloads, types, validation, units and API/IPC handoff (minimum inputs 1–2). Product input obligations remain in spec.md. |
| Outputs: fields, types, units, semantics, guarantees | PENDING_DESIGN — The coding agent defines concrete outputs and technical guarantees (minimum inputs 2 and 4). Source-defined observable results remain in spec.md. |
| States and invariants | PENDING_DESIGN — The coding agent defines runtime state, transitions and coordination (minimum inputs 1–3). Product invariants remain in spec.md. |
| Errors, timeout, retry, cancellation | PENDING_DESIGN — The coding agent defines error structures, propagation, timeout/cancellation and duplicate handling (minimum inputs 2–3). Source failure/restart rules remain in spec.md. |
| Side effects and idempotency | PENDING_DESIGN — The coding agent defines effect enforcement, writes, partial-write recovery and repeated-call mechanics (minimum inputs 2–5). Source effect restrictions remain in spec.md. |
| Compatibility and migration | Provisional r0 identity retained. PENDING_DESIGN — The coding agent defines compatibility/migration representation (minimum inputs 1–2). Source acceptance is unchanged by realization choices; update consumers and invalidate affected evidence on material revision. |
| Machine-readable schema / source path | PENDING_DESIGN — No schema or application path is supplied. Architecture binds locations, schemas and environments (minimum inputs 1–2 and 6). |
| Provider/consumer verification responsibilities | PENDING_DESIGN — The coding agent defines actual check entry points and fault-injection seams (minimum input 7). Required behavioral AC/V intent and evidence mapping remain in native plan.md/tasks.md; no executed result is claimed. |
| Open agreement questions | Architecture binds concrete file schemas/layout, durability/snapshot boundaries, run identity and partial-write recovery. Scorecards must handle unavailable usage truthfully. Export labels come from actual registered runs, not invented outcomes. |

Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../M1-018/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

Architecture reservation: [minimum inputs](../ARCHITECTURE_MINIMUM_INPUTS.txt), items 1-7, owns actual modules/code/processes, typed payload/API/error contracts, runtime coordination, storage/durability, security isolation, configuration realization and executable test entry points. These remain PENDING_DESIGN; no implementation mechanism is selected by this current PRD update.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture: [current design](../../../../architecture/build-package/README.md); detailed realization belongs to the coding agent; user requests document preparation only | All native records; M1-IF-005@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture binds concrete file schemas/layout, durability/snapshot boundaries, run identity and partial-write recovery. Scorecards must handle unavailable usage truthfully. Export labels come from actual registered runs, not invented outcomes. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |
| PRD-R2 / 2026-10-02 | §4.3.3, §4.5.2, §5.3.1, §5.6.5. Adds joinable attribution and actual effective manifest without asserting unavailable telemetry. | AC-003, AC-007; native plan/tasks correspondence; M1-IF-005@r0 | Invalidate affected earlier evidence if any; current candidate NOT_BUILT and runtime NOT_RUN. | UNASSIGNED; complete Implementation-dependent definitions before affected implementation. |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
