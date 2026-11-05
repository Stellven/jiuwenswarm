# Capability Capsules v2 on JiuwenSwarm (`ai4r_ccv2`)

This branch is base JiuwenSwarm, the preserved Codex integration, and a small CC v2 runner that an agent uses through native MCP tools. The M1 research machinery (intent compiler, old capsule pipeline, RSI console, benchmarks) is removed on purpose. See `AGENTS.md`.

## What an agent gets
Eight tools from one MCP server (`python -m jiuwenswarm.ccv2.agent_mcp`):

| Tool | Does |
|---|---|
| `cc_list` | Scan CC folders; list capabilities (finite or service), materials, handles, errors |
| `cc_describe` / `cc_material` | Read a declaration / a passive material (grants no authority) |
| `cc_call` | Run a finite capability, return a receipt; same `key` replays, never reruns |
| `cc_start` / `cc_instance` / `cc_stop` | Run a served capability (native or image), read it, stop it with confirmation |
| `cc_artifact` | Register a local file as an artifact |

Authority comes only from the operator's `--grant` flags and `--workspace`. The model cannot widen them.

## Install
Windows or Linux, Python 3.11 to 3.13, Docker (for the image CC), a ChatGPT account for Codex.
```
uv venv .venv --python 3.12
uv pip install -p .venv/Scripts/python.exe -e . rfc8785 psutil pyyaml jsonschema pywin32 "openai-codex-cli-bin==0.163.0" pytest
```
`openjiuwen` is pinned in `pyproject.toml`. If the git dependency is unreachable, point the venv at an existing site-packages that has it.

## Run the demonstrations
```
python demo/run_agent.py login        # once: copy ~/.codex/auth.json into the app profile, or sign in through the printed URL
python demo/run_agent.py status       # expect state "ready"
python demo/ccs/compute_service/build_image.py   # builds the image, pins its local id into cc.yaml
python demo/run_agent.py run demo/prompts/01_discover_and_inspect.md   --name 01
python demo/run_agent.py run demo/prompts/02_image_service_and_client.md --name 02
python demo/run_agent.py run demo/prompts/03_build_from_request.md      --name 03 --build
```
The agent workspace is `~/.jiuwenswarm-ccv2/agent-workspace` (override with `CCV2_DEMO_HOME`). Put the `sample/` data and `requests/` there as in the prompts. Transcripts go to `artifacts/ccv2-demo/sessions/`.

The driver sets `JIUWENSWARM_CODEX_AGENT=1`. That opts the Codex profile into a `workspace-write` sandbox (Windows: Codex `unelevated` sandbox), shell and patch tools, and the CC MCP server. Without it the profile stays text-only, as before.

## Tests
```
pytest tests/ccv2 --no-cov                                   # runner, demos, MCP over stdio, real Docker
pytest tests/unit_tests/runtime/test_codex_subscription.py tests/unit_tests/runtime/test_codex_integration.py tests/unit_tests/runtime/test_codex_agent_mode.py --no-cov
```
Live agent runs are separate evidence from these tests.

## Layout
- `jiuwenswarm/ccv2/` runner (`ccv2.py` host, `applications.py` services, `schemas/`) and `agent_mcp.py`
- `demo/ccs/` workspace_inspect (native), compute_service (image), service_client (native), methodology (passive)
- `demo/requests/` request CC for a service that does not exist yet
- `artifacts/ccv2-demo/` evidence and `SUMMARY.md`
