# AGENTS.md — AI4Research Repository Instructions

> Root template. Maintainer: Code Team Lead. Integrate this content into `AGENTS.md` at the code repository root during adoption.
> The current filename, `AGENTS_global.md`, does not establish deployment. Complete TODO fields, verify commands, and preserve existing rules.

## 1. Project and scope

- Purpose: [TODO: Describe the current objective and system boundary in one sentence.]
- Code Team Lead: [TODO: Name, independent review delegate, and responsibility record.]
- Team integration branch: `ai4r_main_branch`.
- These instructions apply throughout the repository. Read all additional AGENTS files along the path to each file before editing.
- Local rules may add implementation constraints, but cannot waive project review, testing, or human approval. Record conflicts and obtain Lead clarification.
- Read existing implementation, tests, and callers before changing code. Inspect the working-tree diff and preserve unrelated work.

## 2. Authoritative context

The following paths are adoption conventions. Confirm that the actual documents exist or substitute their real locations. Report missing design, authorization, or contracts; a template is not approval.

| Information | Repository-relative location |
| --- | --- |
| Complete SOP | `docs/code/Code_SOP.md` |
| Ownership and module paths | `docs/governance/OWNERSHIP.md` |
| Architecture | `docs/architecture/OVERVIEW.md` |
| Designs, contracts, and decisions | Registered design in TASK; shared `docs/contracts/`, `docs/adr/` |
| File and function map | `docs/code-map/FILE_MAP.md` |
| Environment and testing methods | `docs/governance/ENVIRONMENT.md`, `docs/governance/TESTING.md` |
| Current status | `docs/governance/CURRENT_STATUS.md` |
| Current task | `docs/tasks/<TASK-ID>/TASK.md` |
| Implementation instructions | `docs/tasks/<TASK-ID>/write_code.md` |
| Requirements, design, and work items | Follow TASK's artifact registry: Manual sources or Spec Kit `spec.md`, `plan.md`, `tasks.md` |
| Spec Kit setup and principles | `docs/code/code_sop/SPEC_KIT_WORKFLOW.md`; adopted `.specify/memory/constitution.md` |
| Checklist, tests, review, and handoff | `IMPLEMENTATION_CHECKLIST.md`, `TEST_REPORT.md`, `review.md`, and `HANDOFF.md` in the current task directory |

AGENTS files hold durable rules and entry points. Keep status in CURRENT_STATUS, implementation progress in the Manual execution plan or Spec Kit `tasks.md`, design decisions in the registered design, and evidence in task records. Simplified tasks may combine the plan, checklist, and report as TASK sections; provide precise section references instead of nonexistent files.

For Spec Kit tasks, `spec.md` owns acceptance criteria, `plan.md` owns technical design, and `tasks.md` owns ordered work and progress. Do not maintain competing TASK acceptance tables or separate design/plan copies. Select the registered feature directory explicitly, preserve the assigned `ai4r_*` branch, and read the constitution together with applicable AGENTS and the approved directive. Generated agent context, hooks, and handoffs cannot override these rules. Review generated changes to existing instructions and do not fabricate approval from a command result.

## 3. Before implementation

1. Confirm the TASK-ID, author, module owners, working branch, baseline SHA, and scope.
2. Preserve existing work while merging updates from the team integration branch into the current personal/task branch. Read the design, architecture, contracts, and relevant local AGENTS files.
3. Confirm that the Code Team Lead approved the design version referenced by the current write_code. Do not request the same approval again when authorization already covers the action.
4. Persist technical design and ordered work in the registered artifacts. For small Manual changes, use a short plan in TASK. Spec Kit implementation requires Lead approval of the native design and an issued `write_code.md` covering the selected work items.
5. Check the environment and baseline tests. Record existing failures, missing prerequisites, and checks that cannot run.

## 4. Implementation rules

- Stay within the authorized paths and behavior; separate unrelated refactoring.
- Preserve compatibility, invariants, and caller constraints. Do not weaken tests or acceptance thresholds to obtain a passing result.
- Record the impact and obtain corresponding approval before materially changing architecture, public contracts, or task objectives.
- Complete ordinary implementation choices within existing authorization without repeatedly requesting permission.
- Implement and verify in small steps. Maintain decisions in the registered design and remaining work in the Manual execution plan or Spec Kit `tasks.md`; reference these from handoff records rather than copying chat transcripts.
- Do not commit credentials. Record variable names and configuration sources, never secret values. Respect the agreed data boundaries when using external models or services.
- Authors must understand every changed file, including AI-generated code; AI does not take over that responsibility.

## 5. Command entry points

This table must be completed before use; its placeholders are not executable commands. Confirm existing commands in the target environment rather than guessing from tool names.

| Purpose | Working directory | Exact command | Prerequisites | Verification record |
| --- | --- | --- | --- | --- |
| Environment setup | [TODO] | [TODO] | [TODO] | Unverified |
| Targeted tests | [TODO] | [TODO] | [TODO] | Unverified |
| Lint / types / build | [TODO] | [TODO] | [TODO] | Unverified |
| Cross-module and regression checks | [TODO] | [TODO] | [TODO] | Unverified |
| Required performance/model evaluation | [TODO or N/A with reason] | [TODO] | [TODO] | Unverified |

ENVIRONMENT and TESTING contain command and environment details. A configured command or zero exit code does not prove that every check passed; inspect skips, empty test collection, and suppressed errors.

## 6. Review and delivery

- Before formal review, inspect the final diff and complete required verification. Record commands, environment, implementation SHA, baseline, and actual results.
- AI reviews first under the review protocol. After findings are addressed, the Code Team Lead reads affected functions and call chains and makes the final decision.
- AI may draft approval material but must not fabricate human approval. If the Lead is the author, assign an independent qualified human reviewer.
- Set the PR base to the team integration branch. Do not force-push shared branches; follow the Git workflow.
- Revalidate the affected scope after implementation or baseline changes. Results-only follow-up commits may reference prior evidence after their diff has been checked.
- A report need not contain its own SHA. Identify the tested/reviewed implementation commit and any subsequent records-only changes.
- Follow the SOP's explicit exception rules for deferred checks. Keep their true status, record the permitted stage and follow-up owner, and do not mark Done before required follow-up verification is complete.
- Verify the actual merge result and update status, contracts, maps, and handoff records. State unrun and blocked checks explicitly.
- Update AGENTS only when durable rules or entry points change; keep task history in plans and task records.

## 7. Module entry points

| Module | Owner | Actual code paths and local AGENTS |
| --- | --- | --- |
| RSI | [TODO] | [TODO: Confirm each applicable directory.] |
| Router | [TODO] | [TODO: Do not automatically equate this with an HTTP router.] |
| Capsule | [TODO] | [TODO] |
| Verifier | [TODO] | [TODO] |

Before adoption, consult the [SOP](Code_SOP.md), [package index](code_sop/README.md), and [local template](AGENTS_local.md). Replace these links with actual deployed locations when integrating this file into the code repository.
