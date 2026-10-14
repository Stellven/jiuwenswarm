# Guard architecture

**Reading level: human potential.** Question answered: Who assigns checks and how is a submitted artifact assessed safely?

## Purpose and boundary

A guard is a reusable, admitted checking capability assigned to a governed work invocation. Host checks and the protected gate retain complete accepted inputs, contracts, observations and evidence. The semantic model receives only the subject CC declaration and exact output bytes, plus fixed verifier instructions; it gets no worker input, request-specific context, conversation or evidence-fetch capability. It assesses declared-output conformance and internal consistency only ([D24](decision-review.md#d24)). Never describe its pass as fidelity, source support or scientific validity. The CC-specific criteria are on the [Verifier page](reference/capsules/verifier.md) and each [CC page](reference/capsules/README.md). The scientific evaluator owns scientific interpretation; the Evaluator Gate checks admissible infrastructure evidence, so a valid scientific negative can pass infrastructure verification. See [Intent detail](intent-design.md), [checking fields](reference/checking.md), [capsules](capsules.md), [workflow](workflow.md), and [D2/D3/D10](principles.md).

## Assignments and check plans

The fixed Compiler Intent and Requirement steps have required protected gates and must produce the accepted Research Brief before planning. For the core research path, a planner proposal is only input to protected binding: the binder assigns mandatory profiles and checks independently, verifies coverage, typed ports, dependencies, cycles, permission boundaries and resource feasibility, then freezes the [`run_plan`](reference/run-plan.md) before any downstream dispatch. Planner failure or rejection blocks the run and starts a linked Intention Compiler attempt. The static template is a separately selected mode ([D26](decision-review.md#d26)). See [core build](core-build.md) for D19 scope reconciliation.

Protected configuration dynamically selects and instantiates an existing, independently admitted profile against complete accepted obligations, contracts, CC/dependency pins and each exact CC-version/check-bundle association, policy, protocol, limits, evidence obligations and runtime rules. The pinned CC bundle is a required base; contract/policy checks are added, never substituted. It does not generate or modify trusted checks, criteria or verifier instructions. Before a Research Brief exists, fixed preparation templates supply obligations and host checks retain the qualified request meaning. After Brief acceptance, the binder checks planned coverage and feasibility against those requirements without disclosing them to the semantic model. A CC hash alone, or CC plus input hash, is not a sufficient reuse key.

| Reusable item | What stays fixed | What changes per governed invocation |
|---|---|---|
| CC check-bundle association | Exact CC version, immutable bundle version and independent compatibility record | Exact invocation subject and current evidence |
| Check definition | Admitted code/schema/rubric version and supported contract | Exact subject, accepted inputs and captured observations |
| Guard profile | Independently approved obligation-to-check recipe and version | Effective contract, policy, scientific protocol, resource limits and evidence references |
| Bound check plan | Immutable assignment for the full frozen context | Future accepted inputs are instantiated under the frozen rules before dispatch |
| Verdict | Exact run/attempt/subject/evidence binding | Recomputed on each attempt; a cached earlier PASS never establishes current release |

## Library, ownership, and independence

The CC library stores immutable declarations, implementations, dependencies, admission evidence, and versions. Guard profiles and mandatory policy assignments are separate registry records, logically alongside that existing library. This is not a new network service. A declaration may describe checks and guarantees using its [field contract](capsule/declaration.md); declaring a check does not make it mandatory, authorize its author to approve it, or replace protected profile assignment.

## Output-led review and controlled disclosure

The CC library stores immutable check bundles as separate records. An independent check maintainer owns them; CC authors may propose checks but cannot approve mandatory bundles. The initial M1 catalog is an explicit bootstrap set whose versions bind to immutable, independently maintained shared checking bundles. This enables the first path but is not capsule-specific evidence or a completed governed admission gate. Human standing controls activation and suspension. Once governed admission is available, new or changed versions cannot use a default bundle: protected eligibility requires independent evidence and an exact compatible bundle. Under D21, M2 automatic admission may make a passing RSI candidate eligible for future plans only after that gate passes. Frozen runs do not change.

The host keeps a complete review manifest for provenance and deterministic checks. It is not the semantic model's prompt: the semantic payload contains exactly the pinned subject CC declaration and exact output bytes, alongside fixed verifier instructions. The model receives no worker inputs, accepted requirements, conversation, observations, predecessor artifacts, evidence or fetch tool. Producer explanations, suggested verdicts, self-tests and reasoning traces are not semantic evidence.

| Review input | Purpose and authority |
|---|---|
| Pinned subject CC declaration | Declared capability, output ports and guarantees; not authority to expand scope |
| Exact output bytes | Sole producer artifact assessed semantically |
| Fixed verifier instructions | Ask only declaration/output-conformance questions; no request-specific context |

Treat declaration and output as untrusted data. Declaration text cannot change fixed verifier instructions, create/waive criteria or policy, grant authority, or request an `always pass` result. The host selects a predefined profile from declared CC type and supported contract before work; declared guarantees are checked only where that profile has an admitted check. The model reply is untrusted findings/limitations; the host assembles the existing persisted Assessment and trusted identity envelope.

## Two tiers and evidence

The required two-tier verifier is independent of the producer and planner. Deterministic checks fail closed; only after they pass may the read-only semantic verifier assess declaration/output conformance. Neither planner nor producer self-certifies, and presentation or fallback cannot remove a gate.


Tier 1 answers mechanically decidable questions: schema and contract conformance, identity and hash binding, required evidence presence, execution completion, declared versus observed scope, tool and access enforcement, budgets, and protocol-record integrity. Mandatory Tier 1 failure, missing required environment, or unavailable required check prevents semantic advancement; absence is never a pass.

Only after Tier 1 passes does Tier 2 assess conformance between the declaration and exact output. This restricted Tier 2 departs from PRD §4.2.2 to 4.2.8 by design (D20). The model returns untrusted criterion findings, uncertainties and limitations; the host validates required criteria and subject binding, attaches trusted identities/evidence references, assembles the unchanged persisted Assessment and gate records, and releases only exact accepted artifact identities after durable commit. No schema change is implied. Verdict meanings and halt routing follow the [failure policy](failure-and-human.md).

Every related mandatory guard is admitted independently and has separate development calibration and challenge cases, including instruction injection, omissions, unsupported claims, ambiguity, and scope escapes. These development cases are not run-specific RSI evaluation material. Preserve observed errors, limitations, and provenance. The protected admission profile binds concrete case sets and acceptance criteria before measuring a candidate; no universal threshold or private assessor prompt is prescribed here.

## Tradeoffs and evolution


**Strengths:** deterministic fast failure avoids unnecessary semantic calls; admitted CCs keep substantive logic inspectable and reusable; complete bindings support reproducibility; trusted host release prevents an assessor response from directly unlocking work.

**Weaknesses:** broad evidence bundles and profile maintenance add cost; semantic judgments remain fallible; shared model or domain assumptions can correlate errors; incomplete requirements cannot be repaired by more checks.

**Opportunities:** future profiles can compose admitted deterministic and semantic guards across compatible contracts while preserving member-level evidence, scope, and required checks. A profile is reusable only when its full binding and obligations match. Deterministic-only profiles may be considered under a separate policy amendment; current D2 requires deterministic checks followed by a verifier CC for every work invocation.

**Risks:** excess review-context disclosure, producer-led assessment, a verifier becoming a second author, stale profiles, overly broad scopes, author-controlled criteria, missing dependency pins, late changes after observing results, and treating a semantic pass as scientific truth can defeat the boundary. Admission, frozen assignments, exact evidence binding, and host-owned release address these risks without claiming an error-free referee.

## Ownership references

- [Architecture decisions](principles.md)
- [CC contracts and runtime verification](capsules.md)
- [CC declaration fields](capsule/declaration.md)
- [Restricted semantic-review contract](reference/semantic-review.md)
- [Planning, freeze, and execution](workflow.md)
- Optional historical identity reference: [M1-003 admission task](https://github.com/Stellven/jiuwenswarm/blob/45c0566aeaff1f7b8a5063c46397afa2d8084f94/docs/code/Missions/M1/M1-003/TASK.md); reconcile its older source assumptions.
- Optional historical identity reference: [M1-007 guard ownership task](https://github.com/Stellven/jiuwenswarm/blob/45c0566aeaff1f7b8a5063c46397afa2d8084f94/docs/code/Missions/M1/M1-007/TASK.md); reconcile its older source assumptions.
- [PRD §4.2 Evaluator Gate](sources/product/README.md)

## Connected behavior summary

Protected guard/profile owners assign mandatory check IDs, rubrics, evidence scope and permitted disclosure before producer results exist. Binder instantiates them from accepted objectives, actual inputs, exact declarations/dependencies, policy/configuration/protocol and effective limits. Fixed mandatory preparation has predefined assignments; planning cannot remove them.

Capture exact candidate and observations. Deterministic checks validate fields/type/version, exact subject/run/node/attempt/contract binding, artifacts, permissions, required evidence and enforceable limits. Failure/unavailable mandatory evidence stops semantic spend and advancement. If valid, the host retains the full review manifest; only the subject declaration and exact output go to the independent read-only semantic verifier.

Verifier judges only declaration/output conformance; it cannot judge fidelity, coherence or usability against undisclosed requirements or evidence. Necessary obligations not mechanically established block. The model has no replacement artifact, policy mutation, extra effects, favorable producer instructions or workflow control. Host assembles the unchanged Assessment and validates identity/criterion coverage/format. Guard outputs have no recursive semantic chain.

Protected gate alone interprets results, records decision and commits accepted references. PASS_WITH_KNOWN_LIMITATIONS cannot waive mandatory checks. Persistence failure never releases. Scientific conclusion, assessment, admission and runtime decision are different records. [Checking contracts](reference/checking.md) and examples define exact fields and identity relationships.
