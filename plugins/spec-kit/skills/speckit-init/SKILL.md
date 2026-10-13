---
name: speckit-init
description: Initialize project-owned Spec Kit state for this Codex plugin without copying vendor scripts or overwriting existing rules.
---

Resolve the plugin root as the directory two parent levels above the folder containing this SKILL.md.
Use its absolute path as the PowerShell variable `$specKitRoot`; do not assume
the source checkout or the installed cache location.

Run from the target project:

```powershell
& "$specKitRoot/scripts/powershell/init-project.ps1" -ProjectRoot (Get-Location).Path -Json
```

This creates only missing project directories, a constitution scaffold and a
feature-pointer ignore file. Preserve existing project files. Read AGENTS.md
and [the integrated TASK workflow](../../workflows/task-governance.md). Use
`$speckit-register` to create a program/task or adopt existing records. The
plugin supplies reusable TASKS/TASK and native templates. Populate a new constitution from actual user/project requirements
when requested; the scaffold is not a completed constitution.

For an existing project, verify its current overrides with the bundled
`scripts/powershell/resolve-template.ps1`; do not reinstall a project-local
vendor skill/script/template tree. Report created files and next native command.
