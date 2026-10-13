# Feature Specification: DEVTOOLS-001 - Spec Kit Codex plugin
**TASK**: [DEVTOOLS-001](TASK.md)
**Parent TASKS**: [DEVTOOLS](../TASKS.md)
**Revision / date**: r3 / 2026-10-05
**Feature Branch**: ai4r_xiaoyang
**Input**: User maintenance request U01-U08; existing Code SOP v2 and Spec Kit 1.0.12
**Status**: Specified

## User Scenarios & Testing
### User Story 1 - Develop with a reusable plugin and clear document locations (Priority: P1)
The developer can find current process guidance, plugin-owned templates and real task records in clear locations, then invoke Spec Kit through a locally installed Codex plugin.
**Independent Test**: Codex discovers and installs the package; an isolated project resolves a bundled template and a project override, generates a feature and reads its native paths.
**Acceptance Scenarios**:
1. docs/code contains current development guidance and its subordinate Missions/ tree, with valid links to plugin-owned templates.
2. Plugin skills and helper scripts work from an installed plugin directory without project-local copies of vendor resources.
3. Task identities and contents survive the requested directory move; project rules, archived snapshots and unrelated edits remain preserved.

### Edge Cases
Installed-cache paths differ from the source path. Projects can have spaces in paths. Missing project overrides fall back to bundled templates. Existing plans and project initialization files must not be overwritten. Historical references to already-removed templates remain historical; this task does not restore removed workflows.

## Requirements
### Functional Requirements
- FR-001: Each class of development content has one explicit maintained location; real development-task records belong under docs/code/Missions/PROGRAM-ID/, with TASKS.md at program level and TASK.md/spec.md/plan.md/tasks.md together per task.
- FR-002: Package existing Spec Kit capabilities as a Codex plugin with version/license provenance and local marketplace installation.
- FR-003: Resolve scripts from the plugin and prefer project overrides; preserve explicit feature selection and existing native records.
- FR-004: Repair moved live links and preserve unrelated work and historical snapshots.
- FR-005: Bundle TASKS/TASK rules, a registration skill and reusable record/native templates in the plugin; commands resume existing registered project records without copying them into the package or creating parallel features.

### Key Entities
Plugin package, local marketplace, project constitution/overrides, task registry, feature artifacts and historical delivery snapshot.

## Success Criteria
### Measurable Outcomes
| AC ID | Source clause / FR / story | Observable criterion and threshold | Required verification level(s) |
| --- | --- | --- | --- |
| AC-001 | U01/U03/U04 / FR-001 / US1 | Current guides, plugin templates and archive have distinct ownership; fictional examples are removed; TASKS and all task/native files share the docs/code/Missions hierarchy; no duplicate active vendor installation | BLOCK |
| AC-002 | U02 / FR-002/003 / US1 | Native Codex discovery/install succeeds; helpers from a relocated package pass override, fallback, feature-generation and non-overwrite checks | BLOCK / BOUNDARY / SYSTEM |
| AC-003 | U01/U03 / FR-004 / US1 | No newly broken active local links; promoted reusable templates retain their contents; constitution, archive and unrelated work are preserved | BOUNDARY |
| AC-004 | U05/U06 / FR-005 / US1 | TASKS/TASK/evidence and native templates resolve from a relocated plugin; overrides still win; native skills use the integrated workflow; existing selected records stay intact; no real project records are packaged | BLOCK / BOUNDARY / SYSTEM |

## Scope and Assumptions
- Scope is developer tools/document organization; product code and M1 requirements are excluded.
- Consumed TASK agreements: None; no product boundary changes.
- Models/providers: N/A; no model calls are needed for packaging verification.
- Source version is the installed 1.0.12; no vendor upgrade is requested.
- New conversations load newly installed skills; the current conversation does not prove automatic UI discovery.
