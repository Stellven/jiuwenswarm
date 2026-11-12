# Factory controller (offline implementation; live operation is separate)

`jiuwenswarm factory` and `jiuwenswarm-factory` share the same CLI. Help, init,
status, show and cancel do not start a model. Run/resume use the real
JiuWenSwarm facade with the Codex subscription agent profile.

## Operator task

Schema: `jiuwenswarm/factory/schemas/task.schema.json`.
Example: `jiuwenswarm/factory/tasks/demo-qwen36.json`.

Required fields: objective (text), constraints (object/list), allowed_effects
(grant strings), target (text/object), budget (positive max_turns and
wall_clock_s), contract_id, initial_run_config (object), component_cc, source
(subpath relative to agent-workspace and pre_integration_commit).
Optional task_id defaults to a generated ID. Optional operator_labels is an
object passed verbatim alongside the first-turn objective. The example uses
J-OM11 pg8 environment with LLAMA_EXPERT_PREGATE_K="48", explicitly labeled
controlled-invalid. Neither init nor the host loop repairs operator settings.

## Live operator procedure

These commands start real services/jobs and are **not** part of the offline unit
tests. Set FACTORY_SOURCE_REPO to an existing local llama.cpp repository that
contains e14b87603, the component's pre-integration revision. The ordinary
siminfeng/ref/llama.cpp checkout is not assumed to contain that revision.
Keep the reference repository read-only; clone into the owned workspace.

```bash
cd /home/muk/projects/jiuwenswarm
export FACTORY_HOME="$PWD/artifacts/factory-demo"
export FACTORY_SOURCE_REPO=/absolute/path/to/local/llama.cpp-with-e14b87603
mkdir -p "$FACTORY_HOME/agent-workspace" "$FACTORY_HOME/agent-data/subscription/codex-home"
cp -n "$HOME/.codex/auth.json" "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
chmod 600 "$FACTORY_HOME/agent-data/subscription/codex-home/auth.json"
git -C "$FACTORY_SOURCE_REPO" rev-parse --verify 'e14b87603^{commit}'
git clone --local --no-hardlinks "$FACTORY_SOURCE_REPO" "$FACTORY_HOME/agent-workspace/llama.cpp"
git -C "$FACTORY_HOME/agent-workspace/llama.cpp" checkout --detach e14b87603
.venv/bin/jiuwenswarm-factory auth-status
# If that profile needs sign-in, use: .venv/bin/jiuwenswarm-factory login
FACTORY_DEMO_TASK=$(.venv/bin/jiuwenswarm-factory init jiuwenswarm/factory/tasks/demo-qwen36.json)
printf '%s\n' "$FACTORY_DEMO_TASK" > "$FACTORY_HOME/demo-task-id"
.venv/bin/jiuwenswarm-factory run "$FACTORY_DEMO_TASK" \
  --grant process.exec --grant workspace.read --grant workspace.write --grant gpu.use
.venv/bin/jiuwenswarm-factory status "$FACTORY_DEMO_TASK" --json
.venv/bin/jiuwenswarm-factory show "$FACTORY_DEMO_TASK"
```

The existing durable campaign jobq worker must be available for submitted work;
Docker/group access, Jetson toolchain, model/prompt/reference-image prerequisites
belong to the operator. No worker, Docker/GPU run or reference freeze is launched
by init/configure. The current example permits local commits only in the owned checkout and forbids
push/publication. The agent must stop with bounded evidence if integration/build
requires authority or prerequisites it lacks.
A scored accept also requires a frozen reference under qwen36-greedy-v1; the
agent must never edit/freeze the contract itself.

After a controller restart, use the saved task ID and repeat the operator grants:

```bash
FACTORY_DEMO_TASK=$(cat "$FACTORY_HOME/demo-task-id")
.venv/bin/jiuwenswarm-factory resume "$FACTORY_DEMO_TASK" \
  --grant process.exec --grant workspace.read --grant workspace.write --grant gpu.use
# In another terminal, to record cancellation intent for active attempts:
.venv/bin/jiuwenswarm-factory cancel "$FACTORY_DEMO_TASK"
```

Resume reconciles attempts before model calls. Completed same-account Codex
agent threads resume by task/session ID; interrupted or uncertain-delivery
threads are rejected rather than replayed. Budgets persist across restarts and
cannot be reset by resume. Exhaustion produces partial with pending attempts and
questions; it does not cancel running jobs or imply a pass. Grant defaults are
empty, and effective grants are always task allowed_effects intersect CLI flags.

Transcripts append scrubbed events (including tool calls/results) to
`FACTORY_HOME/sessions/<task_id>.jsonl`. Host progress is in the adjacent
`.state.json`; evidence stays in Store at FACTORY_HOME. MCP configuration lives
outside the agent workspace, with data in agent-data and CC receipts in ccstore.
