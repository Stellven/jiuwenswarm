# Architecture decisions

`Tier 2 · Part of: [Method](README.md)`

Review the reasoning, then the linked definitions. These are selected standards, not proven optima and not runtime passes. The PRD bytes and D1 to D18 keep their authority.

## Review records R1 to R12

One line each. Superseded records are dropped.

- R1: one exact Node Execution Contract schema. The binder stores a template at freeze and the scheduler builds the concrete contract at dispatch (D28 to D30).
- R2: other shared fields are named in one [field catalog](../reference/field-catalog.md), with a closed required core.
- R3: linked synthetic examples show relationships, including negative science and inactive RSI candidates.
- R4: Target 1 ranks by passed hidden tests first and by paired helper time only at equal pass counts. Timing is a secondary improvement.
- R5: dependencies come only from a prepared lock catalog (see below).
- R6: binder, gate and library admission are separate authorities. RSI makes an inactive candidate and a human changes future selection.
- R7: read README, then system architecture, then principles. Detail sits in the second tier, selected by question.
- R9: planning uses named PlanInput and PlanOutput fields. M1 runs one work CC per subnode. Composite CCs stay later work.
- R10: exact schemas for the consequential boundaries, named field contracts for the rest, and a contract index.
- R11: the Intention Compiler is the whole PRD node. Success is `research_brief.json`. Earlier one-CC "nodes" are subnodes.
- R12: the routing owner's work joins through one shared capsule-routing contract. The Codex baseline stays. D5 is source-aligned and D6 remains a documented departure.

## R5: Separate dependency selection from resolution and installation

**Decision:** protected environment preparation supplies a reviewed dependency catalog with exact direct/transitive locks and immutable package hashes. Resource qualification exposes compatible catalog entries. Hypothesis selects the environment; Builder emits that exact selected lock and bounded code. The trusted Stage 3.7 provisioner checks the lock and installs only those bytes in the isolated environment. Generated code never resolves or installs packages. The Builder declares its dependencies in `requirements.txt` (PRD 1133) and never installs or discovers them. Packages come only from the prepared lock catalog that Hypothesis selects from. Adding a new framework needs protected preparation before the run.


**Review obligation:** no compatible lock or missing package blocks before scientific execution. Provisioning cannot repair the declaration. Hashes establish identity, not package safety; review and confinement remain necessary. [Deployment ownership](../platform/README.md#dependency-preparation-and-provisioning).

## Decisions and source amendments

| ID | Current decision | Source disposition |
|---|---|---|
| D1 | Original full-product phase allocation: static Phase 1; bounded planning later. M1 planned-mode scope amended by D19 | §§1.3, 4.8, 6.5, 6.12; no live restructuring |
| D2 | Deterministic checks, independent verifier, protected gate | §§1.4, 4.2; replaces optional semantic checking |
| D3 | Protected host owns release; freeze referee assets | §§4.1.5, 4.2.8, 4.4.5 |
| D4 | No automatic repair/replay; blocking outcomes halt | §§1.4, 4.6.4; human correction is new linked work |
| D5 | Separate bounded generative Intent and Requirements CCs, each checked | **Aligned with PRD (4)** §§3.2/4.7: architecture defines internal bounded, non-interactive sequencing. The earlier single-generation exception is historical. Freeze combined budgets |
| D6 | One Docker app, Python/TypeScript, SQLite state and artifact files | **Authorized local realization/exception** to source container/native-only and persistence assumptions in §§4.1.4, 4.5, 5.1, 5.2, 5.4. Generated-code confinement remains separately required |
| D7 | Preserve CC concepts with one reconciled current machine contract | §4.1; historical sources are provenance, not competing serialization authorities |
| D8 | Full-product Phase 2 offline RSI; M1 design keeps it independently buildable and non-blocking | §§1.3, 4.4, 6.11; immediate slice excludes execution |
| D9 | Mandatory evidence fails closed; optional telemetry can be unavailable | §§1.4, 4.2, 4.5, 6.4 |
| D10 | Verifier assesses; gate decides; control plane shows halt/triage | §§4.2, 4.3.4, 4.6.4, 5.3; headless never waits |
| D11 | Optional benchmarker uses ordinary scoped client boundary | §§5.3.1, 5.6.5; no privileged product control |
| D12 | Durable product identity/profile separate from local execution host | §§1.1, 2.3, 5.4; optional cloud profile storage grants no remote execution |
| D13 | Node objective/contract differs from CC invocation | §§1.4, 4.1, 4.2; per-call checking plus node aggregate acceptance |
| D14 | Account for broader product stages/phases; D19 separates the M1 Planner path from other Phase 3 work | §§1.3, 6.12, 6.14; preliminary Leader checks never replace plan acceptance |
| D15 | Independent guard profiles and output-led evidence review | §§1.4, 4.1, 4.2, 5.4; review is assessment, not replacement authorship |
| D16 | Three reading levels; critical schemas and other major field contracts | §§1.7, 6.13 and October 7 user direction; replaces agent-owned competing wire shapes |
| D17 | Intent acceptance requires fidelity **and** usefulness to Requirements. Under D24 the Intent and Requirement CCs own these as producer obligations, backed by host span and reference checks. The verifier does not judge them | §§3.2.1, 4.7.3, 4.2; topic-only extraction with material missing purpose/result blocks |
| D18 | Readable IRs, decisions and views; raw evidence separate | §§5.1.2, 5.3.1, US05–US17; no mandatory opaque binary decoding |
| D19 | Bounded Planner path is targeted M1 work; static Phase 1 mode retained; RSI independently buildable and non-blocking | Realizes §§1.3, 4.8 and 6.12; preserves §4.2 checks and exact frozen dispatch. [Build plan](../3-build-plan.md) defines the M1 boundary |
| D20 | Semantic verifier input is the pinned declaration and the exact output only | Departs from the relevant-upstream-context reading of §4.2.1. See [D20](#d20) |
| D21 | November increments: Generalist, automatic generation, automatic admission for future plans, better planning and MCTS. Composition in December | Continuation allocation. See [D21](#d21) |
| D23 | Internal names are lowercase: files, ports, artifact types, check and criterion IDs | Realizes PRD artifact names as lowercase internal files. See [D23](#d23) |
| D24 | Verifier criteria are output-only. Fidelity and preservation are Intent and Requirement producer obligations | Narrows §4.2 verifier duties consistently with D20. See [D24](#d24) |
| D25 | Every CC has a declaration, a field table with constraints, a check bundle and verifier criteria in one tier 3 page | Extends D16. See [D25](#d25) |
| D26 | Build the static fixed DAG first, then the Planner, both producing one frozen run plan type | Follows PRD §2 default over dynamic. See [D26](#d26) |
| D27 | One maintained design package. The compact copy is retired | Design practice, no PRD change. See [D27](#d27) |
| D28 | Every DAG leaf is a Delivery node. M1 plans have exactly one leaf | Realizes §3.9 and keeps §§3.4, 3.5 single path. See [D28](#d28) |
| D29 | The PRD Evaluator Gate is built as check bundle, verifier CC and gate decision. Per-output decisions. The PRD minimum gate result is a view | Realizes §4.2 without a second record. See [D29](#d29) |
| D30 | An infeasible plan halts and starts a linked new Intention Compiler attempt | Realizes §4.8.3 routing back to the Intention Compiler. See [D30](#d30) |
| D32 | Unsupported citations and claims are caught by deterministic host checks at Tier 1, not by the verifier | Consequence of D20 for PRD §4.2.9 case 4, §4.2.6 and §2.8. See [D32](#d32) |
| D33 | Phase 3 implementation status is reported separately; Dynamic Agent Planning is the targeted full M1 item | Realizes §1.3 Phase 3 and §6.12. See [D33](#d33) |
| D31 | The RSI workbench and the platform benchmark runner run in their own containers beside the application container | Amends D6 (one application container) for side systems only. Realizes §§1.3, 4.4 isolation. Amended by D36: the benchmark runner is in the sidecar container. See [D31](#d31) |
| D34 | Restore the CC's own RSI permission: `evolution.rsi` and the `evolution.may_change` allowlist, plus the other CC fields lost on October 6 | Realizes §4.4 "explicitly designated as mutable". See [D34](#d34) |
| D35 | M1 runs on one server host (the GB10). Users reach the app container over the private LAN or VPN with token authentication | Amends D6. Departs from the loopback-only rule of §5.4.2. See [D35](#d35) |
| D36 | One sidecar container holds the platform benchmark runner and the test runner | Amends D31 for the benchmark runner. Realizes §5.6.5. See [D36](#d36) |
| D37 | Data Foundation records are adopted with rulings: the Capsule Run Record extends the invocation observation, and derived records never block | Realizes §4.5. See [D37](#d37) |
| D38 | The package is the authoritative M1 design. One canonical term per concept, with forbidden synonyms checked by the validator | Design practice. See [D38](#d38) |
| D39 | The run setting `plan_source` (`static` or `planned`) is the only way to choose the plan source | Realizes §§1.3, 2.7. See [D39](#d39) |
| D40 | PRD core M1 gate is Phase 1; Phase 2/3 commitments are reported separately | Realizes PRD V.10 §§1.5, 6.12 and 6.14. See [D40](#d40) |
| D41 | A rollback is a standing move: a human reactivates an earlier version. No new version is built | Realizes §4.4 human activation and rollback. See [D41](#d41) |
| D42 | CCs know nothing about the workflow. Placement rules live in the plan policy and binder checks | Realizes §4.1 reuse. See [D42](#d42) |
| D43 | The Builder's agent work is one synchronous headless Codex CLI invocation per CC call. The DAG sees one request and one response | Realizes PRD 1.3 (no multi-turn conversational streaming in the DAG). See [D43](#d43) |
| D44 | The API router is a separate, killable process inside the app container, reached only through `RouterPort` over local IPC. It returns a model choice only. A router failure never fails a run | Amends owner ruling routing row 13. Realizes PRD 1.3 (the Codex fallback) and §4.3. See [D44](#d44) |
| D45 | The Builder's Codex CLI call runs under the executor identity in the POC workspace with `workspace-write`, no network for tool commands and approvals `never`, using a dedicated, budget-limited, revocable credential | Amends D43. Realizes PRD §3.6.2 and §5.4 confinement. See [D45](#d45) |
| D46 | A human activation makes an RSI child selectable in the RSI workbench sandbox first. Adopting it into live runs is a manual promotion plus a new static template. The custodian signs candidate evidence and admission verifies it | Refines D41 and D8. Realizes §4.4 human activation and §4.4.9. See [D46](#d46) |
| D47 | A static template uses selectors (`all_mandatory_requirements`, `all_deliverables`, `all_evidence_obligations`) instead of Brief IDs. The binder expands them before `brief_coverage` runs | Refines D26. Realizes §2 (static default over any Brief). See [D47](#d47) |
| D48 | A submission carries `interaction_mode` (`interactive` or `headless`). The run configuration freezes it for intake clarification; D50 governs later execution | Refines D10 and D29. Realizes §§4.2, 5.3. See [D48](#d48) |
| D49 | A failed node stops only itself and the nodes that depend on it. Independent nodes keep running in Kahn order | Realizes §§1.4, 4.6 halt semantics for an unattended long-running service. See [D49](#d49) |
| D50 | Runs are unattended after intake. Nothing mid-run waits for a human; escalations are records for later review | Refines D10, D48. See [D50](#d50) |
| D51 | Sidecar jobs may delegate bounded environment and host operations to the host launcher | User-authorized expansion on October 15. Extends D11 and D36 without adding product authority or a core dependency. See [D51](#d51) |

## D19

The M1 design supports a fixed Phase 1 static template and the targeted Phase 3 Planner path. The static template satisfies the PRD §6.5 fixed-graph stage exit. The Planner proposes a bounded graph before dispatch; the same protected binder validates and freezes either source. Dynamic Agent Planning is targeted for full implementation, integration and verification during M1, but does not independently block the PRD Phase 1 core gate ([D40](#d40)). This preserves the PRD phase boundary while making the planned path an explicit architectural capability.

## D20

**Authorized semantic-review scope change.** Give the LLM reviewer the pinned declaration and exact worker output only; retain input/runtime evidence in protected deterministic/host processing. Do not replay worker input or conversation under another field name. This removes from the Tier 2 input the relevant upstream contracts, the evidence bundle and the node acceptance criteria that PRD §4.2.1 lists. It narrows the Tier 2 duties of Domain Policy §2.8 (evidence support, citation integrity) and §4.2.6. Those duties move to deterministic host checks, see [D32](#d32). Criteria are output-only ([D24](#d24)). The received PRD is unchanged; record the departure and limited assurance in native implementation acceptance.

## D21

**Authorized continuation allocation and promotion change.** Generalist, automatic generation linked with offline RSI, automatic admission with future-plan eligibility, and planner/MCTS improvements are November increments. M1 retains its human-activation policy; M2 protected admission may make a passing version eligible automatically. Proposers cannot activate themselves, broaden authority or alter running DAGs. Composition/fusion is December. Reconcile the continuation PRD and record unresolved conflicts before its conditional architecture freeze.
## D23

**Lowercase internal names.** Every file the system writes uses a lowercase name unless the user explicitly asks for a different one. Ports, artifact types, check IDs and criterion IDs use lowercase snake_case. The PRD sometimes uses capitals, for example `Research_Brief.json`. The [glossary](../glossary.md) maps those names to `research_brief.json`. Reason: people design on Windows, but the product runs in Docker on Linux, where file names are case sensitive. Mixed case would let two names for one artifact coexist. Enum values keep the spelling of their schema. Rules: [capsule references](../reference/capsules/README.md#naming-rules).

## D24

**Output-only verifier criteria.** Every verifier criterion must be answerable from the pinned declaration and the exact output. Request fidelity and Brief preservation move to the Intent and Requirement CCs as producer obligations with their own self-review. Host checks back them with span bounds, reference resolution, requirement-link coverage and default authorization. The generic criteria are `declared_output_conformance`, `internal_consistency` and `limitations_consistency`. Each CC page adds its own output-only criteria. Reason: a verifier that reads the worker input redoes the task and inherits its context errors. Consequence: no semantic check establishes fidelity. Benchmark cases measure it instead.

## D25

**One build page per CC.** Each work CC and the verifier CC has one tier 3 page with a declaration example, typed ports, a field table with constraints, producer obligations, a check bundle, verifier criteria, a gate rule and failure outcomes. Field tables with plain-English meanings remain the standard for research artifacts. Exact JSON Schemas stay limited to the critical records listed in [reference](../reference/README.md). Examples illustrate. Tables define. Reason: a coding agent must build each CC without inventing shared fields. Index: [capsule references](../reference/capsules/README.md).

## D26

**Static first, then planned.** The first runnable path is a hand-authored static template over the research CCs. The Planner then produces a proposal that the same binder turns into the same frozen run plan type. Both modes use the same dispatch, checks, gates and storage. Reason: PRD §1.3 and §2.7 make the fixed Phase 1 path the baseline that dynamic planning (§4.8) is tested against, and a working static path gives a baseline to debug the Planner against. A static run does not count as planned-mode acceptance. Contracts: [run plan](../reference/run-plan.md).

## D27

**One maintained package.** The compact package is retired. Keeping two packages in step doubled every edit and let them drift, and no paired experiment showed that the compact copy performed as well. Shorten this package by removing repeated explanation. Keep tier 3 contract detail. The last compact version is in Git history at commit `c6c6f08b0`.

## D28

`Standard`. **Delivery per DAG leaf, one leaf in M1.** A leaf is a node that no other node depends on. Every leaf of a plan is a Delivery node, and every Brief deliverable is covered by exactly one leaf. The PRD selects one Top-1 opportunity (§3.4), forbids competing claims (§3.5, "a single deterministic path") and locks one report template (§3.9.1). So every M1 plan has exactly one scientific path and exactly one Delivery leaf, which writes the single output directory of §3.9.3. The binder enforces this with `delivery_leaf_coverage`. Several leaves, assembled by protected host code into one output directory, are later work. Reason: the rule keeps the plan shape general for later milestones without breaking the M1 single path.

## D29

`Standard`. **How the Evaluator Gate is built.** The PRD's Evaluator Gate (§4.2) is three parts. The check bundle (Tier 1) runs once per work subnode over all its outputs. If any mandatory check fails, no verifier runs. Otherwise the verifier CC (Tier 2) assesses each output, and the gate host writes one subnode-scope decision per output, naming it in `output_port`. A node-scope decision aggregates them. The PRD minimum gate result (§4.2) is a view built from these records, with the field mapping in [checking](../reference/checking.md#prd-minimum-gate-result). Under [D50](#d50), `FAIL`, `ENVIRONMENT_BLOCKED` and `INCONCLUSIVE` halts map to `ESCALATE_TO_HUMAN`: a record for later review, never a mid-run wait. Other halts map to `HALT`. The verifier on a `plan_proposal` is PRD §4.2 Tier 2 self-consistency checking of one output against its declaration ([D20](#d20)). It is not the agent peer review the PRD blacklists (PRD 2341). Reason: one record per decision, and PRD consumers still get the PRD shape.

## D30

`Knowledge`. **Infeasible plans go back to the Intention Compiler as new work.** PRD §4.8.3 routes an infeasible plan back to the Intention Compiler for replanning. The package does this by halting the planned run with a `plan_infeasible` outcome and starting a linked new Intention Compiler attempt that carries the reasons. The failed attempt is never rewritten. A request gets at most two plan attempts: the original and one linked new attempt (depth 1 and 2). After the second outcome the host halts for a human ([plan outcome](../reference/run-plan.md#plan-outcome)). This is the only automatic follow-up in the system. It is not the retry or repair loop the PRD blacklists (PRD 1495, 2236, 2252). It is the single PRD §4.8.3 route-back: a new linked attempt, not a retry of the failed node. It happens at most once per request, so the linked new attempt is the second and last plan attempt. A node gate failure never triggers it. Only plan infeasibility does. This applies to planned runs only. A rejected static template is a Phase 1 fault: the run halts for a human, with no automatic new attempt (PRD §2.7, §4.6.2). Reason: headless runs never wait, and a failed attempt stays as evidence.

## D31

`Knowledge`. **Side systems run in their own containers.** D6 keeps the product in one application container. The RSI workbench and the platform benchmark runner run in separate containers on the private network. Neither is needed by a research run. The RSI workbench reads the record export and writes candidates to the admission inbox. Inside it, candidate code runs under a separate process and identity from the referee and the hidden fixtures (PRD 4.4.9). It reaches models through its own bridge instance with its own allowlisted credentials (PRD 1.3). Reason: RSI and benchmarking must never share a trust boundary with live research, and must never block it.

## D32

`Knowledge`. **Citation and evidence support is checked at Tier 1.** Under D20 the verifier sees only the declaration and the output, so it cannot compare a claim with the evidence bundle. Deterministic host checks do this instead. Every cited source must resolve to captured evidence by hash (for Search: `citation_source_resolves` and `idea_citations_resolve`). Every quoted excerpt must match its span. Every measurement in a report must match the accepted payload (Delivery's `ref_hash_match` and evaluation recomputation). PRD §4.2.6 adds three faults. A conclusion that materially exceeds the evidence is caught by evaluation recomputation from the payload against the registered thresholds, by Delivery claims that must cite accepted refs (`ref_hash_match`) and by matched numeric claims, plus a producer obligation on Scientific Evaluation and Delivery. An artifact that contradicts its evidence is caught by the same hash and recomputation checks. An impossible value is caught by `measurement_within_declared_range`, which uses the metric bounds `valid_min` and `valid_max` registered in the `hypothesis_blueprint`. The verifier keeps internal consistency, conformance and limitations consistency. See [verifier criteria](../reference/capsules/verifier.md). PRD §4.2.9 case 4 expects Tier 2 to detect an unsupported citation. In this design the same fault is detected at Tier 1, and the gate emits `FAIL`. The case passes when the fault is caught and the run halts, at either tier. This departure from the case's tier wording needs product confirmation. Reason: a verifier that reads the evidence redoes the work and inherits its errors (D24), while hash and span checks catch fabricated citations exactly.

## D33

`Standard`. **Phase 3 work is M1 work, reported on three axes.** The PRD places dynamic planning, capability binding, routing, the alternate verifier, Agent Team and Cluster Mode, advanced compilation and Code Mode in Phase 3, which is part of M1 (PRD §1.3). Phase 3 may be built in parallel with Phase 2 and does not wait for Stage 8 (PRD V.10 §6.12). The Planner realizes planning assigned to the Cluster Mode Leader Agent (PRD §§4.8.1–4.8.3). Other applicable Phase 3 items remain M1 implementation scope; missing endpoint access may use mocks where the PRD permits (PRD §4.3). The Phase 3 completion report gives each item separate implementation, integration and verification statuses (PRD V.10 §6.12). Implemented but unverified is never `PASS`. Dynamic Agent Planning is the targeted full M1 item ([D19](#d19)); its `PASS` needs positive-path evidence that a valid plan reaches governed execution and negative-path evidence that an invalid or blocked plan starts no downstream work. The static template stays available. Model Routing is an implementation commitment; integration and verification do not block the PRD core gate ([D40](#d40), [D44](#d44)).

## D34

`Standard`. **The CC says what RSI may change.** Commit `36436834a` (2026-09-29) gave the declaration `evolution.rsi` (`none`, `propose`, `submit`) and `evolution.may_change`, an allowlist of declaration paths and `files:<glob>` entries. Missing or empty means RSI may change nothing. The October 6 rebuild from an earlier declaration format replaced both with the denylist `evolution.frozen` and moved the allowlist into the RSI target profile, with no recorded decision. This decision restores the allowlist. `evolution.frozen` is removed. The target profile's `mutable_paths` must be a subset of `may_change`. Screening's `may_change` covers the ranking helper (Target 1) and the work prompt and work rubric (Target 2, conditional on the headless model path, which in M1 is the Codex CLI); referee-owned rubrics are never in any `may_change`. `submit` is rejected in M1, because admission is manual and a human activates. Verifier CCs and the CCs that produce gate evidence are `rsi: none`. The same rebuild also dropped `guarantees.failure_modes`, `needs.secrets`, package and lockfile pins, `needs.external[].purpose` and `needs.human_interaction`. They are restored with the M1 status given in the [declaration](../reference/declaration.md). The `interface_hash` stays later work: M1 compares exact declaration bytes. Reason: PRD §4.4 lets RSI change only material "explicitly listed as mutable by the target capsule", and the author, not the RSI operator, knows which parts are safe to change.

## D35

`Knowledge`. **One server host, reached over the private network.** The team decided to ship M1 as Docker, client-server, and the supervisor requires a client-server model. M1 never runs on a user's computer. Docker Compose runs on the GB10 GPU host: the app container, the sidecar container and, when a human runs it, the RSI workbench container, all on one private Docker network. The app listens on the server's private LAN or VPN address. Every request carries the session token in a header, and `jiuwenswarm-start` inside the app container prints the one-time token URL. This amends D6 and departs from the PRD's loopback-only binding (§5.4.2). The PRD's intent, no exposure beyond authorized users, is kept by the private network, the token and the absence of any public binding. Users upload their files to the server through the web UI or CLI, into the app container volume under `workspace/input/`, and users can delete them (PRD US03, US20). See the [control API](../reference/field-catalog.md#control-api). Reason: users work from their own computers, and the GB10 has the GPU the Research Benchmark CC needs.

## D36

`Knowledge`. **One sidecar container.** The platform benchmark runner and the test runner run in one sidecar container on the private network. Both are ordinary clients of the control API with their own scoped tokens. Neither is needed by a research run. The RSI workbench keeps its own container (D31). Reason: one container for every outside client that drives and scores the product, and one name for it.

## D37

`Knowledge`. **Data Foundation records.** The Data Foundation design (Suraj, 2026-09-29) is adopted with these rulings, recorded in [owner rulings](../side-systems/owner-rulings.md#data-foundation). The Capsule Run Record is the invocation observation, extended with its missing fields. Records are keyed by `run_id`, `node_id` and `attempt_id`, never by a framework agent ID. The Run Bundle stays the run-level manifest, and the raw per-call folders under `records/` are its referenced targets. Evidence the gate needs blocks release when it cannot be written. Every other hook, and every derived record (conformance, scorecard, sample export), never blocks a run. The owner's "Library Snapshot" is renamed "library analysis", because `library_snapshot` already names the Planner's list of eligible CCs. Reason: one record per fact, and the gate's durability rule wins over "hooks never block".

## D38

`Standard`. **The package is the authority.** For M1 design the package is authoritative. The PRD is authoritative for requirements. Build from this package and the separately supplied PRD; archived inputs are outside the delivery and have no implementation authority. Each concept has one canonical term in the [glossary](../glossary.md#canonical-terms), and the validator fails on the listed forbidden synonyms. One fact has one home: tier 3 for fields and checks, tier 2 for behavior and reasons, tier 1 for the shape of the system. Reason: coding agents read every page, and two wordings of one idea become two implementations.

## D39

`Standard`. **`plan_source` chooses the plan.** The run request carries `plan_source`, either `static` or `planned`, with `static` as the default. It is recorded in the run plan. No other setting, profile field or failure changes it. Reason: the PRD keeps the static baseline as the Phase 1 default and the Phase 3 fallback, and the choice must be made before the run, in one place.

## D40

`Standard`. **The PRD core M1 gate is Phase 1.** PRD V.10 §§1.5 and 6.14 require Implementation Stages 0–7, the end-to-end Phase 1 run, mandatory acceptance items, Evaluator Gate tests and Phase 1 evidence. Phase 2 and Phase 3 implementation coverage is reported separately and does not block this gate. RSI and Model Routing are M1 implementation commitments; their integration and verification are not required for core acceptance. Dynamic Agent Planning is the targeted Phase 3 item for full implementation, integration and verification. Its result is reported separately and does not independently block the Phase 1 gate. The platform benchmark pilot is separate from the product gate; its failure does not block a research run.

## D41

`Standard`. **Rollback is a standing move.** A human rolls back by reactivating an earlier admitted version, which is a change of standing in the library. No new version is built, so the lineage relation `rollback_of` is rejected in M1. Reason: one way to roll back, and no new version that needs its own evidence.

## D42

`Standard`. **CCs do not know the workflow.** A CC is a reusable module, like a tool, skill, MCP server or A2A agent. Its declaration and its build page describe only its ports, needs, effects, guarantees and behavior. Rules about where it runs in M1, such as "the Planner may not skip Screening", live in the plan policy and the binder checks. All control flow, including every gate that can halt a run, is protected platform code outside every CC. Reason: authors can write a CC without knowing the pipeline, RSI can change a CC without touching control flow, and no CC can weaken a gate.

## D43

`Standard`. **The Builder is one synchronous CLI call.** The Builder's agent work is one synchronous, headless Codex CLI invocation (`codex exec` style) per CC call. Codex does its own tool use (read, code search and write) inside the confined POC workspace. The DAG sees one request and one response, so there is no multi-turn conversational streaming between the runner and the model, which the PRD blacklists (PRD 1.3). The Builder's budget of 40 tool calls is enforced by counting the tool events the CLI reports and stopping it at the limit. A stop at the limit ends the call as a budget failure. The model router may route the Builder only to an API model that supports this same single-call tool loop. Otherwise the Codex route applies. Reason: the DAG keeps its synchronous request and response shape, and the limit is enforced by host code outside the model. Page: [Builder](../reference/capsules/builder.md). [D45](#d45) fixes how the CLI is launched and what it may reach.

## D44

`Standard`. **The API router is a separate process.** The API router runs as a separate process inside the app container. A person can kill it. `RouterPort` reaches it only over local IPC (a Unix domain socket in the container) and returns the router's model choice and nothing else. The router calls no provider, holds no provider credential and writes no route record. The model bridge dispatches to the provider and writes the route record and the call record. `RouterPort` enforces the 30 s deadline with its own timer. A crash, a hang, an invalid reply or an unreachable process gives the Codex fallback with the matching `router_failure` (`error`, `timeout`, `invalid_decision` or `missing`). A router failure never fails a run. A failure of a model the router chose halts the node like any other model failure, because the model is fixed once the call starts. The router is on only under an approved evaluation profile. Verifier subnode calls always use the Codex route, whatever the router says; only the Phase 3 alternate-verifier evaluation profile may override that. This amends [owner ruling routing row 2](../side-systems/owner-rulings.md#routing-v21) (in-process module) and establishes bridge-owned execution. The hot path now imports no router code at all ([import boundary](../reference/import-boundary.md)). Reason: a router that shares the process of the runtime can take the runtime down with it. A separate process can be killed, and the non-blocking test can prove that a killed router leaves a run unharmed.

## D45

`Standard`. **The Builder's tool use is sandboxed.** [D43](#d43) made the Builder one synchronous Codex CLI call that does its own tool use. This decision fixes how that call is launched. The confined-executor launcher starts it under the executor OS identity, with the POC workspace as its working directory, Codex sandbox mode `workspace-write`, the network disabled for tool commands and approvals `never`. It uses a dedicated Builder model credential that is budget-limited and revocable, never the app's main credential. The credential file is readable only by the executor identity for the duration of the call and is removed after it. The executor identity cannot read run state, other credentials, the library or the fixtures, because filesystem permissions deny it. One risk remains: a tool command inside the call can read the Builder credential. This is accepted and recorded. The credential's budget and its revocation bound the damage. The proof is PLT-11. Reason: the model runs commands here, so confinement must not depend on the prompt. [Builder sandbox](../reference/capsules/builder.md#tool-use-sandbox).

## D46

`Standard`. **RSI activation starts in the sandbox, adoption is manual, and candidate evidence is signed.** A human activation first makes an RSI child `active` for RSI-workbench sandbox selection only (`effect_scope` `rsi_sandbox`). Activating a child never deactivates the parent. Adopting a child into live runs is manual and takes two human steps. First a human records a promotion: an activation record that moves the active child from `rsi_sandbox` to `live_plans`. Then a human writes a new static template file that pins the child and points the operator config `cc.static_template_ref` at it. Runs frozen before that keep their pins (`activation_scope_matches_lineage`). Nothing adopts a child automatically. An RSI child gets the check bundle and checking profile pins of its parent at admission (`child_inherits_parent_check_pins`), because its ports and guarantees cannot change ([D34](#d34)). An activation record carries `to_standing` (`active`, `suspended` or `revoked`) and is checked for an admitted target, non-null check pins and an allowed move. The custodian identity `rsi_custodian` signs the referee evidence and the session result with a key that `rsi_worker` cannot read. Only `rsi_custodian` can write to the admission inbox mount. The admission command verifies the signatures against the custodian public key that the operator pinned in the operator config (`referee_signature_valid`). Reason: a child cannot reach production by a score or by one human click, and candidate evidence must come from the custodian, not from the code under test. [Activation record](../reference/field-catalog.md#activation-record).

## D47

`Standard`. **A static template uses selectors.** A static template is written once and bound to many Briefs, so it cannot know Brief item IDs. A coverage entry may use `selector` (`all_mandatory_requirements`, `all_deliverables` or `all_evidence_obligations`) in place of a concrete ID, and a node tag may hold the first two. Selectors are valid only in a static template. The binder expands them against the accepted Brief before `brief_coverage` runs and records the expanded coverage in the run plan. A Planner proposal must still use concrete IDs. Two Briefs with different IDs bind to the one template. Reason: without selectors the template would fail `brief_coverage` for every Brief but one. [Selectors](../reference/run-plan.md#selectors).

## D48

`Standard`. **Interaction mode is set on the submission.** A `client-submission` carries `interaction_mode`, `interactive` or `headless`. A web UI submission defaults to `interactive`. A CLI or sidecar submission defaults to `headless`. The control plane freezes the value in the run configuration at run start. Interactive intake may ask bounded clarification questions. Headless intake uses supplied answers or halts. After intake, both modes follow [D50](#d50): failures write escalation records and never wait for a person. A client cannot set `cc.router.*` or any other operator setting. The submission's `configuration_ref` is the operator's approved `config.yaml` snapshot. Reason: whether a person is present is a fact about the client, and intake must not guess it. [Client submission](../reference/field-catalog.md#client-submission).

## D49

`Standard`. **A node failure stops its dependents.** When a node's gate halts or its attempt fails, the scheduler marks that node failed and every node that depends on it, directly or through other nodes, as `skipped`, with the failed node named as the reason. Independent nodes continue in Kahn order. This includes an invocation budget limit or access denied within an intact isolation boundary. Protected stops outside a node, such as a library, plan, run-budget or security failure, halt the whole run ([dispatch rules](../reference/run-plan.md#dispatch-record)). An isolation breach or inability to enforce the security boundary is a run-level stop. Nothing is retried. Node failures end the run `partial` unless a run-level stop intervenes. Accepted artifacts and available evidence are kept. Delivery depends on every research node, so a partial run produces no report. In M1 the research path is one chain, so a failure there stops everything after it. Reason: an overnight run should keep sound independent work while the platform remains able to enforce its boundaries.

## D50

`Standard`. **Runs are unattended after intake.** The Intention Compiler resolves ambiguity before planning: it either produces a clear, accepted Brief or halts at intake. After that, the run sticks to the frozen plan and keeps going without waiting for anyone. Slight uncertainty is handled by the CC's declared defaults and recorded, never by asking a person. A gate verdict of `FAIL`, `ENVIRONMENT_BLOCKED` or `INCONCLUSIVE` stops that node (D49) and writes an escalation record for later human review. No run ever pauses for a human answer. `interaction_mode` (D48) applies only to clarification at intake. Reason: a run that waits for a human at night wastes the night, and recorded evidence lets people review every stop in the morning.

## D51

`Standard`. **Sidecar jobs can prepare and inspect their own experiments.** On October 15 the user authorized broader sidecar access so it can run the benchmark families and workflow experiments, rather than require manual setup for each one. The existing host launcher may execute finite, job-scoped operations for the sidecar coordinator: pinned environment preparation, disposable-target lifecycle, declared visible-fixture staging, bounded diagnostics, and approved RSI sessions through the existing custodian. The [sidecar contract](../development-tools/sidecar/README.md#host-executor) owns target identity, grants, resource ownership, limits, evidence and cleanup. Spec Kit defines the detailed transport and operation schemas.

App runs and evaluation entry points still use their authenticated product boundary. Launcher grants give no right to write accepted outputs, waive checks, change admission or read protected labels. Docker credentials remain with the launcher. Standing targets require explicit grants, and automatic cleanup touches only job-owned resources. The base deployment remains three services (D35 and D36). A job may create additional disposable targets within its own limits and cleanup scope.

The launcher extension is optional and need not be a permanent service. Its absence blocks only jobs that need its capabilities. The app never imports it or waits for it. Job resource limits must preserve core capacity on the shared host. A missing optional observation is recorded as unavailable, while missing evidence essential to a benchmark prevents a success claim for that case. This expands benchmark infrastructure access without changing the PRD core gate.

## D52

`Standard`. **One design package plus the separately supplied PRD.** On October 16, 2026 the user authorized removal of competing design inputs from delivery and preservation of exact originals outside it. The package now owns all adopted component behavior, inventory and acceptance scenarios. Archived inputs and historical designs are not linked or delegated implementation authority. The current external PRD identity and clause mapping remain; its body and historical receipts are excluded. Product requirements and authorized departures are unchanged. The [JiuwenSwarm foundation](../platform/native-reuse.md) records concrete reuse, required adaptations and exact source observations; documentation validation creates no runtime PASS.
