# Component integration rulings

`Tier 2 · Part of: [Side systems](README.md) · Serves: Standard`

This page records the package-owned integration rulings for routing, RSI and derived records. The separately supplied PRD owns requirements. Component behavior and shared contracts in this package govern implementation; changes require a recorded decision.

<a id="routing-v21"></a>

## Routing


The rows below preserve stable ruling identities and state the adopted behavior.

| # | Topic | Ruling |
|---|---|---|
| 1 | Domain and task categories | Adopted. The router accepts only `cs_ml` and the eight `task_category` values in the [route request](../reference/model-routing-contract.md#route-request). Upstream sets the labels. They never select a Capsule. |
| 2 | Candidate inventory | The package [qualification inventory](model-catalog.md#qualification-inventory) is the shortlist. Tools (`T`) never enter the executor set. Entries are neither measured quality nor enabled services. |
| 3 | Qualification states | An entry must pass exact endpoint access, capability, permission and host checks before runtime eligibility; the [catalog](model-catalog.md#qualification-states) owns qualification states. |
| 4 | Calibration privacy | Private per-item calibration, tiers and referee cost tables are referee-only. The router receives frozen development aggregates. The platform blocks referee access by router and workers. |
| 5 | Default policy | Default `development_profile`: hard compatibility filtering, then lowest expected complete cost among qualifying frozen profiles, then supported latency and configured priority/ID. Missing coverage uses a permitted compatible baseline or `PROFILE_COVERAGE_MISSING`; singleton candidates obey the same rule. |
| 6 | Optional LLM selection | `bounded_llm_ablation` is optional and outside the M1 default. At most one pinned routing selection call may choose only from the filtered executor IDs; its configuration is `routing_eligible=false`. |
| 7 | Policy mode | Internal `policy_mode` is `development_profile`, `fixed_baseline` or `bounded_llm_ablation`. The bridge treats `fixed_baseline` as router off (row 15). |
| 8 | One frozen model | One model is frozen per execution. A model-specific failure permits the one authorized router alternate model only before freeze. After freeze, failure follows row 19. |
| 9 | Join key and idempotency | `route_id` joins decisions and calls; `execution_id` is the claim key. Matching duplicates return stored outcome or `ROUTING_IN_PROGRESS`; changed input conflicts. Every call has a [route record](../reference/model-routing-contract.md#route-record). The decision `id` is not the model-group `ModelSelection.route_id`. |
| 10 | No call without audit | Amended. A call without its record does not start. The router keeps its decision and event rows in its own audit store. The bridge writes the route and call records. Boundary: a failure of the router's own audit store is a router halt and gives the Codex fallback (row 14). A failure of the bridge route or call record store stops the call, and the node halts. |
| 11 | Acceptance suite | The package [acceptance scenarios](routing-acceptance.md) preserve A01 to A40. M1 applicability is in [model routing](model-routing.md#owner-acceptance-suite). |
| 12 | Cost and margin targets | Proposed benchmark targets are 20% lower total observed cost, 2-point quality non-inferiority, 5% false-block rate and a 0.45 false-pass bound for model judges. They become release thresholds only when frozen before scoring; they are not platform acceptance or measured results. |
| 13 | Process boundary | Boundary. Changed by [D44](../method/decisions.md#d44) and PRD V.10 §4.3 (the Codex CLI is the mandatory verified baseline; routing integration is not mandatory). The router runs as a separate process behind `RouterPort`. The router implementation is launched as that process in the app container. The hot path imports only `RouterPort`. |
| 14 | Router halts and blocks | Boundary. Every router halt or block returns to the bridge as "no route" with a `router_halt_code`. The bridge uses the Codex route, which is the Codex fallback, and records the reason in the route record. The run does not fail. The exception is an invalid Capsule pin or bound context: the binder should have rejected it, so it is a platform integrity fault and the node halts with a recorded reason (see [router design](router-design.md#replies)). Reply shape: [router design](router-design.md#replies). |
| 15 | Switch and fixed baseline | `cc.router.enabled` is the only platform switch and may be true only under an approved evaluation profile. `fixed_baseline` behaves as off. The fixed comparator keeps its exact configured model and cannot silently substitute. |
| 16 | Verifier calls | Boundary. Verifier calls stay on the Codex route in M1. Per-verifier routing is later work. [RTR-8](model-routing.md#build-criteria) stands. |
| 17 | Dispatch and interfaces | Boundary. Dispatch of the model call stays in the model bridge. The router has no executor. Its only port call is `route`. Call records are written by the bridge. Inspection reads route records. |
| 18 | Spare model name | Boundary. The spare is the **router alternate model**: `alternate_model_id` and `alternate_used`. "Fallback" means only the Codex fallback. |
| 19 | Failure after freeze | A failure of the chosen model after freeze halts the node. Shared-context failure never switches models, and an invalidated frozen binding terminates without fallback or replay. |
| 20 | Calibration and milestones | Boundary. Calibration is router work off the hot path. The accepted Phase 1 route stays on the Codex route and does not wait for calibration. |
| 21 | Serving and credentials | Boundary. The platform provisions an endpoint only for a credential held in the protected env file. No credential value appears in a declaration, record, export or log. Provider entries: [model catalog](model-catalog.md#api-provider-entry). |
| 22 | Deadlines | Ready state is valid for 30 s. `cc.router.deadline_s` is 30, enforced independently by `RouterPort`. These are configured limits, not measured latency; selection-call limits apply only to the optional ablation. |
| 23 | Capsule choice | The router never chooses, generates, combines or substitutes Capsules. The upstream binder names the exact Capsule and supplies its declaration and protected context. |
| 24 | Envelope fields | `domain`, `task_category`, `workflow_stage`, `call_function`, host/profile refs and preferences are route-request envelope fields, not declaration fields. |
| 25 | Roles | There is one Executor type. Protected binding labels and `call_function` provide attribution only. No client-controlled role selects an executor type. |

What stays open for the routing owner is the real provider endpoints, the credentials and the qualification evidence (the package qualification rules). These are in [open items](../method/open-items.md).


<a id="rsi-v02"></a>

## RSI


| # | Topic | Ruling |
|---|---|---|
| 1 | Screening target | PRD 4.4 makes Target 1, the `rank_opportunities` helper, a required M1 commitment. Kept as required. The engine stays generic, and the target lives in its profile. |
| 2 | Qualification rule | Both apply by case. **More passes:** at least 0.05 absolute pass-rate gain, zero protected regressions and a one-sided exact paired binomial test at 0.05. **Equal passes:** time is the tie-breaker (PRD 4.4.2), using the calibrated timing rule in the [workbench](rsi-workbench.md#qualification-rule). Zero protected regressions in both cases. **Fewer passes:** never qualifies. |
| 3 | Comparison baseline | Final comparison is against the original parent; track the incumbent separately. |
| 4 | Session limits | Adopted as the package defaults, in [RSI contracts](../reference/rsi-contracts.md#rsi-session). A session may narrow them and never widen them. |
| 5 | Repeats | Adopted for pass counts. Timing uses 5 warm-up batches and 7 paired rounds. |
| 6 | Baseline query | The baseline evaluation counts as a query. |
| 7 | Hash chain | Kept mandatory. Admission needs verifiable history. |
| 8 | Records | Adopted, in [RSI contracts](../reference/rsi-contracts.md) |
| 9 | Interfaces B, C, D | RSI owns its adapters. The hot path only writes the record export. The workbench runs children with the runner library in its own container. |
| 10 | Lineage | Lineage is mandatory for every RSI child. |
| 11 | Phase | RSI is M1 Delivery Phase 2; validation is reported separately from the Phase 1 core gate. |
| 12 | Owners of A to H | See the [owner table](rsi-workbench.md#interfaces-and-owners) |

### Interface asks


| # | Ask | Ruling |
|---|---|---|
| 1 | Confirm owners and registration identities for agreements A to H, and one-source versioning | Owners are in the [owner table](rsi-workbench.md#interfaces-and-owners). The letters stay review labels. This package registers no new TASK or IF identity. Each record in [RSI contracts](../reference/rsi-contracts.md) carries its own `schema_version`, and a change to a required field or enum raises the major version. |
| 2 | Resolve generic release criteria against the PRD's named target | The PRD wins (row 1 above). Target 1 is required. The engine stays generic. RSI-1 to RSI-6 are the acceptance criteria. |
| 3 | Confirm CapsuleRef, ArtifactRef and correlation conventions. Resolve stale milestone labels in the packaged policy | Use the package `Ref` and `CcPin` types. Correlation keys are `run_id`, `node_id` and `attempt_id` ([D37](../method/decisions.md#d37)). Lineage and budgets are enforced (row 10 above). |
| 4 | Approve capture write order and audience-scoped export, including interrupted executions and required versus optional evidence | Evidence the gate needs is written before the dependent dispatch or state change, and a write failure blocks release. Every other capture is optional and records an explicit gap on failure. An interrupted execution writes a record with outcome `interrupted`. Exports are scoped by audience in the manifest ([D37](../method/decisions.md#d37)). |
| 5 | Confirm the oracle's numeric policy, query unit, lifetime and exposure rules, feedback shape and terminal sealing | 30 queries per session and 90 per loop-set lifetime. One query is one scored hidden-loop evaluation of one candidate, and the baseline counts (row 6). A new profile or packaging hash cannot reset a lifetime count for identical fixtures. Feedback is passed, total and queries left. The final comparison runs once, then the session is sealed. See [workbench](rsi-workbench.md#data-needed-from-day-one). |
| 6 | Review search, resource, repeat, gain and statistical defaults with the evaluation owner | The RSI owner team is the evaluation owner for M1. The defaults are adopted (rows 4 and 5). The gain threshold is 0.05 absolute, as in row 2. |
| 7 | Assign approved adapters and seed fixtures for one development target and one unrelated interoperability target | Development target: Target 1, `rank_opportunities`. Interoperability target: a small pure helper written for the RSI test fixtures by the RSI owner team. It proves the engine does not branch on a CC name. Seed fixtures come from the same team. Held-out transfer targets are benchmark work at M2 and M3. |
| 8 | Confirm the checking assignment for offline sandbox execution (architecture D2) | The workbench runs a child with the parent's mandatory tests and the runner library, in its own container. Hidden scoring and fixture custody stay with the custodian. A hidden case never reaches an ordinary verifier, and a production gate verdict is never an oracle score. |

### Review asks


| # | Ask | Ruling |
|---|---|---|
| 1 | Named-target M1 commitment | Row 1 above. Target 1 stays required. |
| 2 | Consolidated design adoption | The package is the authority ([D38](../method/decisions.md#d38)). This page records the integration rulings. |
| 3 | Existing oracle numeric limits | Retained as package policy: 30 and 90 queries, at least 20 cases per hidden split, 10 planted bad and 3 planted good children. Source: the [workbench](rsi-workbench.md#data-needed-from-day-one). |
| 4 | New search and gain defaults | Adopted as package defaults: 20 attempts, 5 without progress, 60 minutes, 5 minutes per call, 0.05 gain. The values are in [RSI contracts](../reference/rsi-contracts.md#rsi-session). A session may narrow them and never widen them. |
| 5 | Statistical protocol | The independent unit is one hidden fixture. A model-backed fixture is scored from the mean of its 3 repeats, and a regression is a lower mean than the parent. The test is the one-sided exact paired binomial test at 0.05. An unsupported sampling assumption gives `INCONCLUSIVE`. Target 1 is deterministic, so it uses 1 repeat. |
| 6 | Capsule policy artifact | The package enforces lineage, budgets and `evolution.may_change` ([D34](../method/decisions.md#d34)). |
| 7 | Shared storage ownership | The workbench volume holds sessions, attempts, oracle receipts and reviewer evidence. The app volume holds the record export and the admission inbox. Only the export flows from the app to the workbench, and only the candidate package flows back. The fixture store has a separate owner, see [custody](rsi-workbench.md#hidden-fixture-custody). |
| 8 | Offline checking assignment | Interface ask 8 above. |
| 9 | Interface allocation | The [owner table](rsi-workbench.md#interfaces-and-owners). No new IF is registered. |

### Pilot decisions


| # | Decision | Ruling |
|---|---|---|
| 1 | First development and validation targets | Target 1 as in interface ask 7. Parent: the admitted Screening version at the start of the session. |
| 2 | Mutation profile | Target 1: code of the pure helper. Target 2 (Screening prompt and work rubric) is conditional M1 work, available when the headless model path exists, which in M1 is the Codex CLI ([D34](../method/decisions.md#d34)). Referee-owned rubrics stay immutable. |
| 3 | Measurable gain and headroom | 0.05 absolute gain and the headroom calibration in the [qualification rule](rsi-workbench.md#qualification-rule). |
| 4 | Search budget and stopping | The defaults of review ask 4. Transport retries: zero. |
| 5 | Evaluation ownership | The RSI owner team, custodian rules in [custody](rsi-workbench.md#hidden-fixture-custody). |
| 6 | Model and execution configuration | The profile pins the route record and the host profile. Unavailable telemetry is recorded as unavailable. |
| 7 | Generalization coverage | Transfer is unmeasured in M1 and measured by benchmark S08 at M2 and M3. |
| 8 | Product ownership | The RSI owner team runs RSI. The Screening owner owns the parent. The architect holds human activation until a person is named. A module author is never the sole judge of its own improvement. |

**Custodian of the hidden fixtures:** the RSI owner team. Until the team names a person, the architect holds the role ([custody](rsi-workbench.md#hidden-fixture-custody)).

## Data Foundation


| # | Topic | Ruling |
|---|---|---|
| 1 | Scope | Adopted. Raw evidence is kept in per-call folders. The Capsule Run Record and the three derived records are built from it after the run and can be rebuilt. Nothing here changes how a CC, check, verifier or gate behaves. |
| 2 | Hooks never block | Adopted for every hook except one. Evidence the gate needs blocks release when it cannot be written, because the platform commits evidence before a successor is released ([release rule](../reference/derived-records.md#release-rule)). Every other hook, and every derived record, never blocks a run. |
| 3 | Build order | Adopted as the order of the record builders. All of them are built in M1 and sit off the hot path. A run works when they are absent. |
| 4 | Record key | Not adopted. A framework agent id is never a key. A record is keyed by `run_id`, `node_id`, `attempt_id` and `subnode_id`, and the observation `id` is the invocation id. |
| 5 | Stage is fixed or routed | Replaced by `decision_source`, copied from the route record: `router`, `codex_router_disabled` or `codex_router_failed`. It is null when the CC made no model call. There is no `static` value, because the fixed Codex route is already `codex_router_disabled`. |
| 6 | Capsule hash | The package CC is a declaration plus the files in `identity.body`. The record carries `declaration_sha256` and `body_files_sha256`, which is the same sorted path and hash construction over `identity.body`. Together they name the exact version. |
| 7 | Gate gives only a verdict | The gate always produces deterministic check results with check ids. `check_result_refs` points to them. A value that is truly missing is null or empty with a reason, never left out. |
| 8 | Where files live | `records/` on the persistent volume of the app container. The [layout table](../reference/derived-records.md#records-folder-layout) lists every path. |
| 9 | Run Evidence Capture | Adopted. The CC runner writes the call folder. The gate host writes `gate/`, `verifier/` and `human/`. Run-start facts go to `run-start.json`. Run-end copies go to `run-end/` and `workspace.tar`, made before team cleanup and trace retention. No openJiuwen platform change, no in-run assembly of records and no continuous CPU or GPU sampling, under the package capture boundary. |
| 10 | Platform configuration | A requirement on the platform configuration. If a source is off, the related items are `unavailable` with a reason, and a conformance item for it is `unavailable`. |
| 11 | Where and when | `run_id`, `node_id`, `attempt_id`, `subnode_id`, `started_at`, `ended_at`, `duration_s`. A stage is a node. There is no retry reason field: the `attempt` number and the earlier attempt's dispatch outcome give it. |
| 12 | Which capsule | `cc_name`, `cc_version`, `declaration_sha256`, `body_files_sha256`, `decision_source`. Kind and owner are in the declaration and are joined by the triple, not copied. |
| 13 | Which model and why | `model_identity` (requested and effective) and `route_id`. The route record, the model-call records and the router decision hold the candidates, exclusions, reasons and settings. The record does not copy them. |
| 14 | Environment | In `run-start.json` and the run bundle `pins` and `configuration_ref`. Not repeated per record. |
| 15 | State at start | Budget limits are in the subnode contract and spend is in `usage` and `model_calls`. Workspace state is in `run-start.json`. Context already used is not adopted, because the runtime does not expose it. |
| 16 | What it was given | `prompt.txt` and `input_refs` (hash, with size from the file). The origin of each message and retrieved memory items are not adopted. Native memory is never evidence ([data foundation](../platform/README.md#data-foundation)). |
| 17 | What it produced | `output_refs` and the `outputs/` folder. |
| 18 | What it cost | `usage` (input and output tokens, cost), `model_calls`, `duration_s`. Cached tokens are not adopted because the `Usage` type has no such field. The model-call record holds provider detail. |
| 19 | What it did and how it behaved | `trace/tool_calls.jsonl`, `effects` and `workspace.tar`. Repeated calls and tool errors are computed by a reader from the tool-call log. Compaction is not recorded. |
| 20 | How it stopped | `outcome`: `success`, `failed`, `budget_exhausted`, `interrupted`. An iteration limit is `budget_exhausted`. A halt by a person is the node gate or dispatch outcome, not an invocation outcome. |
| 21 | Gate and verifier | `check_result_refs`, `verifier_assessment_ref`, and `gate/evidence.json`, `gate/checks/` and `verifier/output.txt` in the call folder. The verifier's own version and model are in its own invocation record, joined through the assessment. |
| 22 | What went wrong | `failure_reason_code`, `error_fingerprint`, `failure_class`, which also allows `none`. The error text stays in the trace. The class comes from the [failure class rules](../reference/derived-records.md#failure-class-rules), never from a model, and the `scientific` class comes from the evaluation `classification`. |
| 23 | What the human said | `human_answer_ref`, and `human/question.json` and `human/answer.json`. The answer does not set the failure class. It acts only through the gate decision it produces. |
| 24 | Lineage | No field. A reader matches `input_refs` and `output_refs` hashes across records and reads `accepted_refs` of gate decisions. The scorecard reports `next_node_acceptance_rate`. |
| 25 | Who produced each judgement | No separate label. The field says it: a check result is deterministic, a verifier assessment is from a model, a human answer is from a person. |
| 26 | Unavailable values | Adopted. The fields are required, and null or empty with a reason means unavailable. `records.jsonl` is append-only. The record is the invocation observation, completed after the gate decision, so the runner's own file stays unchanged. |
| 27 | Contract Conformance | Adopted as the [contract-conformance](../reference/derived-records.md#contract-conformance) record, one file per execution under `conformance/`. It is a separate file so the Capsule Run Record stays immutable and a rebuild cannot change it. It never blocks a run or changes a declaration. |
| 28 | Run Bundle | The [run bundle](../reference/field-catalog.md#run-bundle) stays the run-level manifest, one per run. The raw per-call folders are `runs/<run_id>/<node_id>/<attempt_id>/<subnode_id>/`, and they are what its refs point to. The package has no rerun tool, no deduplication and no automatic deletion, under the package scope. |
| 29 | Redaction | Credentials are never captured. Other raw text is internal. A sample export lists what it removed in `redactions`. |
| 30 | Capsule Scorecard | Adopted as the [capsule-scorecard](../reference/derived-records.md#capsule-scorecard). The JSON record is the contract. The markdown table is a view of it. Infrastructure and scientific failures are reported and do not lower the pass rate. It grants no release authority, ranks nothing and tests no significance. |
| 31 | Comparison | Not adopted. A comparison on matched inputs belongs to the RSI workbench referee and the platform benchmark runner, which own the matching rules. `make_capsule.md` is not part of the package. |
| 32 | Sample Run Export | Adopted as the [sample-run-export](../reference/derived-records.md#sample-run-export). The label is `development` or `held_out`, fixed by a hash of the execution keys, so it is the same in every export. The export is read-only. It is not the RSI evidence export. |
| 33 | Library Snapshot | Renamed **library analysis** and left as later work ([D21](../method/decisions.md#d21)), because `library_snapshot` already means the Planner's list of eligible CCs. `library_snapshot` keeps that meaning. |
| 34 | Memory and telemetry | Task Memory and Coding Memory never hold run evidence. The native run tree, team budgets and tool-security logs are observation sources. |
| 35 | Needs from other owners | Check ids are pinned in the declaration and bundle. Gate and verifier raw output go to the call folder. `route_id` is the execution id. The CC runner is the shared wrapper. Permission decisions are `unavailable` until the executor logs them in a readable form. |
| 36 | Known limit: stage 3.7.3 | The package keeps them as raw evidence in the call folder and in the execution receipt. The disagreement with PRD 3.7.3 is for the PRD owner to settle. |
| 37 | Known limit: retention | M1 runs only on the server host, so bundles do not leave it except in a sample export. No retention rule exists yet, and nothing is deleted automatically ([open items](../method/open-items.md)). |
