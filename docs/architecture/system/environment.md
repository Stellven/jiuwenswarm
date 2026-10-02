---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt, integration.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
provides: [system.environment, system.config, system.secure_ipc, system.isolation_profiles]
consumes: [cc.process_execution_api, cc.fixture_oracle_api]
depends_on: [integration.md, ../capsule/process-boundary.md, ../capsule/fixture-oracle.md]
tags: [system, m1, environment, security]
---

# Environment, configuration and security profiles

This page owns the deployment and effective-configuration contract for PRD 3.0, 2.9 and 5.2–5.6. Current source evidence is jiuwenswarm `6cc05c36b`: `pyproject.toml:9` permits Python 3.11–3.13, `:20` pins agent-core `9e339019`, `:141` names `jiuwenswarm.start_services:main`; `jiuwenswarm/start_services.py:525` builds child commands and `:687` checks readiness. Existing startup is wrapped, not assumed to provide the new security profile.

## Platform and dependency matrix

| Target | Architecture requirement | Evidence / release condition |
|---|---|---|
| Linux, Python 3.11, 3.12, 3.13 | POSIX local files, UDS, native tmux and confinement profile below | design targets, not runtime-validated in this documentation session; doctor and platform CI must demonstrate the negative probes before execution is enabled |
| macOS, Python 3.11, 3.12, 3.13 | same public APIs and local workstation surface | control-plane target; generated-code and hidden-fixture execution return `UNSUPPORTED_SECURITY_PROFILE` until an equivalent profile passes the negative probes |
| Windows native | outside PRD 5.2.1 CLI targets | not a declared M1 release target; WSL is evaluated as Linux and must independently pass doctor |

Do not claim every Python/GPU wheel combination works merely because the package version allows it. The installer locks the chosen Python/engine/dependency versions and records them in doctor output; the wheelhouse manifest enumerates compatible wheel filename, hash, version, Python/ABI/platform tags and dependency closure. No unverified platform combination is labelled supported. The offline POC installer uses `pip --no-index --find-links <approved wheelhouse> --require-hashes --only-binary=:all:` on exact requirements, following pip's [secure-install pattern](https://pip.pypa.io/en/stable/topics/secure-installs/). Source distributions, editable installs, remote URLs and build hooks are rejected at the POC gate. If the required environment cannot be assembled offline, halt as an environment problem; missing or undeclared bundle requirements are capsule contract failures.

## Effective configuration

`load_config(project_root) -> ConfigSnapshot` loads packaged defaults, user `~/.jiuwenswarm/config/config.yaml`, then project-local `config.yaml`. Later layers recursively replace scalar/list values and merge mappings; explicit null is rejected for required keys. Project values override user values as PRD 5.6.2 requires. Paths resolve relative to the file defining them, are normalized to absolute paths in the snapshot, and cannot escape configured authorized roots. CLI `--workspace` selects the project; it does not override policy/security limits. Protected invariants (loopback bind, required capture, frozen referee, disabled external messaging) cannot be relaxed by any layer.

`ConfigSnapshot` is `{version: 1, sha256, effective, provenance: map<key_path, source_file>, loaded_at}`. `effective` uses this closed M1 namespace; upstream unrelated keys remain in upstream config and are not accepted as CC extensions. Each subtree below has only its named keys. Missing optional values use the listed default; missing required values are a configuration error.

| Key path | Type / default | Meaning / validation |
|---|---|---|
| `cc.policy_epoch`, `cc.vocabulary_sha256`, `cc.plan_path` | required string, sha256, path | admitted policy/vocabulary and architecture-generated M1 plan |
| `cc.workspace`, `cc.data_dir` | required path, path | canonical project and local persistent roots |
| `cc.profile.display_name`, `timezone` | string / local user; IANA timezone / UTC | display only; not a principal or authorization rule |
| `cc.model.provider`, `model_id`, `socket_path`, `turn_timeout_s` | codex_subscription; required nonempty model id; path; integer / 120 | doctor verifies the account-supported model; empty model is invalid, never silently sent to Codex |
| `cc.budgets.capsule_timeout_s`, `check_timeout_s`, `run_timeout_s`, `max_model_calls` | positive integers bounded by published policy | no project value may exceed the fixed policy ceiling; model-call counter is enforced even with absent token counts |
| `cc.intake.max_file_bytes`, `max_text_bytes`, `extensions` | 50000000; pinned policy ceiling; `[txt,md,pdf]` | reference-document ingestion only |
| `cc.resources.preinstalled` | list of `{name, kind: project_asset|validation_data, path}` / empty | declared local baseline/model/dataset resources; readable at startup, no downloads |
| `cc.hardware.device`, `gpu_memory_gb` | required device identifier; positive number optional | selected local hardware; cannot contradict Brief constraints |
| `cc.security.profile`, `launcher_path`, `oracle_socket`, `oracle_fixture_root` | required profile; absolute paths | immutable approved policy; fixtures outside public Git and child mounts |
| `cc.packages.wheelhouse`, `manifest_sha256` | required path, sha256 for POC execution | local compatible hashed wheel closure |
| `cc.ipc.max_frame_bytes` | positive integer / 1048576 | caps transport envelopes; content travels by authorized refs |
| `cc.web.host`, `port`, `token_ttl_s` | `127.0.0.1`; 5173; 3600 | host/port fixed by PRD; positive bounded token lifetime |
| `cc.telemetry.required_capture`, `trajectory_lossless`, `external_reporting` | true; true; false | required paths cannot be disabled; UI/tracer display flags may vary |
| `cc.channels.external_enabled`, `tmux_enabled` | false; true | external listeners remain disabled; native terminal lifecycle |

Parsing/validation failures return `CONFIG_INVALID` with source file and key path, excluding credentials. File watchers validate a prospective next-run snapshot; they do not mutate active runs. `begin_run` durably pins the current snapshot. Explicit resume uses the old snapshot; changes to settings or inputs require a new run. Settings which affect already running local services require an explicit service restart with no active run. Authentication secrets are stored only in the native user credential/profile store, not config values or snapshots.

## Model bridge

The CC bridge owns a dedicated app-server transport instance and child, separate from native user-chat transport. It serializes CC turns. Cancellation abandons the requester, captures remaining events for cc.model.cancel_grace_s (positive integer, default 5), then kills/reaps only its own CC child if the stream has not completed. A stopped turn cannot be resubmitted automatically. Restart of that transport requires explicit startup/recovery. No credentials or child-control descriptor cross into tools. This is an adapter requirement, not a claim that the existing shared service already has these semantics.

The existing app-server transport uses inherited stdio (`jiuwenswarm/server/runtime/codex_subscription/transport.py:97` at `6cc05c36b`). Retain it inside the trusted bridge. Add a protected UDS between the supervisor/runner and bridge: socket parent mode 0700, socket mode 0600, owner checked before connect, no symlink path, no TCP listener. The supervisor opens a connection before dropping the runner's identity and passes only that connected descriptor with a random run-scoped capability; child tools do not inherit it. Peer credentials plus capability, request id and pinned run context authorize calls. No claim that chmod alone isolates same-UID malicious processes is made; trusted local owner code remains part of the threat boundary.

`ModelBridgeRequest` is `{request_id, run_id, obs_id, operation: turn|cancel|status, session_id, model_id, deadline_at, text_content_sha256?}`. A turn includes an authorized prompt-content ref; cancel/status address an existing request. `ModelBridgeResult` is `{request_id, state: complete|cancelled|unavailable|timed_out|denied, reply_content_sha256?, reason?}`. It uses [lifecycle](lifecycle.md)'s bounded framing. Duplicate ids with identical content return the original result/status; different content gives `REQUEST_CONFLICT`. No timeout automatically resubmits a paid/model turn. Credentials and app-server launch parameters never cross the response. Model request/reply bytes are captured before a successful response.

## Linux confinement profile: reference deployment design

The reference profile uses a narrowly configured launcher provisioned once by an administrator, a dedicated non-login `jiuwen-runner` uid/gid, and private mount/PID/network namespaces through [Bubblewrap](https://github.com/containers/bubblewrap/blob/main/README.md). The launcher accepts only authenticated supervisor requests with approved run-root descriptors and fixed profiles; it accepts no arbitrary executable, UID, bind mount, shell command or policy override. It clears supplementary groups, drops to the restricted uid/gid, removes capabilities, applies no-new-privileges, and launches only installed hashed runner/Python entrypoints. Policy files and launcher code are root-owned and not writable by either child or research workspace.

Bind only approved interpreter/libraries and admitted code read-only, explicit snapshots read-only, a private writable attempt directory, private tmp/proc/dev, and inherited broker descriptors needed for authorized calls. Do not bind home, root filesystem, store, Codex profile or oracle fixtures. Start in a new network namespace with no host network. A syscall allow-list denies mount/namespace mutation, privilege changes, tracing other processes and host IPC; it is a versioned policy reviewed for the installed interpreter. Process creation is limited to the fixed execution subtree; timeout/cancellation kills and reaps that subtree. CPU/memory/disk limits that cannot be applied are explicitly absent; enforce deadline and maximum capture/output bytes at M1.

Ordinary capsule code receives the same restricted filesystem/network boundary. Scholarly network operations use a trusted broker adapter restricted to the admitted operator and explicit service endpoints; direct child sockets fail. Filesystem writes use broker-authorized resource capabilities; code cannot bypass effects merely by calling `open()` outside its writable mount. POC setup and harness execution use the separate profile rooted in a disposable POC workspace, with offline wheelhouse read-only. Import bans are hygiene checks, not the containment mechanism.

The oracle runs outside all runner mounts, with fixture directory 0700 and files 0600 under its own effective principal. Each tested child has no fixture-root path, credentials or oracle channel; it receives only the one input needed for execution. Expected answers remain in the oracle comparator, never in the child. The proposer receives only aggregate counts.

This design needs administrative bootstrap and therefore conflicts with PRD 4.4.9's root-free wording. That remains the explicit product conflict in [open issues](../open-issues.md). macOS has no approved equivalent profile. The exact syscall policy and installed launcher version require source review and negative probes. Doctor returns `UNSUPPORTED_SECURITY_PROFILE` rather than silently executing as the ordinary user.

### Enforcement matrix

Every checked Declaration field maps, per execution backend, to one of four states: `denied` by the process boundary, `mediated` by an authenticated broker, `observed` with evidence but not prevented, or `unsupported` and refused before launch. `needs.network`, credentials, paths, process creation and hidden fixtures must be denied or mediated for untrusted code. An `observed` value cannot satisfy a required safety boundary. The matrix is part of the versioned ExecutionProfile and doctor probes it before enabling that profile.

## Startup and doctor

`doctor(config_snapshot) -> DoctorReport` returns `{config_sha256, platform, python_version, checks: [{id, status: pass|fail|unsupported, evidence_ref?, message}], ready: boolean}`. Checks cover package versions, model/account auth and nonempty model, secure IPC ownership, local paths/fsync, admitted registry closure, plan structure, hardware, wheelhouse, private fixture separation, helper ownership, and actual negative filesystem/network/credential probes under the execution identities. No live run starts unless mandatory checks pass. The report lists unrun checks as unsupported/fail, never pass. [Verification](verification.md) defines the demonstration cases.

## Proposed: component switches and library pin (development only, 2026-10-02)

For ablation runs: `cc.library.snapshot_sha256` (the run refuses a capsule outside that snapshot, and returns the hash in its run output), `cc.rsi.enabled`, `cc.router.enabled` (waits for Model Routing), and `cc.gates.evaluator` (`on`, or `off` only under an `ablation` profile that marks every output `ablation: true`). A switched-off component is absent from the run, never stubbed to pass. Not adopted; the evaluator-gate switch conflicts with `every_step_gated` and needs Muk's decision. Detail: [proposal](../m1/capsule-inventory-proposal.md#benchmark-harness-requests-headless-entry-and-config-assembled-components).
