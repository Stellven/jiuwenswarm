import pytest

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.native_lease import NativeEffectLease,ProfileInUse


def test_lost_native_effect_blocks_a_new_owner_until_exact_host_containment(tmp_path):
    store=RecordStore(tmp_path);pin=store.put({'unit':'protected binding'})
    lease=NativeEffectLease(store,pin)
    started=lease.start('session-a',pin)
    with pytest.raises(ProfileInUse):NativeEffectLease(store,pin).assert_available()
    # A worker containment/ERROR-history record cannot clear native ownership.
    unrelated=store.put({'contained_worker':True})
    with pytest.raises(ValueError):lease.release_from_receipt(unrelated,store.read)
    proof=store.put({'unit':'explicit host no-process observation; control fixture only'})
    receipt=store.put({'schema':'ai4r-rsi-native-containment:1','scope_ref':pin,'prior_lease_ref':started,
        'owned_container_id':'a'*64,'prior_pid_namespace':store.get(started)['pid_namespace'],
        'observed_exited':True,'observed_no_owned_processes':True,'evidence_refs':[proof],
        'recorded_at':'2026-10-16T00:00:00Z'})
    lease.release_from_receipt(receipt,store.read)
    lease.assert_available()
    next_ref=lease.start('session-b',pin);lease.complete(next_ref,{'known_terminal_call_refs':[proof]})
    NativeEffectLease(store,pin).assert_available()


def test_unknown_call_is_durable_and_cannot_be_released_by_terminal_history(tmp_path):
    store=RecordStore(tmp_path);pin=store.put({'unit':'scope'})
    lease=NativeEffectLease(store,pin);start=lease.start('session',pin)
    lease.uncertain(start,{'reason':'actual native outcome unavailable'})
    with pytest.raises(ProfileInUse):NativeEffectLease(store,pin).start('another',pin)
    with pytest.raises(ValueError):lease.complete(start,{'error_history_only':True})
def test_recovery_bootstrap_does_not_start_another_native_profile_process(tmp_path):
    import asyncio
    from jiuwenswarm.research_rsi.fixed_resources import native_profile_ready
    from jiuwenswarm.research_rsi.records import RecordStore
    store=RecordStore(tmp_path/'records');scope=store.put({'controlled':'scope'})
    lease=NativeEffectLease(store,scope);pin=lease.start('interrupted',scope)
    lease.uncertain(pin,{'no_containment_proof':True})
    class MustNotStart:
        async def status(self):raise AssertionError('uncertain recovery must not start a new native app-server')
    assert asyncio.run(native_profile_ready(MustNotStart(),lease)) is False
    with pytest.raises(ProfileInUse):lease.assert_available()
    store.close()


def test_failed_model_history_requires_exact_actual_containment_not_just_terminal_word(tmp_path):
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research_rsi.native_lease import native_completion_proof
    core=SQLiteRunStore(tmp_path/'core')
    start={'ref':{'id':'start','sha256':'a'*64},'record':{'call_id':'call','run_id':'run','invocation_id':'invocation'}}
    core.append_record('model-call',{'id':'call','invocation_id':'invocation','outcome':'failed'})
    assert native_completion_proof(core,[start])[0] is False
    core.append_record('model-run-contained',{'id':'wrong','run_id':'foreign','contained':True,'invocation_ids':['invocation']})
    assert native_completion_proof(core,[start])[0] is False
    exact=core.append_record('model-run-contained',{'id':'actual','run_id':'run','contained':True,'invocation_ids':['invocation']})
    known,proof=native_completion_proof(core,[start])
    assert known and exact in proof['actual_model_containment_refs']
    core.close()
