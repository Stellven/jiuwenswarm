---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt, integration.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
provides: [system.environment, system.config, system.secure_ipc, system.isolation_profiles]
consumes: [cc.process_execution_api, cc.fixture_oracle_api]
depends_on: [integration.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
tags: [system, m1, environment, security]
---

# Environment, configuration and security profiles

This page owns effective configuration and internal security contracts; [deployment](deployment.md) owns the Dockerized monolith and host/image contract. It defines the configuration contract for PRD 3.0, 2.9 and 5.2–5.6. Current source evidence is jiuwenswarm `6cc05c36b`: `pyproject.toml:9` permits Python 3.11–3.13, `:20` pins agent-core `9e339019`, `:141` names `jiuwenswarm.start_services:main`; `jiuwenswarm/start_services.py:525` builds child commands and `:687` checks readiness. Existing startup is wrapped, not assumed to provide the new security profile.

## Platform and dependency matrix

| Target | Architecture requirement | Evidence / release condition |
|---|---|---|
| Linux Docker Engine, pinned Linux/Python 3.12 image | complete workflow with nested unprivileged Bubblewrap | implementation must validate exact kernel/image/profile and negative probes |
| macOS Docker Desktop, same Linux image | same public APIs and Linux confinement within Docker VM | implementation must validate volume custody, nested namespaces and selected hardware; native Seatbelt is superseded |
| Windows native | outside PRD CLI targets | no declared M1 release target |

Do not claim every Python/GPU wheel combination works merely because the package version allows it. The image release locks one Python/engine/dependency combination and records them in doctor output; the wheelhouse manifest enumerates compatible wheel filename, hash, version, Python/ABI/platform tags and dependency closure. No unverified platform combination is labelled supported. The offline POC installer uses `pip --no-index --find-links <approved wheelhouse> --require-hashes --only-binary=:all:` on exact requirements, following pip's [secure-install pattern](https://pip.pypa.io/en/stable/topics/secure-installs/). Source distributions, editable installs, remote URLs and build hooks are rejected at the POC gate. If the required environment cannot be assembled offline, halt as an environment problem; missing or undeclared bundle requirements are capsule contract failures.

## Effective configuration

`load_config(project_root) -> ConfigSnapshot` loads packaged defaults, user `~/.jiuwenswarm/config/config.yaml`, then project-local `config.yaml`. Later layers recursively replace scalar/list values and merge mappings; explicit null is rejected for required keys. Project values override user values as PRD 5.6.2 requires. Paths resolve relative to the file defining them, are normalized to absolute paths in the snapshot, and cannot escape configured authorized roots. CLI `--workspace` selects the project; it does not override policy/security limits. Protected invariants (loopback bind, required capture, frozen referee, disabled external messaging) cannot be relaxed by any layer.

`ConfigSnapshot` is `{version: 1, sha256, effective, provenance: map<key_path, source_file>, loaded_at}`. `effective` uses this closed M1 namespace; upstream unrelated keys remain in upstream config and are not accepted as CC extensions. Each subtree below has only its named keys. Missing optional values use the listed default; missing required values are a configuration error.

| Key path | Type / default | Meaning / validation |
|---|---|---|
| `cc.policy_epoch`, `cc.vocabulary_sha256`, `cc.plan_path` | required string, sha256, path | admitted policy/vocabulary and architecture-generated M1 plan |
| `cc.execution.track`, `cc.library.snapshot_sha256` | production; required sha256 | production, offline_rsi or isolated_experiment; freezes admitted library and labels every manifest/export |
| `cc.execution.headless` | boolean / false | no stdin/human_session on halt; same durable verdict/review requirement and exit3 |
| `cc.execution.seed` | closed required `{requested: integer?, effective: integer?, unavailable_reason: string?}` / `{requested:null,effective:null,unavailable_reason:NOT_REQUESTED}` | benchmark/CLI requested nonnegative seed is frozen; effective is populated only for a component that actually supports/applies it. Null effective requires a nonempty unavailable_reason (NOT_REQUESTED when requested is null, NOT_SUPPORTED when requested but unsupported); non-null effective requires evidence of application and null unavailable_reason. Unsupported model seed is null with NOT_SUPPORTED. Component model audit records preserve their own requested/effective values; no deterministic model output is claimed |
| `cc.model.cancel_grace_s` | positive integer / 5 | bounded capture grace before killing only the owned model transport child |
| `cc.model.auth_provider`, `auth_profile_id` | codex_managed_file; application | registered AuthProvider and opaque approved profile identity; fixed dedicated volume custody; no token or caller path in configuration |
| `cc.planner.model_id`, `prompt_sha256`, `proposal_timeout_s`, `max_nodes`, `max_proposals_per_submission` | gpt-6.1-sol; required hash when enabled; 120; 32; 1 | isolated planner only; timeout/node bounds limited by policy; no automatic proposal retry/repair |
| `cc.experiments.feature_profile_sha256`, `external_access_approval_ref` | required hash for isolated_experiment; optional reference for mocks | immutable allowed-feature whitelist; approval reference mandatory before real alternate endpoint use |
| `cc.workspace`, `cc.data_dir` | required path, path | canonical project and local persistent roots |
| `cc.profile.display_name`, `timezone` | string / local user; IANA timezone / UTC | display only; not a principal or authorization rule |
| `cc.model.provider`, `model_id`, `socket_path`, `turn_timeout_s`, `cancel_grace_s` | codex_subscription; gpt-6.1-sol; path; integer / 120; positive integer / 5 | doctor verifies account-supported model; empty/unsupported model fails; production route stays Codex, experiment uses isolated approved/mocked endpoints |
| `cc.budgets.capsule_timeout_s`, `check_timeout_s`, `run_timeout_s`, `max_model_calls` | positive integers bounded by published policy | no project value may exceed the fixed policy ceiling; model-call counter is enforced even with absent token counts |
| `cc.intake.max_file_bytes`, `max_text_bytes`, `extensions` | 50000000; pinned policy ceiling; `[txt,md,pdf]` | reference-document ingestion only |
| `cc.resources.preinstalled` | list of `{name, kind: project_asset|validation_data, path}` / empty | declared local baseline/model/dataset resources; readable at startup, no downloads |
| `cc.hardware.device`, `gpu_memory_gb` | required device identifier; positive number optional | selected local hardware; cannot contradict Brief constraints |
| `cc.security.profile`, `launcher_path`, `oracle_socket`, `oracle_fixture_root` | required profile; absolute paths | immutable approved policy; fixtures outside public Git and child mounts |
| `cc.packages.wheelhouse`, `manifest_sha256` | required path, sha256 for POC execution | local compatible hashed wheel closure |
| `cc.ipc.max_frame_bytes` | positive integer / 1048576 | caps transport envelopes; content travels by authorized refs |
| `cc.web.host`, `port`, `token_ttl_s` | container interface; 5173; 3600 | host publication fixed to 127.0.0.1; bounded token lifetime |
| `cc.benchmark.port`, `max_body_bytes`, `request_timeout_s` | 8787; 1048576; 30 | versioned authenticated API; host publication fixed to 127.0.0.1; body/HTTP deadline bounded by policy independently of research deadline |
| `cc.telemetry.required_capture`, `trajectory_lossless`, `external_reporting` | true; true; false | required paths cannot be disabled; UI/tracer display flags may vary |
| `cc.channels.external_enabled`, `tmux_enabled` | false; true | external listeners remain disabled; native terminal lifecycle |

Parsing/validation failures return `CONFIG_INVALID` with source file and key path, excluding credentials. File watchers validate a prospective next-run snapshot; they do not mutate active runs. `begin_run` durably pins the current snapshot. Explicit resume uses the old snapshot; changes to settings or inputs require a new run. Settings which affect already running local services require an explicit service restart with no active run. Authentication secrets are provisioned into the bridge-owned private credential volume, not config values, snapshots, image layers or exports.

## Model bridge

[Model authentication](model-auth.md) owns profile custody and the replaceable AuthProvider. The release mounts one dedicated writable persistent CODEX_HOME directory owned by the bridge. Separate login and exclusive locking replace per-run credential injection; managed refresh remains Codex-owned. Auth management returns status/device challenges only to local setup, never tokens to research or benchmark callers.

The CC bridge owns a dedicated app-server transport instance and child, separate from native user-chat transport. It serializes CC turns. Cancellation abandons the requester, captures remaining events for cc.model.cancel_grace_s (positive integer, default 5), then kills/reaps only its own CC child if the stream has not completed. A stopped turn cannot be resubmitted automatically. Restart of that transport requires explicit startup/recovery. No credentials or child-control descriptor cross into tools. This is an adapter requirement, not a claim that the existing shared service already has these semantics.

The existing app-server transport uses inherited stdio (`jiuwenswarm/server/runtime/codex_subscription/transport.py:97` at `6cc05c36b`). Retain it inside the trusted bridge. Add a protected UDS between the supervisor/runner and bridge: socket parent mode 0700, socket mode 0600, owner checked before connect, no symlink path, no TCP listener. The supervisor opens a connection before dropping the runner's identity and passes only that connected descriptor with a random scope-bound capability; child tools do not inherit it. Peer credentials plus capability, request id and pinned scope/model context authorize calls. No claim that chmod alone isolates same-UID malicious processes is made; trusted local owner code remains part of the threat boundary.

`ModelBridgeRequest` and `ModelBridgeResult` wire shapes are owned by services-v1 definitions model_bridge_request/model_bridge_result. The scope below replaces the old mandatory research run_id. A turn carries an authorized scoped prompt capture reference; cancel/status carry a distinct management request_id and target_request_id for an existing turn in the same scope, with null prompt reference. Canonical duplicate identities include scope and request_id: identical bytes reuse existing status/result; changed bytes conflict. Results carry the same scope. Complete requires committed reply capture plus its underlying content hash; queued/running/cancelled/unavailable/timed_out/denied never pretend complete. Resolve exact capture membership, record hash and underlying bytes through the scope's owner before returning text. A Ref hash identifies its record; reply_content_sha256 identifies payload bytes, so they are checked against their respective records rather than equated. No timeout resubmits a paid turn. Each audit retains requested/effective seed and unavailable reason; unsupported seed is not reported as applied.

### Model-call reservations and effective bounds

[System records](records.md) owns planning_reserved and model_call_reserved. Intake allocates the real experimental run_id before a proposal; frozen run_started is still written only after validation/freeze. Supervisor commits planning inputs and reservation first, then issues one scope-bound bridge descriptor. A failed reservation write causes zero model turns. Duplicate proposal requests retrieve the reservation/result; interrupted calls are not retried automatically.

Before forwarding any planning or run turn, the trusted broker serializes and commits model_call_reserved, deduplicated by scope/request_id. Count proposal, work, nested and semantic Gate calls against the same run ceiling from effective configuration and policy; a validated proposal may tighten but never raise it. Planning additionally obeys max_proposals_per_submission=1. Failed or uncertain turns consume their reservation; cancellation/status/result retrieval do not. Rebuild counts from committed reservations after a crash; in-memory counters are caches. Missing/corrupt quota authority blocks calls. Broker additionally enforces the exact declaration direct-call limit in the pinned ExecutionProfile, with stage-specific authoring ceilings defined by their capsule owners; no body code can raise it. Runtime checks enforce the elapsed deadline and remaining call allowance even if a model's proposal estimates are wrong. Never claim unreported token telemetry as cost evidence. Private RSI/oracle calls retain their separately owned session/case reservations and never enter this public quota ledger.

### Model-call scope and private capture

services-v1 owns the discriminated ModelCallScope and ScopedCaptureRef shapes. Scope variants are planning (run_id plus planning_request_id), run (run_id), admission (candidate_id plus admission_session_id), rsi_controller (session_id plus attempt_id), and oracle (session_id, oracle_request_id, TrialRef, case_call_id, arm and repeat). No RSI/private call fabricates a research run or a public Candidate. ModelCallContext carries this exact scope along with reserved obs_id/turn; private obs_id names the scope's private call audit rather than a public CC Observation. Native session identity is derived from the canonical scope hash plus request_id/obs_id/turn, creating a fresh thread without exposing fixture labels.

The bridge accepts only a descriptor authenticated by its authorized namespace owner. Planning scope validates the supervisor's committed planning_reserved record, exact task/library/config/policy pins, isolated track, selected model and proposal-call quota before freeze; it cannot use a run descriptor or bypass a Binding check by claiming planning. Run scope validates frozen Binding/dispatch/model pins and public Observation reservation; admission validates a submitted Candidate/admission reservation and normally replays fixtures without a live call; RSI controller validates its fixed target/model/config and attempt reservation; oracle validates its private quota request, Trial pins and case/arm/repeat call reservation. No caller-provided scope alone grants access. The profile capability binds principal, scope, permitted model and capture root; tools/proposer cannot mint oracle descriptors. Routing selector remains run-only; planning/admission/RSI/oracle use fixed pinned models.

ScopedCaptureRef is namespace plus a canonical id/hash Ref: public_artifact for planning/run/admission, rsi_private for controller, oracle_private for fixture calls. The existing public store/envelope remains unchanged. Public capture is committed by supervisor; RSI controller commits its private dev/proposal call evidence; oracle alone commits hidden fixture call captures. The bridge sends raw bytes only to the authenticated scope writer and waits for its committed reference before complete. Required capture failure halts that call; duplicate/recovery checks use the same private/public reservation and cannot reroute capture into another namespace. Oracle capture never enters normal events, report context, proposer replies or benchmark export. Only aggregate results cross oracle custody. Broker retrieval returns bounded text only to the principal authorized for that exact scope; private refs cannot be presented at public artifact endpoints. Credential handling remains separate and bridge-owned.

## Linux confinement inside the monolith

[Deployment](deployment.md) owns fixed bootstrap identities, capability drops, outer Docker seccomp, nested unprivileged Bubblewrap, read-only mounts, network denial and credential/fixture custody. The same Linux profile runs on Linux Engine and macOS Docker Desktop; there is no native macOS runtime profile in this release. Ordinary capsule tools, generated POC and oracle case execution use distinct versioned inner profiles. Direct child network access is denied; permitted scholarly/model operations use authenticated brokers. The oracle expected answers never enter candidate mounts or proposer outputs. Only the fixture case input needed to execute that case is passed to its child.

### Enforcement matrix

Every checked Declaration field maps, per execution backend, to one of four states: `denied` by the process boundary, `mediated` by an authenticated broker, `observed` with evidence but not prevented, or `unsupported` and refused before launch. `needs.network`, credentials, paths, process creation and hidden fixtures must be denied or mediated for untrusted code. An `observed` value cannot satisfy a required safety boundary. The matrix is part of the versioned ExecutionProfile and doctor probes it before enabling that profile.

## Startup and doctor

`doctor(config_snapshot) -> DoctorReport` returns `{config_sha256, platform, python_version, checks: [{id, status: pass|fail|unsupported, evidence_ref?, message}], ready: boolean}`. Checks cover package versions, model/account auth and nonempty model, secure IPC ownership, local paths/fsync, admitted registry closure, plan structure, hardware, wheelhouse, private fixture separation, helper ownership, and actual negative filesystem/network/credential probes under the execution identities. No live run starts unless mandatory checks pass. The report lists unrun checks as unsupported/fail, never pass. [Verification](verification.md) defines the demonstration cases.

## Experimental configuration separation

Each run pins a library snapshot and effective configuration. Production keeps the fixed plan, Codex route and real Gates. Isolated experiment configurations may choose only frozen PRD-whitelisted planner/compiler/routing/Code Mode behavior, using mocks until real endpoint access is approved. PRD 5.6.5 preregistered approved component ablations, including Gate disabling/replacement, are accepted only through a pinned isolated_experiment feature profile/study. Production rejects them. Record actual states, omitted checks and deviations; disabled controls never fabricate a passing Verification, authorize production release, change standing or satisfy product acceptance. Confinement, authentication, mandatory capture and evidence integrity remain required. RSI is a separate explicit offline command, never a production switch. Source inspection and profile/config updates occur once per frozen integration map; reopen only for changed pins or disproved behavior.
