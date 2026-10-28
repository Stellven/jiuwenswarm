# capsule_runtime: use capability capsules from any harness

A small runtime that loads Capability Capsules outside the AI4Research pipeline and
keeps their guarantees. It imports nothing from `runner.py`, `scheduler.py`, the run
store or executor RPC. (The capsules themselves import `packet.py`, which imports
`ProducedArtifact` from `runner.py`; that is a data class, nothing runs.)

```
python -m jiuwenswarm.capsule_runtime list
python -m jiuwenswarm.capsule_runtime describe utility.calculate
python -m jiuwenswarm.capsule_runtime admit utility.calculate
python -m jiuwenswarm.capsule_runtime invoke utility.calculate --inputs in.json --out receipt.json
python -m jiuwenswarm.capsule_runtime.mcp          # MCP server over stdio
```

```python
from jiuwenswarm.capsule_runtime import Runtime
rt = Runtime()                                    # or Runtime([extra_dir], worker_model=...)
rt.admit('utility.calculate')
result = rt.invoke('utility.calculate', {'packet': packet})
# {'status': 'delivered', 'outputs': {...}, 'receipt': {...}}
# {'status': 'halted', 'halt': {'stage', 'code', 'reason'}, 'receipt': {...}}   (never any outputs)
```

## What travels with a capsule

| Guarantee | How it holds here | Halt stage |
|---|---|---|
| **Pins** | `release.json` hashes every source file of the capsule, `packet.py` and shared dependencies. A byte that differs refuses the capsule at load, with the file named. The pins are rehashed on every call. Uses `catalog._verify_current_pins` and SHA-256 of file bytes, as `release_tool` writes them. | `pin` |
| **Admission** | `invoke` refuses a capsule not admitted in this process (`require_admission=False` waives it, explicitly). | `pin` (`not_admitted`) |
| **Input guard** | Inputs are checked against the declared ports: required and unknown ports, the port's contract schema, and `validate_packet` for packets. | `input_guard` |
| **Declared limits** | The declared wall time is enforced (a pure worker runs in a daemon thread, so the limit fires even for CPU-bound code). Declared model-call count is enforced. Output ports must match the declaration and their schemas. | `worker` |
| **Capsule checks** | The capsule's own `checks.py` runs on (inputs, outputs). Every declared acceptance check must be present and PASS. A failed verifier never returns outputs. | `verifier` |
| **Trace / packet review** | `checks/trace.py check_trace` runs if an output port named `trace` carries a manifest; `checks/packet_review.py review` runs on science review packets. No shipped capability capsule emits either, so both report `not_applicable`. | `trace` |
| **Semantic verifier** | Only for capsules whose declaration carries semantic checks or declares a model dependency (today: `research.generalist`). Same code as the product: `gate.SemanticVerifier` builds the prompt from the capsule's pinned profile instructions and criteria plus the declaration and exact output bytes only (never inputs, traces or the request, D20), `assemble_assessment` parses the reply, `checks/verifier.verifier_predicates` recomputes the mechanical predicates. Delivered only if every criterion is PASS and every predicate holds. | `semantic_verifier` |
| **Receipt** | Capsule id and version, release hash, declaration hash, input and output SHA-256, check verdicts, which verifier stages applied and why, declared effects, every model call (provider kind, model, SHA-256 of prompt, system and reply, tokens if known), timestamps, and `verifier_independent`. | |

Receipt example for a deterministic capsule:
`verifiers: {deterministic: pass, trace: not_applicable (...), packet_review: not_applicable (...), semantic: not_applicable (deterministic capsule)}`.
With a model capsule and no verifier model: `semantic: not_run (no model configured)`. This is never reported as a pass.
`require_semantic=True` (`--require-semantic`) halts instead of delivering unreviewed.

### Which verifier stages run
The declaration decides. `guarantees.checks[].kind` is `deterministic` or `semantic`; a capsule that lists a
`semantic` check, or declares `needs.injects` (a model), gets the semantic stage. The product has no per-capsule
switch beyond this (its checking profile always lists criteria), so the rule is the declaration's own. Deterministic
capsules (`calculate*`, `table_normalize*`, `markdown_report*`, `packet_report`, `summary_to_packet`) get checks.py,
trace and packet review only. `describe` and the MCP tool description list the stages.

### Models
Capsules that use a model call `await ctx.model(prompt, system=...) -> str`. The runtime supplies it from, in order:

1. Python: `invoke(..., worker_model=async callable(prompt, system=None) -> str)`.
2. A server-configured backend: `--worker-cmd "codex exec ..."` (prompt on stdin, reply on stdout) or
   `--worker-openai-base-url URL --worker-model NAME` (any OpenAI-compatible endpoint; key from `OPENAI_API_KEY`).
3. MCP sampling: if the MCP client declares the `sampling` capability, `ctx.model` sends `sampling/createMessage`
   to the client, so the capsule uses the calling harness's model.

With none of these, the capsule halts at stage `worker`, code `no_model`. Whatever the model, the gate enforces the
declared call limit (default one call, since declarations carry no explicit model-call field), requires a text reply,
and takes the system text only from the capsule (the caller cannot change the pinned instructions).
The semantic verifier model is a separate setting (`verifier_model=callable(prompt)->text`, `--verifier-cmd`,
`--verifier-openai-base-url/--verifier-model`). If it resolves to the same backend as the worker, the receipt says
`verifier_independent: false`.

### Admission
The protected admission executor needs the run store, a root broker and a Linux sandbox, and no shipped declaration
lists `self_tests`. `admit` therefore runs in-process cases (`admission.py`): pins and declaration load; no unrun
declared self-tests (if a capsule declares any, it is not admitted here); positive cases deliver; generic input-guard
cases halt at `input_guard`; capsule-specific bad inputs halt at `worker`; and the verifier rejects an altered copy of
each delivered output (a data change and a trust change; deterministic capsules must reject both). Model capsules are
admitted against a canned reply, which tests the guards and verifier, not the model. Admission is process-local and is
not the AI4R library admission.

## What stays in AI4R
The run store and custody, the scheduler and plans, the protected executor and sandbox, the gates and the decision
records, calibration, and the pipeline-stage capsules (Intent through Delivery). Those stages read and write host refs
through `ctx.store`, `ctx.read_blob`, `ctx.input_ref`, `ctx.executor` and `ctx.connectors`, which this runtime does not
provide. See the survey in the hand-off report for what each would need.

## Register the MCP server

The server admits every loaded capsule at startup and serves one tool per capability. The tool name is the capability id,
the input schema comes from the declared ports, the description is the summary plus the guarantees and verifier stages.
Model capsules take an extra `task_objective` argument and are listed only when a worker backend is configured or the
client supports sampling. The result is the invoke result as JSON text; `isError` is true for a halt.

**JiuwenSwarm.** MCP servers are `mcp.servers` entries in `config.yaml` (template at `jiuwenswarm/resources/config.yaml:1494`),
read by `jiuwenswarm/common/config.py:2546` (`get_mcp_servers`, merged with `mcp/state.json`) and `:2593`, converted to a runtime
config by `jiuwenswarm/common/mcp_config.py:107` (`build_mcp_server_config`, stdio branch `:141`) and registered at
`jiuwenswarm/server/runtime/agent_adapter/interface_deep.py:5245`:

```yaml
mcp:
  servers:
    - name: capsules
      enabled: true
      transport: stdio
      command: python
      args: ["-m", "jiuwenswarm.capsule_runtime.mcp"]
      cwd: /path/to/jiuwenswarm-agentic
      env:
        PYTHONPATH: /path/to/jiuwenswarm-agentic
```

**Claude Code** (sampling is supported by the protocol; whether your build forwards it is client-dependent, so give the server a backend too if in doubt):

```
claude mcp add capsules --env PYTHONPATH=/path/to/jiuwenswarm-agentic -- python -m jiuwenswarm.capsule_runtime.mcp
# with a worker and a separate verifier model:
claude mcp add capsules -- python -m jiuwenswarm.capsule_runtime.mcp \
    --worker-openai-base-url http://localhost:8000/v1 --worker-model my-worker \
    --verifier-cmd "codex exec -"
```

**Codex** (`~/.codex/config.toml`):

```toml
[mcp_servers.capsules]
command = "python"
args = ["-m", "jiuwenswarm.capsule_runtime.mcp", "--require-semantic", "--verifier-cmd", "codex exec -"]
env = { PYTHONPATH = "/path/to/jiuwenswarm-agentic" }
```

## Risks and limits
- The time limit abandons a runaway worker thread; it cannot kill it. A model-backed worker stays on the caller's event
  loop, so its limit only fires if the worker awaits.
- Pins check bytes on disk at load and at each call, but Python may load a stale `.pyc` whose source mtime and size were
  forged. Treat the host filesystem as trusted; use read-only installs.
- Extra directories must follow the built-in layout (`release.json`, `release.py`, `worker.py`, `checks.py`, a sibling
  `packet.py`). They are mounted as a child package of `jiuwenswarm.research`, so relative imports like `...contracts` resolve.
- The MCP server is hand written JSON-RPC, not the `mcp` SDK, because the repo locks mcp 1.29 while hosts may carry 2.x, whose server API differs.
- Semantic review quality is the model's. A mechanical predicate failure or malformed reply halts, but a wrong PASS from the model passes.
- The generalist's own checks do not detect arbitrary extra keys in `data` (free-form by design); admission records this per capsule.
- `check_trace` and `packet_review` have no producer among today's capability capsules; the stages are wired and unit-checked only.

Tests: `python -m pytest tests/unit_tests/capsule_runtime -q -p no:cacheprovider`.
