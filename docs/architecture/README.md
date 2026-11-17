# Architecture: evolved M1 inference engine software factory

Start with the [current CC workflow and RSI design](factory/20261117%20CC%20Workflow%20RSI%20Design%20Review%20prepresentation.md). The system evolves the relevant M1 research, decision, execution and evidence responsibilities; it does not require restoring the old POC workflow. CCv2 replaces the earlier capsule design and dynamic workflows supply reusable composition.

Historical branch context: [Jetson branch record](factory/20261113%20Jetson%20Software%20Factory%20Branch%20Record%20postpresentation.md) for current scope, results and limitations. The CC v2 architecture below is the foundation; the factory extension is described at the end.

See also the [full CC catalog and lab integration guide](factory/20261113%20CC%20Catalog%20and%20Lab%20Integration%20postpresentation.md).

## What this branch is for
The current application is an inference-engine software factory evolved from M1. It retains the relevant research objectives, bounded decisions, dependency checks, durable jobs and evidence responsibilities in the current factory modules. The obsolete POC workflow and old capsule execution path were removed. CCv2 provides functional packages, reusable subworkflows connect their capabilities, dynamic workflows compose procedures, and the RSI controller chooses evidence-led improvements. Base JiuwenSwarm and Codex model integration remain. Historical implementation files remain in Git; restoring them is not a prerequisite for this architecture.

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

## Iterative inference factory
The factory updates M1 responsibilities for inference engineering using CCv2 and dynamic workflow composition; the obsolete POC control path is not active. A real agent makes revisable, evidence-driven decisions while the host enforces authority, durable identity and job lifecycle. The feature-scoped [amendment](factory/AMENDMENT.md) permits this controller without restoring the removed compiler or pipeline. See [migration](factory/MIGRATION.md) for behavior and implementation status, and [lineage](factory/LINEAGE.md) for donor inventory and review limitations. The factory can execute through the CLI and native agent front door. Its operator console and read-only design review run on port 5175. The frontend code defaults to 5173 in `jiuwenswarm/channels/web/app_web.py`; the handoff and `AGENTS.md` require 5175 for local hosting, so configure `FRONTEND_PORT=5175` if using that frontend.

Current Spark availability and operator steps: [November 16 experiment handoff](<factory/20261116 Spark Experiment Handoff prepresentation.md>). The console/worker/build daemon were deliberately stopped, with code and evidence retained.
