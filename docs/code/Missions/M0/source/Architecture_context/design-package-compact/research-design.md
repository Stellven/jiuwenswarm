# Full M1: responsibilities and data connections

**Reading level: human potential.** Question answered: What does each M1 research responsibility produce and what makes it complete?

## Research path and ports

The table names semantic ports linked to the [current field contracts](reference/other-contracts.md). Critical Intent/Requirements boundaries have exact schemas; other artifacts have required field meanings and consumer rules. Each work output is a candidate until deterministic checks, its assigned verifier, and the protected gate accept the exact artifact. Downstream nodes receive accepted references through the runner. Original requests, resources, and the Research Brief remain available where the declared responsibility needs them; the pipeline is not a chain of lossy text summaries.

| Responsibility / source | Needed inputs | Output and next consumer | Important bounds |
|---|---|---|---|
| Intake / §3.1 | Original objective, local profile, permitted document paths, supplied project and validation resources | Qualified intake to Intent; separate resource bindings to requirements, Hypothesis, Builder, Benchmark | `.txt`, `.md`, `.pdf` extraction; readability/size qualification and origin metadata. No repository cloning, dataset downloading, or ingestion web search. Identity binding for release is distinct from intake signing. |
| Intent / §3.2.1–4, §4.7, D5 | Original objective and qualified context | Accepted intent to Requirement compiler | Preserve omissions, conflicts, constraints, and scope without choosing a solution. The compiler accepts qualified text and supported local reference documents; supplied project/data assets remain separate resources. |
| Requirements / §3.2, §4.7, D5 | Accepted intent, original context, supplied resource references, fixed policy/defaults | `Research_Brief.json` to Planner and all research responsibilities | Mandatory outcomes vs preferences, scope, constraints, metrics, evidence obligations, explicit authorized assumptions. Material uncertainty blocks readiness; defaults are marked as defaults, never attributed to the user. |
| Static binder / §6.5; Delivery Phase 3 planner / §4.8, D1 | Accepted Brief, eligible library snapshot, resource bindings, policy and limits | Checked candidate graph, then frozen graph to Scheduler | Baseline binds the fixed sequence without autonomous planning; Delivery Phase 3 may propose compatible nodes. Both preserve responsibilities/coverage and Node Execution Contracts; no live restructuring. Future port values stay references. |
| Search and ideation / §3.3 | Brief, local extracted documents, permitted academic connectors | `Candidate_Set.json` to Screening; cited source evidence retained for later consumers | Fixed query strategy; bounded local and designated academic retrieval, grouped exact source excerpts, 1–3 grounded ideas. No open-web crawler, search swarm, or iterative query repair. |
| Screening / §3.4 | Accepted candidates and citations, Brief constraints | `Opportunity_Card.json` to Hypothesis; rejected/deferred reasons and scoring evidence retained | One-pass consolidation; novelty, feasibility, compute alignment on 1–5 scales with reasons; forbidden dependencies filtered. Baseline sum and Top-1 are retained. Tie/missing-score policy is fixed before use. Pure `rank_opportunities` helper is the independent RSI target; candidate improvement does not rewrite incoming dimensions or verifier criteria. |
| Hypothesis / §3.5 | Accepted opportunity, Brief, supplied baseline and validation resource, cited assumptions | `Hypothesis_Blueprint.json` with frozen protocol to Builder, Benchmark and Evaluation | One claim, mechanism, independent/dependent variables, baseline, fixed measurement functions, success/falsification thresholds and middle-region classification. No invented validation data or actual build code. |
| POC builder / §3.6, §4.9 | Accepted blueprint/protocol, Brief, scoped supplied project assets | `POC_Artifact_Bundle.zip` to Benchmark; build evidence to verifier | Bounded `poc_patch.py`, `run_benchmark.py`, declared `requirements.txt`, environment description. Permitted local CodeSearch; mechanical syntax/readiness only. No dependency installation, scientific trial, large refactor, or repair loop during build. Apply §3.6.2 forbidden-module use/import checks before release; [confinement](placement.md#deployment-and-boundaries) is a separate required boundary. |
| Scientific benchmark / §3.7 | Accepted package, frozen protocol, baseline, fixed validation resource and dependencies | `Benchmark_Payload.json`, empirical results, stdout/stderr and execution evidence to Evaluation | Protected provisioning installs only frozen declarations under restricted identity. Baseline first then treatment, same hardware/data/configuration/seed policy. No threshold changes, dependency-set mutation, or interpretation. Missing environment blocks. |
| Scientific evaluation / §3.8 | Accepted measurements and raw logs, frozen Blueprint, Brief | `Evaluation_Verdict.json` to Delivery | Check empirical origin, complete metrics, validity and pre-registered criteria. No new live leaderboard query, experiment rerun, or post-result threshold change. Record conclusions, residual risks and proposed follow-ups. |
| Delivery / §3.9 | Accepted evaluation, Brief, citations, Blueprint, package and benchmark evidence | Standard Markdown report and evidence package to control plane, then user | Preserve claims, methods, measured delta, scientific verdict, warnings, limits and follow-ups. Use the PRD's standard report structure. No publication or knowledge write-back; valid negative findings are delivered. |

## Checking responsibilities

PRD §4.2 groups six evaluation facets; these are profiles/check obligations, not six mandatory services. Tier 1 handles decidable claims; Tier 2 handles the remaining semantic questions using supplied evidence. The protected host aggregates and releases. The [verification boundary](capsules.md#exact-verification-boundary) applies uniformly.

| Facet | Architectural obligation |
|---|---|
| Contract/schema/artifact conformance (§4.2.2) | Validate port meaning, completeness, scope, subject binding and required evidence. |
| Engineering/code quality (§4.2.3) | Check the bounded build and applicable tests/readiness without converting the verifier into a repair agent. Preserve actual test outputs. |
| Performance/cost/benchmark (§4.2.4) | Check comparable protocol execution and declared limits; token/cost absence stays unavailable. Distinguish platform evaluation from scientific measurement. |
| Security/privacy/IP (§4.2.5) | Enforce scoped effects and restricted execution; check secrets, allowed tools/dependencies, licensing and attribution within M1's supported checks. No fabricated comprehensive legal certification. |
| Evidence/factuality/science (§4.2.6) | Check grounding, measured provenance and correct application of registered scientific criteria. Scientific interpretation remains the Evaluation CC's responsibility. |
| Lifecycle/parity/human review (§4.2.7–8) | Verify real execution, complete transitions, unchanged accepted subjects and durable decisions. Route blocking states to triage or headless halt; a human edit creates new attributable work and cannot override a failed mandatory check. |

## Data and state ownership

| Information | Writer / authority | Readers and compatibility obligation |
|---|---|---|
| Product account and durable profile | Account/profile adapter under authenticated user authority | Stable user ID distinct from OS identity, persistent defaults outside run/workspace lifetime; optional cloud-backed store never owns local release state. |
| Node Execution Contract and bindings | Protected binder from accepted requirements, admitted pins and policy | CC runner and Evaluator Gate; node-specific immutable authority, participating invocation IDs and artifact bindings are exported with evidence. |
| Original request and resource registration | Intake under run-state authority | Compilers and authorized work/verifiers; preserve raw content and origin before normalization. Required mutable local assets need a captured snapshot or validated identity before consumption. |
| Effective configuration and graph freeze | Configuration resolver and protected freeze path | Runner, scheduler, model bridge, verifiers and exports; record requested vs effective state. Changes affect future runs. |
| Attempt evidence and artifacts | Runner captures observations; artifact store retains immutable content | Gate, downstream accepted consumers, record builders, user inspection. Failed/pre-gate attempts remain attributable; candidate data is inspectable as unaccepted, never advertised as a released result. |
| Check results, raw assessment, final gate decision | Protected check runner, verifier invocation, protected gate host respectively | Run-state commits release or halt; scheduler consumes committed readiness. Files are persisted before accepted references become visible; orphan files after failed commits grant no readiness. |
| Raw run evidence / Run Bundle | Capture infrastructure | Local inspection and permitted exports; retain prompts, tool calls, build/measurement logs, versions and static host facts once at run start. Redact credentials and maintain fixture custody. |
| Capsule Run Record / conformance / scorecard | Derived record builders after execution | Offline analysis and planners where comparisons are appropriate; include schema version, source identities, missing observations and sample counts. Regeneration never rewrites historical decisions. |
| Export and RSI development data | Export builder under explicit audience policy | Benchmarker or offline proposer gets only its allowed data. Keep protected evaluation data out of exports, prompts and general-purpose volumes. |
| Library version, lineage, admission, activation | Publishing/admission infrastructure; human controls activation | Plans use eligible snapshots; frozen runs pin versions. Suspension is checked at start/release. Rollback changes future selection, preserving old evidence. |

## Commit before successor release

## Operational shell

**Required for full M1 (§5.1–5.6).** Adapt native CLI, web and TUI to the same control plane. CLI submits research, observes transitions and returns human-readable or structured completion; web captures objectives and renders status/report; TUI supplies native inspection and interactive triage. Headless execution never waits on `human_session`. Browser closure leaves the engine running. Restart preserves accepted artifacts, marks interrupted work paused, and does not automatically replay uncertain effects.

## Extension boundaries beyond the first build

| Extension capability | Boundary to preserve now | Current effort or deferred execution |
|---|---|---|
| Advanced compiler | Accepted Brief meaning, attribution, versioned adapter and verification | Expected Delivery Phase 3 attempt, not blanket deferral; later richer modes need explicit supported scope. Retain bounded baseline fallback. |
| Composite CCs and fusion | Typed boundary ports, pinned closure, member evidence/checks, effects and lineage | Later design only; no M1 composite creation/execution, arbitrary capsule member graphs or merging. M1 connects distinct CC subnodes through protected gates inside declared nodes. |
| Better planning / interaction analysis | Objective mapping, typed graph, library snapshot, evidence uncertainty, effect/precondition parity | Logical lowering, MCTS risk analysis, multiple epochs and richer search remain future decisions. |
| Additional model routes | Audited bridge, role/profile identity, actual effective route and capability constraints | Approved heterogeneous routing and alternate verifier are Delivery Phase 3 efforts; later routes reuse the seam. No silent model/context changes. |
| Broader RSI targets | Target allowlist, frozen contract and protected transitive closure, bounded evaluation/feedback, inactive lineage | Fixed improver can later be replaceable through a versioned interface; changing the referee or activation boundary is excluded. |
| Mid-run installation/removal or remote workers | Invocation/attempt identity, dependency closure, scoped resource/effect semantics, durable readiness | Separate lifecycle/lease and compensation design; removal never erases history or claims effects were undone. |
| Larger benchmark campaigns | Ordinary headless client protocol, profile pins, export versions and audience restrictions | Larger datasets, concurrency and alternate suites must respect domain/access gates and resource budgets. |

## Architectural component obligations

These are design-level acceptance obligations, supplementary to the PRD. Native specifications derive executable checks. Each row includes a real connection to exercise, not merely a file-existence condition. The [design method](design-method.md) explains review depth.

| Responsibility / phase | Connection and required result | Architectural check and failure outcome |
|---|---|---|
| Intake and resources / 1 | User/account/workspace → qualified request and separate registered resources → compilers and scientific stages | Required unreadable/unsupported input rejects explicitly; original text and resource scope survive normalization; no hidden cross-run reuse |
| Intent and Requirements / 1; advanced adapter / 3 | Qualified input → usable faithful Intent → accepted Brief → binder/planner | Mechanical failure spends no verifier call; semantic unusability stops Requirements; Brief preserves intent, marked defaults and mandatory obligations; no invented purpose |
| Search and screening / 1 | Brief and allowed sources → grounded candidates → one supported opportunity → Hypothesis | Cite exact evidence; preserve distinct mechanisms, assumptions and risks; scoring/filtering/ranking obey frozen rules; missing scores/evidence or no eligible idea halt before design |
| Hypothesis / 1 | Opportunity/Brief/supplied resources → one immutable claim and protocol → Builder/Benchmark/Evaluation | Verify measurable variables, available baseline/data, measurement definitions and complete pre-registered outcome rules before code; contradictory/unmeasurable protocol blocks |
| Builder and provisioning / 1; Code Mode adapter / 3 | Frozen Blueprint → bounded scripts/package → protected provisioner → restricted Benchmark | Builder cannot edit analytical contracts, install packages or run science. Provisioner validates archive containment and pinned dependency closure; failure halts without repair |
| Benchmark / 1 | Accepted package/protocol → baseline then treatment → matched measurements and raw evidence → Evaluation | Baseline remains unmodified; same resources/configuration/seed policy and required metrics; failed/missing baseline or metric cannot yield invented delta or accepted success |
| Evaluation and Delivery / 1 | Accepted measurements/protocol → justified scientific classification → consistent report/package → user | Apply registered rules, retain negative/inconclusive results, distinguish recommendations; no rerun, new criteria, external publication or contradictory report |
| Binder/planner/freeze / 1, 3 | Brief + eligible catalogue + policy → checked graph/contracts → scheduler | Full obligation coverage, typed dependency closure, no cycles/denied effects; no compatible admitted CC means blocked. Leader self-review is not release authority |
| Runner/scheduler / 1, 3 | Committed readiness + concrete contracts → managed invocations → captured evidence/checking | Per-CC authority intersection, node-wide budgets, subordinate observation; timeout/cancel stops dispatch and contains work. No cache/retry or library switch substitutes for acceptance |
| Checks/verifier/gate / all | Captured exact outputs/context → deterministic results → read-only assessment → protected committed decision | Required malformed, stale, uncertain or inadmissible evidence blocks; verifier cannot modify subjects or release; persistence failure grants no readiness |
| Library/admission / 1, 2, 3 | Declaration + implementation/provenance/tests → provisional admitted pins → binding/RSI | Hand-written and RSI versions satisfy same integrity rules; changed body gets new identity; human standing controls future eligibility, not retrospective history |
| Model registry/routing/bridge / 1, 3; shared by 2 | Runner-bound CC/role/profile → compatible approved endpoint → response and observations | Router selects model, not CC; fixed Codex baseline; denied disclosure or unavailable mandatory capability blocks. No mid-call substitution; absent telemetry stays unavailable |
| State/evidence/exports / all | Captured artifacts/observations + gate decisions → durable readiness, Run Bundles and permitted exports | Files persist before release transaction; reconstruct exact used versions/inputs/results; orphan files do not advance; partial/redacted exports disclose omissions |
| Account/configuration/clients / 1 | Stable account/defaults + local/project config → frozen run; authenticated clients → shared control plane | Product identity differs from OS identity; project overrides defaults without widening policy; readiness distinguishes liveness/model/storage/isolation. Reconcile uncertain submissions before retry |
| Inspection/lifecycle / 1 | Saved candidate/accepted records → CLI/Web/TUI views and authorized retrieval | Read-only inspection never starts execution; disconnection leaves server work intact; restart preserves evidence without replay; scoped deletion differs from account deletion |
| Packaging/security / 1 | Packaged frontend/service/runtime → loopback browser; private clients; scoped local scientific worker | Image starts its services; no host UI script; protected IPC/token/volumes; direct private connection requires authentication; POC cannot read control/credentials/hidden fixtures or use denied network |
| Offline RSI / 2 | Eligible parent/target profile → isolated bounded proposals → protected paired evaluation → inactive child/evidence | Target 1 leaves live ranking unchanged; contract/referee/hidden splits frozen; limits and adversarial cases enforced; authorized admission/activation/rollback demonstrated without automatic promotion |

### Fixed research policies and feasibility

Screening keeps the PRD sum of novelty, feasibility and compute alignment. Equal sums use ascending immutable `idea_id` order. Missing, duplicate or out-of-range required scores block; do not impute a score or let unknown values win. Filter known forbidden dependencies first; if no eligible candidate remains, halt. This tie rule is an architecture standardization choice, not a claim of scientific superiority; the frozen RSI target/referee must preserve it.

### Shared contract clarification

Research artifacts use the named [field contracts](reference/field-catalog.md#research-artifacts) and linked [research example](reference/examples/README.md#linked-research-path). Hypothesis pins the prepared environment before Builder; Builder reproduces its approved complete lock; trusted provisioning installs it without mutation. The [ownership sequence](placement.md#dependency-preparation-and-provisioning) prevents circular dependency discovery.
