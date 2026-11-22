# Exact task-local evidence projections

Index shows only root/field types and lengths, not scientific summaries or source
values. Project follows caller-supplied RFC6901 JSON pointers and returns exact
parsed JSON values. Include relevant limitations, exactness flags, quality lanes,
contract identity and authority flags alongside numbers. This tool cannot decide
which caveats are scientifically relevant and never interprets or repairs values.

Every source carries its verified original byte SHA256, byte length, artifact ID,
selected pointers and deterministic selected-value JSON SHA256. The selected value
hash uses UTF-8 JSON, sorted object keys, compact separators and no nonfinite
numbers. Parsed values are exact; original whitespace, number lexemes and object
ordering are not preserved. Duplicate object keys and nonfinite/overflowed JSON
numbers are rejected. Missing/malformed pointers fail the entire request.

Explicit omitted_top_level_keys lists source root object fields whose contents
were not touched. A pointer into one child does not include its siblings; the
unselected_nested_fields_may_remain flag makes that partial context explicit.
For root arrays/scalars there are no top-level object keys; root shape remains.
Selecting the empty pointer requests the complete value and still faces all bounds.
No conclusion, admission, causal interpretation, model speed or token savings is
inferred. Serialized source-versus-result byte counts measure only those bytes.

Strict limits: 8 artifacts, 2MiB each, 4MiB total source bytes, 32 unique pointers
per artifact (1024 UTF-8 bytes each), 128 root object keys, 100000 JSON nodes and
64 nesting levels per source. Requests are bounded to 64KiB. The complete success
API JSON envelope plus newline must fit max_output_bytes (1..65536); exceeding
any bound fails, never truncates. Host receipt/provenance wrapping is outside this
result-envelope budget. Sources must have application/json or a +json media type.
Metadata size is checked before artifact_bytes reads the verified blob.

The API uses the existing current-task Store scope and artifact_bytes verification.
No caller task ID, path, network, job or GPU input exists. Even cross-task read grants
do not enable digest access to another task. Index/project append no evidence or
artifacts; existing API telemetry may record the call in the configured Store.
Native process.exec authorizes the fixed API bridge; it is trusted-local execution,
not an OS sandbox. Existing evidence.read/query behavior is unchanged.
