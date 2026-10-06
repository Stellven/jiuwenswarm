# M0 Spec Kit program

This directory contains the complete English coding-program framework for the supplied **M1 product**. M0 names this working program; it does not rename the PRD delivery phases. Begin at [TASKS.md](TASKS.md), then the chosen TASK and its colocated spec/plan/tasks.

The input PRD is [PRD - AI4Research.txt](<source/PRD - AI4Research.txt>); the input architecture is [build-package](source/build-package/README.md). [Source manifest](source-manifest.json) preserves identities; [source coverage](source-coverage.json) maps all numbered clauses; [registry](registry.json) supports validation. Architecture copies of capsules/glossary/guard-design include the two user-requested prose clarifications. Primary PRD and secondary packaged PRD are deliberately distinguished in TASKS.

This is preparation, not a product implementation. Required runtime checks are NOT_RUN, and absent upstream verifier source bodies/revision and runtime prerequisites remain explicit. No generated quality diagnostic or checked preparation item establishes scientific or product acceptance.

Start with M0-001 secured model bridge, M0-002 identity/configuration, M0-003 library and M0-005 persistence; define runner/contracts/guard together, then the bounded [TRIAL-1](M0-TRIAL-1/TASK.md) and full research pipeline. The [system TASK](M0-SYSTEM/TASK.md) owns integrated exits and PRD-required reports.

Select a task without changing branches:

```powershell
$env:SPECIFY_FEATURE_DIRECTORY = "docs/code/Missions/M0/M0-001"
$specKitRoot = "C:/Users/17982/.codex/plugins/cache/ai4research-dev/spec-kit/1.1.2"
& "$specKitRoot/scripts/powershell/check-prerequisites.ps1" -Json -RequireSpec -RequireTasks -IncludeTasks
```

Use the installed plugin skills `spec-kit:speckit-specify`, `spec-kit:speckit-plan`, `spec-kit:speckit-tasks`, `spec-kit:speckit-analyze` and, when implementation is requested, `spec-kit:speckit-implement`. Resolve the root from the actual installed skill in another environment. No vendor skills/scripts/templates are copied into M0. An exact feature selection is not a task lock; isolate concurrent feature-generation sessions.

Document validation:

```powershell
python docs/code/Missions/M0/tools/validate_framework.py --level BLOCK
python docs/code/Missions/M0/tools/validate_framework.py --level BOUNDARY
```

These validate source allocation, artifact/IF/work/check links and documentary consistency only. Plan commands for new product tests explicitly require their future test files/fixtures to be implemented first. Source snapshots, native code inspection and framework validation cannot replace real connected service or complete-system evidence.
