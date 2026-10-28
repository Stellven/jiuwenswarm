# AI4Research RSI Engine M1 Design v0.2

**Version:** v0.2  
**Date:** October 7, 2026  
**Updated:** October 14, 2026  
**Product requirements:** [AI4Research full-system PRD](PRD%20-%20AI4Research.txt), especially Sections 4.4 and 6.11  
**Companion:** [RSI Shared Interfaces v0.2](RSI%20Shared%20Interfaces%20v0.2.md)

M1 uses a fixed offline improver to diagnose a capsule implementation gap, generate one bounded patch at a time, and select one candidate for independent final assessment. The initial strategy is failure-guided patch generation through the existing audited model bridge. Target-specific execution and correctness checks come from approved adapters and profiles. The engine contains no capsule-name or research-stage logic.

The research workflow supplies immutable capsule versions and approved observations. RSI returns an inactive candidate and reconciled evidence. Admission and human activation determine whether future research runs use it. Research execution remains independent of RSI availability.

This is the single RSI development handoff for humans and coding agents. The full-system PRD owns product scope and requirements; this design supplies the RSI implementation behavior, acceptance evidence, and version defaults. The companion shared-interface document defines the cross-component agreements for this version. RSI-specific acceptance identifiers RSI01–RSI15 are defined in Section 13.

An approved document version is adopted for design and implementation. Revisions are reviewed by version. Consolidation does not approve scope changes or numeric defaults, register coding tasks, or replace the maintained architecture package. Where this design conflicts with the full-system PRD or an adopted shared contract, record and resolve the conflict before dependent implementation; do not silently override it. Section 14 identifies the decisions to reconcile and freeze.

## 1 Design decisions and source alignment

| Decision | M1 realization | Basis |
| --- | --- | --- |
| Execution boundary | Separate offline job and isolated candidate execution on the authorized local host; reuse shared platform modules. | Architecture placement and offline RSI responsibilities. |
| Capsule generality | Profile and registered adapters determine the target; no required capsule name. | Generic acceptance in this version; named-target commitment requires source reconciliation in Section 14. |
| Search strategy | One fixed model-guided diagnosis followed by sequential reflection and patch proposals. | Detailed realization of the bounded proposer/controller architecture. |
| Mutable surface | One authorized code component; conditional implementation text through a bounded adapter. | Full-system PRD mutation limits and the M1 scope below. |
| Selection | Mandatory checks first, then hidden-loop test-pass counts; time breaks exact score ties. | Existing M1 scoring boundary. |
| Final decision | One sealed finalist compared with the original parent; meaningful gain, independent evidence, and zero observed protected regressions required. | Full-system PRD, Section 13 acceptance criteria, and benchmark direction. |
| Feedback | Loop feedback contains only passed, total, and queries left; final details never enter proposal context. | Existing offline RSI architecture. |
| State and evidence | Shared protected storage conventions; SQLite session authority and portable append-only evidence projections. | Architecture D6 and D9; RSI state must not become research release authority. |
| Adoption | Human initiates admission review; trusted admission checks and a separate human activation select future-run standing. | Capsule library lifecycle and full-system PRD. |

The parameter values below define this version's defaults and are subject to the adoption decisions in Section 14. The architecture's existing evaluation caps are carried forward for review, with their source disposition explicitly listed in Section 14. No proposer may change any parameter during a session.

The initial strategy keeps each change and selection decision inspectable, uses the available model execution path, and avoids a new optimizer dependency. Its limits are deliberate: bounded local patches may fail to find a useful improvement, loop measurements can be noisy, and binary checks cover only declared obligations. Final evaluation, honest no-gain outcomes, and separate cross-capsule measurements make those limits visible. The pilot should establish whether this strategy is effective before more elaborate search becomes product scope.

### Purpose and system boundary

RSI turns an attributable capsule failure or measurable quality gap into a bounded experiment. It must explain when improvement is justified, which authorized implementation change could address the diagnosed mechanism, and whether independent evidence shows that the child helps. No-gain, inconclusive, blocked, and failed outcomes remain valid results.

RSI belongs to M1 Delivery Phase 2, Local-Isolated RSI Validation. The Phase 1 registry, runner, evaluator, and evidence foundations are integration prerequisites; preparing the engine earlier does not remove them.

The full-system PRD currently requires code improvement of `rank_opportunities` inside `screening_capsule` and conditionally supports its text implementation. This version defines generic acceptance based on eligible target profiles, with those helpers available as pilot examples. The engine must remain generic under either release choice. Removing the named-target release commitment requires corresponding updates to the full-system PRD, architecture, and benchmark; it is unresolved until those governing sources are aligned.

### M1 scope

| Included in M1 | Required behavior |
| --- | --- |
| Offline opportunity intake | Read frozen, authorized observations and benchmark evidence; accept an operator-selected target. |
| Generic target onboarding | Validate a standard profile without changing the engine for a capsule name or research stage. |
| Bounded implementation changes | Support an explicitly authorized code component. Support implementation text when a bounded headless execution adapter is available. |
| Sequential improvement search | Propose and assess one candidate at a time within a frozen session budget. |
| Independent evaluation | Run mandatory checks, visible development tests, capped hidden-loop assessment, and terminal hidden-final assessment. |
| Evidence and review | Preserve all attempts and produce an inactive child, comparison report, and admission handoff. |
| Activation and rollback integration | Demonstrate human-controlled activation of an admitted version and rollback for future runs. |
| Generalization assessment | Onboard unrelated targets through profiles and measure transfer when held-out capsule types are available. |

M1 excludes runtime capsule mutation, live or shadow production A/B tests, autonomous repair of an executing research run, automatic activation, improver self-modification, model-weight training, router optimization, dependency re-pinning, contract changes, whole-workflow evolution, multi-capsule optimization, multi-file code evolution, and population search.

These boundaries limit the permitted **change**, not the capability identity. A retrieval capsule, research skill, analytical tool, or other capsule can be eligible if its authorized implementation component is executable and independently measurable through the standard profile.

Remote services and composites are not assumed to expose an editable local implementation. The engine must report an unavailable mutation surface or adapter explicitly. A composite's graph, wiring, member bindings, and verification obligations remain fixed; an eligible constituent can be targeted separately. Arbitrary remote-service changes or composite rewiring are outside M1.

### Terms and invariants

| Term | Meaning |
| --- | --- |
| Capability Capsule or CC | A reusable capability declaration and its pinned implementation. It is distinct from a workflow node and a Node Execution Contract. |
| Parent | The immutable capsule version used as the session's baseline. |
| Child or candidate | A separately identified implementation derived from an authorized parent. It is inactive until admission and human activation. |
| Improver | The fixed engine, proposer policy, and search behavior that generate and select candidate changes. |
| Target profile | The target-specific configuration and trusted adapters supplied through a common interface. It describes an improvement task; it does not grant authority. |
| Referee | The independent checks, oracles, verifier, scoring policy, and protected evaluation controls that assess candidates. |
| Session | One bounded offline improvement job with a frozen parent, profile, improver, evaluator, and budget. |
| Capsule generalization | A child performs better on inputs excluded from its optimization feedback. |
| Improver generalization | A frozen improver produces useful children for capability classes excluded from engine development and tuning. |

The following invariants apply to every session:

- **Offline isolation.** Proposals and candidate execution occur in a separate workspace. Active capsules and running research graphs remain pinned.
- **Contract preservation.** Ports, required output semantics, preconditions, dependencies, effects, guarantees, checks, and applicable budgets retain their admitted meaning. Version and implementation hashes may change through trusted packaging.
- **External authority.** The host enforces mutation, tools, network, effects, and resources. A declaration, prompt, or `evolution.frozen` entry cannot grant permission.
- **Protected referee.** Evaluation, security, promotion controls, and their transitive behavioral dependencies remain outside the mutation surface. A shared helper used by the referee is protected even if the work capsule also imports it.
- **Frozen comparison.** Parent, splits, scoring, model route, execution settings, and budget are fixed before optimization. Mid-session drift invalidates the comparison.
- **Evidence before improvement claims.** Self-reports and visible-test gains cannot certify a child.
- **Human activation.** A qualifying candidate and an admitted version both remain inactive until a human activates the version.

## 2 Modules and authority

```mermaid
flowchart LR
    Workflow[Research workflow] --> Capture[Shared capture and evidence store]
    Capture --> Export[Approved development export]
    Registry[Admitted capsule registry] --> Profile[Target profile and immutable parent]
    Export --> Intake[Opportunity qualification]
    Profile --> Intake
    Intake --> Controller[Trusted offline session controller]
    Controller --> Context[Scoped proposal context]
    Context --> Bridge[Audited model bridge]
    Bridge --> Patch[Untrusted patch proposal]
    Patch --> Guard[Trusted mutation guard]
    Guard --> Dev[Isolated development execution]
    Dev --> Controller
    Controller --> Oracle[Protected oracle and independent referee]
    Oracle -->|Bounded loop counts| Controller
    Oracle --> Review[Protected final assessment and review package]
    Controller --> Review
    Review --> Admission[Human initiated admission]
    Admission --> Activation[Explicit human activation]
    Activation --> Registry
```

The controller is trusted orchestration code, not generated capsule code. It owns sequencing, frozen manifest checks, stop conditions, and requests to protected services. It cannot access hidden labels, rewrite evaluation policy, or activate a version. The model proposer receives a bounded view and returns data; it has no direct filesystem, process, evaluation, or registry-write tools.

| Module | Responsibility | Authority limit |
| --- | --- | --- |
| Opportunity qualifier | Normalize authorized observations, group failures, and establish readiness/headroom. | Cannot relabel hidden cases or declare a self-report to be ground truth. |
| Diagnosis and context builder | Assemble visible evidence and request a structured diagnosis and proposal. | Cannot expose protected evaluation, unrelated history, or credentials. |
| Session controller | Run the fixed search and persist state transitions and selection decisions. | No security-policy changes, hidden-case reads, or activation authority. |
| Mutation guard | Apply a patch to a fresh isolated copy and verify the full effective change. | Uses a host-issued mutation grant; target prose cannot expand it. |
| Shared runner adapter | Execute an exact parent or candidate under enforced offline authority. | No writes to live project assets or undeclared effects. |
| Oracle and referee | Own hidden execution, checks, query ledger, terminal sealing, and authoritative scores. | Candidate and proposer content cannot change scoring or custody. |
| Result assembler | Reconcile identities, evaluation receipts, and budgets into audience-specific reports. | Cannot invent an assessment or substitute a candidate hash. |

Trusted adapters are admitted, pinned code. A profile references an adapter registration, not an arbitrary shell command or executable supplied by the proposer. Domain-specific oracles remain outside the target's mutable dependency closure.

## 3 Target onboarding

An eligible target needs an immutable admitted parent, a host-authorized mutable component, an invocation adapter, mandatory behavior checks, independently owned evaluation, measurable headroom, and a resource-qualified execution environment.

The profile is a separate object describing this offline improvement task. It is not a new capsule declaration schema. It references the capsule's actual identity, contract, and dependencies; trusted packaging uses the reconciled capsule format when creating a child version.

The profile binds:

- Parent declaration, implementation, dependency closure, and immutable contract.
- Mutation grant, component locator, code or text modality, and trusted change validator.
- Invocation template, model route where applicable, effect restrictions, and environment snapshot.
- Visible development suite and permitted observation export.
- Opaque oracle registration, scoring policy, and protected regression obligations.
- Proposal context recipe and fixed search policy.
- Budgets, final sampling protocol, qualification rule, and terminal reserve.

Readiness returns specific reasons: unsupported adapter, unavailable implementation, incompatible environment, insufficient oracle coverage, protected-closure overlap, undeclared effects, failed parent mandatory behavior, or insufficient headroom. Remote services without an authorized editable implementation are unsupported targets. Composite topology remains fixed; an eligible constituent can be improved as its own target.

A second capsule with a different responsibility must run through the same engine build. Target-specific fixtures and adapters may differ; the search/controller implementation does not. Mock execution demonstrates interface behavior only and is labelled accordingly.

## 4 Telemetry and development data

### Sources and collection

| Producer | Capture at source |
| --- | --- |
| Workflow harness | Requested/effective configuration, graph and contract identities, node transitions, halt reasons. |
| Capsule runner | Invocation start/end, exact implementation and inputs, outputs, tool/effect observations, duration, errors. |
| Model bridge | Actual route, endpoint/profile identity, call outcome, latency, and reliable available usage. |
| Check runner and gate host | Check findings, raw verifier assessment, final decision, and exact evidence references. |
| Research benchmark runner | Baseline/treatment artifacts and raw measurements under the frozen scientific protocol. |
| RSI controller and referee | Proposal and evaluation actions, candidate lineage, scores, counters, selection, and terminal outcomes. |

Correlation is assigned by trusted infrastructure. Preserve run, node, invocation, and execution attempt for workflow observations, and session, proposal attempt, candidate, and evaluation identities for RSI. An RSI proposal attempt is distinct from a candidate execution attempt and from a transport retry.

Emit start records before dispatch and terminal records after completion or an observed fault. Preserve partial evidence during execution where supported; do not depend on a successful end-of-run workspace snapshot. Capture exact inputs before mutable upstream assets or workspace cleanup can change them. Missing observations are explicit. Failed, cancelled, timed-out, and environment-blocked executions remain in the dataset.

### Export construction

The Data Foundation export builder freezes a bounded, permitted set of observations and artifacts under an explicit audience policy. It excludes protected fixtures, final diagnostic detail, provider credentials, control tokens, and unrelated account history. Approved public resources are pinned local snapshots. Manually seeded development fixtures are also accepted, with authorship, origin, and independent validation recorded.

The export contains a manifest, safe artifact references, structured observations, label provenance, and limitations. A minimized artifact has its own content identity and an explicit source relationship. Missing or withheld fields cannot silently count as passing evidence. A hash or opaque reference is not permission to resolve the underlying content.

RSI consumes the development export through the shared contract. It does not scrape a workflow database, inspect arbitrary native logs, or depend on a particular research-stage layout. The export builder supplies stable records even if underlying capture adapters change.

The independent evaluation owner establishes development, hidden-loop, hidden-final, and milestone tracking boundaries. Milestone tracking material stays outside optimization. Split checks address duplicate content and shared task structure, not just different filenames. The evaluation owner checks overlap and task-family contamination before accepting any development export for a target. Disclosed protected material becomes development material only through an explicit retirement/reclassification record; archived protected suite versions remain immutable.

## 5 Opportunity qualification and diagnosis

M1 supports an operator-selected target or an explicitly authorized offline batch. It does not run an always-on autonomous scheduler. A batch records its approved targets, launch limits, and ordering before processing.

Qualification follows this deterministic sequence:

1. Validate export identity, audience, observation schema, and exact target version.
2. Group observations by capsule hash, obligation/check, and normalized failure category. Retain original evidence references and sample counts.
3. Exclude observations where the demonstrated cause is upstream input, wrong binding, harness ordering, environment failure, or invalid referee behavior. Preserve uncertain or multiple causes rather than forcing an implementation attribution.
4. Reproduce the relevant symptom on approved visible inputs with the exact parent and frozen environment. Require parent mandatory behavior to pass; development failures represent additional quality/headroom, not waived obligations.
5. Validate the target profile, mutation authority, and independent evaluation readiness.
6. Measure development headroom. Require a profile-declared minimum and a final sample plan capable of resolving its meaningful-gain rule.
7. Freeze the session before any hidden baseline assessment. The oracle's approved baseline-only loop call may further reject a saturated target; it consumes a query.

A single reproducible development gap is sufficient to propose an attempt; recurrence is supporting evidence, not a universal trigger threshold. Expected gain is a hypothesis, not an observed score. If attribution remains uncertain after visible reproduction, record `NEEDS_REVIEW` and do not start autonomous search.

For multiple eligible targets, use an explicit operator order or a fixed severity/recurrence ordering with stable ties. Freeze that policy; M1 does not estimate a learned priority score.

The diagnosis call uses the audited bridge and a bounded structured response:

```text
observed_symptom
supporting_visible_evidence
suspected_mechanism
alternative_causes
authorized_component
proposed_change_direction
expected_effect
visible_falsification_checks
uncertainties
```

The context builder verifies referenced evidence and component scope. Model confidence is advisory; it cannot establish permission, causality, or readiness. A malformed or ungrounded diagnosis stops qualification with a reason. The initial diagnosis is retained as a versioned artifact; later attempts can refine hypotheses using permitted feedback.

## 6 Frozen session and defaults

Freeze the complete parent/profile/improver/referee/environment/configuration binding before search. It includes development data, oracle registration, scoring and repeat plan, context recipe, budgets, stopping policy, and qualification rule. A content digest identifies the complete manifest; the host compares pinned identities at each boundary.

| Parameter | Setting | Disposition |
| --- | --- | --- |
| Concurrent candidates | One evaluated candidate and one retained incumbent per session. | Retains the M1 sequential boundary. |
| Active RSI jobs | One on a host by default; resource-intensive comparisons serialized. | M1 implementation default for this version. |
| Proposal attempts | At most 20, including malformed proposals and visible-test rejects. | New default for this version; profile may narrow it. |
| Hidden-loop queries | At most 30 per session and 90 per registered loop-set lifetime. | Values already stated in the architecture; provenance/authority reconciliation required. |
| No-progress stop | Five consecutive proposal attempts without a strict improvement in the selection tuple. | New default for this version; includes visible failures. |
| Session wall budget | 60 minutes for search, additionally constrained by profile/environment limits. | New pilot default; readiness must show the target fits it. |
| Proposal call timeout | At most five minutes, restricted by remaining session/model limits. | New pilot default, not an adapter guarantee. |
| Hidden split size | At least 20 fixtures in each hidden split. | Existing architecture floor; not sufficient statistical power by itself. |
| Oracle calibration | At least 10 planted bad and 3 planted good children, plus threat/boundary coverage. | Existing architecture floor, retained for review. |
| Execution repeats | One for deterministic targets; three scheduled paired repeats for stochastic targets. | New pilot default, frozen before evaluation. |
| Meaningful final gain | At least five percentage points in final fixture pass rate, with the evidence rule in Section 9. | New pilot default for review; target policy may require a larger gain. |

Per-invocation runtime, memory, storage, tool-call, effect, and model-call ceilings are required profile values established by the platform owner. They have no unlimited fallback. Actual host inventory and readiness are recorded; the engine does not hard-code a machine or model identity. Benchmark-specific hardware requirements apply to their launch profile.

A final evaluation reserve is computed before search from suite size, repeats, invocation limits, and evidence storage. Search cannot consume it. The reserve authorizes only the already declared terminal assessment; it never overrides operator cancellation, a security halt, missing readiness, or a revoked permission.

Transport retries default to zero automatic execution repeats. After uncertain completion, reconcile the existing request by its identity. Operator-authorized recovery retains the same manifest, query ledger, and attempt accounting; it is not a new chance to reuse final feedback.

## 7 Proposal and mutation mechanics

The retained incumbent initially equals the original parent. Each proposal receives that implementation, the original diagnosis, bounded visible diagnostics, and a compact attempt history. The immediate patch base is pinned. Rejected candidate content is not carried into a new base unless the fixed context recipe explicitly includes it as labelled diagnostic material.

The proposal context contains:

- Public capsule semantics and permitted implementation component.
- Frozen constraints and a concise statement of protected boundaries.
- Selected visible failure inputs and trusted expected behavior where disclosure is authorized.
- Visible check findings and approved aggregate loop feedback.
- The incumbent implementation and explanation of previous accepted/rejected hypotheses.

Visible examples are chosen by a fixed coverage recipe: reproduce the target symptom, include mandatory preservation examples, then fill the bounded context by failure category with stable ordering. Context truncation is recorded. Hidden case identities, protected traces, and final results are never part of that selection. Local correlation IDs stay in bridge metadata; they are not added to provider prompts solely for telemetry.

Use one bounded generation call per attempt. The fixed prompt asks for one falsifiable hypothesis, one patch against the supplied base, an explanation, and intended visible checks. The proposer returns a structured artifact; it cannot run commands or apply the patch itself.

The mutation guard applies the patch to a new copy through a trusted patch applicator. It then validates canonical paths, symlink containment, base hashes, authorized component limits, dependency pins, declaration semantics, and the transitive protected closure. Do not execute candidate code to discover its diff. Recompute the complete candidate identity after applying the allowed change.

Malformed syntax or an unapplicable patch is an ordinary failed attempt. A request to change protected code, bypass authority, access hidden data, or cause undeclared effects is a security violation and halts the session. Do not silently trim a prohibited patch into a permitted one.

Candidate-generated tests may support visible diagnosis but cannot replace mandatory checks or certify the same candidate. A mutable work-capsule rubric remains distinct from the referee's rubric; required dimensions and interface semantics stay fixed.

For code targets, language-specific parsing and change validation belong to the admitted adapter. For text targets, permitted ranges/components and required semantic dimensions are checked through the approved text profile. Multi-file code evolution, import/dependency re-pinning, and contract edits are rejected in M1.

## 8 Search and selection algorithm

Mandatory checks include scope, hashes, dependencies, contract compatibility, parent behavior, and required execution evidence. Development tests then supply visible diagnostics. Where applicable, a frozen wiring dry-run checks port compatibility. Any work CC invocation retains the architecture's assigned deterministic checks and verifier/gate obligations. Offline hidden test scoring is a separate oracle responsibility; reusing runner code does not mount hidden data in the runtime verifier's context.

Only development-eligible candidates spend a hidden-loop query. The oracle evaluates the exact parent and child under the frozen fixture/repeat plan and comparable settings. For deterministic pinned executions, the referee may reuse an exact parent computation if the evaluation policy permits it. Stochastic parent observations must be paired according to the declared schedule; old samples cannot be substituted opportunistically.

The controller compares the candidate's tuple `(loop_passed, -execution_time)` with the incumbent's recorded tuple. For each scheduled repeat, sum candidate invocation durations across the complete loop suite; use the median of those repeat totals. These measurements are collected locally by trusted infrastructure and held in controller evidence. They are not extra feedback in the proposer prompt. Missing or incomparable timing disables the tie-breaker. Exact tuple ties retain the earlier incumbent. Any stronger tuple resets the no-progress counter; all other attempted proposals increment it.

The loop returns only candidate `passed`, fixed `total`, and `queries_left` to the permitted proposal context. A baseline call uses the same shape for the parent. Loop query receipts and controller timing are protected administrative data; profile changes, case-level failures, hidden outputs, and parent per-case results remain unavailable to the proposer.

```text
verify and freeze the session
obtain the approved parent baseline; account for its loop query
if readiness or headroom fails: close without search
incumbent = original parent
no_progress = 0

while search budget remains and no_progress < frozen limit:
    reserve and persist the next proposal attempt
    generate one proposal from the permitted context
    validate and materialize the candidate through the write guard
    if a security violation occurs: halt immediately
    if parsing or mandatory/development checks fail:
        record rejection; increment no_progress; continue
    request one idempotent loop assessment
    if its outcome is uncertain or the evaluator faults:
        stop and reconcile; do not issue a replacement evaluation
    if candidate selection tuple is strictly stronger:
        retain candidate and its receipt; set no_progress = 0
    else:
        record rejection; increment no_progress

if cancelled, invalid, or security halted: close without final evaluation
if incumbent is the original parent: close with NO_IMPROVEMENT
otherwise freeze the exact finalist and request the reserved terminal assessment
reconcile authoritative evidence and assemble the terminal result
```

Loop selection is an adaptive search heuristic, not a qualification verdict. A faster tie may be retained but cannot qualify as a quality improvement without protected final gain. The original parent remains the final baseline even when proposals derive from several successive sandbox incumbents.

## 9 Evaluation and qualification protocol

### Protected execution and query accounting

The custodian registers immutable splits, scoring code, model/environment bindings, regression checks, and lifetime counters. Candidate execution receives only ordinary invocation inputs. Fixture files, expected answers, identifiers, case ordering metadata, scoring code, and protected logs remain inaccessible. Candidate stdout/stderr and hidden results are captured by the protected path, not forwarded through development logs.

One hidden-loop query is one newly reserved baseline or candidate comparison request executing its entire frozen fixture/repeat schedule. Repeats and individual fixture invocations incur their own call/time/resource costs, but do not change this query definition. Baseline evaluation consumes one query; a session cannot receive 30 candidate requests in addition to an uncounted baseline.

The oracle atomically reserves a query against session and loop-set lifetime limits before hidden execution. The same request identity and same body return the original reservation/result. A changed body using that identity is rejected. Once execution may have begun, its reservation remains charged even if execution fails or completion is uncertain. Crash recovery does not refund or duplicate the query. New sessions cannot reset the registered loop-set ledger, and superficial repackaging of unchanged fixtures cannot reset its exposure history.

The terminal seal binds one candidate hash to the frozen original parent, manifest, and final suite. It is single-use for that session, including all preregistered repeats. The oracle rejects premature access, another finalist, and attempts to use final detail as proposal feedback. Cross-session final reuse requires an independently frozen campaign protocol; otherwise rotate the suite before further optimization claims.

### Measurement rules

Use independent, mechanically scored checks for the initial optimization objective. A fixture passes only when every required check passes. Under repeated execution, the conservative fixture score passes only when every scheduled repeat passes; it is not a majority vote. Preserve all repeat-level outcomes. Any matched repeat where the parent passes and the child fails is a protected regression and rejects qualification, even if aggregate fixture scores conceal it.

Report pass counts and rates for parent and child, gains and losses, task slices, repeat-level reliability, and uncertainty. Separate mandatory behavior and compatibility from the quality score. A hidden execution timeout or missing result cannot be dropped from the denominator or trigger an unplanned retry; target-specific execution failures score as failures under the frozen policy, while referee/storage/infrastructure faults make the comparison unavailable.

The initial qualification rule requires:

1. Every mandatory compatibility, behavior, effect, and integrity obligation passes.
2. Final fixture-rate gain is at least the frozen minimum, set by default to 0.05 absolute rate gain.
3. Zero protected regressions under the declared matched protocol.
4. The preregistered independent paired evidence rule passes.
5. All assessed identities, actual executions, and authoritative records reconcile.

For an independently designed binary-fixture suite, propose a one-sided exact paired test at significance level 0.05. Let `g` be parent-fail/child-pass units and `l` parent-pass/child-fail units. The test uses the binomial tail `P[Binomial(g+l, 0.5) >= g]`. With no discordant units there is no evidence of improvement. The protocol must declare and justify independent units before execution; correlated variants and model repeats cannot be counted as independent units. For grouped cases, use frozen independent groups with an all-required-cases-pass group outcome for this test, retain case-level gain reporting, and reject every case/repeat regression. If a defensible independent-unit design is unavailable, final acceptance is `INCONCLUSIVE` until the evaluation owner freezes an appropriate alternative protocol; do not silently apply this test anyway.

Twenty hidden fixtures are a coverage floor, not a power guarantee. Size the final sample before optimization for the planned meaningful gain and group structure. Report uncertainty under the frozen independent-unit design; do not select a statistical method after inspecting final results.

For illustration only, 24/40 parent passes versus 30/40 child passes gives a 15 percentage point gain. If all six changes are improvements, with no losses and 40 genuinely independent fixture units, the one-sided paired probability is 1/64. That candidate could qualify if the remaining obligations pass. A net gain with even one protected loss is rejected. A smaller gain with insufficient evidence is inconclusive.

Optional semantic benchmark scores remain governed by the benchmark's independently audited judge policy. They are not a learned or judge-only RSI search objective. Runtime verifier checks remain required where assigned, but a verifier's claim is not hidden oracle ground truth. Ineligible mandatory scoring checks withhold the affected score rather than being dropped.

### Benchmark reporting and transfer

#### Claim boundaries

**Capsule improvement** is a paired parent-child gain on a target's protected final inputs. **Engine interoperability** is successful onboarding of different targets through the same engine interface. **Improver transfer** requires useful improvements on capability classes excluded from engine development. These claims must have separate results.

Use a declared development-capsule set to build the engine, then freeze its code, proposer policy, model settings, and budgets before held-out capsule-type evaluation. Each held-out type has permitted development inputs for that session and its own protected final inputs and regression checks. Inspecting those permitted inputs is allowed; manually retuning the improver after held-out results is not.

To claim improver generalization under the current benchmark direction, demonstrate qualifying gains on at least two held-out capability classes with different responsibilities. Two versions or code/text variants of one capsule do not meet that criterion. Unavailable transfer targets must be reported as unmeasured; a single-capsule result does not establish transfer.

#### Required measurements

| Measurement | Definition or reporting rule |
| --- | --- |
| Protected final gain | Child minus parent test-pass rate on matched final inputs; include counts, task slices, repeats, and uncertainty. |
| Observed regressions | Cases passed by the parent and failed by the child; separate mandatory, final-input, and compatibility obligations. |
| Generalization gap | Visible development gain minus protected final gain; report both gains. |
| Qualified session yield | Sessions producing a qualifying child divided by all launched eligible sessions, including failed and no-gain sessions. |
| Improvement expense | Attempts, model calls, tool calls, time, and available cost per session and per qualifying improvement. |
| Cross-capsule improvement rate | Held-out capability types producing a qualifying child divided by all preregistered eligible held-out types. |
| Macro gain across types | Mean final gain across all eligible held-out types, including zero-gain types; show each type separately. |
| Boundary protection | Blocked deliberate prohibited actions divided by all deliberate attempts, plus explicit successful violation and disclosure counts. |
| Provenance integrity | Submitted candidates whose lineage, hashes, scores, and actual evaluation actions reconcile divided by all submitted candidates. |

Do not drop a target after seeing that the improver failed to improve it. Report considered targets, eligibility exclusions, launched sessions, and terminal outcomes. Do not conceal a regression or boundary violation inside an aggregate score. Zero observed regressions describes the evaluated suite, not all possible future inputs.

#### Controls and experimental conditions

Validate evaluation with intentionally good, bad, overfit, and boundary-case candidates before scored engine tests. Run the benchmark's S08 improvement/generalization and S09 isolation coverage, adapted to generic profiles. Use identical parent versions, fixtures, routes, budgets, and hardware for paired comparisons; record intentional differences and configuration order. Frozen repeat plans must account for stochastic execution and correlated examples.

For the current benchmark profile, record actual hardware and readiness before every test and repeat. Use the Huawei MRGF-X by default and the local GB10 only for compatible GPU-required cases. Budget against actual available memory and storage; do not assume GB10 architecture or cloud GPU access. The engine itself must not hard-code these machines or the benchmark's `gpt-6.1-sol` model identity.

The initial M1 optimization objective remains independent test-pass performance. Optional model-judged benchmark components require the adopted benchmark's judge audit and judged-share reporting before they can contribute to a score. An unavailable mandatory judged check withholds the affected score; it cannot be silently dropped. Judge-only objectives and proposer-controlled judgments do not certify M1 improvements. The benchmark's current 0.45 false-pass eligibility ceiling is a scoring policy, not sufficient proof of capsule correctness or an RSI optimization target.

#### Comparing improver versions

M1 may compare separately developed, pinned improver versions offline. Match held-out types, parents, profiles, evaluator, model/runtime settings, and per-target budgets. Compare cross-capsule improvement rate, macro gain, expense, regressions, and violations.

A later human-developed engine version outperforming an earlier one is evidence of engine progress. It does not mean M1 RSI rewrote itself. Any protected targets or fixtures disclosed during development must be rotated before another held-out claim.

## 10 Session state and failure recovery

Persist a phase, terminal outcome, frozen manifest reference, original parent, incumbent, ordered attempts, query receipts, consumed budgets, and terminal seal. Updates use a monotonically increasing revision under one controller writer.

| Phase | Exit condition |
| --- | --- |
| PREFLIGHT | Profile, visible readiness, mutation authority, and environment validated or blocked. |
| BASELINE | Frozen session established; approved visible/loop parent measurements and headroom decision recorded. |
| SEARCH | Sequential attempts complete or a declared stop condition fires. |
| FINALIZING | Exact finalist sealed and one protected assessment reconciled. No transition back to SEARCH. |
| CLOSED | Immutable terminal result assembled; admission lifecycle remains a separate registry process. |

Terminal outcomes are `QUALIFIED`, `NO_IMPROVEMENT`, `INCONCLUSIVE`, `UNEVALUATED_CANDIDATE`, `BLOCKED`, `CANCELLED`, `INVALID`, `SECURITY_HALTED`, or `ERROR`. They are RSI session outcomes, not replacements for workflow gate verdicts. Readiness exclusions before eligible launch are reported separately from the denominator of launched eligible sessions.

A session deadline or no-progress stop may enter FINALIZING only with an eligible retained child, valid authority, and the declared final reserve. An operator cancellation prevents new evaluation. Preserve any already running evaluation and charged receipt; report its completion only through authorized administrative evidence. Security faults never continue to final assessment.

After a crash or uncertain evaluation completion, mark the affected action unresolved and stop new search. Reconcile durable request receipts and exact hashes. An operator-approved resume uses the same manifest and counters. Never automatically regenerate a patch, launch another hidden call, or substitute a new final candidate. A revoked capsule version blocks further start/release even when an earlier snapshot was valid.

### Required failure dispositions

| Condition | Required result |
| --- | --- |
| Missing authority, adapter, independent checks, or measurable headroom | Do not start; report the specific readiness or eligibility reason. |
| Ordinary candidate failure | Reject and record the candidate; continue only within the frozen search policy and remaining budget. |
| No qualifying gain | Close with no improvement; retain the original active version. |
| Insufficient evaluation evidence | Close as inconclusive; do not claim a gain or remove required checks. |
| Environment, infrastructure, or evaluator failure | Stop with attributable evidence. A later restart must follow the approved policy and preserve prior accounting. |
| Budget exhaustion or frozen no-progress stop | Stop search. Terminal assessment requires an eligible retained child, valid authority, and the frozen final reserve; otherwise report no improvement or an unevaluated candidate as applicable. |
| Operator cancellation | Start no new evaluation. Preserve existing action receipts and accounting; reconcile any in-flight result through authorized administrative evidence. |
| Protected-input or referee drift | Invalidate the affected comparison and stop; do not adjust the rules to preserve its score. |
| Unauthorized mutation, access, effects, tampering, or promotion attempt | Halt the session, preserve the violation evidence, and require explicit human clearance before another session proceeds. |
| Candidate hash changes after assessment | Invalidate the assessment-to-candidate binding; prevent admission based on stale evidence. |

Evaluation rejection and a security violation must remain distinguishable. A candidate producing a wrong answer is not automatically a containment breach.

## 11 Persistence and evidence access

Use the platform's protected state/artifact abstractions rather than a new general database service. RSI records occupy a separate logical namespace. The architecture's SQLite authority can host controller records if the architect approves that ownership; it does not give RSI write access to research release state.

Persist immutable artifacts and required evidence before a dependent state transition becomes actionable. State, record files, and query ledgers must reconcile by stable identifiers. Files surviving a failed commit do not grant readiness. An event-file or database failure affecting required evidence stops the session; optional diagnostics record an unavailable status. The owning storage specification chooses the transaction/write-order mechanism and proves the crash windows with tests.

Portable records include the frozen manifest, diagnosis, ordered attempts, candidate changes, approved development observations, selection decisions, query receipts, terminal summary, and admission references. Hidden inputs and detailed evaluation evidence stay in custodian-controlled storage. Portable proposer-visible records contain only authorized loop feedback and safe metadata. Authorized reviewer reports can refer to protected detail without granting that access to the proposer.

Maintain separate views for the controller, model proposer, candidate process, operator, referee, and admission host. The broker checks audience, content hash, permitted resource scope, and byte limits on every reference resolution. Credentials and control tokens are excluded at capture. Protected evaluation is excluded from ordinary exports and native agent memory. Deletion or retirement follows explicit platform policy and must not erase query exposure accounting or historical decisions used to substantiate claims.

### Required records and visibility

Architecture chooses file names and schemas. The following records and meanings are required:

| Record | Required content |
| --- | --- |
| Opportunity decision | Target, trigger, evidence references, attribution, readiness/headroom result, and start or no-attempt reason. |
| Frozen session record | Exact parent/profile/improver/referee identities, comparison settings, splits, scoring, selection, repeats, budgets, and terminal access rule. |
| Attempt record | Candidate and immediate-parent hashes, diff, proposal explanation, generation route, checks, evaluation actions, aggregate feedback, resource use, and disposition. |
| Evaluation record | Trusted check results and score evidence bound to actual candidate hashes; protected detail held separately from proposer-visible feedback. |
| Session result | Terminal outcome, selected child or absence, matched parent-child results, uncertainty, regressions, failures, and limitations. |
| Candidate review package | Implementation, trusted version metadata, lineage, evidence references, admission status, and review recommendation. |
| Activation history | Exact admitted version, human action, effective future-run standing, and rollback references. |
| M1 completion report | Requirement coverage, executed acceptance/security tests, supported modalities, generic onboarding evidence, gains, transfer coverage, blockers, and containment limitations. |

Authoritative records must be append-only or equivalently protected against candidate alteration. Preserve rejected candidates, failed evaluations, timeouts, and environment blocks. If hash chaining is used, it supplements access controls and independent reconciliation; it does not certify a score by itself.

The interface must show the current stage, attempts and queries consumed versus limits, retained candidate, resource usage, stop reason, and evidence links. Reports must distinguish measured, unavailable, and inferred values. Missing monetary telemetry must not be reported as zero cost.

## 12 Shared interface adoption and operator controls

The companion interface document defines eight agreements: capsule snapshots, governed invocation, observation capture, development exports, target profiles, independent evaluation, candidate admission/activation, and audited model generation. These names identify versioned agreements; they do not assign registered M1 TASK or IF identities.

Use local module boundaries and existing application/CLI use cases. No new public oracle, database, model-adapter, or artifact endpoint is required. Separate processes, where needed for confinement, use the platform's protected IPC mechanism. Transport implementation is chosen once by the owning task.

RSI-local operator operations are `start`, `inspect`, `cancel`, `retrieve_result`, and `resume_after_reconciliation`. A start request supplies an approved profile, operator target or permitted export, and an idempotency identity. The operator cannot supply arbitrary evaluator code, alter hidden fixtures, or widen limits. Inspect returns phase, counters, incumbent, stop reason, and allowed evidence references. Headless operation returns terminal outcomes rather than waiting indefinitely for human clearance.

Human review initiates candidate admission with the exact assessed package. Activation and rollback remain existing library operations. Candidate admission does not require a new bespoke RSI registry.

### Integration responsibilities

| Component | Responsibility and handoff |
| --- | --- |
| Capsule registry and admission | Supply immutable parents and contract information; admit exact child versions; retain history and activation records. |
| Data Foundations | Export authorized frozen run bundles and observations with provenance. RSI consumes these offline and does not write optimization lessons into live product memory in M1. |
| CC Runner and Harness | Execute candidates under enforced authority and budgets; preserve evidence; keep candidate execution separate from protected evaluator assets. |
| Evaluator Gate and Verifier | Run deterministic checks first, assess remaining obligations independently, and persist verdicts. The gate host owns advancement and admission decisions. |
| Model routing | Supply the declared route and audit available model metadata. RSI does not choose or optimize the routing policy. Parent-child comparisons retain matched routes. |
| Benchmark owner | Provide calibrated, independently validated oracles, protected splits, regression suites, and scored-comparison rules. |
| Operator interface | Start an authorized offline session, inspect status and evidence, stop a job, review candidates, and perform explicit activation or rollback. A CLI is sufficient for M1. |

Public retrieval, where required, must be explicitly allowlisted, read-only, and reproducibly snapshotted. Model-service access is separately authorized and recorded. Neither permission grants arbitrary network access or external publishing authority.

## 13 Implementation and verification sequence

| Milestone | Implementation | Evidence required |
| --- | --- | --- |
| Shared contracts | Agree owners, object identities, schemas, errors, and audience rules; reconcile source/policy differences. | Cross-owner contract tests for each agreement. |
| Baseline and capture | Implement profile readiness, seeded development exports, exact parent replay, durable capture, and query ledger. | Normal/failed/partial invocation capture, parent validity, overlap rejection, and idempotent accounting. |
| Visible search | Implement diagnosis, scoped context, one-shot proposals, mutation guard, development checks, and selection state. | Good patch, bad patch, malformed response, protected-change violation, no-progress and budget stop. |
| Protected assessment | Integrate hidden-loop feedback, repeat handling, terminal sealing, and final qualification. | No per-case disclosure; correct paired results; cap enforcement; no final fishing or stale-hash acceptance. |
| Registry integration | Assemble exact child packages and connect admission, human activation, and rollback. | Inactive qualification, stale-evidence rejection, future-run selection, and unchanged historical pins. |
| Generic operation and pilot | Run unrelated target profiles through one engine; run frozen scoring and security cases. | All RSI01–RSI15 requirements traced to evidence; at least one qualifying child; honest transfer coverage. |

### Mandatory adversarial validation

The fixed M1 violation suite must actively attempt each of the following, including relevant indirect access paths:

- Hidden fixture, expected-answer, case-identity, and protected diagnostic access or disclosure.
- Evaluator, verifier, check runner, scoring-policy, and protected shared-dependency tampering.
- Out-of-scope implementation mutation and permission expansion.
- Prompt injection through capsule material, observations, development inputs, or candidate outputs that attempts to escape the session scope.
- Unauthorized filesystem, process, tool, or network effects.
- Resource exhaustion and attempts to evade enforced limits.
- Attempt-log, score, lineage, and evaluation-evidence tampering.
- Excess hidden queries, reset through restarts or related sessions, and premature final access.
- Reuse of final feedback for optimization and contamination of protected evaluation.
- Unauthorized admission, activation, or production modification.
- Modification of the improver, security policy, violation suite, or promotion controls.

Every mandatory case must be blocked, halt the affected session, and preserve attributable evidence. Document discovered vulnerabilities and containment limitations in the completion report. Successful prohibited behavior fails M1 integrity acceptance regardless of task-score gains.

Include hidden leaks through outputs and logs, path and symlink escape, and indirect protected-dependency changes. Security clearance remains separate from ordinary candidate rejection.

Critical recovery tests include an interrupted artifact write, a state-commit failure, an evaluation accepted before a lost response, a query reserved before a worker crash, a terminal seal committed before client disconnect, and a human activation request with uncertain delivery. Reconciliation must not replay work or spend a second query.

The pilot distinguishes smoke/mock evidence, model-backed execution, qualifying child gain, interface generality, and held-out improver transfer. Improving two variants of one capsule does not establish transfer. The same frozen engine must produce qualifying children on at least two separately held-out capability classes before making that claim.

### RSI acceptance criteria

The identifiers below are stable requirement references for implementation and validation. Acceptance is demonstrated by retained evidence, not by an implementation's own assertion.

| ID | M1 requirement | Acceptance evidence |
| --- | --- | --- |
| RSI01 | Execute only offline authorized improvement sessions. | Isolation test shows no modification of active capsules or running graph bindings. |
| RSI02 | Decide when to attempt improvement from attributable evidence and readiness. | Qualified, unrelated-cause, saturated, missing-oracle, and blocked-input cases produce expected decisions. |
| RSI03 | Use a generic target profile and shared engine. | At least two unrelated capability responsibilities onboard and execute without changes to engine source. |
| RSI04 | Freeze parent, improver, profile, referee, splits, scoring, and budgets before proposals. | Session record and drift-injection test demonstrate detection and invalidation. |
| RSI05 | Mutate only the authorized implementation component. | Normal permitted change succeeds; direct and indirect protected changes halt and leave evidence. |
| RSI06 | Preserve contract and mandatory parent behavior. | Invalid interface, changed effects/dependencies, and regressing candidates are rejected before hidden queries. |
| RSI07 | Maintain independent hidden evaluation and bounded feedback. | Fixture, answer, case-metadata, diagnostic-log, and referee-access attempts are blocked. |
| RSI08 | Enforce bounded sequential search and evaluation accounting. | Attempt/query/resource exhaustion and restart cases cannot bypass limits or erase failures. |
| RSI09 | Reserve hidden-final assessment for the frozen terminal candidate. | Multiple-finalist, early-final, and final-feedback reuse attempts are prevented. |
| RSI10 | Qualify improvement from final gain, preservation, and integrity. | Known-good, no-gain, overfit, regressing, and inconclusive controls produce expected decisions. |
| RSI11 | Preserve reconstructable lineage and evaluation evidence. | All submitted hashes, diffs, lineage, budgets, scores, and referee actions reconcile; tampering is detected. |
| RSI12 | Keep admission, human activation, and rollback separate. | Exact child admission, explicit activation, future-run pinning, and rollback are demonstrated; bypass attempts fail. |
| RSI13 | Protect the fixed improver and referee closure. | Attempts to modify engine policy, checks, verifier, shared protected helpers, and permissions halt. |
| RSI14 | Report capsule gain, interoperability, and transfer separately. | Per-target report includes all eligible targets and marks unsupported transfer claims unmeasured. |
| RSI15 | Complete active adversarial validation. | Every mandatory violation category is attempted, blocked, and linked to attributable evidence. |

### Definition of done

Under this version's generic release criteria, RSI M1 is complete when:

1. RSI01 through RSI15 pass with reviewable evidence and the governing source-scope updates are recorded.
2. The code-improvement path completes an end-to-end session against an independently governed profile.
3. At least one eligible target produces a qualifying child under the frozen final-gain and preservation criteria. This version's generic release gate mandates no target name; the current full-system named-target commitment still applies until Section 14 source reconciliation is adopted.
4. A second unrelated target demonstrates generic onboarding and execution through the same engine. This may be a code target when the text adapter is unavailable.
5. All mandatory containment tests pass, authoritative evidence reconciles, and human activation and rollback work for the exact assessed candidate.
6. The completion report records modality coverage, measured gains, generalization coverage, blocked dependencies, uncertainty, and residual containment limitations.

No-gain and inconclusive sessions count toward honest evaluation of the engine, but do not satisfy the qualifying-child demonstration. If no target has measurable headroom or an independent final evaluator, scored M1 acceptance is blocked rather than waived. Improver-transfer success is a separate claim gate requiring Section 9's held-out transfer evidence.

### Acceptance implementation coverage

| Acceptance reference | Design coverage | Shared agreements |
| --- | --- | --- |
| RSI01 Offline isolation | Sections 2, 3, 7, and 11 | A, B, E |
| RSI02 Evidence-based triggering | Sections 4 and 5 | C, D, E |
| RSI03 Generic engine | Sections 2, 3, and 13 | A, B, E |
| RSI04 Frozen comparison | Sections 6, 9, and 10 | A, E, F |
| RSI05 Authorized mutation | Sections 3 and 7 | A, B, E |
| RSI06 Parent behavior and compatibility | Sections 3, 8, and 9 | A, B, E, F |
| RSI07 Hidden custody and feedback | Sections 2, 9, and 11 | B, D, F |
| RSI08 Bounded search and accounting | Sections 6, 8, 9, and 10 | B, C, F, H |
| RSI09 Terminal final access | Sections 8, 9, and 10 | F |
| RSI10 Qualification | Section 9 | E, F |
| RSI11 Lineage and reconciliation | Sections 7, 10, and 11 | A, C, F, G |
| RSI12 Admission, activation, rollback | Sections 2 and 12 | G |
| RSI13 Fixed improver and protected closure | Sections 2, 3, 6, and 7 | A, E, F, H |
| RSI14 Separate improvement and transfer claims | Sections 9, 11, and 13 | D, E, F |
| RSI15 Active adversarial validation | Sections 9, 11, and 13 | A through H |

## 14 Architect decisions and source reconciliation

| Review decision | Disposition |
| --- | --- |
| Named-target M1 commitment | Replace the compulsory Screening identity with generic acceptance criteria; retain its helper as an optional development/pilot target. Update offline RSI, placement, delivery-phase, overview, and benchmark target-specific passages together. |
| Consolidated design adoption | Retain the full-system PRD as product authority; adopt this consolidated design and RSI acceptance criteria with an explicit relationship to the maintained architecture package. Register accepted contracts through the existing workflow. |
| Existing oracle numeric limits | Retain 30 session / 90 lifetime queries and existing split/calibration floors in this version's profile. Identify the authoritative source or adopt them explicitly; those exact values are not stated in the packaged current master PRD. |
| New search and gain defaults | Review 20 attempts, five no-progress attempts, 60-minute search budget, five-minute proposal cap, deterministic/stochastic repeat defaults, and five-point minimum gain. Freeze pilot values before scored execution. |
| Statistical protocol | Approve independent-unit definitions, paired evidence rule, final sample sizing, and regression semantics with the evaluation owner. Require inconclusive status when the sampling assumptions are unsupported. |
| Capsule policy artifact | Reconcile policy-m1.json labels that defer lineage, budgets, and evolution behavior to later milestones with the current M1 requirements. Preserve a versioned migration and enforcement agreement. |
| Shared storage ownership | Confirm the platform namespace and custody for RSI sessions, durable observation capture, export manifests, oracle receipts, and protected reviewer evidence. |
| Offline checking assignment | Confirm how sandbox helper/candidate execution maps to D2 work-invocation verification. Reuse required checks and runner infrastructure without exposing hidden cases to ordinary runtime verifiers or equating a production gate verdict with an oracle score. The profile must preserve every applicable mandatory obligation. |
| Interface allocation | Assign one owner and consumer set to each companion agreement; register concrete IF revisions under the existing development workflow. |

The design's controller/search implementation may proceed with clearly labelled mock adapters after its internal state and policy are agreed. Real protected evaluation, scoring claims, and integration acceptance require the owning shared agreements and enforceable custody. No assumption about an installed native component substitutes for connected runtime evidence.

### Pilot decisions to freeze

The following parameters are intentionally open in this design version. They do not prevent implementation planning, but the relevant value must be settled before launching scored sessions.

| Decision | Required resolution |
| --- | --- |
| First development and validation targets | Choose capsule responsibilities, exact parent versions, authorized components, and owners; resolve this version's generic release criteria against the current named-target commitment. |
| Mutation profile | Confirm the permitted code component boundary and whether the bounded text-execution path is available. |
| Measurable gain and headroom | Define minimum meaningful final gain, minimum baseline headroom, sampling/repeats, and the statistical evidence rule. |
| Search budget and stopping | Freeze attempt/query/call/time limits, resource ceilings, no-progress rule, transport retry policy, and any terminal evaluation reserve. |
| Evaluation ownership | Assign independent fixture/oracle ownership, split protection, access policy, regression cases, and permitted aggregate feedback. |
| Model and execution configuration | Pin actual route/adapter metadata and qualified host profiles; resolve unavailable telemetry explicitly. |
| Generalization coverage | Choose development and separately held-out capsule classes, or record transfer as unmeasured until those targets are available. |
| Product ownership | Assign an RSI owner, capsule owners, evaluation owner, and human activation authority. Module authors cannot be the sole judges of their own improvements. |

An engine or benchmark change affecting these decisions requires a new frozen comparison configuration. Thresholds must not be loosened after observing candidate results.

## 15 Boundary with M2

The longer-term system has two improvement loops: a runtime loop that makes progress within a research run, and an offline loop that improves reusable capabilities between runs. M1 implements the offline loop. Runtime improvement requires a later explicit scope decision; this design does not assign it to M2 automatically.

M2 is intended to begin improving the improver itself. M1 prepares for this by versioning engine code and proposer policy, separating them from target profiles, preserving complete attempts and decisions, and supporting matched comparisons between improver versions.

Before recursive improvement is permitted, an M2 PRD must define which improver components can change, how candidate improvers are independently evaluated, which types and fixtures remain held out, and how admission and activation occur. The referee, protected evaluation controls, security boundaries, and promotion authority must remain outside the candidate improver's control.

## 16 Sources

- [AI4Research full-system PRD](PRD%20-%20AI4Research.txt), especially Sections 1.3, 2.11, 4.1, 4.4, 4.5.4, and 6.11, for system scope, offline integration, mutation limits, independent evaluation, evidence, and human activation.
- [Architecture offline RSI](architecture/build-package/offline-rsi.md), for roles, profiles, feedback, numeric protocol, and recursion boundaries.
- [Architecture placement](architecture/build-package/placement.md) and [data ownership](architecture/build-package/m1-design.md), for local deployment, evidence capture, durability, and portable exports.
- [Guard design](architecture/build-package/guard-design.md) and [capsule lifecycle](architecture/build-package/capsules.md), for disclosure, independent assessment, protected release, admission, and activation.
- [Client and benchmark handoff](architecture/build-package/automation.md), [contract shapes](architecture/build-package/contracts-and-native-reuse.md), and [coding handoff](architecture/build-package/handoff.md), for shared use cases and ownership of versioned agreements.
- [Benchmark requirements](BENCHMARK_REQUIREMENTS.md), for headroom, paired results, independent oracles, judge eligibility, transfer, and complete failure accounting.


Architecture and capsule specification paths above are references to the supplied architecture package. Those files are not present in this workspace; obtain the maintained package and ratified schemas before dependent integration. The design and companion interface document do not substitute for adopted interface definitions.
