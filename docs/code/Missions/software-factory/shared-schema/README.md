# Shared capability pool schema — draft 0.1

Task 1 of the agreed integration: normalize the actual workflow pool and CC v2
declarations into one pool. Run Coordinator integration is Task 2. This draft
does not alter either executor, grant permissions, run engineering jobs or change
historical recordings. It is a proposal for joint interface review.

## Deliverables

- [JSON Schema](../../../../../jiuwenswarm/software_factory/schemas/capability-pool.schema.json)
- [Non-executing converters](../../../../../jiuwenswarm/software_factory/shared_pool.py)
- [Four actual converted examples](examples.json)
- [Complete merged declaration pool](pool.json)
- [Pinned source identities and counts](export-summary.json)

## One envelope, four explicit meanings

```text
PoolEntry
  id + version + name + kind
  origin: repository, revision, declaration path, original declaration and hash
  inputs / outputs: named contracts
  requirements: resources, effects, backends and constraints
  verification: declared verifier descriptions / guarantees
  implementation OR composition OR members OR material
```

| kind | Meaning | Can be an execution-graph node? |
| --- | --- | --- |
| operation | One declared invocation: Python stage or CC capability | Yes, after runtime admission |
| composite | A DAG of pinned executable child references and port bindings | Yes, expanded into its real children |
| collection | An unordered group of capabilities and/or materials | No; select a member or define a real executable composition |
| material | Guide, method, component descriptor, patch or reference bytes | No; it is read by a real operation or decision maker |

`operation` means an invocation, not an entire engineering acceptance. In
particular, `factory.builder.submit` returning successfully only acknowledges
submission. Status/reconciliation, result inspection and artifact validation
must complete before a future build stage can claim a built result.

## Mapping the existing sources

| Existing representation | Shared representation |
| --- | --- |
| WorkflowDefinition | composite; child refs point to subworkflow composites |
| SubworkflowDefinition | composite; retains every declared child and binding |
| Stage / serialized executable catalog | operation; retains Python entrypoint and actual validator bindings |
| StageRef / SubworkflowRef | local node alias + pinned capability ref + named input bindings |
| CC document | collection; contains its actual tools and materials |
| CC capabilities.* | operation; retains capability name, selected binding and service declaration |
| CC materials.* | material; retains role, relative path and actual byte hash/size |
| CC defs / takes / gives | resolved port definitions; original declaration remains retained |
| CC needs / changes / guarantees | resource declarations / effects / declared guarantees |

An original CC can contain only materials. For example,
`factory.components.expert_fill` becomes a collection of its component descriptor
and three patches, with no invented executable child. Conversely,
`factory.builder` contains four actual tools: submit, status, cancel and result.

## Identity and hierarchy

Every pool reference pins both `id` and `version`. CC versions retain their
declared semantic versions. Existing workflow definitions have no version field,
so the draft uses `sha256:<canonical-declaration-hash>`. Source repository and
commit remain separate provenance fields. Namespaces prevent source collisions:

```text
workflow:workflow/function_extraction
  -> workflow:subworkflow/function_extraction-function_extraction
      -> workflow:stage/source.discover
      -> workflow:stage/source.bind_operation

cc:factory.builder
  -> cc:factory.builder/tool/submit
  -> cc:factory.builder/tool/status
  -> cc:factory.builder/tool/cancel
  -> cc:factory.builder/tool/result
```

The composite preserves the original local aliases `discover` and `extract`.
Execution instances must later record their full selected parent path, so reuse
of one operation through another parent does not falsely select its siblings.
This draft defines reusable capabilities; it does not put attempts or running
status into immutable definitions.

## Port contract

```json
{
  "transport": "artifact",
  "semantic_type": "source.operations",
  "required": true,
  "data_schema": {},
  "schema_known": false
}
```

| Field | Meaning |
| --- | --- |
| transport | artifact file/reference, ordinary value, or host-bound handle |
| semantic_type | existing domain artifact kind, or an explicit `cc:<kind>` |
| required | presence requirement; CC optionality is retained |
| data_schema | original JSON Schema, if supplied; text defaults to string |
| schema_known | whether a structural schema is actually known |
| description / media_type | optional source metadata |

An artifact path is not a host handle. An opaque CC `json` is not automatically
`source.operator`. An empty schema means unspecified structure, not proof of
compatibility. CUDA AST, Ascend implementation and model tensors retain distinct
semantic types. Changing their labels is not an executable conversion.

The draft validator checks declared port names, required inputs, transports and
semantic types. It does not prove JSON Schema subsumption, inspect runtime
files, validate tensor shapes, or establish algorithm equivalence. A future
Coordinator must validate actual values/files and admit real adapters when needed.

## Composition and partial extraction

```json
{
  "nodes": [
    {
      "id": "extract",
      "capability": {"id": "workflow:stage/source.bind_operation", "version": "<pinned version>"},
      "bindings": {"discovery": {"node": "$input", "port": "discovery"}}
    }
  ],
  "outputs": {"operator": {"node": "extract", "port": "operator"}}
}
```

This explanatory fragment illustrates a selected child composition. Exact,
validated versions are in `pool.json`. Bindings reference a prior local alias or
`$input`; the nodes are serialized in topological order. A definition can be
expanded whole, or a selected child can receive compatible external artifacts.
The latter does not replay the skipped parent children. Collection members have
no implied execution order or dependencies.

## Requirements and verification boundary

Both sources share these requirement fields:

- `resources`: literal names with category tool, environment or unspecified.
  CC needs do not reliably distinguish tools from environment, so they remain
  unspecified until resolved against admitted resources.
- `effects`: declared CC effects; null when no trustworthy effect declaration
  exists. These are requirements, never grants.
- `backends`: declared backend constraints; null when unspecified. Null must not
  be interpreted as supporting every backend.
- `constraints`: existing applicability/acceptance metadata, such as lowering kind.

Verification strings retain source assertions. Actual Python output validators
are additionally retained under `implementation.validators` when present.
CC guarantees are not converted into fictitious verifier implementations.
Host admission, authority, actual command execution, target checks and final
acceptance remain the Coordinator/executor's responsibility.

## Actual conversion performed

The draft was exported from workflow source `9f1358d27f53f36d5359269b15700723e26edec3`
and donor CC source `c7891472b399aecba42735df19b8c80451231355`.
All 16 donor factory CC declarations were checked against their original CC v2
schema. Material hashes were calculated from actual pinned Git blobs.

The common pool contains **150 entries**: 52 operations, 42 composites,
16 collections and 40 materials. These are declarations, not claims that all
150 were executed or newly built. No clone/build/model/CC invocation occurred.

## Reproduce

From the repository root, with `origin/cc-siminfeng` already fetched:

```sh
python -m pip install -r jiuwenswarm/software_factory/schemas/requirements.txt
python -m jiuwenswarm.software_factory.scripts.export_shared_pool \
  --cc-ref c7891472b399aecba42735df19b8c80451231355 \
  --output /tmp/shared-pool.json
PYTHONPATH=tests/software_factory python -m unittest test_shared_pool -v
```

## Decisions for joint review

This v0.1 draft proposes four things to settle before Coordinator integration:

1. Keep collections/materials in the same searchable pool, with executable
   eligibility determined by kind and subsequent admission.
2. Pin declaration versions and source revisions; keep originals for inspection
   and migration rather than rewriting source schemas in place.
3. Use named ports and explicit transport/domain contracts; leave missing
   semantic detail unresolved instead of silently declaring compatibility.
4. Keep runtime decisions, graph revisions, asynchronous job lifecycle and
   verification evidence outside the reusable declaration schema.

This task does not yet define how the Coordinator executes an imported CC,
waits for a durable build, grants permissions or shares evidence. Those require
the next agreement and connected execution verification.
