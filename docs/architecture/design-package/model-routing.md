# Governed model routing

**Human component overview.** The protected binder selects one admitted, pinned Capsule. Model routing selects an approved model for that same Capsule and bound task. The governed runner retains execution, permissions, checking and durable release. Routing cannot select another Capsule, widen authority or accept an output.

## Ownership and reading

The architecture owner owns the shared boundary and whole-system consistency. The model-routing owner owns registry qualification, filtering, selection, fallback, provider adapters and routing evidence. Independently owned guard profiles retain checking authority.

- [Shared Capsule–routing contract](reference/capsule-model-routing.md): authoritative exported fields, identities, budgets and dispatch behavior.
- [Router component design](model-routing/router-design.md): filtering, Judge, state transitions, provider integration and audit.
- [Model catalog](model-routing/model-catalog.md): active executor requirements and staged scientific-tool inventory.
- [Received source](sources/model-routing/README.md): exact owner draft, provenance and unavailable evidence.

## Approach and readiness

The core compatibility route is the existing fixed Codex CLI route, selected at run entry under the unchanged schema 1.0.0 contract. The optional API router is isolated and cannot substitute an alternate verifier study or alter verifier policy. A static adapter projects the same protected input and decision/evidence contract per CC invocation; it uses no routing Judge or heterogeneous API catalog. Native configured identity remains distinct from independently observed served-model identity. Missing per-call usage remains unavailable.

The API router is an optional isolated target. Endpoint credentials and actual capability qualification gate real activation. Routing failure halts; it does not silently replay a failed attempt through Codex. The static runner remains available only when explicitly selected as the run mode before execution.

## Registry and two-stage selection

Given Capsule and protected profile → compatibility filtering → sole candidate or at most one authorized Judge → preflight → persisted frozen decision. No automatic model fallback occurs after a failed call; any alternate route requires an explicit new run mode/attempt and frozen decision. The runner rechecks current eligibility and prerequisites before dispatch and uses the same Capsule and model for every call in the invocation. Invalidated frozen decisions halt; new work requires an explicit upstream attempt.

Verifier CCs have separate assignments, contexts, profiles and reserved budgets. Their routed output follows the existing [verifier assessment](reference/checking.md), not a router-defined approval verdict. Code-only/tool-only CCs needing no executor model use the governed runner without a model route. [Placement](placement.md) supplies confinement; [inspection](artifact-inspection.md) supplies authorized evidence views.

## Current semantic-review scope

[D20](principles.md#d20-declarationoutput-only-semantic-review) limits semantic input to declaration/output; earlier full-context descriptions remain source context. Host checks retain runtime evidence. [D21](decision-review.md#d21) governs November generation/admission and December composition.
