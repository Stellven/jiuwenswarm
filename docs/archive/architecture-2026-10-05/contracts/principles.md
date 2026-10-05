---
id: contracts.principles
type: standard
level: detail
status: draft
version: 1
provides: [contracts.principles]
depends_on: [README.md, ../terms.md, ../k8s-lens.md]
prd: []
prd_note: engineering standard for message design, not a PRD requirement
tags: [contracts, standards, messages]
---

# Message design principles

Rules for every message, record and API envelope in this system. They follow common industry practice so a new coder, or a coding agent, already knows what to expect. **We want few message shapes.** Before adding one, check that no existing def can carry the data.

## 1. Pick a family

Every def belongs to exactly one family. The family decides the required fields. The index tables in `contracts/index-*.md` have a Family column and the [validator](../system/planner.md#term-plan-validator) [checks](../capsule/fields.md#term-check) it.

| Family | What it is | Required fields | Like |
|---|---|---|---|
| <a id="term-call"></a>**Call** | a request and its result between two modules | request: `version`, `request_id` (every `_request` def); result: `version`, `request_id`, `state`, `reason` when not ok | JSON-RPC request/response, gRPC |
| <a id="term-record"></a>**Record** | a durable fact, written once, never edited | `version` (system records: `schema_version`), an `id` or a content ref, a time (`at` or `_at`) | a Git object, an OCI manifest |
| <a id="term-event"></a>**Event** | "this happened", for views only, never authority | `version`, `event`, `at`, a subject id | CloudEvents, k8s Events |
| <a id="term-frame"></a>**Frame** | one message in a stream between two processes | supervisor and runner frames: `protocol_version`, `request_id`; child-channel frames: a closed discriminator `t` (the version is pinned when the child is spawned); bounded size | HTTP/2 frames, LSP |
| <a id="term-profile"></a>**Profile** | pinned configuration chosen by name | `version`, `profile_id` or `id`, closed settings, no `ext` | k8s `securityContext`, ConfigMap |
| <a id="term-report"></a>**Report** | a read-only summary a tool or the supervisor produces | `version`, a subject id, the results | test report, readiness probe |
| <a id="term-helper"></a>**Helper** | a small shared building block (`ref`, `id`, `hash`, a nested part of a bigger message) | none | |

A def that is only a part of one bigger message is a Helper even when it is indexed (for example `step`, `model_call`, `finding`).

## Key terms

| Term | Meaning |
|---|---|
| <a id="term-message-family"></a>**Message family** (also: family, families) | The kind every message def belongs to: Call, Record, Event, Frame, Profile, Report or Helper. The family decides the required fields. |
| <a id="term-call"></a>**Call** | A request and its result between two modules. Request defs end `_request` and carry a `request_id`; results end `_result` and carry a `state`. |
| <a id="term-frame"></a>**Frame** | One length-prefixed JSON message in a stream between two processes. It has a closed discriminator and a bounded size. |
| <a id="term-report"></a>**Report** | A read-only summary a tool or the supervisor produces, such as a doctor report. It carries a subject id and the results. |
| <a id="term-helper"></a>**Helper** | A small shared building block, such as `ref`, `id`, `hash` or a nested part of a bigger message. It has no required fields of its own. |
| <a id="term-idempotency"></a>**Idempotency** (also: idempotent) | Repeating a call with the same `request_id` and the same canonical bytes returns the same result or in-progress. Different bytes return `REQUEST_CONFLICT`, and a duplicate is never a retry. |
| <a id="term-request-id"></a>**request_id** | The id every `_request` def requires and every result echoes. It makes a call safe to repeat after a lost reply. |
| <a id="term-boundary-sheet"></a>**Boundary sheet** (also: boundary sheets) | The generated sheet for one module boundary: sender, receiver, transport, request and result defs, a real valid message, a real rejected message and what each side does on failure. |

## 2. Rules every def follows

1. **JSON Schema 2020-12.** One schema file per area, one `$defs` entry per message. Types are generated from the schema.
2. **Closed objects.** `additionalProperties: false`. The only open field is `ext`. It is optional, exists only on **Record and Report** defs (never on Call, Event, Frame or Profile), and is a map keyed by producer name with at most 32 keys (`maxProperties: 32`); each value is an object. Unknown fields are rejected, never ignored.
3. **Names.** `snake_case` fields. Request defs end `_request`, results end `_result`, records are nouns, events are `cc.<area>.<event>`. Enum values follow one rule per [kind](../capsule/capsule.md#term-capsule-kind) of field:
   - `lower_snake`: `state`, `kind`, `action`, `decision`, `outcome`, `phase`, `operation`, `purpose`, `result` (one check outcome: `pass`, `fail`, `unknown`), and every other closed vocabulary that is ours.
   - `UPPER_SNAKE`: verdicts (`verdict`, `gate_verdict`, `normalized_verdict`, `status` of a validation or a doctor probe) and every reason or finding code (`code`, `reason_code`, `reason`, `unavailable_reason`). They come from the PRD and from the [Gate](../verification.md#term-gate) verdicts and are never renamed here. `routing_action` (`ADVANCE`, `HALT`, `ESCALATE_TO_HUMAN`) is the PRD Gate routing code and is `UPPER_SNAKE` like a verdict.
   - One enum never mixes the two styles.
4. **Ids.** Opaque strings, unique within their scope, never reused. Ids that are keys end `_id`, references end `_ref`. A field typed `id` may hold a derived value (for example `dispatch_id`); a field typed `hash` is always the SHA-256 of bytes and is named `sha256` or ends `_sha256`.
5. **References by content.** A `ref` is `{id, sha256}`. The hash is of the canonical bytes (JSON Canonicalization, RFC 8785). Following a ref verifies the hash. Large payloads are passed by ref, not inline. A policy ref or a vocabulary ref also uses `{id, sha256}`, with `id` the epoch or version name (`policy-2026-10`, `vocabulary-v3`). A ref to a [batch](../system/storage.md#term-commit-batch) of [Bindings](../schemas/binding.md#term-binding) is a `batch_ref`.
6. **Time.** RFC 3339 UTC with `Z` (`2026-10-05T12:00:00Z`). Fields end `_at` (record envelopes use `at`). Every time string has `format: date-time` and a pattern that ends in `Z`, so a local offset is refused. Durations are integer milliseconds in fields ending `_ms`, or seconds ending `_s`. Never local time.
7. **Absent vs null.** A field that may be unknown is required and set to `null`. Optional means "may be left out", and the schema says so. Never use empty string for unknown.
8. **Numbers.** Integers for counts and sizes. Decimals as strings when exactness matters. Never `NaN` or infinity.
9. **Version.** Every top-level message (Call, Record, Event, Frame, Profile, Report) carries `version` (`protocol_version` for frames and for the socket APIs of the [RSI](../rsi.md#term-rsi), oracle and measurement service, `schema_version` for system records and the run manifest). Nested helper objects do not carry a version. A change that adds, removes or re-means a field is a new version plus an adapter. Same-version change goes in `ext` where `ext` is allowed. Never reuse a removed field name for a different meaning.
10. **Size limits.** Defaults: a string has `maxLength: 4096`, a list has `maxItems: 10000`. Named long text fields (`prompt`, `text`, `message`, `explanation`, `response_text`, `traceback`) allow 65536. Refs and hashes are bounded by their patterns. A frame is bounded by `cc.ipc.max_frame_bytes`. A message over a limit is refused with `LIMIT_EXCEEDED`.
11. **No secrets.** No credentials, tokens or file contents. Pass refs. Redact before logging.
12. **Exit codes.** A process that prints a result exits with one closed set: 0 success, 2 launch, intake or configuration rejected, 3 [halted](../system/lifecycle.md#term-halt), 4 environment unavailable. `run_status_view`, `cli_json_output`, `halt_report` and `launch_result` all use this set.

## 3. Calls

- **Idempotency.** Every `_request` def requires a `request_id` (an idempotent call is any call that can be repeated after a lost reply). Same id and same canonical bytes returns the same result (or "in progress"). Same id and different bytes returns `REQUEST_CONFLICT`. A duplicate is never a retry (we have zero autonomous retries).
- **Result states.** A result has a closed `state` enum. A non-ok result carries `reason` (code from the policy registry), a short message, and `evidence_refs`. Errors follow the shape of RFC 9457 Problem Details: a stable `code`, a human `message`, and detail by reference.
- **Correlation.** A result echoes `request_id`. Everything inside one [capsule](../capsule/capsule.md#term-capability-capsule) call also carries `obs_id` ([observability](../system/observability.md)). Trace context follows W3C Trace Context when spans are on.
- **Timeouts and cancel.** A call states its deadline. Cancel is its own call keyed by the target `request_id`. It kills the whole process tree.
- **Order.** Calls on one channel are processed in order. Cross-channel order is not assumed.

## 4. Records and events

- **Records** are append-only and immutable. A correction is a new record that points at the old one. One writer per record kind ([storage](../system/storage.md)).
- **Events** are best effort and can be dropped. Nothing may depend on receiving one. State is read from records.

## 5. Frames

**All local sockets and child channels use length-prefixed frames**: a 4-byte big-endian length, then that many bytes of UTF-8 JSON. There is no newline-delimited framing. One message per frame. The maximum is `cc.ipc.max_frame_bytes` (1 MiB by default); a frame over it closes the channel, and large values travel by ref. Each frame has a closed discriminator (`kind`, or `t` on the child channel) so a receiver can reject unknown kinds.

## 6. Fixtures and boundaries

- Every def listed in an index, in every schema file, has a fixture case with **at least one valid and one invalid** example. Defs marked `x-internal` are true helpers that no message sends by itself; they are not indexed and are exempt. The invalid example is a realistic mistake: a missing field, a wrong enum, an extra field, a stale version.
- A boundary (two modules that talk) has a **boundary sheet** ([boundaries](boundaries.md)): sender, receiver, transport, request def, result def, a real valid message and a real rejected message, and what each side does on failure. The sheet is generated from the [fixtures](../system/test-surfaces.md#term-fixture), and shows a valid and a rejected result when the boundary has a result def (one-way events say so).
- Both sides test against the same fixtures. A change to a def changes the fixture in the same change.

## 7. Checklist for a new message

1. Can an existing def carry it? If yes, stop.
2. Pick the family and use its required fields.
3. Name it by the rules above. Closed object, `version`, size limits.
4. Add it to its schema file, the index (with family), and the fixtures (valid and invalid).
5. Link the def from the page that describes the message (`Schema:` line).
6. Add or update the boundary entry if it crosses a module boundary.
7. Run `python _tools/validate_contracts.py`.

## Sources of these rules

JSON Schema 2020-12; RFC 3339 (time); RFC 8785 (canonical JSON); RFC 9457 (problem details); JSON-RPC 2.0 (request and result correlation); CloudEvents (event envelope); W3C Trace Context; the idempotency-key pattern used by common payment APIs; compatibility practice from Protocol Buffers and Confluent schema registry (never reuse a field, new version for a changed meaning); Kubernetes API conventions (`apiVersion`, spec and status, immutable fields). These are patterns we follow, not dependencies.
