---
id: cap.improvement
type: reference
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, README.md]
provides: [research.capability_design_guide]
consumes: [cc.type.run_plan]
depends_on: [README.md, ../capsule/runner.md, ../capsule/gate-host.md, ../capsule/rsi-engine.md, benchmarking-material.md]
tags: [m1, capsule, verification, optimization]
level: detail
prd: [4.1.5, 4.2.9, 4.4.1, 4.4.3, 4.4.9]
---

# Capability design and improvement guide

PRD: 4.1.5, 4.2.9, 4.4.1, 4.4.3, 4.4.9

> Answers: Which improvement hypotheses and fixture families apply to each capsule?

This page is the home of capsule-specific improvement hypotheses and the fixture [families](../contracts/principles.md#term-message-family) needed to evaluate them. It is a reading map to the capabilities in the [inventory](README.md), not another schema, inventory or execution authority. The inventory is the home of membership; the planner and the template plan are the home of wires; each linked page defines its own behavior and [ports](../capsule/fields.md#term-port); [module map](../system/modules.md) is the home of code placement. A change to behavior is made at that page first. These designs remain draft until implementation validation.

## Shared boundaries to read once

All capabilities use [runner](../capsule/runner.md) validation, pinned declarations, protected model broker, deadlines and call capture. [Lifecycle](../system/lifecycle.md) is the home of reservation, duplicates, halt and explicit restart; [storage](../system/storage.md) is the home of publication and recovery. A [work capsule](README.md#term-work-capsule) cannot select its successor, activate a version or release a [Gate](../verification.md#term-gate). Production model calls use the [Codex adapter](../system/integration.md#term-codex-adapter); a model name in a prompt or [capsule](../capsule/capsule.md#term-capability-capsule) does not grant routing authority. The [planner](../system/planner.md) is an ordinary service, not a capsule; its DAG is validated, bound and [frozen](../system/lifecycle.md#term-freeze) before dispatch.

For every case below, also exercise absent input, wrong type/version, bad references, duplicate identity, cancellation, model/store failure and expired deadline using [verification hooks](../system/test-surfaces.md). A stage diagnostic is not automatically an [Observation](../schemas/observation.md#term-observation) `reason`: the runner maps attribution into the [Reason registry](../schemas/policy.md#registries), retaining a declared failure's detail in `ext.runner.failure_code` or safe evidence. Do not introduce a new top-level error vocabulary in individual implementations.

Model work and pure helper work must be measured separately. An optimization candidate must preserve declared outputs and observable ordering, permission [boundaries](../system/modules.md#term-boundary), correlation/capture and Gate criteria. Measure first; a proposed optimization is not a faster implementation. The typed interface/implementation split follows [Kubeflow component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/). Prompt-plus-metric evaluation borrows the explicit program, metric and example separation of [DSPy optimizers](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md); importing its optimizer or widening M1 mutation authority is not required.

## Research chain capabilities

The intent CC ([intent-compile](intent-compile.md)) is model-backed and RSI-eligible for code and prompts (hypothesis in section 13). Screening and the intent CC are the M1 RSI-eligible capsules.

### 1. `research.compile_brief`

**Contract defined in:** [Requirement Compilation](requirement-capsule.md), [research_brief](../types/research-brief.md). Caller: requirement node `N_req`; consumer: the planner and every later research node. Inputs are intake/source projection and the accepted `intent_ir`; the sole output is the [Brief](../types/research-brief.md#term-research-brief).

**Control decisions:** the one semantic pass preserves the requested metric, comparator, target and supporting source quote. Missing compute values use the pinned defaults table; contradictory source never loses to a default. A syntactically valid payload with unresolved objective issues does not prove experimental readiness. The Brief Gate independently assesses fidelity.

**Break cases:** missing quantitative target, percent versus percentage-point ambiguity, contradictory runtime limits, quote that exists but supports a different target, invented metric, locale/unicode offsets and [source text](../types/source-text.md#term-source-text) containing instructions to disable Gates. Check both structure and semantic fidelity rather than relying on JSON validity.

**Improvement hypothesis:** shorten prompt boilerplate or organize approved demonstrations while preserving the single pass and output obligations. Evaluate target/comparator/quote fidelity, issue recall, model calls and elapsed time on held-out intake families. Manual revision only: this capability is not an M1 [RSI target](../capsule/rsi.md#term-rsi-target). The replacement boundary is its admitted body and Brief port, not a mutable shared default table.

### 2. `research.search_ideas`

**Contract defined in:** [Search](search-capsule.md), [idea_set](../types/idea-set.md). Caller: planned search node; consumers: Screening and Report. Uses only pinned scholarly/local [operators](README.md#term-operator).

**Control decisions:** the first model pass proposes bounded keyword queries; declared operators execute them; the second writes evidence-linked ideas. The capsule copies verbatim passages and preserves partial-service limitations. Unknown chunk citations reject the reply. No query reformulation, vote or silent second search occurs after failure.

**Break cases:** both services down versus genuine empty retrieval; one service down with useful other results; repeated source IDs; invented chunk IDs; evidence too large to fit; injection embedded in abstracts; apparently relevant passage supporting the opposite claim. Verify retention/truncation issues and exact service attribution.

**Improvement hypothesis:** reduce repeated prompt serialization, deduplicate retained identical source bytes and reuse fixture-controlled retrieval preparation while preserving source order and citation identity. Changing query-generation examples requires a manually admitted revision; no Search [RSI](../rsi.md#term-rsi). Do not add concurrency, live query rewrites or hidden external fetches as an optimization. Retrieval relevance and grounded-idea quality are separate measurements.

### 3. `research.select_opportunity`

**Contract defined in:** [Screening](screening.md), [opportunity_card](../types/opportunity-card.md), internal [screening_assessments](../types/screening-assessments.md), [ranking helper](op-rank-opportunities.md), [dependency registry](op-assess-dependency.md). The internal assessment type is not another pipeline port.

**Control decisions:** the wrapper makes one assessment call, validates provenance, supplies the frozen registry to local ranking, then returns the one winning card with complete dispositions. The model does not compute authoritative rank or dependency eligibility. No eligible result emits no card and [halts](../system/lifecycle.md#term-halt).

**Break cases:** duplicate/consolidated idea provenance, integer boundary scores, prohibited hidden fourth dimension, higher-scoring ineligible candidate, ties, empty eligible set, unknown dependencies, forged registry bytes and prompt instructions to favor a candidate. Use exact fixture outcomes for arithmetic and separate independently authored labels for semantic scoring.

**Improvement hypothesis:** the isolated pure rank helper may reduce repeated parsing or temporary allocations while producing exactly the same canonical result. The conditionally authorized text target may improve rubric clarity within fixed dimensions. [Offline RSI](../capsule/rsi-engine.md) alone defines mutation paths, query budget, protected splits and comparison. Wrapper, registry, schemas, scoring arithmetic and independent referee stay protected. Additional model calls or relaxed eligibility are behavior changes, not optimizations.

### 4. `research.form_hypothesis`

**Contract defined in:** [Hypothesis](hypothesis.md), [hypothesis_blueprint](../types/hypothesis-blueprint.md), [measurement protocol](measurement-protocol.md). Uses admitted CodeSearch and trusted [snapshot](../capsule/library.md#term-library-snapshot)/method services. Consumer: POC, Benchmark and Evaluation.

**Control decisions:** one claim and one bounded semantic [turn](../system/model-bridge.md#term-model-turn); deterministic code validates quantitative predicates and required Brief metrics. Freeze resources, methods, configuration, seeds and classification before returning. A missing intervention location or unsupported measurement [blocks](../system/modules.md#term-block) readiness rather than producing a vaguely executable plan.

**Break cases:** method exists with wrong hash/unit, stale baseline, wrong resource [kind](../capsule/capsule.md#term-capsule-kind), threshold weaker than Brief, zero or overflowing repeat seed, treatment mutating the baseline and post-result threshold proposals. Assert snapshot publication precedes POC release.

**Improvement hypothesis:** supply compact CodeSearch excerpts and reuse content-addressed snapshot preparation. Preserve verbatim locations, method pins and all scientific constraints. Manual revision only. Replacing a measurement implementation uses the registered method boundary with its own [fixtures](../system/test-surfaces.md#term-fixture), not a model-generated method.

### 5. `research.build_poc`

**Contract defined in:** [POC](poc.md), [poc_bundle](../types/poc-bundle.md). Admitted CodeSearch is separate from ordinary workspace helpers and the trusted syntax service. Consumer: empirical execution.

**Control decisions:** assemble static environment/requirements from frozen inputs; generate the single patch and sequential harness; compile/scan without executing generated imports; publish the complete bundle. The [owning page](poc.md#bounded-generation-design) pins the generation-call ceiling. No syntax-driven regeneration or autonomous repair is permitted.

**Break cases:** archive traversal/symlinks/duplicate roles, extra source files, undeclared package, generated measurement replacement, dynamic import bypass, baseline mutation, syntactically valid patch unrelated to the claim, stdout logging off protocol and setup files that execute code. Static scanning and runtime confinement are independent obligations.

**Improvement hypothesis:** use the pinned bundle template and deterministic static manifests to reduce model-authored surface; compact exact code excerpts to reduce context. Assess patch fidelity and harness fidelity independently, plus compile rate, artifact integrity and cost. Keep failed examples as failures; accepting fewer files or relaxing hygiene is not a speedup. No M1 POC RSI.

### 6. `research.run_benchmark`

**Contract defined in:** [Scientific Benchmark](benchmark.md), [process service](../capsule/process-boundary.md), [benchmark_payload](../types/benchmark-payload.md), [measurement protocol](measurement-protocol.md). Consumer: Evaluation and Report. No model call.

**Control decisions:** one authorized empirical execution with baseline/treatment order and frozen paired seeds. The trusted service supplies measurement references and complete capture; the parser rejects malformed/missing/extra sample records. Collection never decides whether the hypothesis succeeded.

**Break cases:** timeout after baseline, process forks after cancellation, duplicate samples, fabricated measurement_ref, invalid UTF-8, nonfinite value, missing final sample, swapped arms, stdout diagnostic pollution, capture write failure and duplicate request after a crash. Preserve raw failure bytes; never publish partial samples as a complete payload.

**Improvement hypothesis:** prepared immutable environments or streaming parser implementation may reduce setup cost. Demonstrate unchanged arm isolation, completeness and capture before adopting. Do not parallelize arms, change repeats, reuse an old empirical measurement or automatically rerun. Environment warmup effects belong in a preregistered trusted method. No M1 RSI.

### 7. `research.evaluate_results`

**Contract defined in:** [Evaluation](evaluation.md), [evaluation_verdict](../types/evaluation-verdict.md), arithmetic in [measurement protocol](measurement-protocol.md). Consumer: Report. Scientific verdict and infrastructure Gate remain distinct.

**Control decisions:** verify pins and recompute transformations; one plausibility turn explains risks; deterministic classification uses the preregistered predicates. The model cannot move thresholds or change arithmetic. Scientific failure still receives a report when infrastructure evidence is admissible.

**Break cases:** lower-is-better sign, exactly-on-threshold value, percentage points, zero baseline, absent validity evidence, stale measurement hash, contradictory model verdict, middle zone without a preregistered conditional rule and report pressure to hide failure.

**Improvement hypothesis:** simplify explanation prompts and compare cached immutable parsing only, leaving classification exact. Measure numeric equality, classification equality and explanation grounding separately. No M1 RSI. New classification semantics require upstream preregistration and a new run, not a downstream evaluator override.

### 8. `research.write_report`

**Contract defined in:** [write-report](write-report.md), [research_report](../types/research-report.md). Its evidence context is supervisor-scoped; publication is the ordinary [delivery](delivery.md) module after report release.

**Control decisions:** the [bounded synthesis](write-report.md#bounded-synthesis-design) uses admitted evidence and fixed template, preserves scientific classification, citations, contradictions and limitations, then mechanical [checks](../capsule/fields.md#term-check) reconcile sections and facts. It performs no fresh research. Trusted publication controls destinations and atomic manifest completion.

**Break cases:** unsupported numerical claim, wrong cited excerpt, fabricated source, missing issue from an earlier stage, contradictory Gate/scientific labels, hidden-fixture reference, absent template section, incorrect FAIL framing and incomplete publication directory. Check document content and publication separately.

**Improvement hypothesis:** deterministic section assembly, stable evidence ordering and concise summary prompts reduce generation surface. A changed template is a pinned body revision rechecked against all required sections. No M1 Report RSI; no report or renderer may activate candidates, message externally or turn scientific FAIL into PASS.

## Shared verifier and operators

### 9. `research.verifier`

**Contract defined in:** [shared verifier](../capsule/gate-capsules.md), [evidence_bundle](../types/evidence-bundle.md), [verifier_assessment](../types/verifier-assessment.md), stage criteria pages. Caller: [Gate host](../capsule/gate-host.md#term-gate-host); consumer: Gate host only.

The host selects criteria and evidence after [Tier 1](../verification.md#term-tier-1); the verifier must answer every requested criterion exactly once with grounded quotations. It cannot release, modify criteria or query undisclosed evidence. Empty mechanical profiles skip semantic work honestly. Attack missing/extra criteria, cherry-picked quotations, subject pretending to be referee, conflicting input/output evidence and insufficient context. Acceptance must distinguish malformed assessment, unavailable judge and demonstrated subject defect.

**Improvement hypothesis:** bounded evidence projection and deterministic checks can avoid unnecessary model work, but dropping relevant evidence must yield unknown rather than pass. The M1 referee is immutable to RSI. Manual verifier revisions require all stage planted-defect fixtures; a criterion/profile revision rechecks its affected stage. [OPA](https://www.openpolicyagent.org/docs) is the policy/data separation precedent, not assurance that a model judge is correct.

### 10. `op.scholarly_search`

**Contract defined in:** [scholarly operator](op-scholarly-search.md), [search_hits](../types/search-hits.md), [connector adapter](../system/integration.md#deepsearch-scholarly-search). Bounded query/top_k input; Search receives retained abstracts and limitations.

No model work; designated connectors only. Test malformed service rows, duplicate arXiv versions/S2 identities, missing abstracts, partial outage, genuine zero hits, response deadline and replay fixture mismatch. Nested mechanical [Verification](../schemas/verification-record.md#term-verification) must persist before results return. Consider parsing/deduplication improvements using recorded responses; do not change retrieval semantics, rate spacing, deadline or partial-outage attribution silently. Recorded replay is reproducibility, not a fresh live-network result. No M1 RSI.

### 11. `op.local_search`

**Contract defined in:** [local operator](op-local-search.md), [search_hits](../types/search-hits.md). Search supplies its authorized intake reference and query; no arbitrary filesystem read, network or model access.

The existing exact tokenization, passage slicing, ordering and top_k rules are the reference contract. Test empty query, repeated words, Unicode case folding, equal scores, boundary passage length, multiple documents and passages containing injection. Exact source bytes/order matter independently of relevance. Reuse immutable tokenization preparation only if it preserves every reference outcome and stays within authorized content; no new index/retrieval algorithm is implied. No M1 RSI.

### 12. `op.codesearch`

**Contract defined in:** [CodeSearch](op-codesearch.md), [code_hits](../types/code-hits.md). Hypothesis/POC supply an authorized repository snapshot, query and top_k; all returned line spans must match that snapshot.

Test path escape, symlink, stale index, unsupported language, AST chunk boundary, equal relevance, line bounds and forged source excerpt. Existing adapter/index keys pin content and version. Reusing that index reduces repeated preparation without altering retrieval behavior. Improve index implementation only behind the same pinned adapter contract, preserving relevance ordering and deterministic tie keys. No network/model call or M1 RSI.

### 13. `research.compile_intent`

**Contract:** [intent compile](intent-compile.md), [intent gate profile](intent-gate.md), [intent_ir](../types/intent-ir.md). Model-backed bounded compile, validate, review, repair loop.

**Break cases:** constraint dropped, goal invented, "target" hardened into a cap, placeholder replacing enumerated fields, conflicting instructions silently resolved, vague text guessed instead of marked unknown, request text telling the model to skip review, reviewer returning a malformed answer, repair budget exhausted.

**Improvement hypothesis:** better compile and repair prompts and tighter validator-driven repair reduce repairs per request and Gate failures. RSI may change the compile code and prompts only; ports, checks, the nested verifier and profile, and the repair budget stay frozen. Measure: Gate pass rate on held-out prompts first, then repairs used, model calls and time. Parent and child use the same model route.

## Evidence and decision responsibility

[Benchmark material](benchmarking-material.md) is the home of acquisition candidates and fixture construction policy. Public benchmarks seed visible development checks; independently authored hidden fixtures remain the RSI acceptance authority. Fixture custodians choose splits/labels and freeze them; work authors cannot relabel their own failures. The Gate host aggregates infrastructure decisions; scientific classification is preregistered; the librarian/human handles admission activation and recovery. The planner proposes experimental structure, while deterministic validation and supervisor policy decide whether it can execute.

When an improvement wins, record the exact parent/child hashes, inputs/settings, expected/observed outputs, quality and timing, unavailable usage telemetry and affected consumers. Do not optimize on the same cases later called held out. No document, model review or benchmark precedent makes the system unbreakable; the acceptance claim is bounded by exercised scenarios and verified runtime mechanisms.
