# AGENTS.md — [TODO: Module or code subtree]

> Local template. Maintainer: [TODO: Module owner]. Integrate it into `AGENTS.md` in the actual code directory, preserving existing instructions.
> This is a template. Unfilled paths, commands, and owners are not confirmed project facts.

## 1. Scope and responsibility

- Actual scope: [TODO: Repository-relative code paths, included areas, and exclusions.]
- Owner / backup: [TODO: Names.]
- Owns: [TODO: Behavior, state, and interface boundaries.]
- Outside scope: [TODO: Responsibilities owned elsewhere and their owners.]
- Parent instructions: [TODO: Actual AGENTS locations from the root to this directory.]
- Upstream/downstream owners: [TODO: Providers, consumers, and cross-module confirmation roles.]

These instructions supplement parent AGENTS files. For changes outside this subtree, read that path's instructions. Record conflicts with project gates or approved design and obtain Code Team Lead clarification.

## 2. Required context

Enter repository-relative paths and effective versions. Task references may be resolved from the current TASK-ID; do not copy task status history here.

| Material | Location / version |
| --- | --- |
| Module design and architecture | [TODO] |
| Input/output and error contracts | [TODO] |
| Callers and dependencies | [TODO: Relevant section of docs/code-map/FILE_MAP.md.] |
| Ownership and current module status | [TODO: Relevant sections of OWNERSHIP.md and CURRENT_STATUS.md.] |
| Environment and testing methods | [TODO: Relevant ENVIRONMENT.md and TESTING.md sections.] |
| Current TASK / write_code | [TODO: Entry points in `docs/tasks/<TASK-ID>/`.] |
| Current plan and implementation checklist | [TODO: Plan and checklist locations, or simplified TASK sections.] |
| Verification, review, and handoff | [TODO: Actual task evidence locations or sections.] |

Reference existing material where applicable. Explain N/A items; do not create redundant architecture or contract documents for unrelated documentation-only changes.

## 3. Interfaces and invariants

- Entry functions, classes, or APIs: [TODO: Actual symbols and paths.]
- Inputs, outputs, and schema/protocol versions: [TODO.]
- State, side effects, and resource lifecycles: [TODO.]
- Required invariants: [TODO: Observable constraints.]
- Errors, timeouts, retries, cancellation, and idempotency: [TODO or N/A with reason.]
- Compatibility and migration: [TODO.]
- Module-specific rules and non-obvious pitfalls: [TODO.]

Update contracts and obtain provider/consumer confirmation when interfaces change. Follow design change control for material deviations; ordinary implementation choices within authorization do not need repeated approval.

## 4. Verification entry points

| Type | Working directory | Command | Pass criteria / authority |
| --- | --- | --- | --- |
| Targeted tests | [TODO] | [TODO] | [TODO] |
| Boundaries and failure paths | [TODO] | [TODO] | [TODO] |
| Contract / cross-module integration | [TODO or N/A with reason] | [TODO] | [TODO] |
| Required performance/model evaluation | [TODO or N/A with reason] | [TODO] | [TODO: Approved thresholds.] |

Check commands against actual configuration before running them. Missing data, services, LFS objects, or runtime prerequisites remain visible as blocked checks; do not report unrun checks as passed. Record implementation SHA, baseline, environment, commands, results, and logs.

## 5. Development and handoff

1. Read applicable AGENTS, design/contracts, and current write_code; confirm authorization and the baseline.
2. Understand each changed file and identify affected functions, callers, and tests. Coordinate cross-module changes with the corresponding owners.
3. Implement in small steps, maintain the checklist, and update the current-status entry. Keep task logs outside AGENTS.
4. Complete the applicable verification and AI review before the Code Team Lead's function-level human review.
5. Verify integration, update contracts/maps and affected entry points, and hand off known limits, evidence, recovery steps, and follow-up work.

Before adoption, consult the [root template](AGENTS_global.md), [SOP](Code_SOP.md), and [module guide index](code_sop/README.md). Adjust these links to point to actual project documentation when deploying this file.
