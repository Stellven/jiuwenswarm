# Native throughput campaign

The task supplies the frozen workload, baseline image, fixed expert placement,
target gain, allowable candidate knobs and total GPU process allowance. Neither
an agent nor a workflow may change that judge. Search and read experiment history
before choosing an intervention. Retain rejected hypotheses and failed work.

Use native workflow leaves for submit/status/result/cancel. Start with request
`{"stage":"aa"}`. Each process executes an unscored warmup and one measured
request. Collect the independent result before revising the workflow.

After a valid fresh A/A, request `stage: screen` with `environment` and/or
`arguments` maps containing only operator-admitted values. A source candidate may
also supply `build_attempt_id` from a successful same-task builder workflow;
the host resolves and verifies its exact image. Do not supply an image yourself.
Source builds must preserve numerical semantics, model weights, expert count,
placement and the measurement implementation. Never optimize by altering logs,
token output, timers, the workload or the judge.

Only a positive screen admits `stage: confirm` with the exact same candidate.
Confirmation runs A-B-B-A in fresh processes. All raw outputs/finish reasons and
fixed placements must agree, baseline timing must stay within its frozen spread,
and even the slowest candidate process versus the fastest baseline must meet the
target. Report measured tokens/s and gains, including negative results. A failed
execution is inconclusive; it must never become a speedup. No automatic promotion.

One graph tick is one bounded host call. After submission, end the agent turn
while the shared queue owns GPU work. On resumption tick the same graph to collect
the job result, record the evidence in the factory store, and append a justified
workflow revision. Do not dispatch another scheduler or fabricate a plan after
execution. A target that cannot be met within the budget is a valid honest report.
