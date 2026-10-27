# Table normalization candidate

`utility.table_normalize` converts one explicitly selected packet file into
`data.table = {columns, rows}`. `data.table_request` names `file`, `format`
(`csv` or `json`), exact ordered `columns`, and `delimiter` (one character for
CSV, null for JSON). CSV requires an exact matching header and preserves text
including numeric-looking strings. JSON requires an array of records with
exactly those columns and finite scalar values; original value types remain.
No header/type/delimiter inference, missing-field repair or silent row dropping.
At most 10,000 rows and 128 columns; the common packet limits also apply.

The output retains input files, requests, provenance, limitations and trust.
Independent checks compare the complete table against the original file, so
missing, changed or reordered values fail. It uses no model or external I/O;
the normal independently budgeted semantic review and protected gate still run.

Merge after [the foundation](capability-dag.md); qualify, admit and activate
`utility.table_normalize` explicitly. It has no dependency on other optional
capsule branches. Local tests cover quoted CSV, JSON ordering/types, corruption,
malformed rows, duplicate keys, nonfinite values and low-trust preservation.

## Port types (m1-3)

From `m1-3` the result port is typed `table_packet` (same packet schema). The input
stays `work_packet`, because it carries the raw file. A consumer that needs a parsed
table, such as `utility.calculate` `m1-4`, declares `table_packet`, so the binder
rejects a plan that sends an unparsed file straight to it. Earlier releases keep
their declared types and stay pinned in `history/v2`.
