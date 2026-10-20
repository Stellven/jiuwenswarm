from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
"""Private IF012 consumer controls; no model or operational grant is implied."""
import asyncio,hashlib
import pytest
from jiuwenswarm.research_rsi.records import RecordStore
from tests.unit_tests.research_rsi.test_isolated_trial_client import binding,pin


def parent_binding():
    value=binding()
    return {'schema':'ai4r-admitted-measurement-binding:1','id':'parent:one',
        **{k:value[k] for k in ('session_ref','target_ref','parent_admission_ref','parent_declaration_ref','parent_contract_ref',
            'configuration_ref','model_selection_profile_ref','deployment_ref','reservation_ref','inputs','limits','phase','repeat_index')},
        'parent_check_plan_ref':pin('parent-checks')}


def test_parent_client_counts_once_and_unknown_execution_never_resends(tmp_path):
    from jiuwenswarm.research_rsi.text_trial import ParentMeasurementClient
    store=RecordStore(tmp_path/'records');binding=parent_binding();ref=store.put(binding);calls=[]
    async def transport(operation,ref):
        calls.append(operation)
        if operation=='parent_prepare':return {'grant_ref':pin('grant')}
        raise TimeoutError('Actual native effect unknown')
    client=ParentMeasurementClient(store,transport=transport,allowed_session_refs=[binding['session_ref']])
    with pytest.raises(TimeoutError):asyncio.run(client.execute(ref))
    with pytest.raises(ValueError):asyncio.run(client.execute(ref))
    assert calls==['parent_prepare','parent_execute']
    store.close()


def test_parent_result_joins_actual_grant_subject_without_renamed_child_or_acceptance():
    from jiuwenswarm.research_rsi.text_trial import ParentMeasurementClient
    value=parent_binding();grant=pin('grant')
    result={'schema':'ai4r-admitted-measurement-result:1','id':'result','grant_ref':grant,'binding_ref':pin('binding'),
        **{k:value[k] for k in ('session_ref','target_ref','parent_declaration_ref')},'contract_ref':pin('actual-parent-contract'),
        'check_plan_ref':pin('actual-parent-checks'),'status':'completed','measurement_ref':pin('measurement'),'accepted':False}
    ParentMeasurementClient.validate_result(value,grant,result,binding_ref=pin('binding'))
    for mutation in [{'parent_declaration_ref':pin('renamed-child')},{'grant_ref':pin('foreign')},{'accepted':True},{'binding_ref':pin('foreign')}, {'child_declaration_ref':pin('child')}]:
        with pytest.raises(ValueError):ParentMeasurementClient.validate_result(value,grant,result|mutation,binding_ref=pin('binding'))


def test_parent_port_does_not_expose_arbitrary_store_refs_or_jobs_operations(tmp_path):
    from jiuwenswarm.research_rsi.trial_port import ParentTrialPort
    from jiuwenswarm.research.state import SQLiteRunStore
    store=SQLiteRunStore(tmp_path/'core')
    port=ParentTrialPort(object(),store,public_reader=lambda _:b'',allowed_session_refs=[],parent_bindings=[])
    assert set(port.handlers())=={'parent_prepare','parent_execute','parent_inspect'}
    with pytest.raises(ValueError):asyncio.run(port.inspect(pin('unknown')))
    store.close()


@pytest.mark.asyncio
async def test_connected_parent_owner_transfers_original_bytes_without_acceptance_or_replay(tmp_path):
    from tests.unit_tests.research.test_parent_measurement import parent_fixture
    from jiuwenswarm.research_rsi.trial_port import ParentTrialPort
    from jiuwenswarm.research_rsi.text_trial import ParentMeasurementClient
    from jiuwenswarm.research_rsi.native_lease import NativeEffectLease
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    core,owner,fixture,binding=await parent_fixture(tmp_path/'core')
    custody=RecordStore(tmp_path/'custody');controller=RecordStore(tmp_path/'controller')
    ref=custody.put(binding);capture=OriginalBytes(tmp_path/'captures',writable=True)
    lease=NativeEffectLease(controller,controller.put({'scope':'explicit controlled no-model path'}))
    async_calls=[]
    port=ParentTrialPort(owner,core,qualification=ControlledQualification(),public_reader=custody.read,allowed_session_refs=[binding['session_ref']],
        parent_bindings=[{k:binding[k] for k in ('session_ref','parent_contract_ref','parent_check_plan_ref')}],native_lease=lease)
    async def local_transport(operation,pin):
        async_calls.append(operation);return await port.handlers()[operation](pin)
    client=ParentMeasurementClient(custody,transport=local_transport,allowed_session_refs=[binding['session_ref']],capture=capture)
    result,result_ref=await client.execute(ref)
    assert result['status'] in {'failed','blocked'} and result['accepted'] is False
    assert capture.read(result_ref)==core.read_blob(result_ref)
    raw=capture.get(result['measurement_ref']);assert raw['accepted'] is False and raw['contract_ref']==result['contract_ref']
    assert not list(core.iter_records(kinds=('gate-decision','acceptance-commit')))
    with pytest.raises(ValueError):await client.execute(ref)
    inspected=await client.inspect(ref,result['grant_ref']);assert inspected[1]==result_ref
    assert async_calls==['parent_prepare','parent_execute','parent_inspect']
    lease.assert_available();custody.close();controller.close();core.close()


def test_real_session_observer_reads_only_original_indexed_bytes_and_cannot_write(tmp_path):
    import sqlite3
    from jiuwenswarm.research.state import SQLiteRunStore
    from tests.integration.research.rsi.conftest import ReadOnlyCoreCapture
    core=SQLiteRunStore(tmp_path/'actual-store')
    ref=core.append_record('controlled-observer-input',{'controlled_fixture':'reader mechanics only'})
    observed=ReadOnlyCoreCapture(core.root)
    try:
        assert observed.records('controlled-observer-input')==[(ref,{'controlled_fixture':'reader mechanics only'})]
        assert observed.read(ref)==core.read_blob(ref)
        with pytest.raises(sqlite3.OperationalError):observed.db.execute('CREATE TABLE forbidden_observer_write(id TEXT)')
        with pytest.raises(AssertionError):observed.read(ref|{'sha256':'0'*64})
        core.blobs.path_for(ref['sha256']).write_bytes(b'changed original')
        with pytest.raises(AssertionError):observed.read(ref)
    finally:observed.close();core.close()
