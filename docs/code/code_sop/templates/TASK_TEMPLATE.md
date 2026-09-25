# [TASK-ID] — [Task title]

> Suggested location: `docs/tasks/<TASK-ID>/TASK.md`.  
> Maintainer: task author. The Code Lead approves design and implementation boundaries.  
> After copying: fill placeholders and remove guidance that no longer applies. Explain N/A for conditional fields. Pending confirmation, unrun checks, and pending approval remain incomplete.

## 1. Task entry points — required

| Field | Record |
| --- | --- |
| TASK-ID / author / module owner | [Identifier] / [Name] / [Name] |
| Code Lead / independent human reviewer | [Names; if the Lead is the author, identify the authorized independent reviewer and authority] |
| Live task status | The TASK-ID row in `docs/governance/CURRENT_STATUS.md`; maintain current task state only there |
| Workflow path and rationale | [Simplified / Standard / High risk] — [Why this path applies] |
| Affected modules / code paths | [Actual modules and paths; label proposed additions] |
| Working branch / team-main baseline | [Personnel or approved task branch] / [Full SHA] |
| Prerequisite tasks / external dependencies | [Task identifiers, owners, completion conditions; state none if applicable] |
| Applicable AGENTS | [Actual paths from repository root to target directories] |

## 2. Problem, goal, and non-goals — required

- Problem and source: [Requirement, bug reproduction, or current-state evidence].
- Target behavior: [Who observes what change, under which conditions].
- In scope: [Work covered by this task].
- Non-goals: [Explicit exclusions].
- Known risks and assumptions: [Impact, response, owner; state none if applicable].

## 3. Acceptance criteria — required; authoritative source

Keep AC identifiers stable. Designs, tests, and reviews reference these identifiers and the requirements version below. Obtain appropriate approval before changing an accepted criterion. Excerpts elsewhere must identify this source and must not become independently maintained standards.

| ID | Scenario / precondition | Observable expected result | Verification method and pass criterion |
| --- | --- | --- | --- |
| AC-01 | [Scenario] | [Result] | [Test or inspection with an explicit condition] |

For performance or research tasks, specify dataset version, metrics, baseline, environment, seeds/repetitions, and thresholds before implementation. If evidence is missing, define a measurement task first; do not invent thresholds after seeing results.

## 4. Design and implementation authority — required

- Requirements version: [v1 / v2 / project version scheme].
- Standard/high-risk path: design `docs/design/<TASK-ID>.md` at [version]; directive `docs/tasks/<TASK-ID>/write_code.md` at [version].
- Simplified minimum design: [Proposed behavior, approach, file scope, evidence that interfaces remain unchanged, related AC, main risks].
- Simplified implementation boundary: [Allowed paths, excluded scope, stop/escalation conditions]. A brief `write_code.md` may reference this section rather than repeating it.

| Approved object and version | Code Lead / authorized delegate | Decision | Time and timezone | Explicit decision evidence and conditions |
| --- | --- | --- | --- | --- |
| [TASK/design/directive versions] | [Name] | Pending approval | [Pending] | [Actual approval record or pending] |

One explicit decision may approve the listed minimum design and directive together. Before approval, conduct only authorized investigation. Use [CHANGE_REQUEST_TEMPLATE.md](CHANGE_REQUEST_TEMPLATE.md) for scope or contract changes.

## 5. Plan and implementation checklist — required; may reference separate records

Standard/high-risk tasks reference `docs/exec-plans/<TASK-ID>.md` and `docs/tasks/<TASK-ID>/IMPLEMENTATION_CHECKLIST.md` without duplicating progress. Simplified tasks use this table or identify an equivalent actual brief-plan section:

| Step | File / action and dependencies | Related acceptance | Step state and evidence |
| --- | --- | --- | --- |
| 1 | [Action] | AC-01 | Not started — evidence pending |

- Author file-level understanding: [Actual FILE_MAP/checklist/PR section; a small documentation task may record its files and purposes here].
- Findings / decisions / remaining work: [Maintain here for a simplified task; otherwise reference the relevant plan sections].

## 6. Verification record — required; may reference a separate record

Standard/high-risk tasks reference `docs/tasks/<TASK-ID>/TEST_REPORT.md`. Simplified tasks maintain the table here or reference an actual PR verification section, never duplicate the same results. Record implementation [SHA], main baseline [SHA], environment [identifier], and working directory [path]. Uncommitted checks are work-in-progress evidence.

| AC / check | Actual command or inspection | Actual result | Logs / evidence | Owner and deadline for incomplete work |
| --- | --- | --- | --- | --- |
| AC-01 | [Command or action] | Not run | [Pending] | [Name/date or N/A with reason] |

Documentation-only tasks may inspect links, content, and consistency. Report only completed checks; distinguish Passed, Failed, Skipped, Not run, and Blocked.

## 7. Review and delivery entry points — required

- AI and human review: `docs/tasks/<TASK-ID>/review.md`. Simplified tasks still retain genuine evidence for both stages.
- PR: [Actual URL or not created]; base: `huawei_waterloo_main_branch`.
- Handoff: [Actual `docs/tasks/<TASK-ID>/HANDOFF.md`, or simplified TASK/PR section recording changes, verification, remaining items, recipient, and receipt evidence].
- Post-merge verification and state update: [Actual merge SHA, check evidence, and CURRENT_STATUS row]. Do not claim Done while required checks, follow-up verification, or handoff remain incomplete.

Related templates: [DESIGN](DESIGN_TEMPLATE.md), [PLAN](PLAN_TEMPLATE.md), [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [REVIEW](REVIEW_TEMPLATE.md), [STATUS](STATUS_TEMPLATE.md).

