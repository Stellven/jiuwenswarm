# Durable engine factory cycles

The existing controller agent chooses the hypothesis and bounded experiment. This CC
reserves budgets, records decisions and enforces execution admission. The
existing mission supervisor owns agent restarts, stopped-control proof, quiet
barriers and worker reconciliation. No additional scheduler runs.

Operator task constraints must contain `factory_loop` with positive integer
`max_cycles`, `max_experiments`, `wall_clock_s`, and `templates`: a list of
`{id, path, sha256, allowed_hypothesis_ids}` objects. Paths name complete frozen
contracts; SHA256 pins their exact bytes. allowed_hypothesis_ids explicitly
binds each template to hypotheses it can test. For template selection, the
template is the complete admitted treatment envelope; select accepts no
parameter overrides.

Alternatively, `factory_loop.experiment_authority` can authorize agent-authored
experiments, with `templates` left empty. The operator envelope admits purposes,
immutable runtime images, permitted changed variables, resource limits, optional
pinned model identity, owned build worktrees and build/GPU attempt allowances.
It also pins the independent acceptance-policy identity. An execution binding
is required and verifies the selected release, frozen backend and runtime
dependencies. The agent chooses experiments within this authority from retained
evidence; neither a template nor a fixed source/build/GPU sequence is required.

Template contracts use the supported standard benchmark adapters or the separately
scoped `strata-prefill-scoped-v1` workbench. Agent-authored experiments use
`factory-experiment-v1`. Their existing host adapters validate and execute their
distinct obligations. The scoped workbench tests native prefill
with fixed prompt, warmups, one output token and full-six expert operation.
Exact first-token agreement and a qualified prefill signal do not establish
full-generation semantic quality, decode speed or default-promotion authority.

When the task also contains `constraints.cc_qualification`, complete the
operator's required package verification policies before selecting work. Inspect
the sealed release, retain the requested configuration evidence, verify its
bounded units and assess admission through factory.cc_qualification. select
reassesses saved certificates under the current package, module, API, checker
and evidence identities; a saved eligible label alone is insufficient. These
configuration checks qualify only the selected package capabilities. Frozen
runtime contracts and result verification still govern experimental claims.

Use the evidence and inference-lab CCs to inspect reports and identify the
appropriate claim scope. For a template, call `select` with a unique cycle_id,
1..20 evidence_ids, a report-backed methodology hypothesis_id, an admitted
template_id and the current decision expected_rev.

For an authored experiment, first call `prepare_experiment` with a unique
experiment_id, admitted image and specification: hypothesis, evidence_ids,
purpose, changed_variables, text probe artifacts, argv recipe, measurements,
interpretation and explicit resource budget. An optional build identifies a
clean owned source commit, pinned dependency and declared build target.
Preparation freezes the specification and build identity without submitting a
build or lab job. Then select that experiment_id instead of template_id, keeping
evidence_ids and hypothesis_id exactly equal to the prepared evidence_ids and
hypothesis text. Supply the current expected_rev. Select exactly one prepared
experiment or admitted template; selection atomically records the decision and
reserves one cycle.

Call `execute` with the same cycle_id. When a build is attached, execute first
submits or reconciles the existing durable Builder job. After the build ends,
repeat execute to admit its verified receipt and immutable image before lab
submission. Native Spark compilation uses committed source/dependency snapshots
and the admitted toolchain; a caller-supplied image or success flag cannot replace
the build receipt. A failed build closes the cycle with retained failure evidence
and no lab launch. Once ready, the host freezes the child contract into a Store
artifact, creates a separate child task and submits through the adapter and Jobs
using a deterministic key. The parent authority stays pinned. Each child retains
its contract and evidence; authored children also bind the actual runtime image
and any build receipt to their execution binding.

After build or lab submission, END THE TURN immediately naming the durable attempt. Do not
poll or sleep within the model turn. The supervisor proves the whole controller
container stopped before releasing the child worker's quiet barrier. On resume,
recover status, call `collect`, inspect the original child result and followup,
and decide again. If collection reports pending work, end the turn again. The
followup is a proposal; it does not choose or launch the next experiment.

Execution never implies a pass. Retain failed and null episodes. Full combined
validation compares directly against the original baseline; individual gains
cannot be multiplied. Different contracts do not form one scored run set.

Replay uses the same cycle_id and selection fields. A crash around queue
acknowledgement recovers the existing child and Jobs key; budgets remain spent.
Stop/deadline prevents fresh submissions. Collection and reconciliation remain
available after exhaustion. Stop records intent; existing lab cancellation
handles active work. New cycle IDs must not hide retries or reset budgets.
Native CCs are trusted local code, not an OS isolation boundary.

When authorized, source edits and local commits remain agent actions inside the
isolated owned checkout. The agent can attach their clean commit to an authored
experiment's native build, or choose a diagnostic without a build. After each
collected result, choose the next bounded action from its evidence and remaining
authority. Neither package qualification nor loop execution promotes an engine
change automatically. Authored diagnostics do not authorize promotion or change
the independent acceptance policy.

Connected branch mode adds optional paired select inputs branch_id and expected_graph_rev.
Set factory_loop.require_branch_binding=true to require them. The branch hypothesis
is the selected methodology hypothesis ID, and its GPU reservation covers the
contract campaign timeout plus 120 worker seconds. Selection marks the branch
running atomically; collection attaches the result and completes the investigation
without accepting its scientific claim. Pruned branches stay pruned and retain
late results in the host cycle ledger. See SKILL.md for recovery and abandon.
