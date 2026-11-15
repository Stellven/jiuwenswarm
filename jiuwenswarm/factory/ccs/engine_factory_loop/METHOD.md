# Durable engine factory cycles, first draft

The existing controller agent chooses the hypothesis and template. This CC
reserves budgets, records decisions and enforces execution admission. The
existing mission supervisor owns agent restarts, stopped-control proof, quiet
barriers and worker reconciliation. No additional scheduler runs.

Operator task constraints must contain `factory_loop` with positive integer
`max_cycles`, `max_experiments`, `wall_clock_s`, and `templates`: a list of
`{id, path, sha256, allowed_hypothesis_ids}` objects. Paths name complete frozen
contracts; SHA256 pins their exact bytes. allowed_hypothesis_ids explicitly
binds each template to hypotheses it can test. The template is the complete
admitted treatment envelope. Parameter overrides are unavailable; another
workload or intervention requires another explicitly admitted template.

Supported contracts are standard benchmark v1/v2 and the separately scoped
`strata-prefill-scoped-v1` workbench. Their existing host adapters validate and
execute their distinct obligations. The scoped workbench tests native prefill
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
appropriate claim scope. Call `select` with a unique cycle_id, 1..20 evidence_ids,
a report-backed methodology hypothesis_id, an admitted template_id and the
current decision expected_rev. select atomically records the decision and
reserves one cycle. Then call `execute` with cycle_id. The host freezes the exact
template content into a Store artifact, creates a separate child task and
submits through the adapter and Jobs using a deterministic key. The parent
contract remains pinned. Each child retains its own gates and evidence.

After submission, END THE TURN immediately naming the durable attempt. Do not
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

This draft supports admitted contracts and durable evidence-driven cycles.
Source changes and builds remain separate agent actions through existing
component/builder/lab capabilities when explicitly authorized. Neither package
qualification nor loop execution promotes an engine change automatically.
