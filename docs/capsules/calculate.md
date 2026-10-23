# Calculation candidate

`utility.calculate` computes explicit `count`, `sum`, `mean`, `min` and `max`
on selected columns of `data.table = {columns, rows}`. Supply
`data.calculation = {columns: [names], operations: [names], numeric_mode: ...}`.
`numeric_mode` is explicitly `json_numbers` or `decimal_strings`; booleans,
missing values, mixed modes, nonfinite numbers and arbitrary expressions fail.
CSV text from table normalization can use `decimal_strings` without inference.

At most 10,000 rows/128 columns. Numeric inputs have at most 28 significant
digits and adjusted exponent magnitude 28. Arithmetic uses Decimal precision
128 and half-even rounding; repeating means round under that rule. Count is an
integer; other statistics are decimal strings, avoiding silent float conversion.
Empty columns permit count/sum only. Results appear in `data.calculation_result`
with the arithmetic identity. Input data/files, provenance, limitations and
low-trust status are preserved. Independent checks recompute every selected
statistic from original values; normal semantic review/gates still apply.

Merge after [the foundation](capability-dag.md), then explicitly qualify/admit/
activate `utility.calculate`. Other optional branches are not required: a
compatible supplied table packet works directly. No model, network or host I/O
is used by the work carrier.
