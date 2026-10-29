# Ungated native diagnostic

This diagnostic uses `openjiuwen.core.single_agent.agents.react_agent.ReActAgent`
and its native tool-call/session loop. Its authorized completion callback is
the only model transport. Each completion must return strict JSON selecting one
caller-allowlisted action with schema-valid arguments; the adapter maps that
choice to OpenJiuwen's native `ToolCall`. Calls do not retry, tools do not run
in parallel, and hard local ceilings cap model and tool calls. The result
contains the case ID, raw model emissions, dispatched tool traces and explicit
`diagnostic_only` / `product_accepted: false` markers.

This is **not** a raw JiuwenSwarm upstream comparison. The source pinned for
potential later comparison is
[`openJiuwen-ai/jiuwenswarm` at `aa8489799f2e62eae89ef608b7ec1676ede47ad7`](https://github.com/openJiuwen-ai/jiuwenswarm/tree/aa8489799f2e62eae89ef608b7ec1676ede47ad7),
whose declared OpenJiuwen core dependency is
`0ab5913b250d565b35bff3828dae438939cb1acd`. We inspected the pinned source but
did not execute its application harness. The native diagnostic directly uses
the OpenJiuwen ReActAgent API and intentionally imports no JiuwenSwarm harness,
adapter, tool, or policy code.

The raw upstream run has not been executed. Within this timebox, the pinned
JiuwenSwarm harness was not bootstrapped and configured through the authorized
completion callback with the same bounded tools and captured inputs. The small
strict-action adapter supports bounded diagnostics while preserving the native
OpenJiuwen ReAct loop, but it does not reproduce upstream JiuwenSwarm
configuration, provider resolution, or product harness behavior. Any report
from this path is an informal bug-finding artifact only. It must not be
submitted to ordinary Benchmark acceptance or treated as a qualification,
pass-rate, or raw-upstream result.

The Docker verify image used for this diagnostic pins OpenJiuwen core at
`9e3390195a9ea15235b2b5f7412cb2aa440622cc`; the pinned upstream JiuwenSwarm
checkout declares a different core revision (`0ab5913b250d565b35bff3828dae438939cb1acd`).

The callable entry point is
`jiuwenswarm.research_sidecar.native_diagnostic.run_native_diagnostic`. The
caller supplies a stable `case_id`, the already-captured task, explicit tool
schemas and dispatcher, the exact selected model name, and the existing
authorized budgeted `model_call(prompt, system)` callback. No service, API key,
or model endpoint is created by this diagnostic module.
