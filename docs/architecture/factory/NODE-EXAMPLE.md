# Engine slice, contract and work nodes

This replaces the old presentation example with its unfilled run placeholders.
Historical task records are unchanged. The example below is explanatory, not a
claim that a new engine run has occurred.

## Two kinds of node

The system ontology describes engine boxes: L3 generation loop, L4 model
operations and router/selected-expert/expert-execution, L5 CPU/GPU kernels, and
M weight ranges/read requests/readiness/page cache/memory budget. These local
labels are canonical for this capsule; other architecture drawings may number
layers differently. Match named boxes, not numbers.

The detailed domain slice `expert_weight_readiness` groups the affected boxes.
Under Satay's `-cmoe` configuration expert computation is on CPU. Buffered reads
and predictive reads make mapped weight bytes available through shared memory;
these components do not migrate experts to GPU.

A work node is an inspect/integrate/build/measure/decide action, not an engine box.
Multiple work nodes and multiple CCs can target the same domain slice. Plans are
revisable evidence records; stored evidence/source/image references are shared
context, not a copy of the entire environment passed along DAG edges.

## Contract to intervention to evidence

For new tasks use `constraints.engine_slice: expert_weight_readiness`.
The existing operator task contains objective, constraints, source, resources,
budget and `contract_id`. This engineering brief is distinct from the frozen lab
contract that fixes correctness and measurement conditions. The host copies the
slice to seeded work nodes and adds `contract:<contract_id>` to their inputs.
Unknown slice identifiers are rejected. Old tasks without this optional field
keep their existing behavior; no past recording acquires invented metadata.

| Link | Concrete implementation |
|---|---|
| Domain target | `expert_weight_readiness`, regions and quantities in ONTOLOGY.yaml |
| Method | engine.expert_streaming guide: inspect demand I/O, choose a mechanism, inspect effective settings, stop or revise on contradictory evidence |
| Intervention | expert_fill modifies L4.selected_expert and M.read_request; its mmap_advice and router_prefetch source prerequisites can remain disabled |
| Optional later method | expert_pregate predicts upcoming selection and requests asynchronous reads; recall alone is not readiness |
| Integration | factory.integration_skill supplies application guidance; the agent applies and commits source changes |
| Build | factory.builder.submit/status/result: durable job and identified image, not submission-equals-success |
| Evaluation | factory.lab_client.submit or ab_submit plus status/result, under the pinned contract |
| Interpretation | factory.methodology_ab supplies comparison rules; factory.evidence publishes observations, decisions and revised work graph |

A work node may have `engine_slice: expert_weight_readiness`,
`requires_evidence: [fill.decode_bytes_read, decode.ms_per_token]`, source and
contract references in `inputs`, and result links in `evidence_ids`/`attempt_ids`.
Component materials identify `implements`, `modifies_region` and `quantities`.
Together these explain contract -> slice -> component -> source -> image ->
observations -> decision without inventing another ontology service.

## Operational limits and version boundary

The host validates slice and quantity names, component references, graph
lifecycle and dispatch readiness. Applicability uses heuristic evidence-gap
ranking. This is not proof of optimal selection, nor does a slice automatically
satisfy engagement or acceptance obligations. The agent must publish supporting
evidence and the ordinary acceptance rules still apply.

The capsule is now 2.0.1 with ontology 0.2: the slice and method explanation are
added, and phase.decode_tokens is correctly labelled tokens rather than ns.
`cc-rsi-v1` remains the immutable older baseline. These are new-version changes,
not a retroactive alteration of what the recorded run used. No extra cycle CC
is necessary: the host decision loop and existing method already support repeat,
revise and stop, with no fixed number of versions.
