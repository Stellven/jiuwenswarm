"""Actual pinned app-server configuration; no login or model request is made."""
import pytest

from jiuwenswarm.server.runtime.codex_subscription.transport import AppServerTransport


@pytest.mark.asyncio
async def test_packaged_codex_effective_profile_has_no_agent_tools(tmp_path):
    pytest.importorskip('codex_cli_bin')
    transport=AppServerTransport(tmp_path)
    try:
        await transport.start()
        result=await transport.request('config/read',{'includeLayers':False})
        features=result['config']['features']
        for name in ['shell_tool','unified_exec','multi_agent','browser_use','computer_use',
                     'code_mode_host','apps','plugins','skill_search','image_generation',
                     'sleep_tool','goals','hooks','workspace_dependencies','unbounded_connection_retries']:
            assert features[name] is False,name
    finally:
        await transport.close()
