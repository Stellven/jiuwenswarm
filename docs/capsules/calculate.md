# Calculation candidate

`utility.calculate` computes explicit `count`, `sum`, `mean`, `min` and `max`
on selected columns of a table. The packet carries the table and the request
as two keys directly under `data`; there is no extra `data` wrapper around them.
A complete packet, with the envelope fields the host adds:

```json
{
  "schema_version": "1.0.0",
  "files": [],
  "trust": "low",
  "provenance": [],
  "limitations": [],
  "data": {
    "table": {"columns": ["amount"], "rows": [["-5"], ["-2"], ["-9"]]},
    "calculation": {"columns": ["amount"], "operations": ["min", "max"],
                    "numeric_mode": "decimal_strings"}
  }
}
```

If you only produce the content of `data`, produce exactly
`{"table": {...}, "calculation": {...}}`. `{"data": {"table": ...}}` inside
`data` is refused with an error that names the extra wrapper. `table` has
exactly `columns` (names) and `rows` (lists of cells); `calculation` has exactly
`columns` (selected names), `operations` and `numeric_mode`. `numeric_mode` is
explicitly `json_numbers` (cells are JSON numbers) or `decimal_strings` (cells
are strings such as `"-5"`, `"0.10"`, `"1e3"`); booleans, missing values, mixed
modes, nonfinite numbers and arbitrary expressions fail. CSV text from table
normalization can use `decimal_strings` without inference.

At most 10,000 rows/128 columns. Numeric inputs have at most 128 significant
digits, adjusted exponent magnitude 128 and 160 characters as text. Arithmetic
uses Decimal precision 128 and half-even rounding; repeating means round under
that rule. A sum that would need more than 128 digits is refused, never
rounded. When equal values are spelled differently (`-0.00`, `0.00`), min and max report
the first one in row order. Count is an
integer; other statistics are decimal strings, avoiding silent float conversion.
Empty columns permit count/sum only. Results appear in `data.calculation_result`
with the arithmetic identity. Input data/files, provenance, limitations and
low-trust status are preserved. Independent checks recompute every selected
statistic from original values; normal semantic review/gates still apply.

Merge after [the foundation](capability-dag.md), then explicitly qualify/admit/
activate `utility.calculate`. Other optional branches are not required: a
compatible supplied table packet works directly. No model, network or host I/O
is used by the work carrier.

Release `m1-3` (module `calculate_v3`) carries the clear shape error and the
128-digit bounds. The `m1-2` release keeps its exact bytes and manifest under
`capsule_extensions/history/v2/`; `m1-3` is a new candidate that needs its own
qualification, admission and activation before live use.

## Port types (m1-4)

From `m1-4` the `packet` input is typed `table_packet`, not `work_packet`. Only a
table produced by `utility.table_normalize` `m1-3` (or any producer that declares
`table_packet`) can feed it. A raw file packet, or a summary converted to a packet,
fails the plan at port type compatibility instead of crashing the worker. The
worker and checks are the `m1-3` ones; only the declared input type changed.
