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
