# Model catalog and qualification inventory

`Tier 2 · Part of: [Side systems](README.md)`

The model-routing owner maintains deployment qualification and catalog evidence. The [router](router-design.md) consumes this metadata under a protected [selection profile](../reference/model-routing-contract.md#model-selection-profile).

## Qualification inventory

The owner's v2.1 inventory has 24 entries: 12 executor deployments or families (`E`) and 12 typed learned-tool methods (`T`), arranged by the eight CS/ML task categories with shared candidates counted once. The rows, sources, retained boundaries and the removal audit of the v1.8 list are in the owner design, by link: [candidate pool](../sources/model-routing/received/model-router-design-en-v2.1-2026-10-13.md#25-bounded-csml-candidate-pool-by-task-category) and [removal audit](../sources/model-routing/received/model-router-design-en-v2.1-2026-10-13.md#2510-removal-and-retention-audit). This page does not copy them.

The inventory is a shortlist. It is not 24 enabled services, not 24 Capsules and not a measured quality ranking. The default pilot prioritizes five executor routes plus the document and retrieval tools that admitted cases require. Other entries are reserves or are conditional on an admitted case. Deterministic simulators, compilers, database engines and reference checkers are experiment or oracle tools. They are not entries.

The optional selection configuration is outside the pool. The v1.8 entry `openai.judge` is reclassified as a selection configuration with `routing_eligible=false`. It is never an executor candidate or a scoring oracle.

## Qualification states

Each entry moves through `source_reviewed`, `access_verified`, `contract_qualified`, `development_profiled` and `benchmark_profile_frozen`. Disabled, blocked and retired states also exist. Enabling needs the exact account or service, adapter, settings, licence, resources and verification evidence. A changed model, precision, parser, head, tool or schema invalidates the affected evidence. Unknown, stale or out-of-scope evidence stays visible.

## Catalog entries and refresh

The routing owner pins the catalog, capability-verification and pricing revisions used by each decision, and keeps the entry fields (model ID, revision, endpoint, declared versus verified capability, access state, data policy, pricing) in the [owner design](../sources/model-routing/received/model-router-design-en-v2.1-2026-10-13.md). Registration does not activate an endpoint. A typed tool method is never an executor candidate and never the router alternate model. Approved updates apply to new executions, and revocation is rechecked before each call. M1 trains no online router and activates no new model automatically.

## API provider entry

`Standard`. M1 needs the Codex route only, and that route is not a provider entry (it uses the local IPC in the app container). The API router needs one entry per API provider. The routing owner fills these entries in protected router configuration. The package defines their shape and one rule: **a credential value never appears in a declaration, a catalog record, a route record, an export or a log**. Only the name of the environment variable appears. The value comes from the protected env file that Compose mounts into the app container ([platform](../platform/README.md#container-startup-ipc-and-storage-obligations)).

| Field | Type | Required | Constraint | Meaning |
|---|---|---|---|---|
| `provider_id` | `string` | yes | pattern `^[a-z][a-z0-9_.-]{0,63}$`, unique | Identity of the provider entry |
| `base_url` | `string` | yes | `https` URL, no credential inside it | Endpoint the adapter calls |
| `models` | `object[]` | yes | 1 or more, each `{model_id, provider_model_name}` | The deployments this provider serves. `model_id` is the catalog ID. `provider_model_name` is the name sent to the provider. |
| `credential_env_var` | `string` | yes | pattern `^[A-Z][A-Z0-9_]{0,63}$` | Name of the environment variable that holds the key. Unset or empty means the credential does not resolve (`auth_failed`). |
| `timeout_s` | `number` | yes | 1 to 600 | Time limit of one call to this provider. The call's own time limit still applies when it is shorter. |
| `enabled` | `boolean` | yes | default false | Registration does not activate an endpoint. The routing owner sets it after the capability checks. |

Until the routing owner supplies real entries, the router runs against mocked endpoints and every real provider stays disabled ([open items](../method/open-items.md)).
