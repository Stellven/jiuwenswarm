# AI4Research Repository Instructions

Maintainer: Xiaoyang, Code Team Lead. These instructions apply throughout this repository. Existing instructions in code subtrees remain applicable.

## Entry points

- Policy: [Code SOP](docs/code/Code_SOP.md).
- Spec Kit: [workflow](docs/code/code_sop/SPEC_KIT_WORKFLOW.md) and [constitution](.specify/memory/constitution.md).
- Active task register: [AI4R-001](docs/tasks/AI4R-001/TASK.md).
- Current status: [CURRENT_STATUS](docs/governance/CURRENT_STATUS.md).
- Tooling and environment: [ENVIRONMENT](docs/governance/ENVIRONMENT.md).

Task records hold requirements, decisions, status, and evidence. Keep this file focused on durable rules and entry points.

## Working rules

1. Read the task registry, applicable root/local AGENTS, registered specification/design, and current task `write_code.md` before acting. Inspect existing callers and tests before changing implementation.
2. The seven SOP principles remain binding. Reuse existing explicit authorization for the scope it covers; do not fabricate a human decision or require repeated approval of already authorized preparation.
3. Implement on the assigned personal branch. Team PRs target `ai4r_main_branch`. Preserve other work. The explicit local reset requested for task setup is not a standing authorization for future destructive synchronization or remote force pushes.
4. In Spec Kit mode, native `spec.md` owns requirements/ACs, `plan.md` owns technical design, and `tasks.md` owns ordered work/progress. TASK registers paths and approvals. Do not create duplicate design or plan files.
5. Set the exact feature directory from TASK before native commands. `.specify/feature.json` is local and ignored. Do not infer feature selection from the Git branch or allow optional Git hooks to change branches.
6. Check installed hooks and command side effects. Generated tasks, checklists, analysis, and convergence output do not authorize implementation, prove tests passed, or approve merging.
7. Require the task's risk-proportionate verification in native work items. Tests must demonstrate behavior; record actual commands, covered versions, results, skips, and limitations.
8. Authors understand every changed file. AI reviews the actual diff and evidence before final human review. When Xiaoyang is also the author, an independent qualified human must perform final review under the SOP; identifying that reviewer is not a prerequisite for authorized preparation.
9. Preserve credentials in the appropriate local authentication mechanism. Do not expose them in UI state, documentation, version control, or ordinary logs.
10. Material changes to requirements or authorized scope use the SOP change process. Ordinary implementation choices inside an established design do not need repeated approval.
11. Strictly follow each record's corresponding template. Read it before writing, retain required sections/fields/table columns and evidence, explain N/A, and preserve unresolved states with owners and resolution conditions. Verify template coverage before delivery. Follow [SOP Section 4.1](docs/code/Code_SOP.md#41-mandatory-template-conformance-for-ai-and-human-authors), including native Spec Kit coverage mapping; do not substitute an improvised summary.

## Existing local instructions

For web changes, read `jiuwenswarm/channels/web/AGENTS.md` and the frontend's `AGENTS.md`. Trajectory changes also require its subtree instructions. Preserve frontend test identifiers, shared settings layout, supported browser compatibility, localization, and applicable visual/build verification.

The user's requested feature work permits the functional changes needed for that work; the older test-ID-only editing instruction applies to a test-ID-only pass and does not cancel an explicitly requested frontend/backend feature migration. Apply its naming rules to touched controls.

## Evidence and commands

Use the commands recorded in ENVIRONMENT and each task's preparation/test record. Missing dependencies or account access remain visible limitations. Do not claim application readiness from Spec Kit initialization or a successful CLI version command.

Generated `.agents/skills/speckit-*` instructions provide workflow assistance. They must be read together with these rules and the task directive. Shared architecture/contracts stay authoritative; native supporting artifacts reference them rather than silently replacing them.
