# M1 architecture | Design, rationale and review

5 October 2026 | Architecture 952fde474 plus report-review corrections | Frozen PRD: 2 October 2026 | Draft design, not executed system acceptance.

## 01 | Whole system: what and why

- **Goal:** a local question-to-report research workflow with durable evidence. Exact shared contracts let different builders connect modules without inventing product behavior. Internal algorithms remain implementation choices.
- **Deployment:** one Dockerized modular monolith, with protected internal processes where trust requires isolation. This keeps deployment simple while separating credentials, generated code and hidden fixtures. **Pattern:** [Docker restricted containers](https://docs.docker.com/engine/containers/run/); process separation is our local design.
- **Three tracks:** fixed production research; required offline RSI; isolated PRD-whitelisted Phase 2 experiments. Planner experiments never rewrite production. Spec Kit, live replanning, fusion and unrestricted delegation are outside this architecture work.
- **Inventory:** eight research work CCs + one shared verifier + three search operators. Planner, Gate host, store, source extraction, arithmetic and publication are ordinary modules. **Why:** independent governance/reuse needs a capsule; mechanical helpers do not.
- **Contracts:** capability-named capsules compose through exact versioned ports and pinned resources. **Pattern:** [Kubeflow component specifications](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/), borrowed for interfaces rather than its runtime.
- **Authority:** frozen PRD sets scope; owner inputs supply domain detail; architecture chooses shared interfaces. One owner per schema/API/record, with linked generated views. **Pattern:** [Nygard ADRs](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) preserve rationale and supersession.
- **Current state:** proposed modules and concrete contracts are documented. Architecture remains draft; document checks and AI review do not prove a working implementation, platform safety or approval.

Sources: README.md; authority.md; system/modules.md; m1/pipeline.md; policies.md.

## 02 | Connections, control and evidence

- **Entry -> supervisor:** CLI, local Web/TUI and headless HTTP use shared run authority. **Why:** multiple clients must observe one execution state.
- **Supervisor -> runner:** a managed subprocess executes admitted versions through authenticated frames; the supervisor keeps its client. **Runner -> broker -> model bridge:** the protected model adapter mediates Codex turns.
- **Runtime order:** validate inputs -> freeze bindings -> run CC -> store Artifact/Observation -> evaluate Gate -> store Verification -> store release -> dispatch successor. **Pattern:** [Temporal durable execution](https://docs.temporal.io/workflow-execution); our records, not Temporal's runtime, authorize progress.
- **Gate:** the Gate host folds deterministic checks and applicable shared-verifier assessment under pinned stage criteria. **Why:** one policy interface avoids duplicated stage hosts. **Pattern:** [OPA policy/data separation](https://www.openpolicyagent.org/docs).
- **Persistence:** the trusted store commits public records and content-addressed artifacts; required capture feeds Data Foundation views. Atomic/recoverable publication and frozen hashes prevent partial or mutable evidence becoming authority. Durability still needs crash/fsync tests.
- **Failure/recovery:** failed output, Verification or release write blocks the successor. Recovery reuses committed work/decisions; explicit re-execution of failed or interrupted work creates a new attempt. Changed inputs/settings require a new run.
- **Duplicates/quotas:** stable request hashes reuse results or conflict on changed bytes. Committed model reservations enforce bounded calls; uncertain effects are not silently retried. Native engine retry/cache behavior must be constrained by the CC adapter.
- **Reuse:** pinned OpenJiuwen/agent-core workflow, backend, local session, transport and views sit behind replaceable adapters. Source pin 6cc05c36b and agent-core 9e339019 are distinct from this architecture revision; reuse does not imply native security/durability compliance.

Sources: system/integration.md; system/reuse-audit-2026-10-05.md; capsule/toolchain.md; capsule/runner.md; capsule/gate-host.md; system/storage.md; system/lifecycle.md.

## 03 | First CCs: behavior and connections

- **Construction order:** foundation and minimal admitted fixture -> Requirement Compilation -> shared verifier/Gate -> durable continuation -> Search/operators/Screening. This is incremental construction, not execution order. Governed slices need functioning storage, admission, runner and release authority.
- **research.compile_brief (skill):** intake + source_text + optional deterministic intent_ir -> research_brief. Interprets requirements with source grounding. Gate: research.accept_brief.v1. Output connects to Search and downstream stages.
- **research.search_ideas (tool):** research_brief + intake -> idea_set. Collects bounded retained evidence through search operators. Gate: research.accept_ideas.v1. Output connects to Screening.
- **research.select_opportunity (tool):** idea_set + research_brief -> opportunity_card. Prompt-led assessment plus protected deterministic filtering/ranking. Gate: research.accept_card.v1. Output connects to Hypothesis.
- **Screening policy:** one consolidation pass; Novelty, Technical Feasibility and Compute Alignment score 1-5; sum ranks eligible candidates. Frozen dependency conflict/unknown is excluded; canonical source-idea ordering breaks ties. Preserve rejection reasons; no eligible card halts for human review.
- **research.form_hypothesis:** opportunity_card + research_brief + intake -> hypothesis_blueprint. Freezes claims, protocol, resources and predicates before code generation. Gate: research.accept_hypothesis.v1. **Pattern:** [OSF preregistration](https://www.cos.io/initiatives/prereg).
- **Packaging/why:** Declaration, implementation/prompt and checks are pinned by capability version. Exact ports support independent builders. **Pattern:** [Kubeflow typed components](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/). Capsules belong to the admitted library and execute under the runner; the architecture does not claim they are already implemented.

Sources: system/build-order.md; m1/pipeline.md; m1/capability-designs.md; m1/requirement-capsule.md; m1/search-capsule.md; m1/screening.md; m1/hypothesis.md.

## 04 | Remaining CCs and scientific path

- **research.build_poc:** Blueprint + Brief + intake -> poc_bundle. Gate: research.accept_poc.v1. Default: two generation calls, patch then harness, with deterministic packaging/environment checks; no third repair call.
- **research.run_benchmark:** poc_bundle + Blueprint -> benchmark_payload. Gate: research.accept_benchmark.v1. Coordinates frozen baseline/treatment execution; trusted measurement modules, not generated code, own measurement evidence.
- **research.evaluate_results:** benchmark_payload + Blueprint + Brief -> evaluation_verdict. Gate: research.accept_evaluation.v1. Frozen deterministic comparison plus one plausibility turn. **Pattern:** [Python Decimal](https://docs.python.org/3/library/decimal.html) for pinned arithmetic.
- **Scientific outcomes:** PASS, FAIL, INCONCLUSIVE or preregistered CONDITIONALLY_ACCEPTABLE. Valid negative/middle-zone results can proceed to report; missing/corrupt evidence blocks infrastructure acceptance. **Why:** evidence validity and research success answer different questions.
- **research.write_report:** verdict + benchmark + Brief + ideas + opportunity + Blueprint + authorized StageContext -> research_report. Gate: research.accept_report.v1. One synthesis call; ordinary publisher commits the final manifest.
- **research.verifier:** shared semantic evidence/criteria assessment under pinned stage profiles. Gate host owns folding and Verification; the trusted supervisor owns release and dispatch. **Why:** common assessment infrastructure, distinct stage criteria.
- **Search operators:** op.scholarly_search, op.local_search and op.codesearch are independently governed retrieval capabilities serving declared callers. Search uses local/scholarly retrieval; code-location consumers can use CodeSearch. Nested declared retrieval produces retained evidence; bounded permissions mediate external/repository access. DeepSearch/code-search reuse remains behind adapters.
- **Optimization:** permitted prompt/helper changes preserve protected interfaces, ranking, policy and referee. Benchmark materials include EvalPlus, BEIR, CRAG and BIPIA as scoped candidates; assets need receipts/licenses and protected splits. No corpus acquisition or performance improvement is claimed.

Sources: m1/pipeline.md; m1/capability-designs.md; m1/measurement-protocol.md; m1/evaluation.md; m1/delivery.md; m1/benchmarking-material.md.

## 05 | Security, authentication and environment

- **Confinement:** generated-code processes use fixed identities, inner filesystem/PID/network namespaces, bounded syscalls and authenticated brokers. **Patterns:** [Bubblewrap namespaces](https://github.com/containers/bubblewrap/blob/main/README.md) + [Docker seccomp](https://docs.docker.com/engine/security/seccomp/). Their combination remains unvalidated.
- **Access:** admitted code and input snapshots are read-only; assigned attempt root is writable. Credentials, hidden fixtures, store, host home and other attempts are absent from child mounts/descriptors. No Docker socket or external workload network.
- **Lifecycle:** timeout/cancellation kills and reaps the owned namespace process tree before capture seals. **Why:** process-group signaling alone cannot prove that all generated grandchildren stopped.
- **Codex:** separate container login; persistent bridge-owned CODEX_HOME; one serialized owner and exclusive lock. No desktop credential copy or watcher. **Pattern:** [Codex account authentication](https://learn.chatgpt.com/docs/auth/ci-cd-auth) persistent-cache/refresh custody; real binary behavior still needs tests.
- **Replaceability:** ModelProvider/AuthProvider isolate endpoint and login changes. Production starts with Codex; alternative routing is approved/mocked isolated experimentation. Credentials never enter research prompts, configuration snapshots or benchmark export.
- **Environment:** one pinned Linux/Python 3.12 image targets Linux Engine/macOS Docker Desktop. Binary-only hashed offline wheelhouse. **Pattern:** [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/). Repository >=3.11,<3.14 does not establish every wheel/GPU/platform combination.
- **Configuration:** defaults -> user -> project; security ceilings cannot be weakened. Runs pin settings; service changes require explicit idle restart. Doctor exercises the actual profile and fails closed with UNSUPPORTED_SECURITY_PROFILE when required boundaries are unavailable.

Sources: system/deployment.md; system/environment.md; system/model-auth.md; capsule/process-boundary.md; capsule/fixture-oracle.md; open-issues.md.

## 06 | RSI, planner and benchmark interfaces

- **RSI path:** isolated proposal -> private trial/oracle -> paired comparisons -> sealed lineage/ablations -> final holdout -> Candidate -> ordinary admission -> admitted_inactive -> human activation.
- **Mutation/quotas:** freeze interfaces, referee, dependencies and splits. Loop limits: 30/session, 90/immutable-set lifetime; schedule 1 baseline + up to 23 proposals + up to five ablations. Final holdout is separate, once/session. Repeated-session final-aggregate adaptation remains a methodological risk.
- **Admission:** tested evidence or Puppet developer allowlisting; Puppet grants only exempt assurance after integrity checks. It cannot fabricate tests, certify, activate or issue runtime passes. **Pattern:** [MLflow version/alias separation](https://mlflow.org/docs/latest/ml/model-registry/workflow/), adapted to capsule availability/assurance/activation.
- **Planner:** a separate orchestration controller, default GPT-6.1 Sol through Codex. Isolated proposals select admitted versions/bindings. Deterministic validator checks types, closure, cycles, permissions, budgets, Gates and objective coverage; freeze requires committed validation authority.
- **Production distinction:** same plan representation, exact fixed template from committed intake; no model planning prerequisite. No live replanning, unrestricted delegation or autonomous repair. **Why:** stable baseline and replaceable experimental planning boundary.
- **Harness:** authenticated HTTP at host 127.0.0.1:8787 supports runs, status, abort, sealed exports and manifest-scoped downloads. One active run; duplicates reuse handles. A replaceable entry/export adapter connects Saurav's external harness. **Pattern:** [HTTP semantics](https://www.rfc-editor.org/rfc/rfc9110.html) + [OpenAPI](https://spec.openapis.org/oas/v3.1.1.html).
- **Export:** correlated identities, source/library/config pins, model calls, Gates/releases, timing, artifacts, scientific outcomes and failures. Missing telemetry is explicit. Saurav's pending schema changes the export adapter, not the research path. **Pattern:** [OpenTelemetry span/link correlation](https://opentelemetry.io/docs/specs/otel/trace/api/).

Sources: capsule/rsi-engine.md; capsule/fixture-oracle.md; capsule/admission.md; capsule/library.md; system/planner.md; system/experiments.md; system/benchmark-export.md.

## 07 | Adversarial review, evidence and handoff

- **Break cases:** lost Gate save, duplicate/uncertain paid call, credential/fixture read, raw-plan bypass, RSI quota reset, unauthorized export and scientific misclassification. Defenses are durable authority, reservations, private custody, deterministic validation and manifest checks; product fault injections remain unrun.
- **Fresh review corrections:** clarify incremental build order and committed-result recovery; distinguish execution kinds and exempt assurance. Fix stale verification API summaries and source-pin wording. No confirmed targeted owner-contract contradiction remains; this is bounded source review, not exhaustive assurance.
- **Highest residual risks:** exact Docker namespace/credential/process profile on each platform; native retry/cache adapters; fsync/crash recovery; independent semantic fixtures and trusted measurements; Codex refresh/cancellation; repeated-session holdout adaptation.
- **Recorded checks:** prior batches: 464 service checks, 20 source hashes, eight input pairs/18 joins, 131 payload checks, 136 story checks. Review-workflow batch: 1,782 links and 17 packet probes. Earlier diagrams: 50 blocks parsed, 12 selected renders. These are historical documentation evidence, not runtime results.
- **Quality policy:** cheap bounded packets and fresh failure/scope/coder roles; independent seam derivation; escalate shared authority/security disputes. **Patterns:** [Pact consumer/provider verification](https://docs.pact.io/) + [Google small-change reviews](https://google.github.io/eng-practices/review/developer/small-cls.html). No measured token savings or unbreakability claim.
- **Coder handoff:** owners answer placement, API, order/recovery, persistence, security, environment and verification hooks. Start with authority/atlas -> modules -> capability designs -> handoff. Coders produce Spec Kit and actual test evidence; people receive concise decisions/risks.
- **Maintenance:** this report is a dated derived view. Owning pages, decisions and open obligations stay authoritative. An implementation or handoff release must pin current contracts and connected evidence; historical checkpoints cannot certify a later revision.

Sources: authority.md; system/diagram-atlas.md; system/coder-requirements.md; system/handoff.md; open-issues.md; review-workflow.md; reviews/2026-10-05-adversarial-design.md.
