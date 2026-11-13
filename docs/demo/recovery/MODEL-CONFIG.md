# 20261113 Effective Agent Model Configuration prepresentation

## JiuwenSwarm coding agent: GPT-6.1 Sol

- **Supported identifier:** `gpt-6.1-sol` (display name GPT-6.1-Sol). It is listed in both the factory's Codex model cache (client 0.163.0) and the operator CLI cache (0.167.0).
- **Transport:** the factory runs its own pinned Codex. `jiuwenswarm/server/runtime/codex_subscription/transport.py` requires `openai-codex-cli-bin==0.163.0` and launches `app-server --listen stdio://` with `CODEX_HOME=~/.jiuwenswarm-factory/agent-data/subscription/codex-home`. It never reads `~/.codex`. `jiuwenswarm/server/runtime/codex_subscription/service.py` sets `allowProviderModelFallback: false` on thread start.
- **Reasoning effort:** taken from `JIUWENSWARM_CODEX_AGENT_EFFORT`. The transport writes it into its generated config, and any other edit to that config is rejected (`PROFILE_CONFIG_CONFLICT`).
- **Recorded effective values** are from that profile's `state_5.sqlite` `threads` table, read-only, on 13 Nov:

| Task | What it is | Threads | Model | Effort | Codex |
|---|---|---|---|---|---|
| `factory-e5b8d4b7…` | Fresh 32-token fill-only recording | 3 (02:47–03:40) | `gpt-6.1-sol` | medium | 0.163.0 |
| `factory-bd173c08…` | Run 4, source of the J-OM13 headline image `bd173c08-restored-0b514fba` | 1 | `gpt-6.1-sol` | unset (transport default) | 0.163.0 |
| All 13 factory threads | 12–13 Nov | 13 | `gpt-6.1-sol` | unset / medium / one max | 0.163.0 |

- **New this continuation:** jiuwenswarm `factory/controller.py` passes `codex_model` when `JIUWENSWARM_CODEX_MODEL` is set (for example `gpt-6.1-sol`). When the variable is unset, behaviour is unchanged.
  - The value travels through the existing `interface_codex.py` → `service.stream(..., model)` path into `thread/start` and `turn/start`.
  - Test: `tests/factory/test_telemetry.py::test_turn_agent_model_is_explicit_only_when_configured`.
  - The transport pin and the generated config were not touched.
  - No new factory run was made to demonstrate it, and the historical run metadata is unchanged.

## Advisor: GPT-6 Astra

- **Supported identifier:** `gpt-6-astra` (display name GPT-6-Astra).
- **How it was used:** only through the separate operator CLI, `codex exec -m gpt-6-astra --sandbox read-only`, with codex-cli 0.167.0 and `~/.codex`. It was never used through the factory profile, so the factory transport and its single-app-server lock are unaffected.
- **Role:** bounded adversarial review questions with the evidence attached. It owned no implementation.
- **Records:** prompts and replies are under `reviews/`.
