# Verifier Module AGENTS Draft

Status: template pending owner confirmation. Written on 2026-09-25; not installed as code-scope AGENTS instructions.
This file provides an independent editing entry point for Verifier. It does not establish that a target module with this name already exists in the code.
Adopt it using the [general local template](../../AGENTS_local.md), and name it `AGENTS.md` after confirming actual directories.
Preserve and integrate existing AGENTS files. This draft does not replace parent constraints, task authorization, or the formal design.

## Responsibility and Scope

- Module owner: `TODO`; backup: `TODO`; Lead: `TODO`.
- Verification targets, owned behavior, and limits of Verifier's conclusions: `TODO`; the owner must confirm these.
- Actual code, data, and test scope: `TODO`; public entry points and dependencies: `TODO`.
- Out-of-scope generation, execution, policy approval, or human judgment: `TODO`; assign explicitly in contracts.
- Do not equate the module name with code review, a test framework, or final human approval.

## Confirm Paths and Meaning

The locally inspected version was `52abe68db2dd167485f6bd79d6e36e193d608e64`.
The limited inspection did not identify a confirmed implementation directory for the target Verifier module.
Variables named `verifier` or tools named `verify_*` are insufficient to establish a mapping to the target module.
The owner must confirm that mapping using the design, actual call chains, and responsibilities. Do not invent existing interfaces based on a name.
After confirmation, record the actual directories, existing AGENTS, data entry points, and test configuration.

## Design and Upstream/Downstream Contracts

- Approved design, architecture, acceptance version, and approval record: `TODO`.
- Upstream inputs, their trust assumptions, and providers: `TODO`; result consumers and usage: `TODO`.
- Use the [file map](../templates/FILE_MAP_TEMPLATE.md) for entry points, function responsibilities, and call chains.
- Use the [contract template](../templates/CONTRACT_TEMPLATE.md) for result structure, evidence references, and exception semantics.
- Resolve: Which properties are verified, and what constitutes pass, fail, inconclusive, or execution failure?
- Resolve: Who approves the evidence requirements, rules, and thresholds, and how are their versions linked to original evidence?
- Resolve: Who handles timeouts, missing inputs, external service errors, or conflicting results?
- Resolve: If model evaluation is used, what are the requirements for data isolation, randomness, repeated measurement, and reproducibility?
- Resolve: May consumers use a conclusion to trigger automatic actions, and where is a human decision required?

## Invariants and Change Boundaries

- Verification rules, evidence integrity, and result consistency constraints: `TODO`.
- Result states, thresholds, data versions, and failure semantics: `TODO: complete from the approved contract`.
- Do not present unchecked behavior or execution failure as passing. Do not silently ignore missing inputs that affect the conclusion.
- Do not lower thresholds, replace evaluation data, or remove required checks to make the current implementation pass.
- Rule, data, or threshold changes need a design basis. State whether prior conclusions become invalid and what must be verified again.

## Context Entry Points

- Overall workflow: [Code_SOP](../../Code_SOP.md); global draft: [AGENTS_global](../../AGENTS_global.md).
- Current TASK, `write_code.md`, plan, status, and rule sources: `TODO: enter paths after adoption`.
- Use [DESIGN](../templates/DESIGN_TEMPLATE.md) for the approach. Reference approved versions of evaluation and acceptance requirements.
- Do not independently produce formal business conclusions before the verification target, evidence meaning, and decision rules are defined.

## Verification Commands and Evidence

| Item | Information to complete |
| --- | --- |
| Working directory and environment | `TODO: directory, dependencies, data, and external service versions` |
| Targeted tests | `TODO: full commands and selection scope from actual configuration` |
| Contract and integration verification | `TODO: consumer versions, commands, and expected state behavior` |
| Required evaluation and reproduction | `TODO: samples, baselines, thresholds, randomness controls, and commands` |

Under the approved semantics, cover applicable valid, invalid, and incomplete-verification cases. Check consistency between conclusions and evidence.
If reliable expectations or commands are missing, investigate and obtain owner confirmation. Do not define correctness from the current implementation's own outputs.
If data, services, or resources are missing, record the blocker, unverified scope, and deferred-verification owner. Do not invent passing conclusions.
Use [TEST_REPORT](../templates/TEST_REPORT_TEMPLATE.md) to record implementation SHA, baseline, actual results, and evidence versions.

## Review and Handoff

AI reviews using [REVIEW](../templates/REVIEW_TEMPLATE.md). The Lead reads related functions, decision paths, and consumer behavior.
Verification conclusions produced by this module do not replace the AI review and Lead's human approval required by this SOP.
Use [HANDOFF](../templates/HANDOFF_TEMPLATE.md) to transfer rule/data versions, reproduction commands, limitations, and unresolved items.
