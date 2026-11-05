# Task A1: remove retired research coupling from 6 files (constant-fold the M1 profile to OFF)

Repo: this worktree (branch ai4r_ccv2). The packages jiuwenswarm/research*, jiuwenswarm/capsule_runtime and jiuwenswarm/server/rsi, plus gateway/channel_manager/web/research_http.py and channels/cli/research.py, were ALREADY DELETED on purpose. Several retained files still import them or branch on `M1_PROFILE` (a mode flag that DISABLED base features). Behaviour must become what it is when M1_PROFILE is False / JIUWENSWARM_M1_PROFILE is unset: base JiuwenSwarm.

## You may edit ONLY these files (under jiuwenswarm/):
1. start_services.py   (remove `from jiuwenswarm.research.native_profile import M1_PROFILE`; dedent the `if not M1_PROFILE:` block; delete the `if M1_PROFILE:` branch in main())
2. gateway/app_gateway.py   (M1_PROFILE, native_channel_config, attach_native_research, create_gateway_ports)
3. server/app_agentserver.py   (M1_PROFILE, M1_REFUSAL_REASON, native_logging, start_native_capture/stop_native_capture, start_agent_ports)
4. server/front/router.py   (the JIUWENSWARM_M1_PROFILE / research.local_chat / ResearchError block)
5. gateway/channel_manager/web/web_connect.py   (the `research_profile` block calling research_http.native_research_message + ResearchError, around line 1557)
6. server/agent_ws_server.py   (the `from jiuwenswarm.server.rsi import RsiAgentServerHandlers` block near line 11663 and anything that depends on it)

## Rules
- Fold `M1_PROFILE` to False: `if not M1_PROFILE:` bodies stay (dedented), `if M1_PROFILE:` bodies are deleted, `X and not M1_PROFILE` -> X, `M1_PROFILE or Y` -> Y.
- KEEP everything about Codex: the `JIUWENSWARM_AGENT_SDK == "codex_subscription"` paths, CodexAccountAdapter, codex.auth.* handling. e.g. `if M1_PROFILE or os.environ.get("JIUWENSWARM_AGENT_SDK") == "codex_subscription":` becomes `if os.environ.get("JIUWENSWARM_AGENT_SDK") == "codex_subscription":`.
- Remove now-unused variables/helpers that only served the deleted features, but do not refactor anything else. Preserve line endings and unrelated code. No new features.
- Do not touch any other file. Do not run git commit/push/checkout/stash.

## Done when (run these and report output)
- `grep -nE "M1_PROFILE|M1_REFUSAL|jiuwenswarm\.(research|capsule_runtime)|server\.rsi|research_http|native_ports|native_profile|native_logging" <the 6 files>` prints nothing.
- `python -m py_compile` on each of the 6 files succeeds.
- Final report: per file, one line on what was removed; list anything you were unsure about and left alone. If blocked, stop and say why.
