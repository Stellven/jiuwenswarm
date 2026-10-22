# AI4R-001 / CR-01 — Fresh first-run scope

Maintainer: Xiaoyang. Recorded by Codex assistant from the user's explicit instruction.
Template: [CHANGE_REQUEST_TEMPLATE](../../code_sop/templates/CHANGE_REQUEST_TEMPLATE.md).

## 1. Request control — required

| Field | Record |
| --- | --- |
| TASK-ID / CR-ID / proposer | AI4R-001 / CR-01 / Xiaoyang |
| Type | Scope and acceptance change |
| Request status | Approved; documentation synchronization recorded below |
| Current design / directive versions | Native plan.md not created; write_code.md v0.3, updated to reference this decision; spec v0.1 replaced by v0.2 |
| Current implementation / team-main baseline | `dc9e6afdbacdc78a5d2eede3b4ab0dd1347e7483` / same SHA |
| Workflow path / affected module owner | High risk / Xiaoyang coordinates; module assignments remain pending before implementation |
| Live task state | AI4R-001 row in [CURRENT_STATUS](../../../governance/CURRENT_STATUS.md) |

## 2. Existing agreement and proposed change — required

| Item | Approved agreement and source | Proposed change | Reason and evidence |
| --- | --- | --- | --- |
| Legacy migration | Draft spec v0.1 FR-006/FR-008, User Story 3, Migration record entity, AC-05 and SC-004; these details were not separately approved | Spec v0.2 assumes fresh first use; remove legacy-data/configuration import and migration records; retire AC-05 without reusing its ID | Xiaoyang explicitly says migration records are unnecessary and users should open the modified software as a fresh application |
| New-profile persistence | Existing session/history requirements in FR-005 and AC-07 | Retain new conversations and projects across subsequent launches; no reset on every launch | Fresh first use does not remove normal saved-session behavior |

- Feasibility and cost of retaining the existing agreement: legacy migration would add conversion, compatibility, and recovery work the user does not require; no implementation estimate was measured.
- Minimum necessary adjustment: remove legacy import obligations while retaining first-run setup and runtime failure recovery.
- Scope that does not expand with this request: personal local accounts, Codex App Server, no key fallback, capability coverage, credential protection, and new-session persistence remain. No deletion of existing local data is authorized.

## 3. Impact and stop boundaries — required

| Affected object | Behavior / compatibility / data / verification impact | Evidence invalidated or requiring renewal | Affected owner |
| --- | --- | --- | --- |
| spec.md v0.2 | Fresh-start scenario replaces legacy conversion; migration entity removed; AC-05 retired | No acceptance execution existed; future design/tests must use the active v0.2 criteria | Xiaoyang |
| TASK, write_code, research, requirements checklist, TEST_REPORT | References and future checks synchronized; historical baseline results retained | Existing baseline tests do not prove fresh-start acceptance; no source/runtime change requiring their rerun | Xiaoyang |
| Future plan.md/tasks.md | Plan first-run setup and restart persistence, not legacy import | Concrete design and work-item approval still required | Xiaoyang |

- Steps paused pending approval: none for this explicitly authorized documentation change; production implementation still awaits its separate design/directive gate.
- Independent work that may continue under existing authority: setup, investigation, specification correction, and technical design drafting.
- Risks and rollback/stop triggers: if the proposed fresh-profile design would overwrite/delete existing data or clear new data on every launch, stop that approach and redesign it. This instruction authorizes neither behavior.
- Documents to synchronize: registered spec.md, research.md, checklists/requirements.md, TASK.md, write_code.md, and TEST_REPORT.md. No native plan/tasks exist yet.

## 4. Check deferral and follow-up verification — required for a deferral

N/A — this is an explicit requirements change, not a deferred migration test or an exception allowing a failed criterion to pass. AC-05 is retired; active acceptance checks remain Not run. All normal design, verification, and review gates still apply.

## 5. Explicit decision — required

| Decision-maker / role | Decision | Covered version and permitted scope | Conditions / expiry | Time and timezone | Traceable evidence |
| --- | --- | --- | --- | --- | --- |
| Xiaoyang / user and Code Lead | Approved scope change | Fresh first-run scope represented in spec v0.2; remove legacy migration requirement/record; no approval of future technical design or implementation | Applies to AI4R-001; other requirements unchanged | Current conversation; exact message timestamp not recorded; session timezone America/Toronto | User states migration records are unnecessary and the modified software should be treated as a fresh opening for users |
| Affected module owner | N/A at this documentation-only step | No implemented interface or module behavior is changed | Identify and confirm affected owners during design | N/A | Existing pending owner-confirmation requirement is preserved |

## 6. Implementation and closure — fill after execution

| Action | Owner | Actual result / evidence | Incomplete items |
| --- | --- | --- | --- |
| Update design and implementation authority | Xiaoyang; documentation by Codex assistant | spec v0.2 and dependent records updated to reference this decision; no production design approval invented | Technical design/work items remain future task work |
| Rerun checks and supplement review | Codex assistant | Document structure, links, and removal of legacy migration obligations checked; application source unchanged | Production acceptance and formal review remain unperformed |
| Complete deferred verification and close risks | Xiaoyang | N/A — no check deferral requested | Fresh-profile isolation and restart persistence must be addressed in design and acceptance |

This record captures the user's scope decision. It is not the removed runtime migration record, and it does not mark AI4R-001 complete.
