# Intent Compiler Benchmark Pilot Design Draft

Status: Draft v0.2 for CC owner feedback and benchmark preparation; repository status reviewed October 13, 2026
Date: October 8, 2026
Execution status: No implementation, campaign receipt or scored result is included in this repository record. The original October 9 target date is historical; a new date must be recorded after readiness is established.
Test family: IC TC01
Profile: Fixed M1 compiler-only evaluation

This pilot tests whether the Intention CC and Requirements CC faithfully convert a research request and permitted local resources into an independently checked, durably released Research Brief. It uses index maintenance as the technical research objective and evaluates the two work CCs, their handoff, and the enclosing compiler's release behavior. It supplies a design for the benchmark coding run; it contains no harness implementation.

This document is the development review package for the intent compiler pilot. The requesting researcher is the benchmark operator and owns fixture preparation, harness implementation, configuration, execution, and reporting. CC owner feedback focuses on capsule behavior and interface compatibility. Independent evaluation reviewers validate semantic references. The benchmark operator keeps exact held-out requests, source combinations, labels, and reference judgments in a separate evaluation package and freezes the reviewed cases, budgets, and schedule before scored execution.

## Scope and source authority

The benchmark requirements, objective shortlist and execution interface contract below are operator-local prerequisites. They are not bundled in this repository. Their original Windows locations are retained as provenance, not shared links or available execution inputs. Retrieve and pin them before treating this draft as an executable benchmark assignment.

The benchmark obligations come from Benchmark Requirements (`D:/Benchmarking Custom/BENCHMARK_REQUIREMENTS.md`; external prerequisite), especially B01–B17, CC01–CC05, SU01, SU04, and SU05. The recommended topic is RO01 in the Research Objective Shortlist (`D:/Benchmarking Custom/RESEARCH_OBJECTIVE_SHORTLIST.md`; external prerequisite).

Execution and evidence must follow the Intent Compiler Benchmark Interface Contract (`D:/Benchmark Test Run 1/INTENT_COMPILER_BENCHMARK_INTERFACES.md`; external prerequisite). The checked implementation copy is the Verification contract (`D:/Benchmark Test Run 1/jiuwenswarm-verification/docs/code/Missions/M0/source/Verification/INTENT_COMPILER_BENCHMARK_INTERFACE_CONTRACT.md`; external prerequisite). The exact supplied architecture package governs evaluated product behavior and serialization. For current design navigation use the maintained [compiler build scope](../../design-package/builds/intention-compiler/README.md), [Intent and Requirements fields](../../design-package/reference/intent-and-requirements.md) and [verification obligations](../../design-package/reference/compiler-verification.md). Original participant-local locations: compiler build scope (`D:/Benchmark Test Run 1/jiuwenswarm-verification/docs/code/Missions/M0/source/Architecture_context/design-package-compact/builds/intention-compiler/README.md`; external prerequisite), Intent and Requirements fields (`D:/Benchmark Test Run 1/jiuwenswarm-verification/docs/code/Missions/M0/source/Architecture_context/design-package-compact/reference/intent-and-requirements.md`; external prerequisite), and verification obligations (`D:/Benchmark Test Run 1/jiuwenswarm-verification/docs/code/Missions/M0/source/Architecture_context/design-package-compact/reference/compiler-verification.md`; external prerequisite).

Pin the exact source/build package for the evaluated implementation at freeze. Resolve disagreements against that package and record any agreed amendment. Do not invent endpoint names, serialization, verdicts, or a replacement compiler to satisfy the benchmark.

The external node is the Intention Compiler. It contains two work subnodes and their distinct verification boundaries. Intent IR is an intermediate; accepted Research_Brief.json is the external output. The two work CCs do not imply only two CC identities or two model calls: verifier CCs and their invocations must also be recorded.

Run the actual configured model through the protected client and compiler path. No downstream Search, Screening, Hypothesis, scientific experiment, Delivery, or RSI runs in this pilot. Scores describe compiler performance and partial composition, not full research completion or dynamic capsule selection. The current client contract does not establish standalone work-CC evaluation; subnode results are observations within the governed compiler run.

## Research objective and compiler obligation

**Recommended research objective:** Investigate whether incremental inverted-index updates reduce update latency relative to full rebuilds on a supplied document-change workload while preserving retrieval correctness after additions, edits, and deletions.

SQLite FTS5 documents incremental maintenance/merging and rebuilding, providing a concrete source for this systems-research comparison. Optimization of existing segments and rebuilding the index are distinct operations. The objective concerns their behavior on a controlled workload; it does not establish a new scientific discovery. [SQLite FTS5 documentation](https://www.sqlite.org/fts5.html#special_insert_commands)

The compiler must preserve the comparison, requested outputs, data roles, constraints, targets, uncertainty, and evidence obligations. It must not select a winning method, assert a measured speedup, register an unrequested experiment protocol, or invent a numeric target. Uncertain scientific success is compatible with an actionable research request.

Keep two kinds of acceptance distinct. Compiler acceptance means faithful, complete, attributable Intent and Brief plus valid release. Eventual research acceptance means satisfying the scientific obligations represented by that Brief. No experiment results are needed to establish compiler acceptance.

## Execution boundary and required interfaces

The productive path is:

Qualified original request and permitted resources → Intention work → deterministic checks → Intent verifier → protected Intent acceptance → Requirements work → deterministic checks → Requirements verifier → protected Requirements acceptance → enclosing node finalization → durable external Brief release.

Requirements must consume the exact accepted Intent and permitted original context. It cannot consume an unaccepted candidate, repair an upstream misunderstanding silently, or begin before durable Intent acceptance. Node finalization reuses recorded assessments and adds no third semantic-review generation.

Use the existing interfaces for readiness/configuration, protected input qualification/submission, request reconciliation, lifecycle status/cancellation, and authorized evidence export. Export candidate records on failed and blocked attempts. A client disconnect must not cancel or replay a run; a repeated client request ID must reconcile without duplicate execution. These client behaviors are required capabilities; the core semantic campaign below does not prove every transport or restart behavior.

| Object | Required version from the interface contract |
| --- | --- |
| Intent IR | 1.0.0 |
| Research Brief | 2.0.0 |
| Gate decision | 2.0.0 |
| Subnode Execution Contract | 1.0.0 |
| Enclosing Node Execution Contract | 2.0.0 |

Resolve all referenced schemas and other objects from the pinned architecture catalog. Preserve actual gate verdict enums and readiness claims; benchmark outcome labels are reporting metadata, not new product fields. A producer's ready flag and a verifier's overall pass are insufficient without mandatory findings, subject checks, and protected acceptance.

## Development and held out packages

| Material | CC owner and development use | Held-out evaluation handling |
| --- | --- | --- |
| Design, interfaces, general criteria, topic family | Included in the development review package. | Same obligations govern evaluation. |
| Test case request, source files, expected meaning, detailed diagnostics | Development fixtures and debugging references. | Never reuse verbatim as protected evidence. |
| Exact held-out requests, resource combinations, task-specific boundaries | Withhold before model/capsule freeze. | Provide ordinary task inputs only for the scored run through protected intake. |
| Reference labels, accepted semantic alternatives, defect annotations, oracle logic | Development test cases include expected outcomes and reference checks. | Benchmark operator controls them after independent reference review; exclude from producer, author, and evaluated verifier contexts. |
| Detailed held-out feedback | No development access while the fixture remains protected. | Authorized reviewers may inspect; disclosed fixtures become development material for later comparisons. |

The evaluated system may receive its architecture-owned checking criteria. Those criteria are distinct from the benchmark's secret case labels and reference answers. Keep the private evaluation package out of the CC owner's shared repository, model prompt, compiler resource directory, container image, and accessible workspace mounts. A directory called private does not itself provide isolation.

Two independent reviewers must label evaluation inputs and permissible outcomes and resolve disagreements before freeze; fixture authors/reviewers must be independent of the tested capsule's author. Fresh evaluation instances need different task structures and evidence combinations, not just different numbers, names, or seeds. The public topic can remain index maintenance, but this narrow pilot alone cannot establish transfer to unrelated research topics.

Maintain development, protected evaluation, and future milestone-tracking membership explicitly. Milestone tracking is deferred for this first campaign; reserve separate fixtures before making recurring progress claims. If an independent protected package is not ready tomorrow, run development smoke tests and report diagnostic results without a held-out score.

## Test case

The following request and interpretation define the test case. Prepare the named resources before executing this case.

> Investigate whether incremental inverted-index updates reduce median update latency compared with full rebuilds on the supplied local document-change workload, while preserving the same retrieved document IDs after additions, edits, and deletions. The desired improvement is at least 20% relative to the full-rebuild baseline; do not assume that it is achievable. Use CPU-only execution, no GPU or cloud compute, and no external dataset downloads. The eventual experiment must use at most 1 GiB of peak memory. Treat documents.jsonl, changes.jsonl, and queries.jsonl as validation data, and workload_notes.md as a reference document explaining their format. Deliver a comparison report and a per-batch results table, including negative findings and limitations. A chart is optional. I have not selected batch sizes or a statistical procedure.

The benchmark operator prepares tiny, readable, internally consistent resources and registers them through the supported intake path. The notes identify document IDs, query IDs, operation order, and file formats. Qualification must record which original files and extracted text are accepted and their roles. Avoid a missing-resource defect in a semantic case.

| Meaning to preserve | Development acceptance guidance |
| --- | --- |
| Purpose and comparison | Investigate incremental updates versus full rebuilds; neither is a declared winner. |
| Correctness | Preserve retrieved document IDs after each operation type, including deletions. Do not substitute only schema validity or a relevance score. |
| Target | Preserve at least 20% lower median update latency relative to the baseline. Under the catalog's factor convention this is at most 0.8 times baseline, not a factor of 0.2 or an absolute latency of 20 ms. Equivalent supported units/representations are permissible. |
| Scientific uncertainty | Failure to reach the desired gain remains a reportable negative finding, not evidence that the request was unusable at intake. |
| Limits and scope | CPU-only and local resources; no GPU/cloud/downloads. At most 1 GiB applies to scientific execution, not the compiler's own memory ceiling. Preserve value, unit, comparison, and scope. |
| Resources | All three data files retain validation_data roles; the notes retain reference_document status. Names/references resolve to the qualified supplied objects. |
| Outputs and preference | Report and results table are mandatory; chart stays optional. Accepted completion must require attributable evidence and limitations. |
| Omissions | Do not invent batch sizes, repetitions, statistical tests, or an experimental success verdict. Methodology belongs to later Hypothesis work unless explicitly requested. |

Intent IR must attribute meaning to actual source spans. Offsets use Unicode code points and exclude the ending position. Research Brief must link obligations, evidence expectations, target metrics, resources, and any authorized assumptions through the catalog's fields. Accept semantic equivalence, not byte-for-byte matching to a single reference artifact.

CPU-only is explicit in this example. The architecture's current default for omitted hardware is single_gpu, with protected authority and affected-field attribution. Do not overwrite the explicit CPU request or silently change that default to make this pilot fit. Omitted-hardware/default behavior is deferred to a separately qualified fixture.

## Controlled cases in the pilot family

The benchmark operator prepares a development instance and coordinates independent preparation of an evaluation instance for each case class. The table publishes expected behavior categories; exact evaluation texts, source spans, labels, and allowed semantic judgments remain private.

| Case | Controlled condition | Expected behavior |
| --- | --- | --- |
| P1 Explicit actionable request | A concrete purpose/result, declared comparison and resource roles, quantitative target/limit, scope exclusions, and an optional preference. | Faithful accepted Intent and complete Brief; correct unit/comparison/scope; both work gates and node release persist. |
| P2 Actionable request with optional omissions | Clear purpose/result and sufficient permitted context, but no numeric improvement threshold and no selected experiment protocol. Retain explicit CPU-only limits. | Complete compilation with supported qualitative targets and omissions. Do not invent a percentage/procedure or demand nonessential clarification. Apply only authorized defaults with evidence. |
| H1 Unknown purpose or result | A nonempty topic-only or materially ambiguous request that intake can qualify, without enough purpose/result for Requirements. | Preserve the uncertainty in candidate Intent; obtain a non-advancing Intent decision; no Requirements work or external Brief release. End headlessly with an actionable reason. |
| H2 Contradictory mandatory constraints | An otherwise valid request containing mutually incompatible required conditions with no priority or authorized resolution. | Identify the exact contradiction and its source support; halt at the Intent boundary; do not waive, default away, or repair either condition. No Requirements work or external Brief release. |

P1/P2 are productive cases; H1/H2 are expected-halt cases. Keep their scores separate. An infrastructure error is not a correct semantic halt, and an accidental intake failure cannot demonstrate ambiguity detection. Review each H case to ensure the intended conflict is the first relevant blocking condition.

The core campaign does not inject producer/verifier outputs or mutate accepted artifacts through a client bypass. Faults such as stale evidence, malformed assessments, or failed persistence require an approved isolated staging profile and separate fixtures. They remain outside this first campaign's coverage, although natural occurrences must be recorded.

## Independent acceptance checks

All applicable checks are mandatory for full success. Deterministic checks assess mechanics; independent human judgments assess meaning. Product verifiers are outputs being assessed, not the independent benchmark oracle. The proposed authoritative model-judged share is zero. Any later model-based scoring requires B16/VF07 eligibility before use.

| Check | Required evidence and acceptance obligation |
| --- | --- |
| A1 Qualification and identity | Original text/files and qualified resources are traceable and immutable; correct request/run/source relationships; pins, admission, implementation hashes, contracts, and schema versions match the validated configuration. |
| A2 Structural correctness | Intent/Brief satisfy the catalog schemas; source spans and identities resolve; local IDs and requirement links are valid; input roles, typed constraints, assumptions, and affected-field pointers are coherent. |
| A3 Intent fidelity and usability | All material requested meaning is preserved without unsupported methods/targets, scope widening, promoted preferences, suppressed contradictions, or invented purpose. Readiness/uncertainty agrees with the independent case judgment. |
| A4 Requirements fidelity and completeness | Brief preserves the original qualified request and accepted Intent; requirement/preference split, metrics, limit scopes, deliverables, acceptance/evidence obligations, resources, and default authority are sufficient and supported. No unsupported experiment protocol or measured conclusion. |
| A5 Exact handoff | Requirements starts after durable Intent acceptance and consumes that exact subject. Each verifier assesses the correct candidate and original/upstream evidence. Candidate versus accepted references remain distinguishable. |
| A6 Gate and release integrity | Assigned findings are complete; deterministic failures prevent inappropriate verifier spend; malformed/nonpassing assessments cannot advance. Release follows both work acceptances and aggregate finalization, with the exact Brief hash and durable records. |
| A7 Halt correctness | For H1/H2, the candidate meaning and reason identify the intended defect; the halt is semantic and finite; no Requirements invocation, replacement artifact, retry, or external Brief release occurs. |
| A8 Limits and evidence | Hardware readiness, actual invocations, timing, effects, and retained success/failure evidence are sufficient to assess the run. No protected-answer access, unauthorized effect, replay, widened permission, or hidden model substitution. |

Before scoring, validate deterministic oracles against known-good, known-bad, and boundary examples. Two reviewers independently judge semantic cases using source-supported required/forbidden propositions and permissible alternatives, then resolve disagreements. Unresolved ambiguity prevents that fixture from entering scoring. Grade observed raw candidates separately from the product gate's verdict, so a faithful artifact that is falsely blocked remains visible diagnostically.

For an invalid accepted Intent, mark the upstream failure and propagated consequences. Requirements matching bad upstream meaning does not rescue compiler success. Subnode diagnostics must distinguish absent execution, upstream impairment, artifact defects, and false verifier blocking; they do not establish isolated-CC causal performance.

## Proposed configuration and budgets

Freeze one configuration first. Request gpt-6.1-sol as the benchmark baseline only through an approved supported model path; record actual provider/model/adapter and settings for every work and verifier call. If that baseline is unavailable, record the blocked configuration. An explicitly declared alternative can support a separate diagnostic pilot; no silent fallback.

| Resource or action | Proposed pilot ceiling |
| --- | --- |
| Host | Huawei MRGF-X default, subject to actual inventory; CPU-only local compiler runtime; no GPU-dependent experiment or cloud GPU. Distinguish any remote model-service host from the local runtime. |
| Concurrency | One benchmark attempt at a time. |
| Input | At most 1 MiB of qualified text and 5 MiB of registered local resources per case; no literature search or dataset acquisition during scored compilation. |
| Memory | At most 2 GiB combined tracked compiler, adapter, and local evaluation processes above recorded infrastructure baseline; at least 4 GiB available before dispatch. Confirm process/container accounting. |
| Time | At most 8 minutes from preflight through durable terminal evidence export per scheduled attempt, including halt cases. |
| Work invocations | At most one Intention generation and one Requirements generation. Requirements remains zero on a correct H1/H2 halt. |
| Semantic verification | At most one Intent-verifier and one Requirements-verifier generation. No recursive verifier or third semantic node review; no verifier after invalid producer structure. |
| Total model calls | At most four logical calls on the productive path. Record provider requests, tool/child calls, and any unavailable accounting separately. |
| Storage | At most 250 MiB new retained run evidence per attempt; at least 1 GiB free before an attempt, plus confirmed campaign capacity. |
| Tools and effects | Qualified local inputs and declared writes; configured model service through the protected bridge. No arbitrary network, package installation, experiment execution, CC mutation, or production-policy change during a scored attempt. |
| Repair and intervention | Zero automatic repair, retries, replay, rebinding, or hidden model substitution. Humans prepare fixtures and review results outside execution; an intervention cannot rescue a scored attempt. |

These are proposed campaign limits, not existing implementation guarantees. The benchmark operator verifies profile enforceability and feasibility against the implementation and readiness evidence before freeze. Record unavailable token/cost/resource fields with reasons rather than zero. Mandatory limit or readiness failures stay visible; do not loosen a frozen limit mid-campaign to obtain success.

Before every attempt and repeat, persist timestamped actual host identity, CPU/architecture/cores, total and available RAM, accelerator presence/absence, OS/runtime/dependency versions, free storage, enforcement/accounting support, and concurrent workload state or explicit unknown. Link the record to the run manifest. The intake adapter need not profile hardware itself; protected readiness/evidence and the independent driver supply the inventory.

## Procedure and evidence

The benchmark operator performs the following steps and coordinates independent reference review. CC owner feedback addresses product-contract compatibility; benchmark preparation and execution remain with the operator.

1. Confirm reviewed contracts, concrete client commands, actual admitted work/verifier identities, supported schemas/profile, readiness, and independent reference-binding validation. Pin the build and fixture/oracle versions; allocate each scheduled attempt before preflight.
2. Prepare and validate development fixtures. Execute one smoke attempt per class, check raw exports and independent diagnostic judgments, and resolve harness defects before evaluation freeze.
3. Independently prepare protected evaluation fixtures; record source hashes, split membership, judgments, limits, and schedule. Freeze implementation/model/settings and prevent protected references from entering evaluated contexts.
4. Submit through the protected client. Capture exact input qualification, submission/reconciliation receipts, run status, and stage events. Allow no interactive clarification loop or automatic repair.
5. Export candidates, check plans/results, assessments, gate decisions, consumed-input hashes, durable acceptances, finalization/release, actual call/configuration observations, and error/absence reasons. A successful HTTP response or valid JSON alone is insufficient.
6. Independently grade applicable checks, record earliest demonstrated failure and downstream consequences, then calculate separate productive and halt results. Preserve the product decisions even when the oracle disagrees.

Required run exports must cover original/qualified sources, candidate and accepted Intent/Brief where present, all work/verifier identities and observations, effective node/subnode contracts, schema/admission/implementation pins, checking assignments and typed findings, durable ordering/state, hardware/limits/effects, model telemetry, and a versioned manifest of readable files. Missing artifacts must have explicit reasons, including never invoked or persistence failure; no fabricated accepted reference.

Keep the independent scorecard outside compiler state. Every scorecard check must identify its authority, observed evidence location, finding, rationale, and applicability. Failed, timed-out, rejected, and environment-blocked scheduled attempts remain in campaign records.

## Metrics and repeat schedule

**Primary metric:** productive compiler success = fully successful P1/P2 attempts / all scheduled P1/P2 attempts with independently validated compatible bindings and valid inputs. Full success requires A1–A6 and A8, including durable external release. Retain timeouts and environment blocks in this scheduled denominator, even before invocation. Invalid fixtures are benchmark defects and must be reported; any replacement creates an explicit new campaign revision.

**Expected-halt accuracy:** fully correct H1/H2 attempts / all scheduled H1/H2 attempts, using A1–A3 and A5–A8 as applicable. Correctly halted cases never inflate productive success. Report each class separately, especially false release on H cases and false blocking on productive cases.

Report Intent artifact fidelity over scheduled productive attempts; absence counts as failure. Report Requirements fidelity both over scheduled productive attempts and conditionally over actual invocations supplied with independently correct accepted Intent. Show not-run and upstream-impaired counts rather than presenting conditional success as whole-system effectiveness. Also report handoff/release violations, gate/oracle disagreements, elapsed time, actual model calls, peak tracked memory, evidence size, and reliable usage/cost.

Proposed first campaign: four development smoke attempts, then three preregistered repeats of each of four independently authored evaluation cases. This gives 4 development attempts and 12 evaluation attempts per configuration: 6 productive and 6 expected-halt evaluation attempts. At the ceilings, all 16 attempts reserve up to 128 minutes and 4,000 MiB of new evidence. Human preparation and adjudication time is additional. Confirm capacity before scheduling.

Repeats of one case are not independent task families and do not prove broad generalization. Report counts/fractions and clustered uncertainty where defensible; avoid precision claims from the small sample. Development versus held-out rates are descriptive when structures differ. If comparing builds with and without Spec Kit, pin both, use matched fixtures/model/profile/hardware and balanced order, retain paired results, and double the campaign allowance. Such a comparison is optional and does not make Spec Kit a product dependency.

## Requirement traceability and coverage limits

| Requirement | Coverage in this pilot |
| --- | --- |
| SU01 | Source identity/roles, purpose, constraints, targets, uncertainty, and faithful Research Brief compilation. Source-embedded redirection challenges need a separate future fixture. |
| CC01, CC05 | Correct externally validated fixed bindings, actual admitted identity/version/hash, contracts, effects, and provenance. No dynamic selection claim. |
| CC02 | Independently authored evaluation requests with optional omissions and contradictory evidence/meaning within one technical topic. Cross-topic transfer remains unmeasured. |
| CC03 | Real accepted Intent → Requirements handoff and compiler release. No standalone work-CC profile or full research closure is claimed. |
| B01–B09, B11–B12 | Frozen case specifications, independent references, split isolation, explicit denominators, retained failures, pinned comparisons, and explainable scores. |
| B10, B13–B17 | Fast computer-science pilot, local budgets, fixed M1 applicability, no authoritative model judging, and hardware inventory before every attempt. Long-horizon behavior is unmeasured. |
| SU04, SU05 | Observed bounds, finite headless halt, gates, persistence, configuration, and evidence. Dedicated cancellation/restart/transport-fault tests remain separate coverage. |
| CC04, CC06 | Broad catalog faults/stress and automated capsule authoring are outside this campaign. |

## Pilot responsibilities and readiness checklist

The benchmark operator owns this checklist and the decision to freeze and run the pilot. CC owner feedback is limited to capsule behavior, interface compatibility, and implementation capabilities. Independent evaluation reviewers validate the hidden reference judgments; the operator controls their storage and use. The operator records each decision with reviewer, date, evidence, and any revision; this draft is not an approval record.

| Readiness item | Responsible actor | Decision or evidence needed before scored execution |
| --- | --- | --- |
| Supported execution | Benchmark operator | Verify compiler-only entry, concrete submit/status/export commands, schema dependencies, and installed build identity. |
| Work and verifier CCs | Benchmark operator | Collect and pin admitted declarations, identities, versions, loaded implementation hashes, adapter/provider details, and checking configuration from the evaluated build and exports. |
| Meaning and resources | Benchmark operator with independent reviewers | Verify source-span convention, original/extracted text handling, resource qualification/roles, accepted-Intent handoff, defaults, and typed constraint scope. |
| Halt semantics | Benchmark operator with independent reviewers | Verify actionable optional omissions may advance; unknown purpose and contradictory mandatory conditions halt without Requirements dispatch or dialogue. |
| Acceptance and release | Benchmark operator | Inspect candidate/accepted separation, typed findings, both protected decisions, aggregate finalization, durable release, and retained failure evidence. |
| Budgets | Benchmark operator | Verify memory accounting, time/call/effect enforcement, available local capacity, and model support; revise proposed ceilings before freeze if necessary. |
| Reference judgments | Independent evaluation reviewers | Validate permissible semantic outcomes and oracle checks; resolve disagreements before scoring. |
| Benchmark preparation and execution | Benchmark operator | Build the harness, prepare and secure fixtures, freeze validated manifests/configuration/repeat order, run the campaign, and report evidence and scores. |

Before scheduling execution, the benchmark operator reviews the design, gathers CC owner feedback, chooses the initial configuration and identifies missing interfaces or evidence. The operator then builds the external harness, validates development cases and oracles, freezes independently reviewed evaluation instances and runs the ready campaign. Record the actual campaign date with its receipts. An unresolved dependency produces an explicit blocked or diagnostic outcome, not a weakened scored profile.
