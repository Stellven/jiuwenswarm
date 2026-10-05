# Data and permissions

[Start here](README.md) · Specified design · Platform and isolation validation pending

## Inputs and outputs

- Intake validates locally provisioned text, Markdown, PDF, repository and dataset resources, then creates immutable snapshots. Extraction creates source text with source references and offset basis. Intent capsules then derive accepted intent through their Gates; gated requirements supply the planner and DAG input contract. The exact revised ports are tracked in [control flow](../../m1/control-flow.md). See [intake](../../types/intake.md), [source text](../../types/source-text.md), [resources](../../types/resource-snapshot.md) and [workstation](../../system/workstation.md).
- Literature enters through bounded scholarly search; local/code search uses declared resources. A model receives authorized read-only evidence projections, not arbitrary store access. See [local search](../../m1/op-local-search.md), [scholarly search](../../m1/op-scholarly-search.md) and [CodeSearch](../../m1/op-codesearch.md).
- Scientific execution freezes protocol, datasets, baseline/treatment, methods, environment and predicates before execution. Trusted adapters own measurements; generated code supplies experiment behavior rather than self-awarded scores. See [measurement protocol](../../m1/measurement-protocol.md).
- Delivery is ordinary code, not a capsule: it processes/formats accepted terminal results and returns published artifacts through authorized retrieval/user views. The report-writing CC is separate from this delivery boundary.
- Publisher input is the report **and** POC, benchmark, trusted StageContext (the frozen stage/run evidence context), destination and request identity. It requires the committed report Verification/release, validates the complete manifest and publishes files atomically. See [delivery](../../m1/delivery.md).
- The external benchmark runner uses authenticated local HTTP invocation/status/abort and sealed manifest/export retrieval. It does not use a runtime file-upload or clone endpoint. The API is published on `127.0.0.1:8787`, requires a local bearer token except for liveness, and accepts one active research run. Its final external schema connects through a bounded export adapter; harness internals are separate. See [benchmark export](../../system/benchmark-export.md).

## Storage and evidence

- Immutable artifacts and append-only control records share run/step/attempt/request and policy/configuration references. The trusted writer owns public records; the publisher owns its destination; the private oracle owns hidden fixture evidence. See [records](../../system/records.md) and [storage](../../system/storage.md).
- Freeze prevents later stages from changing data, scoring policies or dependencies. Content hashes identify exact bytes; aliases are resolved before freeze.
- Required raw capture and durable records remain enabled in every diagram variant. Telemetry/UI projections are derived; hiding observability edges does not disable required capture or change authority. See [telemetry](../../system/workstation.md) and [information flow](../../system/information-flow.md).

## Permission boundaries

- Dedicated persistent Codex credential storage has a separate login and one serialized owner. Do not copy a personal desktop auth file into disposable workers. The auth provider is replaceable behind the bridge. Exact refresh/account behavior still needs real tests. See [model authentication](../../system/model-auth.md).
- Generated experiment code runs in a restricted child with declared input/output paths. It receives no model credentials, public store, hidden fixtures, Docker socket or unrestricted network. Containerization alone is not the isolation claim. See [process boundary](../../capsule/process-boundary.md).
- Startup pre-checks fail closed if the selected confinement mechanism is unavailable. Linux container mechanisms and macOS host operation require validation; an unsupported profile cannot count as platform acceptance. See [deployment](../../system/deployment.md) and [environment](../../system/environment.md).
- Proposed platform targets are Linux Docker Engine and macOS Docker Desktop running the same pinned Linux/Python 3.12 image. The repository allows Python `>=3.11,<3.14`; that range is not a validated image matrix. Windows native is outside M1 targets. See [environment](../../system/environment.md).
- Configuration layers are packaged defaults, user settings, then project settings. Project values override user values within protected policy limits. Changes affect a new run; resume retains its frozen snapshot. Service-affecting settings require an explicit restart with no active run. Dependencies come from a pinned offline wheelhouse. See [environment](../../system/environment.md).

## Data flow views

Use [current control flow](../../m1/control-flow.md) for the request-to-DAG path. Use [information-flow variants](../../system/information-flow.md) to inspect current data, Gate, persistence and output boundaries. The same page has views without derived observability, without RSI, and without either. [Temporal sequences](../../system/temporal.md) show writes, publication and activation in order.

Storage, sandboxing and API patterns are documented beside their decisions in the linked owners. This page introduces no new permission or endpoint.

[Next: schemas and connections](schemas-and-connections.md)
