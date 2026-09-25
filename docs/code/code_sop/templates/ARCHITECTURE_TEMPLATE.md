# Project Architecture Overview

> Suggested location: `docs/architecture/OVERVIEW.md`  
> Maintainer: Code Lead; module owners maintain their boundaries and dependency information.  
> After copying: verify directories, entry points, and module responsibilities; fill in placeholders and remove template instructions. Do not present examples, assumptions, or unresolved items as established architecture.

## When to use this template

- Establish a project overview when adopting the SOP. Update it when modules, responsibilities, dependency directions, execution modes, or cross-module data flows change.
- If a local implementation does not change these aspects, reference the applicable architecture version in the task rather than creating a new copy.
- Core fields are required. Conditional items may say N/A with a specific reason. Mark unverified facts as Pending confirmation, name an owner and a way to obtain evidence, and state whether they block the current task.
- Record the current architecture and clearly identified proposed changes. Reference design approvals and ADRs separately to avoid contradictory copies of approval status.

## 1. Version and evidence (required)

| Field | Value |
| --- | --- |
| Maintainer / most recent verification date | [Name] / [Date] |
| Code version verified | `huawei_waterloo_main_branch` at [Full SHA] |
| Current status | Not yet established / Verified / Partially verified, with scope |
| Repository entry points | [Actual paths to README, build configuration, and execution entry points] |
| Relevant current design | `docs/design/<TASK-ID>.md` |
| Decision record | `docs/adr/<NNNN>-<slug>.md`, or N/A: no separate ADR yet |

## 2. System purpose and boundaries (required)

- Problem addressed: [One-sentence responsibility].
- External users and calling systems: [Actual roles or systems].
- Inputs, processing, and outputs owned by the system: [Scope].
- Responsibilities outside the system: [Boundaries].
- Execution modes: [Verified CLI, service, batch, library, or other mode].

## 3. Module directories and responsibilities (required)

The following names are team-defined module names awaiting verification. Fill in paths and responsibilities from the actual repository. Mark a module as Proposed if it is not implemented. Explain inapplicable modules; do not invent directories or capabilities.

| Module | Actual directory / status | Primary responsibility | Outside scope | Owner / backup owner | Entry points and evidence | Module AGENTS |
| --- | --- | --- | --- | --- | --- | --- |
| RSI | [Pending verification] | [Pending confirmation] | [Pending confirmation] | [Unassigned] | [Path/symbol] | `<actual-module-directory>/AGENTS.md` |
| Router | [Pending verification] | [Pending confirmation] | [Pending confirmation] | [Unassigned] | [Path/symbol] | `<actual-module-directory>/AGENTS.md` |
| Capsule | [Pending verification] | [Pending confirmation] | [Pending confirmation] | [Unassigned] | [Path/symbol] | `<actual-module-directory>/AGENTS.md` |
| Verifier | [Pending verification] | [Pending confirmation] | [Pending confirmation] | [Unassigned] | [Path/symbol] | `<actual-module-directory>/AGENTS.md` |
| [Other actual module] | [Directory] | [Responsibility] | [Boundary] | [Name] | [Path/symbol] | [Path] |

`docs/governance/OWNERSHIP.md` is authoritative for assignments. Reference the same owners here to avoid conflicting records.

## 4. Dependency directions and data flows (required)

| Caller | Callee | Purpose | Contract path | Synchronous / asynchronous / batch | Failure handling owner |
| --- | --- | --- | --- | --- | --- |
| [Actual component] | [Actual component] | [Responsibility] | `docs/contracts/<contract>.md` | [Actual mode] | [Component and handling rule] |

- Allowed dependency directions: [Source and destination layers or modules].
- Prohibited dependencies and reasons: [Specific rules, or state that no additional restriction applies].
- Core flow: [Numbered inputs, processing, state changes, and outputs; add a consistent diagram if useful].
- Cross-module invariants: [Properties that must hold regardless of implementation details].

See [CONTRACT_TEMPLATE.md](CONTRACT_TEMPLATE.md). Diagrams explain the architecture; their names and relationships must agree with actual code and contracts.

## 5. State, data, and resources (required when applicable)

| Data / state / resource | Owner | Source and storage location | Lifecycle | Consistency / concurrency requirements | Recovery after failure |
| --- | --- | --- | --- | --- | --- |
| [Object] | [Module] | [Path/system; no secret values] | [Creation through disposal] | [Requirements] | [Method] |

Where applicable, explain format versions, migration, idempotency, cache invalidation, resource cleanup, and permission boundaries. Do not create rules for mechanisms that do not exist; explain N/A instead.

## 6. Environment and execution (required)

- Environment configuration and installation command sources: `docs/governance/ENVIRONMENT.md`.
- Main entry points and execution commands: [Verified commands and working directories; explicitly mark anything unverified].
- External dependencies: [Services, databases, models, runtimes, and necessary constraints, or None].
- Configuration sources and precedence: [Files, environment variables, and other sources; record key names only, never credentials].
- Build, test, and evaluation entry points: `docs/governance/TESTING.md`.

## 7. Quality attributes and architectural constraints (required; select applicable items)

| Attribute | Requirement and source | Architectural support | Verification location |
| --- | --- | --- | --- |
| [Applicable compatibility, performance, reliability, reproducibility, or other attribute] | [Metric or explicit condition] | [Mechanism and boundary] | [Design AC / test path] |

## 8. Current facts, proposed changes, and technical debt (required)

| Item | Type | Evidence of current state | Target / treatment | Owner | Task or ADR | Blocks current work? |
| --- | --- | --- | --- | --- | --- | --- |
| [Item, or None] | Pending verification / Known limit / Proposed change / Technical debt | [Code/test/record] | [Treatment] | [Name] | [Path] | [Yes/No and reason] |

## 9. Architecture change log (required when changes occur)

| Date | Change | Design / ADR | Code Lead approval evidence | Effective code SHA |
| --- | --- | --- | --- | --- |
| [Date] | [Boundary or structural change] | [Path and version] | [Actual record; pending approval must not be marked approved] | [Merged SHA, or Not yet effective] |

Architecture approval does not replace final code review. See [DESIGN_TEMPLATE.md](DESIGN_TEMPLATE.md), [ADR_TEMPLATE.md](ADR_TEMPLATE.md), and [FILE_MAP_TEMPLATE.md](FILE_MAP_TEMPLATE.md) for design, durable decisions, and file/function understanding records.
