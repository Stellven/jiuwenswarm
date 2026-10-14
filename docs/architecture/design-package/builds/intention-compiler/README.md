# Intention Compiler: standalone node build

**Architecture Design Main Body.** Start here when the coding prompt assigns the Intent/Intention Compiler. Here **Intention Compiler means the whole node**, not only the Intention CC. The [Context entrypoint](context.md) identifies required supporting design. The package describes the full M1 architecture; this component entrypoint covers only the fixed compiler and its foundations. The current D19 core build consumes this node’s accepted Brief in the protected planner and continues through Search, Screen, Hypothesis, Builder, Benchmark, Scientific Evaluation and Delivery; those downstream stages are outside this component assignment. See [core build](../../core-build.md).

## Completion boundary

**Qualified intake → Intention CC → checked and semantically verified Intent IR → Requirements CC → checked and semantically verified Research Brief → protected node release.**

Successful completion produces accepted `research_brief.json`, both subnode decisions, the enclosing node decision and readable evidence. Intent IR alone, unverified JSON, a mocked model response or a successful HTTP request is not completion. An unusable request legitimately ends in a visible halt; that case does not demonstrate the successful path.

## Node responsibilities

| Component | Required work and output | Authority / boundary |
|---|---|---|
| Local intake adapter | Capture request; qualify `.txt`, `.md`, `.pdf` material; register supplied project/data resources and authorized user/profile/workspace | Protected qualification; no web retrieval, cloning, dataset downloads or host profiling |
| Intention work subnode | Extract meaning, purpose/result, context, scope, constraints, preferences and uncertainty into Intent IR. Self-review fidelity to the request and usefulness to Requirements | No scientific solution selection. Readiness is a candidate claim |
| Intent checks and verifier subnode | Host checks structure, identities and spans first. Then the verifier checks the IR for declared output conformance, internal consistency, limitations consistency and uncertainty consistency | Verifier uses prewritten profile instructions and receives only the declaration and exact output. It cannot replace the IR or control the workflow |
| Intent protected gate | Validate findings and subject; persist decision and accepted IR or halt | Requirements is never dispatched on candidate or blocked Intent |
| Requirements work subnode | Build Research Brief from accepted Intent, qualified context and protected defaults. Self-review that every Intent constraint, target and in-scope item is in the Brief or in `unresolved_items` | Record every applied default. No final experimental protocol |
| Requirements checks and verifier subnode | Host validates shared fields, references, default authorization and requirement-link coverage. Then the verifier checks the Brief for declared output conformance, internal consistency, limitations consistency and requirement link completeness | Assessment is data. No replacement Brief and no producer-selected criteria |
| Requirements and enclosing-node gates | Commit checked Brief; aggregate internal decisions, observations, limits and required outputs; release exact Brief | Protected infrastructure only; aggregate finalization adds no third semantic-review call |

The node owns its external contract and frozen internal structure. Each subnode binds one CC. Work subnodes have two-tier checking; verifier outputs terminate in mechanical validation. Fixed cooperation is not composite/merged CC creation.

## Foundations included in this build

Build or reuse the governed runner, pinned declarations and local admitted capability set, protected model bridge, node/subnode binding, independently owned checking profiles, immutable artifact capture, durable release state and authenticated local control surface. These are relevant compiler dependencies, not unrelated scope. No general library authoring/admission UI is required; fixed fixture admission is not evidence of runtime eligibility.

Use the configured approved model endpoint with the existing fixed Codex CLI route under the unchanged schema 1.0.0 contract. Separate fixed Intention and Requirements generations plus their verifier calls are bounded by a frozen total profile, consistent with confirmed PRD 4. This component ends at the accepted Brief; the assigned core planner consumes it for the downstream JSON DAG. This does not authorize clarification loops, repair or retries. Missing telemetry is unavailable, never zero.

## Browser and container boundary

Bundle frontend, service and runtime in one application image. Its entrypoint starts the component; no external UI startup script is required. Publish the service on loopback, normally `127.0.0.1:5173:5173`. Protected operator configuration supplies model access. Browser/API are same-origin; clients cannot access gate state or model credentials directly.

The browser submits requests and supplied input locations, observes status, and inspects/downloads named candidate and accepted records. Persist run state and evidence on configured volumes. Browser disconnection does not cancel work. Restart preserves records and pauses interrupted work without replay. Cancellation stops new dispatch and retains observed effects. A headless client follows the same gates and returns non-success on halt without waiting for approval.

## Required proof

| Scenario | Required observable result |
|---|---|
| Actionable request with supported input | Both work stages complete; verified `research_brief.json` and node release persist; browser and export agree |
| Missing optional hardware/method/threshold | Preserve omissions; apply only authorized parameter defaults; invent no objective, target or scientific result |
| Topic-only, unsupported or constraint-losing outputs | Measured in independent benchmark cases. The verifier rejects visible declaration or output violations. Producer self-review and host checks carry fidelity and preservation |
| Malformed work or verifier output | Halt at the appropriate deterministic boundary; no absent criterion or fabricated evidence counted as a pass |
| Stale subject, swapped resource, exceeded limit | Reject exact mismatch/violation before downstream release |
| Timeout, missing model access or no output | Halt with real failure evidence; no invented artifact/reference or unnecessary verifier call |
| Storage failure, restart, cancellation, browser closure | No uncommitted release, silent replay or lost provenance |
| Accepted Brief consumed by a bounded test consumer | Match the published version and required fields; reject candidate/unsupported-version inputs |

Use labelled positive/negative fixtures and real configured-model evidence. Record false acceptances/refusals and provider limitations. Deterministic fixture checks cannot prove semantic model quality. The test consumer establishes interface compatibility only; do not implement planning, Search, Hypothesis, Builder, scientific execution, Delivery, RSI, advanced compilation or development-sidecar tooling.

## M1 connection and prompt use

This component supplies the Brief boundary of Implementation Stage 2; it does not initialize the complete research DAG or satisfy full M1 exits. The assigned core planner consumes the same Brief semantics after this component completes. The retained static SwarmFlow workflow is available only as an explicitly selected run mode; advanced planner integration remains optional/later. An advanced compiler adapter must supply the same published output/evidence obligations, without copying the baseline algorithm.

In the supplied four-document coding prompt, replace only the two architecture path placeholders with this file and [context.md](context.md) in the assigned full or compact package. Required links stay within that package. The other machine's PRD Main/Context and token-reporting instructions retain their roles; telemetry-report paths are not product output paths. This design creates no extra coding approval workflow or task identity.

## Verifier boundary

The semantic verifier receives only the declaration and the exact output ([D20](../../principles.md#d20-declarationoutput-only-semantic-review)). Fidelity and preservation are producer obligations backed by host checks. [D21](../../decision-review.md#d21) governs November generation/admission and December composition.
