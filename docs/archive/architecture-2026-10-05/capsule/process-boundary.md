---
id: capsule.process-boundary
type: module-spec
status: draft
version: 1
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [cc.untrusted_process_boundary, cc.process_execution_api]
consumes: [cc.type.poc_bundle, cc.run_plan, cc.binding]
depends_on: [runner.md, permissions.md, ../capabilities/benchmark.md, ../types/poc-bundle.md]
tags: [capsule, security, m1]
level: detail
prd: [2.9, 3.7.1, 4.1.4, 5.4.3]
---

> The API below uses [environment](../system/environment.md)'s authenticated local service, restricted unprivileged identity, fixed mounts, no direct network, credential exclusion and child-tree termination. Doctor enables it only after executable negative probes pass. The service is packaged inside the single monolith container ([placement](../placement.md)); [deployment](../system/deployment.md) is the home of that outer boundary. The service launches the generated program with jiuwenbox's confinement engine (see [Confinement engine](#confinement-engine)); general jiuwenbox orchestration (dependency install, secrets, resources) remains outside M1. No runtime validation is claimed.

# M1 untrusted process boundary

PRD: 2.9, 3.7.1, 4.1.4, 5.4.3

> Answers: How does M1 contain generated POC code when a capsule asks to run it?

## Purpose

This is a system service called by the `research.run_benchmark` [capsule](capsule.md#term-capability-capsule) when it executes generated POC code. It is separate from the [CC runner](runner.md#term-runner): the runner executes the [stage capsule](../capabilities/README.md#term-work-capsule); this boundary contains the generated program that the capsule asks to run. It is also separate from the future general-purpose verification sandbox; it reuses only [jiuwenbox](../isolation.md#term-jiuwenbox)'s confinement engine.

**Sources:** PRD 2.9, 3.7.1–3.7.4, 4.1.4, 4.4.9 and 5.4.3. Product requirements include restricting generated code to authorized local resources, preventing unauthorized host-file access and undeclared network/system effects, retaining execution evidence, and treating a violated mandatory boundary as an infrastructure failure. Stage 3.7 specifically requires a restricted unprivileged process for the POC workspace. The [frozen](../system/lifecycle.md#term-freeze) PRD deferred Docker/Kubernetes, VM and eBPF isolation; M1 adopts Docker packaging ([decisions](../decisions.md), A12). Kubernetes, per-task containers, VM and eBPF orchestration remain outside this design.

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-confinement"></a>**confinement** | Running generated code in a restricted, unprivileged process that can reach only its authorized workspace, with no network egress. If the required settings cannot be applied, nothing runs. |
| <a id="term-restricted-child"></a>**restricted child** | The unprivileged process started under the fixed profile to run generated POC code. It has no credentials, no hidden fixtures and no access to other runs. |

## Placement and responsibility

| Concern | Responsible party | Contract |
|---|---|---|
| Capsule call lifecycle, [Binding](../schemas/binding.md#term-binding), [Observation](../schemas/observation.md#term-observation), generic capsule permissions | [CC runner](runner.md) | The runner calls the benchmark capsule and records its call; it does not claim to contain arbitrary code. |
| Generated benchmark child process | This boundary | Accepts a constrained execution request; starts only within the approved POC workspace and returns status plus evidence references. |
| Benchmark protocol and interpretation of measurements | [Benchmark stage](../capabilities/benchmark.md) | The stage capsule supplies the declared baseline/treatment protocol and consumes the process outcome. |
| Hidden [RSI](../rsi.md#term-rsi) [fixtures](../system/test-surfaces.md#term-fixture) and oracle results | RSI / protected [fixture oracle](fixture-oracle.md#term-fixture-oracle) | The proposer does not receive hidden inputs or expected outputs; the oracle returns aggregate results only. The oracle is not the benchmark process boundary. |
| Confinement engine | jiuwenbox (Bubblewrap, [Landlock](../isolation.md#term-landlock), [seccomp](../isolation.md#term-seccomp), network namespace), reused | Starts the restricted child under the fixed profile below. |
| Broad verification sandbox | future phase | General dependency/config/secret/resource isolation through jiuwenbox orchestration; not part of M1. |

## Confinement engine

jiuwenbox already implements Bubblewrap mount and PID namespaces, Landlock, seccomp, network namespaces and cgroup limits. It is the reuse base for every restricted child, including the generated POC process. We use its policy model and launcher, not its defaults. Its defaults are opt-in, Landlock best-effort, network egress allowed and server authentication off. The service requires:

- Landlock `hard_requirement`, so a kernel without Landlock fails instead of running with less;
- network `isolated`, with no egress from the child (a capsule that declares egress, such as `op.scholarly_search`, reaches its endpoints only through a broker);
- the server token, so only the authenticated service can start a sandbox;
- a policy the service builds itself from the fixed profile; the request supplies no policy.

If the engine cannot start with these settings the result is `unavailable` with `UNSUPPORTED_SECURITY_PROFILE`; there is no fallback that [runs](../system/lifecycle.md#term-run) the child on the host. Native permission rails in jiuwenswarm and agent-core are off by default and are not isolation; nothing on this page relies on them. The engine's source facts were read at a local head: re-check them at the pinned revision before coding against them. Nested Bubblewrap inside Docker, Landlock and seccomp on the target kernel are unverified until the doctor [probes](../system/environment.md#term-probe) pass.

Schema: the restricted-child profile the launcher enforces is `tools-v1.schema.json#execution_profile`.

## Interface: provisional API

The caller and service exchange these named values over the bounded authenticated local channel owned by lifecycle/environment. The interface is defined here; implementation validation must demonstrate the selected profile before execution is enabled.

`execute_poc(PocExecutionRequest) -> PocExecutionResult`

Schema: `library-rsi-v1.schema.json#poc_execute_request` and `library-rsi-v1.schema.json#poc_execute_result`. Both carry `version: 1`. The schema enforces the profile rules below: for `benchmark`, `entrypoint_path` is a string and `argv` and `env` are empty; for `poc_setup`, `entrypoint_path` is null.

### `PocExecutionRequest`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `version` | `integer` | yes | Always 1. |
| `request_id` | `id` | yes | Unique execution request, used to join its result and logs. |
| `run_id` | `id` | yes | Run whose authorized workspace is used. |
| `dispatch_id` | `id` | yes | Exact durable [dispatch reservation](../system/records.md#term-reservation) for the current benchmark capsule attempt. |
| `obs_id` | `id` | yes | Observation identity allocated by that reservation. |
| `attempt` | `integer` | yes | Positive attempt number allocated by the supervisor. |
| `reservation_ref` | `SystemRef` | yes | ID/hash of the committed dispatch_reserved record; resolved and authenticated by the service. |
| `caller_decl_hash` | `sha256` | yes | Admitted benchmark capsule allowed to request the execution. |
| `bundle_ref` | `Ref(Artifact)` | yes | The gated `poc_bundle` containing the POC program and declared requirements. |
| `profile` | `enum(poc_setup, benchmark)` | yes | Selects the fixed installer or the single baseline-then-treatment harness; it cannot relax policy. |
| `entrypoint_path` | `string?` | conditional | For benchmark, exact harness path in the gated bundle. For poc_setup, null: fixed installer uses the requirements role. |
| `working_directory` | `string` | yes | Relative path inside the run's POC workspace; resolution outside that root is denied. |
| `argv` | `list<string>` | yes | Arguments passed to the profile's fixed executable and resolved entrypoint; the caller cannot choose an executable or shell. |
| `env` | `map<string,string>` | yes | Explicit non-secret environment, limited to keys allowed by the selected profile. Inherited host environment and loader/interpreter override variables are excluded. |
| `timeout_s` | `number` | yes | Per-process deadline, bounded by the run policy. |

The service, not the caller, fixes the permitted filesystem root to that run's `/workspace/poc/` (the PRD's `./workspace/poc/`: it exists only in the PRD, nothing in current code creates it, and the installer creates it), the executable for each profile, and the effective unprivileged identity. The request cannot supply a host path, executable, UID, network allow-list, or a broader effect permission. `entrypoint_path` must resolve to the exact `harness` file named by the gated [`poc_bundle`](../types/poc-bundle.md); the bundle does not currently have a separate entrypoint field. How baseline and validation inputs are provisioned there follows the `intake` and `poc_bundle` contracts.

### `PocExecutionResult`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `version` | `integer` | yes | Always 1. |
| `request_id` | `id` | yes | Echo of the request. |
| `profile` | `enum(poc_setup, benchmark)` | yes | Echo of the request profile; the schema uses it to require `measurement_manifest_ref` for a benchmark `exited` result. |
| `state` | `enum(exited, timed_out, denied, unavailable, boundary_violation)` | yes | Distinguishes program outcome from inability to provide the required boundary. |
| `exit_code` | `integer?` | conditional | Required when `state` is `exited`; absent otherwise. A non-zero exit is workload evidence, not by itself an infrastructure failure. |
| `stdout_ref` | `Ref(Artifact)?` | when exited | Captured standard output, stored outside agent reasoning context. |
| `stderr_ref` | `Ref(Artifact)?` | when exited | Captured standard error, stored outside agent reasoning context. |
| `started_at` | `datetime?` | no | Process start time when launched. |
| `finished_at` | `datetime?` | no | End or termination time when available. |
| `boundary_evidence_ref` | `Ref(Artifact)?` | when exited | Evidence of effective identity and mandatory boundary pre-checks; no secret or hidden fixture contents. |
| `measurement_manifest_ref` | `Ref(Artifact)?` | conditional | Required when a `benchmark` result is `exited`; absent for `poc_setup`. See the frozen experiment binding below. |
| `reason` | `Reason?` | no | Required when state is `denied`, `unavailable` or `boundary_violation`; identifies infrastructure/security handling. |

The benchmark capsule derives its stage output from this result and the registered measurement protocol. It must not relabel `unavailable` or `boundary_violation` as a scientific result. Raw output and traces flow to the [Data Foundation](../system/storage.md#term-data-foundation) run bundle; only bounded summaries/references enter agent context (PRD 3.7.3, 4.5).

## Behavior: security invariants

1. No generated process starts unless the required M1 boundary is available and its pre-check passes. Otherwise return `unavailable` and halt as an environment/security failure.
2. The process receives access only to the current run's authorized POC workspace and explicitly provisioned inputs. It cannot read user home files, credentials, the hidden fixture set, or another run's workspace.
3. Network and system-level effects are denied unless an explicit product decision and checked policy permits them. A [Declaration](fields.md#term-declaration) is evidence of intent, not enforcement by itself.
4. The service reports the effective identity and boundary check as evidence. If the check fails before or during execution, report `boundary_violation`; do not return a success-shaped benchmark output.
5. Hidden fixture evaluation is a separate oracle API. It never returns fixture contents to the proposer and returns only the allowed aggregate result.
6. A capsule is never run natively by a jiuwenswarm agent: it gets only admitted snapshots and one attempt directory, through brokers; generated code gets only the POC workspace.
7. The Codex [bridge](../system/model-bridge.md#term-model-bridge)'s local IPC security is specified at its own integration seam; it must not be confused with this generated-code boundary.

## Failure

| Situation | Outcome | Recovery |
|---|---|---|
| The boundary is unavailable or its pre-check fails before launch | `unavailable`; no process starts; halt as an environment or security failure | fix the platform, then explicit review |
| The engine cannot start with the required settings | `unavailable` with `UNSUPPORTED_SECURITY_PROFILE`; no host fallback | use a supported platform |
| The boundary check fails during execution | `boundary_violation`; no success-shaped benchmark output | explicit review |
| Process exceeds `timeout_s` | `timed_out` | explicit review; no automatic rerun |
| Policy-denied request | `denied` | change the request within the approved profile |

## Tests: implementation acceptance obligations

Rows in [test surfaces](../system/test-surfaces.md#verification-table): [V07](../system/test-surfaces.md#verification-table), [V22](../system/test-surfaces.md#verification-table).

- Verify the installer-provisioned runner/oracle identities, POSIX custody and authenticated channel from environment.
- Verify per-backend profile enforcement and typed failure classification.
- Verify capsule/generated-code role separation and offline wheelhouse closure.
- First-run validation: show the active [Swarmflow](../system/integration.md#term-swarmflow) runner cannot read the hidden fixture store and that the generated process cannot escape its POC workspace.

The [deployment](../system/deployment.md) and [environment](../system/environment.md) pages define one Linux Bubblewrap profile within Docker, wheelhouse and authenticated descriptor mechanisms. Linux Engine and macOS Docker Desktop execute that same Linux image. Execution is unavailable until the actual image/kernel/profile probes pass. Requests are [idempotent](../contracts/principles.md#term-idempotency) transport identities: identical duplicates return durable result/status; changed bytes conflict. Reserve before launch; never automatically repeat an interrupted request with uncertain effects. Kill/reap the complete child tree on deadline/cancellation and seal raw capture before returning. Capture failure cannot return exited success. stdout_ref/stderr_ref identify committed capture [Artifacts](../schemas/artifact.md#term-artifact) by ID and hash.

The design is concrete; platform/security validation remains an executable release obligation. Documentation review cannot substitute for those results.

## Frozen experiment binding

Before setup or benchmark, resolve the reserved dispatch and its Binding, exact gated [poc_bundle](../types/poc-bundle.md#term-poc-bundle) and [hypothesis_blueprint](../types/hypothesis-blueprint.md#term-hypothesis-blueprint) inputs from the supervisor's immutable records. The request's reservation_ref, [dispatch_id](../system/records.md#term-dispatch-id), [obs_id](../system/observability.md#term-obs-id), attempt, run/caller/bundle must match that committed reservation and its authorized Binding. A run/caller/bundle tuple alone cannot identify an explicit restart attempt. Request identity includes profile and reservation identity; setup and benchmark use distinct request IDs under the same capsule reservation. Another attempt cannot reuse its process result. Never select a latest blueprint by name. The service derives [snapshot](library.md#term-library-snapshot), methods, hardware, seeds, configuration and four role hashes from those admitted refs and verifies all bytes. Setup and benchmark use the same run/bundle/blueprint hash tuple; a changed tuple requires a new run. working_directory must equal the service-assigned attempt root; benchmark argv and env must be empty, with all execution configuration coming from the frozen environment/blueprint. Setup arguments are also fixed by service policy, not caller-supplied pip flags. Reject overrides before launch.

A benchmark exited result additionally requires measurement_manifest_ref:Ref(artifact), committing the ordered trusted MeasurementEvidence refs from [measurement authority](../capabilities/measurement-protocol.md#trusted-measurement-authority). Setup does not produce it. Raw stdout is checked against that manifest; inability to commit it cannot return success. The service chooses the Python executable and broker descriptors, never the generated code. Result envelopes are closed; this field is part of PocExecutionResult's schema (`library-rsi-v1.schema.json#poc_execute_result`).
