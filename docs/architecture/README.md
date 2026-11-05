# Architecture: JiuwenSwarm + Capability Capsules v2 (`ai4r_ccv2`)

## What this branch is for
A reduced JiuwenSwarm in which a real agent discovers, reads and uses Capability Capsules (CCs) through a small runner. Base JiuwenSwarm and the Codex-as-model integration are kept. The earlier AI4Research M1 machinery (intent compiler, old capsule pipeline, RSI console, benchmarks, its design package) was removed on purpose and is not documented here. It remains in git history and on `AI4Research-Main`.

## How the pieces fit
```
Codex (model, ChatGPT login)        jiuwenswarm/server/runtime/codex_subscription/
        |  agent mode (opt-in: JIUWENSWARM_CODEX_AGENT=1; workspace-write sandbox, shell + patch)
        v
JiuwenSwarm agent  --MCP stdio-->   jiuwenswarm/ccv2/agent_mcp.py   (8 tools: cc_list, cc_describe,
                                    cc_material, cc_artifact, cc_call, cc_start, cc_instance, cc_stop)
                                         |
                                         v
                                    jiuwenswarm/ccv2/ccv2.py   Host: prepare, call, start, stop, receipts
                                         |                      applications.py: image services (docker CLI)
                          +--------------+--------------+
                          v                             v
                 native binding                  image binding
                 process, JSON on stdin/out      docker run, pinned local image id, --pull=never
```
- **Authority** comes only from operator flags (`--grant`, `--workspace`, `--allow-built`). The model cannot widen it.
- **Native CCs** are cheap local clients and inspectors and are not sandboxed. **Image CCs** carry an application with its own OS and runtime and are started, probed and stopped by the host.
- **Passive materials** (methodology, ontology) are readable and grant nothing. A **request CC** states a desired service and is not callable; the agent builds the implementation, which becomes an ordinary CC.

## Where things are
| Topic | Location |
|---|---|
| Install, run, tests | [ccv2/README.md](ccv2/README.md) |
| Base and source revisions | [ccv2/PROVENANCE.md](ccv2/PROVENANCE.md) |
| Protocol and runner changes, with evidence | [ccv2/PROTOCOL-CHANGES.md](ccv2/PROTOCOL-CHANGES.md) |
| Runner and agent front door | `jiuwenswarm/ccv2/` (schemas in `jiuwenswarm/ccv2/schemas/`) |
| Demonstration CCs and request | `demo/ccs/`, `demo/requests/`, driver `demo/run_agent.py`, prompts `demo/prompts/` |
| Live agent evidence, receipts, limitations, keep/remove/change, delegation | `artifacts/ccv2-demo/SUMMARY.md` |
| Tests | `tests/ccv2/`, `tests/unit_tests/runtime/test_codex_agent_mode.py` |

## Rules for changing this branch
See `AGENTS.md`. In short: do not restore the removed M1 packages, keep the protocol lightweight (no registry, planner or compiler), and keep live-agent evidence separate from tests.
