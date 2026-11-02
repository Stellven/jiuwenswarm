"""V-X1.4 part (a) (AC-015): MCP (stdio), Python client and CLI expose the same operations and give equal results and errors."""
import asyncio
import json
import re
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import fixtures as F
from simlab.interface.ops import OPERATIONS

ID = re.compile(r"\b(draft|run|att|tr|cp)-[0-9a-f]{12,24}(-\d{5})?(\.rr\d+)?\b")
TS = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+Z")
VOLATILE = {"resources", "hardware", "started_at", "ended_at", "created_at", "raw_evidence", "taken_at"}


def norm(x):
    if isinstance(x, dict):
        return {k: norm(v) for k, v in sorted(x.items()) if k not in VOLATILE}
    if isinstance(x, list):
        return [norm(v) for v in x]
    if isinstance(x, str):
        return TS.sub("<ts>", ID.sub(lambda m: m.group(1) + "-<id>", x))
    return x


def scenario(call):
    """One scripted scenario; `call(op, **params)` returns the decoded result or {'error': typed error}."""
    out = {"capability": call("capability")}
    d = call("draft_create", header=F.header())["draft_id"]
    out["model_file_put"] = call("model_file_put", draft_id=d, path="pendulum.xml", content=F.PENDULUM)
    out["procedure_put"] = call("procedure_put", draft_id=d, procedure=F.PROCEDURE)
    out["measurement_put"] = call("measurement_put", draft_id=d, measurement=F.PERIOD)
    out["observation_put"] = call("observation_put", draft_id=d, observation=F.QPOS)
    b = call("bind", draft_id=d)
    out["bind"] = b
    out["validate"] = call("validate", experiment=b["experiment"])
    s = call("submit", experiment=b["experiment"])
    out["wait"] = call("wait", run_id=s["run_id"], timeout_s=120)
    res = call("result", run_id=s["run_id"])
    out["result"] = res
    q = call("query", run_id=s["run_id"], signal="qpos:hinge", t_start=0.5, t_end=0.6)
    out["query"] = q
    out["fetch"] = call("fetch", ref=q["traces"][0]["ref"], t_start=0.5, t_end=0.6)
    out["err_status"] = call("status", run_id="run-00000000000000000000")
    out["err_bound"] = call("model_file_put", draft_id=d, path="pendulum.xml", content="<mujoco/>")
    out["err_reserved"] = call("pilot")
    return out


def py_call(client):
    from simlab.interface.client import SimlabClientError

    def call(op, **p):
        try:
            return client.call(op, **p)
        except SimlabClientError as e:
            return {"error": e.error}
    return call


def cli_call(data_dir):
    def call(op, **p):
        r = subprocess.run([sys.executable, "-m", "simlab.interface.cli", op, "--data-dir", str(data_dir), "--params", "-"],
                           input=json.dumps(p), capture_output=True, text=True, timeout=300)
        return json.loads(r.stdout)
    return call


async def mcp_scenario(data_dir):
    params = StdioServerParameters(command=sys.executable, args=["-m", "simlab.interface.cli", "mcp", "--data-dir", str(data_dir)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = sorted(t.name for t in (await session.list_tools()).tools)

            async def acall(op, **p):
                r = await session.call_tool(op, p)
                v = json.loads(r.content[0].text)
                return v
            # the same scenario as `scenario`, in async form
            out = {"capability": await acall("capability")}
            d = (await acall("draft_create", header=F.header()))["draft_id"]
            out["model_file_put"] = await acall("model_file_put", draft_id=d, path="pendulum.xml", content=F.PENDULUM)
            out["procedure_put"] = await acall("procedure_put", draft_id=d, procedure=F.PROCEDURE)
            out["measurement_put"] = await acall("measurement_put", draft_id=d, measurement=F.PERIOD)
            out["observation_put"] = await acall("observation_put", draft_id=d, observation=F.QPOS)
            b = await acall("bind", draft_id=d)
            out["bind"] = b
            out["validate"] = await acall("validate", experiment=b["experiment"])
            s = await acall("submit", experiment=b["experiment"])
            out["wait"] = await acall("wait", run_id=s["run_id"], timeout_s=120)
            out["result"] = await acall("result", run_id=s["run_id"])
            q = await acall("query", run_id=s["run_id"], signal="qpos:hinge", t_start=0.5, t_end=0.6)
            out["query"] = q
            out["fetch"] = await acall("fetch", ref=q["traces"][0]["ref"], t_start=0.5, t_end=0.6)
            out["err_status"] = await acall("status", run_id="run-00000000000000000000")
            out["err_bound"] = await acall("model_file_put", draft_id=d, path="pendulum.xml", content="<mujoco/>")
            reserved = await session.call_tool("pilot", {})
            out["err_reserved"] = json.loads(reserved.content[0].text)
            return tools, out


def test_same_operations_everywhere(service, data_dir):
    cli_ops = json.loads(subprocess.run([sys.executable, "-m", "simlab.interface.cli", "ops"], capture_output=True, text=True).stdout)
    tools, _ = asyncio.run(mcp_scenario(data_dir))
    assert sorted(cli_ops) == tools == sorted(OPERATIONS)


def test_same_results_and_errors(service, data_dir):
    a = norm(scenario(py_call(service)))
    b = norm(scenario(cli_call(data_dir)))
    _tools, c = asyncio.run(mcp_scenario(data_dir))
    c = norm(c)
    for k in a:
        assert a[k] == b[k], f"client and CLI differ on {k}"
        assert a[k] == c[k], f"client and MCP differ on {k}"
    assert a["err_status"]["error"]["code"] == "E_UNKNOWN_RUN"
    assert a["err_bound"]["error"]["code"] == "E_BOUND"
    assert a["result"]["status"] == "COMPLETED" and a["validate"] == {"findings": []}
