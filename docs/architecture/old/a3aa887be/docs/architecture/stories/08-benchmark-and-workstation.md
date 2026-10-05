# The external harness starts and retrieves a run

## Starting item

Saurav's harness has an installer-provisioned local Bearer token and an approved configuration Ref. Repository/data files already exist under the configured container workspace/import roots. The API is part of the one monolith at host loopback port 8787; it cannot upload/clone arbitrary assets or receive host absolute paths.

The task body is canonical qualified intake. `cc/benchmark_api.py` requalifies its declared documents/resources with the same ingestion code as local launch. Supplied text must match actual extraction. The harness chooses a profile, not arbitrary code/model/security settings.

## Requests and code connections

| Order | Endpoint | Proposed code and durable result |
|---|---|---|
| 1 | GET /ready and /api/v1/benchmark/profiles | doctor-backed readiness and permitted config catalogue; secrets excluded |
| 2 | POST /api/v1/benchmark/runs | API → ordinary entry/launcher; request B1 accepted durably before 202 run_handle for R1 |
| 3 | GET /api/v1/benchmark/runs/R1 | Committed lifecycle/manifest view; observation does not release work |
| 4 | POST /api/v1/benchmark/runs/R1/exports | After sealing, `cc/data/export.py` validates evidence and requests immutable publication; 201 export_handle |
| 5 | GET /api/v1/benchmark/runs/R1/exports/E1 | Verified benchmark_export with pins, step/attempt/model identities, Gates, outcomes and unavailable telemetry |
| 6 | GET /api/v1/benchmark/runs/R1/artifacts/A1 | Store → authenticated manifest membership/hash verification → exact bytes; no caller file path |
| 7 | Optional POST /api/v1/benchmark/runs/R1/abort | Explicit supervisor cancellation; partial evidence retained, never restart |

The [HTTP owner](../system/benchmark-export.md) and [services schema](../contracts/services-v1.schema.json) own exact wire fields, status/error behavior and route names. The benchmark harness cannot write Gate/release records or resolve oracle/auth namespaces.

## The lost response and stopped workflow

Suppose the connection drops after step 2 was accepted. R1 continues. Repeating B1 with identical bytes returns its existing handle; changed bytes yield REQUEST_CONFLICT. A second independent request during R1 yields WORKSTATION_BUSY before creation. Polling/downloading produces no additional model or experiment calls.

If Screening halts with no eligible opportunity, headless execution records the halt/review requirement and does not wait on stdin. The sealed halted export contains available steps/evidence and explicit missing scientific/report fields. Export cannot infer a verdict or fabricate absent capture. An active run returns RUN_NOT_SEALED.

If the completed experiment scientifically FAILs on valid evidence, Evaluation and Report may still finish through real infrastructure Gates. The export carries that scientific FAIL rather than turning it into an infrastructure failure or hiding it.

## Local workstation connects to the same state

CLI, browser and TUI use `cc/adapters/entry.py`, `local_session.py` and `runview.py`. A dropped progress event is recovered by reading committed records. UI controls cannot authorize a successor. Terminal review records an authenticated explicit action; unchanged-pin resume uses the same run and a new attempt only where execution is required. Changed inputs/config/versions require a new run. A headless harness has no unattended restart endpoint.

Project configuration overrides user configuration at the next-run snapshot; a changed file cannot mutate R1. Service-affecting settings require explicit restart with no active run. tmux/terminal ownership and local token checks deny another user's session. [Workstation](../system/workstation.md), [environment](../system/environment.md) and [lifecycle](../system/lifecycle.md) own these contracts.

## Denied retrieval and adapter replacement

Missing/wrong token is denied before resource access. Path traversal, absolute locator, changed document text, wrong export/run pairing, corrupt bytes or non-manifest Artifact is refused. The fixture oracle's private captures and CODEX_HOME are never retrievable. Unknown token/cost telemetry is null with its reason, not zero.

Saurav's future schema maps at `cc/data/export.py`'s bounded export adapter. It changes neither the scientific benchmark stage nor the authority of committed evidence.
