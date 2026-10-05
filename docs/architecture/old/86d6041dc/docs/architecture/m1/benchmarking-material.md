---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, ../../product/prd-m1-rsi-full.md]
provides: [research.benchmark_material_policy]
consumes: [cc.offline_rsi]
depends_on: [capability-designs.md, ../capsule/fixture-oracle.md, ../capsule/rsi-engine.md, ../system/benchmark-export.md, measurement-protocol.md]
tags: [m1, benchmarking, fixtures, evidence]
---

# Benchmark material and fixture preparation

This page owns material selection and preparation guidance. It records primary-source candidates inspected on October 5, 2026; it does not claim that datasets were imported, adapters implemented or benchmarks run. Source links below are discovery references; acquisition must pin the exact revision/archive hash and license before use. Public material supplies visible development checks and design patterns. It is not a hidden holdout merely because files are put in a private directory.

[Scientific measurement](measurement-protocol.md), [Saurav's external harness export](../system/benchmark-export.md) and [RSI oracle](../capsule/fixture-oracle.md) have separate authorities. This catalogue does not merge their scores or replace the frozen PRD's acceptance requirements.

## Material shortlist

| Material and primary source | Useful boundary | Borrowed pattern / candidate use | License and adoption disposition |
|---|---|---|---|
| [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/) and [license](https://github.com/HypothesisWorks/hypothesis/blob/master/LICENSE.txt) | Ranking, payload validation, arithmetic and protocol parsing | Generate edge values and shrink failures into small reproducible cases. Preserve the minimized case as a fixed fixture before any RSI session | Code MPL-2.0 except noted third-party files. Testing-library candidate, not a dataset. Pin package/license and compatibility before downstream installation; no runtime dependency required in product |
| [EvalPlus](https://github.com/evalplus/evalplus) and its [license](https://github.com/evalplus/evalplus/blob/master/LICENSE) | Code-generation correctness; sandbox/parser regression | Expanded tests illustrate why a few examples cannot establish code correctness. Use selected approved code tasks in a development-only adapter; generated task correctness is distinct from our single-patch scientific workflow | Repository code Apache-2.0. Dataset/source-specific notices must also be retained; public known tasks cannot serve as fresh hidden RSI evidence |
| [BEIR](https://github.com/beir-cellar/beir) and [dataset catalogue](https://github.com/beir-cellar/beir/wiki/Datasets-available) | Retrieval operators and evidence selection | Corpus/query/relevance-label separation and ranking metrics can inform fixture organization. Keep retrieval-quality results separate from source-byte/provenance correctness | Framework Apache-2.0; individual dataset licenses differ. Select and receipt one dataset, not the entire bundle by assumption |
| [Meta CRAG](https://github.com/facebookresearch/CRAG) | Partial/incorrect retrieval, grounded synthesis, unavailable evidence | Mock search APIs and answer-quality categories provide visible evidence-grounding scenarios. Adapt small approved cases to our ports instead of importing its full application stack | Project CC BY-NC 4.0. Treat as restricted acquisition pending intended-use/license confirmation; use the evaluation pattern without bundling data if permission is unsuitable |
| [Microsoft BIPIA](https://github.com/microsoft/BIPIA), [license/third-party notices](https://github.com/microsoft/BIPIA/blob/main/LICENSE) | Injection in abstracts, intake files, code comments and judge evidence | Indirect-injection tasks inform independently authored attacks against source/evidence boundaries | Code MIT; underlying task/context licenses differ and README identifies contexts requiring separate preparation. Archived upstream: pattern/reference candidate, not an assumed maintained dependency |
| [DSPy optimizer documentation](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md) | Conditional Screening text RSI | Separate candidate program, metric and examples; compare permitted prompt changes under the same inputs/settings | Design precedent. No optimizer package or unrestricted optimization mode is adopted. Frozen whitelist and oracle budgets remain binding |

BEIR reports relevance metrics such as nDCG/Recall for retrieval; these measure retrieval behavior, not whether a Research Brief or scientific claim is correct. EvalPlus also provides efficiency evaluation; its documented perf setup can require additional kernel/capability configuration. Do not copy that privileged configuration into the M1 generated-code sandbox. Any performance method needs its own trusted registration and validated security profile. See [BEIR evaluation](https://github.com/beir-cellar/beir) and [EvalPlus efficiency setup](https://github.com/evalplus/evalplus).

## Build the first useful corpus from our contracts

Start with project-owned synthetic cases. They fit the actual schemas, avoid external dependency installation and provide exact expected results for mechanics. Keep three distinct fixture kinds:

1. **Mechanical:** canonical input and expected output/error, source bytes, exact hashes and deterministic policy. Examples: tied eligible Screening cards, unknown dependency, wrong sample ordering, invalid reference, Gate save failure and duplicate publication.
2. **Semantic:** an independently authored task/evidence packet with criterion labels, exact supporting excerpts and rationale. Examples: a target quote that does not support the target, plausible but unrelated patch, unsupported report number and contradictory source claims. Model-produced labels are proposals requiring custodian adjudication, not self-authenticating ground truth.
3. **Boundary:** action/probe, expected denial or halt and evidence requirements. Examples: hidden fixture read, auth-volume read, forbidden egress, process surviving cancellation, plan permission widening and admission that falsely claims tests ran.

[Capability guide](capability-designs.md) supplies one case family for every active capsule. [Stories](../stories/README.md) provide connected examples; [system verification](../system/verification.md) owns invocation points and required failure observations. A full connected research fixture should include an authorized small repository, deterministic baseline/treatment, registered measurement method, complete raw stream and expected report evidence. An intentionally failing scientific case must still reach a faithful report when infrastructure passes.

## Acquisition and custody procedure

Before importing any external bytes, the curator records the primary URL, exact upstream revision, received archive/content hash, asset-level license, attribution, allowed use, source task IDs, transformation script hash and all derived file hashes. Preserve the original separately from adapted fixtures. This is a preparation receipt, not a new wire payload; [source policies](../policies.md) and oracle manifests own their respective formats.

For derived fixtures, preserve a lineage group identifying cases from the same source task/document/repository, semantic paraphrase or base program. Assign the whole group to one split. Byte-level disjointness alone cannot prevent near-duplicate leakage. Custodians inspect normalized source/task identities and transformations before freezing. A transformed public task remains public-derived; claim no model-training contamination guarantee.

The fixture custodian owns labels, split/freeze and private oracle installation. Capsule authors receive approved dev material only. Oracle-held loop/final cases, IDs, labels, salts and per-case comparisons never go to proposer/public prompts, Candidate bodies, public logs or benchmark export. A scoped oracle-private evaluation may supply the current case input to the candidate and its fixed model bridge call; it never supplies expected answers, labels, salts or comparator output to candidate/model context. Private captures remain oracle-owned. [RSI engine](../capsule/rsi-engine.md) owns minimum set sizes, baseline eligibility, lifetime/session queries, pairing, protected mutation paths and final action. Keep those numeric rules there instead of duplicating them here.

Saurav owns the external evaluation selection and harness. Provide configuration/library/source pins, safe model metadata, Gates, artifacts, timings, available usage and explicit missing telemetry through the existing export API. Hidden oracle material and credentials are excluded regardless of benchmark usefulness. Changing his future schema lands at the export adapter, not in every capsule payload.

## Evaluate improvements without changing the target

Freeze the suite, candidate/parent hashes, model configuration and scoring method before measurement. Keep hard contract correctness as a prerequisite; evaluate quality and resource use as separate dimensions. Faster incorrect ranking or a report omitting limitations is a regression. Record actual model calls and elapsed time; missing Codex token/money telemetry stays unavailable, not zero. Pin configured and served model identity when reported; a mismatch invalidates paired comparison under the oracle rule.

Latency results need environment identity, workload size, declared warm/cold preparation state and complete observations. Measure per-stage preparation and execution separately when possible so an index cache is not mislabeled as a model improvement. Do not claim statistical significance from one favorable timing or claim general scientific quality from general-purpose QA/code benchmarks. Any promotion still follows admission plus separate manual activation.

## Preparation completion evidence

The coding team should be able to identify an asset receipt, compatibility adapter, valid canonical fixture, expected outcome, split lineage, label custodian and independently callable invocation. The evidence must state whether it is authored, structurally validated, replayed or executed. A dataset link is not a completed fixture; an unrun sandbox probe is not a security pass. Once imported, link immutable manifests and real observed evidence from the relevant owner page rather than copying dataset descriptions into all stages.
