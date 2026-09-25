# [TASK-ID] implementation plan

> Suggested location: `docs/exec-plans/<TASK-ID>.md`.  
> Maintainer: task author; the next executor continues the record after handoff.  
> After copying: fill placeholders. Update at milestones, approach changes, and handoff; do not reproduce every edit or conversation.

## Usage rules

- Standard and high-risk tasks use a separate plan. Simplified tasks may keep this content in the plan section of `docs/tasks/<TASK-ID>/TASK.md`.
- A plan explains how approved work will be carried out; it does not expand authority. Explain N/A for conditional items. Give unresolved items an owner and resolution condition.
- Current task state belongs in `docs/governance/CURRENT_STATUS.md`. Maintain only step progress, discoveries, decisions, and remaining work here.

## 1. Baseline and objectives — required

| Field | Record |
| --- | --- |
| TASK / author / updated time | `docs/tasks/<TASK-ID>/TASK.md` / [Name] / [Time] |
| Goal / non-goals | [Expected outcome] / [Excluded work] |
| Requirements and AC source | TASK at [version and actual section] |
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

| Step | Action | Prerequisite steps | Owner | Observable completion condition | Step state / evidence |
| --- | --- | --- | --- | --- | --- |
| 1 | [Action] | [Numbers or none] | [Name] | [Result or check] | Not started / evidence pending |

## 4. Verification plan — required

| When | AC / affected boundary | Command or inspection method | Working directory / environment prerequisites | Pass criterion source | Result location |
| --- | --- | --- | --- | --- | --- |
| [Baseline/after step/final/post-merge] | [AC-ID/boundary] | [Verified command or pending verification] | [Conditions] | [TASK version/AC or approved method] | [Actual TEST_REPORT or TASK/PR verification section] |

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

