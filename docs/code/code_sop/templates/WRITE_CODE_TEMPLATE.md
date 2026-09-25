# write_code.md — [TASK-ID: Task title]

> Deployment location: `docs/tasks/<TASK-ID>/write_code.md`. Maintainer and issuer: Code Team Lead.
> The author or AI may draft this document; actual approval must come from a human. Unfilled authorization fields mean approval is pending and formal implementation must not begin.
> Use for every task. Small tasks may shorten the text and reference design and verification sections in TASK, while retaining boundaries, acceptance criteria, and approval.

## 1. Issue and authorization

| Field | Record |
| --- | --- |
| TASK-ID / author / module owner | [TODO] |
| Document revision | [TODO] |
| Working branch / integration branch | [TODO] / `huawei_waterloo_main_branch` |
| Main branch baseline SHA | [TODO] |
| Approved design version and decision evidence | Pending approval: [TODO] |
| Lead approval of this implementation scope, time, and evidence | Pending approval: [TODO] |
| Related change request | [TODO or None] |

A single human approval may cover explicitly listed versions of both the design and this document. Do not request existing approval again when scope is unchanged. Renew approval for material scope changes instead of reusing an outdated record.

## 2. Required reading

| Material | Actual path / version | Relevant sections for this task |
| --- | --- | --- |
| Root AGENTS and local AGENTS along affected paths | [TODO] | [TODO] |
| TASK and AC identifiers | [TODO] | [TODO] |
| Design, architecture, and ADR | [TODO or N/A with reason] | [TODO] |
| Provider/consumer contracts | [TODO or N/A with reason] | [TODO] |
| Implementation plan and file map | [TODO; may be TASK sections] | [TODO] |
| Environment and testing methods | [TODO] | [TODO] |
| Existing failures, constraints, and handoff | [TODO or None] | [TODO] |

## 3. Goals, permitted scope, and boundaries

- Observable behavior to implement: [TODO; reference AC identifiers. TASK is authoritative for acceptance criteria].
- Out of scope: [TODO].
- Paths permitted for addition/modification: [TODO; identify files/subtrees as precisely as practical].
- Interfaces, data, or dependencies that require confirmation before changing: [TODO].
- Invariants and compatible behavior to preserve: [TODO].
- Cross-module owner confirmation: [TODO or N/A with reason].

## 4. Implementation sequence

| Step | Inputs and prerequisites | Files/functions and expected outcome | Verification / stop conditions |
| --- | --- | --- | --- |
| 1 | [TODO] | [TODO] | [TODO] |

Work in small, verifiable steps. Record detailed progress, findings, and remaining work in the plan. Update this document when implementation authority, boundaries, or sequencing materially change.

## 5. Verification requirements

| AC / risk | Required check | Working directory and exact command | Pass criterion / threshold basis |
| --- | --- | --- | --- |
| AC-01 | [TODO] | [TODO; fill in after confirming the environment] | [TODO] |

- Regression and cross-module checks: [TODO or N/A with reason].
- Performance/model/data reproducibility: [TODO or N/A with reason; establish thresholds in advance].
- Missing environment/data and owners: [TODO or None].
- Verification result location: [TODO: TEST_REPORT or TASK verification section].

## 6. Stops, changes, and exceptions

If a core contract is missing, a design assumption fails, the edit scope must expand, acceptance criteria must change, or an unauthorized external side effect would occur, record the issue and pause affected steps. Independent authorized steps may continue. Use [CHANGE_REQUEST_TEMPLATE.md](CHANGE_REQUEST_TEMPLATE.md) to propose new boundaries; do not lower acceptance requirements unilaterally.

The author decides ordinary implementation details within authorized scope. Record environment blockers honestly; never invent passing results. Exceptions to checks require risks, approval, follow-up verification owner/deadline, and rollback conditions.

## 7. Required deliverables

- Implementation mapped to AC, necessary tests, and final diff, with the author's explanation of every changed file.
- Updated plan and checklist, plus actual verification evidence; update authoritative interface/architecture documents when affected.
- AI review and finding dispositions for the current version, with entry points and call chains for Lead's function-level review.
- PR description, known limitations, rollback information, and handoff material.

Reports do not need their own commit SHA. Reference the tested implementation and baseline, and declare any subsequent changes that only record results or decisions. Revalidate the affected scope after additions or changes to implementation, configuration, contracts, or tests.
