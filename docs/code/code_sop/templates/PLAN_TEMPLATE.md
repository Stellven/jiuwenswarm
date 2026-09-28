# [TASK-ID] implementation plan

> Manual location: `docs/exec-plans/<TASK-ID>.md`. In Spec Kit mode, use these prompts within registered `plan.md` and `tasks.md`; do not create a duplicate execution-plan file.\
> Maintainer: task author; the next executor continues the record after handoff.  
> After copying: fill placeholders. Update at milestones, approach changes, and handoff; do not reproduce every edit or conversation.

## Usage rules

- Follow the artifact mode registered in TASK and [SPEC_KIT_WORKFLOW](../SPEC_KIT_WORKFLOW.md). New Standard/High risk tasks use Spec Kit by default after setup and successful pilot validation; a blocked setup needs documented Lead approval for Manual fallback. Existing Manual tasks do not migrate automatically.
- In Manual mode, Standard/High risk tasks use a separate plan. Simplified tasks may keep this content in the plan section of `docs/tasks/<TASK-ID>/TASK.md`.
- In Spec Kit mode, `plan.md` alone holds technical design, file/dependency rationale, and verification strategy; `tasks.md` alone holds ordered work, dependencies between work items, progress, blockers, and remaining work. Incorporate the relevant prompts below into those files rather than maintaining duplicate tables. Link technical decisions from work items to their design or ADR record.
- A plan explains how approved work will be carried out; it does not expand authority. Explain N/A for conditional items. Give unresolved items an owner and resolution condition.
- Current task state belongs in `docs/governance/CURRENT_STATUS.md`. Step progress belongs in the selected execution record, not in a second task-status register. Native checked tasks are not proof that SOP review, tests, or handoff are complete.

## 1. Baseline and objectives — required

| Field | Record |
| --- | --- |
| TASK / author / updated time | `docs/tasks/<TASK-ID>/TASK.md` / [Name] / [Time] |
| Goal / non-goals | [Expected outcome] / [Excluded work] |
| Artifact mode and registered feature | [Manual / Spec Kit; exact feature directory and personal/approved task branch for Spec Kit] |
| Requirements and AC source | [Manual: TASK section; Spec Kit: registered spec.md; actual version and section] |
| Design / contract versions | [Actual paths and versions; explain N/A] |
| Implementation authority | `docs/tasks/<TASK-ID>/write_code.md` at [version and approval evidence] |
| Working branch / team-main baseline | [Branch] / [Full SHA] |
| Applicable AGENTS / environment | [Actual paths] / `docs/governance/ENVIRONMENT.md` |

## 2. Files and dependencies — required

| File / directory | Proposed change and responsibility | Dependencies / callers | Prerequisite or collaborating owner | Related AC |
| --- | --- | --- | --- | --- |
| [Actual path; identify proposed additions] | [Add/modify/delete and reason] | [Symbols or paths] | [Condition/name or none] | AC-01 |

For contracts, data migration, or cross-module ordering, list required predecessor work and explain what cannot run concurrently. Update actual file changes in `docs/code-map/FILE_MAP.md`.

## 3. Execution steps — required

Make each step independently verifiable. Step states are Not started / In progress / Complete / Blocked; these do not replace the task's state. Completion requires evidence, not merely written code.

For Spec Kit, apply this information to native work-item identifiers and preserve the tool's supported task syntax. Record AC references, dependencies, blockers, and evidence in `tasks.md` without creating a separate progress table here. Technical planning and task generation may precede implementation authorization; execution may not.

| Step | Action | Prerequisite steps | Owner | Observable completion condition | Step state / evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | [Action] | [Numbers or none] | [Name] | [Result or check] | Not started / evidence pending |

## 4. Verification plan — required

| When | AC / affected boundary | Command or inspection method | Working directory / environment prerequisites | Pass criterion source | Result location |
| --- | --- | --- | --- | --- | --- |
| [Baseline/after step/final/post-merge] | [AC-ID/boundary] | [Verified command or pending verification] | [Conditions] | [Registered TASK/spec.md version and AC, or approved method] | [Actual TEST_REPORT or TASK/PR verification section] |

- Pre-existing baseline failures: [Evidence and impact; state Not checked if unknown].
- Inapplicable checks: [Item and reason].
- Checks that cannot run: [Blocker, owner, resolution condition]; do not report them as passed.

## 5. Discoveries and decisions — record when they occur

| Time | Discovery / decision | Evidence and rationale | Effect on steps / AC / authority | Next action / owner |
| --- | --- | --- | --- | --- |
| [Time] | [Actual discovery or decision] | [Path, experiment, or approval] | [Impact] | [Action/name] |

Record ordinary implementation choices within existing authority directly. For scope, public-interface, architecture, or acceptance changes, use [CHANGE_REQUEST_TEMPLATE.md](CHANGE_REQUEST_TEMPLATE.md) and pause dependent steps. Lasting decisions may also need an ADR.

## 6. Remaining work and handoff — required; keep current

| Incomplete item | Cause / blocker | Concrete next action | Owner | Deadline / resumption condition |
| --- | --- | --- | --- | --- |
| [Item; explicitly state none once complete] | [Cause] | [Action] | [Name] | [Date/condition] |

- Read before resuming: [Minimum necessary files, versions, and sections].
- Verified code SHA / scope: [Actual commit and check evidence].
- Conclusions not yet supported: [Unverified behavior or unapproved scope; state none if applicable].

## 7. Plan closure — fill when complete

- Final outcome and AC evidence: [Actual verification and review locations].
- Deviations and disposition: [Changes and approval records; state none if applicable].
- Post-merge checks and handoff: [Actual evidence; retain incomplete status until done].

Related templates: [TASK](TASK_TEMPLATE.md), [IMPLEMENTATION_CHECKLIST](IMPLEMENTATION_CHECKLIST_TEMPLATE.md), [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [FILE_MAP](FILE_MAP_TEMPLATE.md).

