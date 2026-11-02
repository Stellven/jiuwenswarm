"""Progress must never reveal private records, authorize actions or mask results."""
import copy
import pytest

from jiuwenswarm.research_rsi.progress import emit
from jiuwenswarm.research.cc_ui_runtime import module

progress = module('cc_rsi_progress')
SCHEMA, overlay, validate = progress.SCHEMA, progress.overlay, progress.validate


def packet():
    return {'schema': SCHEMA, 'workspace_id': 'workspace', 'run_id': 'run-one',
        'target_id': 'arbitrary.capsule', 'parent_hash': 'a'*64,
        'observed_at': 1000, 'started_at': 900, 'worker_status': 'running',
        'events': [{'id': 'b'*64, 'at': 950, 'stage': 'parent', 'iteration': 0, 'source': 'engine'},
                   {'id': 'c'*64, 'at': 990, 'stage': 'diagnose', 'iteration': 1, 'source': 'engine'}],
        'iteration': 1, 'max_iterations': 3, 'completed_iterations': 0,
        'model_calls': 1, 'executions': 9, 'execution_limit': 100, 'limit_seconds': 600}


def test_live_stage_and_stale_heartbeat_do_not_claim_completion():
    p = validate(packet(), 'workspace')
    base = {'runs': [], 'targets': []}
    view = overlay(base, [p], now=1002)
    run = view['runs'][0]
    assert run['stage'] == 'Diagnose' and run['status'] == 'RUNNING'
    assert run['progress']['iteration'] == 1 and run['budget']['elapsed_seconds'] == 100
    assert not view['targets'][0]['run']['allowed']
    assert base == {'runs': [], 'targets': []}
    stale = overlay(base, [p], now=1030)['runs'][0]
    assert stale['status'] == 'UNKNOWN' and stale['progress']['stale']


def test_final_publication_wins_over_live_or_stale_events():
    terminal = {'id': 'run-one', 'status': 'ERROR_NO_REPLAY', 'stage': 'Failed'}
    base = {'runs': [terminal], 'targets': []}
    assert overlay(base, [packet()], now=1000) == base


@pytest.mark.parametrize('change', [
    lambda p: p.update(prompt='PRIVATE'),
    lambda p: p.update(workspace_id='another'),
    lambda p: p['events'][0].update(output='PRIVATE'),
    lambda p: p['events'][0].update(stage='arbitrary private text'),
    lambda p: p.update(model_calls=-1),
    lambda p: p['events'][0].update(at=float('nan')),
])
def test_progress_rejects_private_fields_and_wrong_scope(change):
    p = copy.deepcopy(packet()); change(p)
    with pytest.raises(ValueError): validate(p, 'workspace')


def test_telemetry_write_failure_does_not_fail_execution():
    class BrokenStore:
        def put(self, value): raise OSError('disk unavailable')
    emit(BrokenStore(), {'id': 'run-one', 'capsule_name': 'arbitrary.capsule'}, 'diagnose')
