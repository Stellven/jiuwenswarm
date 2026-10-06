# TASK: M1-001 - Intent Compiler and Verifier Trial

This TASK is the identity and entry point for the first connected slice. Acceptance criteria, technical design, work, and evidence belong in the registered Spec Kit artifacts.

Start from the [frozen master PRD](../../../product/prd-m1-full-2026-10-02.txt), the exact clauses in §1, the [architecture reading set](../../../architecture/README.md), and its [glossary](../../../architecture/README.md#glossary). Apply [decisions D1–D9](../../../architecture/principles.md#decisions-and-source-amendments) where they amend the PRD. Read [Code SOP](../../../code/Code_SOP.md), the [Spec Kit workflow](../../../code/code_sop/SPEC_KIT_WORKFLOW.md), the constitution, and project template overrides before generating native artifacts.

From the repository root, select this feature:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'specs/M1-001-intent-trial'
```

Invoke `$speckit-specify` through the installed agent integration with this context:

```text
Implement TASK docs/tasks/M1/M1-001/TASK.md under docs/tasks/M1/TASKS.md.
Use feature directory specs/M1-001-intent-trial/ and Code SOP v2.
Read the original allocated PRD clauses, architecture decisions, required CC
field reference, and the owning interface agreement before specification.
Keep the slice at Intent compiler -> Intent verifier with shared foundations.
Derive detailed acceptance criteria, implementation design, work, and tests
in the native spec.md, plan.md, and tasks.md using project overrides.
```

Then follow the native clarify/plan/tasks/analyze/implement sequence in the workflow. These invocation names are agent skills, not shell commands. The directory is registered here; its native artifacts are intentionally not generated yet.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | M1-001 / r1 / 2026-10-06 |
| Parent TASKS | [M1 TASKS](../TASKS.md) |
| Executor / collaborators | UNASSIGNED; executor selection is not a blocker to specification |
| Requested outcome and instruction/source | Implement the explicitly selected first slice: accept an objective, run an Intent compiler CC, run an independent Intent verifier CC, apply deterministic integrity checks and a protected gate, then expose either an accepted intent artifact or a durable halt reason. Source: [Immediate plan](../../../architecture/immediate-plan.md); user direction dated 2026-10-06; frozen master PRD clauses below. |
| Included scope / exclusions | Include the intent compiler/verifier pair, shared runner and CC declaration support needed by the pair, deterministic output checks, independent verifier invocation, gate-controlled release, run/attempt/evidence records, configured local model bridge, and visible status/result/failure. The slice ends at the accepted intent artifact. Exclude requirement compilation, the research planner, search, POC execution, benchmarking, scientific evaluation, delivery, dynamic routing, RSI implementation, automatic repair, and full M1 completion claims. |
| PRD clause and architecture node references | Master PRD: §§1.4–1.6, 2.3, 2.6, 2.8–2.10, 3.0, 3.0.1–3.0.2, 3.1.1, 3.1.3, 3.1.5, 3.2.1–3.2.2, 3.2.4, 4.1.1–4.1.4, 4.2.1–4.2.2, 4.2.6–4.2.9, 4.3.3–4.3.4, 4.5.2–4.5.3, 4.6.1–4.6.4, 4.7.2–4.7.3, 5.1.1–5.1.2, 5.2.2, 5.3.2, 5.4.2, 5.6.1–5.6.3, 5.6.5, and 6.3–6.4; plus global constraints in §§1–2, 6. Architecture: [overview](../../../architecture/README.md), [immediate plan](../../../architecture/immediate-plan.md), [workflow](../../../architecture/workflow.md), [capsules](../../../architecture/capsules.md), [placement](../../../architecture/placement.md), [declaration](../../../architecture/capsule/declaration.md), [authoring](../../../architecture/capsule/authoring.md), and [decisions D1–D9](../../../architecture/principles.md#decisions-and-source-amendments), revision r2026-10-06; aggregate SHA256 `45d7a27b2323148f96b26c192791aa11dabed0cdd992432d3d8ceeb2ce309e88` from [source baseline](../source-baseline-2026-10-06.json). |
| Working checkout / branch / base | Current JiuwenSwarm checkout; documentation preparation branch `ai4r_muk`, base `37d1097d7026745b3057319adf0b963f1a8e1101`; this is not an implementation candidate |
| Affected code/document paths | Code paths PENDING_DESIGN by the task plan. Native feature directory is `specs/M1-001-intent-trial/`; no generated files exist yet. |

Only the intent-applicable portions of the listed clauses belong to this slice. In §4.1.3, select the two admitted pinned CCs and check eligibility; full planner discovery remains outside the slice. In §4.2.9, cover intent validity, swapped/stale outputs, timeouts, environment failures, uncertainty, and gate locking; scientific-negative and POC cases remain full-M1 work. Configuration covers applicable local paths and precedence, invocation time/call limits, and frozen effective state; full evaluation-profile machinery remains outside the slice.

No separate authorization card or review assignment is required. The requested scope applies; material scope changes are recorded below.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `specs/M1-001-intent-trial/` (NOT_GENERATED) | One directory for M1-001 |
| spec.md | `specs/M1-001-intent-trial/spec.md` (NOT_GENERATED) | Requirements, ACs, thresholds |
| plan.md | `specs/M1-001-intent-trial/plan.md` (NOT_GENERATED) | Technical/block design and verification procedures |
| tasks.md | `specs/M1-001-intent-trial/tasks.md` (NOT_GENERATED) | Work/progress and evidence correspondence |
| evidence/ | `specs/M1-001-intent-trial/evidence/` (NOT_GENERATED) | Actual verification runs and raw artifacts |
| Supporting artifacts | Registered source links in §1; generated schemas or fixtures are owned by the native task artifacts | Subordinate to registered authorities |

Do not repeat acceptance tables, work lists, or results here.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PRD §§3.0.1–3.0.2 and 4.3.1–4.3.4; bridge implementation task UNALLOCATED | Configured local Codex CLI model bridge for compiler and verifier calls, with local call attribution and protected provider boundary | The feature specification must inspect current bridge support and identify any blocking runtime prerequisite; do not invent provider behavior | Native plan/tasks NOT_GENERATED |
| M1-IF-001@draft (owned here) | Intent input, compiler result, verifier assessment, and gate release/halt boundary | Define exact payload fields and runtime procedures in the native spec/plan before implementation; no released wire contract currently exists | Native spec/plan/tasks NOT_GENERATED |

Separate definition-time dependencies from runtime/implementation dependencies. Continue independent work when one dependency is unresolved.

## 4. Embedded cross-module agreements

### M1-IF-001 at draft
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: M1-001 Intent compiler CC. Consumers: M1-001 Intent verifier CC and protected gate. |
| Purpose / source requirement | Preserve the submitted objective through intent compilation and independently assess fidelity before release. Source: PRD §§3.1.1, 3.2.1–3.2.4, 4.2.1, 4.2.6, 4.2.8; Immediate plan. |
| Inputs: fields, types, units, required/optional, validation | Conceptual inputs are the original request and qualified intake context. Exact fields, types, units, and validation are PENDING_DESIGN for the owning Spec Kit task. |
| Outputs: fields, types, units, semantics, guarantees | Conceptual outputs are an intent artifact, an independent verifier assessment with reasons/evidence references, and a gate decision. Exact representation is PENDING_DESIGN. Only an accepted gate decision releases the artifact. |
| States and invariants | Compiler cannot certify its own output. Verifier is read-only and cannot edit the artifact or its criteria. Deterministic integrity checks precede the verifier. A failed, unclear, invalid, or unavailable boundary halts with a reason; no automatic correction or retry occurs in this slice. |
| Errors, timeout, retry, cancellation | Timeout, invalid output, failed verification, or unresolved ambiguity produces a visible halt reason and no accepted artifact. Exact error identifiers, timeout values, cancellation semantics, and record fields are PENDING_DESIGN. Automatic repair/retry count is zero for this slice. |
| Side effects and idempotency | Persist run identity, attempts, evidence references, gate result, and accepted artifact as applicable. Exact storage operation/idempotency key is PENDING_DESIGN. |
| Compatibility and migration | Draft only. No compatibility promise is released. Schema/version behavior is PENDING_DESIGN and must follow the registered capsule schema plus supported M1 profile. |
| Machine-readable schema / source path | None registered yet. The task must create any required schema as a subordinate implementation of this agreement and record the IF ID/revision. |
| Provider/consumer verification responsibilities | Protected runner checks validate the compiler output mechanically; the independent verifier checks request fidelity; the protected gate records and applies the release decision. Exact procedures belong in plan.md and tasks.md. |
| Open agreement questions | Serialization of the required CC field inventory and intent payload; verifier result format; model bridge invocation shape and supported runtime; durable storage boundary; accepted-intent presentation. Resolve in Spec Kit without changing product intent. |

Consumed agreements: None. This is the only registered interface for M1-001; other M1 interface ownership remains UNALLOCATED.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| DEC-001 / 2026-10-06 | User-selected intent pair is the first connected slice; each work invocation has deterministic checks followed by an independent verifier; failures halt with no automatic repair | M1-IF-001@draft; future native artifacts | None generated. If the gate or verifier contract changes, revise this agreement and affected consumer artifacts before implementation evidence exists. | M1-001 executor; resolve in spec.md/plan.md |
| OPEN-001 / 2026-10-06 | Exact payload fields and procedures are not defined by architecture | M1-IF-001@draft | Dependent implementation blocks only; no runtime evidence exists | M1-001 executor; resolve in native Spec Kit artifacts |
| OPEN-002 / 2026-10-06 | Bridge availability and supported runtime must be verified against current code and environment | §§3.0/4.3 dependency above | Model-backed integration block only | M1-001 executor; resolve during specification and environment verification |

Progress remains in tasks.md. A material source or interface change updates the parent TASKS allocation/index and all affected native references.
