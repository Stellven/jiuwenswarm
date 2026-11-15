# Exact evidence projections

`factory.evidence_digest_lab` adds two current-task tools: index for shallow JSON
field shapes, and project for explicit RFC6901 JSON-pointer values. It avoids
sending source payloads when only specified fields are requested. It generates no
scientific summary and makes no model-token, latency or quality claim.

The API addition is one prefix entry in the existing dispatch table:
`evidence_digest.*` routes to `jiuwenswarm.factory.evidence_digest.dispatch`.
Existing evidence APIs are unchanged. Pure parsing, pointer traversal, shape and
projection functions live in that module; the adapter reads only current-task
verified Store artifacts. The package COMPONENT.json pins the source module SHA.
It first checks scoped immutable artifact metadata sizes, then calls the existing
scoped artifact_bytes verifier. Cross-task read grants cannot widen this tool's
current-task scope. No path, task override, command, network or GPU input exists.

Each source includes its artifact ID, original raw byte SHA256 and length. Each
selection retains its exact pointer, parsed JSON value and deterministic value JSON
hash. Omitted top-level keys and possible nested omissions are explicit. Selecting
one number does not establish that its unselected context is irrelevant. Examples
select limitations, exactness and authority flags alongside reported numbers;
the caller remains responsible for choosing scientifically relevant context.
Original number lexemes/whitespace/order are not retained; parsed values are.

Limits are enforced by failure rather than truncation: 8 sources, 2MiB/source,
4MiB total, 32 pointers/source, 1024 bytes/pointer, 128 root keys, 100000 nodes and
64 levels/source, 64KiB request and at most 64KiB success envelope. The output
budget includes the API success envelope plus newline, not the enclosing Host
receipt/provenance. Duplicate keys, nonfinite values, invalid JSON and missing or
malformed pointers fail the entire call. There is no fallback to another pointer.

The manual demo copies three actual closed-night JSON input files into a NEW
owned qualification Store. It never opens the closed mission Store:
engine-analysis.json, extra-2-analysis.json (quality), and extra-3-measurements.json
(factory CPU overhead). Selected original fields and hashes are checked exactly
on every source. It retains the source copies, pointer inputs, index/projection,
report and actual Host receipts, including a rejected missing-pointer call.

```bash
export PYTHONPATH=/home/user2/software-factory-spark-20261113/venv/lib/python3.12/site-packages:/home/user2/software-factory-spark-20261113/sources/cc-dgx-spark
/home/user2/rsi-expert-streaming-001/factory-env/bin/python -m pytest --no-cov -q tests/factory/test_evidence_digest.py
/home/user2/rsi-expert-streaming-001/factory-env/bin/python tools/qualify_evidence_digest.py --output-dir /absolute/new-owned-qualification
```

The report distinguishes original raw file bytes from a consistent compact UTF-8
serialization of the parsed input document array, and compares the latter with
serialized projected success-envelope bytes including provenance and omissions.
Those are byte measurements for these exact explicit selections. They are not
provider token counts or evidence of model speed, quality or token savings.

Final qualification evidence: `night-evidence-digest-qualification-003/`, release
`4252789591ab32394f4b405518d8701ddbce1edf21b85f23cb8e0e1edf731a5c`. The final focused suite passed 17 tests
in 1.40 seconds. Earlier rounds 001/002 were successful development snapshots;
round 003 matches the final component source SHA and includes the explicit
null-pointer rejection fix. Raw source copies totaled 124,876 bytes;
the consistent compact parsed input array was 53,127 bytes, versus
10,326 bytes for the projected success envelope
(10,288 for the result alone). Full selected values and source hashes
matched, and the missing-pointer negative call failed. No mission data changed.

To reproduce using only retained copies, pass
`--source-dir /path/to/night-evidence-digest-qualification-003/source-copies` to
the qualification script together with a new `--output-dir`.
