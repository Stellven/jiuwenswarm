# TASK: PAS-M1-003 - Library contracts and integration path
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-003 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 3, first part, of ARCH "Build order": "First the shared contracts they need (runtime, observation and model interfaces, timing, save and restore), proven on interacting components; then [the libraries] in parallel where those contracts are ready, merged through one integration path". Exit X3.2; harness for X3.1; A-12 |
| Included scope / exclusions | Included: SIMLAB-IF-003@r1 implementation (runtime contract, observation, timing, save/restore, composition, typed errors); A-12 laptop admission probe for models under test and world models; conformance harness and registry admission; F1 phase 3 case packaging; the one integration path and the `libraries` check group; X3.2 interacting pair and three-library scene; library state in checkpoints; phase 3 snapshot and report. Excluded: each library's own known-answer work (004 to 011) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-003. Nodes N-LIB, N-REG, E4 |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 IF-003 implemented with library unit checks and declared execution modes; AC-002 X3.2 interacting pair passes the runtime contract; AC-003 X3.2 one scene with at least three interacting libraries, each affecting the others' results; AC-004 one integration path, `libraries` check group, parallel work only where contracts are ready, earlier checks keep running; AC-005 A-12 admission per checkpoint, task and runtime; AC-006 X3.1 conformance harness, registry admission by conformance, F1 phase 3 cases; AC-007 phase 3 snapshot and completion report; AC-008 controller, planner and library state saved and restored through IF-003 (SL-7.D part).

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-003/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-003/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-001, SIMLAB-IF-001@r1 (implementation) | Experiment core, registry, checkpoints, check groups | Phase 1 exits verified | All |
| SIMLAB-IF-004@r1 (definition) | Model-call state and timing for interacting components | Embedded in PAS-M1-011 TASK | AC-001, AC-002 |

## 4. Embedded cross-module agreements

### SIMLAB-IF-003 at r1
Library interface. Source: ARCHC "Shared interfaces", SIMLAB-IF-003; ARCH Responsibilities (Libraries); PRD SL-5.D.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: PAS-M1-003 (interface, harness, integration path). Consumers that implement it: PAS-M1-004 to PAS-M1-011. Consumer that saves and restores through it: PAS-M1-013 |
| Purpose / source requirement | A library is built once against one interface, admitted by its known-answer checks, and composes with other libraries in one scene |
| Inputs: fields, types, units, required/optional, validation | **Library declaration** (`simlab-library`): `library_id`, `version`, `kind` ∈ `executor`/`actuator`/`force`/`flexible`/`solver`/`policy`/`world_model`/`model_interface`/`memory`; `execution_mode` ∈ `in_process`/`process`/`service`; `registry_entries` (capabilities it adds); `sensitivity_settings` (settings that reruns may vary, with ranges and units); `known_answer_cases` (references to F1 cases); `inputs` and `outputs` (each {`name`, `unit`, `frame`, `rate_hz`}); `timing` ({`update_rate_hz`, `clock` = simulation clock, `action_application`}); `saved_state` (what it saves and restores); `composition` (which forces, actuators, controllers and measurements it composes with; unsupported combinations) |
| Outputs: fields, types, units, semantics, guarantees | **Runtime contract:** lifecycle `initialize`, `reset`, `step` or `callback`, `terminate`; outputs with declared units and frames each step; `save_state` returns bytes that `restore_state` turns back into an identical continuation on the same machine and build; typed errors |
| States and invariants | A library is usable for research only after its known-answer cases pass (registry status `admitted`). Actions apply exactly when `timing.action_application` says. No library holds credentials. Agent-authored components run confined |
| Errors, timeout, retry, cancellation | Typed errors {`code`, `message`, `library_id`}; an unsupported combination is a validation finding before the run; a runtime numerical failure makes the attempt `INVALID` with `numerical_failure` (IF-001) |
| Side effects and idempotency | `reset` and `restore_state` are deterministic for a given seed and state on the same machine and build |
| Compatibility and migration | `simlab-library` carries `schema_version`; library versions are pinned in experiments; changing a library version invalidates its admission evidence |
| Machine-readable schema / source path | PENDING_DESIGN (this TASK's contracts/) |
| Provider/consumer verification responsibilities | Provider: AC-001 to AC-003. Each library TASK: its X3.1 AC |
| Open agreement questions | None |

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-004@r1](../PAS-M1-011/TASK.md#simlab-if-004-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-07 / 2026-10-30 | A-12 (TASKS §6 Q-07) | AC-005; 010/AC-002; 011/AC-004 | None yet | This TASK's first block |

Progress remains in tasks.md.
