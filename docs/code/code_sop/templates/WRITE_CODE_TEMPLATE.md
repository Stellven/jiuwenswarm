# write_code.md — [TASK-ID: Task title]

> Deployment location: `docs/tasks/<TASK-ID>/write_code.md`. Maintainer and issuer: Code Team Lead.
> The author or AI may draft this document; actual approval must come from a human. Unfilled authorization fields mean approval is pending and formal implementation must not begin.
> Use for every task. Small tasks may shorten the text and reference design and verification sections in TASK, while retaining boundaries, acceptance criteria, and approval.

Spec Kit does not replace this directive. Its generated specification, plan, work items, or analysis report cannot authorize implementation. Follow the artifact mode registered in TASK and [SPEC_KIT_WORKFLOW](../SPEC_KIT_WORKFLOW.md); actual Lead authorization is required before the implementation stage in either mode.

## 1. Issue and authorization

| Field | Record |
| --- | --- |
| TASK-ID / author / module owner | [TODO] |
| Artifact mode / registered feature directory | [Manual / Spec Kit; exact `specs/<feature-directory>/` for Spec Kit] |
| Document revision | [TODO] |
| Working branch / integration branch | [TODO] / `ai4r_main_branch` |
| Main branch baseline SHA | [TODO] |
| Approved design version and decision evidence | Pending approval: [TODO] |
| Registered acceptance source / approved work-item scope | [Manual: TASK and PLAN/brief-plan sections; Spec Kit: exact spec.md, plan.md, tasks.md paths/versions and covered work-item identifiers] |
| Lead approval of this implementation scope, time, and evidence | Pending approval: [TODO] |
| Related change request | [TODO or None] |

A single human approval may cover explicitly listed versions of both the design and this document. Do not request existing approval again when scope is unchanged. Renew approval for material scope changes instead of reusing an outdated record.

## 2. Required reading

| Material | Actual path / version | Relevant sections for this task |
| --- | --- | --- |
| Root AGENTS and local AGENTS along affected paths | [TODO] | [TODO] |
| TASK register and authoritative AC identifiers | [TODO: Manual TASK acceptance section or Spec Kit spec.md] | [TODO] |
| Design, architecture, and ADR | [TODO or N/A with reason] | [TODO] |
| Provider/consumer contracts | [TODO or N/A with reason] | [TODO] |
| Technical design, ordered work, and file map | [TODO: registered plan.md/tasks.md in Spec Kit mode; actual DESIGN/PLAN or simplified TASK sections in Manual mode] | [TODO] |
| Environment and testing methods | [TODO] | [TODO] |
| Existing failures, constraints, and handoff | [TODO or None] | [TODO] |

## 3. Goals, permitted scope, and boundaries

- Observable behavior to implement: [TODO; reference AC identifiers in the registered authoritative source: TASK for Manual mode, spec.md for Spec Kit mode. Do not redefine criteria here].
- Out of scope: [TODO].
- Paths permitted for addition/modification: [TODO; identify files/subtrees as precisely as practical].
- Interfaces, data, or dependencies that require confirmation before changing: [TODO].
- Invariants and compatible behavior to preserve: [TODO].
- Cross-module owner confirmation: [TODO or N/A with reason].

## 4. Implementation sequence

In Manual mode, use the table for the authorized sequence. In Spec Kit mode, identify permitted native task IDs or groups and any authorization conditions; link to `tasks.md` for the complete order and current progress rather than copying its task list. A generated task outside this directive's scope is not authorized.

| Step / authorized native task IDs | Inputs and prerequisites | Files/functions and expected outcome | Verification / stop conditions |
| --- | --- | --- | --- |
| 1 | [TODO] | [TODO] | [TODO] |

Work in small, verifiable steps. Record detailed work progress and remaining items in the registered execution source: native `tasks.md`, Manual PLAN, or a simplified TASK section. Technical design decisions belong in the registered design artifact. Update this directive when authority, boundaries, or authorized sequencing materially change; ordinary progress updates do not require duplicate approval.

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
- Updated authoritative design/work records and the SOP checklist, plus actual verification evidence; update authoritative interface/architecture documents when affected. In Spec Kit mode, do not add parallel DESIGN/PLAN documents or mirror AC tables.
- AI review and finding dispositions for the current version, with entry points and call chains for Lead's function-level review.
- PR description, known limitations, rollback information, and handoff material.

Reports do not need their own commit SHA. Reference the tested implementation and baseline, and declare any subsequent changes that only record results or decisions. Revalidate the affected scope after additions or changes to implementation, configuration, contracts, or tests.
