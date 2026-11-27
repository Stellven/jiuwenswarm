"""Run 3 replay evidence checks use a temporary store and start no jobs."""
import json

import pytest

from jiuwenswarm.factory.export import sha, verify
from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService
from scripts.spark.build_r10_replay import TASK, build


def sources(tmp_path, *, eligibility='already_batched', action='stop_missing_prerequisite',
            cite_trace=True):
    home = tmp_path / 'graph'
    contract = tmp_path / 'contract.json'
    contract.write_text(json.dumps({
        'contract_id': TASK, 'version': 10,
        'extensions': {'muse.r10-dispatch': {'baseline': {'image_id': 'sha256:' + 'a' * 64}}},
    }) + '\n')
    raw = json.dumps({'eligibility': eligibility, 'may_build': eligibility == 'eligible',
                      'identity': {'image_id': 'sha256:' + 'a' * 64}}).encode()
    with Store(home) as store:
        store.create_task(dict(task_id=TASK, contract_id=TASK, objective='Test dispatch gate',
                               constraints={'contract_sha256': sha(contract.read_bytes())}))
        store.put_artifact(TASK, 'test-trace', raw, 'application/json', None)
        trace = store.append_observation(TASK, dict(
            kind='node_check', source_artifacts=['test-trace'],
            values=dict(node_id='trace_dispatch', output='dispatch_trace', passed=True,
                        verifier=dict(sealed_artifact='test-trace'))))
        store.advance_decision(TASK, 0, dict(action=dict(type=action, node_id='trace_dispatch'),
                                            evidence_ids=[trace['obs_id']] if cite_trace else [],
                                            reason_for_change='A verified trace recorded the verdict.'))
    return home, contract, raw


def test_prebuild_stop_is_a_native_demo_with_source_and_report(tmp_path):
    home, contract, raw = sources(tmp_path)
    out = tmp_path / 'bundle'
    build(home, contract, out)
    assert verify(out) > 0
    replay = json.loads((out / 'replay.json').read_bytes())
    assert replay['order'] == 3
    assert replay['presentation_header']['image_id'] is None
    assert replay['presentation_header']['outcome'].startswith('Stopped before build.')
    assert (out / replay['contract_versions'][0]['path']).read_bytes() == contract.read_bytes()
    assert (out / f'evidence/{sha(raw)}.json').read_bytes() == raw
    assert not list(out.glob('**/*.diff'))
    report = (out / 'reports/lab-report.html').read_text()
    assert 'already batches' in report
    assert 'No candidate image was built.' in report
    service = FactoryHttpService(roots=[out])
    run, = service.listing()['runs']
    assert run['contract_demo'] and run['demo_order'] == 3
    assert service.detail(run['id'])['contract']['version'] == 10


@pytest.mark.parametrize(('eligibility', 'action', 'cite_trace', 'message'), [
    ('already_batched', 'stop_missing_prerequisite', False, 'Pre-build stop disagrees'),
    ('already_batched', 'accept', True, 'Pre-build stop disagrees'),
    ('eligible', 'accept', True, 'Release requires delivery'),
])
def test_replay_refuses_unsupported_terminal(tmp_path, eligibility, action, cite_trace, message):
    home, contract, _ = sources(tmp_path, eligibility=eligibility, action=action, cite_trace=cite_trace)
    out = tmp_path / 'bundle'
    with pytest.raises(ValueError, match=message):
        build(home, contract, out)
    assert not out.exists()
