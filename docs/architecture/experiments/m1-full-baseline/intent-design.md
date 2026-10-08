# Intent and Requirements: interpretation, checking and release

**Reading level: human potential.** Question: what does the compiler need to understand, what must its verifier establish, and why does Requirements wait? [Immediate Plan](immediate-plan.md) selects the first build; [field contracts](reference/intent-and-requirements.md) define its interoperable data.

## Intent CC responsibility

The compiler takes the exact qualified original request and permitted context. In a bounded generative pass it extracts the problem/research purpose, desired change, requested result, affected entities, scope, exclusions, constraints, preferences and stated targets. It preserves source attribution and separates absent information from stated values. It produces **Intent IR**, not a Research Brief or proposed scientific solution.

The result is an interpretation usable by a downstream compiler. A topic label alone is insufficient when no purpose or requested result can be discerned. The compiler must represent that uncertainty, not invent a benchmark, report type, algorithm or desired change. Missing optional hardware/method/threshold fields are different from not knowing what work the user wants. Requirements may apply authorized parameter defaults; Hypothesis later registers empirical criteria. No browsing, host profiling, research or autonomous clarification is needed to fabricate missing intent.

## Deterministic boundary

```mermaid
flowchart TB
    Request[Exact qualified request] --> Compile[Intent CC: attributed interpretation]
    Compile --> IR[Candidate Intent IR]
    IR --> D{Protected deterministic checks}
    D -->|schema, spans and identities valid| Context[Protected review context]
    D -->|invalid or unavailable| Gate[Protected host: halt decision]
    Request --> Context
    Profile[Predefined independently owned obligations] --> D
    Profile --> Context
    Context --> V[Intent verifier CC: judge submitted IR]
    V --> A[Typed assessment verdict and reasons]
    A --> Validate[Mechanical assessment and subject validation]
    Validate --> Gate
    Gate -->|usable and all mandatory checks pass| Commit[Commit exact accepted Intent]
    Gate -->|not usable or failed or unclear| Halt[Visible reason and retained candidate]
    Commit --> R[Requirements CC]
```

The fixed slice has a predefined schema and checking profile. Runtime binding still ties them to the exact request, candidate and invocation. Deterministic checks validate required fields/types, schema version, span ranges and permitted source references, identity/pins, observed completion and supported limits/effects. They do not establish that a paraphrase is correct, that a topic is actionable, or that a contradiction is harmless. Their pass authorizes review only.

## Intent verifier responsibility

The verifier receives the candidate IR as its primary subject, original request/context as evidence, protected criteria and relevant execution observations. It asks whether **this artifact** performed Intent's job: faithful coverage, no unsupported additions, preserved scope/constraints, consistent interpretation, explicit material uncertainty and a workable purpose/result for Requirements.

It does not take the prompt and issue a competing answer, complete missing work, rewrite the candidate, choose a research solution or stop the scheduler. It reports criterion findings, evidence, uncertainty, limitations and a verdict. A faithful “I cannot determine the requested work” is valid candidate data but yields a non-advancing assessment. A confident yet contradictory/invented interpretation also blocks. An unproven research hypothesis is not automatically an impossible intent; the question is usable requested work, not advance proof of scientific success.

Malicious instructions in candidate text are data. Separate invocation/conversation and protected criteria reduce self-certification; the same provider can still make correlated mistakes. A verifier has no recursive semantic reviewer. Its output is mechanically checked for schema, subject identity and complete required criterion coverage.

## Gate responsibility and human outcome

Protected host code validates and interprets deterministic results plus the assessment, then writes the authoritative decision. It alone publishes accepted output after persistence succeeds. Missing references, contradictory findings, failed mandatory obligations, material unresolved uncertainty or unavailable evidence cannot advance. A compiler-generated readiness flag is advisory.

On an unusable intent, the control plane shows which purpose/result/constraint needs clarification, the retained IR and verifier/gate reasons. The original run remains halted. A clearer user submission starts a linked new run; Phase 1 does not wait for asynchronous approval or run a multi-turn clarification/repair loop. Headless returns immediately; browser disconnect does not resume or cancel the run. [Failure policy](failure-and-human.md) handles infrastructure failures and later Phase 3 clarification separately.

## Requirements CC and the second boundary

Requirements receives **accepted** Intent, original context, supplied resource references and protected defaults. A second bounded generative pass produces the Research Brief: objective, scope, mandatory outcomes, optional preferences, constraints, targets, deliverables, acceptance expectations, evidence obligations, attributed assumptions/defaults and remaining uncertainty. It cannot silently repair misunderstood intent or select the eventual experiment.

```mermaid
flowchart TB
    I[Accepted Intent and original context] --> R[Requirements CC]
    Policy[Authorized defaults and template obligations] --> R
    R --> Brief[Candidate Research Brief: requirements contract]
    Brief --> D{Deterministic contract checks}
    D -->|valid| V[Requirements verifier CC]
    D -->|invalid or unavailable| G[Protected Requirements gate]
    I --> V
    Policy --> V
    V -->|verdict, findings and reasons| G
    G -->|durably accepted| P[Static binder or Phase 3 planner must fulfil contract]
    G -->|failed or unclear| H[Visible halt; do not plan]
```

The Requirements verifier checks that the submitted Brief preserves accepted meaning and accounts for all mandatory outcomes, constraints, exclusions and deliverables; preferences do not become obligations silently. Defaults must come from permitted policy and remain distinguishable from user statements. Acceptance/evidence obligations must be coherent and usable for planning. Unknown experimental methods need not block a Brief if downstream Hypothesis can legitimately determine them; missing intended result or unresolved contradictory requirements does block.

The binder/planner consumes the accepted contract. Coverage maps required outcomes and deliverables to proposed work; required checks are independently assigned. The Hypothesis Blueprint later fixes experiment-specific measurements and classifications, without altering user requirements. [Guard design](guard-design.md) defines the shared mechanism; [reference](reference/intent-and-requirements.md) connects required fields to deterministic and semantic checks.

## Source and build boundaries

D5 explicitly permits two compiler generations instead of the unchanged PRD's literal single bounded generation. Combined limits are frozen; each compilation remains bounded/non-interactive in the baseline. Verifier calls are separate checking work. The Immediate Plan builds only Intent and its boundary. Complete Stage 2 includes qualified documents/resources, accepted Brief and initialized baseline graph; the Intent verifier is not downstream work Node B.
