# Governed model routing

**Human component overview.** The protected binder selects one admitted, pinned Capsule. Model routing selects an approved model for that same Capsule and bound task. The governed runner retains execution, permissions, checking and durable release. Routing cannot select another Capsule, widen authority or accept an output.

## Ownership and reading

The architecture owner owns the shared boundary and whole-system consistency. The model-routing owner owns registry qualification, filtering, selection, fallback, provider adapters and routing evidence. Independently owned guard profiles retain checking authority.

- [Shared Capsule–routing contract](reference/capsule-model-routing.md): authoritative exported fields, identities, budgets and dispatch behavior.
- [Router component design](model-routing/router-design.md): filtering, Judge, state transitions, provider integration and audit.
- [Model catalog](model-routing/model-catalog.md): active executor requirements and staged scientific-tool inventory.
- [Received source](sources/model-routing/README.md): exact owner draft, provenance and unavailable evidence.

## Approach and readiness

Phase 1 keeps the fixed Codex CLI route selected at run entry. A static adapter projects the same protected input and decision/evidence contract per CC invocation; it uses no routing Judge or heterogeneous API catalog. Native configured identity remains distinct from independently observed served-model identity. Missing per-call usage remains unavailable.

The API-only owner module is Phase 3, in a separately approved and reversible development/evaluation configuration. Endpoint credentials and actual capability qualification gate real activation. Disabled Phase 3 routing leaves the baseline available; an API failure does not automatically replay work through Codex.

## Registry and two-stage selection

Given Capsule and protected profile → compatibility filtering → sole candidate or at most one authorized Judge → optional single predefined fallback → preflight → persisted frozen decision. The runner rechecks current eligibility and prerequisites before dispatch and uses the same Capsule and model for every call in the invocation. Invalidated frozen decisions halt; new work requires an explicit upstream attempt.

Verifier CCs have separate assignments, contexts, profiles and reserved budgets. Their routed output follows the existing [verifier assessment](reference/checking.md), not a router-defined approval verdict. Code-only/tool-only CCs needing no executor model use the governed runner without a model route. [Placement](placement.md) supplies confinement; [inspection](artifact-inspection.md) supplies authorized evidence views.
