import pytest

from jiuwenswarm.research.native import NativePlanner


@pytest.mark.asyncio
@pytest.mark.filterwarnings('ignore:invalid escape sequence:SyntaxWarning')
async def test_actual_native_leader_harness_uses_one_governed_text_call():
    from openjiuwen.core.common.logging.log_config import configure_log_config
    configure_log_config({'backend':'default','log_path':'/tmp/ai4r-native-verify/logs','output':['console']})
    calls=[]
    async def invoke(prompt,system=None):
        calls.append((prompt,system))
        return 'INFEASIBLE: the frozen catalog has no matching capability'
    result=await NativePlanner().propose({'brief_ref':{'id':'brief','sha256':'a'*64}},invoke=invoke,instructions='Return a bounded data-only proposal or INFEASIBLE line. No tools.')
    assert result.startswith('INFEASIBLE:') and len(calls)==1
