# Router Module AGENTS Draft

Status: template pending owner confirmation. Written on 2026-09-25; not installed as code-scope AGENTS instructions.
This file is an independent editing entry point, not an active local instruction file for the target code directory.
Use the [general local template](../../AGENTS_local.md) when adopting it, and name it `AGENTS.md` after confirming its scope.
If the target path already has AGENTS, integrate lasting rules and preserve existing constraints rather than overwriting the file.

## Responsibility and Scope

- Module owner: `TODO`; backup: `TODO`; Lead: `TODO`.
- Router's business meaning and owned behavior: `TODO`; confirm with the owner and design lead.
- Actual code directories, entry points, and test scope: `TODO`; responsibility for shared files: `TODO`.
- Decisions, execution, storage, or evaluation outside its scope: `TODO`; do not assign responsibilities based on the name alone.
- Do not interpret responsibility for routing as authorization to change all callers or other module contracts.

## Confirm Names and Paths

The locally inspected version was `52abe68db2dd167485f6bd79d6e36e193d608e64`.
Existing paths include `jiuwenswarm/server/front/router.py` and `jiuwenswarm/extensions/agentos/agentos_router/`.
These are leads to similarly named or related implementations; they are not confirmed mappings to this SOP's target Router module.
Verify the target directory against the approved design, callers, and owner responsibilities rather than assigning it by name.
After confirmation, record the actual mapping and parent AGENTS files, and remove candidate notes that do not apply.

## Design and Upstream/Downstream Contracts

- Approved design, architecture version, and approval record: `TODO`.
- Upstream callers, input boundaries, and preconditions: `TODO`; downstream targets and output conventions: `TODO`.
- Register public functions and call chains in the [file map](../templates/FILE_MAP_TEMPLATE.md).
- Record contract versions and owners on both sides using the [contract template](../templates/CONTRACT_TEMPLATE.md).
- Resolve: What does Router assign, and how are available targets declared and validated?
- Resolve: Do configuration, policy, or models determine selection, and how is the active rule version recorded?
- Resolve: What happens when there is no matching target, multiple candidates, or an unavailable target?
- Resolve: Are retry and fallback allowed, and which party handles possible duplicate execution?
- Resolve: How can callers trace routing results, and must sensitive inputs be redacted?

## Invariants and Change Boundaries

- Input validity, selection constraints, and output consistency: `TODO: complete each applicable item from the design`.
- Error, timeout, cancellation, and concurrency constraints: `TODO`; performance requirements and measurement method: `TODO`.
- Changes to selection, fallback, or retry semantics require contract updates and confirmation from affected owners.
- Do not assume a target always exists, silently convert exceptions to success, or weaken acceptance requirements.
- Similarly named infrastructure files do not automatically fall within this module's authorized scope.

## Context Entry Points

- Overall workflow: [Code_SOP](../../Code_SOP.md); global draft: [AGENTS_global](../../AGENTS_global.md).
- Current TASK, `write_code.md`, plan, status, and responsibility mapping: `TODO: enter actual relative paths`.
- Use [DESIGN](../templates/DESIGN_TEMPLATE.md) for the approach and boundaries. Keep task progress in the plan.
- Before implementation, confirm approved versions and permitted directories. Questions in this template do not substitute for design decisions.

## Verification Commands and Evidence

| Item | Information to complete |
| --- | --- |
| Working directory and environment | `TODO: directory, operating system, dependencies, and required services` |
| Targeted tests | `TODO: full commands from actual configuration` |
| Contract and integration verification | `TODO: upstream/downstream versions, commands, and acceptance criteria` |
| Failure and performance checks | `TODO: applicable failure scenarios, baselines, and measurement commands` |

Based on the approved design, cover normal selection and applicable boundary and failure cases. Do not assume mechanisms that do not exist.
If commands are missing, inspect configuration and existing tests, then obtain owner confirmation. Do not invent entries such as `test:router`.
If services or credentials are missing, record the blocker and deferred-verification owner, and leave required gates incomplete.
Use [TEST_REPORT](../templates/TEST_REPORT_TEMPLATE.md) to record implementation SHA, baseline, commands, and actual results.

## Review and Handoff

The author reviews each file. AI uses [REVIEW](../templates/REVIEW_TEMPLATE.md), and the Lead checks key functions and call chains.
Contract changes across modules require confirmation from both owners. Later code or baseline changes require updated tests and reviews for the affected scope.
Use [HANDOFF](../templates/HANDOFF_TEMPLATE.md) to transfer configuration versions, verification methods, known limitations, and recovery entry points.
