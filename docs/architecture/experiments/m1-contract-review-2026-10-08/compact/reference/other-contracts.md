# Other major artifact field contracts

**Reading level: AI reference.** These define information and relationships without expanding an exact schema library. [Named fields and types](field-catalog.md) are mandatory shared representation, not independently chosen names. Native interfaces realize one compatible version. [Research detail](../research-design.md) and [inspection](../artifact-inspection.md) explain responsibilities.

## Planning and node contracts

| Artifact / producer → consumer | Needed fields and behavior |
|---|---|
| Qualified intake / protected intake → compilers | Original request and extracted-source identity/text/offset basis; permitted document/resource refs; origin/type/readability/size qualification; rejected/skipped input with reason. Missing required input is explicit rejection |
| Resource snapshot / protected resolver → Hypothesis/Builder/Benchmark | Resource ID/kind, original locator, captured files/content hashes, immutable revision, permitted access, origin/license and availability. Capture required mutable identities before consumption |
| Plan proposal / static template or planner → binder/checking | Brief and library-snapshot refs; mode; node IDs/objectives; requirement/deliverable coverage; exact proposed CC pins; dependencies; named typed inputs/outputs; accepted refs or future `{producer_node,port,type/version}` bindings; budgets; additional checks. No execution or permission grant |
| Frozen graph / protected freeze → scheduler | Accepted proposal/decision; topology; node-contract templates; declaration/implementation/dependency and guard/profile/policy/config pins; limits; future-input rules. Reject cycles, unbound/incompatible ports, missing coverage/checks or denied effects |
| Node Execution Contract / protected binder → runner/gate | Run/node/attempt/revision; objective; accepted obligations; participating per-role CC bindings/pins; concrete input refs and required output contracts; acceptance/evidence obligations; effective per-CC effects/resources and node-wide limits; guard/profile/policy and captured template refs. Final identity is recorded before dispatch; template future values are not observed artifacts |
| Bound check plan / protected guard resolver → checking/review/gate | Exact concrete contract and input refs; each participating CC/dependency pin; profile/policy/config/protocol refs; required criteria/check IDs, tier and mandatory flag; independently owned pinned runners/rubrics; supported evidence/source scope. No self-reference hashing cycle: contracts pin guard/profile; bound check plans reference finalized contracts |

## Research artifacts

| Artifact / producer → consumer | Required information |
|---|---|
| `Candidate_Set.json` / Search & Ideation → Screening | Brief ref, fixed queries, exact source IDs/origins/excerpts/location/hash, citation links, grouped evidence and 1–3 ideas. Each idea has `idea_id`, title, summary, linked citations, core assumptions and identified risks. Missing grounding blocks |
| Screening assessments and ranking / Screening/helper → selection/checking/RSI | Candidate/Brief and frozen work-rubric refs; per-idea novelty/feasibility/compute-alignment scores 1–5 with reasons/evidence; dependency eligibility; rejected/deferred reasons; eligible ordered IDs/totals; equal totals use ascending immutable `idea_id`; missing/duplicate/out-of-range required scores block. Baseline sum/Top-1 retained; RSI does not change incoming dimensions or referee |
| `Opportunity_Card.json` / Screening → Hypothesis | Exactly one selected idea identity, purpose/summary, `opportunity_statement` describing the evidence-grounded bottleneck and mechanism, original scores, ranking refs, citations, scope/constraints, assumptions/risks and dispositions. Selection must resolve to the candidate set |
| `Hypothesis_Blueprint.json` / Hypothesis → Builder/Benchmark/Evaluation | Brief/opportunity refs; claim/mechanism, independent/dependent variables; captured baseline/validation resources; measurement functions/units/aggregation/configuration; repeat/seed policy; success/falsification boundaries and registered middle/conditional classification; constraints, implementation scope and verification plan. Freeze before code/results |
| POC manifest and `POC_Artifact_Bundle.zip` / Builder → Benchmark/checking/Delivery | Blueprint ref; archive/files/hash/media types; bounded `requirements.txt`, `poc_patch.py`, `run_benchmark.py`; declared fully pinned direct/transitive dependencies/environment and protected provisioning policy; mechanical syntax/readiness/forbidden-module evidence. No build-stage dependency installation or empirical scientific trial. Manifest is readable; executable bundle is a separate artifact |
| `Benchmark_Payload.json` / Benchmark → Evaluation/checking/Delivery | Blueprint/package/resource/config/hardware refs; baseline then treatment execution identities and unmodified baseline identity; each required metric's baseline/treatment values and delta; raw repeats/units/seed, empirical-results/stdout/stderr refs; actual provisioning/limits/effects and unmeasured/error reasons. Same frozen protocol; no scientific interpretation |
| `Evaluation_Verdict.json` / Scientific Evaluation → Delivery/checking | Brief/Blueprint/measurement refs; scientific `PASS/FAIL/INCONCLUSIVE/CONDITIONALLY_ACCEPTABLE`; per-metric measurement-to-registered-rule rationale; completeness/plausibility, blockers/residual risks and follow-ups. Conditional acceptance only if registered before results; no post-hoc criteria |
| Report/delivery manifest / Delivery → checking/control plane/user | Original objective, hypothesis, methods, citations, baseline/treatment comparison, scientific outcome/reasoning, limitations/risks, follow-ups and reproducibility. Report file plus lifecycle artifact/evidence refs, exact hashes/audience. Recommendations remain distinct from observations; do not contradict saved scientific verdict |

## Manifest and runtime records

| Record / producer → consumer | Required information |
|---|---|
| Artifact envelope / trusted capture → runner/checks/export | Artifact ID/type/schema version, payload hash and descriptive path/media type, run/node/attempt and producing invocation, original/accepted source refs, audience. Separate content from protected metadata and acceptance |
| Invocation observation / runner → gate/Run Bundle/records | Exact contract and CC/dependency/binding refs; start/end, role/model route, input/output refs, completion/failure/effects/tools, time/calls, available token/cost and explicit unavailable reasons; trace/log refs. Append-only; no fabricated observations |
| Review context / protected builder → verifier | Exact subject/output contract, original/accepted input, assigned criteria/profile/policy/protocol, deterministic results, relevant observations and evidence classified as protected policy, accepted input, observed evidence or untrusted producer content. No producer-selected success narrative or unrelated conversation |
| Accepted-output record / protected durable state → scheduler/client | Exact run/node/attempt, committed gate/contract and output refs, commit identity. Written only after immutable artifact and decision persistence; never infer acceptance from file presence |
| Run Bundle / evidence capture → authorized inspection/export | Run/status/stage, requested/effective configuration/seed, static host facts, artifact/decision/observation inventory, raw logs, missing evidence and redactions. In-progress bundles explicitly mark not-yet-produced artifacts |
| Scorecard/conformance / derived builder → analysis/planner | Exact capsule/version/source observations; sample/window counts, required outcome/failure measures, time/calls/available cost and unavailable reasons. Regeneration does not rewrite gate history; unmeasured quality stays unmeasured |

Manifests map reference IDs/hashes to exact schema/type/version and named content, declare audience and omissions, and use confined relative paths in exports. Hash exact bytes under a pinned profile; changed/redacted content receives a new identity. Readers can inspect substantive JSON/Markdown directly. Raw binary/executable media must never be the only representation of Intent or a verdict.

## Client and model boundaries

Model registry entries carry endpoint/version, declared/verified capabilities, approved role/profile scope, access/health and available usage metadata. A route decision carries invoking CC/role, pinned selection rule, eligible/excluded candidates with reasons, selected endpoint and requested/effective identity. Phase 3 filters eligibility before selecting; Phase 1 has only its static Codex route. No eligible endpoint blocks; the router does not select or replace the CC.


| Boundary / producer → consumer | Required information and behavior |
|---|---|
| Readiness / application → browser/CLI/benchmarker/sidecar | Client-contract version, target instance/build, supported operations, liveness plus storage/auth/model/isolation prerequisite states and failure reasons. Unsupported version, wrong target or required unavailable capability blocks before submission |
| Submission/reconciliation / scoped client ↔ control plane | Client request identity and authorized workspace/user scope; original request/resources; selected approved configuration/profile/mode and requested seed; returned run identity/status/reason. Resolve uncertain delivery before retrying submission; never retry capsule work implicitly |
| Observation/completion / control plane → client | Run identity, current stage/lifecycle/revision, candidate vs accepted refs, last decision/reasons, observed limits, bundle/result refs and completion/halt distinction. Disconnection does not cancel or duplicate work |
| Retrieval/cancellation / scoped client ↔ application | Run/artifact/decision identity, desired authorized audience and returned named files/redactions; cancellation request identity, terminal/acknowledgment status and preserved effects. Inspection read-only; no private DB/volume access |
| Error / application → client | Stable reason/category, human-readable explanation, request/run identity when available, allowed evidence/correction, no credentials/hidden fixtures |
| Model invocation / runner → routing/bridge | Invocation identity, approved role/profile/endpoint requirements, permitted context/tools, input/config pins, effective time/call/resource limits and requested seed. Bridge returns actual response/error, requested/effective model identity and identity basis, duration/calls and supported telemetry/unavailable reasons |

Concrete routes, protocol encodings and internal APIs remain implementation choices, but required information cannot be omitted or changed independently by clients. Pin one implementation agreement/version when realizing these field contracts. Sidecar internals remain separately scoped.

## Offline RSI records

| Record / producer → consumer | Required information / restriction |
|---|---|
| Target profile / protected owner → session/guard/referee | Eligible exact parent/implementation and frozen interface; mutable paths and protected dependency closure; visible tests; distinct development/hidden-loop/hidden-final/platform split identities; fixed scoring adapter/improver/config, improvement measure/minimum meaningful delta/headroom eligibility and calibration evidence; budgets and admitted access |
| Session/proposal/attempt / controller and proposer → guard/referee | Session/ordered attempt identity, parent/child/candidate hashes, diff/rationale, target/policy/config/evaluator pins, visible test observations, actual calls/time, query counts, violations, stop reason; protected ordered attempt-chain sequence/previous-record hash/root and pinned hash profile. Proposal contains only authorized context; protected observations are not proposer evidence |
| Loop feedback / custodian → proposer | Only passed, total and queries-left. Enforce 30/session and 90/loop-set lifetime; no case/expected-answer/hidden-final feedback |
| Protected referee evidence / custodian → restricted admission/evidence | Exact parent/child, split/scoring/configuration and paired repeated results/aggregation; integrity/violations/counters. At least 20 cases per hidden split, 10 known-bad and 3 known-good calibration children; final once/session. Keep secret custody and comparable parent/child settings |
| Allowed export / trusted builder → authorized development/user | Session/attempt/parent/child/config refs; allowed paired aggregate comparison, available observations, limits/violations/stop reasons and redactions. Hidden cases/scoring secrets are not included; final feedback cannot become proposal context |
| Candidate/admission/standing / builder and protected library → eligibility/human | Exact declaration/body/lineage/parent, builder/test evidence; independent allowed-change/contract/test/integrity assessment; admitted/rejected/blocked status and reasons; append-only active/inactive/suspended/revoked history |
| Human activation/rollback / authorized human → future selection | Actor/time, exact admitted from/to versions and reason; security-session clearance additionally pins violation/remediation and validated guardrail evidence; effect is future selection only. Target 1 M1 remains sandbox delivery, not changed live production |

The implementation mutation target and work scoring rubric are distinct from protected verifier/referee assets. Future improver policy changes need held-out improvement-task evaluation; no current record or extension activates recursion, new hidden-suite generation, fusion or live installation.
