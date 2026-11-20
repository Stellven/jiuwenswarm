"""Synthetic evidence fixtures exercise read-only capsule replay projection."""

import hashlib
import json

from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.capsule_evidence import collect_capsule_evidence
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService


RECORDER = 'observability.build_runtime_event_recorder'
WEIGHT_CACHE = 'engine.build_expert_weight_cache'
ANALYZER = 'factory.deep_profile'


def _record(call, capability='verify', finished=10, **outputs):
    return dict(cc='2', release='retained-release', capability=capability, call=call,
                state='succeeded', completeness='complete', provenance={'finished': finished}, outputs=outputs)


def _events(capsule, call, receipt):
    return [dict(event_type='chat.tool_call', tool_call=dict(
        tool_call_id=call, name='cc.cc_call', arguments=dict(cc=capsule, capability=receipt['capability']))),
        dict(event_type='chat.tool_result', tool_call_id=call, tool_name='cc.cc_call', result=json.dumps(
            {'result': {'content': [{'text': json.dumps(receipt)}]}}))]


def _export(root, task, *, artifacts=(), observations=(), transcript=()):
    (root / 'records').mkdir(parents=True)
    (root / 'artifacts').mkdir()
    files = []
    for artifact_id, content in artifacts:
        blob = json.dumps(content).encode()
        digest = hashlib.sha256(blob).hexdigest()
        relative = f'artifacts/{digest}'
        (root / relative).write_bytes(blob)
        files.append(dict(artifact_id=artifact_id, sha256=digest, exported_path=relative,
                          location=relative, media_type='application/json', created=20))
    (root / 'records/tasks.json').write_text(json.dumps([task]))
    (root / 'records/artifacts.json').write_text(json.dumps(files))
    (root / 'records/observations.json').write_text(json.dumps(observations))
    (root / 'artifacts.json').write_text(json.dumps(files))
    (root / 'session.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in transcript))
    manifest = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file()}
    (root / 'MANIFEST.json').write_text(json.dumps(manifest))
    return files


def test_live_capsule_links_products_and_preserved_verify_receipts(tmp_path):
    task = 'recorder'
    checks = [dict(name='activation', status='inconclusive', detail='No runtime observation')]
    with Store(tmp_path) as store:
        store.create_task(dict(task_id=task, objective='Synthetic recorder', component_cc=RECORDER))
        receipt_id = 'native-verifier-receipts.json'
        receipt = store.put_artifact(task, receipt_id, json.dumps([
            _record('old', done=False), _record('latest', finished=11, done=True, checks=checks),
        ]).encode(), 'application/json', None)
        store.append_observation(task, dict(kind='verifier_receipt_preserved', source_artifacts=[receipt_id],
                                           values={}, limitations='Static checks only.'))
        store.put_artifact(task, 'input-16:sample.diff', b'sample', 'text/x-diff', None)
        product = store.put_artifact(task, 'product.diff', b'product', 'text/x-diff', None)
        store.put_artifact(task, 'attempt:build-record', b'{}', 'application/json', None)
    (tmp_path / product['location']).write_bytes(b'altered product')

    service = FactoryHttpService(roots=[tmp_path])
    data = collect_capsule_evidence(service, RECORDER)
    latest = data['latest_verify_receipt']
    assert (latest['call'], latest['done'], latest['checks'], latest['limitations']) == ('latest', True, checks, 'Static checks only.')
    assert latest['path'] == receipt['location']
    assert service.file(latest['run_id'], latest['path'])['integrity'] == 'verified'
    assert {a['artifact_id']: (a['kind'], a['integrity']) for a in data['artifacts']} == {
        receipt_id: ('verify_receipt', 'verified'), 'product.diff': ('diff', 'mismatch'),
        'attempt:build-record': ('build_record', 'verified'),
    }


def test_bundle_uses_export_paths_and_skips_corrupt_receipt_payload(tmp_path):
    root = tmp_path / 'bundle'
    files = _export(root, dict(task_id='native', component_cc=RECORDER), artifacts=[
        ('verifier-receipt.json', _record('embedded', finished=50, done=True)),
    ], observations=[dict(kind='verify_receipt', source_artifacts=['verifier-receipt.json'], values={})],
        transcript=[*_events(RECORDER, 'first', _record('replay', done=False)),
                    *_events(WEIGHT_CACHE, 'other', _record('foreign', finished=20, done=True))])
    (root / files[0]['exported_path']).write_text(json.dumps(_record('tampered', finished=100)))

    data = collect_capsule_evidence(FactoryHttpService(roots=[root]), RECORDER)
    assert data['artifacts'][0]['path'] == files[0]['exported_path']
    assert data['artifacts'][0]['integrity'] == 'mismatch'
    assert data['latest_verify_receipt']['call'] == 'replay'
    assert data['latest_verify_receipt']['path'] == 'session.jsonl'
    assert data['latest_verify_receipt']['integrity'] == 'verified'


def test_measurements_require_eligibility_and_matching_benchmark_inputs(tmp_path):
    def sample(id_, arm, ttft, **overrides):
        values = dict(arm=arm, ttft_s=ttft, measurement_eligible=True, warm=True,
                      prompt_tokens=512, prompt_sha256='fixed', contract_sha256='contract')
        return dict(obs_id=id_, kind='measurement', values=values | overrides)

    observations = [sample('stock', 'A', 10), sample('strata', 'S', 5), sample('cache', 'A+', 8),
                    sample('fast', 'C1', 6), sample('slow', 'C1', 8), sample('excluded', 'C1', 50, measurement_eligible=False),
                    sample('warmup', 'C1', 50, warm=False), sample('other-capsule', 'C2', 4),
                    sample('combined', 'D', 5), sample('different-prompt', 'C1', 2, prompt_sha256='alternate')]
    task = dict(task_id='comparison', contract_id='star-deepseek-v1')
    _export(tmp_path / 'current', task, observations=observations)
    _export(tmp_path / 'copy', task, observations=observations)
    service = FactoryHttpService(roots=[tmp_path])
    result = collect_capsule_evidence(service, RECORDER, starred=True)
    rows = {tuple(row['observation_ids']): row for row in result['measurements']}
    assert set(rows) == {('fast', 'slow'), ('combined',), ('different-prompt',)}
    candidate = rows[('fast', 'slow')]
    assert candidate['scope'] == 'capsule' and candidate['samples'] == 2 and candidate['ttft_s'] == 7
    assert candidate['delta_vs_stock_s'] == -3 and candidate['gap_closed'] == 0.6
    assert candidate['inverse_vs_stock'] == 10 / 7 and candidate['inverse_vs_cache'] == 8 / 7
    assert rows[('combined',)]['scope'] == 'combined' and rows[('combined',)]['gap_closed'] == 1
    assert rows[('different-prompt',)]['delta_vs_stock_s'] is None


def test_analysis_uses_native_producer_and_retains_distinct_results(tmp_path):
    records = [dict(obs_id='observed-analysis', kind='retained_table', values={
        'capsule_id': ANALYZER, 'phase_breakdown': {'decode_ms': 23}, 'password': 'fixture-secret'}),
        dict(obs_id='native-profile', kind='profile_result', values={'native_profile': {'trace': 1}})]
    transcript = [*_events(ANALYZER, 'the-call', _record('analysis-call', 'analyze', analysis={'gap_attribution': {'transfer_ms': 3}})),
                  *_events(WEIGHT_CACHE, 'unrelated', _record('different-analysis', 'analyze', analysis={'unrelated': 1}))]
    _export(tmp_path / 'analysis', dict(task_id='multi-capsule-review'), observations=records, transcript=transcript)
    service = FactoryHttpService(roots=[tmp_path])

    rows = collect_capsule_evidence(service, ANALYZER, analysis=True)['analyses']
    assert [(row['call'], row['observation_id'], row['path']) for row in rows] == [
        ('analysis-call', None, 'session.jsonl'), (None, 'observed-analysis', None),
    ]
    assert rows[0]['values'] == {'gap_attribution': {'transfer_ms': 3}}
    assert rows[1]['values']['phase_breakdown'] == {'decode_ms': 23}
    assert rows[1]['values']['password'] == '<redacted>'
