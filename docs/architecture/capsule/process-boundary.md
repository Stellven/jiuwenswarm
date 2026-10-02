---
type: design
status: blackbox
version: 1
owner: muk
sources: [../../product/prd-m1-full-2026-10-01.txt]
provides: [cc.untrusted_process_boundary, cc.process_execution_api]
consumes: [cc.type.poc_bundle, cc.run_plan, cc.binding]
depends_on: [runner.md, permissions.md, ../m1/benchmark.md, ../types/poc-bundle.md]
tags: [capsule, security, m1, blackbox]
---

> **Black box: M1 generated-code boundary.** This page records the required boundary and its provisional API. The PRD makes an unprivileged process boundary mandatory for generated POC execution in M1; it defers the broader jiuwenbox container sandbox. The exact operating-system identity, oracle permissions, and containment mechanism remain open under issues 40 and 54. Benchmarking and RSI must not be treated as runnable until their applicable boundary is checked.

# M1 untrusted process boundary

This is a system service called by the `research.run_benchmark` capsule when it executes generated POC code. It is separate from the CC runner: the runner executes the stage capsule; this boundary contains the generated program that the capsule asks to run. It is also separate from the future, general-purpose jiuwenbox verification sandbox.

**Sources:** PRD 2.9, 3.7.1–3.7.4, 4.1.4, 4.4.9 and 5.4.3. Product requirements include restricting generated code to authorized local resources, preventing unauthorized host-file access and undeclared network/system effects, retaining execution evidence, and treating a violated mandatory boundary as an infrastructure failure. Stage 3.7 specifically requires a restricted unprivileged process for the POC workspace. The PRD defers Docker/Kubernetes, VM and eBPF isolation to a future phase.

## Placement and ownership

| Concern | Owner | Contract |
|---|---|---|
| Capsule call lifecycle, Binding, Observation, generic capsule permissions | [CC runner](runner.md) | The runner calls the benchmark capsule and records its call; it does not claim to contain arbitrary code. |
| Generated benchmark child process | This boundary | Accepts a constrained execution request; starts only within the approved POC workspace and returns status plus evidence references. |
| Benchmark protocol and interpretation of measurements | [Benchmark stage](../m1/benchmark.md) | The stage capsule supplies the declared baseline/treatment protocol and consumes the process outcome. |
| Hidden RSI fixtures and oracle results | RSI / fixture oracle, under issue 40 | The proposer does not receive hidden inputs or expected outputs; the oracle returns aggregate results only. The oracle is not the benchmark process boundary. |
| Broad verification sandbox | jiuwenbox, future phase | General dependency/config/secret/resource isolation; not the M1 process-boundary implementation. |

## Provisional API

The caller and service exchange these named values over a local authenticated channel. This interface is provisional until issues 40 and 54 are resolved and the area passes the design loop.

`execute_poc(PocExecutionRequest) -> PocExecutionResult`

### `PocExecutionRequest`

| Field | Type | Required | Meaning |
|---|---|---:|---|
| `request_id` | `id` | yes | Unique execution request, used to join its result and logs. |
| `run_id` | `id` | yes | Run whose authorized workspace is used. |
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

## Waiting on

- Issue 40: reconcile the unprivileged execution identity and fixture-oracle isolation requirements across PRD 4.4.9 and 5.4.3; define the actual trust principals and oracle channel.
- Issue 54: specify per-backend runtime guard coverage and failure classification, and ensure it agrees with this boundary.
- PRD items 42–43: confirm capsule-versus-generated-code roles and offline wheelhouse provisioning.
- First-run validation: show the active Swarmflow runner cannot read the hidden fixture store and that the generated process cannot escape its POC workspace.

The [environment](../system/environment.md) page proposes actual Linux process/mount/network confinement, wheelhouse and authenticated descriptor mechanisms. macOS remains unavailable pending issue 57. Requests are idempotent transport identities: identical duplicates return the durable result/status; changed bytes conflict. Reserve execution before launch, and never automatically repeat an interrupted request with uncertain effects. The service kills and reaps the entire child tree on deadline/cancellation and seals raw capture before returning. Required capture failure cannot return exited success. stdout_ref/stderr_ref refer to committed capture Artifacts with both record ID and hash.

Until the source conflicts and platform validation are settled, this is a provisional deployment contract, not a checked implementation guarantee.

## Frozen experiment binding

Before setup or benchmark, resolve the reserved dispatch and its Binding, exact gated poc_bundle and hypothesis_blueprint inputs from the supervisor's immutable records. The request's run/caller/bundle must match that reservation. Never select a latest blueprint by name. The service derives snapshot, methods, hardware, seeds, configuration and four role hashes from those admitted refs and verifies all bytes. Setup and benchmark use the same run/bundle/blueprint hash tuple; a changed tuple requires a new run. working_directory must equal the service-assigned attempt root; benchmark argv and env must be empty, with all execution configuration coming from the frozen environment/blueprint. Setup arguments are also fixed by service policy, not caller-supplied pip flags. Reject overrides before launch.

A benchmark exited result additionally requires measurement_manifest_ref:Ref(artifact), committing the ordered trusted MeasurementEvidence refs from [measurement authority](../m1/measurement-protocol.md#trusted-measurement-authority). Setup does not produce it. Raw stdout is checked against that manifest; inability to commit it cannot return success. The service chooses the Python executable and broker descriptors, never the generated code. Result envelopes are closed; this field is part of PocExecutionResult's schema.
