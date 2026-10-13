# Verification: blocks, boundaries, system
Version 2, 2026-09-29. This replaces the former testing policy and test-report/checklist workflow. It defines future M1 verification and does not claim application readiness.

## 1. Define a block
A block is bounded behavior with specified inputs, observable outputs or state changes, failure semantics and an executable check. It may be a function, service, workflow step or small connected component. A filename alone is not a block definition.

Define blocks in plan.md and map them to spec.md ACs. Put implementation and verification work in tasks.md; attach results in evidence/. No parallel implementation checklist or report is required.

## 2. Verification levels
| Level | Required conclusion | Representative checks | Limits |
| --- | --- | --- | --- |
| BLOCK | A block implements its required behavior | Normal, boundary and invalid inputs; state invariants; relevant failure and recovery paths | Stubs isolate dependencies but cannot prove real connections |
| BOUNDARY | Connected blocks obey the TASK agreement | Real serialization and semantic fields, compatibility, timeout/error propagation and repeated calls | Fixtures alone cannot prove an external service is available |
| SYSTEM | The integrated candidate satisfies M1 | Complete journeys, applicable persistence/restart, recovery, quality, budgets, cost and latency | A partial demo or green block suite does not prove M1 |

Unit, integration, end-to-end, evaluation, static inspection and reproducible manual checks are methods, not additional workflow stages. Documentation tasks need relevant document checks, not unrelated application tests.

## 3. Define each check before execution
For every V ID, plan.md records level, block/IF IDs, AC references, fixtures, dependency mode (stub/local real/external real), expected outcomes, threshold source, command and working directory or exact manual procedure, prerequisites and retained artifacts.

Select applicable normal, boundary, failure and recovery cases; explain omissions. Expected results must come from requirements or independent fixtures, not a copy of the implementation's algorithm. Prefer a reproducing regression case for a bug.

Missing thresholds, schemas or services remain unresolved. Independent preparation can continue; dependent verification cannot pass.

## 4. Block loop
1. Read the block ACs and interface dependencies.
2. Build the check and implementation in small steps.
3. Execute checks and retain a run record and raw outputs.
4. Link each V/AC row to its evidence in tasks.md.
5. Preserve failures, fix causes and rerun.
6. Connect verified blocks and execute boundary checks.

Tests may precede or accompany implementation. Do not invent failing tests for every document edit. Checks must exercise and assert the target behavior.

## 5. Evidence
Use [EVIDENCE_TEMPLATE](../../plugins/spec-kit/templates/EVIDENCE_TEMPLATE.md) in feature evidence/. One run may cover several checks, but each check has its own result.

Record time and run ID; candidate identity; source/spec/plan/IF versions; exact command/procedure and working directory; environment; dependency mode; fixture versions; expected and observed results; exit code; pass/fail/skip counts; raw artifact paths; and limitations.

For uncommitted code, HEAD alone is insufficient: record HEAD, a diff digest and hashes of relevant changed/untracked execution inputs, or an immutable snapshot reference. Include tests, configuration and dependency inputs. Preserve reproducibility without capturing secrets or committing solely to obtain an ID.

## 6. Results
| Result | Meaning |
| --- | --- |
| PASS | Required assertions executed and met expectations on the identified candidate |
| FAIL | A requirement was violated |
| BLOCKED | A prerequisite or unresolved definition prevented verification |
| NOT_RUN | The check has not executed |
| STALE | Earlier evidence no longer covers the current candidate or requirements |
| N/A | Inapplicable with a scope-derived reason; never substitutes for a failed required check |

Zero cases, all-skipped cases, suppressed errors or only stubs cannot establish behavior requiring actual execution or real services. Record skips separately. If a required assertion is skipped, its check is not PASS.

All required V IDs mapped to an AC must have valid PASS evidence. Do not hide mixed outcomes behind a passing average.

## 7. System TASK
TASKS designates one normal TASK for system verification. It has its own spec/plan/tasks/evidence. It owns system ACs and journeys and references child-task coverage without copying their requirements.

Its plan fixes the candidate configuration and component revisions, dependency requirements, complete journeys, datasets and measurable constraints. Its matrix maps system AC -> participating TASK/block/IF IDs -> system V -> evidence.

Before final acceptance, required blocks and interfaces must be ready and their evidence valid for that candidate. Early system runs are useful but do not establish final completion.

Run the assembled product, including applicable cross-module failures and recovery. Missing real accounts/services remain BLOCKED; mock results cannot fill that gap.

## 8. Models and research
Take permitted models from the registered PRD. Never invent model identifiers, role-based selection, providers or evaluation thresholds.

Record provider/model identifiers and available versions, executor inputs, prompts/configuration, datasets and splits, sample counts, repetitions, controllable seeds, scoring rubric, quality metrics and raw outcomes. Cost/latency evidence includes measurement boundaries, retries, concurrency, caching and billing basis.

Use frozen evaluation inputs for comparable runs and define thresholds before final measurements. A single response cannot establish reliability. Stubs can establish routing rules but require separate real-service evidence for live invocation ACs. Disclose uncontrolled variability.

## 9. Revalidation
Behavior, schemas, tests, configuration, dependencies, acceptance and candidate changes trigger an impact assessment. Use TASKS dependencies and TASK agreements to identify affected blocks and downstream consumers. Mark affected matrix rows STALE and rerun their checks and relevant system journeys.

Reuse unchanged evidence only with a recorded comparison establishing equivalent behavior, inputs and dependencies. Evidence-only edits do not inherently require reruns. Keep the reuse basis with the evidence reference.

System completion refers to one exact candidate. After candidate changes, reassess evidence and rerun affected checks before retaining that claim.

## 10. Completion
TASK requires completed required work and valid PASS evidence for every required AC/check, with no invalidating dependency unresolved.

M1 requires all in-scope source clauses allocated, all required TASKs verified for the candidate, consistent interfaces and a passing system TASK on that candidate.

Preparing this framework does not require unfinished teammates' tasks to be completed first.
