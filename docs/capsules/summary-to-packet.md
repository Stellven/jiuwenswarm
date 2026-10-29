# Summary to work packet

`utility.summary_to_packet` accepts exactly `urn:ai4r:paper-summary:1.0.0` and
emits the unchanged `urn:ai4r:work-packet:1.0.0` envelope. It copies the full
summary, brief and document references, source references and citation details
into bounded packet data, creates a deterministic Markdown view, and marks the
packet low trust. Its independent deterministic checks recompute that
projection from the captured summary input and verify packet hashes and
references.

This adapter makes the type boundary explicit. It does not verify the summary,
turn citations into proof, or convert arbitrary scientific contracts. The
`utility.packet_report` capsule demonstrates a checked downstream packet
consumer; other packet capsules still need their own operation-specific inputs
and checks. The shared packet runtime is an independently pinned dependency,
so a capsule version can evolve while retaining the same packet v1 contract.

The adapter is optional. It must pass the usual Library admission and standing
process before a Planner can select it. Existing v1 utility release manifests
remain readable; newly authored releases use `release_tool.freeze` to record
the shared runtime pin separately from their capsule source closure.
