# Cache-size Pareto analysis

Use completed, independently verified 16-position llama.cpp native bank launches. The
fixed uncached greedy workload has three discarded warmups and five measured
requests at each of 512 and 2048 prompt tokens, with 32 generated tokens per
request. The original verifier establishes exact request, cap, readiness,
kernel scope, engine, bank, source conditioning, and result identity.

`ops/spark/report_cache_pareto.py --source HOME TASK ARTIFACT_PREFIX` reads the
native producer's `analysis.json`, `analysis-input.json`, `verify-receipt.json`
and release manifest from the Factory Store. It joins them to the exact native
verification request and reads actual capacity and timing from the verified
scope. Use the full report once available. A 60 GiB screening result can be
used on its own. Do not submit the screening and full reports together when
they share launch scopes. Repeated `--source` arguments can combine disjoint
reports from separately verified launch series.

A future lab can provide `--evidence PATH` with `spark-cache-pareto-input/1`
from the same independently verified scope evidence. This is a normalized
receipt format, and the operator is responsible for original verification.
Use `--prepare-only PATH` on an existing report to export an exact example.
Each source carries the analysis and verifier artifact references (ID and
SHA-256), source authority, and ordered launch rows. Each launch carries role,
source commit, binary digest, requested and allocated MiB, load-to-ready
seconds, optional seed receipt, exact normalized matching fields, verified
start/stop/conditioning/kernel/protocol/log/load references and 16 indexed
request rows with result digest and greedy hashes. Capacity and role must come
from the witnessed flags, gate/profile receipt and bank allocation readback.
Stock means the native stock bank in `equivalent-stock`, and `off` is the same
candidate binary with the optional profile gate unset. No-bank stock and other
engines are reference evidence outside this capacity analysis.

Matching requires model and source-region identities, prompt manifest, profile
family, effective launch flags apart from the explicit native bank setting,
runtime settings, process scope controls, file-specific conditioning and
greedy hashes for both workloads. Each distinct verified launch contributes
five results per size. Report the observed minima, medians and maxima in
seconds and tokens per second, with sample counts. For each size, one arm
dominates another when its TTFT median is no worse and its decode median is no
worse, with at least one strict improvement. Ties remain on the front. Report
both the targeted 15/30/45 GiB set and the context of all admitted measured
native capacities. Different matched cohorts get independent fronts.

Same-budget controls must also have equal logged allocated MiB. The log has
limited decimal precision, so matching establishes equality at that precision.
For a profile-off control also require the same candidate binary. Report absent
treatments and absent stock/profile-off controls for all three target budgets.
Startup includes load-to-ready, measured profile initialization time and seed
bytes when available. Record the charged bound separately from actual bank
allocation. Startup spans can overlap, so do not add them. No scalar score,
sampling confidence interval, causal estimate, or imputation is produced.

Use the native `verify` capability to recompute the complete report from the
same evidence artifact. A passed report describes fixed launch samples. The
official stock tuner remains a separate calibration sequence.
