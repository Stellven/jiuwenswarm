# Model router: boundary behavior

`Tier 2 · Part of: [Side systems](README.md)`

This page states what the platform must know about the API router: what it receives, what it replies, its deadline and the records it leaves. The routing owner's [v2.1 design](../sources/model-routing/received/model-router-design-en-v2.1-2026-10-13.md) owns the internals: qualification, the candidate pool, selection, the state machine and accounting. The [shared contract](../reference/model-routing-contract.md) owns the fields. The [rulings](owner-rulings.md#routing-v21) record each difference from the owner design.

The router is an M1 side system, off the hot path. It runs as a separate, killable process in the app container. The bridge reaches it only through `RouterPort` ([D44](../method/decisions.md#d44)). With `cc.router.enabled` false, or after any router failure or halt, the bridge uses the Codex route.

## Inputs the platform sends

Each model-backed call sends one `route` request. Its fields are in the [route request](../reference/model-routing-contract.md#route-request):

- `selected_capsule`: the exact declaration, its original-byte hash, the node and subnode contract refs and the protected `bound_context`. Protected upstream code builds it. A client's permission object is not trusted.
- `domain` (`cs_ml`), `task_category`, `workflow_stage` and `call_function`: upstream labels.
- `execution_id`, `request_id` and the authenticated user.
- Protected refs: the host launch profile, hardware inventory, model-selection profile and policy.
- Narrowing requirements and soft preferences only.

The router checks the Capsule pins, the binding, the category and the host against these inputs. It never searches the Capsule library or resolves an unversioned name. The owner's checks are in its [§2.7](../sources/model-routing/received/model-router-design-en-v2.1-2026-10-13.md#27-validation-of-the-upstream-assigned-capsule-and-task).

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

- **Router-owned:** route decision and route event rows in the router's audit store. They are written before the reply. A failed write is a halt (`AUDIT_UNAVAILABLE`).
- **Bridge-owned:** one [route record](../reference/model-routing-contract.md#route-record) before every model call, router on or off. One [model-call record](../reference/model-routing-contract.md#model-call) per call, with `call_started` persisted before dispatch.
- **Routing selection call:** only under `bounded_llm_ablation`. It is a model call with `purpose` `routing_selection`. The bridge records it like any other call.

## Boundary rules

- The hot path imports only `RouterPort`. The router process imports no hot-path code. See the [import boundary](../reference/import-boundary.md).
- The router process never calls a provider, never holds a provider credential and never writes a route record.
- Dispatch of the model call stays in the model bridge. The router has no executor. Its only port call is `route`.
- The router never selects, generates, combines or substitutes a Capsule, and never writes a verifier result.
- Verifier calls use the Codex route in M1. See [RTR-8](model-routing.md#build-criteria).
- After freeze, a failure of the model the router chose halts the node. There is no switch and no replay.
- The router may use its [router alternate model](../reference/model-routing-contract.md#model-selection-profile) once, before freeze, inside the original eligible set.

## Internals

The owner design holds the detail. Read these sections of the [v2.1 design](../sources/model-routing/received/model-router-design-en-v2.1-2026-10-13.md) rather than a copy here: the candidate pool and qualification states (§2.2, §2.5), the development-profile policy and the optional selection ablation (§2.8), the state machine (§2.10) and accounting (§2.12). The [model catalog](model-catalog.md) lists the inventory by link.
