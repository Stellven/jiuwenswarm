# Model router: boundary behavior

`Tier 2 · Part of: [Side systems](README.md)`

This page states what the platform must know about the API router: what it receives, what it replies, its deadline and the records it leaves. This page and the [model catalog](model-catalog.md) own qualification, selection, state transitions and accounting. The [shared contract](../reference/model-routing-contract.md) owns the fields. The [rulings](owner-rulings.md#routing-v21) record the adopted responsibilities.

The router is an M1 side system, off the hot path. It runs as a separate, killable process in the app container. The bridge reaches it only through `RouterPort` ([D44](../method/decisions.md#d44)). With `cc.router.enabled` false, or after any router failure or halt, the bridge uses the Codex route.

## Inputs the platform sends

Each model-backed call sends one `route` request. Its fields are in the [route request](../reference/model-routing-contract.md#route-request):

- `selected_capsule`: the exact declaration, its original-byte hash, the node and subnode contract refs and the protected `bound_context`. Protected upstream code builds it. A client's permission object is not trusted.
- `domain` (`cs_ml`), `task_category`, `workflow_stage` and `call_function`: upstream labels.
- `execution_id`, `request_id` and the authenticated user.
- Protected refs: the host launch profile, hardware inventory, model-selection profile and policy.
- Narrowing requirements and soft preferences only.

The router checks the Capsule pins, the binding, the category and the host against these inputs. It never searches the Capsule library or resolves an unversioned name. Validation checks declaration bytes and schema, admitted binding identity, accepted typed ports, protected profile references, dispatch predicates, permissions, remaining budgets and current host/dependency readiness. Invalid pins or bound context are integrity faults; other routing blocks follow the reply table below.

## Replies

The port returns exactly one of three shapes:

| Reply | When | Bridge action |
|---|---|---|
| `RouteDecision` (the [model-route](../reference/model-routing-contract.md#model-route) record) | A model is chosen and the decision is persisted in ready state. | Record `decision_source` `router`. Dispatch the call to `selected_endpoint`. |
| `NoRoute` | Any router halt or block. Examples: no compatible model, routing deadline exhausted inside the router, audit write failure, stale required service, host incompatibility, missing or unauthorized profile, or a same-input duplicate still `ROUTING_IN_PROGRESS` after 30 s. | Use the Codex route. Record `decision_source` `codex_router_failed`, `router_failure` `no_route` and the `router_halt_code`. |
| `IntegrityFault` | The router finds an invalid Capsule pin or invalid bound context. The protected binder should have rejected it before the call, so this is a platform integrity fault and not a router failure. | Halt the node. Record the reason `platform_integrity_fault` with the failed pin or context check. Do not use the Codex route. |

`NoRoute` carries `execution_id`, the phase, the halt code, a retryable flag and redacted candidate reasons. It never names a model. The router writes candidate reasons to its own audit store. The halt codes are the enum in the [route record](../reference/model-routing-contract.md#route-record).

## Deadline and expiry

`RouterPort` enforces `cc.router.deadline_s` (30 s) with its own timer. An expired timer, a dropped connection, a crash or an unreadable reply gives the Codex route with `router_failure` `timeout`, `missing`, `error` or `invalid_decision`. The contract's [router failure rules](../reference/model-routing-contract.md#routerport-the-hot-path-seam) list each case.

A decision in ready state is valid for 30 s. An unexecuted decision then expires. An executing decision does not become invalid when the period passes. A new route needs a new `execution_id` created by explicit upstream work.

## Records

- **Router-owned:** route decision and route event rows in the router's audit store. They are written before the reply. A failed write is a router halt (`AUDIT_UNAVAILABLE`), so the bridge uses the Codex fallback. A failed write of the bridge's own route or call record is different: no call starts and the node halts.
- **Bridge-owned:** one [route record](../reference/model-routing-contract.md#route-record) before every model call, router on or off. One [model-call record](../reference/model-routing-contract.md#model-call) per call, with `call_started` persisted before dispatch.
- **Routing selection call:** only under `bounded_llm_ablation`, which is not built in M1. It is a model call with `purpose` `routing_selection`. The bridge records it like any other call.

## Boundary rules

- The hot path imports only `RouterPort`. The router process imports no hot-path code. See the [import boundary](../reference/import-boundary.md).
- The router process never calls a provider, never holds a provider credential and never writes a route record.
- Dispatch of the model call stays in the model bridge. The router has no executor. Its only port call is `route`.
- The router never selects, generates, combines or substitutes a Capsule, and never writes a verifier result.
- Verifier calls use the Codex route in M1. See [RTR-8](model-routing.md#build-criteria).
- After freeze, a failure of the model the router chose halts the node. There is no switch and no replay.
- The router may use its [router alternate model](../reference/model-routing-contract.md#model-selection-profile) once, before freeze, inside the original eligible set.

## Internals

### Qualification and filtering

Use only runtime-qualified, authorized executor entries in the [catalog](model-catalog.md). Typed tools and selection configurations never enter the executor set. Filter exact access/adapter, task and method scope, verified capabilities, context/output limits, disclosure/effect permissions, current host/dependencies and enforceable remaining budgets. Keep rejection reasons and the original eligible set. A JSON output port alone does not require provider-native schema generation. Reserve verifier allowance separately and recheck readiness before dispatch.

### Selection policy

`development_profile` matches frozen development evidence to the exact category, Capsule/method, deployment/settings and input/resource stratum. Retain candidates meeting the preregistered quality and uncertainty rule. Choose the lowest expected complete execution cost, then supported latency preference and configured priority/ID. Record scope, uncertainty and policy revision. Missing coverage uses the profile's permitted compatible baseline or returns `PROFILE_COVERAGE_MISSING`. A singleton obeys the same coverage rule. No private per-item calibration enters the router.

`fixed_baseline` behaves as router off at the platform boundary. `bounded_llm_ablation` is outside the M1 default: at most one separately pinned and audited selection call, only filtered IDs, no credentials or private labels, no recursion. Its expense counts even when its reply is invalid. It cannot change the Capsule, plan, criteria or tools.

### Claim, freeze and lifecycle

Atomically claim the authenticated `execution_id` before any selection side effect. Fingerprint exact request, input/declaration/contract/dependency pins, protected profiles, host configuration and preferences. Matching duplicates return the stored outcome or `ROUTING_IN_PROGRESS`; changed inputs conflict and cross-user access is denied. Do not hold a transaction across a network call. An interrupted owner with uncertain call state records an unknown outcome and makes no replay under that key.

Persist the initial choice and reason before final preflight, and preserve them if the one profile-authorized router alternate model is used before freeze. The alternate must be in the original eligible set and pass current checks. Shared contract failures never authorize a model switch. Ready expiry, dispatch ownership and the immutable frozen binding prevent duplicate calls. The bridge rechecks dispatch predicates, permissions and binding, persists call-start and performs the call. After the call starts, failure halts the node without replacement or replay.

### Accounting and evaluation

Join router decision/event rows to bridge route and model-call records. Retain requested and effective identities separately; unknown provider identity, usage and cost are unavailable rather than zero. Complete execution expense includes worker, verifier, permitted planning, selection, alternate-model and tool calls. Keep calibration, authoring and RSI costs separate. Monetary savings require reliable tariff and usage evidence; labelled time/call proxies cannot establish money saved. The [acceptance scenarios](routing-acceptance.md) define adverse cases and benchmark populations.
