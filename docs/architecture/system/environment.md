---
id: system.environment
type: module-spec
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt, integration.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
provides: [system.environment, system.config, system.secure_ipc, system.isolation_profiles]
consumes: [cc.process_execution_api, cc.fixture_oracle_api]
depends_on: [integration.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
tags: [system, m1, environment, security]
level: detail
prd: [3.0, 2.9, 5.6.1, 5.6.5]
---

# Environment, configuration and security profiles

PRD: 3.0, 2.9, 5.6.1, 5.6.5

> Answers: What configuration, platform and security profiles does a run need?

## Purpose

This page is the home of effective configuration and internal security contracts; [deployment](deployment.md) is the home of the Dockerized monolith and host/image contract. It defines the configuration contract for PRD 3.0, 2.9 and 5.2–5.6. Current source evidence is jiuwenswarm `6cc05c36b`: `pyproject.toml:9` permits Python 3.11–3.13, `:20` pins agent-core `9e339019`, `:141` names `jiuwenswarm.start_services:main`; `jiuwenswarm/start_services.py:525` builds child commands and `:687` [checks](../capsule/fields.md#term-check) readiness. Existing startup is wrapped, not assumed to provide the new security profile. Line references to agent-core and jiuwenswarm in the design pages were read at a local head; re-check them at the pin before coding against them.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-doctor"></a>**Doctor** | The check run before every run that reports the platform, dependencies and security profile as a `DoctorReport`. It starts with the native diagnostics, adds our negative probes, repairs nothing and blocks the run on a mandatory failure. |
| <a id="term-probe"></a>**Probe** (also: negative probe, probes) | A doctor test that tries something a confined child must not be able to do, such as reading credentials, the store or fixtures. A probe that is not run is never a pass. |
| <a id="term-configsnapshot"></a>**ConfigSnapshot** | The effective configuration after layering packaged defaults, user config and project config, with its provenance and sha256. It is pinned for a run. |

## Platform and dependency matrix

| Target | Architecture requirement | Evidence / release condition |
|---|---|---|
| Linux Docker Engine, pinned Linux/Python 3.12 image | complete workflow with nested unprivileged Bubblewrap | implementation must validate exact kernel/image/profile and negative probes |
| macOS Docker Desktop, same Linux image | same public APIs and Linux confinement within Docker VM | implementation must validate volume custody, nested namespaces and selected hardware; native Seatbelt is superseded |
| Windows native | outside PRD CLI targets | no declared M1 release target |

Do not claim every Python/GPU wheel combination works merely because the package version allows it. The image release locks one Python/engine/dependency combination and records them in doctor output; the wheelhouse manifest enumerates compatible wheel filename, hash, version, Python/ABI/platform tags and dependency closure. No unverified platform combination is labelled supported. The offline POC installer uses `pip --no-index --find-links <approved wheelhouse> --require-hashes --only-binary=:all:` on exact requirements, following pip's [secure-install pattern](https://pip.pypa.io/en/stable/topics/secure-installs/). Source distributions, editable installs, remote URLs and build hooks are rejected at the POC gate. If the required environment cannot be assembled offline, halt as an environment problem; missing or undeclared bundle requirements are [capsule](../capsule/capsule.md#term-capability-capsule) contract failures.

Schema: the wheelhouse manifest is `tools-v1.schema.json#wheelhouse_manifest`.

## Interface: effective configuration

Messages of this module. The key table and the doctor report follow.

- **Who a model call belongs to** (call, supervisor -> [bridge](model-bridge.md#term-model-bridge)). Schema: [`services-v1.schema.json#model_call_scope`](../contracts/services-v1.schema.json).
- **Capture kept by the oracle or [RSI](../rsi.md#term-rsi) controller** (record, bridge). Schema: [`services-v1.schema.json#private_model_capture`](../contracts/services-v1.schema.json).
- **One model [turn](model-bridge.md#term-model-turn) request** (call, [CC runner](../capsule/runner.md#term-runner) -> bridge; the planner only in the isolated experiment track). Schema: [`services-v1.schema.json#model_bridge_request`](../contracts/services-v1.schema.json).
- **The model turn result** (call, bridge -> runner or planner). Schema: [`services-v1.schema.json#model_bridge_result`](../contracts/services-v1.schema.json).
- **DoctorReport: probes, ready flag, probed profile** (report, doctor -> launcher, supervisor, CLI). Schema: [`tools-v1.schema.json#doctor_report`](../contracts/tools-v1.schema.json).
- **Named [execution profile](../schemas/profiles.md#term-executionprofile) of a [kind](../capsule/capsule.md#term-capsule-kind) (restricted_child, poc, oracle, bridge)** (profile, policy publisher -> store; launcher, doctor, runner). Schema: [`tools-v1.schema.json#execution_profile`](../contracts/tools-v1.schema.json).
- **Approved offline wheel closure for POC execution** (record, installer -> doctor, process service). Schema: [`tools-v1.schema.json#wheelhouse_manifest`](../contracts/tools-v1.schema.json).
- **ConfigSnapshot: effective config, provenance, hash** (record, config loader -> launcher, doctor, store). Schema: [`tools-v1.schema.json#config_snapshot`](../contracts/tools-v1.schema.json).

Native jiuwenswarm configuration is one user-level `config.yaml` with environment-variable substitution: no project layer, no provenance, no hash, no freeze, and `CONFIG_YAML_PATH` is bound at import. So CC keeps its own `load_config` and no CC module calls the native `get_config()` ([reuse](../reuse.md)).

`load_config(project_root) -> ConfigSnapshot` loads packaged defaults, user `~/.jiuwenswarm/config/config.yaml`, then project-local `config.yaml`. Later layers recursively replace scalar/list values and merge mappings; explicit null is rejected for required keys. Project values override user values as PRD 5.6.2 requires. Paths resolve relative to the file defining them, are normalized to absolute paths in the [snapshot](../capsule/library.md#term-library-snapshot), and cannot escape configured authorized roots. CLI `--workspace` selects the project; it does not override policy/security limits. Protected invariants (loopback bind, required capture, [frozen](lifecycle.md#term-freeze) referee, disabled external messaging) cannot be relaxed by any layer.

Schema: `tools-v1.schema.json#config_snapshot`. `ConfigSnapshot` is `{version: 1, sha256, effective, provenance: map<key_path, source_file>, loaded_at}`. `effective` uses this closed M1 namespace; upstream unrelated keys remain in upstream config and are not accepted as CC extensions. Each subtree below has only its named keys. Missing optional values use the listed default; missing required values are a configuration error.

| Key path | Type / default | Meaning / validation |
|---|---|---|
| `cc.policy_epoch`, `cc.vocabulary_sha256`, `cc.plan_path` | required string, sha256, path | admitted policy/vocabulary and the [prep plan](../types/run-plan.md#term-prep-plan) (intent and requirement [steps](nodes.md#term-step)) plus the M1 template DAG the planner emits |
| `cc.execution.track`, `cc.library.snapshot_sha256` | production; required sha256 | production, offline_rsi or isolated_experiment; freezes admitted library and labels every manifest/export |
| `cc.execution.headless` | boolean / false | no stdin/human_session on halt; same durable verdict/review requirement and exit3 |
| `cc.execution.seed` | closed required `{requested: integer?, effective: integer?, unavailable_reason: string?}` / `{requested:null,effective:null,unavailable_reason:NOT_REQUESTED}` | benchmark/CLI requested nonnegative seed is frozen; effective is populated only for a component that actually supports/applies it. Null effective requires a nonempty unavailable_reason (NOT_REQUESTED when requested is null, NOT_SUPPORTED when requested but unsupported); non-null effective requires evidence of application and null unavailable_reason. Unsupported model seed is null with NOT_SUPPORTED. Component model audit records preserve their own requested/effective values; no deterministic model output is claimed |
| `cc.model.cancel_grace_s` | positive integer / 5 | bounded capture grace before killing only the bridge's own model transport child |
| `cc.model.auth_provider`, `auth_profile_id` | codex_managed_file; application | registered AuthProvider and opaque approved profile identity; fixed dedicated volume custody; no token or caller path in configuration |
| `cc.planner.model_id`, `prompt_sha256`, `proposal_timeout_s`, `max_nodes`, `max_proposals_per_submission` | gpt-6.1-sol; required hash when enabled; 120; 32; 1 | isolated experiment track only: the M1 production planner emits the fixed template with zero model calls and does not read these keys; timeout/node bounds limited by policy; no automatic proposal retry/repair |
| `cc.experiments.feature_profile_sha256`, `external_access_approval_ref` | required hash for isolated_experiment; optional reference for mocks | immutable allowed-feature whitelist; approval reference mandatory before real alternate endpoint use |
| `cc.workspace`, `cc.data_dir` | required path, path | canonical project and local persistent roots |
| `cc.profile.display_name`, `timezone` | string / local user; IANA timezone / UTC | display only; not a principal or authorization rule |
| `cc.model.provider`, `model_id`, `socket_path`, `turn_timeout_s`, `cancel_grace_s` | codex_subscription; gpt-6.1-sol; path; integer / 120; positive integer / 5 | doctor verifies account-supported model; empty/unsupported model fails; production route stays Codex, experiment uses isolated approved/mocked endpoints |
| `cc.budgets.capsule_timeout_s`, `check_timeout_s`, `run_timeout_s`, `max_model_calls` | positive integers bounded by published policy | no project value may exceed the fixed policy ceiling; model-call counter is enforced even with absent token counts |
| `cc.intake.max_file_bytes`, `max_text_bytes`, `extensions` | 50000000; pinned policy ceiling; `[txt,md,pdf]` | reference-document ingestion only |
| `cc.resources.preinstalled` | list of `{name, kind: project_asset|validation_data, path}` / empty | declared local baseline/model/dataset resources; readable at startup, no downloads |
| `cc.hardware.device`, `gpu_memory_gb` | required device identifier; positive number optional | selected local hardware; cannot contradict [Brief](../types/research-brief.md#term-research-brief) constraints |
| `cc.security.profile`, `launcher_path`, `oracle_socket`, `oracle_fixture_root` | required profile; absolute paths | immutable approved policy; [fixtures](test-surfaces.md#term-fixture) outside public Git and child mounts |
| `cc.packages.wheelhouse`, `manifest_sha256` | required path, sha256 for POC execution | local compatible hashed wheel closure |
| `cc.ipc.max_frame_bytes` | positive integer / 1048576 | caps every length-prefixed frame on every local socket and child channel, tool-host frames included; a larger frame closes the channel; content travels by authorized refs |
| `cc.test.review_injection` | path / unset | test-only seam: a pre-recorded human review file used by `cc resume` in tests; refused by the production profile |
| `cc.web.host`, `port`, `token_ttl_s` | container interface; 5173; 3600 | host publication fixed to 127.0.0.1; bounded token lifetime |
| `cc.benchmark.port`, `max_body_bytes`, `request_timeout_s` | 8787; 1048576; 30 | versioned authenticated API; host publication fixed to 127.0.0.1; body/HTTP deadline bounded by policy independently of research deadline |
| `cc.telemetry.required_capture`, `trajectory_lossless`, `external_reporting` | true; true; false | required paths cannot be disabled; UI/tracer display flags may vary |
| `cc.channels.external_enabled`, `tmux_enabled` | false; true | external listeners remain disabled; native terminal lifecycle |

Parsing/validation failures return `CONFIG_INVALID` with source file and key path, excluding credentials. File watchers validate a prospective next-run snapshot; they do not mutate active [runs](lifecycle.md#term-run). `begin_run` durably pins the current snapshot. Explicit resume uses the old snapshot; changes to settings or inputs require a new run. Settings which affect already running local services require an explicit service restart with no active run. Authentication secrets are provisioned into the bridge-owned private credential volume, not config values, snapshots, image layers or exports.

## Model bridge

The [model bridge](model-bridge.md) has its own page: the protected UDS, the capability token in the first frame, length-prefixed frames, one blocking exchange per turn, the `status` operation and the failure table. [Model authentication](model-auth.md) is the home of profile custody and the replaceable AuthProvider. This page keeps the configuration keys above and the model-call reservations and scope below.

### Model-call reservations and effective bounds

[System records](records.md) is the home of planning_reserved and model_call_reserved. This section applies to the run scope and, for planning, to the isolated experiment track only: the M1 fixed-template planner makes no model call and has no planning reservation. Intake allocates the real experimental [run_id](records.md#term-run-id) before a proposal; the frozen `run_phase_started` record (phase `prep`, then phase `planned`) is still written only after that phase's validation and freeze. Supervisor commits planning inputs and reservation first, then issues one scope-bound bridge descriptor. A failed reservation write causes zero model turns. Duplicate proposal requests retrieve the reservation/result; interrupted calls are not retried automatically.

Before forwarding any planning or run turn, the trusted broker serializes and commits model_call_reserved, deduplicated by scope/request_id. Count proposal, work, nested and semantic [Gate](../verification.md#term-gate) calls against the same run ceiling from effective configuration and policy; a validated proposal may tighten but never raise it. Planning (experiment track only) additionally obeys max_proposals_per_submission=1. Failed or uncertain turns consume their reservation; cancellation/status/result retrieval do not. Rebuild counts from committed reservations after a crash; in-memory counters are caches. Missing/corrupt quota authority [blocks](modules.md#term-block) calls. Broker additionally enforces the exact declaration direct-call limit in the pinned ExecutionProfile, with stage-specific authoring ceilings defined by their capsule authors; no body code can raise it. Runtime checks enforce the elapsed deadline and remaining call allowance even if a model's proposal estimates are wrong. Never claim unreported token telemetry as cost evidence. Private RSI/oracle calls retain their separately owned session/case reservations and never enter this public quota ledger.

### Model-call scope and private capture

services-v1 is the home of the discriminated ModelCallScope and ScopedCaptureRef shapes. Scope variants are planning (experiment track only; run_id plus planning_request_id), run (run_id), admission (candidate_id plus admission_session_id), rsi_controller (session_id plus attempt_id), and oracle (session_id, oracle_request_id, [TrialRef](../capsule/fixture-oracle.md#term-trialref), case_call_id, arm and repeat). No RSI/private call fabricates a research run or a public Candidate. ModelCallContext carries this exact scope along with reserved [obs_id](observability.md#term-obs-id)/turn; private obs_id names the scope's private call audit rather than a public CC [Observation](../schemas/observation.md#term-observation). Native session identity is derived from the canonical scope hash plus [request_id](../contracts/principles.md#term-request-id)/obs_id/turn, creating a fresh thread without exposing fixture labels.

The bridge accepts only a descriptor authenticated by its authorized namespace authority. Planning scope validates the supervisor's committed planning_reserved record, exact task/library/config/policy pins, authorized planning track, selected model and proposal-call quota before freeze; it cannot use a run descriptor or bypass a [Binding](../schemas/binding.md#term-binding) check by claiming planning. Run scope validates frozen Binding/dispatch/model pins and public Observation reservation; admission validates a submitted Candidate/admission reservation and normally replays fixtures without a live call; RSI controller validates its fixed target/model/config and attempt reservation; oracle validates its private quota request, Trial pins and case/arm/repeat call reservation. No caller-provided scope alone grants access. The profile capability binds principal, scope, permitted model and capture root; tools/proposer cannot mint oracle descriptors. Routing selector remains run-only; planning/admission/RSI/oracle use fixed pinned models.

ScopedCaptureRef is namespace plus a canonical id/hash Ref: public_artifact for planning/run/admission, rsi_private for controller, oracle_private for fixture calls. The existing public store/envelope remains unchanged. Public capture is committed by supervisor; RSI controller commits its private dev/proposal call evidence; oracle alone commits hidden fixture call captures. The bridge sends raw bytes only to the authenticated scope writer and waits for its committed reference before complete. Required capture failure [halts](lifecycle.md#term-halt) that call; duplicate/recovery checks use the same private/public reservation and cannot reroute capture into another namespace. Oracle capture never enters normal events, report context, proposer replies or benchmark export. Only aggregate results cross oracle custody. Broker retrieval returns bounded text only to the principal authorized for that exact scope; private refs cannot be presented at public artifact endpoints. Credential handling remains separate and bridge-owned.

## Linux confinement inside the monolith

[Deployment](deployment.md) is the home of fixed bootstrap identities, capability drops, outer Docker [seccomp](../isolation.md#term-seccomp), nested unprivileged Bubblewrap, read-only mounts, network denial and credential/fixture custody. The same Linux profile runs on Linux Engine and macOS Docker Desktop; there is no native macOS runtime profile in this release. Ordinary capsule tools, generated POC and oracle case execution use distinct versioned inner profiles. Direct child network access is denied; permitted scholarly/model operations use authenticated brokers.

**Reuse base.** [jiuwenbox](../isolation.md#term-jiuwenbox) already implements Bubblewrap, [Landlock](../isolation.md#term-landlock), seccomp and network namespaces. Our `cc/adapters/sandbox.py` calls the jiuwenbox HTTP API (create, exec, upload, download, delete per attempt; `jiuwenbox/src/jiuwenbox/server/routes/sandbox.py`) and requires Landlock compatibility `hard_requirement` (the jiuwenbox default is `best_effort`), network `isolated` and the server token. It never uses jiuwenbox's default policy (opt-in, Landlock best-effort, egress allowed, authentication off). A profile that cannot start with these settings fails with `UNSUPPORTED_SECURITY_PROFILE`; there is no fallback to the host. It does not use the process-global `JiuwenBoxRunner` singleton, which auto-starts a server. Native permission rails in jiuwenswarm and agent-core are off by default (shipped config has `permissions.enabled: false` with defaults `allow`), ignore per-agent permissions (the compose layer in `permission_compose.py` around line 246 uses only Global, User and Session) and are not part of this boundary. The native local `restrict_to_sandbox` check only sees absolute paths written literally in a shell command string; `$var` paths are not detected and `get_cwd` falls back to `os.getcwd()`, so it is not a boundary either. Doctor check zero is native `startup_diagnostics.run_doctor` (map `ok`/`failed` to `pass`/`fail`/`unsupported`), followed by our probes. A native agent never runs a capsule: a capsule gets only admitted snapshots and one attempt directory through brokers.

**Workspace paths.** `./workspace/input` and `./workspace/poc` exist only in the PRD. No current code creates them; the installer creates them, with the identities and volumes, before the first run. Nested Bubblewrap inside Docker, Landlock and seccomp on the target kernel stay unverified until the doctor's negative probes pass. The oracle expected answers never enter candidate mounts or proposer outputs. Only the fixture case input needed to execute that case is passed to its child.

Schema: the restricted-child profile is `tools-v1.schema.json#execution_profile`.

### Enforcement matrix

Every checked [Declaration](../capsule/fields.md#term-declaration) field maps, per execution backend, to one of four states: `denied` by the process boundary, `mediated` by an authenticated broker, `observed` with evidence but not prevented, or `unsupported` and refused before launch. `needs.network`, credentials, paths, process creation and hidden fixtures must be denied or mediated for untrusted code. An `observed` value cannot satisfy a required safety boundary. The matrix is part of the versioned ExecutionProfile and doctor probes it before enabling that profile.

## Behavior: startup and doctor

Schema: `tools-v1.schema.json#doctor_report` with elements `tools-v1.schema.json#doctor_check`.

`doctor(config_snapshot) -> DoctorReport` returns `{version: 1, config_sha256, platform, python_version, profile_id, checks: [{id, status: PASS|FAIL|UNSUPPORTED|NOT_RUN|BLOCKED, mandatory, source, evidence_ref?, blocks_profiles?, message}], ready: boolean}`; `ready` is true only when every mandatory check is `PASS`. Checks cover package versions, model/account auth and nonempty model, secure IPC ownership, local paths/fsync, admitted registry closure, plan structure, hardware, wheelhouse, private fixture separation, helper ownership, and actual negative filesystem/network/credential probes under the execution identities. No live run starts unless mandatory checks pass. The report lists unrun checks as `NOT_RUN` (or `UNSUPPORTED`/`FAIL`), never `PASS`; a check that is not `PASS` blocks the profiles it names in `blocks_profiles`. [Verification](test-surfaces.md) defines the demonstration cases.

## Failure

| Situation | Outcome | Recovery |
|---|---|---|
| Configuration fails to parse or validate | `CONFIG_INVALID` with source file and key path, credentials excluded | fix the file; `begin_run` pins the snapshot, so a change needs a new run |
| A mandatory doctor check is not `PASS` | `ready` is false; the run does not start | fix the platform or profile, then run doctor again |
| A Declaration field cannot be denied or mediated on the backend | `unsupported`; refused before launch | change the backend or the capsule |
| Model stream has not completed after cancellation | the bridge kills and reaps only its own child after `cc.model.cancel_grace_s` | explicit restart; capture is kept |

## Experimental configuration separation

Each run pins a library snapshot and effective configuration. Production keeps the fixed [SwarmFlow](integration.md#term-swarmflow) outer flow, the requirements-planned DAG frozen before execution, the static Codex route and real Gates. Isolated experiment configurations may choose only frozen PRD-whitelisted planner/compiler/routing/Code Mode behavior, using mocks until real endpoint access is approved. PRD 5.6.5 preregistered approved component ablations, including Gate disabling/replacement, are accepted only through a pinned isolated_experiment feature profile/study. Production rejects them. Record actual states, omitted checks and [deviations](../decisions.md#term-deviation); disabled controls never fabricate a passing [Verification](../schemas/verification-record.md#term-verification), authorize production release, change standing or satisfy product acceptance. Confinement, authentication, mandatory capture and evidence integrity remain required. RSI is a separate explicit offline command, never a production switch.

## Tests

Fixtures and fakes: a fake app-server replaying recorded replies, negative probes under real child identities, doctor against supported, unsupported and misconfigured fixtures. Rows in [test surfaces](test-surfaces.md#verification-table): [V01](test-surfaces.md#verification-table), [V02](test-surfaces.md#verification-table), [V07](test-surfaces.md#verification-table), [V30](test-surfaces.md#verification-table).
