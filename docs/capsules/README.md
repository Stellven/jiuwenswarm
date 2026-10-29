# Capability capsules

- [Current M1 Docker execution](m1-local-process.md): completion-only Codex, OpenJiuwen agents, ordinary app-container jobs, current tests and live acceptance limits.

- [Builder upgrade branch](builder-upgrade.md): bounded edits, protected development tests, independent checks and Benchmark handoff.
- [Builder before the upgrade](builder-current-flow.md): inspected M1 baseline at `60f65abe`.
- [Core typed Planner for M1](typed-planner-m1.md): catalog assembly, bounded correction, checks, gates and operation.
- [Capability admission and interoperability](capability-dag.md): optional capsule candidates and trust boundaries.
- [Development process](development.md): building and independently checking a candidate.
- [Factory direction](factory-direction.md): proposed follow-on work.
- [Historical branch handoff](branches.md): original delivery identities; see the current [integration status](../../deploy/m1/INTEGRATION-STATUS.md) for merge state.

The core Planner is required M1 integration. Individual new work capsules remain
optional until explicitly qualified, admitted and activated. Merging their code
does not perform those steps. Earlier optional-Planner framing in development
guidance is superseded by the required core Planner described above.

These are October 23 user-authorized extensions. The maintained design-owner
checkout remains the architecture authority for unchanged behavior. Historical
Generalist definitions do not automatically authorize new runtime permissions.
