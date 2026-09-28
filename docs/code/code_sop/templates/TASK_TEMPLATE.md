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
| Artifact mode | [Manual / Spec Kit; select one] |
| Feature directory and branch mapping | [Spec Kit: exact `specs/<feature-directory>/` and its actual personal/approved task branch; Manual: N/A] |
| Tooling version and setup evidence | [Spec Kit: pinned version and verified repository setup; Manual: N/A or documented setup blocker] |
| Manual fallback decision, if required | [New Standard/High risk task with blocked setup: Lead approval, reason, permitted scope, and evidence; otherwise N/A] |
| Affected modules / code paths | [Actual modules and paths; label proposed additions] |
| Working branch / team-main baseline | [Personnel or approved task branch] / [Full SHA] |
| Prerequisite tasks / external dependencies | [Task identifiers, owners, completion conditions; state none if applicable] |
| Applicable AGENTS | [Actual paths from repository root to target directories] |

After repository setup and successful pilot validation, new Standard and High risk tasks use Spec Kit by default. If setup is blocked, the Lead may approve a documented Manual fallback. Existing Manual tasks are not automatically migrated; the simplified Manual path remains available. See [SPEC_KIT_WORKFLOW](../SPEC_KIT_WORKFLOW.md) for the verified tool version, setup, and branch handling. Selecting a mode or generating artifacts grants no implementation authority.

### Register the authoritative artifacts

Replace conventions with actual paths and versions. In Spec Kit mode, TASK is the ownership, risk, branch, artifact, and approval register. Requirements remain in `spec.md`, technical design in `plan.md`, and ordered work/progress in `tasks.md`. Do not copy their contents into parallel TASK, DESIGN, or PLAN records.

| Information | Actual source and version |
| --- | --- |
| Requirements, scope, non-goals, and AC identifiers | [Manual: Section 2/3 below; Spec Kit: exact `specs/<feature-directory>/spec.md` and version] |
| Technical design | [Manual: actual DESIGN or TASK minimum-design section; Spec Kit: exact `specs/<feature-directory>/plan.md` and version] |
| Ordered work, dependencies, and progress | [Manual: actual PLAN or TASK brief-plan section; Spec Kit: exact `specs/<feature-directory>/tasks.md`] |
| Human implementation authorization | `docs/tasks/<TASK-ID>/write_code.md` at [version and actual approval evidence] |
| File understanding and SOP gates | [Actual IMPLEMENTATION_CHECKLIST, FILE_MAP, or permitted compact record] |
| Verification and review evidence | [Actual TEST_REPORT and review records, or permitted compact verification section] |

## 2. Problem, goal, and non-goals — required

**Manual:** complete the fields below. **Spec Kit:** replace the fields with references to the relevant sections of the registered `spec.md`; do not maintain a second requirements description here. Task coordination risks may remain here; requirement assumptions belong in the specification.

- Problem and source: [Requirement, bug reproduction, or current-state evidence].
- Target behavior: [Who observes what change, under which conditions].
- In scope: [Work covered by this task].
- Non-goals: [Explicit exclusions].
- Known risks and assumptions: [Impact, response, owner; state none if applicable].

## 3. Acceptance criteria — required; one authoritative source

**Manual:** the table below is authoritative. **Spec Kit:** remove the table from the task instance and record only the exact `spec.md` version and acceptance-section reference. Maintain stable `AC-01`, `AC-02`, and subsequent identifiers in that specification, with mappings to native requirement/story identifiers where useful. Never mirror its AC table in TASK.

Designs, tests, work items, and reviews reference the selected source and its stable identifiers. Obtain appropriate approval before changing an accepted criterion. Excerpts elsewhere must identify the source and must not become independently maintained standards.

| ID | Scenario / precondition | Observable expected result | Verification method and pass criterion |
| --- | --- | --- | --- |
| AC-01 | [Scenario] | [Result] | [Test or inspection with an explicit condition] |

For performance or research tasks, specify dataset version, metrics, baseline, environment, seeds/repetitions, and thresholds in the registered requirements/design artifacts before implementation. If evidence is missing, define a measurement task first; do not invent thresholds after seeing results.

## 4. Design and implementation authority — required

- Requirements source and version: [Registered TASK section or `spec.md`; v1 / v2 / project version scheme].
- Technical design: [Spec Kit: registered `plan.md`; Manual Standard/High risk: `docs/design/<TASK-ID>.md`; version in either case].
- Implementation directive: `docs/tasks/<TASK-ID>/write_code.md` at [version].
- Simplified Manual minimum design: [Proposed behavior, approach, file scope, evidence that interfaces remain unchanged, related AC, main risks; omit in Spec Kit mode].
- Simplified Manual implementation boundary: [Allowed paths, excluded scope, stop/escalation conditions; omit in Spec Kit mode]. A brief `write_code.md` may reference this section rather than repeating it.

| Approved object and version | Code Lead / authorized delegate | Decision | Time and timezone | Explicit decision evidence and conditions |
| --- | --- | --- | --- | --- |
| [Registered requirements/design/work-item scope and directive versions] | [Name] | Pending approval | [Pending] | [Actual approval record or pending; reference one decision rather than duplicating it] |

One explicit decision may approve the listed design and directive together. Generated specifications, plans, work items, analysis results, or checkboxes are not human approval. Before approval, conduct only authorized investigation and preparation. Use [CHANGE_REQUEST_TEMPLATE.md](CHANGE_REQUEST_TEMPLATE.md) for scope or contract changes.

## 5. Plan and implementation checklist — required; may reference separate records

**Spec Kit:** reference registered `plan.md` for technical design and `tasks.md` for ordered work, dependencies, and progress; omit the step table below. Do not create duplicate `docs/design/` or `docs/exec-plans/` copies. IMPLEMENTATION_CHECKLIST retains SOP gates and author understanding and references native work-item progress.

**Manual:** Standard/High risk tasks reference `docs/exec-plans/<TASK-ID>.md` and `docs/tasks/<TASK-ID>/IMPLEMENTATION_CHECKLIST.md` without duplicating progress. Simplified tasks use this table or identify an equivalent actual brief-plan section:

| Step | File / action and dependencies | Related acceptance | Step state and evidence |
| --- | --- | --- | --- |
| 1 | [Action] | AC-01 | Not started — evidence pending |

- Author file-level understanding: [Actual FILE_MAP/checklist/PR section; a small documentation task may record its files and purposes here].
- Findings / decisions / remaining work: [Simplified Manual: maintain here; other Manual tasks: reference PLAN; Spec Kit: reference technical decisions in plan.md and work/progress in tasks.md].

## 6. Verification record — required; may reference a separate record

Standard/high-risk tasks reference `docs/tasks/<TASK-ID>/TEST_REPORT.md`. Simplified tasks maintain the table here or reference an actual PR verification section, never duplicate the same results. Record implementation [SHA], main baseline [SHA], environment [identifier], and working directory [path]. Uncommitted checks are work-in-progress evidence.

| AC / check | Actual command or inspection | Actual result | Logs / evidence | Owner and deadline for incomplete work |
| --- | --- | --- | --- | --- |
| AC-01 | [Command or action] | Not run | [Pending] | [Name/date or N/A with reason] |

Documentation-only tasks may inspect links, content, and consistency. Report only completed checks; distinguish Passed, Failed, Skipped, Not run, and Blocked.

## 7. Review and delivery entry points — required

- AI and human review: `docs/tasks/<TASK-ID>/review.md`. Simplified tasks still retain genuine evidence for both stages.
- PR: [Actual URL or not created]; base: `ai4r_main_branch`.
- Handoff: [Actual `docs/tasks/<TASK-ID>/HANDOFF.md`, or simplified TASK/PR section recording changes, verification, remaining items, recipient, and receipt evidence].
- Post-merge verification and state update: [Actual merge SHA, check evidence, and CURRENT_STATUS row]. Do not claim Done while required checks, follow-up verification, or handoff remain incomplete.

Related templates: [DESIGN](DESIGN_TEMPLATE.md), [PLAN](PLAN_TEMPLATE.md), [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [REVIEW](REVIEW_TEMPLATE.md), [STATUS](STATUS_TEMPLATE.md).
