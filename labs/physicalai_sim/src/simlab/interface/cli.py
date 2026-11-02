"""simlab command line (PAS-M1-001 B09; PRD SL-9.D).

    simlab serve                         run the runner service (JSON-RPC on <data dir>/runner.sock)
    simlab mcp                           MCP server over stdio (a client of the service)
    simlab <operation> [--params JSON | --params-file FILE | --params -]
    simlab ops                           list operations
    simlab doctor [--json]               environment readiness with typed failures
    simlab bench ...                     SIMLAB-Bench (run, report, speed, admit)
    simlab compute-log append ...        one row per run in compute-log.csv
    simlab schema [--write]              exported IF-001@r1 JSON Schema drift check

Operations take the same parameters as the Python client and MCP tools and
print the same JSON. A typed error prints {"error": {...}} and exits 1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _params(args) -> dict:
    if args.params_file:
        return json.loads(open(args.params_file).read())
    if args.params == "-":
        return json.loads(sys.stdin.read())
    if args.params:
        return json.loads(args.params)
    return {}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in {"-h", "--help", "help"}:
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "serve":
        ap = argparse.ArgumentParser(prog="simlab serve")
        ap.add_argument("--data-dir")
        a = ap.parse_args(rest)
        from simlab.interface.rpc import serve
        return serve(a.data_dir)
    if cmd == "mcp":
        ap = argparse.ArgumentParser(prog="simlab mcp")
        ap.add_argument("--data-dir")
        a = ap.parse_args(rest)
        from simlab.interface.mcp_server import main as m
        return m(a.data_dir)
    if cmd == "doctor":
        from simlab.doctor import main as m
        return m(rest)
    if cmd == "bench":
        from simlab.bench.cli import main as m
        return m(rest)
    if cmd == "compute-log":
        from simlab.resources import compute_log_main
        return compute_log_main(rest)
    if cmd == "feasibility-sim":
        from simlab.feasibility_sim import main as m
        return m(rest)
    if cmd == "build-identity":
        from simlab.build_identity import main as m
        return m(rest)
    if cmd == "schema":
        from simlab import schemas
        if "--write" in rest:
            for p in schemas.write():
                print(p)
            return 0
        d = schemas.drift()
        print(json.dumps({"drift": d}))
        return 1 if d else 0
    from simlab.interface.ops import OPERATIONS, RESERVED
    if cmd == "ops":
        print(json.dumps({k: {"doc": v["doc"], "params": sorted(v["params"]), "required": v["required"]} for k, v in OPERATIONS.items()},
                         indent=1, sort_keys=True))
        return 0
    op = cmd.replace("-", "_")
    if op not in OPERATIONS and op not in RESERVED:
        print(json.dumps({"error": {"code": "E_UNKNOWN_OPERATION", "message": f"no operation {cmd!r}", "path": "", "severity": "error"}}))
        return 1
    ap = argparse.ArgumentParser(prog=f"simlab {cmd}")
    ap.add_argument("--params", help="JSON object of parameters, or - for stdin")
    ap.add_argument("--params-file")
    ap.add_argument("--data-dir", default=os.environ.get("SIMLAB_DATA_DIR"))
    a = ap.parse_args(rest)
    from simlab.interface.client import Client, SimlabClientError
    try:
        params = _params(a)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": {"code": "E_INVALID_INPUT", "message": f"parameters are not JSON: {e}", "path": "", "severity": "error"}}))
        return 1
    try:
        out = Client(a.data_dir).call(op, **params)
    except SimlabClientError as e:
        print(json.dumps({"error": e.error}, sort_keys=True))
        return 1
    except (FileNotFoundError, ConnectionRefusedError) as e:
        print(json.dumps({"error": {"code": "E_INTERNAL", "message": f"no SIMLAB service at the data directory ({e}); start `simlab serve`",
                                    "path": "", "severity": "error"}}))
        return 1
    print(json.dumps(out, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
