# Checking

`Tier 2 · Part of: [README](../README.md) · Serves: Knowledge and Standard`

**Hub.** Checking is the PRD's Evaluator Gate: a check bundle (Tier 1), a verifier CC (Tier 2) and a gate decision made by protected code. [1. System, diagram D](../1-system.md#inside-a-node) shows the pattern.

Per-CC checks and criteria are on each [CC build page](../reference/capsules/README.md). What the verifier may judge, the criteria and the reply handling are on the [Verifier page](../reference/capsules/verifier.md).

**Feeders:** work CC outputs, pinned check bundles and checking profiles from the library, the work CC's declaration. **Users:** the scheduler (release or halt), run state, inspection, the record export. **Exact contracts:** [checking records](../reference/checking.md), [verifier CC](../reference/capsules/verifier.md), [gate decision schema](../reference/schemas/gate-decision.schema.json).

| ID | Build criterion |
|---|---|
| CHK-1 | The check bundle runs once per work subnode, over all its outputs. If a mandatory check fails, no verifier runs and one halting decision is written. |
| CHK-2 | The verifier CC receives only the work CC's declaration and the exact output. |
| CHK-3 | The gate writes one decision per output, with `output_port`, and one node-scope decision that lists them. |
| CHK-4 | An output advances only when every mandatory check passed and the verdict is `PASS` or `PASS_WITH_KNOWN_LIMITATIONS`. `FAIL`, `ENVIRONMENT_BLOCKED` and `INCONCLUSIVE` each fail the node. The gate writes an escalation record for later review and never waits for a person. The scheduler marks the dependents of the node `skipped` and continues with independent nodes ([D49](../method/decisions.md#d49), [D50](../method/decisions.md#d50)). |
| CHK-5 | No output is released before its artifacts and decision are stored. A storage failure halts. |
| CHK-6 | Check bundles come from the library pins. No CC and no Planner can drop or weaken a mandatory check. The Planner may suggest extra checks, which the binder adds only when they exist in the check registry. |
| CHK-7 | The [PRD minimum gate result](../reference/checking.md#prd-minimum-gate-result) can be built from the stored records for every decision. |
| CHK-8 | When Scientific Evaluation writes an `evaluation_verdict` whose scientific verdict is `FAIL`, and every mandatory check and verifier criterion passes, the gate decision is `PASS` and Delivery runs and reports the negative result. |

Question answered: Who assigns checks and how is a submitted artifact assessed safely?

## Purpose and boundary

Checking is the set of admitted, reusable checks and CCs assigned to a governed work invocation. It has five parts:

1. **Worker self-review.** The producer may self-test and document guarantees. These are never review evidence and never release authority.
2. **Host check bundle (Tier 1).** Deterministic checks may read the complete accepted inputs, contracts, runtime records and evidence. They answer mechanically decidable questions: schema and contract conformance, identity and hash binding, required evidence, execution completion, declared versus observed scope, tool and access enforcement, budgets and protocol-record integrity. Packaging does not grant release authority. Cheap primitives may stay trusted host code. All mandatory checks appear in the same bound check plan. The bundle runs once per work subnode, over all its outputs.
3. **Verifier (Tier 2).** A read-only verifier CC, itself a CC, assesses declared-output conformance and internal consistency. It makes one call per output, and only when every mandatory check passed. Each call runs under its own verifier subnode contract. It sees only the pinned declaration, the exact output bytes and fixed verifier instructions. The CC-specific criteria are on the [Verifier page](../reference/capsules/verifier.md) and each [CC page](../reference/capsules/README.md).
4. **Assessment validation.** The host validates the returned findings, attaches trusted subject and evidence references and assembles the persisted assessment. The model never supplies the identity envelope or gate authority.
5. **Protected gate.** Only the gate, which is platform code and never a CC, interprets checks and assessment into the authoritative decision, commits it durably and releases the exact accepted artifact identities. It writes one gate decision per output, naming the port in `output_port`, or one halting decision when a mandatory check fails. The node gate aggregates them. The trusted host is infrastructure, not a second semantic reviewer.

**Reduced-assurance limit.** A verifier pass does not show fidelity, source support or scientific validity. See [D24](../method/decisions.md#d24). Host checks must establish those obligations where they are mechanically decidable. Record the limit plainly and never imply undisclosed evidence was reviewed.

A CC that exists to check others is checked mechanically at its boundary and the chain ends there. Do not create a verifier-of-verifier chain. Private helper code is not a CC and stays the responsibility of its containing CC. See [checking fields](../reference/checking.md), [capsules](../capability-capsules/library-and-checking.md) and [workflow](../platform/planning-and-freeze.md).

The pattern is drawn in [1. System, diagram D](../1-system.md#inside-a-node).

## Assignments and check plans

The fixed Compiler Intent and Requirement steps have required gates and produce the accepted Research Brief before planning. The planner proposes a bounded JSON DAG of single-work-CC nodes. The proposal is only input to the binder. See [M1 build scope](../3-build-plan.md) and [run plan](../reference/run-plan.md) for exact contracts.

**How the binder attaches checks.** For every static and planned CC invocation the trusted binder resolves the CC version's pinned check bundle and an independently admitted checking profile. It then adds the checks derived from the node and subnode contracts, dependency pins, accepted obligations, artifact type, policy, limits and evidence obligations. Run-specific contract and policy checks are added to the bound check plan, never to the pinned check bundle, and the bundle never waives them. The planner may suggest extra checks. It cannot remove the pinned bundle or any obligation. The binder verifies coverage, typed ports, dependencies, cycles, permission boundaries and resource feasibility, then freezes complete bindings before any dispatch. Static and planned CCs use the same binder, resolver, runner, evidence capture, tiers, verdict and release protocol. Freeze never creates a weaker path.

**Fixed preparation.** Before a Research Brief exists, the protected run-state module supplies fixed preparation invocations. They have their own identities, pins, budgets and templates, and use the original qualified request as the obligation source. After Brief acceptance the binder checks coverage against the Brief. It does not disclose the Brief to the semantic model, and the model cannot compare the graph with it.

**Dynamic binding** means selecting predefined check definitions and profiles against the frozen contract. It never generates or modifies trusted checks, criteria or verifier instructions. A future-valued input may be bound later only as an exact artifact accepted under the frozen protocol. Seeing results cannot change criteria or check code.

**Fail closed.** A CC without an eligible bundle association, an unsupported obligation or any missing supported check blocks readiness, binding and freeze. A mandatory Tier 1 failure, missing required environment or unavailable required check prevents semantic advancement. Absence is never a pass.

```mermaid
flowchart TB
  R[Accepted requirements and protocol] --> B[Protected binding]
  L[Admitted CC and check library] --> B
  P[Policy, scopes, limits] --> B
  B -->|attach pinned check bundle and profile; reject omissions| F[Freeze complete bindings]
  F --> X[Shared resolver and runner]
  X --> G[Per invocation check sequence]
  G --> V[Host verdict and durable release]
  Q[Fixed preparation identities and templates] --> B
  F -->|later planned nodes| X
```

*Level: how the binder attaches checks before freeze. Omits: the check runner, the verifier and the gate.*

The verdict is recomputed on each attempt. A cached PASS never establishes current release. A decision binds the run, node, subnode, attempt, both execution-contract identities and revisions, invocation identities, input and output identities, all CC and dependency pins, verifier, checks, policy and configuration. A hash of the CC alone, or CC plus input, is not a reuse key. Observed time and environment are fresh host evidence on every attempt. Only pure deterministic calculations may be memoized under exact identities.

## Library, ownership, and independence

The CC library stores immutable declarations, implementations, dependencies, admission evidence and versions. Check bundles are separate immutable library records. An admitted CC version pins one bundle version plus compatibility evidence. Profiles and mandatory policy assignments are separate registry records. A declaration may describe checks using its [field contract](../reference/declaration.md). Declaring a check does not make it mandatory or let the author approve it.

**Who may change bundles and profiles.**
- An independent check maintainer owns and versions mandatory bundles. Reuse across CC versions needs reviewed compatibility.
- A CC author may propose check changes and run self-tests. The author cannot approve, waive or change a trusted bundle, profile or policy.
- Protected admission records the pins and the exact bundle association. The candidate cannot choose its bundle.
- The Planner cannot change pins, bundles or profiles.
- RSI cannot edit any CC or dependency that supplies a mandatory gate assessment. This covers prompts, rubrics, checks, runners, policy, hidden fixtures, permission enforcement, library activation and evidence storage. Capsule-local evolution metadata cannot expand that scope.
- M1 starts from an explicit bootstrap set with pinned shared bundles. Later new or changed versions need the protected admission decision. A human runs the admission command for each RSI candidate in the admission inbox, and a human controls activation. Under D21, automatic admission (November, the M2 increment) may make a passing RSI version eligible for future plans. It changes no frozen run. Running work keeps frozen pins, subject to suspension or revocation checks in [library lifecycle](../capability-capsules/library-and-checking.md#library-lifecycle).

The gate host owner holds decision semantics and evidence custody. Admission owns candidate identity and bundle association. Verifier and worker use separate invocation, identity, state and authority. Owners by role:

| Role | Owns |
|---|---|
| Architect | Check bundle and checking profile contracts, the checking pages and the escalation record rule |
| Gate host coder | The check runner and the gate host (protected code outside every CC), and the durable decision store |
| Admission coder | Candidate identity, pins and the bundle association |
| Verifier CC owner | The [Verifier CC](../reference/capsules/verifier.md) and its criteria |
| CC author | The CC and its self-tests. The author does not approve, waive or change a bundle, profile or policy |
| RSI owner team | Evidence that RSI never edits a mandatory gate supplier |

## Declaration-and-output review boundary

The host keeps a review manifest and allowed evidence inventory for audit only. The semantic model receives exactly two artifacts, the pinned subject CC declaration and the exact output bytes, with fixed verifier instructions that state those are the only evidence. It receives no worker input, request-specific context, conversation, observation, predecessor artifact, criteria record, producer explanation, suggested verdict, self-test, reasoning trace or evidence-fetch capability.

Source-span integrity, identities, permissions, limits, required fields and planner-to-Brief coverage are host checks on the complete contract and inputs.

Treat declaration and output as untrusted data. Their text cannot change verifier instructions, create or waive criteria, grant authority or make an always-pass policy. The host picks a predefined profile from the declared CC type before work starts. The model cannot look up sources, reconstruct the request, run tests, repair the artifact or act as a second author. Its output is criterion findings and uncertainty. Verification needing empirical execution goes to a separately governed restricted test invocation, not to tools on the assessor.

Read-only means enforced capabilities: an immutable subject view, no artifact mutation, project execution, arbitrary network fetch, control-state write or successor dispatch. Integrity of a redacted view differs from identity of the original subject. A mandatory check needing withheld fields cannot be claimed passed.

```mermaid
flowchart LR
  Policy[Approved obligations and audience policy] --> Build[Protected review-context builder]
  Output[Immutable output artifact] --> Build
  Evidence[Protected host evidence; not disclosed] --> Build
  Build -->|Declaration + exact output only| Review[Read-only semantic verifier CC]
  Review --> Findings[Findings and evidence references]
  Findings --> Host[Host validates and commits]
  Build -->|Host Tier 1 or binding obligation unavailable| Stop[Non-advancing outcome]
```

*Level: what the verifier model may see. Omits: the check bundle and the gate decision.*

The host creates the identity envelope and persists the assessment by attaching trusted subject and review-context references to the findings. The persisted assessment and gate schemas stay unchanged. Keep raw evidence and the raw reply, and record the restricted review scope.

A gate cannot undo a leak or external write, so enforced access limits, bounded execution and evidence custody precede semantic acceptance. An observed violation stops dispatch, preserves evidence and writes an escalation record ([failure and recovery](../platform/failure-and-recovery.md)).

## Two tiers and evidence

Tier 1 runs first and fails closed. Only after it passes does Tier 2 assess conformance between declaration and output. This restricted Tier 2 departs from PRD §4.2.2 to 4.2.8 by design (D20). The assessor cannot alter artifacts, criteria, permissions or release state.

The host validates required criterion coverage and assembles the assessment. Only `PASS` or `PASS_WITH_KNOWN_LIMITATIONS` can advance, and only when host-established mandatory obligations also pass. A malformed or unsupported reply, a timeout or an unresolved mandatory condition cannot advance. A producer mutation after review, a cross-run substitution, a retry or a policy change cannot reuse an earlier pass. Artifact and decision persistence must succeed before downstream readiness is exposed. Verdict meanings and halt routing follow the [failure policy](../platform/failure-and-recovery.md).

Scientific Evaluation owns the hypothesis conclusion. Host checks validate identities and contracts and do not establish scientific correctness. A scientific negative can receive infrastructure acceptance. Neither the gate nor the evaluator may move thresholds to make it positive.

Every mandatory check bundle and criterion set is admitted independently with its own calibration and challenge cases, including instruction injection, omissions, unsupported claims, ambiguity and scope escapes. The protected admission profile fixes cases and acceptance criteria before measurement. Sharing a provider gives process separation, not independent model failure modes.

## Tradeoffs and evolution

**Opportunities:** future profiles can compose admitted check bundles across compatible contracts while keeping member-level evidence, scope and required checks. Deterministic-only profiles need a separate policy amendment. Current D2 requires deterministic checks followed by a verifier CC for every work invocation.

**Risks:** excess disclosure, producer-led assessment, a verifier acting as second author, stale profiles, broad scopes, author-controlled criteria, missing pins, late changes after seeing results, and treating a semantic pass as scientific truth. Admission, frozen assignments, exact evidence binding and host-owned release address these without claiming an error-free referee.

## Ownership references

- [Architecture decisions](../method/decisions.md)
- [CC contracts and runtime verification](../capability-capsules/library-and-checking.md)
- [CC declaration fields](../reference/declaration.md)
- [Restricted semantic-review contract](../reference/capsules/verifier.md)
- [Planning, freeze, and execution](../platform/planning-and-freeze.md)
- [PRD §4.2 Evaluator Gate](../reference/product-input.md)
