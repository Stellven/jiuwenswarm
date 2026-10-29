# Model routing

## Approved local product policy, 26 October 2026

The owner approved an additional, versioned product mode:
`ai4r-local-bounded-routing:1`. The historical Codex baseline and evaluation-only
API-router rules below remain descriptions of those modes, not restrictions on
this newly approved local mode. Existing runs retain their frozen policy.

- Each worker/Planner Capsule invocation filters the frozen local pool against the
  current Capsule declaration, adapter capabilities, context and access.
  A bounded E4B call selects one eligible executor using declaration, node task
  summary, candidate cards and remaining budgets. It never plans or swaps CCs.
  It also receives a bounded projection of an already bound Research Brief or
  Intent; the first Intent call can use a short original-request excerpt. It
  receives no attached document contents. Verifier calls receive none of these
  task-context fields and never invoke the selector.
  That executor remains pinned across all internal model turns in the invocation.
  A later turn that exceeds its context/access limits blocks instead of switching
  models. The next Capsule invocation makes its own selection.
- E4B is both the fixed selector and an eligible executor. Its selector call
  dispatches directly, without recursively invoking selection.
- The pool contains Nemotron 3.5 Bolt E4B Q4_K_M, Qwen3.8-27B FP8 and the official
  Nemotron 3.5 Bolt 74B-A9B 24GB GGUF. Model revisions and actual service aliases
  are pinned by the operator. Automatic mode never uses ChatGPT or commercial
  API credentials. ChatGPT remains an explicitly selected comparison mode.
- The three inference services are shared with all Spark OS users and users
  permitted by the administrator's Tailscale network policy. Shared endpoints
  bind loopback and the explicit Tailscale address, never a public interface.
  Stopping AI4R retains these shared services; model context/concurrency limits
  still apply to every caller. AI4R accounts and research state remain separate.
- A verifier call always uses compatible Qwen, with no selector call. The
  verifier Capsule still receives only the subject declaration and output.
  Deterministic checks and existing gates retain acceptance authority.
- Selection has its own call claim, invocation, 15-second ceiling and 256-token
  output ceiling. Node accounting records this allowance separately; original
  worker/verifier limits and the overall run call ceiling remain unchanged.
  Insufficient selection budget leaves the verifier reserve untouched.
- A selector failure can choose the frozen compatible baseline (prefer Qwen)
  before execution starts. No compatible executor/verifier blocks explicitly.
  Integrity/capture failures halt. Executor failures are never replayed on a
  different model. No response is silently obtained from ChatGPT.
- Run selection snapshots are version 2; local automatic route records are
  version 3. Exports retain the pool, deployments, decisions and accounting.
  The implementation is in `research/automatic_routing.py` and the existing
  governed bridge/runner. This bounded inference step is separate from the
  older isolated API-router process and its evaluation contracts.

Deployment commands and current hardware limitations are in
`deploy/m1/SPARK-LOCAL-MODELS.md`. Hardware availability and an actual successful
research run are required before calling the Spark deployment complete.

`Tier 2 · Part of: [Side systems](README.md) · Serves: Knowledge and Standard`

## What it is

Model routing picks which model serves one CC call. The CC itself is chosen earlier, by the static template or the Planner. Routing never picks, swaps or combines CCs, never widens permissions and never accepts an output.

## Why

`Knowledge`. Different models fit different work and costs. The PRD asks for dynamic routing in Phase 3, tested against the Phase 1 fixed Codex route as its Codex fallback (PRD 1.3, 4.3). PRD V.10 makes routing an implementation commitment: the registry, selection, configuration and route-observation code is built, but integration with outside model endpoints and full verification are not mandatory. The Codex CLI route is the mandatory verified baseline, and an unverified route stays off the accepted configuration ([D40](../method/decisions.md#d40)). A router failure never fails a run. A failure of a model the router chose halts the node like any other model failure. The router is on only under an evaluation profile ([D44](../method/decisions.md#d44)).

## How it works

1. A CC asks the runner for a model call.
2. The **model bridge** asks `RouterPort.select` which model to use, before the call starts.
3. With `cc.router.enabled` false, `CodexRouter` answers with the fixed Codex route. With it true, which is allowed only under an approved evaluation profile (PRD 4.3), `RouterPort` asks the API router, a separate killable process in the app container reached over local IPC. The router answers with a frozen decision for one approved model. It returns a model choice only. The bridge dispatches to the provider. Until model access is approved, the router uses mocked endpoints. A verifier call never consults the router: it always uses the Codex route.
4. If the router process is unreachable, crashes, hangs past the 30 s deadline that `RouterPort` enforces, names an unapproved model or returns an invalid reply, `RouterPort` returns the Codex route. A router halt or block (for example no compatible model or an audit write failure) also returns the Codex route, as `no_route`. An invalid Capsule pin or bound context is not a router failure. It is a platform integrity fault and the node halts with a recorded reason.
5. The bridge writes a **route record** and makes the call. The model stays fixed for the whole CC call. A failure during the call halts the node.

Exact rules: [RouterPort seam](../reference/model-routing-contract.md#routerport-the-hot-path-seam).

## Now and after the core

| Now (M1 core and side system) | After the core, or never |
|---|---|
| `RouterPort`, `CodexRouter`, route records, the switch | The alternate verifier: M1 Phase 3 work after the core, reported as done, `BLOCKED` or `INCOMPLETE` ([D33](../method/decisions.md#d33)) |
| The API router, built by the routing owner team in parallel against the [routing contract](../reference/model-routing-contract.md) | Never built: mid-call switching (forbidden, PRD 4.4.2) |
| Benchmark comparison of router on and off | Never built: learned or bandit routing (PRD 4.4.2 blacklist) |

## Do not block

- Hot-path code imports only `RouterPort`, and with the router in its own process it imports no router code. See the [import boundary](../reference/import-boundary.md).
- A declaration states model needs (`needs.model`), never a model.
- Every model call carries a `route_id`.

## Children

- [Router design](router-design.md): the boundary behavior, meaning inputs, replies including `no route`, the deadline and the records. The package owns the filtering, selection and lifecycle rules.
- [Model catalog](model-catalog.md): the 24-entry qualification inventory, qualification states and provider entries.
- [Owner rulings](owner-rulings.md#routing-v21): the adopted integration responsibilities.

**Feeders:** CC declarations (`needs.model`), the run configuration (`cc.router.enabled`, `cc.router.deadline_s`, `cc.router.profile_ref`), the owner catalog snapshot and the run budget ledger. **Users:** the model bridge, the [platform benchmark runner](benchmark-runner.md) and [inspection](../platform/inspection.md).

## Exact contracts

[RouterPort seam and route-record](../reference/model-routing-contract.md#routerport-the-hot-path-seam), [model-selection-profile](../reference/model-routing-contract.md#model-selection-profile), [route-request](../reference/model-routing-contract.md#route-request), [model-route](../reference/model-routing-contract.md#model-route), [model-call](../reference/model-routing-contract.md#model-call), [provider errors](../reference/model-routing-contract.md#provider-errors).

## Build criteria

| ID | Criterion |
|---|---|
| RTR-1 | With `cc.router.enabled` false, every call uses the Codex route and writes a route record with `decision_source` `codex_router_disabled`. |
| RTR-2 | With the router enabled, each router failure gives the Codex route and the matching `router_failure` value: `missing` (the process is not installed, not started or unreachable), `error` (it crashed or replied with an error), `timeout` (no answer within `cc.router.deadline_s`, including a hang), `unapproved_model`, `invalid_decision` (the decision fails validation against the [model-route contract](../reference/model-routing-contract.md#model-route)). Every router halt or block gives `no_route` with a `router_halt_code` from the [route record](../reference/model-routing-contract.md#route-record). |
| RTR-3 | A model failure after the call starts halts the node. No call is resent and no model is switched. |
| RTR-4 | No hot-path module imports router code. The one router client module is the `RouterPort` IPC client (import linter, see the [import boundary](../reference/import-boundary.md)). |
| RTR-5 | The same run with the router on and off has the same frozen plan and declaration hashes. Switching the router off restores the Codex baseline (the PRD 1.3 Phase 3 exit test). |
| RTR-6 | Provider failures map to the [provider error codes](../reference/model-routing-contract.md#provider-errors) (`auth_failed`, `rate_limited`, `timeout`, `provider_error`, `invalid_request`, `network_error`, `invalid_output`), with no SDK retries. |
| RTR-7 | When the bridge cannot write the route record or call record, no new model call starts and the node halts. A failed write to the router's own audit store is a router halt, which gives the Codex fallback. A call that already started keeps a recovery state of unknown or failed. |
| RTR-8 | A verifier subnode call always uses the Codex route, even with `cc.router.enabled` true. Its route record has `router_enabled` false and `decision_source` `codex_router_disabled`. Only the Phase 3 alternate-verifier evaluation profile may override this. |

## Owner acceptance suite

`Standard`. The package [acceptance scenarios](routing-acceptance.md) preserve A01 to A40 with current platform boundary rules. RTR-1 to RTR-8 remain the platform criteria. Evaluation-only scenarios do not become core M1 gate conditions.

## Decisions

[D40](../method/decisions.md#d40), [D44](../method/decisions.md#d44) and the [integration rulings](owner-rulings.md#routing-v21).
