# ai4r_ccv2 demonstration summary (2026-11-05)

Base `141c1c401`, CC source `89893083`; see `docs/ccv2/PROVENANCE.md`. Reproduce with `docs/ccv2/README.md`.

## Live agent evidence
A real JiuwenSwarm agent (the `JiuWenSwarm` facade, `codex_subscription` backend, Codex as the model on a ChatGPT login) used CCs through the `cc` MCP server. Logs in `sessions/` are the raw event streams, credentials scrubbed. Sessions that failed first are kept (`01`, `01b`, `01c`, `03`) because they show the defects that were fixed.

| Session | What the agent did | Observed result |
|---|---|---|
| `01d-discover-inspect` | `cc_list`, read passive `method`, `cc_describe`, native `workspace_inspect` | 4 CCs listed usable; receipt `succeeded/complete`; 2 files, `.csv`/`.json`, keys and columns reported correctly |
| `02-image-service-client` | `cc_start` the **image** service, `benchmark` with the returned handle, replayed the same key, `cc_stop` | `running/ready` from image `sha256:ec5b1df2…`; values `[2,4,6,8,10]`; service reported Debian 13 (the image, not the Windows host); replay returned the earlier receipt (attempt 1); `stopped`; no `cc-app` containers left |
| `03b-build-from-request` | Read the request CC, wrote a native CC with Codex shell/patch tools, re-listed, started it, benchmarked it via the client CC, stopped it | request not callable before; built CC listed usable; `[2,4,8]→[4,8,16]`; `stopped`. Built package kept in `ccs-built/`; I re-ran it with my own host and got the same values |

Native arm: `workspace_inspect`, `service_client`, the built `compute_service_native`. Image arm: `compute_service`. Roles: native tools are cheap local clients and inspectors; the image carries an application with its own OS and Python (the service reported `Debian GNU/Linux 13` while the host is Windows).

## Tests
- `tests/ccv2`: 81 vendored runner tests, 15 demo-CC tests (including real Docker start, ready, request, stop, no leftover), 4 MCP tests over real stdio.
- Codex: 41 retained base tests plus 5 agent-mode tests (the default text-only profile still rejects tool activity).
- Run commands are in `docs/ccv2/README.md`. Test results are not evidence of live agent behaviour; the sessions above are.

## Keep / remove / change
- **Kept:** base JiuwenSwarm (agents, gateway, channels, symphony, observability, instance_manager, jiuwenbox, packages, plugins), Codex subscription service/transport/adapters, `codex_start`, their tests and the web UI.
- **Removed:** `research*`, `capsule_runtime`, `server/rsi`, the intent compiler and its assets, ccbench and harbor benchmarks, `deploy/m1`, about 480 tests and fixtures that imported them, and all `M1_PROFILE` branches in startup, gateway, agent server, CLI and web channel.
- **Changed:** Codex service no longer imports `research.pilot_budget`; opt-in agent profile (`JIUWENSWARM_CODEX_AGENT=1`); `AGENTS.md` replaced by the branch purpose. Original is in git history.
- **Added:** `jiuwenswarm/ccv2/`, `demo/`, `docs/ccv2/`, tests above.

## Known limitations
- Image services need the `network.request` grant (a published port cannot be no-egress). Native CCs are not sandboxed.
- Synthetic timings are loopback client timings, not inference TTFT or token rate. No Muse/Strata, weights, GPU or Incus was touched.
- Agent mode is opt-in and Codex-only; the `approval_policy=never` agent profile relies on Codex's own `workspace-write` sandbox (Windows `unelevated`) plus pre-approved CC tools. The model can run any command that sandbox allows.
- The Windows run used host credentials copied from `~/.codex/auth.json` into the app-owned profile. Evaluators use their own login.
- `gateway/app_gateway`, the web UI and other base features were only import-checked, not exercised, on this branch. The wider base test suite was not run.
- Single run per session; the agent's wording varies between runs.

## Delegation
Codex children (`codex exec`, one at a time, briefs in `.ccv2-delegation/`): A1 strip hooks (first brief did nothing: read repo docs instead of editing; rewritten tighter, second run edited six files, verified by grep and compile), E1 write demo CCs (wrote them; could not reach Docker from its sandbox, so I built the image and ran its Docker test myself). A cheap Haiku watcher audited the strip commit (no out-of-scope deletions; flagged leftover `M1` references, which I removed).
