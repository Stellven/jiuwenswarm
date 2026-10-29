# Build scope

`Tier 2 · Part of: [Method](README.md)`

This page holds ownership, scope limits and the future work the build must not block. The build order and M1 acceptance boundary are in the [build plan](../3-build-plan.md). The assignment follows [D19](decisions.md#d19) and [D26](decisions.md#d26).

## Responsibility and reuse

| Boundary | Owner role | Reuse |
|---|---|---|
| Compiler contracts | CC owner (contracts), Verifier owner (checking profiles) | Reconcile the built compiler, runner, bridge and store before replacing code |
| Planner, binder, freeze, dispatch | Architect (graph and authority), CC owner (Planner ports) | Adapt agent-core Leader where it fits. Dispatch runs on SwarmFlow ([native reuse](../platform/README.md#native-reuse)) |
| Check bundles, profiles, gates | Verifier owner | Reuse the compiler's deterministic checks and durable gate store. A producer is never its own referee |
| Research CCs | CC owner | Existing tools and bounded code capsules |
| Platform benchmark | Benchmark owner | Side system in the sidecar container ([benchmark runner](../side-systems/benchmark-runner.md)) |
| Model access | Router owner (API router), Architect (bridge and `RouterPort`) | Fixed Codex route is the default and the Codex fallback. The API router sits behind `RouterPort` |

## Future work this build must not block

The Phase 1 research workflow never waits for a side system. The model router, the RSI workbench and the platform benchmark runner are built in M1, in parallel, and never block a run ([side systems](../side-systems/README.md)). No alternate verifier or route, Generalist, MCTS, composition or spatiotemporal capability is a dependency of the hot path.

| Later capability | Seam kept now |
|---|---|
| Model router | Capsules declare model needs, not models. The model bridge asks `RouterPort`. `cc.router.enabled` false gives the fixed Codex route |
| RSI workbench | CC versions are immutable and pinned. Check bundles, profiles and labels sit outside the capsule. RSI only creates candidate versions |
| Generalist and automatic capsule generation (November) | A generated capsule uses the same declaration, check bundle and admission path as a hand-written one |
| Automatic library admission (November) | Admission writes an eligibility record. Plans read it from the library snapshot pinned at plan time |
| Better planning and MCTS (November) | The `plan_proposal` type and the binder stay the same. Only how a proposal is produced changes |
| Composition and fusion (December) | A run plan node references one CC version. Node contracts already allow an enclosing node with subnodes |
| Spatiotemporal lifecycle (2027) | Frozen runs keep their identities. New versions affect only new runs |

## Scope boundaries

- The RSI workbench is a human-run side system outside startup, imports, tests and release gates.
- Full M1 PRD coverage is in [clause coverage](clause-coverage.md). It is not the same as this assignment.
- The Planner is a targeted Phase 3 M1 capability. D19 specifies its bounded proposal and shared protected binder; the PRD owns its required M1 outcome.
- Existing TASK, AC, IF and feature identities are not renamed.
- Missing model access, baseline data, a check bundle or durable storage stops the affected run. Record the missing resource and its owner. Never invent a result.
