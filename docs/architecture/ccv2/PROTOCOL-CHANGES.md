# Changes to the CC protocol and runner

The schemas are unchanged from the source (`jiuwenswarm/ccv2/schemas/`). All changes are in the runner and its edges, and each came from actual use.

| # | Change | Found by | Evidence |
|---|---|---|---|
| 1 | Host child processes that are not the tool itself (`git` snapshot, `docker` helper, `docker rm`) now get `stdin=DEVNULL`. | A live `cc_call` hung under the stdio MCP server: the child inherited the MCP protocol pipe. The same call took 0.5 s directly. | Probe over stdio failed with `TimeoutError`, then passed in 0.5 s after the change; `tests/ccv2/test_agent_mcp.py` |
| 2 | Finite image calls add `--pull=never`, matching services. Preparing a release no longer allows a call to pull implicitly. | Survey of the reference code. | `ccv2.py` docker command; the real-Docker test still passes |
| 3 | A local image id (`sha256:<hex>`) is the binding for the demo image, written by `build_image.py`. The base-image digest alone does not identify the application that ran. | Running the image service. | `cc.yaml`; `artifacts/ccv2-demo/image/compute_service.inspect.json`; instance records report the same id |
| 4 | New front door `agent_mcp.py`: one MCP server over a CC folder, tools listed in `README.md`, `handles` advertised by `cc_list`, several CC folders, tool signatures preserved. | The first live run advertised wrong signatures; the agent then said no workspace handle existed. | `tests/ccv2/test_agent_mcp.py`; `sessions/01d-*.jsonl` |

## Not changed, with the reason
- **Image services need the `network.request` grant.** A published Docker bridge port cannot be combined with `--network none`, so the runner refuses a service unless egress is granted and says so. This is honest but weak: the service can reach the network. A real no-egress service needs an enforcing network provider, which this branch does not build.
- **Only `workspace` resources mount into containers.** Other kinds are refused with `UNSUPPORTED_RESOURCE`.
- **Native execution is not isolated.** The CLI requires `--trusted-local`; the MCP server runs native CCs under the operator's `--grant` list, and receipts record `assurance: trusted_local`. Treat every native CC as team-trusted code.
