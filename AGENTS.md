# AI4Research Repository Instructions
Maintainer: Xiaoyang. These durable instructions apply throughout the repository; existing code-subtree instructions remain applicable.

## Entry points
- [Code SOP v2](docs/code/Code_SOP.md)
- [Future M1 TASKS](docs/code/Missions/M1/TASKS.md)
- [Spec Kit workflow](docs/code/SPEC_KIT_WORKFLOW.md)
- [Verification method](docs/code/VERIFICATION.md)
- [Constitution](.specify/memory/constitution.md)
- Historical environment facts: docs/governance/ENVIRONMENT.md.
- Historical task: docs/code/Missions/AI4R-001/TASK.md; it is not the future-M1 register.

## Working rules
1. Follow TASKS -> TASK -> one registered Spec Kit directory per TASK. Read applicable AGENTS, the exact source clauses, agreements, native spec/plan/tasks and existing callers/tests before implementation.
2. TASKS owns source allocation and task dependencies. TASK owns identity, executor, scope and cross-module agreements. spec.md owns ACs; plan.md owns technical/block design and verification procedures; tasks.md owns work/progress and AC-to-evidence correspondence.
3. Do not create separate write_code, implementation checklist, test-report, review, handoff or change-request cards. The user's requested scope is recorded in TASK. This v2 process has no reviewer-assignment or approval gate.
4. A cross-module agreement has one owning TASK and a stable IF ID/revision. Consumers and generated schemas reference it.
5. Implement and verify blocks, verify connected boundaries, and then verify the complete integrated system. Use current evidence, not checklist completion or generated analysis, to claim acceptance.
6. Record exact candidates, commands, environments, fixtures, expected/observed outcomes and limitations. Required skips, missing services, stale evidence and unrun checks are not passes.
7. Future PRD/architecture/model/threshold inputs may be PENDING_SOURCE. Continue independent preparation and constrain only affected work. Do not fabricate product requirements.
8. Select the exact feature directory before native commands. Isolate concurrent generation; a local feature pointer is not a task lock.
9. Read project overrides in .specify/templates/overrides/ and use the v2 invocation context. Installed skill suggestions about optional tests, reviewer-owned checklists or auto-commits do not reintroduce processes the user explicitly removed. Resolve quality findings in native artifacts; preserve diagnostic truth.
10. Material source/interface changes update TASKS/TASK and affected native records, and invalidate affected evidence. Ordinary progress changes only tasks.md.
11. Preserve unrelated work, existing implementation constraints and credentials. Follow user authorization for external actions. Do not commit, push, merge or deploy merely because a generated task or hook suggests it. Explicit no-commit instructions also exclude merges that would create commits.
12. Read and follow the relevant templates, retaining required fields and matrices. Record unresolved conditions and justified N/A values instead of invented facts.

## Existing code-subtree instructions
For web changes, read jiuwenswarm/channels/web/AGENTS.md and the frontend AGENTS.md. Trajectory changes also require its subtree instructions. Preserve frontend test identifiers, shared settings layout, supported browser compatibility, localization and applicable visual/build verification.

A feature request permits necessary functional changes; the older test-ID-only instruction applies to a test-ID-only pass and does not cancel explicitly requested feature work. Apply its naming rules to touched controls.

## Legacy evidence
Existing task histories and application tests are preserved. New v2 tasks do not require legacy authorization/review cards or completion of unfinished legacy tasks. Do not rewrite past run results when referencing them.
