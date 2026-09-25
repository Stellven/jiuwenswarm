# Current team status

> Suggested location: `docs/governance/CURRENT_STATUS.md`.  
> Maintainers: task authors update their rows, module owners verify blockers, and the Code Lead verifies review and merge state.  
> After copying: insert real tasks, module paths, and owners; remove example rows. Historical snapshots are not live verification.

## Usage rules

- This is the single maintained source for current task state. TASK, AGENTS, plans, and handoffs reference the TASK-ID row here. Keep stage-specific evidence in its authoritative record rather than duplicating details.
- Allowed states: `Backlog / Design pending / Ready / In progress / Blocked / AI review / Human review / Ready to merge / Merged / Done`.
- Update the row and timestamp when a stage or blocker changes. A state represents satisfied conditions; plans, AI self-assessment, or a successful push do not establish completion.
- Explain N/A for conditional items. Missing evidence stays pending, never assumed passed. Return to the appropriate stage when needed; do not bypass invalidated checks or approvals.

## 1. Status baseline — required

| Field | Record |
| --- | --- |
| Last update / updater | [Time and timezone] / [Name] |
| Team integration branch | `huawei_waterloo_main_branch` |
| Last verified main-branch SHA / verification time | [Full SHA] / [Actual time] |
| Environment / known shared limits | `docs/governance/ENVIRONMENT.md` / [Limits or none] |
| Authoritative responsibilities | `docs/governance/OWNERSHIP.md` |

## 2. Current tasks — required

After adoption, replace displayed paths with working repository links. Keep one current-state row per task.

| TASK-ID / task entry | Module / owner | Working branch / PR | Current state | Supporting evidence / verified SHA | Next action | Blocker owner / resolution condition | Updated |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [TASK-ID] / `docs/tasks/<TASK-ID>/TASK.md` | [Module/name] | [Actual branch/PR or not created] | Backlog | [Record or pending; SHA] | [Concrete action] | [Name/condition or none] | [Time] |

After a PR merges, retain Merged while post-merge checks, required follow-up verification, or handoff remain incomplete. Use Blocked when coordination requires it, while preserving the merge fact and the stage to resume.

## 3. Module index — required

Record verified responsibilities and paths. Do not infer function from module names or map the four personnel branches automatically to the four modules.

| Module | Owner / backup | Code and module AGENTS entry | Active TASK-ID | Design / contract entry | Module blocker and owner |
| --- | --- | --- | --- | --- | --- |
| [Verified module] | [Names] | [Actual directory] / `<module-directory>/AGENTS.md` | [Identifiers or none] | [Repository-relative paths] | [Item/name or none] |

Confirm RSI, Router, Capsule, and Verifier responsibilities and directories at adoption. Register unverified items in the blocker table when they affect work.

## 4. Blockers and task dependencies — required when present

| ID | Affected tasks / modules | Blocker facts and evidence | Resolution action | Owner | Deadline / next check | Stage to resume |
| --- | --- | --- | --- | --- | --- | --- |
| [BLOCK-ID] | [TASK-ID/module] | [Facts] | [Executable action] | [Name] | [Actual date] | [Allowed state] |

Maintain each shared blocker once and reference its BLOCK-ID from task rows. Do not keep conflicting resolution states elsewhere. Reference the relevant CHANGE_REQUEST for deferred checks and preserve their incomplete status.

## 5. State entry conditions

| State | Entry conditions and main evidence | Updater / verifier |
| --- | --- | --- |
| Backlog | Problem and task owner registered; design is not yet ready to proceed | Author |
| Design pending | Goal, initial AC, and risks recorded; design or approval incomplete | Author / Lead |
| Ready | Design approved, directive published, scope/owner/prerequisites sufficient to start | Lead / author |
| In progress | Implementation within approved scope; starting baseline and steps recorded | Author |
| Blocked | A concrete blocker prevents progress; owner, resolution condition, and resumption stage recorded | Author / blocker owner |
| AI review | Current implementation self-review and required stage verification have evidence; PR scope and baseline verified | Author / AI reviewer |
| Human review | AI review complete; findings handled or presented for explicit disposition; current version awaits final human decision | Author / Lead |
| Ready to merge | Current human approval valid; blocking findings resolved; required checks passed or have explicit Code Lead deferrals permitting merge; all other gates satisfied | Lead / merge executor |
| Merged | PR is actually in the team main branch, merge SHA recorded, post-merge checks/handoff underway | Merge executor |
| Done | Post-merge checks, required follow-up verification, documentation/state updates, and owner handoff complete; release tasks also finish release verification | Author / receiving owner |

Return to In progress for review fixes, or Design pending for a material design change, pausing affected work only. If implementation or baseline changes invalidate evidence, return to the stage that must be repeated. A deferral never turns Not run into Passed and cannot alone bypass known blocking defects or current acceptance failures.

## 6. Completed-task index and recent changes — update as needed

| TASK-ID | Merge SHA / date | Final verification and review entry | Handoff and receipt evidence |
| --- | --- | --- | --- |
| [Actually Done task; state none if absent] | [SHA/date] | [Actual paths/sections] | [Actual HANDOFF or TASK/PR handoff section] |

- Recent material state changes: [Date, task, change, and reason; retain what helps coordination and handoff].
- Priorities for the next person taking over: [Action, owner, and necessary context].

Related templates: [TASK](TASK_TEMPLATE.md), [PLAN](PLAN_TEMPLATE.md), [CHANGE_REQUEST](CHANGE_REQUEST_TEMPLATE.md), [HANDOFF](HANDOFF_TEMPLATE.md).

