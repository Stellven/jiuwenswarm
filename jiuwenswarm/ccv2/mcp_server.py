"""Generate MCP tools from one sealed CC. Run in the pinned experiment environment."""
import argparse
import asyncio
from copy import deepcopy
import json
import uuid

from .ccv2 import CCError, Host, port, callable_entries


def tool_schema(capability, defs):
    properties, required = {}, []
    for name, definition in capability['takes'].items():
        p = port(definition, defs)
        if p['kind'] == 'text':
            schema = {'type': 'string'}
        elif p['kind'] == 'artifact':
            schema = {'type': 'object', 'properties': {'uri': {'type': 'string'}, 'sha256': {'type': 'string'}}, 'required': ['uri', 'sha256']}
        elif p['kind'] == 'handle':
            schema = {'type': 'string', 'description': 'Host-issued resource handle'}
        else:
            schema = {}
        constraint = deepcopy(p.get('schema', {}))
        if isinstance(constraint, bool):
            if constraint is False:
                schema = {'allOf': [schema, False]}
        else:
            schema.update(constraint)
        if p.get('description'):
            schema['description'] = p['description']
        properties[name] = schema
        if not p['optional']:
            required.append(name)
    # _cc_key is adapter-owned metadata. It is not a model-authored port.
    return {'type': 'object', 'properties': properties, 'required': required}


async def invoke_tool(client, name, arguments, invocation_id):
    """Host adapter: bind identity before the native client's retry boundary."""
    if '_cc_key' in arguments:
        raise CCError('RESERVED_ARGUMENT', '_cc_key is host-owned; it is not a capability argument')
    if not isinstance(invocation_id, str) or not invocation_id:
        raise CCError('INVALID_KEY', 'Host invocation identity is required')
    return await client.call_tool(name, dict(arguments, _cc_key=invocation_id))


async def serve(store, release, grants=(), resources=None):
    import mcp.types as types
    from mcp.server.lowlevel import Server
    from mcp.server.stdio import stdio_server
    host = Host(store, resources=resources, session_grants=grants)
    declaration, _ = host.release(release)

    def tools():
        return [types.Tool(name=name, description=cap['does'] + (' Permitted effects: ' + ', '.join(cap['changes']) if cap['changes'] else ''),
                           inputSchema=tool_schema(cap, declaration['defs'])) for name, cap in callable_entries(declaration).items()]

    async def dispatch(name, arguments):
        values = dict(arguments or {})
        key = values.pop('_cc_key', None) or str(uuid.uuid4())
        try:
            receipt = await asyncio.to_thread(host.call, release, name, values, key=key)
            return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps(receipt))], structuredContent=receipt,
                                        isError=receipt['state'] in {'failed', 'blocked', 'unknown'})
        except CCError as e:
            return types.CallToolResult(content=[types.TextContent(type='text', text=json.dumps({'error': e.record()}))], isError=True)

    if hasattr(Server, 'call_tool'):
        server = Server('cc-v2')

        @server.list_tools()
        async def list_tools():
            return tools()

        @server.call_tool(validate_input=False)
        async def call_tool(name, arguments):
            return await dispatch(name, arguments)
    else:
        async def list_tools(context, params):
            return types.ListToolsResult(tools=tools())

        async def call_tool(context, params):
            return await dispatch(params.name, params.arguments)

        server = Server('cc-v2', on_list_tools=list_tools, on_call_tool=call_tool)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--store', required=True)
    parser.add_argument('--release', required=True)
    parser.add_argument('--grant', action='append', default=[])
    parser.add_argument('--resources')
    args = parser.parse_args()
    resources = None
    if args.resources:
        from pathlib import Path
        resources = json.loads(Path(args.resources).read_text(encoding='utf-8'))
    asyncio.run(serve(args.store, args.release, args.grant, resources))
