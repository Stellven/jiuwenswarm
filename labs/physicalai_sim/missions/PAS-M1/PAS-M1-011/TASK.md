# TASK: PAS-M1-011 - Model interface and memory under test
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-011 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 3 library "model interface and memory" (ARCH "Build order"); PRD SL-6; ARCHC flow 3; exits X3.3 and X3.1 for this library; TB-17; F8 |
| Included scope / exclusions | Included: SIMLAB-IF-004@r1 implementation; call records; waiting, measured-latency and fixed-latency timing; budgets; declared fallbacks; route-unavailable behavior; memory modules evolving across episodes and their checkpoint state; replay of recorded decisions; IF-001 `fresh_replication`; `models` check group. Excluded: training or fine-tuning (SL-6.B); VLAs too large for the laptop (M2) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-011. Nodes N-MOD, E5, PL-ROUTE |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN |

**Reserved ACs (TASKS §2):** AC-001 IF-004 implemented, calls only through the lab's model route, no executor credentials; AC-002 every call recorded, three timing modes, budgets (`LIMIT_REACHED`), declared fallbacks for timeout, refusal and bad answer, route unavailable gives a halt or BLOCKED with real evidence; AC-003 TB-17 (actions apply per timing mode; memory restores identically); AC-004 X3.3 (real model, two timing modes, replay reproduces decisions, fresh replication recorded as new); AC-005 F8 cases and `models` check group; AC-006 memory module as the thing under test; AC-007 no training or fine-tuning; AC-008 X3.1 for this library.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-011/` | One directory for this TASK |
| spec.md / plan.md / tasks.md | Created by `$speckit-specify`, `$speckit-plan`, `$speckit-tasks` | ACs / design and procedures / work and evidence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-011/evidence/` (not committed) | Actual runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-003, SIMLAB-IF-003@r1 (implementation) | Timing and save/restore runtime contract | Shared contracts proven (003/AC-001, AC-002) | All |
| A-12 (003/AC-005) | Admitted models that fit the laptop beside AI4R | Admission recorded | AC-004 |
| Lab model route (runtime) | A reachable model route with a credential the runner never exposes to executors | Doctor reports it reachable | AC-001, AC-002, AC-004 |

## 4. Embedded cross-module agreements

### SIMLAB-IF-004 at r1
Model interface. Source: ARCHC "Shared interfaces", SIMLAB-IF-004; PRD SL-6; ARCHC flow 3 and failure behavior.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: PAS-M1-011. Consumers: PAS-M1-001 (`Result.model_calls`), PAS-M1-010 (world models reached through the route), PAS-M1-012, PAS-M1-013 (checkpoint state), PAS-M1-014 |
| Purpose / source requirement | A model or memory module under test is called, timed, budgeted and recorded so its behavior is measurable and replayable |
| Inputs: fields, types, units, required/optional, validation | **Model binding** in the experiment: `model_id`, `model_version`, `route` (the lab's model route), `declared_inputs` (which observations, in which units and frames, at which decision points), `timing_mode` ∈ `waiting`/`measured_latency`/`fixed_latency` with `fixed_latency_s` when fixed, `budgets` ({`max_calls`, `max_wall_s`, `max_cost`, `max_tokens`} where measurable), `fallback` (declared action for timeout, refusal, bad answer), `call_timeout_s`. **Memory binding:** `memory_id`, `version`, initial state reference |
| Outputs: fields, types, units, semantics, guarantees | **Call record** per call: `call_id`, `trial_id`, `attempt_id`, `decision_point`, `model_id`, `model_version`, `inputs` (exact payload or its hash and reference), `answer`, `requested_at`, `answered_at`, `latency_s`, `applied_at` (simulation time), `cost` (when the route reports it, otherwise `unavailable`), `failure` ∈ none/`timeout`/`refusal`/`bad_answer`/`route_unavailable`, `fallback_applied`. **Checkpoint state:** memory contents, pending-call status (M1 requires none unrecorded), call history |
| States and invariants | Every call is recorded, including failures. Replay feeds recorded answers at recorded simulation times instead of calling the model, and its `run_kind` is `replay`. A fresh replication makes new calls, gets a new `run_id`, and its `run_kind` is `fresh_replication`. No executor holds credentials; calls go runner → model interface → lab model route |
| Errors, timeout, retry, cancellation | Timeout, refusal or bad answer applies the declared fallback and is recorded. Budget exhausted ends the attempt `LIMIT_REACHED`. Route unavailable halts the run or marks the arms BLOCKED with real failure evidence. No hidden retries |
| Side effects and idempotency | Calls may cost money. Replay makes no calls |
| Compatibility and migration | Records carry `schema_version`. Model identity and version are pinned per experiment |
| Machine-readable schema / source path | PENDING_DESIGN (this TASK's contracts/) |
| Provider/consumer verification responsibilities | Provider: AC-001 to AC-004. Consumers verify the records they read |
| Open agreement questions | None. A-12 decides which models are admitted, not this agreement |

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1); [SIMLAB-IF-003@r1](../PAS-M1-003/TASK.md#simlab-if-003-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| None | None | None | None | None |

Progress remains in tasks.md.
