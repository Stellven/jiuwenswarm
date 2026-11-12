# M1 to the iterative software factory (uses CCs)

This is a substantial AI4Research runtime redesign using CC-v2. The old M1 control model does not remain. The donor is `2889a1d6342e9baa7721648eca196bbce79a31d4`, descended from AI4Research-Main `141c1c401138f916af0a41aca791adf226d814c7`. See [LINEAGE.md](LINEAGE.md) for the removal inventory and the completed local hunk review, and [AMENDMENT.md](AMENDMENT.md) for the controller exception.

The operator-authorized change from frozen execution to in-run revision is recorded in
[DESIGN-CHANGE-2026-11-12.md](DESIGN-CHANGE-2026-11-12.md).
[RESPONSIBILITIES.md](RESPONSIBILITIES.md) gives the M1 → factory responsibility and source map.
Run 5 evidence IDs are placeholders for the operator to fill from actual recovery records.

## Operational mapping

Old paths below are historical source paths at `141c1c40`, not imports or compatibility entry points. New paths describe the implemented native factory. Attempt 2 provides a recorded real-agent build/admission/lab chain; see the [completion report](../../../artifacts/factory/COMPLETION-REPORT.md) for scoped evidence and remaining acceptance gaps.

| Concern | Old M1 model (removed paths) | New factory model |
|---|---|---|
| Submit a task | Research CLI/router and compiler admission in `jiuwenswarm/channels/cli/research.py`, `jiuwenswarm/research_router/`, `jiuwenswarm/research/compiler.py` | Task/revision identity and inputs in `jiuwenswarm/factory/store.py`; `jiuwenswarm factory` CLI. Do not submit using `research`. |
| Choose the next action | Compiler/planner pipeline in `jiuwenswarm/research/advanced_compiler.py`, `jiuwenswarm/research/capability_planning.py`; RSI loop in `jiuwenswarm/research_rsi/` | One real JiuwenSwarm/Codex agent records observations, hypothesis, uncertainty, bounded next action, expected evidence, budget and stop condition, then invokes CCs under `jiuwenswarm/factory/ccs/`. A deterministic Manager enforces state, authority and lifecycle; it does not choose actions. |
| Find evidence | M1 records and runtime in `jiuwenswarm/research_records/`, `jiuwenswarm/capsule_runtime/`, `jiuwenswarm/research/` | Versioned decisions, runs and evidence references in `jiuwenswarm/factory/store.py`, plus CC-v2 receipts/artifacts. Historical run records remain historical evidence: never deserialize them as live tasks or implicitly resume them. |
| Track a long job | M1 executors/sidecar in `jiuwenswarm/research/admission_executor.py`, `jiuwenswarm/research_sidecar/` | Durable siminfeng `bin/jobq` jobs, wrapped by `jiuwenswarm/factory/jobs.py`, with persisted job IDs, status, logs and evidence links. Keep GPU/build work behind existing campaign jobs. Submission is not completion. |
| Revise the visible plan | M1 proposal/check/freeze in `research/planning.py`, `unified_planning.py`, serial `scheduler.py`, and Symphony graph artifacts | [Task graph](TASK-GRAPH.md): task-scoped append-only patches with graph CAS and decision lineage; proposed seed work, explicit retries/cancellation/supersession and evidence-linked states. Agent chooses revisions; controller/jobs retain execution authority. No compiler or frozen graph executor. |
| Cancel or restart | M1 pipeline/RSI lifecycle in `jiuwenswarm/research_rsi/`, `jiuwenswarm/research_sidecar/` | Manager and job wrapper reconcile durable job IDs and actual queue state. Cancellation must be confirmed by the underlying job lifecycle. Restart reconciles existing jobs before any new submission and preserves task/revision identity and evidence; it never infers completion from a vanished launcher. |
| Return results | Research router/RSI console (`jiuwenswarm/research_router/`, `jiuwenswarm/gateway/channel_manager/web/research_http.py`, `jiuwenswarm/server/rsi/rsi_handlers.py`) | CC receipts and job evidence feed the store, then the agent decides whether to iterate or return a bounded result through `jiuwenswarm factory`. No RSI console or factory web UI is required. |

An evaluation contract never changes inside a scored comparison: a changed contract requires a new revision and comparable run set. Grants still come from operator flags, workspace and task `allowed_effects`. Replanning cannot widen them. Native CCs remain trusted local code.

## Legacy configuration errors

`jiuwenswarm/factory/migration.py` has only standard-library imports. `check_legacy_config(environ=os.environ, argv=None)` raises `LegacyConfigError` for any nonempty `JIUWENSWARM_M1_*` setting (including `JIUWENSWARM_M1_PROFILE`) or `AI4R_PILOT_BUDGET_DIRECTORY`, or an argv token `research`. Empty values pass. Messages identify the key/subcommand, explain that the M1 pipeline was removed on this branch, and link this guide.

The start-services module checks before dotenv and heavyweight imports; the Codex and root CLI main functions check before argument parsing or service/profile setup. These boundaries print the message to stderr and exit 2. The guard examines the environment present at that point: it does not scan arbitrary dotenv/config files or historical evidence. Remove legacy keys from shell/service environments and dotenv files rather than renaming them to invented factory equivalents. Residual TUI TypeScript M1 reads are recorded in LINEAGE.md; direct TUI execution is not covered by these three Python guards.

## Rollback

Stop/reconcile active jobs through the actual lifecycle before rolling back code. Restore revision `2889a1d6` using the operator's normal checkout/deployment procedure, or remove factory configuration to return to the base CC-v2 workflow. No rollback rewrites, deletes, or reclassifies evidence. Keep decisions, run records, job IDs and receipts as historical evidence; never deserialize them as live tasks. Rolling back the factory does not restore M1.

## Local install and ports

Use the [Linux/aarch64 install block](../ccv2/README.md#install), including Codex 0.163.0, without `pywin32`. The frontend code default is 5173 (`jiuwenswarm/channels/web/app_web.py`), but the handoff/AGENTS local hosting rule is 5175 (`FRONTEND_PORT=5175`). The factory needs no web UI.
