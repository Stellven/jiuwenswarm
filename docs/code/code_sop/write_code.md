# Coding Execution Protocol for AI

Maintainer: Code Team Lead. This is a reusable operating protocol. Store the current task's specific authorization separately in `docs/tasks/<TASK-ID>/write_code.md`, using the [WRITE_CODE template](templates/WRITE_CODE_TEMPLATE.md). This protocol alone does not approve a design or grant merge or release permission.

## Preparation

The Lead provides the specific TASK-ID, design approval, permitted change scope, and acceptance criteria. The author provides the working branch, baseline, environment, and a description of uncommitted changes. Mark missing facts as pending confirmation; do not invent an approval to let AI start work.

Provide the following text to AI together with actual task entry points, replacing every placeholder:

```text
You are responsible for implementing AI4Research task [TASK-ID].

Working repository: [Path]
Working branch: [Personal branch or approved task branch]
Task and implementation authorization: [TASK.md path], [This task's write_code.md path and version]
Design and contracts: [Paths and approved versions]
Plan: [Path or TASK section]

1. Confirm the repository, branch, working-tree diff, and baseline. Read every AGENTS file from the repository root to the target directory.
2. Read TASK, write_code, the design, contracts, related implementation, tests, and callers.
3. Check whether current authorization covers the planned actions. Do not request an existing explicit approval again.
4. Identify affected files and functions, callers, implementation order, and verification methods. Maintain a persistent plan.
5. Implement in small steps within the authorized scope. Preserve other work, avoid unrelated refactoring, and do not weaken acceptance criteria.
6. If a core contract is missing, the design must change, or the scope must expand, report the specific conflict and pause work that depends on that decision. Continue independent, authorized work.
7. Run the required checks and record exact commands, working directories, environment, implementation SHA, baseline, and results.
8. Inspect the final diff and update affected design, contract, code-map, and task records.
9. Deliver a change description, file-level responsibilities, verification evidence, known limitations, risks, rollback information, and next steps.

AI does not replace the author's understanding of the code and must not invent test results or human approvals. Merging and releasing require actual task authorization and workflow gates; this task's write_code defines the specific boundaries.
```

## When the Author Receives AI Output

- Personally read each changed file and be able to explain its purpose, callers, failure paths, and corresponding tests.
- Verify that the output satisfies the design and ACs, rather than only checking that it runs.
- Check that AI actually executed the commands it claims to have run. State limitations for results that cannot be reproduced.
- Use the [review protocol](review.md) for AI review first, then submit the work to the Code Team Lead for human review.
- Assign an owner and next action to every unresolved item so that it does not remain only in chat.
