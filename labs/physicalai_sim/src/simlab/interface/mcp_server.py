"""SIMLAB MCP server over stdio (PAS-M1-001 B09; PRD SL-9.D; `mcp` 2.3.0 low-level API).

Every operation in OPERATIONS is one MCP tool with the same name, inputs,
outputs and typed errors as the Python client and the CLI. The server is a
thin client of the runner service; it holds no state of its own.

    simlab mcp            # inside the container: docker exec -i simlab-runner simlab mcp
"""
from __future__ import annotations

import json

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from simlab.interface.client import Client, SimlabClientError
from simlab.interface.ops import OPERATIONS

INSTRUCTIONS = (
    "SIMLAB builds and runs physics experiments (MuJoCo). Typical flow: draft_create -> model_file_put (MJCF) -> "
    "procedure_put / measurement_put / observation_put (and component_put for controllers) -> bind -> validate -> submit -> "
    "wait -> result / query / fetch. Errors are typed {code, message, path}. SIMLAB records and reports; it never judges results."
)


def tools() -> list[types.Tool]:
    out = []
    for name, spec in sorted(OPERATIONS.items()):
        schema = {"type": "object", "properties": spec["params"], "required": spec["required"], "additionalProperties": False}
        out.append(types.Tool(name=name, description=spec["doc"], input_schema=schema))
    return out


def build(client: Client) -> Server:
    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=tools())

    async def call_tool(ctx, params: types.CallToolRequestParams):
        args = dict(params.arguments or {})
        try:
            value = await anyio.to_thread.run_sync(lambda: client.call(params.name, **args))
            text = json.dumps(value, sort_keys=True, default=str)
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=False)
        except SimlabClientError as e:
            text = json.dumps({"error": e.error}, sort_keys=True)
            return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=True)

    return Server("simlab", version="0.1.0", instructions=INSTRUCTIONS, on_list_tools=list_tools, on_call_tool=call_tool)


async def _main(client: Client) -> None:
    server = build(client)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main(data_dir: str | None = None) -> int:
    anyio.run(_main, Client(data_dir))
    return 0
