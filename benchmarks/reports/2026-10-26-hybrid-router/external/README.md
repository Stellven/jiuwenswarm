# External presentation package — Hybrid v5

Open `benchmark-report.html` directly, or read `benchmark-report.md` with its
local figures. Both reports are in English. No web server is required.

## Data included

- `data/originals/{chatgpt,v5}/`: 48 original public input requests, 48 original
  worker answers and eight original campaign metadata files (104 total).
  Their byte-for-byte SHA-256 values and source paths are in `manifest.json`.
- `data/measurements.json`: the 48-observation worker-performance projection,
  with offline correctness flags, model choices, role usage, timing and native
  proof summaries. Only Hybrid v5 and the all-ChatGPT reference are included.
- `data/receipt-projections.json`: captured model-call records and worker route
  decisions, explicitly extracted from fuller receipts. Source receipt hashes
  are retained. These are not complete diagnostic receipts.
- `data/observations.csv`: flat metrics; `data/runtime.json`: environment snapshot.
- `SHA256SUMS.txt`: package-file integrity hashes.

The complete internal dataset, diagnostic verdicts, reviewer answer file,
credentials and native authentication material are not in this package.
Offline correctness was scored against the frozen reviewer criteria; that
reviewer-only file is not distributed here, so the bundle cannot independently
recompute gold-answer correctness without authorized access to those criteria.

Token totals include all calls actually made in each arm. Subscription/local
tokenizers and wrapper overhead differ; token reductions are not dollar savings.
Worker-answer accuracy is not an end-to-end delivery success rate. The results
come from eight public development fixtures repeated three times, not held-out
or universal task evaluation. The measured 12.5-point accuracy gap is retained.
