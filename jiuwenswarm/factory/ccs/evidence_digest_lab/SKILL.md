# Read evidence without requesting full payloads

Use factory.evidence_digest_lab for exact bounded inspection of current-task JSON
artifacts. Use index first when field structure is unknown. Select explicit JSON
pointers with project, preserving relevant caveats and exactness/authority fields.
The tool supplies no scientific summary and cannot choose the caveats for you.

Check source SHA256 and pointer provenance. Read omitted_top_level_keys and the
nested-omission flag before interpreting a number. Source hashes identify the
original bytes; selected values preserve parsed JSON meaning, not source lexemes.
If a requested projection is too large, choose a smaller explicit selection and
retry; do not call a failed result a truncated success. Unknown/missing pointers,
nonfinite JSON, duplicate keys and bound violations fail the whole request.

Supply only task-local artifact IDs. No path or task override is supported.
Use existing evidence APIs when a different representation or full artifact is
actually required. Compare serialized source/result bytes only; do not infer
model-token savings, model latency, quality or scientific conclusions.
