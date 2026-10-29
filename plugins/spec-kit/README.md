# Spec Kit for Codex development

Local Codex adapter of [GitHub Spec Kit 1.0.12](https://github.com/github/spec-kit/tree/v1.0.12), under its MIT license. This is a maintained local package, not an official GitHub/OpenAI plugin release. Plugin version and upstream version are recorded separately in plugin.json and upstream.json.

## Package ownership

| Location | Purpose |
| --- | --- |
| skills/ | Spec Kit commands, project initialization and TASKS/TASK registration |
| scripts/powershell/ | Shared helper implementation; Windows PowerShell or PowerShell 7 |
| templates/ | Reusable TASKS/TASK/evidence/AGENTS templates and TASK-native spec/plan/tasks defaults |
| workflows/task-governance.md | Integrated TASKS -> TASK -> native-artifact rules |
| workflows/speckit/ | Upstream optional workflow assets; not automatically enabled |
| tests/ | Isolated helper/package verification |

Each project owns its .specify/memory/constitution.md, .specify/templates/overrides/, feature pointer/settings, task records and specs. Project overrides win over plugin defaults. Plugin initialization never overwrites existing rules or plans. No scripts/templates/skills are copied into project-local vendor directories.

The user's TASKS/TASK design is part of this local adapter, not an upstream Spec Kit feature. Read [the integrated workflow](workflows/task-governance.md). The plugin owns reusable templates and commands; the target repository owns all real TASKS/TASK records and native artifacts. Existing records are adopted through their registration links and stay in the project. This package contains no real project task or demonstration program. Project-specific overrides remain optional and take priority; shared defaults are maintained once here.

## Install

This repository exposes the package in `.agents/plugins/marketplace.json`, named `ai4research-dev`. From the repository root:

```powershell
codex plugin marketplace add . --json
codex plugin add spec-kit@ai4research-dev --json
codex plugin list --marketplace ai4research-dev --json
```

Start a new Codex conversation to load newly installed skills. The repository enables this package in `.codex/config.toml`. Codex manages its installation cache; edit this source package and reinstall/refresh with native plugin tooling after changes.

For another repository, register this repository as a local marketplace once using `codex plugin marketplace add <absolute-path-to-this-repository>`, then install the same plugin. Run `$speckit-init` in the target project if it has no `.specify/` state.

## Use

Use the discovered skill names: `$speckit-init`, `$speckit-register`, `$speckit-constitution`, `$speckit-specify`, `$speckit-clarify`, `$speckit-plan`, `$speckit-tasks`, `$speckit-analyze`, `$speckit-implement`, `$speckit-converge`, `$speckit-checklist` and `$speckit-taskstoissues`. A host may display them with the `spec-kit:` plugin namespace.

Each upstream skill has a short adapter context for locating bundled resources and following the caller's repository rules. Hooks, branch operations, issue creation, commits and publication still require the user's actual authorization. This package enables no automatic lifecycle hooks or external services.

Read the target repository's AGENTS.md and development workflow. Project-specific process guidance remains in that repository rather than in this reusable package.

## Validate

```powershell
python plugins/spec-kit/tests/test_plugin.py
```

Tests relocate the package to a temporary directory and execute real PowerShell helpers against temporary projects. They do not run product services or change current feature records.
