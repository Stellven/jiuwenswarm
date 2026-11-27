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
    assert replay['presentation_header']['report_kind'] == 'run'
    assert replay['presentation_header']['image_id'] is None
    assert replay['presentation_header']['outcome'].startswith('Stopped before build.')
    assert (out / replay['contract_versions'][0]['path']).read_bytes() == contract.read_bytes()
    assert (out / f'evidence/{sha(raw)}.json').read_bytes() == raw
    assert not list(out.glob('**/*.diff'))
    report = (out / 'reports/lab-report.html').read_text()
    assert '<h1>Run 3 · Run report</h1>' in report
    assert 'The node verifier passed the dispatch trace with may_build false. The final decision (rev 1) stopped the graph.' in report
    assert report.index('The final decision (rev 1)') < report.index('What the names mean') < report.index('Starting engine')
    assert 'AQBCD = AQBC + D (Run 3, not built).' in report
    assert 'AQBCE = AQBC + E (Run 4).' in report
    assert 'Expert cache seeding CC: fills the GPU expert cache at startup from a routing profile' in report
    assert 'class="metric-chart"' not in report
    assert 'already batches' in report
    assert 'No candidate image was built.' in report
    service = FactoryHttpService(roots=[out])
    run, = service.listing()['runs']
    assert run['contract_demo'] and run['demo_order'] == 3
    detail = service.detail(run['id'])
    assert detail['contract']['version'] == 10
    assert detail['run_state']['state'] == 'stopped'
    assert detail['run_state']['outcome'] == 'stop_missing_prerequisite'


def test_imported_instrumentation_uses_diff_view_even_when_store_labels_it_plain_text(tmp_path):
    home, contract, _ = sources(tmp_path)
    raw = b'--- before\n+++ after\n@@ -1 +1 @@\n-old\n+new\n'
    artifact = 'prior-dispatch_fixture_diff'
    with Store(home) as store:
        store.put_artifact(TASK, artifact, raw, 'text/plain', None)
        store.append_observation(TASK, dict(kind='operator_input', source_artifacts=[artifact],
            values=dict(key='dispatch_fixture_diff', artifact_id=artifact, sha256=sha(raw))))
    out = tmp_path / 'bundle'
    build(home, contract, out, instrumentation_diff=artifact)
    copied = out / f'evidence/{sha(raw)}.diff'
    assert copied.read_bytes() == raw
    replay = json.loads((out / 'replay.json').read_bytes())
    assert any(f['label'] == 'Pre-graph dispatch probe instrumentation diff'
               for step in replay['steps'] for f in step['key_files'])


def test_scheduler_gap_uses_a_short_final_reply_and_genuine_version_bindings(tmp_path):
    home, contract, _ = sources(tmp_path)
    cc = 'engine.gpu_kernel_lab'
    with Store(home) as store:
        for node_id, version in [('trace_dispatch', '1.1.0'), ('verify_fixtures', '1.1.1')]:
            store.append_observation(TASK, dict(kind='node_contract_final', values=dict(
                node_id=node_id, cc_versions={cc: version},
                final={'verifiers': [{'verifier': cc + '.verify_candidate'}]},
            )))
    session = home / 'sessions' / f'{TASK}.scheduler.jsonl'
    session.parent.mkdir(exist_ok=True)
    excerpt = 'The only eligible capsule, `engine.gpu_kernel_lab` v1.1.0, declares only `evaluate`, `benchmark`, and `trace_dispatch` in `cc.yaml`.'
    content = f'Private discussion. {excerpt} The contract needs verify_candidate. I did not submit a proposal.'
    raw = (json.dumps(dict(event_type='chat.final', session_id=TASK + '-scheduler-verify_fixtures-1',
                           content=content)) + '\n').encode()
    session.write_bytes(raw)
    out = tmp_path / 'bundle'
    build(home, contract, out)
    proof = json.loads((out / 'projections/scheduler-capability-gap.json').read_text())
    assert proof['source_sha256'] == proof['line_sha256'] == sha(raw)
    assert proof['excerpt'] == {'path': f'sessions/{TASK}.scheduler.jsonl', 'line': 1, 'text': excerpt}
    assert not (out / 'sessions').exists()
    replay = json.loads((out / 'replay.json').read_text())
    assert 'The later fixture final bound verify_candidate at v1.1.1.' in replay['steps'][1]['say']
    assert 'Private discussion' not in (out / 'replay.json').read_text()


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
