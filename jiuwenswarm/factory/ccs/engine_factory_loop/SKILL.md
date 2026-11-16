# Run a bounded branch investigation

Use this package when the agent has selected a report-backed hypothesis and an operator-admitted experiment template. It owns reservation/submission/recovery, not hypothesis selection, arbitrary source admission or scientific acceptance.

For a connected investigation, create an eligible branch whose hypothesis is the exact selected hypothesis ID. Its conservative GPU-seconds allocation must cover campaign_timeout_s +120 worker seconds. This reservation bounds admitted work; it is not measured GPU utilization. Read graph/decision revisions once, then call select with branch_id and expected_graph_rev as well as the ordinary fields. Policies can require this binding. Select atomically records the branch as running and reserves the existing loop cycle. Multiple CCs can serve the branch; this package handles the experiment lifecycle as one cohesive job.

Execute the same cycle ID. End the agent turn after durable submission so the existing supervisor can quiet control and release the lab. After restart, recover the same cycle and collect. The host records the branch/cycle/child/attempt/result chain; it never converts the result to an accepted gain. Inspect raw verification and scope before deciding. The branch is a completed investigation even if the experimental result failed; refine it into a new branch for another trial.

A prune blocks fresh dispatch but cannot erase a submitted attempt. Recover and collect already-submitted work, including after deadline or pruning; its result remains linked in branch status. If selection was abandoned before submission, use abandon with a reason. It consumes the reserved cycle and refuses any existing attempt, including a lost acknowledgement. Never use a new ID to hide a retry.

Branch status exposes current host-ledger experiment_cycles separately from historical graph revisions. Caller-reported measurement fields remain unknown until explicitly supplied; a completed lab does not invent a Pareto score. Use evidence intake/projection as needed, reuse returned state, and preserve failed outcomes. stop blocks fresh dispatch globally; it does not cancel already queued lab work.

For an agent-authored experiment, use prepare_experiment with hypothesis, evidence,
changed variables, probe artifacts, argv recipe, measurements, interpretation and
explicit limits. Preparation freezes data but executes nothing. Select exactly one
experiment_id or template_id. The operator's experiment_authority supplies permitted
purposes, images, changes, owned worktrees and the independent acceptance-policy
identity. A build request must identify a clean owned source commit, dependency and
declared engine/probe target. Execute reconciles its separate durable build first;
repeat execute to dispatch the lab after verified artifact admission. Collect every
attempt, including failure. Probe tolerances never authorize engine promotion.
