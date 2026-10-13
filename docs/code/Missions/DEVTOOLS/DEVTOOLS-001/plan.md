# Implementation Plan: DEVTOOLS-001 - Spec Kit Codex plugin
**TASK**: [TASK](TASK.md) | **Spec**: [r3](spec.md)
**Revision / date**: r3 / 2026-10-05 | **Branch**: ai4r_xiaoyang
**Input sources**: Current user request; Code SOP v2; OpenAI plugin packaging documentation; installed Spec Kit 1.0.12

## Summary
Move existing content into explicit locations. Bundle the existing upstream skills, scripts and core templates once in plugins/spec-kit. Adapt helper resolution to the package location while leaving project rules/overrides in .specify. Register and install with native Codex tooling.

## Technical Context
- Windows PowerShell, Python standard library, Git and the installed Codex CLI.
- No model/provider or new application dependency.
- Project storage: .specify/memory and .specify/templates/overrides; all real task/native records share docs/code/Missions task directories.
- Native plugin resources: plugins/spec-kit/; marketplace: .agents/plugins/marketplace.json.
- Performance constraints: N/A for document maintenance; observable checks are in spec.md.

## Constitution Check
TASKS/TASK/feature are linked. Native files own ACs, design and progress. No reviewer gate or parallel implementation card is introduced. Verification uses real helpers and native Codex commands; no product acceptance is inferred.

## Project Structure
TASKS.md lives at docs/code/Missions/PROGRAM-ID/. Each TASK-ID directory contains TASK.md, spec.md, plan.md, tasks.md and any native support/evidence files. The plugin owns reusable rules/templates/commands; .specify owns project-specific rules/settings. No fictional example or separate root specs tree remains.

## Blocks and Dependencies
| Block ID | Responsibility / AC references | Inputs, outputs, state invariants | Dependency block/TASK/IF references | Affected implementation paths |
| --- | --- | --- | --- | --- |
| B01 | Plugin adaptation / AC-002 | Existing 1.0.12 resources become a relocatable package; project overrides take priority | None | plugins/spec-kit/, .specify/ |
| B02 | Mission organization / AC-001/003/004 | Colocate registered records, preserve source/evidence bytes and repair links | None | docs/code/Missions, active navigation |
| B03 | Installation and integration / AC-002/003 | Native Codex manages discovery/cache; no hand-edited cache files | B01/B02 | .agents/plugins/marketplace.json, .codex/config.toml, native evidence |

## Interfaces and Technical Decisions
- Product agreements: N/A; the Codex manifest and existing template stack are external development contracts.
- Adapt the two core-template fallbacks in common.ps1 to bundled templates after project overrides/presets/extensions and existing legacy core files.
- Skills determine the physical package root from their loaded file path; source/cache paths are not hardcoded.
- Past compiled handbooks/ZIP/manifest/translations remain immutable snapshots, clearly labeled in the archive; no second active handbook is generated.
- Move native task histories beneath docs/code; rebase their navigation and repair incoming pointers. Preserve all non-path content, source-file bytes and prior recorded results; do not restore obsolete templates.

- Promote TASKS/TASK/evidence/AGENTS and the three reusable native templates into plugin/templates, removing duplicate active copies. Retain project override precedence. Add speckit-register and a shared TASK workflow used by every native skill. Reuse registered paths and existing specs; refresh the native plugin cache after validation.

## Verification Design
| V ID | Level | Block / IF / AC references | Fixture and dependency mode | Expected assertion / criterion source | Command + working directory or manual procedure | Required prerequisites / artifacts |
| --- | --- | --- | --- | --- | --- | --- |
| V01 | BLOCK / BOUNDARY | B01 / AC-002 | Temporary relocated package and project path with spaces; actual PowerShell helpers | Bundled fallback, override precedence, explicit feature paths, feature creation and non-overwrite pass | python plugins/spec-kit/tests/test_plugin.py from repository root | PowerShell and Python; temporary files only |
| V02 | BLOCK / BOUNDARY | B02 / AC-001/003 | Actual migrated files and pre-migration link/hash baseline | No new broken active links; distinct ownership; protected bytes unchanged | Python local-link/hash scan and git diff --check | Baseline hashes and missing-link inventory |
| V03 | SYSTEM | B03 / AC-002 | Actual Codex local marketplace and installed cache | Native discovery/install reports this plugin installed and enabled | codex plugin list --marketplace ai4research-dev --available --json; codex plugin add spec-kit@ai4research-dev --json | Package and marketplace present |

## System Candidate and Journeys
Working tree on the recorded base, plus installed local plugin. Record package identity, commands, environment, results and limits in evidence. New-chat UI activation remains a separate observation if unavailable during this session; CLI installation alone does not prove UI behavior.

## Unresolved Decisions and Impact
No unresolved scope choice. Preserve existing broken historical-template links rather than expand this task into restoration. Plugin installation may require a new conversation for skill discovery; report that limit.
