# Utility candidates that preserve JSON types

`utility.table_normalize_typed`, `utility.calculate_typed` and
`utility.markdown_report_typed` are additive optional `m1-1` candidates. Existing
utility v1/v2 workers, checks, manifests and active associations remain unchanged.
The new candidates require the ordinary independent qualification, admission and
activation before live product use. Source merge alone does not activate them.

The original value checks compare Python objects. Python equates `True` with `1`
and `False` with `0`, which can conceal data-type corruption. These candidates
reuse the original workers/value checks and additionally compare inherited JSON
values with their primitive types preserved. Table normalization independently
parses the original selected file; calculation requires an integer count and
string decimal statistics. Report generation retains original typed data.

The independent helper and reused worker/check source dependencies are pinned
in each new immutable release. The packet schema and general architecture are
unchanged. This is a precise type-fidelity guarantee, not a claim about scientific
truth or semantic-verifier accuracy. Do not replace an active existing pin with
these candidates without qualification and a new frozen plan.
