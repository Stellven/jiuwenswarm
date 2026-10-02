# TASK: M1-005 - Evidence foundations and run exports

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-005 / r1 / 2026-10-01 |
| Parent TASKS | [M1](../TASKS.md) |
| Executor / collaborators | UNASSIGNED for implementation; Codex prepares documents at the user's request |
| Requested outcome and instruction/source | Prepare English TASK/Spec Kit documents from PRD Full. Current action scope: documentation only; no application changes, runtime tests or commits. Future product outcome: Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI. |
| Included scope / exclusions | Included: Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI. Excluded: No raw benchmark/telemetry logs in agent memory, external/vector/distributed stores, multi-user separation, trace redaction/deduplication, live telemetry dashboards or host CPU/GPU monitoring; no synthetic run generation or live writeback from offline experiments. All §4.5.5 extended graph management is deferred. |
| PRD clause and architecture node references | [Registered PRD](../sources/PRD-Full.r1.txt): PRD r1 (2026-10-01), SHA256 2F689644EF9517378F5CF16B28FA372F011811B9F9095AA0CA6996A6A10B13D9, 177840 bytes; §4.5, §4.5.1, §4.5.2, §4.5.3, §4.5.4; §4.5.5 explicitly excluded; sequencing §6.4; global §1.3–§1.6 and §2.1–§2.12 apply. Architecture PENDING_SOURCE; architecture nodes are not invented. |
| Working checkout / branch / base | D:/research/ai_for_research/jiuwenswarm / ai4r_xiaoyang / a8f36245a83358a606bf00f83a64b3353a41c4cd; existing checkout; no tested runtime candidate prepared |
| Affected code/document paths | docs/tasks/M1/M1-005/TASK.md; specs/M1-005-evidence-foundations/spec.md, plan.md, tasks.md. Application/test/configuration paths PENDING_DESIGN after architecture and existing-code inspection. |

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | specs/M1-005-evidence-foundations/ relative to repository root | Exactly one feature for this TASK |
| spec.md | [spec](../../../../specs/M1-005-evidence-foundations/spec.md) | Requirements, ACs and thresholds |
| plan.md | [plan](../../../../specs/M1-005-evidence-foundations/plan.md) | Behavior blocks, future design and verification procedures |
| tasks.md | [tasks](../../../../specs/M1-005-evidence-foundations/tasks.md) | Work, progress and acceptance/evidence correspondence |
| evidence/ | specs/M1-005-evidence-foundations/evidence/ (create on actual verification) | Actual candidate run records/raw artifacts; none generated during preparation |
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
### M1-IF-005 at r0
**Provisional PRD-semantic agreement.** This is not a final architecture, API or schema. Fields and rules explicitly present in the PRD are retained; unspecified technical details remain PENDING_DESIGN.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-005. Consumers: M1-003, M1-004, M1-006, M1-007, M1-014, M1-016, M1-017, M1-018, M1-SYSTEM. |
| Purpose / source requirement | Separate native agent working memory from system evidence; capture local run bundles/append-only records, compare declared versus observed behavior, generate static scorecards and export frozen real runs for offline RSI. Source: §4.5, §4.5.1, §4.5.2, §4.5.3, §4.5.4; §4.5.5 explicitly excluded; sequencing §6.4. |
| Inputs: fields, types, units, required/optional, validation | Native Task/Coding Memory working context; run/stage/capsule identity/versions; prompts, input/output, complete traces and raw verifier evidence; stdout/stderr and artifacts; declared/observed tools/ports/effects; route/time/failure and reliable usage data. Exact field types/requiredness/units not stated by PRD remain PENDING_DESIGN. |
| Outputs: fields, types, units, semantics, guarantees | Native durable working context, isolated local run bundle/workspace snapshot, append-only records.jsonl, durable gate record, Markdown/JSON scorecards and frozen labelled content-hashed run exports. PRD examples records/bundles/<run_id>/ and records/exports/<export_id>/ are retained as examples; exact architecture remains pending. |
| States and invariants | Raw system evidence stays outside reasoning memory and attributable to run/stage/capability. Earlier entries/failed runs retained; gate release requires durable decision. Unknown token/cost values are not fabricated or made mandatory. Exports do not write into the live workflow. |
| Errors, timeout, retry, cancellation | Evidence-write failure cannot establish a durable advancing decision. Exact write errors, partial-write recovery, cancellation and atomicity PENDING_DESIGN; no synthetic evidence substitution. |
| Side effects and idempotency | Writes local records, bundles, scorecards and frozen exports. Repeated-hook/export identity and idempotency semantics PENDING_DESIGN; do not promise automatic trace deduplication excluded by PRD. |
| Compatibility and migration | Initial r0. Architecture may refine technical representation without altering product behavior. Material changes update this owner, parent allocation and affected consumers and invalidate corresponding boundary/system evidence. |
| Machine-readable schema / source path | None created; PENDING_DESIGN. Future generated representations implement this agreement and carry its effective IF revision. |
| Provider/consumer verification responsibilities | M1-005/V01–V06 cover source criteria; M1-005/V90 connects actual peers. Consumers provide actual inputs/state and their matching boundary evidence. M1-SYSTEM owns complete journeys. |
| Open agreement questions | Architecture binds concrete file schemas/layout, durability/snapshot boundaries, run identity and partial-write recovery. Scorecards must handle unavailable usage truthfully. Export labels come from actual registered runs, not invented outcomes. |

Consumed agreements: [M1-IF-003@r0](../M1-003/TASK.md#4-embedded-cross-module-agreements); [M1-IF-004@r0](../M1-004/TASK.md#4-embedded-cross-module-agreements); [M1-IF-006@r0](../M1-006/TASK.md#4-embedded-cross-module-agreements); [M1-IF-007@r0](../M1-007/TASK.md#4-embedded-cross-module-agreements); [M1-IF-018@r0](../M1-018/TASK.md#4-embedded-cross-module-agreements). Definition-time and runtime usage differ as recorded in Section 3; reciprocal semantic dependencies are not full-task completion prerequisites.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| D01 / 2026-10-01 | Initial PRD r1 allocation; Architecture PENDING_SOURCE; user requests document preparation only | All native records; M1-IF-005@r0 | No runtime evidence exists; affected implementation and checks cannot pass before their definitions exist | UNASSIGNED; register architecture and inspect existing code before binding technical paths |
| D02 / 2026-10-01 | Architecture binds concrete file schemas/layout, durability/snapshot boundaries, run identity and partial-write recovery. Scorecards must handle unavailable usage truthfully. Export labels come from actual registered runs, not invented outcomes. | plan.md unresolved decisions; T001; relevant AC/V rows | Only dependent work is constrained; independent source/fixture preparation continues | UNASSIGNED; resolve from architecture or registered capsule/product policy, not guessed requirements |

Progress is in tasks.md. No separate approval, review, handoff or implementation-checklist card is introduced.
