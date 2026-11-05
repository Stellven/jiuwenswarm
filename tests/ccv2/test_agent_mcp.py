"""The agent-facing MCP catalog, exercised over a real stdio MCP session."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]
CCS = ROOT / "demo" / "ccs"


def payload(result):
    if result.structuredContent is not None:
        return result.structuredContent.get("result", result.structuredContent)
    return json.loads(result.content[0].text)


class AgentMcpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Path(self.tmp.name) / "ws"
        (self.workspace / "sample").mkdir(parents=True)
        (self.workspace / "sample" / "study.json").write_text('{"a": 1, "b": [1]}', encoding="utf-8")
        (self.workspace / "sample" / "m.csv").write_text("id,x\n1,2\n", encoding="utf-8")

    def params(self, grants=("process.exec", "workspace.read")):
        args = ["-m", "jiuwenswarm.ccv2.agent_mcp", "--ccs", str(CCS), "--store", str(Path(self.tmp.name) / "store"),
                "--workspace", str(self.workspace)]
        for grant in grants:
            args += ["--grant", grant]
        return StdioServerParameters(command=sys.executable, args=args, env={**os.environ, "PYTHONPATH": str(ROOT)})

    async def test_tool_signatures_are_the_real_ones(self):
        async with stdio_client(self.params()) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name: t.inputSchema for t in (await session.list_tools()).tools}
        self.assertEqual(set(tools), {"cc_list", "cc_describe", "cc_material", "cc_artifact", "cc_call",
                                      "cc_start", "cc_instance", "cc_stop"})
        self.assertEqual(tools["cc_list"].get("properties", {}), {})
        self.assertEqual(set(tools["cc_call"]["required"]), {"cc", "capability"})

    async def test_discover_read_and_call(self):
        async with stdio_client(self.params()) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            listing = payload(await session.call_tool("cc_list", {}))["ccs"]
            by_id = {e["cc"]: e for e in listing if e.get("usable")}
            self.assertGreaterEqual(set(by_id), {"demo.workspace_inspect", "demo.compute_service",
                                                 "demo.service_client", "demo.methodology"})
            self.assertEqual(by_id["demo.compute_service"]["capabilities"]["api"]["kind"], "service")
            self.assertEqual(by_id["demo.compute_service"]["capabilities"]["api"]["binding"], "image")
            self.assertEqual(by_id["demo.methodology"]["callable"], [])

            material = payload(await session.call_tool("cc_material", {"cc": "demo.methodology", "material": "method"}))
            self.assertIn("Reading this grants no execution authority", material["authority"])
            self.assertTrue(material["text"].strip())

            receipt = payload(await session.call_tool("cc_call", {
                "cc": "demo.workspace_inspect", "capability": "inspect", "inputs": {"workspace": "workspace"}}))
            self.assertEqual(receipt["state"], "succeeded", receipt)
            self.assertEqual(receipt["outputs"]["report"]["file_count"], 2)

    async def test_denied_effect_and_unknown_cc_are_errors_not_successes(self):
        async with stdio_client(self.params(grants=())) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            denied = payload(await session.call_tool("cc_call", {
                "cc": "demo.workspace_inspect", "capability": "inspect", "inputs": {"workspace": "workspace"}}))
            self.assertNotEqual(denied.get("state"), "succeeded", denied)
            unknown = payload(await session.call_tool("cc_call", {"cc": "nope.nope", "capability": "x"}))
            self.assertEqual(unknown["error"]["code"], "UNKNOWN_CC")

    async def test_passive_material_cannot_be_called(self):
        async with stdio_client(self.params()) as (read, write), ClientSession(read, write) as session:
            await session.initialize()
            result = payload(await session.call_tool("cc_call", {"cc": "demo.methodology", "capability": "method"}))
            self.assertTrue("error" in result or result.get("state") != "succeeded", result)


if __name__ == "__main__":
    unittest.main()
