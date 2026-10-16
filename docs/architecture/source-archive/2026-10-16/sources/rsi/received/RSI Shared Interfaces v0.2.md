# RSI M1 Shared Interfaces v0.2

**Version:** v0.2  
**Date:** October 7, 2026  
**Updated:** October 14, 2026  
**Related design:** [RSI M1 design](DESIGN%20-%20RSI%20M1%20v0.2.md)  
**Product requirements:** [AI4Research full-system PRD](PRD%20-%20AI4Research.txt); RSI acceptance criteria are in the [consolidated design](DESIGN%20-%20RSI%20M1%20v0.2.md#rsi-acceptance-criteria)

The workflow and offline RSI should reuse capsule identity, invocation, capture, export, model access, and admission contracts while preserving separate orchestration and protected evaluation. This document specifies eight shared agreements, their payload meaning, ownership, access rules, and failure behavior. They can be realized as local typed interfaces; separate public services are unnecessary for M1.

An approved document version is adopted for design and implementation. Revisions are reviewed by version.

The architect reviews these boundaries, assigns an owner to each agreement, and registers its version under the TASK/IF workflow. Letters A–H below are review labels, not new registered coding identifiers. The record fields are transfer objects outside capsule.json. The authoritative capsule serialization remains the capsule owner's responsibility.

## 1 Common conventions

### Identity and versioning

Each transfer object has `schema_name` and `schema_version`. Schema version 1 is an agreement revision, not a claim that an implementation exists. Unknown major versions and unknown authority-bearing fields fail validation. Any minor-version evolution must have an explicit compatible consumer rule; do not inherit permissive unknown-field handling from native models.

Use non-empty strings for identifiers, lowercase SHA-256 hex strings for content digests, UTC ISO 8601 strings for timestamps, and nonnegative integers for counts and stream revisions. Rates are numbers in `[0, 1]`; elapsed time is measured in seconds. Named bindings are maps from declared port names to artifact references. Reference collections are arrays of the common reference type. Required booleans and numeric observations cannot disappear through a default value. Exact field requiredness, union shapes, and canonical schema files must be ratified once per owning agreement; the tables below define the semantic contract for that ratification.

`CapsuleRef` binds the canonical registry version, declaration hash, implementation manifest hash, dependency closure hash, and immutable contract identity. The implementation manifest lists relative paths, content hashes, and dependency pins using the reconciled capsule format. No version label or single source-file hash alone establishes execution identity.

`ArtifactRef` carries `artifact_id`, `sha256`, `media_type`, and `byte_length`. Resolution is through the protected store/broker and caller authorization; no raw host path or executable locator is supplied by untrusted content. A minimized view has a distinct hash and an explicit source relationship visible only where authorized.

Correlation uses `run_id`, `node_id`, `invocation_id`, `execution_attempt_id`, `rsi_session_id`, `proposal_attempt_id`, and `evaluation_id` as applicable. Fields that do not apply are explicitly null. Producer authority determines which contexts may be absent; callers cannot erase required attribution. Local correlation stays in metadata, not provider prompt text solely for telemetry.

Every required usage field has a measurement status: `observed`, `unavailable`, or `not_applicable`, with units, source, and an unavailable reason. A measured zero is distinct from missing token or cost information. Cost estimates, if separately permitted, are labelled estimates and never silently substituted for endpoint-observed usage.

### Requests and failures

Mutating operations use `request_id`, `request_digest`, and a scoped idempotency identity derived from the authorized caller. Same identity and body reconcile to one action/result. Reuse with a different body returns `IDEMPOTENCY_CONFLICT`. A pending or uncertain result is queried by its original identity before any new dispatch; idempotency does not authorize re-execution.

Replies distinguish `pending`, `completed`, and `rejected`, with an operation-specific result or typed error. This transport status is separate from execution outcome, gate verdict, and RSI qualification. Caller context comes from protected authentication/IPC, not an `actor` field that the caller can self-assert.

Common error categories are `UNSUPPORTED_VERSION`, `INVALID_REQUEST`, `NOT_AUTHORIZED`, `IDENTITY_MISMATCH`, `UNSUPPORTED_ADAPTER`, `PREREQUISITE_BLOCKED`, `BUDGET_EXHAUSTED`, `STORAGE_UNAVAILABLE`, `IDEMPOTENCY_CONFLICT`, and `OPERATION_UNRESOLVED`. Protected errors return safe reasons and restricted audit references without hidden case detail. Each owner defines which failures consume an execution/query budget.

Every agreement needs executable validation, a fixture-based producer/consumer test, and a documented failure/recovery case before integration acceptance. Hashing, canonical serialization, authentication, error enums, and version negotiation are defined once by the platform owner and referenced by consumers.

## 2 Agreement summary

| Agreement | Owner responsibility | Main consumers |
| --- | --- | --- |
| A Capsule snapshot and compatibility | Capsule registry/admission owner | Workflow binder, RSI controller, runner, referee. |
| B Governed invocation and evidence | Runner/Harness owner | Workflow controller; RSI development controller; protected oracle. |
| C Observation capture and records | Data Foundation owner, with event authority retained by producers | Workflow, model bridge, gate host, RSI controller/referee, export builders. |
| D Approved development export | Data Foundation export owner | Offline RSI and authorized benchmark clients. |
| E Target profile and readiness | RSI owner for profile composition; component owners for grants, adapters, and policy | Controller, mutation guard, invocation/evaluation owners. |
| F Independent evaluation | Evaluation/custodian owner | Trusted RSI controller and authorized reviewers; proposer gets only a filtered feedback view. |
| G Candidate admission and activation | Registry/admission owner | RSI result assembler and authorized human operator. |
| H Audited model generation | Model bridge/routing owner | RSI diagnosis/proposer, workflow and verifier callers under their own profiles. |

Owner names denote logical responsibilities. Existing M1 task identities should be reconciled and reused by the coding owner; this document does not create new historical task allocations.

## 3 Agreement A Capsule snapshot and compatibility

**Operations:** `resolve_snapshot`, `check_compatibility`, and `read_eligibility`.

| Payload | Fields and meaning |
| --- | --- |
| Snapshot request | Capsule identity and exact requested version or authorized active-version resolution; purpose and request metadata. |
| Snapshot result | `capsule_ref`; `declaration_ref`; `implementation_manifest_ref`; read-only permitted implementation resources; `contract_ref`; admitted dependency pins; admission/standing record; supported modality/adapter registrations. |
| Compatibility request | Original parent reference, candidate implementation manifest, unchanged contract reference, and approved compatibility profile. |
| Compatibility result | `compatible`, required-check evidence, unsupported obligations, and protected dependency-closure result. This is not final admission or activation. |
| Eligibility result | Current suspension/revocation/standing status and its revision, checked before execution and release. |

Resolve active standing once when freezing the session; thereafter use exact pins. Current suspension can block another invocation but must not silently substitute a different version. Missing dependencies or unsupported obligations block readiness. Trusted packaging, not the proposer, computes candidate identity and permitted lineage/version metadata.

**Acceptance:** Identical exact references resolve the same content; a changed implementation, stale hash, suspended version, or incomplete closure cannot execute as the original parent. A new unrelated capsule uses the same resolution contract.

## 4 Agreement B Governed invocation and evidence

**Operations:** `invoke`, `get_invocation`, and `request_cancel`.

| Payload | Fields and meaning |
| --- | --- |
| Invocation request | Request identity; correlation; execution scope; exact capsule/candidate reference; contract reference; named input artifact bindings; registered adapter; effective environment/model configuration; host-issued effect/resource authority; budget reference; required evidence profile. |
| Invocation result | Exact consumed identities; execution outcome; output artifact references; evidence-manifest reference; observed effects; timing/call usage; missing observations; check/gate references where assigned. |
| Cancellation result | Request recorded, execution state, any already completed work, and retained partial evidence. Cancellation is not an undo guarantee. |

Execution scopes are `WORKFLOW`, `RSI_DEVELOPMENT`, and `RSI_PROTECTED_EVALUATION`. The scope labels do not grant authority: the host validates caller role and admission or sandbox authority. Development candidates are explicitly unadmitted and can execute only under a host-issued offline candidate grant. They cannot be bound into production because their ordinary invocation passed.

Only the protected evaluation owner can invoke hidden cases under the protected scope. Their input/output/evidence references do not appear in development results. The shared runner may receive individual ordinary hidden inputs in an isolated worker; it does not receive the fixture store or scoring logic.

Keep `execution_outcome`, mandatory check results, and gate verdict distinct. The established workflow gate verdict meanings remain unchanged. A successful process exit alone does not pass a mandatory check. Assigned verifier/gate obligations remain applicable to CC work; hidden test scores are supplied separately by Agreement F.

An unavailable required observation blocks compliance acceptance. Execution failure retains partial evidence and budget use. A lost response is reconciled against the original invocation; no automatic replay. Registry or contract changes require a new frozen binding, not an invocation-side fix.

**Acceptance:** Parent and child run with matched settings; rejected effects cannot occur before a later gate; a crash retains an attributable started/incomplete invocation; protected outputs cannot be retrieved through the development caller.

## 5 Agreement C Observation capture and records

**Operations:** `append_observation`, `read_observations`, and `get_capture_status`.

| Field | Meaning |
| --- | --- |
| `event_id`, `producer_event_id` | Stable trusted record identity and producer identity for duplicate reconciliation. |
| `schema_name`, `schema_version`, `payload_schema` | Envelope revision and independently versioned event-payload definition. |
| `stream_id`, `sequence` | Store-assigned ordered position within a run/session capture stream. No fabricated total order across unrelated streams. |
| `event_type` | Registered observation kind: execution started/finished/faulted, tool/model call, check result, committed gate decision, export created, proposal disposition, evaluation receipt, terminal result, or lifecycle action. |
| `occurred_at`, `recorded_at` | UTC source timestamp and capture timestamp; durations use trusted monotonic measurements. |
| `correlation` | Applicable run/node/invocation/execution-attempt/session/proposal-attempt/evaluation identities. |
| `subject_ref`, `configuration_ref` | Exact capsule/candidate/contract and effective settings relevant to the observation. |
| `payload_ref`, `evidence_refs` | Immutable captured content and supporting evidence; permitted audience enforced by the store. |
| `observation_status`, `missing_fields` | Complete, partial, or unavailable observation with reasons. |
| `authority_source`, `audience_policy_ref` | Store-verified writer authority and disclosure policy; never trusted solely from producer-supplied strings. |

The gate host alone emits authoritative gate decisions; the oracle alone emits authoritative evaluation results; the admission host alone emits registry actions. Capsule/model output is untrusted artifact content, even if it contains text resembling an event or verdict. Derived classifications include their producer, classifier version, and evidence; they do not replace original observations.

Capture occurs around each dispatch and at meaningful completion/fault boundaries, not only at successful workflow end. Required evidence acknowledgment precedes dependent dispatch or state advancement. Optional diagnostic capture may fail with an explicit gap. The platform owner defines the SQLite/files write protocol, replay of portable projections, and crash tests; a projection cannot grant release authority.

Reading supports a stable cursor and caller-scoped filters. A cursor is a position, not permission. Consumers detect gaps and cannot infer that missing events establish absence of effects. A duplicate producer event with identical content resolves to the original; conflicting content is rejected and retained for investigation.

**Acceptance:** Interrupted runs retain start and partial/fault evidence; duplicate delivery does not double-count calls; missing required evidence prevents advancement; an untrusted producer cannot inject gate or oracle authority.

## 6 Agreement D Approved development export

**Operations:** `prepare_export`, `get_export`, and `resolve_export_artifact`.

| Payload | Fields and meaning |
| --- | --- |
| Export request | Request identity, authorized source run/session or seeded-fixture references, target capsule versions, bounded selection criteria, requested approved audience policy, and purpose `RSI_DEVELOPMENT` or approved benchmark analysis. |
| Export manifest | Schema revision; export identity/hash; creation time; exporter version; audience approval; exact source/effective-configuration provenance; selected observation identities; permitted artifact references; case records; withheld/missing information; split/overlap review reference. |
| Development case | Stable visible case identity; exact parent version; visible inputs; observed output; independently validated expected behavior where available; failure category; label authority/evidence; reproduction settings; raw-reference and minimized-view relationship where permitted. |

Export creation uses a frozen source selection and produces an immutable manifest. An ordinary consumer cannot request a broader audience by setting a field. Seeded cases carry authorship and validation rather than fake originating run IDs. Export content never contains hidden fixture or final-diagnostic detail.

Allowed failure labels include implementation, upstream input, binding/composition, harness, verifier, environment, and uncertain/multiple attribution. They carry provenance and validation status. A heuristic label or capsule self-report is insufficient to qualify a target without visible reproduction and readiness checks.

The export builder pins dependencies and origin metadata sufficiently for replay, or marks the case non-replayable with a reason. Protected original references may remain withheld while a permitted minimized view is supplied; mandatory checks requiring hidden/redacted fields cannot be claimed passed from that view.

The evaluation owner controls partition registration and contamination decisions. The consumer cannot promote a disclosed case into a hidden suite or erase overlap history. An immutable export cannot acquire new artifacts after a session starts.

**Acceptance:** A failed run exports usable permitted observations; missing labels remain unknown; a forbidden artifact or audience escalation is rejected; hashes and provenance reconstruct the exact frozen development inputs.

## 7 Agreement E Target profile and readiness

**Operations:** `validate_profile` and `prepare_target`.

| Profile field | Meaning |
| --- | --- |
| `profile_id`, `profile_revision`, `profile_hash` | Immutable profile identity and content binding. |
| `parent_ref`, `contract_ref` | Exact admitted baseline and preserved semantic contract. |
| `mutation_grant_ref`, `mutable_component`, `modality` | Host-issued authority, one authorized component, and code or conditional text pathway. |
| `invocation_template_ref`, `adapter_ref`, `environment_ref` | Approved execution mapping and frozen dependencies/settings. |
| `mandatory_checks_ref`, `development_suite_ref`, `development_export_ref` | Independently assigned preservation checks and approved proposer-visible material. |
| `oracle_registration_ref`, `scoring_policy_ref`, `regression_policy_ref` | Opaque protected evaluation registration and frozen policy references; no hidden content. |
| `improver_ref`, `context_recipe_ref`, `search_policy_ref` | Fixed shared engine/proposal policy, bounded context assembly, and stopping/selection rules. |
| `resource_policy_ref`, `model_profile_ref` | Authorized ceilings and audited model route. |
| `final_protocol_ref`, `qualification_policy_ref` | Frozen repeats, independent units, statistical evidence, minimum gain, and terminal reserve. |

Readiness returns `ready`, exact prepared references, required capabilities, and typed blockers. It verifies contract/closure compatibility, admitted adapter identity, parent mandatory behavior, visible headroom, split readiness, actual host/resource feasibility, and supported scoring. Protected baseline queries occur only after the complete session binding is frozen and are charged by Agreement F.

The profile author composes references; it does not approve its own mutation grant, verifier policy, hidden fixtures, or resource authority. A profile can narrow an approved ceiling but cannot widen it. No arbitrary executable callback supplied in a profile is loaded as trusted code.

**Acceptance:** Two unrelated targets validate and execute under the same engine build. A protected dependency overlap, absent authority, saturated target, unsupported modality, or unavailable mandatory oracle blocks search with a clear reason.

## 8 Agreement F Independent evaluation

**Operations:** `evaluate_baseline`, `evaluate_loop`, `get_evaluation`, `seal_terminal`, and `evaluate_terminal`.

| Payload | Fields and meaning |
| --- | --- |
| Baseline/loop request | Scoped request identity; session and frozen manifest references; original parent; optional exact candidate; registered oracle and split-purpose reference; preserved-check evidence; frozen comparison protocol. No case selection or threshold override. |
| Loop feedback | Exactly `passed`, `total`, and `queries_left`. Completed score feedback only; administrative status is separate. |
| Protected receipt | Evaluation identity; request digest; parent/candidate/manifest binding; suite/scoring/environment identities; charged ledger reservation; execution status; restricted evidence references. Controller gets safe accounting metadata; proposer gets only the feedback view. |
| Terminal seal | Custodian-issued handle bound to session, frozen manifest, original parent, one finalist, final protocol, and final suite. Issuance validates session authority and terminal state. |
| Terminal result | Qualification outcome; matched aggregate gain/counts; protected regression summary; frozen evidence-rule result; check/integrity results; usage and limitations; restricted reviewer evidence references. Never fed back into proposal context. |

The oracle owns fixture execution and scoring. It atomically reserves each query before execution against session and loop-set lifetime limits. Query accounting is one complete baseline or comparison request per query, regardless of its frozen repeats, with all underlying invocations charged separately to resource/call budgets. Baseline queries count. The same idempotent request reconciles to one reservation. Failed or uncertain executions retain charges once execution may have begun; a new request cannot refund or repeat them automatically.

The architecture's 30/session and 90/lifetime limits are carried forward for review. The custodian tracks dataset lineage/exposure; identical fixtures cannot acquire a fresh lifetime through a new profile or packaging hash. Query-limit checks and split eligibility remain external to the improver.

Terminal assessment is one transactionally claimed session operation, including the preregistered repeats. A repeated same request can retrieve its status/result; it cannot execute the suite again. A second candidate or changed protocol is rejected. Unknown completion stops search pending reconciliation. A final-result view never becomes a development export for a later run without explicit dataset retirement and disclosure handling.

Hidden worker outputs and diagnostics are captured under protected custody. Errors expose only safe categories to the controller/proposer; an exception cannot embed labels, case identifiers, expected output, or hidden file paths in feedback. Mandatory missing results yield unavailable assessment or a protocol-defined execution failure, not a reduced denominator.

**Acceptance:** Excess queries, baseline bypass, restart reset, altered request replay, early/multiple final access, candidate log leakage, and score tampering are blocked. The referee's actual executions and reported scores reconcile against exact hashes.

## 9 Agreement G Candidate admission and activation

**Operations:** `submit_candidate_for_admission`, `get_admission`, `activate_version`, and `rollback_version` through the existing registry boundary.

| Payload | Fields and meaning |
| --- | --- |
| Candidate package | Original baseline; immediate-parent lineage; exact candidate implementation manifest; preserved contract; permitted diff; generating model/policy provenance; session result and evaluation receipts; compatibility evidence; known limitations. |
| Admission request | Human-authorized request identity, candidate package reference, and approved admission profile. The registry re-resolves and verifies exact hashes. |
| Admission result | Existing gate/admission decision, evidence references, and immutable admitted version if accepted. `active` remains false. |
| Activation request | Separately authenticated human action, exact admitted version, expected current standing revision, and idempotent request identity. |
| Activation/rollback result | Committed future-run standing revision, acting human identity, exact selected version, and historical action reference. |

The RSI service identity cannot activate or roll back a capsule. Admission authority is independently enforced, not inferred from a `qualified` flag. Trusted packaging changes only allowed identity/version/hash/lineage metadata in the reconciled capsule representation; semantic contract changes require a different governed change path.

A modified package, stale assessment hash, missing receipt, revoked dependency, or unsupported check blocks admission. Existing frozen runs retain their original pins; current suspension checks still apply. An uncertain activation response is reconciled before another request. Rollback changes future standing, not historical evidence or external effects.

**Acceptance:** A qualifying child remains inactive; a human can admit, activate, and roll back the exact version; altered packages and RSI-origin activation attempts fail.

## 10 Agreement H Audited model generation

**Operations:** Reuse the platform's model generation and request-reconciliation boundary.

| Payload | Fields and meaning |
| --- | --- |
| Generation request | Request identity; local correlation metadata; approved model/route profile; prompt/context artifact reference; requested response format; authorized call/time limits; disclosure-policy reference. |
| Generation result | Actual route/model/adapter identities; raw bounded response artifact; execution outcome; latency/call count; reliable usage fields with availability status; disclosure/capture evidence reference. |

RSI diagnosis and proposal calls use the same audited bridge as other product model calls. The controller supplies an approved profile; it cannot tune routing, switch models opportunistically, or create an unaudited client. Context is minimized before provider disclosure; hidden fixtures, credentials, control tokens, and unrelated history are excluded.

The initial proposer is one-shot generation with no ambient filesystem/process/evaluation tools. Model output is parsed and validated as an untrusted proposal. A provider failure, timeout, or malformed response consumes its declared attempt/call budget and leaves evidence. Reliable token/cost telemetry is optional, with explicit unavailable values; time and call limits remain enforced independently.

**Acceptance:** Requested and actual routes are recorded; unavailable usage is distinct from zero; private correlation remains local metadata; no hidden evidence can be fetched by a proposal call; uncertain delivery does not trigger another model execution automatically.

## 11 Required architect dispositions

The architect should resolve the following before the shared contracts become implementation authority:

1. Confirm the owners and registration identities for A–H and the one-source versioning strategy.
2. Resolve the generic release criteria in the design version against the full-system PRD named-target commitment; align governing sources and adopt the consolidated RSI design and acceptance criteria.
3. Confirm the common CapsuleRef/ArtifactRef/correlation conventions against the reconciled capsule schema; resolve the packaged policy's stale milestone labels.
4. Approve the capture/write-order and audience-scoped export contract, including interrupted executions and required-versus-optional evidence.
5. Confirm the oracle's existing numeric policy, query accounting unit, lifetime/exposure rules, feedback shape, and terminal sealing.
6. Review the search, resource, repeat, gain, and statistical defaults in the companion design with the independent evaluation owner.
7. Assign approved adapters and seed fixtures for one development target and a second unrelated interoperability target. Held-out transfer targets are a separate benchmark obligation.
8. Confirm the checking assignment for offline sandbox execution under architecture D2, keeping hidden scoring and fixture custody separate from ordinary runtime verification while preserving all applicable mandatory checks.

These agreements define the coupling needed to build the workflow and RSI in separate implementation passes. The offline controller, diagnosis strategy, and patch-search logic remain RSI-owned. The workflow depends on the shared foundations, not on RSI finishing a session.

## 12 References

- [Architecture data ownership](architecture/build-package/m1-design.md) and [placement](architecture/build-package/placement.md).
- [Offline RSI responsibilities and protocol](architecture/build-package/offline-rsi.md).
- [Guard and disclosure design](architecture/build-package/guard-design.md), [capsule lifecycle](architecture/build-package/capsules.md), and [capsule declaration inventory](architecture/build-package/capsule/declaration.md).
- [Benchmark-client export contract](architecture/build-package/automation.md), [illustrative contract shapes](architecture/build-package/contracts-and-native-reuse.md), and [owning interface workflow](architecture/build-package/handoff.md).
- [RSI M1 consolidated design and acceptance criteria](DESIGN%20-%20RSI%20M1%20v0.2.md), [AI4Research full-system PRD](PRD%20-%20AI4Research.txt), and [benchmark requirements](BENCHMARK_REQUIREMENTS.md).
