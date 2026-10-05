---
id: arch.runtime
type: design
level: present
status: draft
version: 1
provides: [arch.runtime]
consumes: [arch.terms, arch.flow, arch.verification]
depends_on: [terms.md, flow.md, verification.md, capsule/runner.md, system/lifecycle.md, system/environment.md, system/storage.md, system/observability.md, capsule/permissions.md]
tags: [runtime, runner, failures, permissions, observability, start-here]
prd: [4.5.3, 4.6.3, 4.6.4, 5.1.2, 2.9]
---

# Runtime: runner, exceptions, permissions, observability

PRD: 4.5.3, 4.6.3, 4.6.4, 5.1.2, 2.9

> Answers: How does a run execute, fail, get permissions and show what happened?

*Kubernetes parallel ([k8s-lens](k8s-lens.md)): a node is like a Pod with `restartPolicy: Never`, a run like a Job with `backoffLimit: 0`. Limits are per-call budgets.*

## Who does what during a run

| Part | Job | Never does |
|---|---|---|
| **Supervisor** ([SwarmFlow](system/integration.md#term-swarmflow)) | validates, [freezes](system/lifecycle.md#term-freeze), reserves each dispatch, calls runner, commits what the runner returns, calls the [Gate host](capsule/gate-host.md#term-gate-host) through `CcBackend`, commits release, dispatches next | run [capsule](capsule/capsule.md#term-capability-capsule) code; decide a Verdict |
| **[CC runner](capsule/runner.md#term-runner)** (managed subprocess) | loads the exact admitted capsule by hash, [checks](capsule/fields.md#term-check) [port types](schemas/port-types.md#term-port-type), [runs](system/lifecycle.md#term-run) it by [kind](capsule/capsule.md#term-capsule-kind), enforces call budget, captures output and effects, returns an [Observation](schemas/observation.md#term-observation) | choose a successor; talk to the store directly |
| <a id="term-gate-host"></a>**Gate host** | deterministic checks, calls the verifier, folds one Verification | invent criteria; let a capsule override the fold |
| <a id="term-store"></a>**Store** | atomic, append-only durable records. Supervisor is the only writer. | n/a |
| <a id="term-model-bridge"></a>**Model bridge** | one model turn per request, authenticated, captured | pick capsules |

Details: [runner](capsule/runner.md), [lifecycle](system/lifecycle.md), [Gate host](capsule/gate-host.md), [storage](system/storage.md).

## One call, in order

1. Supervisor reserves a dispatch identity: `(run_id, step_id, binding_sha256, input hashes, attempt)`. Reserved before anything runs.
2. Runner resolves the [Binding](schemas/binding.md#term-binding), checks input types and preconditions, reserves model-call budget.
3. Runner executes by kind (`tool`, `skill`, `prompt_section` are the M1 kinds). Model turns go to the [Model bridge](system/model-bridge.md#term-model-bridge); effectful work stays in a [restricted child](capsule/process-boundary.md#term-restricted-child).
4. The runner returns output, raw capture and the Observation. The supervisor **commits** them (`commit_request`, boundary BD21); `runner_response` complete means that commit happened.
5. `CcBackend` calls the [Gate](verification.md#term-gate) host; the [Verification](schemas/verification-record.md#term-verification) is **committed** by the supervisor.
6. Supervisor re-reads committed bytes, checks `ADVANCE`, commits the **release**, dispatches the next node.

A passing decision whose save fails never [releases](system/lifecycle.md#term-release) anything.

## Exception handling

| Situation | Outcome | Recovery |
|---|---|---|
| Capsule output invalid or contract broken | Gate FAIL, halt | new run with changed implementation or input |
| Timeout (runner, bridge, process service, or outer deadline: first wins) | halt, kill the whole child tree, record which clock expired | explicit reviewed new run; never automatic |
| Cancel | kill and reap children; no new work | explicit |
| Denied effect, forbidden import or tool | FAIL, halt | fix and new run |
| Runtime or dependency unavailable | ENVIRONMENT_BLOCKED, halt | human fixes environment, new attempt, same pins |
| Process died or killed (any time) | never resumes by itself. On restart the supervisor writes a halt report (INTERRUPTED) and waits. Uncertain effect if no Observation | human runs `cc resume <run_id>`: review record `resume_after_fix`, new attempt of that step under unchanged pins. A disposable attempt directory is cleaned with `cc attempts clean` |
| Duplicate request, same bytes | returns in-flight or committed result | none needed |
| Duplicate request, changed bytes | `REQUEST_CONFLICT` | caller error |
| Persistence failure | halt, nothing released | explicit |
| Model auth lost or model unavailable | halt as ENVIRONMENT_BLOCKED, keep capture | login, then human `resume` (`resume_after_fix`): new attempt under the same pins. The possibly-paid model [turn](system/model-bridge.md#term-model-turn) is never resubmitted without that command. |
| Declared failure mode (for example `NO_ELIGIBLE_OPPORTUNITY`) | capsule ends with outcome error and its failure code; Gate host maps it to INCONCLUSIVE, HALT and ESCALATE_TO_HUMAN | human review. Not a scientific negative. |

Rules: **zero autonomous retries** in M1 for every node. A failed run is kept as a clean failure record. Halt opens the native human session; in headless mode it writes the same evidence, opens nothing, and exits with code 3. Exit codes: 0 success, 2 launch or configuration rejected, 3 halt, 4 environment unavailable. Gate Verdict is identical either way. Full rules: [lifecycle](system/lifecycle.md#failure-human-review-and-recovery).

Failure reasons use one registry ([policy](schemas/policy.md)), not a vocabulary per capsule.

## Permissions and credentials

- **A capsule gets only what its [Declaration](capsule/fields.md#term-declaration) says.** Effects, network, dependencies and secrets are declared, mapped to enforceable rules, and compared with what was observed. Fields nothing can enforce are marked `unsupported` and fail closed ([permissions](capsule/permissions.md)).
- **Restricted children:** distinct non-root identity, private network namespace with no external interface, no credentials, no store, no [fixtures](system/test-surfaces.md#term-fixture), one writable attempt directory ([process boundary](capsule/process-boundary.md)).
- **Generated POC code is untrusted.** Runs only in a separate restricted service with offline, hash-pinned dependencies ([process boundary](capsule/process-boundary.md)).
- **Codex login** is used only by the bridge, on its own volume; never in prompts, configs, exports or child mounts ([model auth](system/model-auth.md)).
- **Framing:** every local socket and child channel uses length-prefixed frames (4-byte big-endian length, UTF-8 JSON, at most `cc.ipc.max_frame_bytes`, default 1 MiB); large values go by reference.
- **Local access:** loopback [ports](capsule/fields.md#term-port) only, per-start session token with `0600` file permissions, no external binding ([environment](system/environment.md)).
- **Configuration** is resolved and frozen at run start; later edits cannot change a running run ([environment](system/environment.md)).

## Observability

- **Required capture is part of the run, not a display:** prompts and replies as sent, outputs, raw stdout/stderr, observed effects, Verification, release. If required capture is lost, the run [halts](system/lifecycle.md#term-halt).
- **Join key:** `obs_id` ties everything inside one capsule call. Events, traces, UI progress, scorecards and benchmark exports are **[derived views](system/storage.md#term-derived-view)** that can be rebuilt from committed records.
- Hiding a view in a diagram or UI never turns capture off. [Data Foundation](system/storage.md#term-data-foundation)'s run records are a view over these records ([observability](system/observability.md), [run records](data-foundation/capsule-run-records.md)).
- Token and cost counts are recorded only when the endpoint reports them; otherwise explicit "unavailable".
- Static host facts (OS, CPU count, GPU model) are captured once at run start. No live CPU/GPU sampling in M1.

## Quality attributes

| Attribute | Requirement | How the design supports it | Where it is checked |
|---|---|---|---|
| Reproducibility | a run can be re-explained from its records | frozen [run plan](types/run-plan.md#term-run-plan), pinned versions, recorded config and seed, raw capture | [test surfaces](system/test-surfaces.md), demo D6 |
| Traceability | every output links to inputs, capsule version, Gate verdict | `obs_id` join key, Observation, Verification, release record | demo D2, US-17 |
| Fail fast | no work continues after a failed check | a Gate on every dispatch call, whole-run halt, zero autonomous retries | D2, D3, US-07 |
| Recoverability | resume without loss or repeat | committed-state replay, explicit human recovery | D3, US-08 |
| Isolation | untrusted code cannot reach secrets or other runs | restricted children, brokers, confinement engine | doctor [probes](system/environment.md#term-probe), US-11 |
| Independence of the verifier | the checker is not changed by what it checks | zero RSI-mutable Gate CCs, fixed profiles | [RSI](rsi.md#term-rsi) attack suite |
| Testability | each block can be built and tested alone | typed schemas, fakes, one-link-at-a-time build order | [build order](build-order.md) |
| Bounded cost | model and time use is capped | per-call time and turn budgets, repair budget, no retries | budget cases in [verification](verification.md) |
