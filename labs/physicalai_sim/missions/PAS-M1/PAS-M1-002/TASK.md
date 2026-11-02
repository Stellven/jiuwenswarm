# TASK: PAS-M1-002 - Builder, first demonstration and thin AI4R connection
TASK.md, spec.md, plan.md and tasks.md share this directory. The parent program directory holds TASKS.md.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | PAS-M1-002 / r1 / 2026-10-30 |
| Parent TASKS | [../TASKS.md](../TASKS.md) |
| Executor / collaborators | Claude Code (coding agent) for Suraj (owner) |
| Requested outcome and instruction/source | Phase 2 of ARCH "Build order": "The builder using phase 1's authoring path (extended where needed), feasibility records, the first demonstration (Fit2Form unless decided otherwise), a changed follow-up, and a thin AI4R connection that keeps working afterwards". Exits X2.1 to X2.6 |
| Included scope / exclusions | Included: builder capsule `simlab.experiment_build` and run capsule `simlab.benchmark` in `jiuwenswarm/research/capsule_extensions/simlab_*/`; protocol with origins; typed halts; feasibility inspection; IF-001 phase 2 operations (`preview`, `pilot`, `release_inspection`); first demonstration; follow-up; planted defects (F3); feasibility honesty (F10); development F4 cases; F5 phase 2 replay; `builder` check group; phase 2 report. Excluded: Planner-selected full journey (012), libraries (003 to 011) |
| PRD clause and architecture node references | TASKS §3 rows owned by PAS-M1-002 (reserved ACs below). Nodes N-BLD, N-RCAP, N-SRC, E1, E2, E8, E9; PL-AI4R |
| Working checkout / branch / base | NOT_STARTED |
| Affected code/document paths | PENDING_DESIGN (plan.md). Expected: `jiuwenswarm/research/capsule_extensions/simlab_*/`, `labs/physicalai_sim/benchmarks/` |

**Reserved ACs (TASKS §2):** AC-001 X2.1 first demonstration (F2; [confirm] 5 pp on 20 objects, pilot 3, one paired observation per object); AC-002 X2.2; AC-003 X2.3 (F3); AC-004 X2.4 (F10, SL-8.B); AC-005 X2.5 (F7 phase 2, SL-2.B); AC-006 X2.6 (SYSTEM); AC-007 intake, protocol with origins, typed halts, no refusal, no invention (SL-1); AC-008 construction only through the tools, capability gaps (SL-2); AC-009 phase 2 operations, pilot never counts; AC-010 engine choice with reason and feasibility inspection (SL-5.S); AC-011 F4 development cases and F5 phase 2; AC-012 adopted assets, scenes and builder-evaluation design (licenses per item); AC-013 phase 2 snapshot, completion report and `builder` check group; AC-014 run capsule returns data without interpretation or improving reruns.

No separate authorization card or review assignment is required.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-002/` | One directory for this TASK |
| spec.md | spec.md (created by `$speckit-specify`) | Requirements, ACs, thresholds |
| plan.md | plan.md (created by `$speckit-plan`) | Technical/block design and verification procedures |
| tasks.md | tasks.md (created by `$speckit-tasks`) | Work/progress and evidence correspondence |
| evidence/ | `labs/physicalai_sim/missions/PAS-M1/PAS-M1-002/evidence/` (not committed) | Actual verification runs |
| Supporting artifacts | None yet | Subordinate |

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PAS-M1-001, SIMLAB-IF-001@r1 (implementation) | Phase 1 operations, authoring tools, records, checks, MCP server | Phase 1 exits verified | All builder and run blocks |
| O-12 and owner preflight (definition and runtime) | First demonstration choice; Fit2Form code and data at a pinned commit with licenses | Owner decision and fetched assets | AC-001, AC-002, AC-005 |
| AI4R capsule format and gate (runtime, unmodified) | `reference/declaration.md` schema 1.0.0; verifier and gate path | Pinned AI4R baseline (TASKS §1) | AC-006, AC-014 |

## 4. Embedded cross-module agreements

### SIMLAB-IF-002 at r1
Capsule ports. Source: ARCHC "Shared interfaces", SIMLAB-IF-002; ARCH Responsibilities (Builder, Run capsule); PRD SL-9.D.

| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: PAS-M1-002. Consumers: PAS-M1-012 (Planner-selected journey), PAS-M1-014, PAS-M1-SYSTEM |
| Purpose / source requirement | Let AI4R's research journey reach SIMLAB through two capsules that follow AI4R's capsule format, Planner, verifier and gates (ARCH "AI4R connection", r0.4.3). SIMLAB owns this agreement and IF-001; the capsules are the adapter (anti-corruption layer) between SIMLAB and AI4R, and AI4R's current formats never limit SIMLAB's capabilities |
| Inputs: fields, types, units, required/optional, validation | **Builder capsule `simlab.experiment_build`** (AI4R kind `agent`, text with tool calls): AI4R outputs the Planner binds to it (artifacts carrying the objective, protocol inputs and design choices; exact port artifact types fixed in the capsule declaration per AI4R `reference/declaration.md`); `sources` (references with hashes); `registry_snapshot` (SIMLAB `capability` output); `earlier_runs` (optional run or checkpoint references for a follow-up, with the requester's next question). **Run capsule `simlab.benchmark`** (AI4R kind `tool`): `experiment_ref` (a validated, bound IF-001 Experiment) and `ai4r_run_ref` |
| Outputs: fields, types, units, semantics, guarantees | Builder: either an IF-001 Experiment that validates with zero findings and is bound to an immutable manifest, with every protocol item carrying an origin, or a typed halt {`halt_kind` ∈ `ambiguity`/`source_conflict`/`missing_capability`, `findings`, `references`}. Run: an AI4R `benchmark_payload` (`benchmark-payload:field-contract:2`, `docs/architecture/design-package/reference/capsules/research-benchmark.md` §4.1) translated by the capsule from the SIMLAB Result, whose references resolve to the full SIMLAB Result and traces. Whatever the payload cannot carry is attached by reference to the full Result or reported in the capsule output, never dropped silently. Neither capsule interprets results |
| States and invariants | The builder never runs the counting trials and never edits a submitted experiment. The run capsule submits, waits and returns. It never reruns to improve a result. A halt is a valid output, not a failure to hide |
| Errors, timeout, retry, cancellation | SIMLAB unreachable or failing: the capsule fails with real failure evidence (no proxy, no mock). No automatic retry. AI4R budget limits apply as declared in each capsule's declaration |
| Side effects and idempotency | Builder: writes only SIMLAB draft workspaces and manifests through the tools. Run: creates one SIMLAB run per invocation |
| Compatibility and migration | Follows the pinned AI4R declaration schema 1.0.0. A newer AI4R baseline is a recorded update (TASKS §6) and reruns this TASK's boundary checks |
| Machine-readable schema / source path | The capsule declarations in `jiuwenswarm/research/capsule_extensions/simlab_*/` (PENDING_DESIGN) |
| Provider/consumer verification responsibilities | Provider: AC-006 and AC-014 V IDs (plan.md). Consumer PAS-M1-012: payload compatibility (012/AC-005) |
| Open agreement questions | TASKS §6 Q-05 (direction set 2026-10-31): `benchmark_payload@2` allows only `baseline` and `treatment` roles with `repeat_count` runs and requires blueprint, POC, lock and provisioning references, while SIMLAB experiments can have any number of arms, factors and conditions. The run capsule translates into the payload and carries the rest by reference to the full SIMLAB Result or reports it; the exact translation is decided in this TASK's plan. Only if the capsule cannot bridge a gap may a small AI4R patch on `PhysicalAI-Sim` be made, recorded as a deviation with reason and removal condition and offered upstream (TASKS §6 C-05 limits it until the owner reconciles the coding prompt) |

Consumed agreements: [SIMLAB-IF-001@r1](../PAS-M1-001/TASK.md#simlab-if-001-at-r1).

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| Q-03 / 2026-10-30 | O-12 and Fit2Form preflight (TASKS §6 Q-03) | AC-001, AC-002, AC-005 | None yet | Owner, before phase 2 |
| Q-05 / 2026-10-30, updated 2026-10-31 | Benchmark payload mapping (TASKS §6 Q-05). r0.4.3 and the owner: SIMLAB owns its interfaces; the capsules are the adapter; untranslatable content is attached by reference or reported; a recorded AI4R patch only as a last resort (TASKS §6 C-05) | IF-002 run capsule; AC-006, AC-014 | None yet | This TASK's plan fixes the translation |

Progress remains in tasks.md.
