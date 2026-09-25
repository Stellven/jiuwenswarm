# Capsule Module AGENTS Draft

Status: template pending owner confirmation. Written on 2026-09-25; not installed as code-scope AGENTS instructions.
This file provides an independent editing entry point for Capsule. It does not establish that a module implementation or local rules already exist.
Adopt it using the [general local template](../../AGENTS_local.md), and use `AGENTS.md` after confirming the actual code scope.
Read, preserve, and integrate existing AGENTS files first. This draft must not overwrite constraints active along the directory path.

## Responsibility and Scope

- Module owner: `TODO`; backup: `TODO`; Lead: `TODO`.
- Capsule's business definition, owned behavior, and external commitments: `TODO`; the owner must establish these.
- Code directories, entry points, shared dependencies, and test scope: `TODO`.
- Out-of-scope build, execution, storage, permission, or evaluation behavior: `TODO`; assign according to the actual design.
- Do not infer from the Capsule name that it necessarily owns packaging, sandboxing, containers, or persistence.

## Confirm Paths and Meaning

The locally inspected version was `52abe68db2dd167485f6bd79d6e36e193d608e64`.
The limited inspection did not identify a confirmed implementation directory for the target Capsule module.
This does not establish that related capabilities are absent from the entire repository. Map them using the design, call chains, and owner confirmation.
Do not create a fictitious directory or fill in guessed commands and then present them as existing implementation facts.
After confirming actual paths, complete the scope, parent AGENTS references, and module responsibility mapping.

## Design and Upstream/Downstream Contracts

- Approved design, architecture version, and approval record: `TODO`.
- Upstream inputs, producers, and preconditions: `TODO`; downstream consumers and outputs: `TODO`.
- Register core entry points, function responsibilities, and shared dependencies in the [file map](../templates/FILE_MAP_TEMPLATE.md).
- Define data and interface conventions using the [contract template](../templates/CONTRACT_TEMPLATE.md), with owners on both sides.
- Resolve: What entity or capability is a Capsule, and how are its boundaries and lifecycle defined?
- Resolve: Who creates, reads, modifies, and retires it? Are there state or version compatibility requirements?
- Resolve: If it carries files or metadata, who validates references, integrity, and provenance?
- Resolve: If execution or storage is involved, who owns authorization, resource boundaries, and cleanup after failure?
- Resolve: Does it relate to the other three target modules, and which relationships need explicit contracts?

## Invariants and Change Boundaries

- Identity, structure, lifecycle, and compatibility invariants: `TODO: include only items applicable to the design`.
- Data integrity, recovery, and cleanup constraints: `TODO`; corresponding verification entry points: `TODO`.
- If existing data is involved, define compatibility, migration, and recovery before changing formats or processing rules.
- Do not hide undefined entity semantics, path conventions, or permission boundaries in implementation details.
- Do not change fields, states, or error behavior relied on by consumers without contract confirmation.

## Context Entry Points

- Overall workflow: [Code_SOP](../../Code_SOP.md); global draft: [AGENTS_global](../../AGENTS_global.md).
- Current TASK, `write_code.md`, plan, status, and responsibility mapping: `TODO: enter paths after adoption`.
- Use [DESIGN](../templates/DESIGN_TEMPLATE.md) for the module definition and approach. Record significant tradeoffs in an ADR.
- Formal implementation must be based on confirmed scope and approved design. State whether each unresolved item blocks progress.

## Verification Commands and Evidence

| Item | Information to complete |
| --- | --- |
| Working directory and environment | `TODO: directory, dependencies, sample data, and required services` |
| Targeted tests | `TODO: full commands based on actual test configuration` |
| Contract and integration verification | `TODO: producer/consumer versions, commands, and pass criteria` |
| Applicable migration or recovery checks | `TODO: test inputs, commands, expected results, and recovery verification` |

If implementation and tests have not been located, complete authorized investigation and record its results first. Do not claim module verification passed.
If commands, data, or dependencies are missing, record the blocker, owner, and deferred-verification plan. Do not guess executable entry points.
Run the required verification appropriate to approved behavior. Explain items that do not apply.
Use [TEST_REPORT](../templates/TEST_REPORT_TEMPLATE.md) for results, including implementation SHA, baseline, and unverified scope.

## Review and Handoff

AI uses [REVIEW](../templates/REVIEW_TEMPLATE.md). After the author addresses findings, the Lead reviews related functions and system impact.
For consumer or data changes, include owner confirmations, compatibility notes, and required recovery steps in the handoff.
Use [HANDOFF](../templates/HANDOFF_TEMPLATE.md) to record status, sample/artifact locations, reproduction commands, and unresolved items.
