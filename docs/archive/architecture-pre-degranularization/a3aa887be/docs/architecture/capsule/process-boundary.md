---
type: design
status: draft
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-02.txt]
provides: [cc.untrusted_process_boundary, cc.process_execution_api]
consumes: [cc.type.poc_bundle, cc.run_plan, cc.binding]
depends_on: [runner.md, permissions.md, ../m1/benchmark.md, ../types/poc-bundle.md]
tags: [capsule, security, m1]
---

> **Draft: concrete execution profile.** The API below uses [environment](../system/environment.md)'s authenticated local service, restricted unprivileged identity, fixed mounts, no direct network, credential exclusion and child-tree termination. Doctor enables it only after executable negative probes pass. The user's Docker agreement packages this service inside the single monolith container; [deployment](../system/deployment.md) owns that outer boundary. General jiuwenbox orchestration remains outside M1. No runtime validation is claimed.

# M1 untrusted process boundary

This is a system service called by the `research.run_benchmark` capsule when it executes generated POC code. It is separate from the CC runner: the runner executes the stage capsule; this boundary contains the generated program that the capsule asks to run. It is also separate from the future, general-purpose jiuwenbox verification sandbox.

**Sources:** PRD 2.9, 3.7.1–3.7.4, 4.1.4, 4.4.9 and 5.4.3. Product requirements include restricting generated code to authorized local resources, preventing unauthorized host-file access and undeclared network/system effects, retaining execution evidence, and treating a violated mandatory boundary as an infrastructure failure. Stage 3.7 specifically requires a restricted unprivileged process for the POC workspace. The frozen PRD deferred Docker/Kubernetes, VM and eBPF isolation; the later user agreement explicitly adopts Docker packaging for M1. Kubernetes, per-task containers, VM and eBPF orchestration remain outside this design.

## Placement and ownership

| Concern | Owner | Contract |
|---|---|---|
| Capsule call lifecycle, Binding, Observation, generic capsule permissions | [CC runner](runner.md) | The runner calls the benchmark capsule and records its call; it does not claim to contain arbitrary code. |
| Generated benchmark child process | This boundary | Accepts a constrained execution request; starts only within the approved POC workspace and returns status plus evidence references. |
| Benchmark protocol and interpretation of measurements | [Benchmark stage](../m1/benchmark.md) | The stage capsule supplies the declared baseline/treatment protocol and consumes the process outcome. |
| Hidden RSI fixtures and oracle results | RSI / protected fixture oracle | The proposer does not receive hidden inputs or expected outputs; the oracle returns aggregate results only. The oracle is not the benchmark process boundary. |
| Broad verification sandbox | jiuwenbox, future phase | General dependency/config/secret/resource isolation; not the M1 process-boundary implementation. |

## Provisional API

The caller and service exchange these named values over the bounded authenticated local channel owned by lifecycle/environment. The interface is defined here; implementation validation must demonstrate the selected profile before execution is enabled.

`execute_poc(PocExecutionRequest) -> PocExecutionResult`

### `PocExecutionRequest`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `request_id` | `id` | yes | Unique execution request, used to join its result and logs. |
| `run_id` | `id` | yes | Run whose authorized workspace is used. |
| `dispatch_id` | `sha256` | yes | Exact durable dispatch reservation for the current benchmark capsule attempt. |
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

The service, not the caller, fixes the permitted filesystem root to that run's `/workspace/poc/`, the executable for each profile, and the effective unprivileged identity. The request cannot supply a host path, executable, UID, network allow-list, or a broader effect permission. `entrypoint_path` must resolve to the exact `harness` file named by the gated [`poc_bundle`](../types/poc-bundle.md); the bundle does not currently have a separate entrypoint field. How baseline and validation inputs are provisioned there follows the `intake` and `poc_bundle` contracts.

### `PocExecutionResult`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `request_id` | `id` | yes | Echo of the request. |
| `state` | `enum(exited, timed_out, denied, unavailable, boundary_violation)` | yes | Distinguishes program outcome from inability to provide the required boundary. |
| `exit_code` | `integer?` | no | Present only when the process exits normally. A non-zero exit is workload evidence, not by itself an infrastructure failure. |
| `stdout_ref` | `Ref(Artifact)?` | no | Captured standard output, stored outside agent reasoning context. |
| `stderr_ref` | `Ref(Artifact)?` | no | Captured standard error, stored outside agent reasoning context. |
| `started_at` | `datetime?` | no | Process start time when launched. |
| `finished_at` | `datetime?` | no | End or termination time when available. |
| `boundary_evidence_ref` | `Ref(Artifact)?` | no | Evidence of effective identity and mandatory boundary pre-checks; no secret or hidden fixture contents. |
| `reason` | `Reason?` | no | Required when state is `denied`, `unavailable` or `boundary_violation`; identifies infrastructure/security handling. |

The benchmark capsule derives its stage output from this result and the registered measurement protocol. It must not relabel `unavailable` or `boundary_violation` as a scientific result. Raw output and traces flow to the Data Foundation run bundle; only bounded summaries/references enter agent context (PRD 3.7.3, 4.5).

## Security invariants

1. No generated process starts unless the required M1 boundary is available and its pre-check passes. Otherwise return `unavailable` and halt as an environment/security failure.
2. The process receives access only to the current run's authorized POC workspace and explicitly provisioned inputs. It cannot read user home files, credentials, the hidden fixture set, or another run's workspace.
3. Network and system-level effects are denied unless an explicit product decision and checked policy permits them. A Declaration is evidence of intent, not enforcement by itself.
4. The service reports the effective identity and boundary check as evidence. If the check fails before or during execution, report `boundary_violation`; do not return a success-shaped benchmark output.
5. Hidden fixture evaluation is a separate oracle API. It never returns fixture contents to the proposer and returns only the allowed aggregate result.
6. The Codex bridge's local IPC security is specified at its own integration seam; it must not be confused with this generated-code boundary.

## Implementation acceptance obligations

- Verify the installer-provisioned runner/oracle identities, POSIX custody and authenticated channel from environment.
- Verify per-backend profile enforcement and typed failure classification.
- Verify capsule/generated-code role separation and offline wheelhouse closure.
- First-run validation: show the active Swarmflow runner cannot read the hidden fixture store and that the generated process cannot escape its POC workspace.

The [deployment](../system/deployment.md) and [environment](../system/environment.md) pages define one Linux Bubblewrap profile within Docker, wheelhouse and authenticated descriptor mechanisms. Linux Engine and macOS Docker Desktop execute that same Linux image. Execution is unavailable until the actual image/kernel/profile probes pass. Requests are idempotent transport identities: identical duplicates return durable result/status; changed bytes conflict. Reserve before launch; never automatically repeat an interrupted request with uncertain effects. Kill/reap the complete child tree on deadline/cancellation and seal raw capture before returning. Capture failure cannot return exited success. stdout_ref/stderr_ref identify committed capture Artifacts by ID and hash.

The design is concrete; platform/security validation remains an executable release obligation. Documentation review cannot substitute for those results.

## Frozen experiment binding

Before setup or benchmark, resolve the reserved dispatch and its Binding, exact gated poc_bundle and hypothesis_blueprint inputs from the supervisor's immutable records. The request's reservation_ref, dispatch_id, obs_id, attempt, run/caller/bundle must match that committed reservation and its authorized Binding. A run/caller/bundle tuple alone cannot identify an explicit restart attempt. Request identity includes profile and reservation identity; setup and benchmark use distinct request IDs under the same capsule reservation. Another attempt cannot reuse its process result. Never select a latest blueprint by name. The service derives snapshot, methods, hardware, seeds, configuration and four role hashes from those admitted refs and verifies all bytes. Setup and benchmark use the same run/bundle/blueprint hash tuple; a changed tuple requires a new run. working_directory must equal the service-assigned attempt root; benchmark argv and env must be empty, with all execution configuration coming from the frozen environment/blueprint. Setup arguments are also fixed by service policy, not caller-supplied pip flags. Reject overrides before launch.

A benchmark exited result additionally requires measurement_manifest_ref:Ref(artifact), committing the ordered trusted MeasurementEvidence refs from [measurement authority](../m1/measurement-protocol.md#trusted-measurement-authority). Setup does not produce it. Raw stdout is checked against that manifest; inability to commit it cannot return success. The service chooses the Python executable and broker descriptors, never the generated code. Result envelopes are closed; this field is part of PocExecutionResult's schema.
