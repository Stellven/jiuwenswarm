# Changes to the CC protocol and runner

The historical import documentation described unchanged source schemas. The current branch also has a local schema extension, introduced in `608656eb1`: optional `capabilities.*.kind: tool` and `materials.*.kind: component|skill|method|reference`. The runner validates these fields, discovery exposes them, and the factory component loader uses them. The table below records the earlier runner changes; it is not an exhaustive compatibility claim.

Against current `Muxite/tools` commit `b74121c712ee5378b70ad54c4997cd81563685e7`, these fields are not in the closed upstream CC v2 schema. All 48 factory declarations (40 top-level, eight nested) fail that schema; removing only those fields in memory makes all 48 structurally valid. This does not prove runtime portability. See [the source-pinned alignment review](../factory/MUXITE-CONTEXT-ALIGNMENT-2026-11-16.md) and its audit receipt.

Treat the fields as a local extension, not portable CC v2 syntax. Preserve historical sealed releases. Any canonical export or schema migration must produce new package identities and retain role information through a documented compatible representation; do not silently rewrite admitted packages. Ordinary semantic checks remain opt-in.

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

## Construction-loop canonical migration (2026-11-16)

The earlier compatibility gap is addressed for newly authored factory releases:
all 48 existing declarations now use the pinned upstream schema, with passive
`roles.json` materials replacing local capability/material `kind` fields. The
new performance-baseline package brings the total to 49. Canonical loading is
the default; historical extended releases require explicit `legacy=True` and
retain their original manifests and hashes. `factory/ccs/migration.json` records
old, initial migrated, and final release identities. The copy-only migration
utility never edits historical release directories.

`scripts/factory/check_construction_compat.py` validates against the supplied
pinned upstream checkout and executes the mixed baseline package through both
runners. Factory execution bindings remain outside the CC declaration protocol.
See [construction-loop contracts](../factory/CONSTRUCTION-LOOP.md) for backend,
runtime and selected-component provenance and the bounded live acceptance scope.
