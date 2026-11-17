# CC workflow interconnect version 1

`factory.interconnect/1` is the small data contract between CC capabilities,
subworkflows and workflows. CCs remain functional packages; subworkflows compose
their capabilities; workflows compose those procedures. The same bindings work
through nested composition and evidence-backed graph append. This contract does
not add another executor, message bus or scheduler, or change CC v2 itself.

The machine-readable authoring schema is
`jiuwenswarm/software_factory/interconnect.schema.json`. Its `$defs` also describe
expanded node references and the existing CC port descriptor shape. Version-1
`workflow_catalog` / catalog API responses include this schema as
`interconnect_schema`, so an agent can discover the contract before composing.

## Ports and bindings

A capability is selected by its sealed release and capability name. Named ports
retain the CC's full descriptors: `kind` (`json`, `text`, `artifact`, `handle`),
optional status, JSON Schema, description and media type where declared. Workflow
and subworkflow declarations continue using port-kind maps; detailed destination
validation is owned by the CC host. A broad `json` kind alone establishes no
domain compatibility: add JSON Schema to the CC port when that distinction matters.

Bindings are stored under the destination port name. `source` identifies a
preceding local component alias, or `$input`; `port` names its output. AI may
author bindings, but execution uses the recorded binding and CC host validation.

```json
{
  "request": {
    "source": "build",
    "port": "attempt_id",
    "channel": "result",
    "assemble": {
      "template": {"stage": "screen"},
      "at": "/build_attempt_id"
    }
  }
}
```

This takes the collected build result's attempt ID and constructs the benchmark
request `{"stage":"screen","build_attempt_id":"..."}`. The benchmark CC still
admits the exact same-task build and enforces its frozen evaluation and budget.

- `channel` defaults to `outputs`, meaning the original CC call outputs. For an
  asynchronous submission these are the acknowledgement, not completed work.
- `channel: result` selects a named output of the lifecycle's collected result
  call. Wrapped result envelopes retain their original named `result` port.
  Consumers wait for successful collection; failed or unknown work cannot unlock
  descendants. The acknowledgement and collected outputs remain separately stored.
- Optional `pointer` selects a field using RFC 6901 JSON Pointer. A selection
  requires a declared resulting `kind`; the resolved value is validated before
  dispatch. For example, `pointer: /image/id, kind: text` selects an image identity.
- Optional `assemble` inserts that selected value into a copied JSON object
  template at `at`, another JSON Pointer. The result is JSON. Parent containers
  must exist; no implicit coercion, evaluation, file reads or code execution occurs.
  Version 1 supports one selected source per binding. Multi-source assembly and
  projections after an assembled export require an explicit component or a later
  contract revision; unsupported combinations are rejected.

Expansion replaces local aliases with node IDs and carries the selected channel,
pointer and assembly through subworkflow boundaries. An expanded reference uses
`node_id`, `port`, `kind` and those optional fields. A null node ID means an
external input. Selecting an internal procedure requires supplying its inputs.

## Provenance and outcomes

Bindings live in the durable graph. Source node identity connects them to the
task/run, sealed release, invocation receipts and any admitted job attempt. Keep
artifact URI/digest references intact; the existing host verifies artifact bytes
and host-issued handles. A JSON Pointer is a JSON field selector, not a file path.
No new wrapper copies or renames the original CC outputs or receipts.

Missing fields, incorrect kinds, violated destination schemas and invalid
artifact identities prevent downstream invocation. Resolution failures become
recorded graph failures. Graph completion is distinct from scientific acceptance;
the existing evaluation remains authoritative.

## Versioning and compatibility

New `cc_prepare` configurations select `interconnect: factory.interconnect/1`.
Existing configurations without the field retain the legacy identity and binding
behavior. Extended bindings require explicit version selection. Unknown versions
fail; requests cannot select a different interconnect version or expand authority.
Version and full CC contract descriptors are part of a version-1 run's identity.

Do not change an existing run's configuration to upgrade it. Use a new task/run
configuration when adopting this version or a future revision. Historical records
and active campaigns are not migrated. The schema can evolve when actual
compositions demonstrate a missing feature; changes must preserve replay identity
or introduce a new version.

CPU qualification covers real native CC calls through a deferred-result fixture,
cross-subworkflow binding, restart, structured request assembly, schema rejection,
missing fields and legacy compatibility. It makes no GPU or performance claim.
