# RSI Module AGENTS Draft

Status: template pending owner confirmation. Written on 2026-09-25; not installed as code-scope AGENTS instructions.
This file is an independent editing entry point. Having AGENTS in its name does not make it an active instruction file for a code directory.
Before adoption, complete it using the [general local template](../../AGENTS_local.md), and have the Lead and owner confirm its scope.
Use `AGENTS.md` only in confirmed code directories. Preserve and integrate existing local AGENTS files rather than overwriting them.

## Responsibility and Scope

- Module owner: `TODO`; backup: `TODO`; Lead: `TODO`.
- Definition, owned behavior, and delivery boundaries of the target RSI module: `TODO`; directory names alone do not establish them.
- Actual code scope: `TODO`; test scope: `TODO`; maintenance across directories: `TODO`.
- Out-of-scope behavior, shared capabilities, and their owners: `TODO`; confirm jointly with the relevant owners.
- Do not independently change another module's contracts, acceptance criteria, or global rules. Obtain the corresponding authorization first.

## Observed Candidate Paths

The following came from read-only inspection of local repository commit `52abe68db2dd167485f6bd79d6e36e193d608e64`.
They establish that similarly named implementations exist, but do not establish that all belong to the team's target RSI scope.

- `jiuwenswarm/agents/harness/common/rsi/`: candidate shared RSI implementation directory.
- `jiuwenswarm/server/rsi/`: candidate server entry-point directory.
- `jiuwenswarm/channels/web/frontend/src/features/rsi/`: candidate frontend directory.
- `tests/unit_tests/rsi/`: candidate test directory; inspect coverage of each target behavior.
- The candidate frontend path already has parent AGENTS files. Read and preserve their rules before adoption.

## Design and Upstream/Downstream Contracts

- Approved design and version: `TODO`; architecture entry point: `TODO`; approval record: `TODO`.
- Upstream callers and input contracts: `TODO`; downstream dependencies and output contracts: `TODO`.
- Register key entry points, function responsibilities, and call chains in the [file map](../templates/FILE_MAP_TEMPLATE.md).
- Define interface fields, error semantics, states, and compatibility requirements using the [contract template](../templates/CONTRACT_TEMPLATE.md).
- Resolve: Which steps does the target RSI cover, and who owns starting, stopping, and recovery?
- Resolve: How do inputs, artifacts, states, and evaluation results relate, and where is each authoritative source?
- Resolve: If external models or evaluations are involved, who owns data versions, budgets, randomness, and reproducibility?
- Resolve: Does RSI interact with Router, Capsule, or Verifier? If so, how do both owners confirm the boundaries?

## Invariants and Change Boundaries

- Business invariants: `TODO`; state-transition and recovery constraints: `TODO`; corresponding tests: `TODO`.
- Do not assume the questions above already have settled answers or silently define public contracts through implementation.
- For evaluations, do not manufacture passing results by deleting failed samples, changing thresholds, or mixing data versions.
- When call chains, states, or artifact formats change, update the design, consumer confirmations, and regression scope together.

## Context Entry Points

- Overall workflow: [Code_SOP](../../Code_SOP.md); global rule draft: [AGENTS_global](../../AGENTS_global.md).
- Current TASK, `write_code.md`, plan, and status: `TODO: enter actual relative paths after adoption`.
- Use [DESIGN](../templates/DESIGN_TEMPLATE.md) for design drafts. Keep process records in task documents.
- Before implementation, confirm the owner, paths, approved versions, permitted change scope, and required environment.

## Verification Commands and Evidence

| Item | Information to complete |
| --- | --- |
| Working directory and environment | `TODO: repository-relative directory, operating system, dependencies, and data versions` |
| Targeted tests | `TODO: confirm the full command and test selection against actual configuration` |
| Contracts, integration, and required evaluations | `TODO: commands, external dependencies, baselines, and acceptance thresholds` |
| Required checks | `TODO: formatting, static checks, and verification of affected frontend behavior` |

If commands are missing, inspect configuration and existing tests first, then have the owner confirm executable checks. Do not guess script names.
If environment, data, or services are missing, record the blocker, alternative checks, and owner for deferred verification. Do not mark unrun checks as passed.
Use [TEST_REPORT](../templates/TEST_REPORT_TEMPLATE.md) for results, referencing the implementation SHA and team main-branch baseline.

## Review and Handoff

The author explains each changed file. AI reviews using [REVIEW](../templates/REVIEW_TEMPLATE.md), followed by the Lead's review of key functions.
Changes across directories or modules require confirmation from affected owners. Later implementation changes require updated evidence for the affected scope.
Use [HANDOFF](../templates/HANDOFF_TEMPLATE.md) to transfer status, reproducible commands, artifact locations, unresolved items, and recovery entry points.
