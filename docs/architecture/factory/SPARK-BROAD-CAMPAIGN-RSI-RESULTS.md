# Spark broad campaign: measured results and factory revision evidence

All ten admitted inference experiments completed: the original A/A, six bounded
configuration screens, an A/A on a newly built fixed-placement engine, and two
exact-output v5 screens on that new image.
No end-to-end performance gain was accepted. The best observed native decode
rate was 16.704 tokens/s with drafting, but its combined prefill-plus-decode rate
fell by about 3.91%. The fixed-placement engine established bounded repeatability;
it was not compared as a speed treatment against the old image.

The external workspace is `/home/user2/software-factory-spark-20261113`. Paths
below are relative to that workspace unless a repository path is explicit. The
proof JSONs retain child attempt IDs, exact contract hashes, execution source
hashes, native calls, decisions, cleanup outcomes and supervisor results. They
are evidence references; they do not supply new execution or promotion authority.

## Completed experiment ledger

Rates are measured output tokens divided by summed native timing for three
requests after discarding the first request in each speed process. The workload
uses 512 prompt tokens and 128 generated tokens. Combined rates include native
prefill and decode, while excluding process startup and tokenization. Each screen
has one fresh A/B pair; these are exploratory observations with no independent
confidence interval or general-quality guarantee.

| # | Task / admitted experiment | Decode A / B tokens/s | Combined B/A | Recorded result and interpretation |
| --- | --- | ---: | ---: | --- |
| 1 | `spark-broad-throughput-004`: original A/A | 14.437 / 14.403 | 1.00518 | `aa_invalid`: timings were close, but exact output repeatability failed; no treatment acceptance could follow. |
| 2 | `spark-broad-throughput-006`: Engram threads 2 → 4 | 14.459 / 14.436 | 0.97877 | `screen_no_improvement`. |
| 3 | Same parent: Engram row cache 64 → 256 MB | 14.417 / 13.868 | 0.95384 | `screen_no_improvement`. |
| 4 | Same parent: CPU threads 8 → 4 | 14.394 / 11.309 | 0.88222 | `screen_no_improvement`; a substantial observed slowdown. |
| 5 | Same parent: verified drafting none → on | 14.431 / 16.704 | 0.96092 | Decode increased about 15.75%, while combined throughput declined; `screen_no_improvement`. |
| 6 | Same parent: `DS4_AHEAD` 0 → 1 | 14.402 / 13.995 | 1.12219 | `screen_candidate` is an exploratory screen label; no confirmation, valid original A/A, causal mechanism proof or accepted gain followed. |
| 7 | Same parent: CPU threads 8 → 6 | 14.429 / 14.465 | 1.02391 | `screen_no_improvement`; below the declared 5% screen signal. |
| 8 | `spark-fixed-placement-aa-001`: new-image fixed-placement A/A | 13.929 / 13.986 | 0.99733 | `fixed_placement_aa_observed_repeatable`: exact generated tokens/finish and complete placement identities agreed across all four processes. This is an A/A check, not a speedup. |
| 9 | `spark-fixed-placement-screens-001`: fixed-placement ahead 0 → 1 | 13.989 / 13.558 | 0.96451 | `fixed_screen_diagnostic_inconclusive`: exact cross-arm tokens/finish, all placement identities and 8/8 sampled quality passed, while combined throughput declined about 3.55%. |
| 10 | `spark-fixed-placement-screens-002`: fixed-placement CPU threads 8 → 6 | 13.989 / 13.815 | 0.98652 | `fixed_screen_diagnostic_inconclusive`: all five structural/output/quality gates passed, while combined throughput declined about 1.35%. |

The six diagnostic screens deliberately retained useful negative results despite
the failed original repeatability reference. Their outcomes must not be combined
into a performance acceptance claim. The original apparent ahead result was a reason for a bounded follow-up under
corrected repeatable conditions. The completed v5 follow-up on the fixed image
observed combined B/A 0.9645124948 and lower decode throughput, despite all
structural/output/quality gates passing. It did not reproduce the earlier
positive screen signal and establishes no benefit.
Draft engagement establishes that drafting ran; acceptance ratios and decode-only
rates do not establish a useful complete-request speed improvement.

The fixed-placement A/A used eight sampled quality questions, with A/B accuracy
1.0/1.0 and no sampled per-question regression. This bounded sample does not
establish full benchmark or general semantic correctness. All 40 per-layer
placement identities and their aggregate matched across the quality and speed
processes in both arms. The combined B/A ratio was 0.9973279618 and the declared
A/A timing gate passed. Its report explicitly leaves performance acceptance
unevaluated and promotion unauthorized. Four recorder phases completed with
removed containers and quiescent state.

## Source build and validation boundaries

The fixed-placement engine is a real source change and native build:

- Source commit: `89ae0ee6123597636ef162dec826230186c00f3b`.
- Source tree: `55eb1b479a648d5211b2846302a60b6c79f2528e`.
- New image: `sha256:a431b930d26d0abb6eacbd56a970f56216367d901f514a898a2197dc9d1d3b24`.
- Native recorded build time: 166.460 seconds; base-image cache availability
  remained unknown. This interval is not the complete submit/queue/collection
  lifecycle and is not a measured inference gain.
- CPU validation log: `results/fixed-placement-full-tests.log`, reporting 945
  passed and one skipped in 140.89 seconds. CPU tests and source compilation are
  separate from the actual A/A inference evidence.

The source build receipt is `results/fixed-placement-build-result.json`; source
and dependency pins are in `results/fixed-placement-preparation.json`. The new
A/A proof names this new image/source explicitly. The original configuration
screens reused the earlier pinned image and must not be described as evaluating
this new source implementation. Likewise, the new engine's decode rates cannot
be compared directly with old-image rates to infer an optimization effect.

## Factory evidence access failure and repair

The initial diagnostic agent stopped after six screens, reporting that raw
placement and resource counters were inaccessible through collection. Host logs
existed. The defect was an evidence-access gap between a parent task's scoped
interface and its ledger-owned child results, not absence of measurements.

The repair added `inspect_evidence(cycle_id)` to throughput workbench 1.1.0 and
inference lab 1.2.0. It resolves only a collected child in the current parent's
ledger; validates task/attempt ownership, admitted template, child contract and
original collected manifest; and hashes the retained source files again. It
publishes a bounded allowlist of stdout, stderr, samples, recorder report and
pipe events as immutable host-owned parent artifacts. Existing mismatching
copies fail; historical reports are not overwritten. Generic cross-task
`evidence.read` permissions remain unchanged.

A second access gap appeared after introducing v5: the inspector's finite
adapter allowlist still covered v1 through v4 and rejected the collected v5
child with `SCOPE_DENIED`. Task `spark-fixed-placement-screens-001` stopped after
its first screen rather than bypassing scope or hiding the failure. Its sticky
stop is preserved; a separate task is being prepared for the last experiment.
The runner repaired finite v5 support and independently checked it in a
285-pass CPU validation run. Throughput workbench 1.1.1 and inference lab 1.2.1
contain the repair. An actual native Host call then verified the prior v5 child
and exposed 20 parent artifacts with `complete_verified` status; its receipt is
`fixed-screen-final-v1/prior-inspection-host-receipt.json`. The original task001
stop remains sticky. A new task002 ran the final CPU-six screen and subsequently
completed its own report review, rather than silently reopening task001.
Future adapter introductions should include a parent evidence-inspection test,
so a valid measurement cannot become inaccessible through an omitted adapter
entry.

The same inspector supports collected failed/cancelled jobs. A sealed partial
manifest produces diagnostic-only raw evidence, never a claim of complete
execution or valid scoring. If the raw manifest is gone, only already-collected
child artifacts with independently verified stored hashes can be exposed,
explicitly marked archive-only with raw source verification unavailable.

Actual inspection of `diagnostic-01-engram4` imported 20 parent artifacts and
four phase summaries. It exposed 8,959 expert slots, 6,401 CPU experts and zero
RAM experts, plus the Engram counters retained by the native engine. The receipt
is `results/lab-evidence-task006-first-cycle.json`. A report-only resumption used
the repaired interface without reserving new GPU experiments; the parent's stop
remained sticky. Subsequent report review is a separate supervisor run and is
not part of the original six-screen runtime.

The resource summaries distinguish native request timing from lifecycle counters.
Cgroup CPU usage, throttling and I/O endpoints span initialization, prefill,
decode and idle periods; they do not establish decode-causal CPU or storage cost.
Pipe-observed first tokens include buffering and earlier work. True per-request
TTFT, GPU utilization and unsampled kernel memory peaks remain unknown. These
limits also apply to the offline `broad-diagnostic-v1/analyze-resources.py` helper.

## CC cost and usable-job measurements

The table counts completed native job-wrapper spans for the named workbench
release. It excludes other direct backend tool calls, Host admission/startup and
receipt completion. Nested API spans overlap with wrapper spans and are reported
separately; they are not added to these totals.

| Workflow / release | Wrapper calls | Successful / error responses | Sum wrapper seconds |
| --- | ---: | ---: | ---: |
| Original A/A, workbench 1.0.0 | 32 | 29 / 3 | 3.913 |
| Initial six diagnostic screens, workbench 1.0.0 | 159 | 138 / 21 | 21.284 |
| Report-only evidence review, workbench 1.1.0 | 14 | 13 / 1 | 4.227 |
| Fixed-placement A/A, workbench 1.1.0 | 20 | 20 / 0 | 3.531 |
| First fixed-placement v5 screen, workbench 1.1.0 | 54 | 48 / 6 | 5.574 |
| Final fixed-placement v5 screen, workbench 1.1.1 | 38 | 37 / 1 | 5.056 |

These observations describe different workflows. They do not demonstrate that
one release reduced error rates or cost under a matched workload. In particular,
report review exercises inspection rather than six experiment submissions.
Successful API responses are not independently verified useful job outcomes.

The original A/A supervisor interval was 528.323 seconds and its worker interval
381.833 seconds. The initial six-screen supervisor interval was 3,101.572
seconds; the separate report-only supervisor interval was 218.965 seconds. The
fixed-placement A/A supervisor interval was 532.604 seconds and its worker
interval 363.962 seconds. The first fixed-placement v5 screen supervisor interval
was 615.034 seconds over two control generations, with worker interval 370.798
seconds. The v5 attempt was `1c95ea21af6549b1b725379c5e31aa75`. The final CPU-six
supervisor interval was 583.839 seconds over two control generations, with
worker interval 372.202 seconds and attempt `f72109d301124dca8f8b107899ce3e5c`. These nested intervals overlap and use distinct
boundaries. Subtraction does not identify agent reasoning time, overhead causes
or idle waiting without additional evidence.

The original three workbench input failures suggested specific material changes:
place observation summaries/citations under `record.values`, advertise the query
limit of 1–50, and explain parent/child evidence scope. Two separate qualification
inspection failures belong to backend calls outside that three-error denominator.
Only sanitized error reasons and field names are recorded here. The later child
attribution fix is forward-only: explicit execute receipts retain parent call
identity and add child task/attempt ownership. Old missing attribution stays
unknown instead of being guessed from timestamps or attempt-ID uniqueness.

## Evidence artifacts and preservation

The following files are in workspace `results/`:

- `broad-campaign-proof.json` and `broad-campaign-cc-metrics.json`: original A/A.
- `broad-diagnostic-initial-proof.json` and
  `broad-diagnostic-initial-cc-metrics.json`: preserved before report review was
  folded into the current diagnostic proof.
- `broad-diagnostic-initial-supervisor.json` and
  `broad-diagnostic-report-review-supervisor.json`: separate original and review
  intervals; the latest supervisor result must not replace the original duration.
- `broad-diagnostic-proof.json` and `broad-diagnostic-cc-metrics.json`: current
  combined diagnostic evidence, retaining `supervisor_runs` for both intervals.
- `fixed-placement-aa-proof.json` and `fixed-placement-aa-cc-metrics.json`: final
  fixed-placement A/A proof after its supervisor completed.
- `fixed-screen-proof.json` and `fixed-screen-cc-metrics.json`: the first v5
  fixed-placement screen, including its stopped supervisor and negative result.
- `fixed-screen-final-proof.json` and `fixed-screen-final-cc-metrics.json`: final
  task002 CPU-six screen after its supervisor finished, completing the ten-run
  ledger.
- `lab-evidence-task006-first-cycle.json`: actual parent-scoped raw inspection.
- `fixed-placement-build-result.json`, `fixed-placement-preparation.json` and
  `fixed-placement-full-tests.log`: source build and CPU validation evidence.

Collectors reside in `broad-diagnostic-v1/collect-proof.py` and
`fixed-placement-campaign-v1/collect-proof.py`; the v5 screen collector is
`fixed-screen-campaign-v1/collect-proof.py`, with final task002 in
`fixed-screen-final-v1/collect-proof.py`. The task001 collector keeps its original
stopped task ID explicit rather than reading a later replacement input. They use read-only SQLite
snapshots and retained spool files; they do not initialize a Store, reconcile
jobs, launch a model or rescore mutable state. Preserve the initial archives
before regenerating current summaries. A proof collects recorded facts; it does
not replace independent hash/contract verification of raw evidence.

## RSI methodology and final outcome

The completed work provides a practical revision loop across the factory rather
than one isolated speed knob: retain failed and negative experiments, identify a
repeatability mechanism, build a bounded source revision, qualify its outputs,
repair the agent's evidence interface, then inspect the resulting job evidence
under the normal scope/authority boundary.

For subsequent revisions, freeze representative workflows and expected useful
outputs before editing. Separate data preparation, package qualification, CPU
tests, native builds, real agent usage, model execution and accepted improvement.
A qualification certificate is not a model-quality or performance certificate.
Use immutable task/store snapshots for matched offline CC comparisons and retain
per-release errors, retries, actual child ownership and missing measurements.
Measure input usability and completed useful jobs alongside wrapper latency.

For engine comparisons, retain model/tokenizer/workload identities, full-expert
policy, cache/warmup protocol, quiet execution and effective configuration.
Establish repeatable outputs and stable A/A timing separately. Mechanism counters
must show that a requested treatment engaged, but engagement alone does not
establish benefit. Small sampled screens guide a next experiment; they do not
supply population noninferiority. A two-pair bootstrap interval is small-sample
descriptive evidence and should not be presented as a general confidence guarantee.
The final combined metric and correctness obligation govern the claim: faster
decode with worse complete-request throughput remains a negative result.

The final two v5 experiments are now complete. Both preserved exact cross-arm
tokens/finish and all 40 fixed-placement layer identities, passed all five
recorded structural/output/quality gates, and answered all eight sampled quality
questions correctly in each arm. Neither improved the combined primary metric.
The ahead screen returned B/A 0.9645124948; the CPU-six screen returned
0.9865244346. Their verdicts remain `fixed_screen_diagnostic_inconclusive`, with
no accepted performance or promotion claim. V5 admission was frozen and
independently qualified; its initial separate CPU validation reported 238 passing
tests, including 40 new tests, and the later evidence-access repair validation
reported 285 passes. Those checks remain separate from the real inference runs.

The final retained conclusion is ten completed experiments, a repeatable
fixed-placement baseline at approximately 14 native decode tokens/s, and no
accepted end-to-end gain. Drafting's observed 16.704 decode tokens/s remains the
highest decode rate in this campaign, with a worse combined prefill-plus-decode
rate. The factory did produce usable negative results, a bounded source build,
a verified repeatability reference and a repaired parent evidence interface.
Future improvements must demonstrate a benefit under the fixed final contract;
they cannot inherit acceptance from faster partial metrics or successful tool
responses.

## Final software verification

After all ten GPU experiments and agent reviews stopped, the complete factory
test suite passed: **1,000 passed, one skipped in 151.32 seconds**. The log is
`results/fixed-screen-final-full-tests.log`. This supersedes the earlier 945-test
run as final software validation; it does not add GPU experiments or establish
a performance improvement. No shared containers were stopped, no global packages
were installed for this campaign, and no shared Docker/model data was pruned.
