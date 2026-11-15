# Agent-chosen branch exploration

`factory.branch_workbench` records alternative hypotheses in the existing task graph. It does not choose, schedule or execute them. Each branch can reference multiple CC capabilities, and the JiuwenSwarm agent calls admitted CCs normally before attaching their actual evidence. See the [package skill](../../../jiuwenswarm/factory/ccs/branch_workbench/SKILL.md) and [method](../../../jiuwenswarm/factory/ccs/branch_workbench/METHOD.md).

The nine capabilities are `create`, `fork`, `refine`, `attach`, `record`, `prune`, `status`, `ready` and `compare`. All mutations use the shared graph revision CAS, an existing decision revision and an idempotency key. Alternative forks have parent lineage without an execution dependency; refinement creates a continuation depending on the completed parent. Hypotheses, lineage, capability references and resource allocations cannot be rewritten; prior failures and evidence remain in immutable patch history.

Operator constraints use `constraints.branch_workbench` with `max_branches`, `cpu_seconds` and `gpu_seconds`. Defaults are eight branches, 60 CPU seconds and zero GPU seconds. Allocations accumulate across every branch, including pruned alternatives, and ordinary taskgraph patches enforce the same limits. Reservations confer no effects or execution authority.

`attach` finishes a qualitative investigation without inventing metrics. `record` links a current-task observation containing an explicitly scoped reported measurement. `compare` groups identical comparison keys and scope, maximizes throughput and quality, and minimizes peak memory. Incomplete vectors remain unknown. Historical measurements on a pruned branch remain visible and comparable: pruning is a work decision, not erasure of evidence. Caller-published measurements remain reported claims; the workbench never grants scientific acceptance or promotion.

The independently launchable [mission script](../../../scripts/factory_branch_mission.py) freezes a fresh source/runtime snapshot, only the selected CPU packages, a task, input artifact hashes and a manifest. It can then run the real JiuwenSwarm Controller through the existing Codex subscription integration, with model identity and token usage retained. Private authentication is linked only for the run and removed afterward. It performs no GPU benchmark and does not reuse a prior task's budget.

```bash
PYTHONPATH=/path/to/dependencies:. /path/to/factory-python scripts/factory_branch_mission.py --root /path/to/fresh-mission --engine-evidence /path/to/manual/run-001/analysis.json freeze
/path/to/factory-python /path/to/fresh-mission/launch.py --root /path/to/fresh-mission verify
/path/to/factory-python /path/to/fresh-mission/launch.py --root /path/to/fresh-mission run
```

Freeze after the manual round and all selected packages are final. Inspect the concrete task and manifest before launch. The mission uses an existing local subscription auth file by default, configurable with `--auth`; no credential contents enter reports. Its live evidence files distinguish actual native receipt outputs, operator manual evidence, package historical fixtures and remaining unknowns.

Offline verification is `pytest -o addopts='' tests/factory/test_branch_workbench.py tests/factory/test_taskgraph.py`. Those tests include actual native Host prepare/call and durable restart checks, but they are not a live agent mission or engine measurements.

The current overnight mission launcher admits only its explicit CPU package/capability allowlist. It removes memory `native_experiment` from the frozen declaration and records both declaration hashes; no package source is altered. No GPU capsule is discoverable. The operator deadline is 2026-11-15 08:00 UTC: starting requires at least ten minutes plus cleanup margin, the outer run timeout leaves 30 seconds for cleanup, and subscription shutdown is bounded. The task and report retain that deadline.

Pass repeatable `--extra-evidence FILE` at freeze to include later long-prefill analysis or factory overhead evidence without changing the primary round. Up to eight regular files of at most 2 MiB each are read with a no-follow file descriptor, checked for changes during reading, copied as `inputs/extra-N-basename`, hashed in the manifest/task and imported as separate operator evidence. The mission prompt requires reading extras while preserving workload and scope differences.
