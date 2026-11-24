# Native expert prefetch readiness

Use completed, retained stock A+30, candidate gate-off, and candidate gate-on
scopes. The three starts must have the same command flags, native allocation,
CPU miss share, common environment, greedy output and reasoning hashes. The
candidate controls share one executable. Keep the exact scope, request, log and
source identities. Gate-off silence and cap evidence are part of the admission.

The `spark-native-prefetch-evidence/1` artifact contains `arms` keyed by
`stock`, `off`, and `on`. Each arm includes decoded raw `start`, `stop`, `scope`
and `probe` receipts, `stderr` text preserving the engine's bytes and a
`references` map for the five artifacts. Receipt references contain
`artifact_id` and `sha256` and come from a verified Factory Store or an exact
closed scope. Use the companion `ops/spark/prepare_prefetch_evidence.py` to
collect and hash real scopes before the native call.

Read terminal `expert_demand_predictor: native phase=...` counters by phase.
Requested records forecasts considered for issue. Already-resident records
existing ready copies and stays separate from speculative issue. Useful-ready
requires observed demand consumption of the issued ready slot. Keep observed
issue/useful bytes, demand misses, late demand, unused issues and pending state
in their emitted units. Do not add cumulative and per-request lines together.
When present, request IDs label the producer's observed scope, and do not make
these rows request timing measurements. Graph rows keep sequence, graph ID and
graph completion separately from counts of completed transfers. Late and miss
counters preserve the producer's independent demand outcomes. An inactive marker has a reason;
missing phase rows remain unobserved even when a legacy log reports zero.

The verifier recomputes the report exactly. A stock and candidate parity check
establishes functional equivalence for these workloads. The separate quiet
timing protocol supplies performance evidence.
