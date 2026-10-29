"""Actual Linux private sockets; controlled owners, not model qualification."""
import json
import os
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.native_ports import NativePorts
from jiuwenswarm.research.private_rpc import PrivateRPCClient
from jiuwenswarm.research.router_client import PlatformIntegrityError


@pytest.mark.asyncio
async def test_authorization_socket_has_finite_operations_and_exact_active_binding(tmp_path):
    ipc=tmp_path/'ipc';ipc.mkdir(mode=0o700)
    session=ipc/'session.json';session.write_text(json.dumps({'session_id':'fixture-session','capability':'controlled-test-capability'}));session.chmod(0o600)
    ports=NativePorts(ipc_root=ipc,app_uid=os.geteuid())
    class Runner:
        def authorize_model_context(self,value):
            if value!={'execution_id':'active','call_ordinal':1}:raise ValueError('unknown execution')
            return {'call_id':'fixture:claimed'}
        def authorize_executor_binding(self,value):return {'invocation_id':'fixture:active','contract':{'frozen':True}}
        def authorize_model_dispatch(self,value):return {'call_id':'fixture:claimed','remaining_time_s':1}
        def authorize_containment(self,value):return {'authorized':True,**value,'invocation_ids':[]}
    await ports.bind_runner(Runner())
    client=PrivateRPCClient(ipc/'authorization.sock',protocol='ai4r-authorize-v1',session_id='fixture-session',capability='controlled-test-capability',peer_uid=os.geteuid())
    assert await client.call('authorize_model_context',{'execution_id':'active','call_ordinal':1})=={'call_id':'fixture:claimed'}
    with pytest.raises(PlatformIntegrityError):await client.call('authorize_model_context',{'execution_id':'unknown','call_ordinal':1})
    assert await client.call('authorize_model_dispatch',{})=={'call_id':'fixture:claimed','remaining_time_s':1}
    assert set(ports.authorization_server.handlers)=={'authorize_model_context','authorize_model_dispatch','authorize_executor_binding','authorize_containment',
        'authorize_executor_preparation','publish_scientific_start_receipt','inspect_scientific_attempt','inspect_scientific_evaluation',
        'authorize_admission_self_test','prepare_calibration_case','inspect_calibration','cancel_calibration'}
    for operation in ('authorize_executor_preparation','publish_scientific_start_receipt','inspect_scientific_attempt','inspect_scientific_evaluation'):
        assert ports.authorization_server.operation_uids[operation]=={0}
    assert ports.authorization_server.operation_uids['authorize_admission_self_test']=={0}
    for operation in ('prepare_calibration_case','inspect_calibration','cancel_calibration'):
        assert ports.authorization_server.operation_uids[operation]=={os.geteuid()}
    await ports.close();assert not (ipc/'authorization.sock').exists()
