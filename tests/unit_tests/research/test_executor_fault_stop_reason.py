"""The executor's real fault reaches the protected stop receipt and the run status (gates: no masked errors)."""
from types import SimpleNamespace

from jiuwenswarm.research.control import status_reasons
from jiuwenswarm.research.runner import CapsuleRunner


class _Store:
    def __init__(self, rows):
        self.rows, self.appended = rows, []

    def iter_records(self, *, run_id=None, kinds=None):
        return iter([row for row in self.rows if row['kind'] in kinds and row['record']['run_id'] == run_id])

    def append_record(self, kind, record):
        self.appended.append((kind, record))
        return {'id': 'stop', 'sha256': 'x'}


CONTRACT = {'run_id': 'run:1', 'node_id': 'builder', 'attempt_id': 'builder-a1', 'node_contract_ref': {'id': 'n'}}
FAULT = {'run_id': 'run:1', 'node_id': 'builder', 'attempt_id': 'builder-a1', 'operation': 'builder_action',
         'exception_class': 'AttributeError', 'code': None, 'frame': 'jiuwenswarm.research.x:f:34'}


def _stop(rows, failure='integrity_fault'):
    store = _Store(rows)
    runner = SimpleNamespace(store=store, _executions={}, _run_contexts={})
    ref = CapsuleRunner._capture_protected_stop(runner, {'id': 'c'}, CONTRACT, {'id': 'o'}, failure)
    assert ref is not None
    return store.appended[-1][1]


def test_stop_receipt_carries_the_latest_executor_fault_for_the_node():
    older = dict(FAULT, frame='old:frame:1')
    other = dict(FAULT, node_id='benchmark', frame='other:frame:2')
    stop = _stop([{'kind': 'executor-rpc-fault', 'record': older}, {'kind': 'executor-rpc-fault', 'record': FAULT},
                  {'kind': 'executor-rpc-fault', 'record': other}])
    assert stop['reason_code'] == 'integrity_fault'
    assert stop['executor_fault'] == {'operation': 'builder_action', 'exception_class': 'AttributeError',
                                      'code': None, 'frame': 'jiuwenswarm.research.x:f:34'}


def test_stop_receipt_without_a_fault_record_says_none_rather_than_inventing_one():
    assert _stop([])['executor_fault'] is None
    assert _stop([{'kind': 'executor-rpc-fault', 'record': FAULT}], failure='security_fault')['executor_fault'] is None


def test_status_reasons_show_the_executor_cause_after_the_run_reason():
    stop = {'node_id': 'builder', 'executor_fault': {'exception_class': 'AttributeError', 'code': None, 'frame': 'm:f:3'}}
    reasons = status_reasons({'reason': 'protected_stop'}, [{'kind': 'protected-invocation-stop', 'record': stop},
                                                            {'kind': 'gate-decision', 'record': {}}])
    assert reasons == ['protected_stop', 'executor fault in builder: AttributeError  at m:f:3']
    assert status_reasons({'reason': None}, []) == []
    assert status_reasons({'reason': 'protected_stop'}, [{'kind': 'protected-invocation-stop',
                                                          'record': {'node_id': 'b', 'executor_fault': None}}]) == ['protected_stop']
