---
type: schema
id: cc.common.v1
status: proposed
tags: [schema, foundation]
---

# Common: envelope and shared shapes · `cc.common.v1`

The fields every record carries and the shapes every schema reuses. It is not a record: every other schema extends it and lists only its own fields (INV-1).

**Rules:** INV-1, INV-6, INV-14, INV-15.

**Field tables.** Every schema page lists its fields with these columns: **Field**, **Type** (the grammar in the [invariants](invariants.md)), **Req** (`req` always present, `opt` may be absent), **M1**, **Unlocks** and **Description**. M1 means the PRD's first milestone.
- **checked**: required for M1 performance and tested for M1 completion.
- **unchecked**: part of the shared schema. When a value is present, admission validates its type and hashes it, but M1 neither requires it nor tests it. **Unlocks** names the tool or feature that reads it.

A `req` field in an unchecked object or record is required only when that object or record is present.

## Fields

**Envelope**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `schema_version` | `string` | req | checked |  | The schema and major version, `cc.<name>.v<major>`. Example: `cc.observation.v1` |
| `id` | `id` | req | checked |  | The record's id, unique within its kind. A page may call it `verdict_id`, `obs_id` and so on. Example: `obs-0001` |
| `scope` | `object` | req | checked |  | What the record belongs to. Exactly one of the three fields below is set |
| `scope.run_id` | `id` | opt | checked |  | A run: one pass of a workflow from request to answer. Example: `run-0001` |
| `scope.candidate_id` | `id` | opt | checked |  | An admission: the Verdict and admission's test calls. Example: `cand-0001` |
| `scope.library` | `boolean` | opt | checked |  | `true` for records about the library, in no run: Standing, test cases and suites, the port type vocabulary, the policy |
| `at` | `time` | req | checked |  | When it was written, RFC 3339 UTC (as jiuwenswarm's E2A `timestamp`) |
| `producer` | `object` | req | checked |  | The record kind's one writer (INV-3) |
| `producer.component` | `string` | req | checked |  | The tool that wrote it. Example: `runner` |
| `producer.version` | `string` | req | checked |  | Its code version. Example: `cc@1a2b3c4` |
| `producer.model` | `string` | opt | checked |  | The model, when a model produced the content. Example: `qwen3-32b` |
| `causation_id` | `id` | opt | checked |  | The record that caused this one, when no field of the record already names it |
| `idempotency_key` | `string` | opt | unchecked | retries | A second write with the same key is dropped, so retries are safe. Example: `run-0001/extract/1` |
| `trace` | `object` | opt | unchecked | tracing | The agent-core span, when one exists. Spans are sampled and expire; records do not |
| `trace.trace_id` | `string` | req | unchecked | tracing | The OpenTelemetry trace id |
| `trace.span_id` | `string` | req | unchecked | tracing | The OpenTelemetry span id |
| `visibility` | `enum(all, builder_hidden)` | opt | unchecked | certification | Default `all`. `builder_hidden` hides it from builders (people and RSI) when it would leak a sealed suite |
| `ext` | `map<string, json>` | opt | checked |  | Extensions keyed by tool, e.g. `{"openjiuwen": {...}}`; other readers ignore them (INV-14, INV-18) |

**Shared shapes**

| Field | Type | Req | M1 | Unlocks | Description |
|---|---|---|---|---|---|
| `Ref.id` | `id` | req | checked |  | The id of the record pointed at, written `Ref(kind)` in type columns |
| `Ref.sha256` | `sha256` | req | checked |  | That record's hash (INV-15), so a wrong reference fails loudly |
| `EvidenceRef.evidence_type` | `string` | req | checked |  | The kind of evidence. Example: `observation` |
| `EvidenceRef.reference` | `string` | req | checked |  | A record id or a URI. Example: `obs-0001` |
| `EvidenceRef.description` | `text` | opt | checked |  | One line on what it shows |
| `EvidenceRef.metadata` | `map<string, json>` | opt | checked |  | Anything else the producer keeps |
| `Reason.code` | `reg(reason_code)` | req | checked |  | Why something failed or moved. Example: `CARRIER_CHANGED` |
| `Reason.message` | `text` | req | checked |  | The same in plain words |
| `Reason.evidence` | `list<EvidenceRef>` | opt | checked |  | What shows it, e.g. the failing Observation |

Records are written once (INV-2); how a store keeps them is not part of the schema.

## Reuse

- `EvidenceRef`: agent-core `symphony/models/evaluation.py:57`, as is.
- `FailureReason` (`evaluation.py:70`): as `Reason`, without `severity`.
- `SymphonyModel` (`symphony/models/_base.py:19`): frozen as there, but extra fields are refused, since ignoring one silently changes the hash.
- `causation_id`, `idempotency_key`: from AI4Research `session-event-v2.schema.json:71-78`.
