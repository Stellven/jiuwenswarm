---
type: design
status: draft
version: 6
owner: muk
sources: [../model_router_design_en.md, ../../product/prd-m1-full-2026-10-02.txt, ../policies.md]
provides: [routing.change_list, routing.adapter]
consumes: [cc.declaration, cc.model_reply]
depends_on: [../capsule/runner.md, ../system/experiments.md]
tags: [model-routing, seam, m1]
---

# Model routing adaptation

The frozen v1.7 [owner design](../model_router_design_en.md) is preserved. This page owns the architecture adaptation and supersedes the former router-capsule proposal. Production uses the fixed Codex endpoint. The [isolated experiment](../system/experiments.md) may choose an approved model; it cannot select capsules, change work semantics or modify Gate authority.

## Comparison and choice

| Owner proposal | Architecture choice | Reason |
|---|---|---|
| Task type first selects Capsule | Plan selects exact admitted capability; routing consumes its requirements | full PRD says DAG-provided capability; one Declaration authority |
| Duplicate Capsule registry and executor | reuse library metadata and CC runner | avoid conflicting contracts and execution owners |
| Catalog with declared/verified capabilities, filter, bounded judge | keep behind ordinary routing adapter | useful implementation, replaceable endpoint choice |
| Route frozen per execution; expires after 30 seconds | freeze per model request identity; durable replay never expires recorded choice | multiple model calls remain attributable; halt does not cause silent re-routing |
| Router audit store | supervisor persists decision; owner audit tables are derived | one persistent writer and reliable evidence joins |
| Fixed GPT-6.1 Sol judge, single-candidate skip | keep in isolated profile; one judge call, no automatic retry | bounded overhead and predictable failure |
| Catalog's large tool/capsule collection | inactive proposal only; no automatic M1 admission | a catalog listing does not extend whitelist |

The style is policy/provider separation from [OPA](https://www.openpolicyagent.org/docs) and linked observations from [OpenTelemetry](https://opentelemetry.io/docs/specs/otel/trace/api/). Neither library is required. Replace the selector behind `select`; callers continue to consume the same recorded decision.

## Public interface

RoutingRequest is run-scoped and applies only to production/static routing and isolated run/planner experiments. Admission replay and offline RSI/controller/oracle calls do not invoke this selector; they use their fixed pinned model through the normalized [model bridge scope](../system/environment.md#model-call-scope-and-private-capture). No synthetic run_id is assigned for routing. Extending selection to a private scope would require a new explicit schema/custody revision.

[Services-v1 schema](../contracts/services-v1.schema.json), definitions `routing_request` and `routing_decision`, owns the closed wire shapes, both with required `version:1`. The descriptions below explain field meanings. The supervisor persists routing results as immutable content Artifacts referenced from the model-call audit, not an undefined SystemRecord variant. `record_ref` identifies that routing Artifact; no new system kind or second writer is introduced.

`select(request: RoutingRequest) -> RoutingDecision` is owned by `cc/adapters/model_routing.py`, called only through the trusted model bridge. It is an ordinary module, not another admitted M1 capsule.

`RoutingRequest` is closed JSON with required `request_id`, `run_id`, `step_id`, `attempt`, `obs_id`, `capsule_name`, `decl_hash`, `catalog_ref`, `config_ref`, `required_capabilities` (string list), `model_allowlist` (string list), `default_model_id`, `deadline_at`, and optional `ext`. Context size and cost preferences are optional `context_chars` (nonnegative integer) and `preferences` (closed list of `cost`, `latency`, `quality`). Routing receives metadata, not hidden fixtures or full artifact contents. For planner calls use the planner's recorded operation identity and null `capsule_name`/`decl_hash`.

`RoutingDecision` is closed JSON with `request_id`, `route_id`, `selected_model_id`, `catalog_ref`, `config_ref`, `reason` (string), `fallback` (boolean), `judge_obs_ref` (nullable Observation reference), `record_ref` (system record reference), and optional `ext`. `record_ref` is returned only after supervisor persistence. Identical request IDs and identical canonical requests reuse the recorded decision; changed requests under the same ID return `IDEMPOTENCY_CONFLICT`; outstanding work returns `IN_PROGRESS`. Unknown required fields/models or expired deadline refuse before a judge call.

The request's catalog/config references resolve immutable content in the store. The allowlist must be a subset of the experiment's approved endpoints; incompatible or unapproved endpoints cannot be fallback candidates. An empty allowlist means all approved compatible entries in the pinned catalog. Exactly one candidate skips judging. Several candidates permit one bounded Sol judge call; malformed/timeout judge responses are recorded as selector failure.

Production and `router.enabled=false` return the pinned default Codex route without a model-selector call. A selector failure may return that default only when it satisfies the same capabilities and approved endpoint policy; otherwise return `NO_COMPATIBLE_ENDPOINT`. Default failure, authentication loss or invocation timeout halts through the standard model-client errors. There is no silent endpoint failover after an effectful model call has begun.

## Records and configuration

The [effective run manifest](../system/records.md) pins track, catalog, configuration and baseline endpoint. The bridge joins `route_id` to its model-turn Observation; capture metadata never enters the task prompt. Requested and resolved model identifiers are recorded even for the static baseline; unknown usage is null, not zero.

Only the supervisor writes the decision record. Neither selector nor judge receives credentials directly. The endpoint adapter owns authentication and transport. Non-Codex real access requires the PRD's access gate; mocks may validate interfaces before approval. A resumed run reads its decision and model result; a new invocation requires a new explicit attempt identity.

## Verification and replacement

Standalone selector cases cover disabled/static route, one/many/no candidates, malformed catalog, capabilities mismatch, unapproved endpoint, judge timeout, duplicate/conflicting identity, failed decision write and resumed record reuse. B2-fixed and B2 share library hash and differ in frozen configuration; experimental results cannot satisfy production acceptance.

Provider-specific registry mapping and exact source symbols belong to [integration](../system/integration.md). A changed catalog needs a new catalog reference; a changed selector needs a new configuration/profile pin. Broader routing, capsule catalog imports and production promotion require a later explicit scope decision.
