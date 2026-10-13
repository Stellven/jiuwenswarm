# Repository AGENTS template for SOP v2
Integrate into the repository root, preserving applicable implementation constraints.

## Entry points
- Policy: docs/code/Code_SOP.md.
- Program entry: docs/code/Missions/<PROGRAM-ID>/TASKS.md.
- Task entry: docs/code/Missions/<PROGRAM-ID>/<TASK-ID>/TASK.md.
- Spec Kit workflow: docs/code/SPEC_KIT_WORKFLOW.md.
- Verification: docs/code/VERIFICATION.md.
- Constitution: .specify/memory/constitution.md.

## Durable rules
1. Start with TASKS -> TASK -> the exact registered feature directory. Read applicable subtree AGENTS and existing callers/tests before implementation.
2. TASKS owns source allocation and dependencies. TASK owns identity, scope and interface agreements. Native spec, plan and tasks own acceptance, design and work/evidence correspondence respectively.
3. Each TASK has an executor and one Spec Kit directory. Do not create separate authorization, implementation-checklist, review, handoff or test-report cards.
4. Cross-module definitions live in one owning TASK; consumers reference IF ID/revision. Generated schemas implement that agreement.
5. Implement and verify block by block, verify connected boundaries, then verify the whole candidate through a system TASK.
6. Preserve evidence and distinguish PASS, FAIL, BLOCKED, NOT_RUN, STALE and N/A. Checkboxes alone never prove acceptance.
7. Missing future PRD/architecture inputs do not stop unrelated preparation. Never invent models, thresholds or schemas.
8. Select the feature explicitly; isolate concurrent generation. Read project overrides and include the v2 invocation context when using native skills.
9. Generated requirements-quality checklists are diagnostic and must not restore the removed approval/reviewer process. Resolve their findings in native artifacts.
10. Update affected source mappings, IF references and evidence after material changes. Ordinary progress updates only native tasks.md.
11. Preserve unrelated work and credentials. Follow actual user authorization for external actions; never auto-commit or bypass a no-commit instruction.
12. Read the relevant template and retain its required fields and matrices. Explain N/A and unresolved conditions.
