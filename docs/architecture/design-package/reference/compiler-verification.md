# Intention Compiler verification obligations

**AI reference and human reviewer context.** [Build entrypoint](../builds/intention-compiler/README.md) defines scope. These are architectural checks to realize in native implementation tests, not a replacement PRD or proof of runtime acceptance.

## Independently assigned criteria

| Subject | Deterministic obligations | Semantic obligations |
|---|---|---|
| Qualified intake | Nonempty request; authorized identity/workspace; configured readable directory; supported/size-bounded required sources; preserved original/extracted references | No model-based meaning judgment during intake |
| Intent IR | Current schema; source/span/ID bounds; permitted identities; completed invocation; effects and limits | Fidelity; material coverage; no unsupported additions; coherent scope/entities; preserved exclusions/constraints; explicit uncertainty; workable purpose/result |
| Research Brief | Current schema; source/input consistency; unique/resolved obligations; valid typed limits; default authority and actual affected fields; completed invocation | Preserve accepted Intent and relevant context; coherent requirement/preference split; no unsupported widening; permitted defaults; usable inputs/deliverables/acceptance/evidence |
| Verifier assessment | Exact subject/context; every assigned criterion exactly once; reason/evidence; valid verdict; no control action or replacement artifact | No recursive semantic verifier |
| Node release | Required subnode decisions and observed work/review; exact accepted Brief; aggregate budgets/effects; durable evidence/state; required external ports | Reuse recorded Requirements assessment; no additional LLM interpretation |

A profile must explain each criterion, evidence and failure disposition before observing producer output. Bare PASS, producer readiness and valid JSON are insufficient. Missing/duplicate findings, mismatched subjects or nonpassing mandatory checks block release. A verifier reads the submitted artifact as its subject and original/upstream data as evidence; it cannot author replacement work.

## Cases and evidence

| Case | Expected behavior / evidence |
|---|---|
| Supported actionable research request | Accepted Intent and Brief, two independent assessments, subnode/node decisions, invocation observations; bounded consumer reads exact released Brief |
| Optional hardware absent | Authorized `single_gpu` assumption points to actual Brief constraint; no observed hardware claim |
| No numeric target/method | Preserve qualitative target/omission; Hypothesis chooses registered experimental procedure later |
| Topic-only or unknown purpose/result | Structurally valid IR may be faithfully extracted but unusable; semantic block, no Requirements invocation |
| Contradiction or invented method/target | Findings identify affected fields/source support failure; no rewrite or autonomous retry |
| Missing specified resource or unreadable directory | Explicit intake/environment error; never represent rejected material as qualified |
| Malformed producer or verifier output | Deterministic halt; bad producer output avoids verifier call; malformed assessment cannot advance |
| Missing/duplicate criterion or stale/swapped evidence | Reject even with an overall PASS |
| Time/call overrun or unavailable endpoint | Halt with observations/failure receipt; unknown token/cost is unavailable |
| Compiler produces no artifact | Record a failure receipt as the check subject; output/accepted inventories remain empty |
| Brief loses a user constraint, defaults purpose, or invents percentage | Requirements semantic rejection even if schema validates |
| Node/subnode mixup, cyclic dependency or parent budget exceedance | Reject binding/release; parent does not pool child permissions |
| Failed persistence | No accepted-output publication; preserve candidate/error when possible |
| Cancellation, restart, browser disconnection | No new dispatch on cancel; pause interrupted work on restart; closure alone does not cancel; retain effects/history |
| Image startup/export | Entrypoint starts bundled UI/service/runtime; loopback access works; evidence survives recreation; readable filenames and views match records |

Use the supplied examples for representation/relationships, and labelled challenge cases for model quality. Fixture checks are not measured model behavior; real endpoint evidence is required for successful implementation claims. Keep provider limitations and false acceptances/refusals visible. The downstream consumer is a test boundary, not an implementation of research stages.
