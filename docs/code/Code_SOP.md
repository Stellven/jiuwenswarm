# AI4Research Code Collaboration SOP

Version: 1.0 draft · Document date: 2026-09-25 · Process owner: Code Team Lead [name to be assigned]

This SOP expands the original seven principles into a complete workflow covering requirements, design, implementation, testing, review, integration, handoff, and recovery. It applies to the team's work in `Stellven/jiuwenswarm`, including RSI, Router, Capsule, Verifier, and changes across module boundaries.

Start here: [Documentation index](code_sop/README.md) · [Adoption checklist](code_sop/ADOPTION_CHECKLIST.md) · [Git workflow](code_sop/GIT_WORKFLOW.md) · [Worked example](code_sop/WORKED_EXAMPLE.md)

This delivery is a process and template package. Actual owners, module paths, acceptance thresholds, and operating commands must be completed from project evidence. Writing this package does not approve the policy or configure GitHub branch protection or CI. Existing research materials may inform designs; implementation must reference an identified, approved design version.

## 1. The seven governing principles

1. **Approve the design before implementation.** Establish the objective, boundaries, interfaces, and acceptance criteria before writing the implementation. Obtain Code Team Lead approval. Small changes may use a short design record; material changes require an updated design and approval covering the new scope.
2. **Use one team integration branch and individual working branches.** Synchronize with the latest team integration branch before starting. Code entering it must undergo testing, AI review, and Code Team Lead review.
3. **Humans must understand the code.** Authors must explain every changed file. The Code Team Lead must understand affected functions, call chains, and system consequences. Authors remain accountable for AI-generated code.
4. **Maintain root and local AGENTS.md files as durable human–AI context.** The Code Team Lead owns the root instructions; module owners maintain local instructions. These provide reliable entry points to design, architecture, contracts, responsibilities, environment, status, plans, checklists, and tests.
5. **Implement against the Code Team Lead's write_code.md.** This document defines the task's implementation authorization and boundaries. Read it together with applicable AGENTS files and the approved design.
6. **Complete the agreed verification before requesting formal review.** Provide traceable evidence for the current implementation. A Draft PR may support early collaboration; it must not become Ready for review before the applicable gates are met.
7. **AI reviews first; the human lead decides afterward.** AI produces a structured review.md record. After the author addresses findings, the Code Team Lead makes the final decision for the current version. An AI recommendation is not merge approval.

## 2. Roles and accountability

Throughout this package, `Lead` and `Code Lead` mean `Code Team Lead`; an `owner` is a named accountable person. The `base` is the team integration baseline being compared, and the `head` is the proposed branch version.

| Role | Responsibilities | Primary records |
| --- | --- | --- |
| Code Team Lead | Approve design and implementation boundaries; understand the system architecture; review affected functions; decide merges and exceptions | Root AGENTS, architecture, write_code, human review |
| Module owner | Confirm responsibilities, interfaces, and caller impact; receive handoffs | Local AGENTS, contracts, module status and test entry points |
| Task author | Plan, implement, explain files, test, and address findings | TASK, plan, code map, checklist, test report, handoff |
| AI assistant / reviewer | Implement or review within authorization; identify evidence and coverage limits | Implementation records or the AI section of review |
| Affected module owners | Confirm cross-module contracts, compatibility, joint testing, and migration order | Contract and design/PR confirmations |
| Merge / release operator | Check the approved version, verify integration, and perform applicable release or recovery work | PR, status, release and rollback records |

A person may hold multiple execution roles, but an author cannot replace independent human review. If the Code Team Lead authors the change, appoint a qualified human delegate who understands the system; record their authority and review scope. Without an appropriate reviewer, the PR remains pending.

The [ownership register](code_sop/templates/OWNERSHIP_TEMPLATE.md) records names, backups, code paths, and interface relationships. Four personal branches do not imply a fixed one-to-one assignment of people to the four modules.

Authors must explain why each file changed, who calls it, how failures behave, and which checks establish correctness. The Code Team Lead must trace affected functions, state transitions, and failure paths from the relevant entry points. The [file and function map](code_sop/templates/FILE_MAP_TEMPLATE.md) records this understanding; checked boxes do not replace reading the code.

## 3. Branch policy

| Purpose | Branch |
| --- | --- |
| Team integration branch | `huawei_waterloo_main_branch` |
| Xiaoyang working branch | `huawei_waterloo_xiaoyang` |
| Saurav working branch | `huawei_waterloo_saurav` |
| Ramika working branch | `huawei_waterloo_ramika` |
| Muk working branch | `huawei_waterloo_muk` |

All five branches were pushed to and verified on `origin` on 2026-09-25 at initial commit `52abe68db2dd167485f6bd79d6e36e193d608e64`. This is an initialization snapshot, not a claim that the branches remain identical. Neither `origin/HEAD` nor the upstream default branch automatically denotes the team's integration branch.

- Set the base of team feature PRs explicitly to `huawei_waterloo_main_branch`. Integrate through PRs; do not push routine implementation directly to it or force-push shared branches.
- Synchronize persistent personal branches by merging the team integration branch. Use merge commits for PR integration by default to preserve shared history. Define the subsequent synchronization procedure before adopting another strategy.
- Keep one pending task on each persistent personal branch. For concurrent work, obtain Lead agreement to create short-lived task branches from the latest team baseline and associate each with an author and TASK-ID.
- Treat upstream updates as separate integration tasks with their own review and testing.
- Recheck the baseline before starting, requesting formal review, and merging. Preserve existing uncommitted work; do not substitute reset/clean for resolving an issue. See the [Git workflow](code_sop/GIT_WORKFLOW.md).

## 4. Documentation and sources of truth

Use [AGENTS_global.md](AGENTS_global.md) for root instructions and [AGENTS_local.md](AGENTS_local.md) for local instructions. During adoption, place them in the appropriate code scopes under the name `AGENTS.md`, integrating existing instructions. Module adaptations are available for [RSI](code_sop/modules/RSI_AGENTS.md), [Router](code_sop/modules/Router_AGENTS.md), [Capsule](code_sop/modules/Capsule_AGENTS.md), and [Verifier](code_sop/modules/Verifier_AGENTS.md).

| Information | Primary adopted location, relative to the code repository | Update trigger |
| --- | --- | --- |
| Durable rules and entry points | `AGENTS.md`, `<module-directory>/AGENTS.md` | Rules or paths change |
| Requirements and acceptance criteria | `docs/tasks/<TASK-ID>/TASK.md` | Task creation or requirement change |
| Design, architecture, and contracts | `docs/design/`, `docs/architecture/`, `docs/contracts/` | Approval before implementation; subsequent changes |
| Significant decisions and rationale | `docs/adr/` | A major choice is accepted or superseded |
| Implementation authorization | `docs/tasks/<TASK-ID>/write_code.md` | Design approval or scope changes |
| Steps, progress, and discoveries | `docs/exec-plans/<TASK-ID>.md` | Start, milestone, approach change, or handoff |
| File, function, and dependency map | `docs/code-map/FILE_MAP.md` | Responsibilities or key functions change |
| Checklists, tests, review, and handoff evidence | `docs/tasks/<TASK-ID>/` | Stage completion or evidence invalidation |
| Team status, environment, and testing methods | `docs/governance/` | Status, dependencies, commands, or strategy change |

AGENTS files link to these records rather than duplicating logs or weekly progress. Maintain each fact in one primary place and reference it elsewhere. Approval identities, dates, versions, and evidence must be real; `TODO`, `unconfirmed`, and `not run` are not completion states.

Read all AGENTS files along the path from the repository root to the file being edited. Local rules may add detail. If they conflict with root gates, task authorization, or the approved design, record the conflict and obtain Lead clarification; do not silently waive project requirements.

## 5. Scale the paperwork to the risk

| Path | Appropriate changes | Required records |
| --- | --- | --- |
| Simplified | Documentation corrections or isolated, low-risk fixes without interface, architecture, data, or critical behavior changes | TASK, short write_code, verification, and AI plus human review; plan, checklist, and report may be TASK sections |
| Standard | New behavior, substantial fixes, or extensions within a module | TASK, design, write_code, plan, checklist, test report, review, and PR; update maps and contracts as affected |
| High risk | Cross-module interfaces, architecture, breaking compatibility, migrations, model/evaluation methodology, critical performance, or environment changes | Standard records plus affected architecture/contracts, ADR, migration/recovery plan, owner confirmations, integration checks, and applicable evaluation |

The simplified path still requires approval of a short design before implementation; one explicit decision may cover both TASK and write_code. For documentation-only work, check links, instructions, and consistency instead of claiming runtime tests. Reference existing designs by version. Explain N/A entries; they must not hide required verification. Instantiate optional templates only when their triggering conditions apply.

## 6. End-to-end procedure

### Stage 0: Prepare and synchronize

Confirm the repository, origin, personal branch, and working-tree state. Read applicable AGENTS files, implementation, tests, and callers. Preserve other work, merge updates from the team integration branch into the current personal/task branch, and record the baseline SHA. Prepare the environment from ENVIRONMENT and run relevant baseline checks, recording existing failures. Complete the setup prerequisites in the [adoption checklist](code_sop/ADOPTION_CHECKLIST.md) before the first pilot task; complete the adoption record after that pilot validates the workflow.

Exit condition: owners, paths, baseline, environment, and known failures are identifiable.

### Stage 1: Define the task

Create a TASK-ID such as `AI4R-001`. Complete [TASK](code_sop/templates/TASK_TEMPLATE.md) with the problem, objectives, non-goals, risk path, owners, dependencies, and acceptance criteria. Assign stable identifiers such as `AC-01` to connect design, implementation, testing, and review. Define performance or quality methods and thresholds before implementation; if a baseline is missing, propose a measurement task first.

Investigate unclear requirements before committing to behavior. Exploratory work must have a stated authorization and purpose; it does not imply approval of the production implementation.

### Stage 2: Design and obtain approval

Use [DESIGN](code_sop/templates/DESIGN_TEMPLATE.md) to describe the proposal, alternatives, data flow, boundaries, and failure handling. Update [ARCHITECTURE](code_sop/templates/ARCHITECTURE_TEMPLATE.md), [CONTRACT](code_sop/templates/CONTRACT_TEMPLATE.md), and [ADR](code_sop/templates/ADR_TEMPLATE.md) when applicable.

The Code Team Lead approves a specific design version. Affected owners confirm cross-module changes. List unresolved questions and whether they block implementation. Before approval, perform only authorized exploration.

### Stage 3: Publish write_code and prepare the plan

The Lead publishes the task's `write_code.md` using [WRITE_CODE](code_sop/templates/WRITE_CODE_TEMPLATE.md), specifying allowed paths, excluded scope, interface versions, steps, checks, and stop conditions. The author uses [PLAN](code_sop/templates/PLAN_TEMPLATE.md) to identify file changes, dependencies, implementation steps, and acceptance checks within that authorization.

Authors or AI may draft the material; an actual human must confirm approval.

### Stage 4: Implement and maintain records

Implement in small steps on the assigned branch. Run relevant checks as steps become verifiable and update the [IMPLEMENTATION_CHECKLIST](code_sop/templates/IMPLEMENTATION_CHECKLIST_TEMPLATE.md) and code map. AI inputs must include applicable AGENTS, write_code, design/contract versions, the plan, baseline, and current scope.

Authors inspect generated code, dependencies, and data sources. Do not expand scope, lower thresholds, or delete failing tests to obtain a passing result. Keep credentials and restricted data out of code, logs, and external prompts.

When requirements, public interfaces, architecture, or critical assumptions change, create a [CHANGE_REQUEST](code_sop/templates/CHANGE_REQUEST_TEMPLATE.md). Pause dependent implementation while continuing independent, authorized work. Resume after approval of the revised scope. Ordinary implementation choices already within authorization do not require repeated approval.

### Stage 5: Self-review and verify

Inspect the final diff and explain every changed file. Use [TESTING](code_sop/templates/TESTING_TEMPLATE.md) to select proportionate unit, boundary/failure, contract, integration, regression, performance, or model evaluations. Prefer a reproducing regression test for bug fixes. Tests that simply mirror the implementation do not establish correctness.

Record commands, working directories, environment, implementation commit, baseline, results, and logs in [TEST_REPORT](code_sop/templates/TEST_REPORT_TEMPLATE.md). Distinguish passed, failed, skipped, not run, and blocked. Check whether a zero exit code hides failures or collected no relevant tests. State limits caused by missing LFS objects, services, data, credentials, or GPUs.

### Stage 6: Submit the PR and obtain AI review

Before formal review, merge updates from the team integration branch into the current personal/task branch, resolve conflicts, and revalidate the affected scope. Use the [PR template](code_sop/templates/PR_TEMPLATE.md) to explain the problem, behavior change, scope, design, verification, risks, and recovery. Check the PR base.

AI uses [REVIEW](code_sop/templates/REVIEW_TEMPLATE.md) to inspect the actual diff, callers, design, contracts, and evidence. Findings must identify files/functions, evidence, impact, a proposed remedy, and a verification method. State unreviewed areas. Authors fix findings or explain their disagreement with evidence; the Lead decides acceptance of significant risks. After implementation changes, rerun relevant checks and obtain AI follow-up review before final human review.

### Stage 7: Human review and the merge decision

The Code Team Lead reads affected functions and call chains, checking design, contracts, failure behavior, dependencies, and evidence credibility. Affected owners confirm joint behavior. Record approval, requested changes, or rejection with the covered version and rationale.

Ready to merge requires closed blocking findings, passing required checks or a formal deferral under Section 8, explicit risk disposition, and valid human approval for the current version. “AI checked it” does not establish human understanding.

### Stage 8: Verify integration and hand off

The operator checks the current PR head, integration base, evidence, and approval scope. If the baseline moved, reassess impact and complete the necessary checks and review. After merging, verify the actual merge commit through CI or the required smoke checks. On failure, stop release, choose a fix or recovery action, and create an [INCIDENT](code_sop/templates/INCIDENT_TEMPLATE.md) record.

Use [RELEASE_ROLLBACK](code_sop/templates/RELEASE_ROLLBACK_TEMPLATE.md) when the task includes a release. Update status, maps, and affected documentation; use [HANDOFF](code_sop/templates/HANDOFF_TEMPLATE.md) to transfer the work to its owner. Personal branches synchronize again before the next task. Mark Done only after post-merge verification and handoff are complete.

## 7. Evidence and version validity

Tests, AI review, and human approval must identify at least the implementation commit and integration baseline they cover. Checks of uncommitted implementation are work-in-progress evidence and cannot alone establish the final merge gate.

Committing a report creates a new SHA; the report need not contain its own SHA. It may reference the tested implementation commit, followed by commits containing only results or approval records. The PR must identify those later commits and verify that they do not change implementation, configuration, tests, contracts, or acceptance criteria. A Markdown change to a contract or gate can invalidate evidence.

| Later change | Required response |
| --- | --- |
| Results-only records; implementation, configuration, tests, contracts, and acceptance unchanged | Inspect the diff, state the scope, and reuse the applicable runtime evidence |
| Implementation, dependencies, configuration, tests, or contracts change | Rerun relevant checks; add AI review and human confirmation |
| New baseline merged or conflicts resolved | Inspect the resulting implementation, rerun affected integration/regression checks, and update review scope |
| Quality thresholds, dataset, or evaluation methodology changes | Follow design change control, reevaluate, and explain why previous conclusions no longer apply |

Unrelated documentation changes do not require repeating expensive full suites. Time pressure does not justify reporting unrun checks as passed.

## 8. Definition of Done and exceptions

Before merging, ensure traceable design and implementation authorization; author understanding of every changed file; truthful verification evidence; disposition of AI findings; current function-level human review; necessary cross-module confirmation, compatibility, and recovery information; and the correct PR base and scope.

Done additionally requires post-merge checks and deferred verification to be complete, documentation and status to be updated, and the owner to have received the handoff. Release tasks must also complete their agreed release checks. Local completion, opening a PR, or an AI recommendation is not Done.

Urgent fixes may use shorter design and planning records, but still need implementation boundaries, necessary verification, and an explicit human decision. When prerequisites prevent an individual check from completing promptly, the Lead may formally approve a deferral in CHANGE_REQUEST. State the permitted stage, reason, alternative evidence, risk, verification owner, deadline, and recovery trigger. Permission to continue implementation is not permission to merge; only an explicit deferral covering merge can satisfy that check's temporary disposition. Other gates remain applicable.

Keep the check's actual status as not run, blocked, or failed. A deferral cannot bypass a known blocking defect or failure of current acceptance criteria. A genuine requirement change must instead follow design change control, approval, and verification of the new criteria. If verification is still outstanding after merge, keep the task Merged or Blocked, never Done. Exceptions must not conceal credential exposure, data corruption, or irreversible migration risks.

## 9. Maintain the process

The Lead maintains this SOP and root rules; module owners maintain local rules and entry points. Process changes identify the reason, scope, effective version, and adoption steps. Preserve superseded designs and ADRs with links to their replacements.

Judge the process by earlier defect discovery, genuine human code understanding, handoffs that work without chat history, and reproducible verification—not by document count.
