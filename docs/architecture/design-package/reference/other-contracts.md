# Other major artifact field contracts

**Reading level: AI reference.** These define information and relationships without expanding an exact schema library. [Named fields and types](field-catalog.md) are mandatory shared representation, not independently chosen names. Native interfaces realize one compatible version. [Research detail](../research-design.md) and [inspection](../artifact-inspection.md) explain responsibilities.

## Planning and node contracts

| Artifact / producer → consumer                                                | Needed fields and behavior                                                                                                                                                                                                                                                                                                                                          |
| ----------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Qualified intake / protected intake → compilers                               | Original request and extracted-source identity/text/offset basis; permitted document/resource refs; origin/type/readability/size qualification; rejected/skipped input with reason. Missing required input is explicit rejection                                                                                                                                    |
| Resource snapshot / protected resolver → Hypothesis/Builder/Benchmark         | Resource ID/kind, original locator, captured files/content hashes, immutable revision, permitted access, origin/license and availability. Capture required mutable identities before consumption                                                                                                                                                                    |
| Plan proposal / static template or planner → binder/checking | Owned by the [Planner page](capsules/planner.md#output-field-contract). Static templates and frozen run plans are on [run plan](run-plan.md). |
| Frozen graph / protected freeze → scheduler | Now the frozen `run_plan`. Owned by [run plan](run-plan.md#run-plan). |
| Node Execution Contract / protected node binder → runner and node gate        | Enclosing objective, external ports, fixed internal work/verifier assignments, dependencies/check profiles, authority ceiling and aggregate limits. [Fields](field-catalog.md#node-execution-contract)                                                                                                                                                              |
| Subnode Execution Contract / protected child binder → CC runner and work gate | One admitted CC, exact implementation/dependency pins, accepted typed inputs, outputs/evidence, narrowed authority and limits, owning node reference. [Critical fields](node-execution.md#concrete-subnode)                                                                                                                                                         |
| Bound check plan / protected guard resolver → checking/review/gate            | Exact concrete contract and input refs; each participating CC/dependency pin; profile/policy/config/protocol refs; required criteria/check IDs, tier and mandatory flag; independently owned pinned runners/rubrics; supported evidence/source scope. No self-reference hashing cycle: contracts pin guard/profile; bound check plans reference finalized contracts |

## Research artifacts

Each research CC page owns the field contracts of its outputs. This table only routes you there.

| Artifact | Producer | Owning page |
|---|---|---|
| `search_scope`, `candidate_set` | Planner (scope), Search | [Search](capsules/search.md) |
| `screening_rubric`, `screening_result`, `opportunity_card` | Verifier owner (rubric), Screening | [Screening](capsules/screening.md) |
| `hypothesis_blueprint` | Hypothesis | [Hypothesis](capsules/hypothesis.md) |
| `poc_manifest`, `poc_artifact_bundle`, `build_receipt` | Builder, host check bundle (receipt) | [Builder](capsules/builder.md) |
| `benchmark_payload`, `execution_receipt`, `provisioning_receipt` | Research Benchmark and protected executor | [Research Benchmark](capsules/research-benchmark.md) |
| `evaluation_verdict` | Scientific Evaluation | [Scientific Evaluation](capsules/scientific-evaluation.md) |
| `delivery_manifest`, `research_report` | Delivery | [Delivery](capsules/delivery.md) |

## Manifest and runtime records

| Record / producer → consumer | Required information |
|---|---|
| Artifact envelope / trusted capture → runner/checks/export | Artifact ID/type/schema version, payload hash and descriptive path/media type, run/node/subnode/attempt and producing invocation, original/accepted source refs, audience. Separate content from protected metadata and acceptance |
| Invocation observation / runner → gate/Run Bundle/records | Exact contract and CC/dependency/binding refs; start/end, role/model route, input/output refs, completion/failure/effects/tools, time/calls, available token/cost and explicit unavailable reasons; trace/log refs. Append-only; no fabricated observations |
| Review manifest / protected host → gate/audit | Host-only audit record: exact subject and output contract, accepted inputs, assigned bundle and profile, deterministic results and observations. It is never sent to the verifier model. `review_context_ref` in the assessment points to it. Fields: [review-context](field-catalog.md#review-context). |
| Accepted-output record / protected durable state → scheduler/client | Exact run/node/subnode/attempt, committed gate/contract and output refs, commit identity. Written only after immutable artifact and decision persistence; never infer acceptance from file presence |
| Run Bundle / evidence capture → authorized inspection/export | Run/status/stage, requested/effective configuration/seed, static host facts, artifact/decision/observation inventory, raw logs, missing evidence and redactions. In-progress bundles explicitly mark not-yet-produced artifacts |
| Scorecard/conformance / derived builder → analysis/planner | Exact capsule/version/source observations; sample/window counts, required outcome/failure measures, time/calls/available cost and unavailable reasons. Regeneration does not rewrite gate history; unmeasured quality stays unmeasured |

Manifests map reference IDs/hashes to exact schema/type/version and named content, declare audience and omissions, and use confined relative paths in exports. Hash exact bytes under a pinned profile; changed/redacted content receives a new identity. Readers can inspect substantive JSON/Markdown directly. Raw binary/executable media must never be the only representation of Intent or a verdict.

The verifier model receives only the pinned declaration and the exact output. See [verifier](capsules/verifier.md).

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
| Activation/rollback / protected library → future selection | M1 activation remains an explicit human record; M2 eligible RSI versions may be admitted automatically and selected by future plans. Preserve actor/time where human action occurs, exact admitted from/to versions and reason; security-session clearance pins violation/remediation and validated guardrail evidence. Effect is future selection only; existing runs keep frozen pins. |

The implementation mutation target and work scoring rubric are distinct from protected verifier/referee assets. Future improver policy changes need held-out improvement-task evaluation; no current record or extension activates recursion, new hidden-suite generation, fusion or live installation.

## Finalized Capsule–routing agreement

The [integration contract](capsule-model-routing.md) owns selected-Capsule export, model-selection profile, RouteRequest, RouteDecision and call provenance fields. The generic client/model descriptions above retain system context. Checking profiles remain independently owned. Trace references in invocation observations and Run Bundle inventories include exact route/call artifacts; they do not embed credentials or replace accepted output/gate records.
