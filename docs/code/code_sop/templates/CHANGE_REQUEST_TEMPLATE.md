# [TASK-ID] / [CR-ID] — [Change or exception title]

> Suggested location: `docs/tasks/<TASK-ID>/CHANGE_REQUEST-<NN>.md`, where NN is the request sequence number within the task.  
> Maintainer: proposing task author. The Code Lead decides authority boundaries and exceptions.  
> After copying: fill placeholders, select the applicable request type, and remove irrelevant guidance. Preserve pending approval and incomplete checks as actual states.

## Usage rules

- Use for changes to requirements, scope, architecture, interfaces, critical assumptions, acceptance thresholds, or evaluation protocols, and for necessary check deferrals.
- Ordinary implementation choices within approved scope need no new request; record them in the plan. Reference existing approval when it already explicitly covers the change.
- Complete required fields and explain N/A for conditional ones. Do not use an exception to conceal sensitive-information exposure, data damage, irreversible migration, or other material risks.

## 1. Request control — required

| Field | Record |
| --- | --- |
| TASK-ID / CR-ID / proposer | [Task identifier] / [Sequence] / [Name] |
| Type | [Scope/design/contract/acceptance change; check exception; select all that apply] |
| Request status | Draft / Pending approval / Approved / Rejected / Withdrawn / Implemented; initially Draft |
| Current design / directive versions | [Actual paths and versions] |
| Current implementation / team-main baseline | [Full SHA] / [Full SHA] |
| Workflow path / affected module owner | [Simplified/Standard/High risk] / [Name] |
| Live task state | TASK-ID row in `docs/governance/CURRENT_STATUS.md` |

## 2. Existing agreement and proposed change — required

| Item | Approved agreement and source | Proposed change | Reason and evidence |
| --- | --- | --- | --- |
| [Scope/contract/AC/check] | [Version, section, original condition] | [Specific difference] | [Discovery, blocker, or constraint] |

- Feasibility and cost of retaining the existing agreement: [Alternatives evaluated].
- Minimum necessary adjustment: [Why this scope resolves the issue].
- Scope that does not expand with this request: [Preserved boundaries].

## 3. Impact and stop boundaries — required

| Affected object | Behavior / compatibility / data / verification impact | Evidence invalidated or requiring renewal | Affected owner |
| --- | --- | --- | --- |
| [File, module, contract, or AC] | [Impact] | [Tests, AI review, human approval, and reasons] | [Name] |

- Steps paused pending approval: [Implementation or merge actions dependent on the new decision].
- Independent work that may continue under existing authority: [Scope and source; state none if applicable].
- Risks and rollback/stop triggers: [Specific signals and recovery methods].
- Documents to synchronize: [Actual TASK, design, directive, contract, plan, report, and other paths].

## 4. Check deferral and follow-up verification — required for a deferral

Exception approval is not a test pass. Keep the actual Not run / Blocked / Failed result in the original record and reference this request. Deferred checks remain incomplete work; the task cannot be Done until required follow-up verification is complete.

The approval must explicitly identify the permitted stage. Permission to continue implementation does not permit merging. An approval that expressly permits merging may defer only specified checks; it does not replace other gates or bypass a known blocking defect or failure of current acceptance criteria. Acceptance changes require the design/requirements change process and renewed verification, not merely a check exception.

| Deferred check / related AC | Actual result and blocker evidence | Deferral risk and available substitute evidence | Follow-up owner | Deadline and timezone | Execution prerequisites and command |
| --- | --- | --- | --- | --- | --- |
| [Check] | [Actual state/evidence] | [Residual risk; substitute evidence is not the original check] | [Name] | [Explicit time] | [Conditions/action] |

- Requested permitted stage: [Continue implementation only / Begin review / Permit merge, with explicit scope].
- Gates that still apply: [Required checks and human decisions].
- Response to an overdue or failed follow-up check: [Escalation owner, stop-release/fix/rollback triggers].

## 5. Explicit decision — required

| Decision-maker / role | Decision | Covered version and permitted scope | Conditions / expiry | Time and timezone | Traceable evidence |
| --- | --- | --- | --- | --- | --- |
| [Code Lead or authorized delegate] | Pending approval | [Pending] | [Pending] | [Pending] | [Actual record or pending] |
| [Affected module owner; remove only with an N/A reason] | Pending confirmation | [Interface/joint-behavior scope] | [Conditions] | [Pending] | [Actual record or pending] |

AI and the author may draft the request but may not invent human decisions. Approval covers only the identified versions and boundaries; it does not approve future implementation, tests, or the final PR.

## 6. Implementation and closure — fill after execution

| Action | Owner | Actual result / evidence | Incomplete items |
| --- | --- | --- | --- |
| Update design and implementation authority | [Name] | [Version/record or incomplete] | [Remaining work] |
| Rerun checks and supplement review | [Name] | [SHA and actual evidence or incomplete] | [Remaining work] |
| Complete deferred verification and close risks | [Name] | [Actual result or incomplete; explain N/A] | [Remaining work] |

Mark the request Implemented only when its conditions and required follow-up verification are complete. Whether the task is Done still depends on the full task completion definition.

Related templates: [TASK](TASK_TEMPLATE.md), [DESIGN](DESIGN_TEMPLATE.md), [PLAN](PLAN_TEMPLATE.md), [TEST_REPORT](TEST_REPORT_TEMPLATE.md), [STATUS](STATUS_TEMPLATE.md).

