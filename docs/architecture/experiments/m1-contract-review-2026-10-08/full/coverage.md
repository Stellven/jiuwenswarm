# Design coverage and review

**Reading level: AI reference; design audit.** This is the single maintained design-review account, not a coding handoff or runtime acceptance report. The first human route is [README](README.md); details and contracts are linked underneath it.

Current October 8 results are recorded in the final contract/reading review section. Earlier counts describe dated snapshots.

## Baseline and source differences

The prior package, including local edits and the interrupted reference draft, was copied byte-for-byte to `architecture-checks-2026-10-07/three-tier-before` outside the repository; every copy hash was verified. The interrupted broad reference draft had 60 contracts and 178 example/context records. It is superseded by six critical schemas plus shared definitions and concise field contracts for other major boundaries.

The current received PRD is the unchanged October 7 download. Differences from the previous receipt include §1.10 change classification/canonical synchronization, §1.11 US01–US20, §6.2.1 verification governance and §6.2.2 incremental implementation. Product changes additionally require explicit intake/default/readiness outcomes, measured baseline/treatment/delta, scientific rationale, report consistency, read-only inspection and visible lifecycle results. Output conformance now references Node Execution Contract plus applicable CC declarations. Architecture dispositions appear in the coverage below; development governance remains outside the design package.

## Observed Intent outputs

`intent-output-1.zip` contained an ACCEPTED run for “research on data lake retrieval algorithm”. Its IR repeated the topic, had null desired outcome, and listed missing research questions/methods/evaluation/deliverable/timeframe. The verifier passed fidelity and omission preservation while explicitly denying Brief readiness. This demonstrates a missing **usability acceptance obligation**, not proof that all omitted experimental details must be demanded at Intent. The revised boundary blocks absent purpose/result, preserves uncertainty and asks for clearer intent without automatically conducting clarification.

`intent-output-2.zip` was exported in COMPILING state, with a RUNNING compiler attempt and no accepted IR. It provides incomplete snapshot evidence, not a completed compiler-quality result. Both archives put UTF-8 text/JSON in anonymous `.bin` members; the revised inspection boundary requires readable named artifacts and derived views. These observations motivate design changes; they do not prove that documentation alone caused every implementation defect.

## PRD and user-story responsibility map

The [clause index](coverage-allocation.md) maps every current numbered heading. The table below checks the specific user-visible journey without repeating the PRD stories. Each is realized within Phase 1; Phase 2 RSI and Phase 3 efforts remain separately covered by [phase details](phase-details.md).

| Story | Specific source | Architectural realization | Owner document |
|---|---|---|---|
| US01 | 5.2.1–5.2.2 | Pre-flight explicitly checks mandatory services/model/workspace; no dispatch if unavailable | [research-design.md](research-design.md) |
| US02 | 3.1.1, 3.1.3 | Original objective and effective profile attribution | [reference/other-contracts.md](reference/other-contracts.md) |
| US03 | 3.1.2–3.1.3 | Qualified local context and explicit required-input rejection | [research-design.md](research-design.md) |
| US04 | 3.2.3–3.2.6 | Constraints/targets and attributed authorized defaults | [reference/intent-and-requirements.md](reference/intent-and-requirements.md) |
| US05 | 3.2.7, 5.3.1 | Inspect accepted Brief, assumptions and underlying records | [artifact-inspection.md](artifact-inspection.md) |
| US06 | 3.3.5–3.3.6, 5.3.1 | Cited ideas and exact source evidence | [research-design.md](research-design.md) |
| US07 | 3.4.3–3.4.7, 5.3.1 | Scores, rationale and selected/rejected dispositions | [reference/other-contracts.md](reference/other-contracts.md) |
| US08 | 3.5.2, 3.5.4–3.5.5, 5.3.1 | Inspectable registered hypothesis and test protocol | [research-design.md](research-design.md) |
| US09 | 3.6.2–3.6.5 | Bounded POC and mechanical readiness before empirical work | [placement.md](placement.md) |
| US10 | 3.7.2–3.7.4 | Matched baseline/treatment values, delta and raw evidence | [reference/other-contracts.md](reference/other-contracts.md) |
| US11 | 3.8.4–3.8.6, 3.9.2 | Measurement-to-registered-criterion reasoning; negative result delivered | [research-design.md](research-design.md) |
| US12 | 5.1.1, 5.3.1–5.3.2 | Run/stage/status distinguish progress, checking, completion and halt | [artifact-inspection.md](artifact-inspection.md) |
| US13 | 5.1.2, 5.3.3 | Retained failed attempt, reasons and authorized fresh correction | [failure-and-human.md](failure-and-human.md) |
| US14 | 5.1.3, 5.6.3 | Observed enforceable limits and unavailable telemetry | [model-routing.md](model-routing.md) |
| US15 | 3.9.2, 3.9.4 | Readable report consistent with saved verdict | [artifact-inspection.md](artifact-inspection.md) |
| US16 | 3.9.3–3.9.4 | Audience-scoped experiment/evidence retrieval | [reference/other-contracts.md](reference/other-contracts.md) |
| US17 | 5.1.2, 5.3.1 | Read-only previous-run inspection without execution | [artifact-inspection.md](artifact-inspection.md) |
| US18 | 5.6.2 | Durable defaults outside run/workspace lifetime; effective freeze | [placement.md](placement.md) |
| US19 | 5.4.2–5.4.3, 3.9.4 | Pre-effect confinement and scoped authorized transfer | [placement.md](placement.md) |
| US20 | 5.4.4 | Authenticated local data inspection/removal; scoped lifetime | [artifact-inspection.md](artifact-inspection.md) |

## Scenario walkthrough

These are expected design outcomes, not observed runtime test passes. Executable fixtures and measured verifier criteria remain implementation verification work.

| Challenge | Designed outcome | Boundary |
|---|---|---|
| Actionable request, optional omissions | Intent schema passes; verifier accepts usable purpose/result; method and experiment details remain downstream | [intent-design.md](intent-design.md) |
| Topic-only request | Shape/fidelity may pass; semantic usability is INCONCLUSIVE; gate halts before Requirements | [intent-design.md](intent-design.md) |
| Conflicting constraints / invented goal / missing exclusion | Valid shape cannot rescue invalid interpretation; verifier reports failed/unclear obligation | [reference/intent-and-requirements.md](reference/intent-and-requirements.md) |
| Candidate instruction injection | Treat content as evidence; no policy change or replacement interpretation | [guard-design.md](guard-design.md) |
| Malformed compiler/verifier or stale/swapped subject | Mechanical checks halt; no old decision reused | [reference/checking.md](reference/checking.md) |
| Verifier/model unavailable or timeout | No acceptance; preserve available evidence and actionable environment reason | [failure-and-human.md](failure-and-human.md) |
| Persistence failure | No successor readiness; do not claim unavailable evidence is durable | [capsules.md](capsules.md) |
| Headless / browser disconnect / restart | Headless never waits; disconnect preserves execution; restart pauses without replay | [failure-and-human.md](failure-and-human.md) |
| Scientific rejection | Correct scientific FAIL receives infrastructure acceptance and goes to Delivery | [reference/checking.md](reference/checking.md) |
| In-progress export / unavailable telemetry | Incomplete state or unsupported observation remains explicit, never a complete pass | [artifact-inspection.md](artifact-inspection.md) |
| RSI hidden leak / referee edit / promotion bypass | Contain/reject, retain violation evidence, no secret export or activation | [offline-rsi.md](offline-rsi.md) |
| Wrong sidecar target/version / missing capability | Compatibility/readiness blocks before submission through ordinary client boundary | [automation.md](automation.md) |

## Human review and quality checks

The immediate route explains the complete system, CC/verifier/gate ownership, Intent versus Requirements, routing/RSI placement, container/browser access, readable evidence and phase direction. Deep explanations retain purpose, connections, broad approach, passing/blocking behavior, authority and rationale. Review it without tier 3 and answer:

1. What does the system do from intake to delivered evidence?
2. Who writes each major artifact and who may release it?
3. Why do deterministic checks and semantic assessment both exist?
4. What distinguishes Intent, Requirements and registered experimental criteria?
5. Where do routing and RSI connect, and what authority do they lack?
6. What is built now, what does each phase add, and what does a user see after a halt?

Reference quality checks cover schema/field agreement, source spans and exact references, verdict/control distinctions, consumer compatibility and shared version authority. Mechanical checks validate critical schemas/examples, deliberate invalid cases, source hashes, current clause/story coverage, link/fragment closure and a copied standalone folder. All maintained Mermaid views are audited; changed sources and SVG/PNG projections are rendered and visually inspected. Executed results and remaining limitations are recorded below.

## Conflicts, risks and limits

- D5 deliberately retains two compiler generations despite the PRD's single-pass wording; D6 retains local packaging/persistence exceptions. Source text stays unchanged; no literal zero-difference claim is made.
- Historical CC machine/prose requiredness, network, predicates, ports, budget and exemption shapes are resolved in one current field/schema contract. Historical maturity labels do not override M1 phases. Existing implementation v2.11 declarations need explicit adapter reconciliation.
- Separate producer/verifier contexts do not guarantee independent errors. A schema and a readable view cannot prove scientific truth or actual enforcement.
- Three levels reduce first-reading burden but risk stale summaries; shared links, schema/field checks and diagram-source ownership constrain duplication.
- The old very-condensed experiment remains outside this maintained package and predates the new detail. It must not silently substitute for these current contract inputs.
- Required product Change Records/verification summaries are source obligations outside this design. Existing repository governance must reconcile their realization without inventing duplicate design-owned workflow cards.
- This revision changes documentation only. Runtime code, installed endpoint support, containment and M1 completion remain unestablished by these checks.

## Executed documentation checks — October 7, 2026

- Preserved checkpoint: all 346 baseline file hashes rechecked successfully. Original CC machine/semantic/policy sources and the prior packaged PRD match the checkpoint; the current packaged PRD is byte-identical to the latest download.
- `python reference/validate.py`: PASS for six critical Draft 2020-12 schemas plus shared definitions, 34 indexed example/context records, 12 deliberate invalid cases, exact content references/source-span bounds and selected cross-record gate relationships. Both Intent and Requirements have linked checking/assessment/decision examples.
- Coverage/navigation: 188 current numbered PRD headings, US01–US20, 939 package-local links/fragments, catalog versions/phase associations, required field-summary inventories and the five-document immediate route (4,282 whitespace-delimited words, including diagram text).
- Diagrams: 26 maintained Mermaid blocks rendered to SVG and PNG with Mermaid CLI 12.0.0; source/projection hash closure passes. Contact-sheet inspection covered every maintained view, with enlarged inspection of the system and sidecar access views. A temporary filename collision was corrected and all views regenerated; obsolete projections/index anchors were removed.
- Portability: copied the entire folder with byte verification to an independent validation location and ran the same validator there successfully. Required current references and schema resolution do not depend on repository siblings or online schema retrieval.
- Repository hygiene: `git diff --check` passes. Incoming architecture/product/task entrypoints point to the current PRD and reading route; the reference ignore exception is restricted to this package. Existing task/interface identities remain unchanged.

These checks establish document structure and selected design relationships. Clause/story links are architecture traceability, not proof of every source bullet or runtime behavior. Source support, model/verifier error rates, authorization, durable commit behavior, adapter reconciliation with historical declarations, and actual containment need implementation evidence. The topic-only and scientific-negative records illustrate intended outcomes; the second downloaded ZIP remains an incomplete execution snapshot. No application implementation, commit or push was performed.

## Full-M1 design-integrity review — October 7, 2026

Review method: [design method](design-method.md). The pre-review 151-file checkpoint outside the repository preserves the current package, root rules and historical condensed input with verified hashes. Source bytes and existing local changes are retained. This review examined clause behavior/exclusions across §§1–6 alongside current component explanations; the numbered heading map remains an index, not proof of behavioral coverage.

### Clause obligations, connections and dispositions

| Source cluster | Obligations/exclusions reviewed | Architectural home / disposition |
|---|---|---|
| §§1.1–1.9, 2 | Evidence-backed supplied-baseline research, user-scoped/local execution, phases/core release, lane and non-scope | Immediate system/phases; full component obligations. No external channels, training, remote worker fleet or uncontrolled autonomy |
| §§3.0, 4.3, 5.6.1 | Existing secure synchronous Codex bridge; static baseline; two-stage experimental routing; clean provider prompts/telemetry | Placement now defines in-container CLI/IPC prerequisites; routing now defines bounded registry and eligibility/selection. Access and supported runtime must be demonstrated |
| §§3.1, 3.2, 4.7 | Qualified text/resources, scope/default attribution, input errors, stable Brief, baseline no clarification | Intent/Requirements design and fields; topic-only halt; resource availability downstream. D5 remains two compiler passes, explicitly different from literal one-pass source |
| §§3.3–3.4 | Fixed queries/designated connectors, exact grouped citations, 1–3 ideas; consolidation/cards/opportunity/scores/filter/Top-1 | Research fields/obligations; added opportunity statement and fixed tie/missing-score semantics. No dynamic search repair, new unsupported ideas, live feasibility trial or human selection |
| §3.5 | One measurable claim, immutable supplied baseline/data, measurement functions and outcome rules before code | Hypothesis obligations: availability and complete registered classification, no synthetic validation or retrospective changes |
| §§3.6–3.7, 4.9 | Bounded scripts and bundle, no build-time scientific trial/install, restricted provisioning and matched baseline/treatment | Placement clarifies archive containment, direct/transitive pins, protected provisioning versus generated-code restrictions, immutable baseline and same-host worker. No generated Docker orchestration |
| §§3.8–3.9 | Logs-to-metric validity, frozen criteria/rationale, four scientific classifications, consistent template report and local package | Research/Evaluation/Delivery obligations; trusted hash capture is outside scientific evaluator, which does not invent a crypto provenance service. No post-result criteria, rerun or publication |
| §§4.1–4.2 | CC/node/contract distinction, declaration/provenance/admission, per-invocation and aggregate evidence, deterministic-first/read-only semantic checking | Capsules, guard, checking contracts and component obligations. Mandatory unknown/malformed/stale/effect evidence cannot advance; human standing and version history remain protected |
| §§4.4, 6.11 | Required bounded Target 1, conditional Target 2, split custody/query limits/referee/calibration/adversarial evidence, human activation | Offline RSI and reference records; live ranking unchanged. Demonstrate admission/activation through eligible sandbox standing, not automatic production replacement |
| §§4.5–4.6 | Agent memory distinct from Run Bundle, effective state/observations, scorecards/exports, dispatch/timeouts/durable gates/headless halt | State/evidence and runtime obligations. D6 SQLite authority plus portable append-only evidence retained; no broker, automatic replay or distributed scheduler |
| §§5.1–5.3, 5.5 | Native run-tree/CLI/Web/TUI, install/doctor, artifacts/report, tmux and stable headless completion | Operational shell/inspection; supported POSIX workstation and Linux container prerequisites; browser disconnect not cancellation; no native desktop binaries/custom workflow editor |
| §§5.4, 5.6 | Stable account separate from OS/workspace, protected token/local access, fixture/POC isolation, scoped deletion, frozen precedence/limits/evaluation | Placement/client/inspection obligations. Private authenticated container access is D6; no LAN/public model bridge, false token accounting or end-user control bypass |
| §§1.10–1.11, 6.1–6.14 | Canonical change discipline, US01–20, stage exits/failure tests/reports, all expected dynamic efforts | Phase details, coverage and design-method change propagation; native records own concrete implementation evidence. Every applicable Phase 3 effort accounted; core demonstration differs from complete accounting |

### Repairs and source distinctions

- Added full-system architectural acceptance obligations and explicit downstream usability; Intent is one component, not the M1 coverage proxy.
- Standardized Screening tie/invalid-score behavior, added the Opportunity Card bottleneck field and model-registry/route-decision information.
- Specified containerized Codex IPC/credential prerequisites, persistent volumes, trusted pinned provisioning, archive containment and baseline immutability.
- Distinguished intake qualification/scientific interpretation from trusted capture hashing. Existing protected hash contracts remain; no new intake-signing or evaluator crypto service.
- Preserved D5/D6 and conditional Phase 3/RSI scope. Did not reinterpret supported-device/API availability or OS enforcement as already proven compatibility.
- Added tier-specific human review and change propagation without introducing coding authorization cards.

### Additional connected challenge cases

| Challenge | Required designed outcome |
|---|---|
| Equal/missing/duplicate/out-of-range Screening scores | Equal sums use stable IDs; invalid required scores halt without imputation |
| Forbidden dependency or no eligible idea/model/CC | Filter against declared policy; empty eligibility blocks, never substitutes an invented capability |
| Blueprint path exists but required data/measurement is unavailable | Block before Builder/empirical work; do not infer resources or manufacture validation |
| Archive traversal/link or unresolved dependency closure | Protected provisioner rejects before extraction/execution; no dynamic repair |
| Treatment changes baseline or metric definition | Reject conformance; original captured baseline and protocol stay immutable |
| Container restarted/recreated, account volume distinct | Saved results remain inspectable; interrupted attempt paused, no replay; workspace deletion does not delete account |
| Missing subscription/device or model IPC exposed over TCP | Execution readiness blocks; no mock pass, unsafe proxy or hidden host helper |
| POC reads credentials/control/fixtures or uses denied network | Enforced denial and retained failure evidence; packaging/venv alone cannot pass security |
| Native cache/retry hides fault or uncaptured effect | No acceptance; record uncertainty and stop new dispatch |
| Incomplete experiment outcome rules or report contradicts saved verdict | Block artifact acceptance; no favorable classification invention |

### Review limits and remaining human decisions

The architecture selects behavior and information at material M1 boundaries. Private enforcement mechanisms, concrete transport adapters and selection algorithms require native specifications within these constraints. Actual installed compatibility, reproducibility quality, scientific judgment quality and OS isolation remain unproven by documentation.

Human review has not been performed or approved by this authoring pass. Review the three-document route for whole-system/deployment clarity, then the affected component obligations, provisioning/routing/RSI boundaries and consequential fields. Ask whether any supplied research case still requires an unstated material decision; whether cautious blocking distinguishes optional omissions; and whether intended future seams justify the present standardization. No unanswered material decision is knowingly claimed as resolved runtime behavior.

The clause pass additionally restored hash-chained RSI attempt/lineage/score reconciliation, human security clearance with remediation evidence, explicit target-profile headroom calibration, and lossless trajectory/truncation/activity-log bootstrap obligations. Retained RSI numeric limits are identified as architecture policy; the current PRD states these obligations qualitatively.

### October 7 checks: preserved original experiment

- Full input: six critical schemas plus common definitions, 34 indexed examples/context records, 12 deliberate invalid cases, exact references/source spans and selected gate relationships pass. Required field summaries, versions, source hashes, 188-heading index and US01–20 mapping pass.
- Package navigation: 948 local links/fragments in the full package and 761 in the compressed package pass. Five-document routes contain 4,370 and 1,973 whitespace words respectively, including diagram text. Heading coverage remains an index; the clause obligation/disposition table above supplies the behavioral review.
- Diagram review: audited all 26 full-package views, rendered SVG/PNG and inspected contact sheets plus enlarged changed views. Explicit build/measurement deterministic checks, committed-acceptance/halt edges and resource-to-Hypothesis connection are repaired. The cut-down input retains two rendered system/deployment views with identical source meaning. Projection hashes pass. Long views support SVG zoom; rendering is not behavioral proof.
- Compression: 23,882 → 7,693 whitespace words across the same 20 explanatory documents, a 67.79% reduction. PRD/source receipts, identical contracts/examples, glossary/index, governance/review material and generated projections are excluded from this measure; total package size is not claimed to shrink by that percentage.
- Experiment: 65 reference/source/field-inventory files are byte-identical; eight responsibility/phase/decision tables and two diagram definitions match. Frozen complete input inventories and word counts pass. Six deliberate inventory/manifest omissions, duplicates, stale hashes and path escapes are rejected. Comparison is a protocol, not an observed agent outcome.
- Preservation: all 151 checkpoint hashes rechecked; current received sources and old very-condensed document unchanged. Both package trees retain exact bytes under Git clean filters; narrow ignore exceptions expose experiment contracts for tracking. Working/staged whitespace checks pass.
- Standalone full and cut-down copies are frozen outside the repository and validated independently through the same comparison/portable validators. Their identities are checked against final input manifests.

No application implementation, agent build experiment, commit or push was performed. Human tier reviews remain required and unperformed. Installed model/device support, concrete OS confinement, scientific quality and actual M1 acceptance require implementation evidence. Private realization choices remain constrained specification work rather than unresolved product behavior.


## October 8 contract and reading review

Current definitions supersede the earlier six-schema counts below. Earlier executed-check sections are historical receipts for their dated package snapshots. The original full/compact experiment remains pinned to its original bytes. Current results below concern the repaired design and the separately registered October 8 pair.

### Gap dispositions and connected checks

| Gap | Selected disposition / architectural home | Integrity check |
|---|---|---|
| Incomplete dispatch contracts | Seventh exact schema; bindings, per-CC authority, node/checking budgets, typed concrete inputs/outputs and independent guard pins in reference/node-execution | Four complete contracts; invalid binding/port/inventory/limit cases rejected |
| Ambiguous field representations | 35 named major field contracts; shared nested types; catalog-resolvable CC ports | Typed example checks, names/version summaries and public-port resolution |
| Detached examples | Linked synthetic Brief-to-negative-Delivery and RSI-to-admission/activation/rollback | Exact-byte refs, scope, protocol/metric/ranking/lineage and candidate-body relationships |
| Target 1 scoring/headroom | Passed tests first; paired time only at ties; calibrated conservative improvement rule in offline-rsi | Profile order, split identities, query/final-use rules; actual calibration remains unmeasured |
| Builder lock/install ownership | Protected prepared catalog → Hypothesis lock → unchanged Builder package → trusted provisioner | ZIP contents match manifest/lock hashes; runtime provisioning/confinement remains unproven |
| Hidden admission authority | Separate binder/gate/admission owners on README map/table | Updated overview rendered and visually checked; RSI still outside live DAG |
| Excess mandatory reading | Three-document route; phase/slice detail selected by assignment; deeper component ownership in design-method | Full route 2,898 words versus previous 4,370 across five files; critical full principles retained in compact |
| Experiment drift / unfair scope | Original pair frozen; new paired inputs share source/contract/example/decision content | Separate inventories, same responsibility/phase tables, real headings and bounded assignment |

R1–R8 in [decision review](decision-review.md) give alternatives, pros, cons and consequences. No known material outcome in these audited gaps remains delegated as an unanswered product question. A selected format or threshold is a standardization choice, not a proven optimum. Unsupported environment, confinement or calibrated headroom blocks the affected work; implementation agents cannot relax contracts to make it pass.

### Documentation check receipt before final independent review

- Seven critical Draft 2020-12 schemas plus common definitions; 62 indexed synthetic example/context records; 23 targeted invalid cases; source-span bounds and exact reference hashes; selected gate, dispatch, scientific and RSI relationships pass.
- The current 188-heading index and US01–US20 mappings, source receipt hashes, package-local links/fragments, field summaries/versions and diagram-source/projection identities pass. Heading coverage is an index; the clause dispositions and scenario tables above supply behavioral analysis.
- Full has 26 maintained views (24 product, two separately scoped tooling); compact has nine (seven product, two tooling). Selected diagram definitions retain the same meaning. Changed overview and generated compact views are rendered; visual checks examine clarity and crossings, not runtime behavior.
- Explanatory scope: the same 20 files contain **24,417 full words versus 15,093 compact words**, a **38.19% reduction**. Immediate routes contain 2,898 and 2,251 words. Counts include tables/diagram text. Identical source/reference/governance files are excluded; no claim of that reduction in total package input tokens.
- All 253 pre-edit checkpoint file hashes pass independently. Original sources, historical condensed input and original experiment input bytes remain preserved. New full/compact copies are validated independently outside the checkout before freezing their comparison manifest.

These are documentation checks and author scenario review, not completed independent human review, experimental agent outcomes or runtime acceptance. Scientific fidelity, provider availability, concrete OS confinement, durable transaction correctness and empirical RSI headroom require implementation evidence. No application implementation, paired agent build, commit or push is included.

### Focused human review

Review R1's execution/authority fields, R4's lawful but calibration-dependent improvement objective, R5's prepared-dependency constraint, and the three-document orientation. Review full-M1 responsibilities/phase exits next for the assigned build; domain reviewers inspect changed consequential contracts. The four questions in decision-review are review prompts about chosen behavior, not open architecture placeholders. Human review completion must be recorded from actual review.


The final field/prose consistency check additionally made invocation token/cost usage explicit, with nullable values and unavailable reasons. Both revised experimental conditions receive identical fields/examples. A pre-trial manifest receipt records the superseded first freeze; revision 6 is the usable October 8 input. No participant results were invalidated because no trials were run.

The final tier/context crosscheck corrected design-method to the three-document route and made RSI scorer/improver/configuration pins, equal batch workload and attempt observations explicit. Versioned pre-trial receipts preserve superseded manifest identities; no participant input or result is silently reinterpreted.

### Final independent review dispositions

The independent reviewer identified named planning-port gaps, ambiguous multi-CC execution, optional-port checking, RSI custody/clearance fields and newline-normalized source-span checks. R9 records remedies and tradeoffs. User clarified composition/merging is later work: M1 uses one work CC per node and separate gated nodes for additional work, resolving the member-wiring gap by deferral. Named planning fields, security-clearance and attempt genesis/profile pins close existing boundaries. Checker regressions cover concrete/future inputs, named ports, optional omissions, missing work observations, unsupported member composition, custody omissions and exact CRLF/non-BMP spans. This is documentation verification, not observed execution.

### Final independent review and verified package receipt

The independent reviewer examined the actual PRD, full design, shared contracts and experimental controls, then rechecked the corrections. Five substantive findings were resolved:

| Finding | Disposition |
|---|---|
| Planning could not represent concrete inputs or named outputs | PlanInput/PlanOutput and separate connected research-node example; future bindings resolve predecessor port/type/version |
| Multi-CC nodes lacked internal wiring | User confirmed one work CC per M1 node; additional work uses separate gated nodes. Composite/merged CCs and member graphs remain later work; no new composition machinery retained |
| Optional ports treated as mandatory | Required-only inventories; validate present optional ports; positive optional omission/output checks |
| RSI chain custody and security clearance lacked fields | Exact hash-profile/genesis pins plus independent security-clearance record; clearance cannot activate a child or resume a violated session |
| Source-span offsets checked on normalized newlines | Decode exact bytes; CRLF/non-BMP fixture verifies positions and slices |

The reviewer found no further actionable contradiction in compiler/verifier/gate authority, scientific-negative delivery, D5/D6 exceptions, Docker/client placement, prepared dependency ownership or declared experiment controls. This is independent agent review, not completed human approval or proof of runtime behavior. R9 preserves alternatives, costs and rationale.

Final checks pass: seven critical schemas plus common definitions; 36 named field contracts; 68 indexed example/context records; 32 negative cases; exact reference/source hashes, selected cross-record relationships, 188 PRD heading mappings and US01–US20 dispositions, local links and 26 full/nine compact diagram identities. Diagram sources did not change in this review; existing rendered views remain exact.

The final three-document route is **2,911 full / 2,264 compact words**. The matched 20 explanatory files are **24,554 / 15,149 words**, **38.30% smaller** in compact. Shared source/reference/decision files and M1 scope remain identical. The original experiment pair is unchanged; explicit receipts retain superseded unused October 8 freezes, with revision 6 current. Full and compact copies are checked outside the checkout. No agent implementation trials, application tests, commit or push were performed.

The author's final fixture check also binds planning obligations to the accepted Brief and rejects unknown IDs. Revision 6 records this matched correction; it changes no architectural decision or compression measurement. Independent reviewer conclusions precede this mechanical fixture correction; final validators cover the delivered bytes.
