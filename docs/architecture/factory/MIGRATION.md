# The software factory alongside M1

The software factory (`jiuwenswarm/factory/`, CLI `jiuwenswarm-factory`) is a second way to run research work on JiuwenSwarm, built on Capability Capsules v2. It sits next to the M1 research runtime; it does not replace or remove it. On M2 both are present: the M1 research routes and the factory routes are mounted side by side in the web gateway. The factory controller is allowed by the feature-scoped [amendment](AMENDMENT.md).

## Operational mapping

The table maps each M1 concern to its factory counterpart. Both columns are live code on M2; the factory column is what `jiuwenswarm-factory` uses.

| Concern | M1 research runtime | Software factory |
|---|---|---|
| Submit a task | Research CLI/router and compiler admission in `jiuwenswarm/channels/cli/research.py`, `jiuwenswarm/research_router/`, `jiuwenswarm/research/compiler.py` | Task/revision identity and inputs in `jiuwenswarm/factory/store.py`; `jiuwenswarm factory` CLI. |
| Choose the next action | Compiler/planner pipeline in `jiuwenswarm/research/advanced_compiler.py`, `jiuwenswarm/research/capability_planning.py`; RSI loop in `jiuwenswarm/research_rsi/` | One real JiuwenSwarm/Codex agent records observations, hypothesis, uncertainty, bounded next action, expected evidence, budget and stop condition, then invokes CCs under `jiuwenswarm/factory/ccs/`. A deterministic Manager enforces state, authority and lifecycle; it does not choose actions. |
| Find evidence | M1 records and runtime in `jiuwenswarm/research_records/`, `jiuwenswarm/capsule_runtime/`, `jiuwenswarm/research/` | Versioned decisions, runs and evidence references in `jiuwenswarm/factory/store.py`, plus CC-v2 receipts/artifacts. Historical run records remain historical evidence: never deserialize them as live tasks or implicitly resume them. |
| Track a long job | M1 executors/sidecar in `jiuwenswarm/research/admission_executor.py`, `jiuwenswarm/research_sidecar/` | Durable `bin/jobq` jobs from the bundled lab kit, wrapped by `jiuwenswarm/factory/jobs.py`, with persisted job IDs, status, logs and evidence links. Keep GPU/build work behind existing campaign jobs. Submission is not completion. |
| Revise the visible plan | M1 proposal/check/freeze in `research/planning.py`, `unified_planning.py`, serial `scheduler.py`, and Symphony graph artifacts | [Task graph](TASK-GRAPH.md): task-scoped append-only patches with graph CAS and decision lineage; proposed seed work, explicit retries/cancellation/supersession and evidence-linked states. Agent chooses revisions; controller/jobs retain execution authority. No compiler or frozen graph executor. |
| Cancel or restart | M1 pipeline/RSI lifecycle in `jiuwenswarm/research_rsi/`, `jiuwenswarm/research_sidecar/` | Manager and job wrapper reconcile durable job IDs and actual queue state. Cancellation must be confirmed by the underlying job lifecycle. Restart reconciles existing jobs before any new submission and preserves task/revision identity and evidence; it never infers completion from a vanished launcher. |
| Return results | Research router/RSI console (`jiuwenswarm/research_router/`, `jiuwenswarm/gateway/channel_manager/web/research_http.py`, `jiuwenswarm/server/rsi/rsi_handlers.py`) | CC receipts and job evidence feed the store, then the agent decides whether to iterate or return a bounded result through `jiuwenswarm factory`. The web UI's Factory runs page shows tasks, task graphs, capsules and results ([HTTP API](FACTORY-RUNS-HTTP.md)); it is optional. |

An evaluation contract never changes inside a scored comparison: a changed contract requires a new revision and comparable run set. Grants still come from operator flags, workspace and task `allowed_effects`. Replanning cannot widen them. Native CCs remain trusted local code.

## Legacy configuration errors

`jiuwenswarm/factory/migration.py` has only standard-library imports. `check_legacy_config(environ=os.environ, argv=None)` raises `LegacyConfigError` for any nonempty `JIUWENSWARM_M1_*` setting (including `JIUWENSWARM_M1_PROFILE`) or `AI4R_PILOT_BUDGET_DIRECTORY`, or an argv token `research`. Empty values pass. The message names the key or subcommand, explains that the software factory does not run under the M1 research profile, and links this guide.

Only the `jiuwenswarm-factory` CLI calls the guard, before argument parsing, and exits 2 with the message on stderr. The shared chat CLI, `start_services` and `codex_start` are not guarded, so M1 keeps working unchanged.

## Rollback

Stop and reconcile active jobs through the job lifecycle first. Then remove the factory configuration, or revert the factory commits; M1 is unaffected either way. Rollback never rewrites, deletes or reclassifies evidence: keep decisions, run records, job IDs and receipts as historical evidence, and never deserialize them as live tasks.
