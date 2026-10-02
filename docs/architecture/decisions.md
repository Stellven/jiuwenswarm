---
type: home
status: draft
tags: [decisions, precedents, m1]
depends_on: [PROCESS.md, open-issues.md]
---

# M1 architecture decisions and precedents

This is the disposition ledger for the decisions formerly kept as a flat question list. A row is an architecture decision, not proof that the referenced software proves our implementation correct. The source identifies the design style borrowed; the owning contract and architecture verification establish correctness here.

## Record format

Every new or reversed architecture decision records: context and PRD clauses; disposition and status; primary precedent and borrowed pattern; local rationale and rejected alternatives; owning schema/API; affected producers, consumers, gates, records and diagrams; existing validation; replacement trigger; and migration boundary. Reversals retain the old row as `superseded`. This follows Michael Nygard's [Architecture Decision Record](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) pattern.

Statuses are `adopted`, `provisional`, `product-conflict`, `implementation-validation`, `deferred`, and `superseded`. `adopted` means the architecture has chosen the behavior; it does not claim code or runtime validation.

## Precedent registry

| Key | Primary source | Pattern borrowed | M1 boundary |
|---|---|---|---|
| ADR | [Cognitect: Documenting Architecture Decisions](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions) | small, immutable decisions; supersede rather than erase | documentation only |
| KFP | [Kubeflow Component Specification](https://www.kubeflow.org/docs/components/pipelines/reference/component-spec/) | reusable component identity with explicit typed inputs, outputs and implementation | no Kubernetes dependency |
| SKP | [scikit-learn pipelines](https://scikit-learn.org/stable/modules/compose.html) | compose transforms by passing one output to the next | no estimator dependency |
| CSR | [Confluent schema compatibility and migrations](https://docs.confluent.io/platform/current/schema-registry/fundamentals/data-contracts.html) | versioned schemas and explicit migration for incompatible change | no Schema Registry service |
| MLR | [MLflow Model Registry workflow](https://mlflow.org/docs/latest/ml/model-registry/workflow/) | immutable versions separated from mutable activation aliases and assurance tags | no MLflow dependency |
| OPA | [Open Policy Agent](https://www.openpolicyagent.org/docs) | stable decision interface with policy-selected behavior | policy remains local JSON |
| TMP | [Temporal workflow execution](https://docs.temporal.io/workflow-execution) and [retry policies](https://docs.temporal.io/encyclopedia/retry-policies) | persist progress before release; separate deterministic control from fallible work; bounded retry by operation class | no Temporal dependency |
| PACT | [Pact contract testing](https://docs.pact.io/) | independently verify consumer and provider messages against one contract | architecture canary, not Pact runtime |
| OTEL | [OpenTelemetry Trace API](https://opentelemetry.io/docs/specs/otel/trace/api/) | stable trace identity and links across process boundaries | CC records remain authoritative |
| DEC | [Python decimal arithmetic](https://docs.python.org/3/library/decimal.html) | explicit precision, rounding and traps for reproducible arithmetic | Python `Decimal`, no new package |
| PIP | [pip secure installs](https://pip.pypa.io/en/stable/topics/secure-installs/) | offline, hash-pinned, binary-only dependency installation | local wheelhouse only |
| BWRAP | [Bubblewrap](https://github.com/containers/bubblewrap/blob/main/README.md) | unprivileged Linux namespace and mount isolation | Linux generated-code child only |

## Dispositions: D1-D16

| ID | Status | Decision and owner | Precedent | Recheck and replacement trigger |
|---|---|---|---|---|
| D1 | adopted | Every wired boundary uses one named payload type; `json` is private to one capsule. Owner: types vocabulary. | KFP, PACT | Recheck binder, all producers/consumers and canaries. Replace only with a type-safe structural compatibility algorithm. |
| D2 | adopted | Field tables are canonical and generate JSON Schema. Owner: vocabulary builder. | CSR | Recheck generated schemas/examples. Replace if another single source can prove no drift. |
| D3 | adopted | Core payloads are closed and expose only optional `ext`. Owner: type rules. | CSR | New core meaning creates a new type version and adapter. |
| D4 | superseded | `intake` remains the qualified package, but capability inputs use smaller projections such as `source_text` and `resource_snapshot`. | KFP, SKP | Recheck Intent and Requirement. Remove a projection only when no independent consumer remains. |
| D5 | adopted | `research.compile_intent` is a capability-named pre-requirement step. | KFP | Recheck the static plan and PRD map. Phase 2 may bind it elsewhere without renaming it. |
| D6 | adopted | `research_brief` retains cited evidence and explicit metric comparator/unit/basis fields. | KFP, DEC | New scientific meaning requires a new payload version. |
| D7 | adopted | Checks use one call/result ABI. Owner: check runner. | PACT | Recheck every check provider/consumer. Replace only through an ABI version and adapter. |
| D8 | superseded | `evidence_bundle`/`verifier_assessment` remain the Tier 2 seam; durable `Verification.gate_result` is the only advancement authority. | TMP | Recheck Gate host, storage and supervisor. |
| D9 | adopted | Model Routing chooses endpoint/model inside a capsule call and records `route_id`; it does not choose capsules. | KFP, OTEL | Recheck router seam and observations. Phase 2 picker changes do not alter this interface. |
| D10 | adopted | Data Foundation run records are views over CC authority plus owned raw capture. | TMP, OTEL | Recheck record projection whenever CC records change. |
| D11 | adopted | `cc/` and `capsules/<capability-name>/` are proposed code locations; package/file names do not define capsule identity. | KFP | Code SOP may relocate modules through an adapter-preserving change. |
| D12 | adopted | A frozen `run_plan` is the only step/wiring definition. | KFP, TMP | Recheck freeze, supervisor and graph after any plan-field change. |
| D13 | adopted | Policy owns registries and bounded runner settings; named profiles own admission, Gate, retry and execution selection. | OPA | New profile version, never call-site branching. |
| D14 | adopted | `obs_id` is the one join key for everything inside a capsule call. Every other id is stored where observability says and joins through `obs_id`. Two authorities (records, sealed capture) both carry it; events, spans and exports are derived views. Owner: [observability](system/observability.md). | OTEL, TMP | Recheck the runner, bridge, tracer, Data Foundation projection and the model-routing seam. Replace if a feed needs a second key. |
| D15 | adopted | The model endpoint receives the prompt only. The runner's context (stage, role, capsule) stays on the trusted side of the bridge, and attribution is a reader-side join on `obs_id`. Owner: [observability](system/observability.md). | OTEL | Recheck the bridge request and the router gateway mode. Replace only with a separate decision and threat note. |
| D16 | adopted | Build in thin slices: one capsule, then one connected capsule with its wire tested, then expand. The runner and its records grow with the capsules; the event bus comes after the first gate. Owner: [capsule inventory proposal](m1/capsule-inventory-proposal.md). | PACT, TMP | Recheck the PRD stage order and every build-step check. |

## Dispositions: issues 1-58

| ID | Status | Decision | Precedent / replacement trigger |
|---|---|---|---|
| 1 | provisional | Do not promise general determinism. A capsule may declare it only when admission can repeat fixed fixtures and compare canonical outputs. | PACT; replace after a measured determinism protocol exists. |
| 2 | adopted | Candidate.files covers every carrier, body, check, rubric and private value-schema file. | CSR; change rechecks admission and freeze. |
| 3 | adopted | Architecture owns type-check semantics; a reviewer other than the payload producer owns/checks executable check code. | PACT; replace via reviewed check-library ownership policy. |
| 4 | adopted | A released type version is immutable. Any core-field change creates a new version and explicit adapter; `ext` is the same-version extension point. | CSR. |
| 5 | adopted | Failure modes are optional and economical: add only non-derivable, enforceable hazards; each listed mode creates a verification obligation. | PACT; no additive-only promise. |
| 6 | adopted | Puppet admission permits developer-selected exact declaration hashes as `exempt`; integrity and runtime Gates remain mandatory. | MLR, OPA. |
| 7 | adopted | The generic supervisor walks `run_plan`; no parallel script definition exists. | KFP, TMP. |
| 8 | adopted | Names express capabilities; stage mapping belongs to `run_plan`. | KFP. |
| 9 | provisional | Evidence quotes must be nonblank, source-exact spans; no arbitrary character threshold. | PACT; replace if evaluation evidence supports a domain threshold. |
| 10 | adopted | Every metric pins basis (`absolute`, `delta`, `relative_percent`, `percentage_points`), unit, direction, statistic and comparator. | DEC. |
| 11 | adopted | Hardware becomes a frozen resource/profile reference plus captured device facts, not a free control string. | KFP; extend registry for new devices. |
| 12 | adopted | Contradictory user constraints remain explicit conflicts in IntentIR/Brief and halt at the requirement Gate for human resolution. | TMP. |
| 13 | adopted | Framework constraints are part of Brief constraints because POC consumes them; origin remains traceable to PRD 3.6.1. | KFP. |
| 14 | adopted | Intake carries project and validation resource bindings. | KFP. |
| 15 | adopted | Content hashes identify stored bytes; they are neither signatures nor product claims of intake authenticity. | CSR. |
| 16 | adopted | Data Foundation retains raw logs; memory carries referenced summaries. | OTEL. |
| 17 | superseded | Capsule selection and model routing are separate decisions as stated in D9. | KFP. |
| 18 | adopted | Full PRD 4.2 is the Verifier source; Gate host is the adapter boundary. | PACT. |
| 19 | implementation-validation | CC emits its own spans/records when no team worker exists; first runtime verifies native view compatibility. | OTEL; replace adapter if native spans become available. |
| 20 | provisional | Raw bundles are local-owner read-only, excluded from UI by default, and retained until explicit project deletion; no automatic M1 deletion. | OTEL; replace when product supplies retention policy. |
| 21 | provisional | Each runtime Gate is a non-RSI referee capsule with a pinned rubric; Puppet Gate does not replace it. | OPA, PACT. |
| 22 | implementation-validation | Intent compiler code adjustments remain a downstream coding task against the revised `source_text` port. | KFP. |
| 23 | adopted | Hypothesis through Report payload schemas are canonical v2 contracts. | CSR. |
| 24 | deferred | Planned mid-run segment freeze is Phase 2; M1 freezes one static plan before launch. | TMP. |
| 25 | implementation-validation | Reuse native run-view shapes behind an adapter; prove non-team rendering in the first integrated run. | OTEL. |
| 26 | implementation-validation | Trace `chat.send` through the local entry adapter during integration; the entry adapter owns the hop. | OTEL. |
| 27 | adopted | Every governed step names a Gate profile/capsule; the existing Binding verifier slot is the gate binding. | OPA. |
| 28 | adopted | The protected CC model bridge satisfies M1 pipeline subscription routing; interception of unrelated OpenJiuwen traffic is outside M1. | KFP. |
| 29 | adopted | Step-check runners are immutable files of the admitted Gate capsule and are frozen with it. | CSR. |
| 30 | adopted | Intent and Brief Gate capsules are designed under the common Gate profile. | OPA. |
| 31 | deferred | Admission-judge configuration remains available for later judged admission checks but has no M1 caller. | OPA. |
| 32 | adopted | The CC runner executes capsules; generated POC code executes only through a separate restricted boundary. | BWRAP. |
| 33 | adopted | `op.codesearch` preserves the verified DeepSearch BM25-facing contract but does not add DeepSearch's conflicting dependency tree to M1. | KFP; replace internals without changing sorted output contract. |
| 34 | adopted | `EXTERNAL_UNAVAILABLE` is runtime-owned, maps to environment blocked, and supports explicit resume. | TMP. |
| 35 | adopted | Admission replays model and external replies from test fixtures; it performs no live external calls. | PACT. |
| 36 | adopted | All stages use one Gate API. Profiles contain every applicable deterministic and semantic criterion; a mechanical profile legitimately has zero semantic criteria. | OPA. |
| 37 | adopted | `blackbox` is reserved for a genuine external product conflict or unvalidated safety mechanism. Sourced replaceable defaults are `draft`. | ADR. |
| 38 | adopted | A capsule may call a pinned router capsule; route decisions join observations by `route_id`. | KFP, OTEL. |
| 39 | adopted | Freeze verifies the complete dependency, check, rubric and profile closure and publishes Bindings atomically. | CSR, TMP. |
| 40 | provisional | Linux uses separate supervisor, generated-code and oracle identities plus Bubblewrap/namespaces. Oracle fixtures are unreadable to runners. | BWRAP; replace only after equivalent isolation tests pass. |
| 41 | adopted | Brief target, claim expectation and falsification boundary remain distinct and pre-registered. | DEC. |
| 42 | adopted | Stage capsules run in CC; only generated experiment code crosses the POC execution boundary. | BWRAP. |
| 43 | adopted | Dependencies install offline from hash-pinned binary wheels; build hooks and network indexes are unavailable. | PIP. |
| 44 | adopted | Deterministic classification is `PASS`, `FAIL`, `INCONCLUSIVE` or `ERROR`; valid scientific FAIL/INCONCLUSIVE may pass the infrastructure Gate. | DEC. |
| 45 | adopted | Intake v2 includes reference, project and validation resources; readiness belongs to later Gates. | KFP. |
| 46 | adopted | Durable Verification is the single Gate decision record; release is written only after it. | TMP. |
| 47 | adopted | Native human session performs triage; explicit resume preserves pins and creates a new attempt. | TMP. |
| 48 | adopted | Numeric Screening dimensions are exactly Novelty, Technical Feasibility and Compute Alignment. Evidence maturity and verification path are required qualitative context. Novelty compares against Brief evidence and cited Idea evidence. | KFP. |
| 49 | provisional | A frozen dependency registry uses canonical kind/identifier entries with availability and license facts; CC policy owner publishes it. | OPA; replace provider without changing assessment type. |
| 50 | adopted | `research.select_opportunity` is a prompt-led skill; RSI may alter only its prompt/rubric candidate. Deterministic ranking and policy remain non-RSI dependencies. | KFP, MLR. |
| 51 | adopted | Only dependency conflicts affect M1 eligibility. Value, timing, safety, legal and resource observations remain card context; verified dependency/resource context flows to Hypothesis. | OPA. |
| 52 | adopted | Ties resolve by ascending lexicographic sorted source `idea_ids` tuple. | DEC; replace only with a new ranking-policy version. |
| 53 | adopted | No eligible candidate produces `NO_ELIGIBLE_OPPORTUNITY`, no card, no Gate call, and human triage. | TMP. |
| 54 | adopted | Field enforcement is mapped per backend as `denied`, `mediated`, `observed`, or `unsupported`; unsupported requirements fail closed. | BWRAP, OPA. |
| 55 | provisional | Oracle query budget 30: baseline 1, proposals at most 23, accepted-lineage ablations at most 5, final holdout 1. Six queries are unavailable to proposal generation; unused reservations stay unused. | OPA; policy version may change allocation without API change. |
| 56 | adopted | RSI uses durable sessions/attempts, submits a Candidate, admits independently, and requires manual activation. | MLR. |
| 57 | product-conflict | Linux is the reference generated-code profile. macOS control plane may run, but generated-code execution returns `UNSUPPORTED_SECURITY_PROFILE` until equivalent isolation is validated. | BWRAP; full macOS claim requires a validated replacement profile. |
| 58 | provisional | A measurement method is selectable only when a trusted adapter, workload coverage and validation fixture are registered. Missing coverage blocks that experiment. | KFP; registry additions do not change the protocol. |

## Change propagation

Changing an adopted or provisional row reopens its owning type/API and every producer, consumer, Gate profile, run-plan binding, persistent record, seam, coverage row and graph edge that relies on it. The change record names that set before edits begin. Contract changes use a new schema/API/profile version or an explicit adapter; callers do not branch on historical exceptions.
