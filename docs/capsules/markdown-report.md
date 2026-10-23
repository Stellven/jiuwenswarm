# Markdown report candidate

`utility.markdown_report` renders supplied content into a new Markdown artifact
and digest manifest. `data.report` explicitly supplies `path`, a single-line
`title`, `sections: [{heading, text}]`, and `data_keys` to include as formatted
JSON. It generates no research prose or inferred claims. Text is escaped so
supplied HTML/Markdown cannot silently introduce active markup. The report
discloses the packet's trust and limitations.

The file's text/digest are appended to the packet; existing input files are
retained and cannot be overwritten. `data.report_manifest` records report
path/hash/size, selected data fields, original file digests, provenance and
trust. Independent checks rebuild the report and verify the complete manifest
and packet. Up to 16 sections/data keys; common packet/file limits apply.
Normal independent semantic review and protected gates remain mandatory.

Merge after [the foundation](capability-dag.md), then explicitly qualify/admit/
activate `utility.markdown_report`. Other optional capsule branches are not
required. The work carrier performs no model call, network or ambient file I/O.
