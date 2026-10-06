# TASK: TRIAL-1 - Intent Compiler and Verifier Trial

This TASK is the identity and entry point for the first connected slice. Acceptance criteria, technical design, work, and evidence belong in the registered Spec Kit artifacts.

Start from the [frozen master PRD](../../../../architecture/sources/product/prd-m1-current-2026-10-06.txt), the exact clauses in §1, the [architecture reading set](../../../../architecture/README.md), and its [glossary](../../../../architecture/README.md#glossary). Apply [decisions D1–D15](../../../../architecture/principles.md#decisions-and-source-amendments) where they amend the PRD. Read [Code SOP](../../../Code_SOP.md), the [Spec Kit workflow](../../../SPEC_KIT_WORKFLOW.md), the constitution, and project template overrides before generating native artifacts.

From the repository root, select this feature:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'docs/code/Missions/M1/TRIAL-1'
```

Invoke `$speckit-specify` through the installed agent integration with this context:

```text
Implement TASK docs/code/Missions/M1/TRIAL-1/TASK.md under docs/code/Missions/M1/TASKS.md.
Use feature directory docs/code/Missions/M1/TRIAL-1/ and Code SOP v2.
Read the original allocated PRD clauses, architecture decisions, required CC
field reference, and the owning interface agreement before specification.
Keep the slice at Intent compiler -> Intent verifier with shared foundations.
Derive detailed acceptance criteria, implementation design, work, and tests
in the native spec.md, plan.md, and tasks.md using resolved plugin defaults or intentional project overrides.
```

Then follow the native clarify/plan/tasks/analyze/implement sequence in the workflow. These invocation names are agent skills, not shell commands. The directory is registered here; its native artifacts are intentionally not generated yet.

## 1. Identity
| Field | Value |
| --- | --- |
| TASK ID / revision / date | TRIAL-1 / r4 / 2026-10-06 |
| Parent TASKS | [M1 TASKS](../TASKS.md) |
| Executor / collaborators | UNASSIGNED; executor selection is not a blocker to specification |
| Requested outcome and instruction/source | Implement the explicitly selected first slice: accept an objective, run an Intent compiler CC, run an independent Intent verifier CC, apply deterministic integrity checks and a protected gate, then expose either an accepted intent artifact or a durable halt reason. Source: [Immediate plan](../../../../architecture/immediate-plan.md); user direction dated 2026-10-06; frozen master PRD clauses below. |
| Included scope / exclusions | Include the intent compiler/verifier pair, shared runner and CC declaration support needed by the pair, deterministic output checks, independent verifier invocation, gate-controlled release, run/attempt/evidence records, configured local model bridge, and visible status/result/failure. The slice ends at the accepted intent artifact. Exclude requirement compilation, the research planner, search, POC execution, benchmarking, scientific evaluation, delivery, dynamic routing, RSI implementation, automatic repair, and full M1 completion claims. |
| PRD clause and architecture node references | Current user-supplied PRD received October 6: §§1.4–1.7, 2.3, 2.6, 2.8–2.10, 3.0, 3.0.1–3.0.2, 3.1.1, 3.1.3, 3.1.5, 3.2.1–3.2.2, 3.2.4, 4.1.1–4.1.4, 4.2.1–4.2.2, 4.2.6–4.2.9, 4.3.3–4.3.4, 4.5.2–4.5.3, 4.6.1–4.6.4, 4.7.2–4.7.3, 5.1.1–5.1.2, 5.2.2, 5.3.2, 5.4.1–5.4.2, 5.4.4, 5.6.1–5.6.3, 5.6.5, and 6.3–6.4, 6.14; plus global constraints in §§1–2, 6. Architecture: [overview](../../../../architecture/README.md), [immediate plan](../../../../architecture/immediate-plan.md), [workflow](../../../../architecture/workflow.md), [capsules](../../../../architecture/capsules.md), [placement](../../../../architecture/placement.md), [declaration](../../../../architecture/capsule/declaration.md), [authoring](../../../../architecture/capsule/authoring.md), and [decisions D1–D15](../../../../architecture/principles.md#decisions-and-source-amendments), revision r2026-10-06.4; aggregate SHA256 `9b8658d271eced4758a13aacd5d9f80d32d5dc51e0f987ae1cf6c16a3dfcc2ec` from [source baseline](../../../../architecture/source-baseline.json). |
| Working checkout / branch / base | Documentation preparation against target-main 343a77dbd5e6dcd18de2e57794cc992d36c2f35c; this is not an implementation candidate |
| Affected code/document paths | Code paths PENDING_DESIGN by the task plan. Native feature directory is `docs/code/Missions/M1/TRIAL-1/`; no generated files exist yet. |

Bind stable product-user/workspace/run attribution and a protected intent-node contract, with separate compiler and verifier invocation evidence. Durable profile identity is independent of workspace deletion; cloud persistence and full account UX remain broader M1 concerns.

Only the intent-applicable portions of the listed clauses belong to this slice. In §4.1.3, select the two admitted pinned CCs and check eligibility; full planner discovery remains outside the slice. In §4.2.9, cover intent validity, swapped/stale outputs, timeouts, environment failures, uncertainty, and gate locking; scientific-negative and POC cases remain full-M1 work. Configuration covers applicable local paths and precedence, invocation time/call limits, and frozen effective state; full evaluation-profile machinery remains outside the slice.

The [guard contract](../../../../architecture/guard-design.md) also applies to this first slice: fixed independently approved intent checks, full-context binding, exact output-led review, scoped immutable evidence reads and provider disclosure before the call. Derive challenge cases for persuasive producer explanations paired with incorrect intent, omitted/ambiguous constraints, prompt injection, unnecessary private context, blocked necessary disclosure and a verifier attempting effects. Characterize false acceptance and unresolved evidence rather than claiming independent errors from a separate invocation. The verifier returns findings, not a replacement intent that rescues the producer.

No separate authorization card or review assignment is required. The requested scope applies; material scope changes are recorded below.

## 2. Spec Kit registry
| Artifact | Exact path | Authority |
| --- | --- | --- |
| Feature directory | `docs/code/Missions/M1/TRIAL-1/` (NOT_GENERATED) | One directory for TRIAL-1 |
| spec.md | `docs/code/Missions/M1/TRIAL-1/spec.md` (NOT_GENERATED) | Requirements, ACs, thresholds |
| plan.md | `docs/code/Missions/M1/TRIAL-1/plan.md` (NOT_GENERATED) | Technical/block design and verification procedures |
| tasks.md | `docs/code/Missions/M1/TRIAL-1/tasks.md` (NOT_GENERATED) | Work/progress and evidence correspondence |
| evidence/ | `docs/code/Missions/M1/TRIAL-1/evidence/` (NOT_GENERATED) | Actual verification runs and raw artifacts |
| Supporting artifacts | Registered source links in §1; generated schemas or fixtures are owned by the native task artifacts | Subordinate to registered authorities |

Do not repeat acceptance tables, work lists, or results here.

## 3. Dependencies
| Dependency TASK/block/IF ID and revision | Required behavior or artifact | Condition needed before dependent work | Affected block/work-item references |
| --- | --- | --- | --- |
| PRD §§3.0.1–3.0.2 and 4.3.1–4.3.4; existing main M1-001 (Codex adapter), with M1-002/004 configuration and audited-call agreements | Configured local Codex CLI model bridge for compiler and verifier calls, with local call attribution and protected provider boundary | The feature specification must inspect current bridge support and identify any blocking runtime prerequisite; do not invent provider behavior | Native plan/tasks NOT_GENERATED |
| TRIAL-IF-001@draft (owned here) | Intent input, compiler result, verifier assessment, and gate release/halt boundary | Define exact payload fields and runtime procedures in the native spec/plan before implementation; no released wire contract currently exists | Native spec/plan/tasks NOT_GENERATED |

Separate definition-time dependencies from runtime/implementation dependencies. Continue independent work when one dependency is unresolved.

## 4. Embedded cross-module agreements

### TRIAL-IF-001 at draft
| Property | Definition |
| --- | --- |
| Provider and consumer TASK IDs | Provider: TRIAL-1 Intent compiler CC. Consumers: TRIAL-1 Intent verifier CC and protected gate. |
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

Consumed agreements: Shared foundation agreements: main M1-IF-001/002/003/004/005/006/007 as applicable; consume their owning definitions and current architecture refinements without inventing parallel contracts. TRIAL-IF-001 is trial-specific. Exact supported revisions are bound during native specification.

## 5. Changes and unresolved decisions
| ID / date | Change or question and source | Affected spec/plan/work/IF references | Dependent work and evidence to invalidate | Executor / resolution condition |
| --- | --- | --- | --- | --- |
| DEC-001 / 2026-10-06 | User-selected intent pair is the first connected slice; each work invocation has deterministic checks followed by an independent verifier; failures halt with no automatic repair | TRIAL-IF-001@draft; future native artifacts | None generated. If the gate or verifier contract changes, revise this agreement and affected consumer artifacts before implementation evidence exists. | TRIAL-1 executor; resolve in spec.md/plan.md |
| OPEN-001 / 2026-10-06 | Exact payload fields and procedures are not defined by architecture | TRIAL-IF-001@draft | Dependent implementation blocks only; no runtime evidence exists | TRIAL-1 executor; resolve in native Spec Kit artifacts |
| OPEN-002 / 2026-10-06 | Bridge availability and supported runtime must be verified against current code and environment | §§3.0/4.3 dependency above | Model-backed integration block only | TRIAL-1 executor; resolve during specification and environment verification |

Mode-specific required behavior: web submission/inspection and durable correlated failure attention; explicit headless input/configuration with requested/effective seed where supported, no interactive wait, stable non-zero failure status, run identity and bundle reference where available. Preserve detailed verdict/reason and unavailable telemetry. Full M1 interactive CLI/TUI routes blocking failures through native human_session; this web/headless trial preserves that shared routing extension without claiming terminal-shell completion. Human correction creates a fresh linked run and never changes a failed mandatory check to PASS.

The trial must characterize faithful extraction, omissions, unsupported additions, drift, ambiguity, instruction injection, malformed/stale/swapped output, missing model, timeouts, storage failure and headless behavior against fixed independent expected labels. Native spec/plan/tasks select exact cases, pre-measurement thresholds and evidence procedures. Separate invocation/context does not imply independent errors.

Identity/source reconciliation: former local M1-001/M1-IF-001 trial identities are retired. Main M1-001 remains the adapter. Current working input is the preserved 232,081-byte PRD received October 6, SHA256 897af8427e2cf4e2427a2097b9b9e8a5a427a7de53b89f4e541d2cc437594036; see architecture/review-resolution.md. Stage 0/1/2 contributions and missing exits follow immediate-plan.md; accepted intent is not a Research Brief or governed work Node B.

Progress remains in tasks.md. A material source or interface change updates the parent TASKS allocation/index and all affected native references.
