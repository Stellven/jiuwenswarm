import pytest

from jiuwenswarm.research.native import run_native_workflow


@pytest.mark.asyncio
@pytest.mark.filterwarnings('ignore:invalid escape sequence:SyntaxWarning')
async def test_native_serial_order_and_failed_dispatch_is_never_retried():
    from openjiuwen.core.common.logging.log_config import configure_log_config
    configure_log_config({'backend':'default','log_path':'/tmp/ai4r-native-verify/logs','output':['console']})
    seen=[]
    async def dispatch(node):
        seen.append(node)
        if node=='failed':raise RuntimeError('actual controlled failure')
        return {'node':node}
    with pytest.raises(RuntimeError,match='actual controlled failure'):
        await run_native_workflow(['first','failed','later'],dispatch,run_id='native_negative')
    assert seen==['first','failed']
