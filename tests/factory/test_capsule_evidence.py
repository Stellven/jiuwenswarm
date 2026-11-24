"""Synthetic evidence fixtures exercise read-only capsule replay projection."""

import hashlib
import time
import json

from jiuwenswarm.factory.store import Store
from jiuwenswarm.gateway.channel_manager.web.capsule_evidence import capsule_usage, collect_capsule_evidence
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


def test_analysis_links_only_its_retained_report_and_iteration_outputs(tmp_path):
    report = {'rows': [{'phase': 'prefill', 'elapsed_ms': 12}]}
    report_digest = hashlib.sha256(json.dumps(report).encode()).hexdigest()
    markdown_report = {'formatted': 'report'}
    markdown_digest = hashlib.sha256(json.dumps(markdown_report).encode()).hexdigest()
    files = _export(
        tmp_path / 'analysis', dict(task_id='multiple-producers'),
        artifacts=[('applicable.json', report), ('unrelated.json', {}), ('report.md', markdown_report)],
        observations=[
            dict(obs_id='analysis', kind='analysis', source_artifacts=['unrelated.json', 'applicable.json'],
                 values=dict(capsule_id=ANALYZER, report_sha256=report_digest, rows=report['rows'])),
            dict(obs_id='report', kind='factory_iteration_report', values={
                'schema': 'spark-factory-iteration/1',
                'analysis': {'ccs': [{'id': ANALYZER}], 'output_artifact_ids': ['applicable.json']},
                'report': {'artifact_id': 'report.md', 'sha256': markdown_digest},
            }),
        ],
    )
    result = collect_capsule_evidence(FactoryHttpService(roots=[tmp_path]), ANALYZER, analysis=True)

    analysis = result['analyses'][0]
    assert analysis['report_artifact_id'] == 'applicable.json'
    assert analysis['path'] == files[0]['exported_path']
    assert analysis['integrity'] == 'verified'
    assert {(item['artifact_id'], item['kind']) for item in result['artifacts']} == {
        ('applicable.json', 'analysis_report'), ('report.md', 'report'),
    }


def test_catalog_fresh_analysis_comes_from_native_results_and_deduplicated_usage(tmp_path):
    historical = 'analysis.older'
    imported = 'analysis.imported'
    now = time.time()
    task = dict(task_id='review')
    obs = [
        dict(kind='analysis', created=now, values=dict(capsule_id=ANALYZER, rows=[{'elapsed_ms': 42}])),
        dict(kind='analysis', created=now - 172800, values=dict(capsule_id=historical, rows=[{'elapsed_ms': 9}])),
        dict(kind='analysis', created=now, values=dict(capsule_id=imported, analysis_obs_id='foreign-result')),
    ]
    _export(tmp_path / 'review', task, observations=obs)
    _export(tmp_path / 'review-replay', task, observations=obs)
    usage = capsule_usage(FactoryHttpService(roots=[tmp_path]), {ANALYZER, historical, imported, RECORDER})

    assert usage[ANALYZER] == {'used_in_runs': 1, 'featured_analysis_at': now}
    assert usage[historical] == {'used_in_runs': 1, 'featured_analysis_at': None}
    assert usage[imported] == {'used_in_runs': 1, 'featured_analysis_at': None}
    assert usage[RECORDER] == {'used_in_runs': 0, 'featured_analysis_at': None}


def test_builder_summary_links_latest_iteration_revision_and_verified_functional_evidence(tmp_path):
    binary = 'd' * 64
    crossed = 'e' * 64
    build = {'status': 'success', 'executable': {'sha256': binary}}
    lab = {
        'schema': 'spark-functional-lab/1', 'binary_sha256': binary,
        'arms': [{'arm': 'feature-off-functional', 'stock_match': {'output_sha256': True}},
                 {'arm': 'feature-on-functional', 'stock_match': {'output_sha256': True}, 'peak_memory_bytes': 120}],
        'session_summary': {'written': 3, 'lost': 0, 'bytes_transferred': 900},
        'scope': 'Functional probe; timing ineligible',
    }
    report = {'formatted': 'report'}
    report_hash = hashlib.sha256(json.dumps(report).encode()).hexdigest()
    envelope = {'schema': 'spark-factory-iteration/1', 'plan': {'builder_ccs': [{'id': RECORDER}]},
                'report': {'artifact_id': 'iteration/report-v2.md', 'sha256': report_hash, 'revision': 2}}
    files = _export(
        tmp_path / 'builder', dict(task_id='recorder', component_cc=RECORDER),
        artifacts=[('build-a:build-record', build), ('fixture/lab.json', lab), ('iteration/report-v2.md', report)],
        observations=[
            dict(kind='build_result', created=1, values=build, source_artifacts=['build-a:build-record']),
            dict(kind='build_result', created=2, values={'status': 'failed', 'executable': {'sha256': crossed}}),
            dict(kind='functional_lab', created=3, values=lab, source_artifacts=['fixture/lab.json']),
            dict(kind='factory_iteration_report_revision', created=4, values=envelope),
        ],
    )
    service = FactoryHttpService(roots=[tmp_path])
    summary = collect_capsule_evidence(service, RECORDER, starred=True)['latest_builder_run']
    assert summary['build']['binary_sha256'] == binary
    assert summary['build']['artifact']['path'] == files[0]['exported_path']
    assert summary['lab']['parity'] is True
    assert summary['lab']['activation'] is True
    assert summary['lab']['metrics'] == {'written': 3, 'lost': 0, 'bytes_transferred': 900, 'peak_memory_bytes': 120}
    assert summary['report']['path'] == files[2]['exported_path']
    assert summary['report']['integrity'] == 'verified'
