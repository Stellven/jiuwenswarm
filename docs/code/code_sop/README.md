# SOP Documentation Index

Use this package with [Code_SOP.md](../Code_SOP.md). Read the main workflow first, then copy the templates appropriate to the task's risk. All templates require completion; generating files does not approve a design, prove that tests passed, or configure remote governance.

## Where to Start

| What you need to do | Entry point |
| --- | --- |
| Adopt the workflow for the first time | [ADOPTION_CHECKLIST](ADOPTION_CHECKLIST.md) |
| Send the weekend kickoff and collect setup replies | [WEEKEND_KICKOFF](WEEKEND_KICKOFF.md) |
| Read the complete workflow and gates | [Main SOP](../Code_SOP.md) |
| Prepare branches, synchronize, open a PR, resolve conflicts, or revert | [GIT_WORKFLOW](GIT_WORKFLOW.md) |
| Assign a coding task to AI | [write_code protocol](write_code.md) |
| Ask AI to review changes | [review protocol](review.md) |
| Follow an example from task definition to handoff | [WORKED_EXAMPLE](WORKED_EXAMPLE.md) |
| Establish repository-wide AI context | [AGENTS_global](../AGENTS_global.md) |
| Establish local AI context | [AGENTS_local](../AGENTS_local.md) |

## Complete Template Catalog

All adoption locations are relative to the target code repository's root. Angle brackets indicate task, module, or version identifiers to replace. After copying a template, update package documentation links to the actual project locations. Use optional materials when their conditions apply; each task does not need a copy of every file.

| Template | Adoption location | When to use / Maintainer |
| --- | --- | --- |
| [KICKOFF_REPLY](templates/KICKOFF_REPLY_TEMPLATE.md) | `<your-name>_kickoff_reply.md`, sent in the kickoff thread | One short setup and proposed-task reply per teammate |
| [TASK](templates/TASK_TEMPLATE.md) | `docs/tasks/<TASK-ID>/TASK.md` | Every task; author |
| [DESIGN](templates/DESIGN_TEMPLATE.md) | `docs/design/<TASK-ID>.md` | Standard or high-risk design; author drafts, Lead approves |
| [ARCHITECTURE](templates/ARCHITECTURE_TEMPLATE.md) | `docs/architecture/OVERVIEW.md` | Architecture baseline or changes; Lead |
| [CONTRACT](templates/CONTRACT_TEMPLATE.md) | `docs/contracts/<contract>.md` | Boundary or interface changes; providers and consumers |
| [ADR](templates/ADR_TEMPLATE.md) | `docs/adr/<NNNN>-<slug>.md` | Significant tradeoffs; decision owner |
| [OWNERSHIP](templates/OWNERSHIP_TEMPLATE.md) | `docs/governance/OWNERSHIP.md` | Project-wide responsibilities; Lead and module owners |
| [FILE_MAP](templates/FILE_MAP_TEMPLATE.md) | `docs/code-map/FILE_MAP.md` | File responsibilities, functions, or call-chain changes; author and Lead |
| [ENVIRONMENT](templates/ENVIRONMENT_TEMPLATE.md) | `docs/governance/ENVIRONMENT.md` | Project environment and reproducibility; environment owner |
| [TESTING](templates/TESTING_TEMPLATE.md) | `docs/governance/TESTING.md` | Project verification methods and matrix; owners and Lead |
| [STATUS](templates/STATUS_TEMPLATE.md) | `docs/governance/CURRENT_STATUS.md` | Current project task status; authors and owners |
| [WRITE_CODE](templates/WRITE_CODE_TEMPLATE.md) | `docs/tasks/<TASK-ID>/write_code.md` | Each implementation authorization; Lead |
| [PLAN](templates/PLAN_TEMPLATE.md) | `docs/exec-plans/<TASK-ID>.md` | Nontrivial tasks; author |
| [IMPLEMENTATION_CHECKLIST](templates/IMPLEMENTATION_CHECKLIST_TEMPLATE.md) | `docs/tasks/<TASK-ID>/IMPLEMENTATION_CHECKLIST.md` | Implementation self-checks; author |
| [TEST_REPORT](templates/TEST_REPORT_TEMPLATE.md) | `docs/tasks/<TASK-ID>/TEST_REPORT.md` | Verification evidence; person running the checks |
| [REVIEW](templates/REVIEW_TEMPLATE.md) | `docs/tasks/<TASK-ID>/review.md` | AI and human review; AI, author, and Lead |
| [PR](templates/PR_TEMPLATE.md) | `.github/pull_request_template.md` | PR description template; Lead maintains, author completes |
| [HANDOFF](templates/HANDOFF_TEMPLATE.md) | `docs/tasks/<TASK-ID>/HANDOFF.md` | Pausing, changing owners, or completing a handoff; author and recipient |
| [CHANGE_REQUEST](templates/CHANGE_REQUEST_TEMPLATE.md) | `docs/tasks/<TASK-ID>/CHANGE_REQUEST-<NN>.md` | Scope or design changes, or requests to defer checks; requester and Lead |
| [RELEASE_ROLLBACK](templates/RELEASE_ROLLBACK_TEMPLATE.md) | `docs/releases/<VERSION>.md` | Releases or migrations; release owner |
| [INCIDENT](templates/INCIDENT_TEMPLATE.md) | `docs/incidents/<INCIDENT-ID>.md` | Failures after merging or during operation, and recovery; incident owner |

Adopt the global template as `AGENTS.md` at the repository root and local templates as `AGENTS.md` within their actual code subtrees. One logical module may span multiple physical subtrees. Multiple local files with explicit scopes can reference the same contract; do not assume each module has only one directory.

## Four Module Drafts

| Module | Independent entry point | Current purpose |
| --- | --- | --- |
| RSI | [RSI_AGENTS](modules/RSI_AGENTS.md) | Existing related paths are candidates; the owner must confirm the full scope |
| Router | [Router_AGENTS](modules/Router_AGENTS.md) | Do not automatically equate a similarly named HTTP router with the target module |
| Capsule | [Capsule_AGENTS](modules/Capsule_AGENTS.md) | Physical paths, contracts, and responsibilities require confirmation |
| Verifier | [Verifier_AGENTS](modules/Verifier_AGENTS.md) | Physical paths, contracts, and responsibilities require confirmation |

## Recommended Structure After Adoption

```text
<code-repository>/
  AGENTS.md
  <actual-module-subtree>/AGENTS.md
  .github/pull_request_template.md
  docs/
    code/                              # Published SOP package
      README.md
      Code_SOP.md
      AGENTS_global.md                  # Retained global template
      AGENTS_local.md                   # Retained local template
      code_sop/                        # Complete package; preserve internal relative paths
      AI4Research_Weekend_Kickoff_Pack.zip
    governance/                        # Working records created during adoption
      OWNERSHIP.md
      ENVIRONMENT.md
      TESTING.md
      CURRENT_STATUS.md
    architecture/OVERVIEW.md
    design/<TASK-ID>.md
    contracts/<contract>.md
    adr/<NNNN>-<slug>.md
    code-map/FILE_MAP.md
    exec-plans/<TASK-ID>.md
    tasks/<TASK-ID>/
      TASK.md
      write_code.md
      IMPLEMENTATION_CHECKLIST.md
      TEST_REPORT.md
      review.md
      HANDOFF.md
      CHANGE_REQUEST-<NN>.md           # Create only when a change is requested
    releases/<VERSION>.md              # Create only for a release
    incidents/<INCIDENT-ID>.md         # Create only for an incident
```

The SOP package is published under `docs/code/`. The remaining directories above describe proposed working records; publishing templates does not create or approve those records, install AGENTS instructions, or configure CI. Small tasks may combine the plan, checklist, and report into TASK sections. When no separate file exists, link to the relevant section rather than leaving a nonexistent entry point. Register and reference existing architecture, testing, or interface documents without duplicating the same facts.

## Completion and Status Rules

- `TODO` / `Pending confirmation`: reliable input is missing; assign a named owner to complete it.
- `N/A` / `Not applicable`: state the specific reason and obtain confirmation from the required reviewer when appropriate.
- `Not run` / `Blocked`: record the command, missing prerequisites, and recovery steps accurately.
- `Passed` / `Approved`: require evidence of the actual execution or human decision.
- `Template` / `Example`: cannot serve as execution evidence; do not prefill a real approval in an example.
- Bind evidence to the implementation commit and main-branch base. State the scope of later report commits to avoid a cycle of recording a report's own SHA.

The task's row in CURRENT_STATUS is the single summary of its current status; the plan retains detailed progress. To reproduce the work, start at TASK and follow its design, plan, report, review, and handoff references.
