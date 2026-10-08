# Guard architecture

**Reading level: human potential.** Question answered: Who assigns checks and how is a submitted artifact assessed safely?

## Purpose and boundary

A guard is a reusable, admitted checking capability assigned to a governed work invocation. Its purpose is to determine whether the invocation's observed result satisfies the obligations fixed for that run. For Intent these include usefulness to Requirements, not merely faithful topic extraction. [Intent detail](intent-design.md) explains that assessment; [checking fields](reference/checking.md) define the response. It does not certify the truth of scientific claims: the scientific evaluator owns that interpretation, while the Evaluator Gate checks that the evaluator followed its contract and produced admissible evidence. A valid scientific negative result can therefore pass infrastructure verification. See [capsules](capsules.md), [workflow](workflow.md), and [D2/D3/D10](principles.md).

## Assignments and check plans

Protected configuration derives the mandatory check plan from the applicable accepted obligations, Node and applicable Subnode Execution Contracts, every participating CC and transitive dependency pin, guard profile and version, policy and scope, protocol references, limits, evidence obligations, and relevant runtime rules. Before a Research Brief exists, fixed preparation templates supply the product obligations and the qualified original request supplies the input meaning; no compiler depends on its own accepted output or a later Brief to establish its guard assignment. After Brief acceptance, planned research contracts use those accepted requirements. Hashes identify these inputs. The plan is invariant for the same complete binding; a CC hash alone, or a CC plus input hash, is not a sufficient reuse key. Observed time and environment are fresh evidence on every attempt and are not frozen as predicted facts.

| Reusable item | What stays fixed | What changes per governed invocation |
|---|---|---|
| Check definition | Admitted code/schema/rubric version and supported contract | Exact subject, accepted inputs and captured observations |
| Guard profile | Independently approved obligation-to-check recipe and version | Effective contract, policy, scientific protocol, resource limits and evidence references |
| Bound check plan | Immutable assignment for the full frozen context | Future accepted inputs are instantiated under the frozen rules before dispatch |
| Verdict | Exact run/attempt/subject/evidence binding | Recomputed on each attempt; a cached earlier PASS never establishes current release |

## Library, ownership, and independence

The CC library stores immutable declarations, implementations, dependencies, admission evidence, and versions. Guard profiles and mandatory policy assignments are separate registry records, logically alongside that existing library. This is not a new network service. A declaration may describe checks and guarantees using its [field contract](capsule/declaration.md); declaring a check does not make it mandatory, authorize its author to approve it, or replace protected profile assignment.

## Output-led review and controlled disclosure

The protected review-context builder is responsible for giving the assessor enough evidence without letting the producer lead the judgment. Bind an evidence manifest to the exact subject and obligations; identify each item as trusted policy, accepted input, observed runtime evidence, or untrusted producer content. Present obligations and actual output as the primary comparison. Producer explanations, suggested verdicts, self-tests and reasoning traces are optional diagnostic material, never proof that obligations passed. Do not pass the producer's conversation, chain of thought or unrelated history by default.

| Review input | Purpose and authority |
|---|---|
| Original accepted request and requirements | Establish intended meaning and boundaries; preserve material uncertainty |
| Exact produced artifact and declared output contract | Establish the subject actually being judged, rather than a producer-written summary |
| Approved rubric, guard profile, protocol and scope | State the independently assigned acceptance questions; producer text cannot override them |
| Minimum relevant accepted predecessor evidence | Allow claim/support checks with attributable source references |
| Runtime completion, effects, limits and integrity observations | Establish compliance claims the output alone cannot prove; missing mandatory observation blocks |

## Two tiers and evidence


Tier 1 answers mechanically decidable questions: schema and contract conformance, identity and hash binding, required evidence presence, execution completion, declared versus observed scope, tool and access enforcement, budgets, and protocol-record integrity. Mandatory Tier 1 failure, missing required environment, or unavailable required check prevents semantic advancement; absence is never a pass.

Only after Tier 1 passes does Tier 2 assess grounded fidelity, coverage of obligations, support from cited evidence, internal consistency, and scientific interpretation where the assigned question requires it. The assessor cannot alter artifacts, criteria, permissions, or release state. A malformed, unsupported, uncertain, or out-of-scope assessment does not advance. The host validates subject and evidence references, records the applicable stable verdict and raw assessment, and releases only exact accepted artifact identities after durable commit. Verdict meanings and halt routing follow the [failure policy](failure-and-human.md).

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
- [Planning, freeze, and execution](workflow.md)
- Optional historical identity reference: [M1-003 admission task](https://github.com/Stellven/jiuwenswarm/blob/45c0566aeaff1f7b8a5063c46397afa2d8084f94/docs/code/Missions/M1/M1-003/TASK.md); reconcile its older source assumptions.
- Optional historical identity reference: [M1-007 guard ownership task](https://github.com/Stellven/jiuwenswarm/blob/45c0566aeaff1f7b8a5063c46397afa2d8084f94/docs/code/Missions/M1/M1-007/TASK.md); reconcile its older source assumptions.
- [PRD §4.2 Evaluator Gate](sources/product/README.md)

## Connected behavior summary

Protected guard/profile owners assign mandatory check IDs, rubrics, evidence scope and permitted disclosure before producer results exist. Binder instantiates them from accepted objectives, actual inputs, exact declarations/dependencies, policy/configuration/protocol and effective limits. Fixed mandatory preparation has predefined assignments; planning cannot remove them.

Capture exact candidate and observations. Deterministic checks validate fields/type/version, exact subject/run/node/attempt/contract binding, artifacts, permissions, required evidence and enforceable limits. Failure/unavailable mandatory evidence stops semantic spend and advancement. If valid, protected review context supplies submitted artifact, original/accepted inputs, criterion assignments and observations to an independent read-only verifier CC.

Verifier judges fidelity/coherence/usability/evidence against assignment; no replacement artifact, policy mutation, extra effects, favorable producer instructions or workflow control. Scope confidential evidence to approved audiences before model disclosure; necessary undisclosable evidence blocks. Mechanically validate assessment identity/criterion coverage/format. Guard outputs have no recursive semantic chain.

Protected gate alone interprets results, records decision and commits accepted references. PASS_WITH_KNOWN_LIMITATIONS cannot waive mandatory checks. Persistence failure never releases. Scientific conclusion, assessment, admission and runtime decision are different records. [Checking contracts](reference/checking.md) and examples define exact fields and identity relationships.
