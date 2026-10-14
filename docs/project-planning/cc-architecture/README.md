# CC architecture planning

Human coordination for the October target and the sequenced November architecture work. The target is a bounded Compiler → Planner → selected downstream CCs → Delivery path with benchmark report and indexed artifact dataset. Current implementation status uses generic Leader/SwarmFlow with four fixed roles and worker-data replay; it is not yet the integrated target or an interactive conversation. This folder does not define product architecture or coding-task authority.

## Start here

- [Plan and dated coordination schedule](plan.md)
- [One-shot comparative study and evidence limits](oneshot-study.md)
- [Approved scope decisions](decisions.md)

## Design authority

The maintained design remains [the full architecture package](../../architecture/design-package/README.md), interpreted with the separately supplied PRD. Product owners author the PRD; architecture consumes it. Start implementation preparation at the [Core build](../../architecture/design-package/core-build.md) and [immediate plan](../../architecture/design-package/immediate-plan.md). This schedule records an approved declaration-and-output-only semantic assessment limit; it does not claim full intent-fidelity assurance. The October benchmark sidecar remains separate development tooling and never blocks product startup or acceptance.

The [plan](plan.md) groups existing records into Compiler, Planner, bounded downstream CCs, and shared checking/gates without replacing task identities. October interface integration and benchmark-runner architecture have separate subtasks. Investigation notes link to shared work and evidence. November work is a 15-human-day sequence with feature-level acceptance; composition is reserved for December M3.
