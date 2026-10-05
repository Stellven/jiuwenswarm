---
type: design
status: draft
version: 3
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [research.evaluate_results]
consumes: [cc.type.benchmark_payload, cc.type.hypothesis_blueprint, cc.type.research_brief]
depends_on: [pipeline.md, research-gates.md, measurement-protocol.md]
tags: [m1, contract]
---

# Scientific evaluation

`research.evaluate_results` is the distinct scientific evaluator work capsule required by PRD 3.8. It consumes the admitted benchmark_payload, frozen hypothesis_blueprint and research_brief; it emits [evaluation_verdict](../types/evaluation-verdict.md). It performs one bounded plausibility model turn and deterministic comparison/classification. It has read-only evidence access, no external fetch, patches, retries of the benchmark or threshold changes.

## Contract and sequence

Resolve required inputs and exact versions; verify the Blueprint/artifact/method pins; resolve raw captures through the trusted evidence broker; recompute paired samples and transformations using the pinned Decimal context; calculate claim/acceptance/falsification predicates; perform one plausibility turn over admitted values and bounded retained excerpts; apply the frozen classification rule; persist output and evidence. Full logs remain in the store rather than model memory.

`compare_to_thresholds(benchmark_payload, hypothesis_blueprint) -> comparisons` is an ordinary pure module, not another admitted capsule. It returns the entries owned by evaluation_verdict and rejects unknown metric IDs, invalid units and mismatched method pins. Its independent callable entry point allows exact arithmetic fixtures.

The [Blueprint](../types/hypothesis-blueprint.md) defaults middle_zone_classification to INCONCLUSIVE. CONDITIONALLY_ACCEPTABLE is available only if selected before POC generation and every Brief acceptance and guard predicate holds. A real effect below the claim does not automatically receive conditional acceptance. All four PRD tags remain scientific data: PASS, FAIL, INCONCLUSIVE, CONDITIONALLY_ACCEPTABLE.

Missing or corrupted evidence is a validity blocker, never a scientific FAIL. An incomplete evaluation may retain an INCONCLUSIVE draft and explicit blocker evidence, but mandatory evidence failures cause infrastructure Gate rejection. A scientific FAIL on admissible evidence advances through the same Gate and release sequence as PASS.

## Interface, failures and persistence

Runner input port names are benchmark_payload, hypothesis_blueprint and research_brief; output port is evaluation_verdict. Gate slot uses research.verifier and pinned research.accept_evaluation.v1. Its deterministic checks recompute classification; its semantic criterion assesses grounding of plausibility/risk explanations without issuing a second scientific verdict.

INPUT_MISSING, INPUT_INVALID and REFERENCE_INVALID reject absent/malformed/unresolvable inputs; PIN_MISMATCH rejects cross-run or changed frozen data; METHOD_UNAVAILABLE rejects missing trusted methods; MODEL_TIMEOUT retains attempted plausibility evidence and halts; OUTPUT_INVALID rejects invalid output. Deadline, duplicate request, cancellation and explicit restart use [lifecycle](../system/lifecycle.md), with no silent second model call.

The runner/store is the sole output Artifact and Observation writer; the Gate host/store writes Verification; the supervisor/store writes release. Correlation resides in those records rather than duplicated payload IDs. Store failure prevents successor dispatch. The model route and timeout are frozen configuration references.

## Verification and replacement

Independently call comparison/classification with success, falsification, default middle-zone, preregistered conditional zone, guard failure, null, nonfinite, zero-denominator and corrupted-reference fixtures. Inject model/store timeout and cancellation. Assert failed Gate persistence cannot dispatch report. Runtime evidence comes from implementation; these are expected outcomes.

The immutable preregistration boundary follows the distinction between declared analysis and observed results in [OSF preregistration](https://www.cos.io/initiatives/prereg). [Python Decimal](https://docs.python.org/3/library/decimal.html) supplies the arithmetic precedent. Alternative evaluators replace the work capsule behind these ports; changed classification semantics require a new Blueprint/versioned rule before a new run.
