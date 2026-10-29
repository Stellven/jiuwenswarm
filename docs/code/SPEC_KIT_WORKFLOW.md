# Spec Kit workflow for TASKS / TASK
## 1. Tool and task identity
The [Codex development plugin](../../plugins/spec-kit/README.md) bundles the existing Spec Kit 1.0.12 resources. This is a local adapter, with no upstream upgrade. Previous project-local installation facts remain historical in docs/governance/ENVIRONMENT.md and the delivery archive.

Install the plugin through the repository's marketplace, from the repository root:
```powershell
codex plugin marketplace add . --json
codex plugin add spec-kit@ai4research-dev --json
codex plugin list --marketplace ai4research-dev --json
```

Start a new Codex conversation to discover the installed skills. The project enables the package in .codex/config.toml. For a new project, `$speckit-init` creates missing project state without copying vendor resources or overwriting existing rules.

One plugin installation serves many projects and feature directories. Each project retains its constitution and optional overrides. Each program is under docs/code/Missions/PROGRAM-ID/; TASK.md, spec.md, plan.md and tasks.md share each task directory. Start from TASKS -> TASK, never from a guessed branch name.

Before native commands, select the exact registered directory:
```powershell
$env:SPECIFY_FEATURE_DIRECTORY = 'docs/code/Missions/M1/M1-001'
git status --short --branch
```
Replace the example with the actual TASK path. Environment selection has priority over the local .specify/feature.json pointer. Feature selection is not a branch switch. Do not run two feature-generating sessions in one checkout concurrently; use isolated checkouts for concurrent task work.

## 2. Project templates
The local resolver gives .specify/templates/overrides/ priority over installed templates. The plugin supplies TASKS_TEMPLATE, TASK_TEMPLATE, EVIDENCE_TEMPLATE and TASK-native spec/plan/tasks defaults in plugins/spec-kit/templates; no shared copy remains in project overrides.

Use resolved plugin defaults or intentional project overrides rather than copying old DESIGN/PLAN templates. Shared core templates and scripts live only in the plugin; its resolver preserves project override priority. A plugin refresh must preserve and re-check the project overrides.

Read-only resolver check from the repository root:
```powershell
$specKitRoot = Join-Path (Get-Location).Path 'plugins/spec-kit'
& "$specKitRoot/scripts/powershell/resolve-template.ps1" spec-template -Json
& "$specKitRoot/scripts/powershell/resolve-template.ps1" plan-template -Json
& "$specKitRoot/scripts/powershell/resolve-template.ps1" tasks-template -Json
```

This manual check uses the source package in this repository. Installed skills resolve their own physical package root, so they also work from Codex's cache. They do not guess a repository-relative vendor script path.

## 3. Native command sequence
| Command | Inputs and output | Project requirement |
| --- | --- | --- |
| $speckit-register | User request or existing records -> TASKS/TASK registration | Keep all four task files together; preserve existing work |
| $speckit-specify | Allocated PRD clauses -> native spec.md | Preserve source locators, AC IDs and required verification |
| $speckit-clarify | Unresolved spec inputs -> clarified spec | Ask only about real missing information; independent preparation can continue |
| $speckit-plan | Spec and TASK agreements -> native plan.md | Define blocks, dependencies and verification procedures |
| $speckit-tasks | Spec and plan -> native tasks.md | Include verification work and the AC/block/check/evidence matrix |
| $speckit-analyze | Cross-artifact consistency findings | Diagnostic only; resolve issues in authoritative artifacts |
| $speckit-implement | Ordered work -> code, checks and evidence | Follow block dependencies and update the same native records |
| $speckit-converge | Optional further gap detection | New findings become native work items within the TASK scope |

The $speckit command names above are invocation names, not PowerShell executables. Use the installed plugin's discovered skills; a host may show a `spec-kit:` namespace.

Spec Kit's built-in requirements checklist is a generated specification diagnostic. It is not the removed implementation checklist. Do not add a custom checklist workflow, reviewer assignment, separate authorization card or human-review gate. Resolve diagnostic findings in spec/plan/tasks; missing definitions constrain dependent work, not unrelated preparation.

The upstream implementation skill may suggest pausing on checklist markers or committing work. The user's v2 instruction explicitly removes the parallel gating process. Include the project instruction below when invoking native skills. These instructions take precedence over upstream defaults. The adapter changes resource paths and supplies project-governance context; upstream provenance is recorded in the plugin.

## 4. Reusable invocation context
```text
Work under Code SOP v2. TASK: <exact path>; parent TASKS: <exact path>;
feature directory: <exact registered path>. Read its registered source clauses,
TASK interface agreements and project native overrides.
Use spec.md for ACs, plan.md for blocks/procedures and tasks.md for all work
and AC-to-evidence mapping. Required block/boundary/system verification is
explicitly requested. Generated quality findings are diagnostic: resolve
them in those files; do not add an implementation checklist, reviewer gate,
write_code card, test-report card or handoff card.
Respect the user's current action scope and no-commit/no-push instructions.
```

## 5. Large PRDs and generated support files
TASKS covers the complete source. Each task receives its assigned source clauses, relevant global constraints, architecture views and provider/consumer agreements. A summary alone is insufficient. Verify that every AC has a source and every allocated clause has AC coverage.

Research, data-model, quickstart and generated schema files are optional support. Normative cross-module behavior stays in the owning TASK. Generated contracts/ files carry the IF revision they implement.

After generation, verify required sections and matrix columns. Regenerating tasks.md must preserve completed work and evidence or explicitly migrate them; do not overwrite run history.

## 6. Resuming and blocked inputs
Resume through TASKS -> TASK -> selected feature -> native tasks.md next action. Read the matrix and unresolved dependencies, not a second status report.

PENDING_SOURCE is allowed while the future PRD/architecture is being written. Do not fabricate models, contracts or thresholds to complete a template. Block only work whose correctness depends on the missing input.

## 7. Hooks and external actions
Inspect actual hooks before execution. This process does not enable automatic branch/commit/PR extensions. No generated hook or recommendation overrides a user instruction. Commit, push, merge, messaging and deployment follow the user's action scope, not a checklist result.
