# [Contract name]

> Suggested location: `docs/contracts/<contract>.md`  
> Maintainer: interface provider owner; consumer owners help verify the contract. Code Lead approves contract changes.  
> After copying: create one document per stable boundary, fill in placeholders, and remove inapplicable examples and template instructions. Do not create a separate contract document for every private helper function.

## When to use this template

- Create or update a contract for a new or changed cross-module API, public function/class, event, file/message format, persistence schema, or external integration boundary.
- For internal implementation changes that preserve the contract, reference the existing contract and unchanged boundaries in the task rather than copying this document.
- Required fields need explicit content. Conditional fields may say N/A with a reason. Mark uncertain semantics as Pending confirmation with an owner; resolve and approve them before implementing code that depends on them.
- This document defines the behavior agreement. Examples and tests are verification material and cannot override conflicting contract text. Resolve inconsistencies in the contract and design first.

## 1. Contract control (required)

| Field | Value |
| --- | --- |
| Contract identifier / document version | [Name] / [Version] |
| Status | Draft / Pending approval / Approved but not effective / Effective / Deprecated |
| Provider / owner | [Actual module and owner] |
| Consumers / owners | [Actual callers and owners] |
| Code entry point | [File path and function/class/endpoint/message name] |
| Design / ADR | `docs/design/<TASK-ID>.md` / [Applicable ADR or N/A] |
| Verified code SHA | [Full SHA, or Not implemented] |
| Compatibility classification | Compatible addition / Compatible extension / Breaking change / Unchanged |

## 2. Responsibility and preconditions (required)

- Behavior provided: [Responsibility guaranteed by the interface].
- Caller preconditions: [State, permissions, ordering, or input requirements].
- Provider guarantees: [Results, invariants, and state changes].
- Non-guarantees: [Behavior that is not guaranteed and callers need to understand].

## 3. Inputs (required)

| Field / parameter | Type / schema | Required / default | Units, range, and constraints | Missing / null / invalid handling |
| --- | --- | --- | --- | --- |
| [Name] | [Exact type] | [Requirement] | [Constraints] | [Handling] |

Write No input parameters if there are none. Where applicable, specify character encoding, time zones, path resolution, ordering, floating-point precision, and unknown-field policy. Explain inapplicable items.

## 4. Outputs and side effects (required)

| Field / return value | Type / schema | Meaning and constraints | Behavior when no result exists |
| --- | --- | --- | --- |
| [Name] | [Exact type] | [Semantics and invariants] | [Explicit behavior] |

- Side effects: [Files, databases, caches, processes, network requests, or state changes, or None].
- Ordering and determinism: [Ordering guarantees and configuration of random behavior].
- Resource ownership: [Who closes, releases, or cleans up resources, or N/A].

## 5. Error and failure semantics (required)

| Error condition | Representation / type / code | Observable result and side effects already incurred | Retry allowed and conditions | Caller responsibility |
| --- | --- | --- | --- | --- |
| [Condition] | [Actual representation] | [Result] | [Conditions or reason retries are prohibited] | [Action] |

Specify timeouts, cancellation, partial success, repeated calls, idempotency keys, concurrency, reentrancy, and retry limits only when applicable. Do not assume the interface supports them.

## 6. Compatibility, versions, and migration (required)

- Version currently in use: [Version or First introduction].
- Differences from existing behavior: [List each difference, or explicitly state None].
- Affected consumers: [Complete known list and verification evidence].
- Migration steps and executors: [Required for breaking changes; compatible changes may use N/A with a reason].
- Activation conditions and rollback: [When to switch and how to restore; documentation-only verification may use N/A].
- Deprecation plan: [Date, communication, and replacement interface when applicable; otherwise N/A].

## 7. Examples and executable verification (required)

Provide a minimal valid call and output in the actual format, plus at least one relevant boundary or error scenario. Use shareable, non-sensitive example data. Mark examples as Expected example if the interface is not implemented yet.

| ID | Input / initial state | Expected output / error / state | Test path and test name | Design acceptance criterion |
| --- | --- | --- | --- | --- |
| CT-01 | [Normal scenario] | [Expected behavior] | [Actual test or To be added] | [AC-ID] |
| CT-02 | [Boundary or error scenario] | [Expected behavior] | [Actual test or To be added] | [AC-ID] |

Record actual commands, environment, code SHA, and pass/fail results in `docs/tasks/<TASK-ID>/TEST_REPORT.md`. Expected results here do not mean tests have run.

## 8. Contract approval and activation (required)

| Document version | Decision-maker / role | Decision and scope | Time and time zone | Evidence location | Effective SHA |
| --- | --- | --- | --- | --- | --- |
| [Version] | [Code Lead] | Pending approval | [Pending] | [Actual approval record or Pending] | [Not yet effective] |
| [Version] | [Consumer owner; explain if there is no separate consumer] | [Understanding confirmed / Pending; does not replace Lead approval] | [Actual time] | [Record] | [SHA or Not yet effective] |

## 9. Change log (required when changes occur)

| Version | Behavior change | Compatibility impact | Design / ADR | Renewed approval required? |
| --- | --- | --- | --- | --- |
| [Version] | [Change] | [Impact] | [Path] | [Yes/No and reason] |

Related templates: [DESIGN_TEMPLATE.md](DESIGN_TEMPLATE.md), [ARCHITECTURE_TEMPLATE.md](ARCHITECTURE_TEMPLATE.md), [ADR_TEMPLATE.md](ADR_TEMPLATE.md).
