# Offline expert prediction experiments

This CC measures prediction hypotheses from retained traces before an engine
patch. It never executes inference, changes routing or predicts inference speed.
Use `evaluate` with a scoped artifact ID and a frozen k (1..64, default 6).

The JSON trace has exactly `schema_version: 1`, `origin` (`synthetic` or
`recorded`) and `requests`. Origin is caller metadata, not proof of a live
capture. Synthetic tests and traces must retain their explicit label.

Each request has a unique `request_id`, `split` (`train` or `test`) and nonempty
`events`. All complete training requests precede holdout requests. Every training
demand must precede every holdout prediction issue. Do not split adjacent tokens
from the same request into training and test sets, or tune k on the holdout.

Each event has exactly these fields:

| Field | Meaning |
| --- | --- |
| phase | `prefill` or `decode`; policies keep separate phase/layer histories |
| token, layer | Nonnegative token and layer indices; tokens increase per phase/layer |
| issued_ns | Prediction issue time on the shared monotonic capture clock |
| demand_ns | First demand time for the selected experts |
| selected | Ordered records `{expert, bytes}` for actual chosen expert IDs |
| predicted | Ranked records `{expert, bytes, ready_ns}` issued at issued_ns |

`ready_ns` is the read completion/residency timestamp under the observed policy;
null means no completion was observed by demand. Require complete event capture
and explicit nulls rather than silently dropping pending reads. An already
resident expert should record readiness at issue; earlier residency timestamps
must be normalized to issue. The source must distinguish request and read
identities before constructing events; duplicates within one event are rejected.
Each byte count describes the same expert footprint for that decision. Readiness
must not precede issue, and issue must not follow demand. Events are sorted by
demand. Limits: 8 MiB, 128 requests, 10,000 events, 64 chosen/predicted experts.

Coverage@k is the selected ID intersection with the first k predictions divided
by selected IDs, pooled across all holdout decisions (including empty-history
decisions). Observed timely coverage counts a hit only if ready by demand.
Observed byte waste is completed-by-demand bytes not selected at that demand;
later reuse is unknown, so this is not lifetime waste or physical disk traffic.
Requested but unselected bytes are reported separately.

Frequency counts expert selections by phase/layer on training requests only,
then freezes. Ties use ascending expert ID. Last-token uses only the previous
token's selections within the same test request/phase/layer and only once its
demand has occurred by the new issue time. Its history resets for each request.
Neither baseline reads future token choices or trains frequency on holdout
data. Counterfactual policies have no measured read schedule: their timely
coverage and waste bytes remain unknown. A coverage improvement motivates a
bounded instrumented engine hypothesis; it cannot establish readiness, quality,
resource safety or speedup.
