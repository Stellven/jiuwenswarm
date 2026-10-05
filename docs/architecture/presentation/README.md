# Presentable M1 architecture

Start with the [seven-page showcase](showcase/README.md). Its linked Markdown is the current presentation source; the PDFs are derived snapshots, not separate authorities.

## Current shape

- Fixed SwarmFlow path: intake -> one intent compilation capsule -> intent Gate -> requirement capsule calls -> requirement Gates.
- Accepted requirements feed the planner. Its DAG is validated, bound to reusable CC versions and declaration-derived Gate tests, then frozen before local execution.
- A node is the task-specific hot-path use of a CC. `research.verifier` is a CC that checks the result of the node. One shared implementation serves pinned declaration-specific test instances; Gates have zero RSI-mutable components.
- Failed Gates halt following capsule dispatch. Accepted terminal results enter ordinary Delivery processing/publication and flow to the user view.
- [Information flow](../system/information-flow.md) provides full, observability-hidden, RSI-hidden and core views. Required capture and authority remain in all views.
- [Gate construction](../capsule/gate-capsules.md#declaration-derived-gate-construction), [node model](../system/nodes.md#capsule-versus-node), [planner](../system/planner.md) and [control flow](../m1/control-flow.md) define these architecture responsibilities. Exact revised frontend/builder wire contracts remain connected design work.

## Portable snapshots

- [Presentation PDF](../../../output/pdf/m1-architecture-presentation-2026-10-05.pdf).
- [Current-state PDF](../../../output/pdf/m1-architecture-current-state-2026-10-05.pdf).

Both currently contain the same eight-page snapshot so their labels and flow agree. Detailed schemas and behavior stay in the linked Markdown owners. Design precedents and their reasoning remain beside decisions in those owners; there is no separate presentation citation authority.
