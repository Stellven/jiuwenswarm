# Capsules

[Start here](README.md) · Specified design · No measured optimization claims

## Research capability baseline

The [pipeline](../../m1/pipeline.md) records twelve existing research/verifier/operator identities. This is not the complete inventory for the corrected intent-to-DAG architecture. Intent capability identities and their Gate profiles remain to be reconciled; do not count unnamed roles as admitted versions. The [capability guide](../../m1/capability-designs.md) links each behavior owner, fixture family and optimization hypothesis. Installation does not mean every capability executes in every run: retrieval operators execute through declared callers, and the shared verifier executes at applicable Gates.

| Capability | Responsibility and execution | Dependencies / behavior owner |
|---|---|---|
| `research.compile_brief` | Skill; one semantic pass turns the source request into a research contract | [Requirement](../../m1/requirement-capsule.md) |
| `research.search_ideas` | Tool; bounded model work and retrieval form evidence-backed ideas | Both local and scholarly operators per query; [Search](../../m1/search-capsule.md) |
| `research.select_opportunity` | Tool; consolidation and scoring, deterministic filtering/ranking, one selected card | Frozen dependency registry; [Screening](../../m1/screening.md) |
| `research.form_hypothesis` | Tool; bounded model work freezes hypotheses, predicates and protocol | CodeSearch and resource freezing; [Hypothesis](../../m1/hypothesis.md) |
| `research.build_poc` | Tool; bounded generation creates experiment files and harness | CodeSearch; [POC](../../m1/poc.md) |
| `research.run_benchmark` | Tool; no model; coordinates trusted baseline/treatment execution | Measurement adapters and confined worker; [Benchmark](../../m1/benchmark.md) |
| `research.evaluate_results` | Bounded plausibility turn plus deterministic numeric classification | Read-only measurement evidence; [Evaluation](../../m1/evaluation.md) |
| `research.write_report` | Skill; one synthesis turn, then ordinary rendering/publication | No admitted nested dependency; [Delivery](../../m1/delivery.md) |
| `research.verifier` | Shared skill; stage-selected semantic assessment, not numeric scientific classification | [Verifier](../../capsule/gate-capsules.md), [assessment](../../types/verifier-assessment.md) |
| `op.local_search` | Tool; query and local documents produce ranked search hits | [Local search](../../m1/op-local-search.md) |
| `op.scholarly_search` | Tool; query produces bounded scholarly search hits | [Scholarly search](../../m1/op-scholarly-search.md) |
| `op.codesearch` | Tool; query and repository snapshot produce code hits | [CodeSearch](../../m1/op-codesearch.md), [code hits](../../types/code-hits.md) |

## Verification count

Each work Binding gets an automatically prepared test instance derived from its capsule Declaration. These instances reuse a fixed implementation; they are not independently mutable referees. There is **one shared semantic verifier identity**, `research.verifier`; intent, requirement and DAG-node Gate profiles reuse it. Gate invocation count depends on the executed capsule calls, not the number of profiles. Gate-role capsules have zero RSI-mutable components. Deterministic host checks are ordinary code, not extra verifier capsules. See [Gate owner](../../capsule/gate-capsules.md).

## Research ports to reconcile

Baseline generated from [pipeline](../../m1/pipeline.md), whose fixed-plan entry is superseded. Exact payload versions are in [schema inventory](schemas-and-connections.md). StageContext is a trusted contextual input, not an invented output port. **The requirement row below is the old launcher/hint entry, not the corrected accepted-intent contract.**

<!-- generated:showcase-ports -->
| Step / capability | Required inputs and context | Output | Gate profile |
|---|---|---|---|
| requirement: `research.compile_brief` | launcher intake; source_text; optional deterministic intent_ir hints | `research_brief` | `research.accept_brief.v1` |
| search: `research.search_ideas` | research_brief; intake | `idea_set` | `research.accept_ideas.v1` |
| screening: `research.select_opportunity` | idea_set; research_brief | `opportunity_card` | `research.accept_card.v1` |
| hypothesis: `research.form_hypothesis` | opportunity_card; research_brief; intake | `hypothesis_blueprint` | `research.accept_hypothesis.v1` |
| poc: `research.build_poc` | hypothesis_blueprint; research_brief; intake | `poc_bundle` | `research.accept_poc.v1` |
| benchmark: `research.run_benchmark` | poc_bundle; hypothesis_blueprint | `benchmark_payload` | `research.accept_benchmark.v1` |
| evaluation: `research.evaluate_results` | benchmark_payload; hypothesis_blueprint; research_brief | `evaluation_verdict` | `research.accept_evaluation.v1` |
| report: `research.write_report` | evaluation_verdict; benchmark_payload; research_brief; idea_set; opportunity_card; hypothesis_blueprint; authorized StageContext | `research_report` | `research.accept_report.v1` |
<!-- /generated:showcase-ports -->

The shared verifier consumes an [evidence bundle](../../types/evidence-bundle.md) and emits a [verifier assessment](../../types/verifier-assessment.md). The Gate host combines that assessment with deterministic checks. Operator argument/result contracts are owned by [local search](../../m1/op-local-search.md), [scholarly search](../../m1/op-scholarly-search.md) and [CodeSearch](../../m1/op-codesearch.md), not this inventory.

## Bound capsule execution graph

Generated from [M1 control flow](../../m1/control-flow.md). Every planned node binds work and Gate capsules. The diagram illustrates dependencies, not a concurrency promise.

<!-- generated:showcase-capsules -->
```mermaid
flowchart TB
  INPUT["Validated task data"] --> N1["Node 1: task-specific bound CC use"]
  N1 --> S1["Commit output and evidence"]
  S1 --> G1["Gate: host checks then shared verifier<br/>RSI mutable components: 0"]
  G1 -->|"advancing result only"| R1["Commit advancing Verification and release"]
  R1 -->|"accepted typed output"| N2["Node 2: task-specific bound CC use"]
  R1 -->|"accepted typed output when required"| N3["Node 3: task-specific bound CC use"]
  N2 --> S2["Commit output and evidence"] --> G2["Gate: host checks then shared verifier<br/>RSI mutable components: 0"] -->|"advancing result only"| R2["Commit advancing Verification and release"]
  N3 --> S3["Commit output and evidence"] --> G3["Gate: host checks then shared verifier<br/>RSI mutable components: 0"] -->|"advancing result only"| R3["Commit advancing Verification and release"]
  R2 --> JOIN["Dependent join: required inputs accepted"]
  R3 --> JOIN
  JOIN --> END["Next governed node or ordinary delivery"]
  G1 -->|"failure"| STOP["Halt entire run<br/>no next or sibling capsule starts"]
  G2 -->|"failure"| STOP
  G3 -->|"failure"| STOP
```
<!-- /generated:showcase-capsules -->

## Construction and optimization

- Build storage, runner, admission, broker and minimal fixtures first; then intent capsules and Gates, requirements and Gates, planner/validator/binder, then durable node continuation. Reconcile the old [build order](../../system/build-order.md) before coding. Add retrieval/Screening, Hypothesis/POC, scientific execution/evaluation/report, workstation/export, RSI and isolated experiments in dependency order. [Build order](../../system/build-order.md) owns prerequisites.
- Keep algorithm choices inside modules. Preserve output semantics, frozen policies, permission boundaries and evidence ordering when optimizing.
- Measure model calls separately from deterministic helper work. Use pinned fixtures and compare correctness before latency/cost. [Capability guide](../../m1/capability-designs.md) owns proposed optimization experiments; [benchmark materials](../../m1/benchmarking-material.md) records candidate material and restrictions.
- SkillFuzz capsule-set interaction analysis is deferred. Current contract checks establish interface compatibility, not semantic safety of every combination. See [library](../../capsule/library.md).

[Next: runtime and improvement](runtime-and-improvement.md)
