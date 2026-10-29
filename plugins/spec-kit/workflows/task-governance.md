# TASKS / TASK workflow

This local plugin integrates the user's TASKS -> TASK -> spec/plan/tasks design.
Read this workflow before native commands. User instructions, applicable AGENTS
and project-specific rules govern the actual scope and existing layout.

| Authority | Responsibility |
| --- | --- |
| TASKS.md | Program source allocation, task register and dependencies |
| TASK.md | Task identity, executor, scope, native paths and owned interface agreements |
| spec.md | Requirements and acceptance criteria |
| plan.md | Technical blocks, dependencies and verification procedures |
| tasks.md | Sole implementation work list, progress and acceptance-to-evidence matrix |
| evidence/ | Observed runs; retain history and invalidate affected results after changes |

The plugin owns templates and tools. The target project owns every real record.
Default project locations are docs/code/Missions/PROGRAM-ID/TASKS.md,
docs/code/Missions/PROGRAM-ID/TASK-ID/TASK.md and docs/code/Missions/PROGRAM-ID/TASK-ID/. These paths
use one physical hierarchy: TASKS.md is at the program level; TASK.md, spec.md,
plan.md and tasks.md share each task directory. Existing migrated registrations
point to that directory. Never place project
records in the plugin source or cache or copy them there for installation.

Use `$speckit-register` to create a program/task or adopt existing records. For
an existing task, read its parent TASKS and TASK, then set
`SPECIFY_FEATURE_DIRECTORY` to the exact registered feature before calling
helpers. A feature pointer is not a task lock. Never create a second feature,
overwrite an existing artifact with a scaffold or renumber existing work/AC IDs
merely to adopt this workflow.

Resolve templates through scripts/powershell/resolve-template.ps1. The bundled
TASKS_TEMPLATE, TASK_TEMPLATE and EVIDENCE_TEMPLATE accompany TASK-native spec,
plan and tasks defaults. Project overrides and existing preset/extension
precedence still apply. Initialize only missing state with `$speckit-init`.

Implement and verify the blocks and connected boundaries required by the spec
and plan, then the applicable system journey. Checkboxes do not establish
acceptance: each required check needs current observations. Missing source
inputs remain PENDING_SOURCE and constrain only dependent work. Cross-module
agreements have one owning TASK and stable IF IDs/revisions; consumers link it.

Do not introduce separate authorization, implementation-checklist, review,
test-report, handoff or change-request cards. Resolve quality findings in the
native records. Ordinary progress updates tasks.md; material scope/interface
changes update TASKS/TASK and affected native artifacts and evidence. No
automatic commit, branch switch, issue creation or publication is authorized.
