---
name: speckit-register
description: Create a TASKS program register and TASK entry, or adopt existing project task records into the integrated TASKS/TASK Spec Kit workflow.
---

Resolve `$specKitRoot` to the absolute directory two parent levels above this
skill's folder. Read [the TASK workflow](../../workflows/task-governance.md),
applicable project AGENTS and existing records before writing. Run helpers from
the target project; initialize missing .specify state with `$speckit-init`.

For an existing TASK, reuse its parent register and exact native feature path.
Check that its registration and links agree. Repair only missing or inconsistent
linkage needed for the request; preserve scope, IDs, completed work and evidence.
Do not copy live project files into the plugin, move valid existing records,
generate a parallel registry/feature or replace their contents with templates.

For a new program/task:
1. Derive the program/task IDs, bounded scope and source allocation from the
   request and existing register. Use the project layout; defaults are
   docs/code/Missions/PROGRAM-ID/TASKS.md and PROGRAM-ID/TASK-ID/TASK.md.
2. Resolve TASKS_TEMPLATE and TASK_TEMPLATE with the bundled resolver and create
   only missing records. Fill identity, scope, dependencies and exact links;
   unresolved source inputs remain explicit. Add the task to the parent's
   register and source coverage without duplicating progress checkboxes.
3. Register the TASK-ID directory itself as the feature directory. Keep TASK.md,
   spec.md, plan.md and tasks.md together there. Link TASK to
   spec.md, plan.md, tasks.md and evidence/ and link native artifacts back to
   TASK/parent. Preserve existing native files. Create absent native artifacts
   when their corresponding specify/plan/tasks phase is requested, using the
   active resolved templates rather than inventing parallel documents.
4. Select that exact feature for subsequent native commands:

```powershell
& "$specKitRoot/scripts/powershell/resolve-template.ps1" TASKS_TEMPLATE -Json
& "$specKitRoot/scripts/powershell/resolve-template.ps1" TASK_TEMPLATE -Json
$env:SPECIFY_FEATURE_DIRECTORY = '<exact path registered in TASK.md>'
```

Return the program register, TASK and selected feature paths, plus the next
required native action. Report unresolved conditions without inventing product
requirements or claiming acceptance from scaffolds.
