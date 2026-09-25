# Review Protocol for AI and the Code Team Lead

This document defines a reusable review method. Use the [REVIEW template](templates/REVIEW_TEMPLATE.md) for each task's actual evidence and save it as `docs/tasks/<TASK-ID>/review.md`. Different people's tasks must not overwrite a single global results file.

## Inputs for AI Review

Provide TASK/ACs, the basis for design approval, applicable AGENTS files, write_code, the final diff, implementation commit and base, and actual verification records. Plans, checklists, and reports may reference simplified sections within TASK. Reference existing architecture, contracts, and file maps according to their relevance to the change. For unrelated cases, such as explanatory documentation edits, explain N/A rather than creating unnecessary files. For code changes, also read affected callers and key tests. If required inputs are missing, state the uncovered scope and do not claim comprehensive verification.

Provide the following protocol to AI with the actual paths:

```text
Review task [TASK-ID]. At this stage, review only; do not modify code or substitute for human approval.
Implementation commit: [HEAD or tested implementation SHA]; team main-branch baseline: [BASE SHA].
Materials: [Actual paths for TASK, design, contracts, write_code, plan, test report, and file map, as applicable].

Check in this order:
1. Whether requirements and acceptance criteria are fully implemented, and whether the current implementation matches the design.
2. Architecture boundaries, interface compatibility, call chains, state, and resource lifecycles.
3. Applicable normal, boundary, exception, timeout, and cancellation paths; side effects and recovery from failure.
4. Whether tests demonstrate the changed behavior, and whether any failures were skipped or hidden.
5. Whether performance or model evaluations use the agreed data, versions, baselines, and thresholds, and whether results are reproducible.
6. Whether file changes exceed write_code authorization, and whether documentation, contracts, and handoff records are consistent.

For each finding, record its ID, severity, file/function location, trigger conditions, evidence, user/system impact, suggested fix, and verification method.
Distinguish confirmed defects, risks requiring verification, clarification questions, and nonblocking suggestions. Do not invent defects.
Report reviewed and unreviewed scope, versions, findings, author action items, and the review recommendation.
If there are no findings, state coverage and remaining limitations rather than claiming there are no defects anywhere.
Write results in the AI section of this task's review.md. Leave human approval pending for the human reviewer.
```

## Addressing Findings and Reviewing Again

The author fixes each finding or provides evidence explaining why it is not a defect. The Lead decides whether significant risks are acceptable. A follow-up review references finding IDs, fix commits, and check results. Verify affected portions again when implementation, contracts, tests, configuration, or the relevant baseline changes.

When only result documents are added, the original implementation SHA may be referenced. List later record-only commits and verify the diff; the report does not need its own SHA. Markdown that changes a contract or acceptance criterion cannot be treated as documentation without behavioral impact.

## Human Review and Decision

The Code Team Lead, or an independent delegate who understands the overall codebase, must personally read affected key functions and call chains. They check the author's file-level explanation, test evidence, cross-module confirmations, and rollback information. If the Lead is the author, they cannot replace independent review with self-approval.

Record the human review's version, date, scope, decision, and reasoning. AI may recommend a decision, but a human approves merging. A task must not enter Ready to merge when blocking findings remain open, required checks are incomplete without a formal deferral explicitly authorizing merge, or approval is no longer valid. The main SOP's exception rules define the permitted deferral scope. Deferral cannot bypass known blocking defects or current acceptance failures, and the task cannot be Done until deferred verification is complete.

The [main SOP](../Code_SOP.md) governs all gates and exception rules. Use the [REVIEW template](templates/REVIEW_TEMPLATE.md) for structured records.
