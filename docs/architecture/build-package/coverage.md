# PRD coverage and architecture review

**Result of this review:** the design preserves the complete M1 research journey and required offline RSI. It now defines stage handoffs, state/data ownership, human callbacks, a user-equivalent benchmark client, and future extension boundaries. It is ready for detailed specification of TRIAL-1. Main already has a behavioral task/AC allocation. It needs architecture/source reconciliation; versioned wire agreements, concrete realization, measured thresholds and implementation evidence remain native Spec Kit work.

## Which document to read

| Need | Read |
|---|---|
| Product whitelist, blacklist, scientific outputs and acceptance intent | [Latest supplied PRD](sources/product/prd-m1-current-2026-10-06.txt); source identity in [source index](sources/product/README.md) |
| Architecture orientation and responsibility inventory | [Overview](README.md) |
| Same concept under a different name | [PRD translation and naming](glossary.md) |
| First implementable connected slice | [TRIAL-1](immediate-plan.md), [human callback](failure-and-human.md), then [coding entry](handoff.md) |
| Every delivery phase, implementation stage and TRIAL-1 exit | [Phase/stage account](delivery-phases.md) |
| Illustrative handoff meaning and optional native reuse | [Contract shapes](contracts-and-native-reuse.md) |
| Full research stages, inputs, outputs, checks and operational shell | [M1 design](m1-design.md) |
| Planning, freeze, readiness and scheduling | [Workflow](workflow.md) |
| Verifier (Evaluator Gate), capsule authority, admission and composition | [Capsules](capsules.md), [declaration](capsule/declaration.md), [authoring](capsule/authoring.md) |
| Deployment, model/POC isolation, evidence and offline RSI | [Placement](placement.md) |
| Compose automation, ports and external benchmark handoff | [Automation](automation.md) |
| Reasons, recorded PRD amendments and specification boundary | [Principles](principles.md) |

## Actual coverage, not heading-count compliance

The [clause map](coverage-allocation.md) lists all numbered headings in the current PRD §§1–6. A mapped heading only identifies responsibility; it does not prove that all whitelist bullets have been specified or implemented. This review adds the semantic connections absent from the short inventory. The full original clauses remain mandatory inputs to each owning TASK.

| PRD area | Architectural coverage and disposition | What remains to specify or verify |
|---|---|---|
| §§1–2 scope/invariants | Scientific-research lane, supplied baseline/data, one opportunity/claim, pre-registration, gate locks, user-scoped identity with local execution security; [M1](m1-design.md), [principles](principles.md). D1 is aligned to static baseline/dynamic Phase 3; D5/D6 amend named defaults only. | Domain qualification, enforceable profiles and integrated evidence. Future scope is not promoted by metadata. |
| §3.0; §4.3 models | Protected audited baseline bridge; compiler and runtime verifier roles; time/call controls; isolated approved alternative-model evaluation; [placement](placement.md). | Actual installed bridge compatibility, authentication and container IPC support. Missing endpoint blocks only real model execution. |
| §3.1 intake | Document extraction and qualification; separate project/data resource bindings, origin metadata and limits; [M1 ports](m1-design.md#research-path-and-ports). Trial exercises text only. | Asset staging, supported PDF extraction, path isolation and exact bounds. No signing service added; accepted subject identity is needed for gate binding. |
| §3.2; §4.7 requirements | Intent pair, then Brief with scope, priorities, constraints, metrics and marked assumptions; [workflow](workflow.md), [M1](m1-design.md). D5 separates compilation and preserves material uncertainty. | Canonical Brief agreement and Ontario-module adapter. No mandatory interactive approval/clarification loop. |
| §3.3 search | Static strategy, permitted local/academic retrieval, bounded excerpts and 1–3 cited ideas; [M1](m1-design.md). | Connector availability, query/resource limits, citation preservation and grounding checks. No swarm or adaptive crawler. |
| §3.4 screening | One-pass consolidation, scored dimensions and rationales, dependency exclusion, pure ranking, Top-1 and rejected reasons; [M1](m1-design.md). | Fixed tie/invalid-score rules, reusable pure-helper contract, verifier rubric and offline target fixtures. |
| §3.5 hypothesis | Single mechanism, fixed baseline/data/measurement, immutable success/falsification and intermediate outcome rules; [M1](m1-design.md). | Precise protocol agreement and measurement authority; unsupported measurement cannot be invented by Builder. |
| §3.6; §4.9 builder | Bounded code/harness/dependency package, local CodeSearch and mechanical readiness, no scientific run or installation during build; [M1](m1-design.md). | Native adapter, dependency pin realization, archive/path checks and restricted build checks. |
| §3.7 benchmark | Frozen dependencies provisioned in restriction; baseline then treatment, raw logs and comparable measurements; [M1](m1-design.md), [placement](placement.md). | Confinement evidence, reproducible provisioning and hardware availability. Application Docker packaging is not POC isolation evidence. |
| §3.8 science | Empirical-origin/completeness/validity review; fixed criteria; scientific conclusion separated from gate verdict; [M1](m1-design.md). | Per-metric classification, reportable limitations and valid negative/inconclusive end-to-end cases. |
| §3.9 delivery | Standard report plus evidence/artifacts, valid negative results, authorized local transfer and lifecycle closure; [M1](m1-design.md). | Template adaptation, complete references, report verifier and retrieval integration. No external publication. |
| §4.1 capsules | Complete authored inventory, immutable closure, admission/activation/suspension, typed binding; [capsules](capsules.md), [declaration](capsule/declaration.md). | Reconcile machine/prose schema differences and M1 enforcement profile in one versioned owning agreement. |
| §4.2 verifier | One logical Verifier (Evaluator Gate), six facets, deterministic precedence, independent semantic context, protected release and exact subject; [capsules](capsules.md), [M1 checks](m1-design.md#checking-responsibilities). | Challenge set/thresholds and all applicable failure injections. Supplementary verifier template has blank scope fields; master §4.2 wins. |
| §4.4 required RSI | Pure ranking target, bounded proposer/referee/oracle, four data partitions, transitive freeze, inactive lineage, human promotion and rollback; [placement](placement.md), [offline connections](offline-rsi.md), [callbacks](failure-and-human.md). | Native owner adapter, target/scoring interfaces, query caps and security/violation suite. Target 2 only under the PRD's conditional support; no verifier evolution. |
| §4.5 evidence | Capture → structured record → bundle → conformance → scorecard → scoped export; native reasoning memory separate; [M1 data](m1-design.md#data-and-state-ownership), [placement](placement.md). | Portable records/export agreement and capture-before-retention behavior. D6/D9 make release authoritative while optional diagnostics remain best effort. |
| §4.6 harness | Frozen graph, committed readiness, bounded runner, stop new dispatch, no repair/replay, durable attention; [workflow](workflow.md), [callbacks](failure-and-human.md). | Native exception/cache/retry/cancel adapters and crash/persistence evidence. Static baseline and Phase 3 planning share this governed boundary. |
| §4.8 planner | Bounded direct CC graph proposal, deterministic validation, semantic coverage, preconditions and freeze; [workflow](workflow.md). | Search/ranking algorithm, conservative comparisons and concrete graph agreement. Preserve an operational deterministic fallback under D1. |
| §5.1 visibility | Live native transitions, static records/scorecards, observed duration/calls and once-per-run host facts; [M1 shell](m1-design.md#operational-shell). | Event projections and record views; no custom aggregate dashboard or continuous host-resource sampling. |
| §5.2–5.3 installation/interfaces | Automated scaffolding/seeding/doctor, native start/CLI/web/TUI, same application contract; [M1 shell](m1-design.md#operational-shell), [automation](automation.md). | Packaged/native launch parity, provider readiness and terminal modes. No desktop installers or workflow editor. |
| §5.4–5.5 security/channels | Stable account/durable profile plus local token, loopback, protected IPC, restricted POC/fixture access, local privacy and native terminal sessions; [placement](placement.md), [M1](m1-design.md). | Supported OS/container permission enforcement and authenticated triage. No external chat integrations. |
| §5.6 configuration/evaluation | Project precedence, frozen effective profile, declared budgets, isolated ablations and requested/effective seeds; [automation](automation.md). | Versioned profile validation, credential delivery and product-validity marking. No distributed settings or hidden live reconfiguration. |
| §§1.3/6.12/6.14 dynamic integration and completion | [Delivery phases](delivery-phases.md) accounts for all six Phase 3 efforts, reports, entry/fallback/promotion and core-demo distinction. | Concrete owned native work, real endpoint/Code Mode availability and PASS/BLOCKED/INCOMPLETE evidence. Mocks are preparation, not real integration PASS. |
| §6 integration order | Trial first, then connected incremental boundaries; original product-stage dependencies retained, [handoff](handoff.md). Offline interfaces prepared early, execution waits for meaningful stable baseline. | TASKS decomposition/IF allocation, native ACs and block-to-system evidence. Architecture review is not acceptance. |

## Reconciliation rules and resolved gaps

The latest user-supplied PRD wins over compatible owner suggestions and incomplete templates. Preserve received source bytes. [D1–D15](principles.md#decisions-and-source-amendments) are dated amendments/refinements, not a claim that unchanged static PRD behavior is implemented. Their affected clauses must accompany specifications. In particular, the direct planner is now Phase 3 and the earlier dynamic-baseline exception is retired, and Docker/SQLite realization supersedes native-only/best-effort assumptions.

“Evaluator Gate = Verifier” now means one logical boundary with internal deterministic, semantic and authoritative responsibilities. Runtime profiles and offline RSI referee names remain role-qualified. The human callback rules are decided in [one page](failure-and-human.md); automation uses that same policy. Internal topology and control messages are not scientific DAG cycles. Metadata for future capabilities never grants runtime permission.

## SWOT and architectural attacks

| SWOT | Finding | Design response |
|---|---|---|
| Strength | One runner, one logical Verifier and one durable release authority give reusable boundaries. | Trial exercises these before downstream science; client adapters share one workflow use case. |
| Weakness | Shared-provider producer/reviewer errors can correlate; schema/prose requiredness conflicts; installed native behavior is not yet proven. | Preserve verifier characterization/limits; reconcile versioned formats in the owning task; inspect hidden retries/cache/IPC and measure real connections. |
| Opportunity | Ordinary headless client and portable evidence make regression, matched benchmarking and independent offline development simple. | Sequential Compose campaign, immutable profile pins, scoped exports and pure ranking target; no direct state insertion. |
| Threat | Native reply/replay might resume rejected work; mutable artifacts or leaked fixtures could falsify evidence; packaging could be mistaken for confinement. | Correlated triage without resume, subject-bound durable release, protected fixture ownership, enforced restricted execution and no Docker socket. |

Walkthroughs examined an omitted constraint, forged pass text, cross-run artifact substitution, unavailable model, storage failure, lost client response, browser closure/restart, negative science, and failed RSI promotion. The revised boundaries define non-advancing outcomes and their owner; implementation must still demonstrate them. Three focused subagents reviewed new PRD reconciliation, contracts/native reuse, and cross-document consistency. Their findings were reconciled by the primary assistant. This is documentation/source review, not runtime validation or evidence of statistically independent errors.

## Remaining legitimate specification decisions

[Architecture decisions](principles.md#decisions-and-source-amendments) record source reconciliation and intentional amendments. Exact payload serialization, algorithms, prompts, time/resource values, fixture catalogs, measured thresholds, adapter files and deployment commands remain with Spec Kit. They must be fixed before the dependent measurement or implementation, using exact source clauses. Existing main TASK/AC allocation is preserved; no competing M1 identifiers or replacement AC catalog is fabricated. TRIAL-1 can be specified now; real model execution depends on verified bridge/environment support, and a required containment failure blocks POC/RSI execution.
