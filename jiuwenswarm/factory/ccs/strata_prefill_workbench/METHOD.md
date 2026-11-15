# Native prefill workbench

This package provides inspection, experiment design, profile transformation and
verification, durable submission, lifecycle reconciliation and independent result
analysis for one scoped optimization. Each capability has its own effects and
verification scope; a certificate for profile transformation does not certify
GPU execution or performance.

`design` produces a **new** `strata-prefill-scoped-v1` contract, separate from
historical benchmark v1/v2. The operator must admit its exact bytes before
`submit`. `screen` runs fresh processes in AB order. `confirm` runs ABBA. A uses
prefill chunk256; B changes only that value to512. Every process replays the same
pinned512-token prompt seven times: four warmups, then three measured requests.
Each request produces exactly one token with EOS disabled and native drafting
disabled. The single token's decode-loop time may be zero; no decode rate is
invented. All raw timings and output IDs are retained.

Frozen model inventory, tokenizer tables, image ID, source closure, full-six
experts, no prefix reuse, static expert cache, fixed placement, eight CPU threads,
104GiB memory with no extra swap, 8GiB host guard, per-cell300s timeout and a
bounded campaign deadline remain host obligations. The existing recorder owns
the GPU lease, journal, container boundary and guardian cleanup. Native chunk
startup counters must show the requested value, and all draft counters stay zero.
The result importer independently checks exact argv, mounts, environment, GPU,
raw replay, complete pipe coverage, no OOM, cleanup and sealed artifact hashes.

Correctness here requires the same single token and finish reason across all
requests and both arms. A mismatch rejects the scoped result. This is an
explicitly narrow repeatability check, **not full-generation or task quality**.
Long-form output, accuracy and overall end-to-end behavior require a separate
later integration contract.

The primary measurement is each process's median native prefill milliseconds
over its final three requests. Screen reports operational completion and a trend
only. Confirmation reports `scoped_improvement` only when all candidate process
medians are below every baseline process median and the ratio of arm medians is
at least1.05. This small-N signal does not authorize automatic promotion, a
general speedup claim or full-quality acceptance. The immutable scoped result is
stored as `scoped_prefill_result`, distinct from ordinary full benchmark results.

`VERIFICATION-UNITS.json` is an ordinary hashed material. Its
`profile-single-change` unit applies only to `apply` and `verify_profile` and is
checked independently against recorded baseline/candidate profile evidence.
Runtime evidence has separate obligations; qualification never widens grants.

The package also contains the prefill component material and an executable-job
integration skill (`INTEGRATE.md`). Evidence query/read/publication, methodology,
explicit composed profile qualification and bounded loop operations are exposed
alongside the original seven tools. Their shared implementations remain host
modules; packaging the job does not fork a recorder, worker or model runtime.
`status`/`result` refer to one prefill attempt; `loop_status`/`collect` refer to
controller cycles. Qualification applies only to the profile unit described
above, even when other capabilities are present in the same release.
