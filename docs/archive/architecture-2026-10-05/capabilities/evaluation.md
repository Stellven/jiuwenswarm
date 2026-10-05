---
id: cap.evaluation
type: capability
status: draft
version: 3
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.evaluate_results]
consumes: [cc.type.benchmark_payload, cc.type.hypothesis_blueprint, cc.type.research_brief]
depends_on: [README.md, research-gates.md, measurement-protocol.md]
tags: [m1, contract]
level: detail
prd: [3.8.1, 3.8.2, 3.8.3, 3.8.4, 3.8.5]
---

# Scientific evaluation

PRD: 3.8.1, 3.8.2, 3.8.3, 3.8.4, 3.8.5

> Answers: How does the evaluator turn a benchmark payload into a scientific verdict?

## What it does

`research.evaluate_results` is the distinct scientific evaluator [work capsule](README.md#term-work-capsule) required by PRD 3.8. It consumes the admitted [benchmark_payload](../types/benchmark-payload.md#term-benchmark-payload), [frozen](../system/lifecycle.md#term-freeze) [hypothesis_blueprint](../types/hypothesis-blueprint.md#term-hypothesis-blueprint) and [research_brief](../types/research-brief.md#term-research-brief); it emits [evaluation_verdict](../types/evaluation-verdict.md). It performs one bounded plausibility model [turn](../system/model-bridge.md#term-model-turn) and deterministic comparison/classification. It has read-only evidence access, no external fetch, patches, retries of the benchmark or threshold changes.

## Where it sits

[Task node](../system/nodes.md#term-task-node) `research.evaluate_results` in the research chain template ([capabilities](README.md)). Inputs: `benchmark_payload`, `hypothesis_blueprint`, `research_brief`. Output: [evaluation_verdict](../types/evaluation-verdict.md). [Gate profile](../schemas/profiles.md#term-gateprofile): shared `research.verifier` with `research.accept_evaluation.v1` ([research gates](research-gates.md)).

## Contract and sequence

Resolve required inputs and exact versions; verify the Blueprint/artifact/method pins; resolve raw captures through the trusted evidence broker; recompute paired samples and transformations using the pinned Decimal context; calculate claim/acceptance/falsification predicates; perform one plausibility turn over admitted values and bounded retained excerpts; apply the frozen classification rule; persist output and evidence. Full logs remain in the store rather than model memory.

`compare_to_thresholds(benchmark_payload, hypothesis_blueprint) -> comparisons` is an ordinary pure module, not another admitted [capsule](../capsule/capsule.md#term-capability-capsule). It returns the entries defined in [evaluation_verdict](../types/evaluation-verdict.md#term-evaluation-verdict) and rejects unknown metric IDs, invalid units and mismatched method pins. Its independent callable entry point allows exact arithmetic [fixtures](../system/test-surfaces.md#term-fixture).

The [Blueprint](../types/hypothesis-blueprint.md) defaults middle_zone_classification to INCONCLUSIVE. CONDITIONALLY_ACCEPTABLE is available only if selected before POC generation and every Brief acceptance and guard predicate holds. A real effect below the claim does not automatically receive conditional acceptance. All four PRD tags remain scientific data: PASS, FAIL, INCONCLUSIVE, CONDITIONALLY_ACCEPTABLE.

Missing or corrupted evidence is a validity blocker, never a scientific FAIL. An incomplete evaluation may retain an INCONCLUSIVE draft and explicit blocker evidence, but mandatory evidence failures cause infrastructure [Gate](../verification.md#term-gate) rejection. A scientific FAIL on admissible evidence advances through the same Gate and release sequence as PASS.

## Interface, failures and persistence

Runner input port names are benchmark_payload, hypothesis_blueprint and research_brief; output port is evaluation_verdict. Gate slot uses [research.verifier](../capsule/gate-capsules.md#term-verifier) and pinned research.accept_evaluation.v1. Its deterministic [checks](../capsule/fields.md#term-check) recompute classification; its semantic criterion assesses grounding of plausibility/risk explanations without issuing a second scientific verdict.

INPUT_MISSING, INPUT_INVALID and REFERENCE_INVALID reject absent/malformed/unresolvable inputs; PIN_MISMATCH rejects cross-run or changed frozen data; METHOD_UNAVAILABLE rejects missing trusted methods; MODEL_TIMEOUT retains attempted plausibility evidence and [halts](../system/lifecycle.md#term-halt); OUTPUT_INVALID rejects invalid output. Deadline, duplicate request, cancellation and explicit restart use [lifecycle](../system/lifecycle.md), with no silent second model call.

The runner/store is the sole output Artifact and [Observation](../schemas/observation.md#term-observation) writer; the [Gate host](../capsule/gate-host.md#term-gate-host)/store writes [Verification](../schemas/verification-record.md#term-verification); the supervisor/store writes release. Correlation resides in those records rather than duplicated payload IDs. Store failure prevents successor dispatch. The model route and timeout are frozen configuration references.

## Declaration

No [Declaration](../capsule/fields.md#term-declaration) JSON is abridged on this page. Ports and the Gate slot are stated in Interface, failures and persistence above; the Declaration format is in [capsule fields](../capsule/fields.md).

## Checks

The deterministic Gate checks are in the `research.accept_evaluation` row of [research gates](research-gates.md). `compare_to_thresholds` is the pure comparison module named in Contract and sequence.

## Tests and replacement

Independently call comparison/classification with success, falsification, default middle-zone, preregistered conditional zone, guard failure, null, nonfinite, zero-denominator and corrupted-reference fixtures. Inject model/store timeout and cancellation. Assert failed Gate persistence cannot dispatch report. Runtime evidence comes from implementation; these are expected outcomes.

The immutable preregistration boundary follows the distinction between declared analysis and observed results in [OSF preregistration](https://www.cos.io/initiatives/prereg). [Python Decimal](https://docs.python.org/3/library/decimal.html) supplies the arithmetic precedent. Alternative evaluators replace the work capsule behind these [ports](../capsule/fields.md#term-port); changed classification semantics require a new Blueprint/versioned rule before a new run.

## Acceptance seeds

These rows seed the spec AC table. Each is derived from the behavior on this page; the coding spec sets final thresholds and fixtures. Level is [BLOCK](../v-model.md#term-block), [BOUNDARY](../v-model.md#term-boundary) or [SYSTEM](../v-model.md#term-system).

| AC ID | Source | Observable criterion | Level |
|---|---|---|---|
| cap.evaluation.AC-01 | PRD 3.8.4 | compare_to_thresholds on exact-arithmetic fixtures returns the expected comparison entries; unknown metric ids, invalid units and mismatched method pins are rejected. | BLOCK |
| cap.evaluation.AC-02 | PRD 3.8.5 | Success, falsification, default middle-zone, preregistered conditional zone and guard-failure fixtures give PASS, FAIL, INCONCLUSIVE, CONDITIONALLY_ACCEPTABLE and INCONCLUSIVE respectively. | BLOCK |
| cap.evaluation.AC-03 | PRD 3.8.2 | Null, nonfinite, zero-denominator and corrupted-reference inputs produce an incomplete-evidence blocker, never a scientific FAIL. | BLOCK |
| cap.evaluation.AC-04 | PRD 3.8.5 | Classification is applied only from the frozen Blueprint rule; a missing preregistered rule gives INPUT_INVALID before evaluation. | BLOCK |
| cap.evaluation.AC-05 | N_node | The capsule makes exactly 1 plausibility model turn; a MODEL_TIMEOUT retains attempted evidence and halts with no second call. | BOUNDARY |
| cap.evaluation.AC-06 | G_node | [Tier 1](../verification.md#term-tier-1) independently recomputes arithmetic and classification and matches the output exactly. | BOUNDARY |
| cap.evaluation.AC-07 | US-09 | A scientific FAIL on admissible evidence passes the infrastructure Gate and the report node starts. | SYSTEM |
| cap.evaluation.AC-08 | US-07 | A failed evaluation Gate persists nothing releasable and the report node does not start. | SYSTEM |
