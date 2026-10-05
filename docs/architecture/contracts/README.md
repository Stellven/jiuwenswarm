---
prd: [3.7, 4.3.2, 4.8.2]
id: contracts.readme
type: index
level: detail
status: draft
provides: [contracts.readme]
depends_on: [../terms.md, principles.md]
---
# Authored public contracts

PRD: 3.7, 4.3.2, 4.8.2

> Answers: Which contract files exist, what is in each, and how are they validated?

Every message, record and API envelope between modules has a JSON Schema here, with [fixtures](../system/test-surfaces.md#term-fixture) and an index. These are documentation contracts, not implementation. Payload and CC record schemas stay generated under `exports/schemas/` from their field tables. Never keep a second payload field list here.

## Files

| File | What it holds | Index |
|---|---|---|
| [`services-v1.schema.json`](services-v1.schema.json) | planner request, proposal and validation; experiment request and profile; benchmark request, handle and export; [model bridge](../system/model-bridge.md#term-model-bridge) request and result; model call scope and limits; trusted auth requests; routing and ablation records; shared failure response | [index-services](index-services.md) |
| [`execution-v1.schema.json`](execution-v1.schema.json) | launch, resume and abort; run status and CLI output; freeze; phase, release and [dispatch reservation](../system/records.md#term-reservation) records; runner request and response; commit request and result; tool and skill frames; [Gate](../verification.md#term-gate) request and result; halt report and human review; system records; events | [index-execution](index-execution.md) |
| [`library-rsi-v1.schema.json`](library-rsi-v1.schema.json) | admission, [library snapshot](../capsule/library.md#term-library-snapshot), catalogue and activation; [RSI](../rsi.md#term-rsi) session, attempt and trial records; [fixture oracle](../capsule/fixture-oracle.md#term-fixture-oracle) API; generated-code and measurement requests; delivery; intake and [resource snapshot](../types/resource-snapshot.md#term-resource-snapshot); intent review and repair records | [index-library-rsi](index-library-rsi.md) |
| [`tools-v1.schema.json`](tools-v1.schema.json) | manual Standing commands; doctor check and report; check calling convention and `run_checks`; author kit report; [execution profile](../schemas/profiles.md#term-executionprofile); broker search; policy publish; wheelhouse manifest; config snapshot | [index-tools](index-tools.md) |

The fixture oracle API, the oracle manifests (fixture set and evaluator) and the attack-suite definitions all live in `library-rsi-v1`; there is no separate oracle schema file. Select the named `$defs` entry for a message. Each def belongs to one [family](principles.md#term-message-family) ([principles](principles.md)). `ext` is the only open extension surface, and it exists only on Record and Report defs; Call, Event, Frame and Profile defs are closed. Shape changes after release need a new schema revision or an explicit adapter; draft edits change schema and fixtures together.

## Other contract files

| Item | What it is |
|---|---|
| `index-*.md` | generated tables: def, family, message, sender and receiver, transport, page that describes it |
| [`fixtures/`](fixtures/execution-v1.json) | `execution-v1.json`, `library-rsi-v1.json`, `services-v1.json`, `tools-v1.json`: for each def at least one valid and one invalid example. `_tools/validate_services.py` additionally builds constructed positive and negative service cases |
| [principles](principles.md) | message design rules: families, required fields, versioning, errors |
| [boundaries](boundaries.md) | generated [boundary sheets](principles.md#term-boundary-sheet), one per module boundary (BD ids), each with a real valid and a rejected message. Source: `boundaries.json` |

## Rules

- Linked design pages define behavior, effects and field meanings. The schema defines the wire shape. A page that describes communication links the def.
- `Ref` uses the id and hash encoding in [common](../schemas/common.md). Whether a reference exists, its scope and its content hash need boundary [checks](../capsule/fields.md#term-check) beyond JSON Schema.
- The `retry_profile` def is the closed M1 [RetryProfile](../schemas/profiles.md#term-retryprofile) wire object. [Profiles](../schemas/profiles.md) and [lifecycle](../system/lifecycle.md) require `max_execution_retries=0` for every [effect class](../capsule/fields.md#term-effect-class). Retrieving an already reserved result is not another execution.
- Service errors project the CC Reason into code, message and evidence refs. Only public committed references appear in a reply. The canonical stored reason keeps its private evidence.
- Every local socket and child channel uses length-prefixed frames (4-byte big-endian length, UTF-8 JSON, at most `cc.ipc.max_frame_bytes`, default 1 MiB); large values go by reference.
- Authentication management is not exposed through benchmark endpoints. [Model auth](../system/model-auth.md) and [experiments](../system/experiments.md) define those APIs.

## Control artifacts without duplicate payload types

Planner proposal, validation, effective configuration and template-plan provenance are control [Artifacts](../schemas/artifact.md#term-artifact) (type json, origin control, the allocated run scope). Their API selects the exact `services-v1` def (or the config snapshot def) and validates before publication, so a caller cannot pick a weaker schema. `ext.control.schema_ref` is a closed `{id, sha256}` binding of the expected schema identity and bytes. Raw prompt and reply content is text or file capture, not a proposal. No control def is registered as a [capsule](../capsule/capsule.md#term-capability-capsule) payload port.

In M1 the planner emits the fixed research template ([research-template.plan.json](../capabilities/research-template.plan.json)) with no model call, so `planner_proposal` carries deterministic template provenance in `proposal_source_ref`. A captured model response as proposal source belongs to the isolated experiment track. The [Plan validator](../system/planner.md#term-plan-validator)'s input is the proposal envelope, not a bare [run_plan](../types/run-plan.md#term-run-plan). The planner [runs](../system/lifecycle.md#term-run) after accepted intent and requirements; the exact entry contract is described in [planner](../system/planner.md) and open items are in [decisions](../decisions.md#pending-source-do-not-invent).

## How the contracts are checked

| Command | Checks |
|---|---|
| `python _tools/validate_contracts.py` | all four schema files (no schema is skipped): every schema is valid, every ref resolves, every indexed def has a valid and an invalid fixture, valid ones pass and invalid ones are rejected |
| `python _tools/validate_services.py` | constructed positive and negative service fixtures |
| `python _tools/boundary_sheets.py` | regenerates the boundary sheets from `boundaries.json`, schemas and fixtures |

These use Python and jsonschema in the documentation environment. They do not run research, authenticate Codex, resolve real records or validate process security.
