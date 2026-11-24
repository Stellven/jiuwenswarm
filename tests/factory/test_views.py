"""Narrow offline parser/render checks. Synthetic traces are never run evidence."""
import hashlib
import json
from pathlib import Path
import re

from jiuwenswarm.factory.store import Store
from jiuwenswarm.factory.views import load_run, load_task, parse_stderr, parse_trace, render_html
from jiuwenswarm.factory.views.activity import build_activity
from jiuwenswarm.factory.views.__main__ import main


# Exactly two unmodified lines from J-OM13/008-factory/stderr.txt, lines 355–356.
FIXTURE = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/views/sample/j-om13-stats.stderr.txt'


def test_real_jom13_stats():
    stats = parse_stderr(FIXTURE.read_text(), str(FIXTURE))
    assert stats['fill']['decode_bytes_read'] == 5269782528
    assert stats['fill']['prompt_bytes_read'] == 0  # measured zero, unlike absent counters
    assert stats['fill']['decode_fill_wall_ns'] == 15657048894
    assert stats['pregate']['hits'] == 15908
    assert stats['pregate']['recall_at_k'] == .809320
    assert stats['pregate']['hit_inflight'] == 1094
    assert stats['snapshots']['fill'][0]['line'] == 2
    doc = build_activity(stats)
    assert doc['totals']['speculative_read_bytes'] == 8541995008
    assert doc['totals']['join_wait_ns'] is None
    assert doc['totals']['speculative_unused_target_bytes'] is None
    assert doc['stats']['readiness'] is None
    # Patch 10 and 11 optional counters are parsed without requiring old lines to
    # supply them. These appended fields are synthetic parser input, not lab data.
    extended = FIXTURE.read_text().replace('precision=0.809320', 'precision=0.809320 join_waits=2 join_wait_ns=99 join_bytes=4096')
    extended += 'expert_readiness: stats decode_tokens=63 decode_ready_bytes_predicted=8192 decode_wasted_async_bytes=0 probe_ns_total=12\n'
    extra = build_activity(parse_stderr(extended))
    assert extra['totals']['join_wait_ns'] == 99
    assert extra['totals']['speculative_unused_target_bytes'] == 0
    assert extra['totals']['speculative_unused_lifetime_bytes'] is None


def test_no_trace_stays_unknown_and_cli(tmp_path):
    (tmp_path / 'stderr.txt').write_text(FIXTURE.read_text())
    (tmp_path / 'summary.json').write_text(json.dumps({'eval_tokens': 63, 'eval_ms_total': 45394.67}))
    (tmp_path / 'result.json').write_text(json.dumps({'image': 'engine:mutable-tag', 'argv': ['llama-completion', '-cmoe']}))
    doc = load_run(tmp_path)
    assert doc['schema'] == 'expert_activity/1'
    assert doc['activity']['status'] == 'unknown'
    assert doc['activity']['events'] == []
    assert doc['timeline'] == []
    assert doc['predictions'] == []
    assert doc['provenance']['image_id'] is None
    assert doc['phases']['load']['duration_ns'] is None
    assert doc['phases']['prompt']['demand_read_bytes'] == 0
    assert doc['provenance']['source_files'][-1]['overhead']['measured_ratio'] is None
    page = render_html(doc)
    assert 'aggregate, no per-token trace' in page
    assert 'REPLAY' in page and 'UNKNOWN' in page
    out = tmp_path / 'view.html'
    main([str(tmp_path), '--out', str(out)])
    assert out.read_text() == page


def test_current_csv_selected_only_and_appended_sessions():
    selected_only = parse_trace('run,token_idx,layer,phase,selected\na,195,0,decode,1 2 3 4 5 6 7 8\n')
    event = selected_only['events'][0]
    assert event['selected_ids'] == list(range(1, 9))
    assert event['predicted_ids'] is None
    assert event['demand_wait_ns'] is None
    assert all(r['class'] == 'unknown' for r in event['readiness'])
    doc = build_activity(trace=selected_only)
    assert doc['predictions'][0]['recall'] is None
    csv = 'run,token_idx,layer,phase,selected,predicted\na,195,0,decode,1 2,\nb,195,0,decode,1 2,1\n'
    trace = parse_trace(csv)
    doc = build_activity(trace=trace)
    assert trace['sessions'] == ['a', 'b']
    assert doc['predictions'][0]['recall'] == 0  # an observed empty set
    assert doc['predictions'][1]['recall'] == .5
    assert len(doc['timeline']) == 2
    assert parse_trace(csv, trace_run='b')['sessions'] == ['b']
    assert 'Predicted IDs: []' in render_html(doc)


def test_html_with_synthetic_v2_trace():
    rows = [dict(schema='expert_trace/2', type='meta', run_id='synth', origin='synthetic', n_layers=2,
                 sampling={'mode': 'all'}, overhead={'mode': 'synthetic fixture', 'measured_ratio': None, 'evidence_id': None})]
    for layer in range(2):
        rows.append(dict(schema='expert_trace/2', type='expert', run_id='synth', phase='decode', token_idx=195, layer=layer,
            selected_ids=list(range(8)), predicted_ids=list(range(4)), prediction_source={'kind': 'synthetic'},
            readiness=[dict(expert_id=i, **{'class': ('resident', 'prefetched_done', 'inflight', 'queued', 'missing', None, None, None)[i]}) for i in range(8)],
            demand_read_bytes=4096, demand_wait_ns=1_000_000, arrival_ns=10_000_000, fill_end_ns=11_000_000,
            speculative=dict(issued_bytes=8192, read_bytes=4096, used_bytes=2048, wasted_bytes=2048,
                             timely_bytes=1024, late_bytes=1024, unused_scope='target_arrival')))
    rows.append(dict(schema='expert_trace/2', type='token', run_id='synth', phase='decode', token_idx=195,
                     start_ns=0, end_ns=5_000_000))
    trace = parse_trace('\n'.join(json.dumps(r) for r in rows))
    doc = build_activity(trace=trace, metadata={'run_id': '</script><script>alert(1)</script>'})
    assert doc['timeline'][0]['demand_wait_ns'] == 2_000_000
    assert doc['timeline'][0]['rest_ns'] == 3_000_000
    assert doc['predictions'][0]['recall'] == .5
    assert doc['predictions'][0]['speculative']['wasted_bytes'] == 2048
    page = render_html(doc)
    assert '<svg' in page and 'data-event="0"' in page
    assert 'SYNTHETIC' in page
    assert 'state-prefetched_done' in page
    assert all(label in page for label in ['A · Selected', 'B · Predicted', 'C · Where', 'D · What changed'])
    assert 'inferred residual' in page
    assert '<script>alert(1)</script>' not in page
    embedded = re.search(r'<script id="activity-data" type="application/json">(.*?)</script>', page, re.S)[1]
    assert json.loads(embedded) == doc
    assert not re.search(r'<(?:script|link)[^>]+(?:src|href)=', page)
    # One measured layer is a partial wait, not a token total or inferred rest.
    trace['events'].pop()
    partial = build_activity(trace=trace)
    assert partial['timeline'][0]['demand_wait_ns'] is None
    assert partial['timeline'][0]['measured_layer_wait_ns'] == 1_000_000
    assert partial['timeline'][0]['rest_ns'] is None


def test_factory_store_chain_and_home_remains_read_only(tmp_path):
    home = tmp_path / 'factory'
    image = 'sha256:' + 'a' * 64
    with Store(home) as store:
        store.create_task({'task_id': 't', 'objective': 'synthetic offline view'})
        store.create_attempt('t', dict(attempt_id='build', kind='build', idem_key='build', fingerprint='f',
            request={'source': {'commit': 'b' * 40, 'files_changed': ['src/llama-context.cpp']}}))
        store.append_observation('t', dict(obs_id='built', kind='build_result', host_run={'attempt_id': 'build'},
                                          values={'image_id': image}))
        for name, content in [('stderr.txt', FIXTURE.read_bytes()), ('result.json', json.dumps({'image_id': image}).encode())]:
            store.put_artifact('t', 'lab:' + name, content, 'text/plain', None)
        store.append_observation('t', dict(obs_id='lab', kind='lab_result', source_artifacts=['lab:stderr.txt', 'lab:result.json'],
                                          values={'details': {'engagement_checks': {'fill_active': True}}}))
        store.create_attempt('t', dict(attempt_id='ab-run', kind='lab', idem_key='ab', fingerprint='f',
            request={'admissions': {'candidate': {'build_attempt_id': 'build', 'image': {'id': image}},
                                     'base': {'build_attempt_id': 'unknown-base'}}}))
        store.append_observation('t', dict(obs_id='ab', kind='ab_result', host_run={'attempt_id': 'ab-run'},
                                          values={'gate': 'improved', 'ratio': 1.1}))
        store.advance_decision('t', 0, dict(action={'type': 'keep_component', 'component': 'expert_fill', 'image': image},
            evidence_ids=['lab', 'ab'], reason_for_change='Synthetic decision: measured fill engagement.'))
    def tree():
        return {str(p.relative_to(home)): (hashlib.sha256(p.read_bytes()).hexdigest(), p.stat().st_mtime_ns)
                for p in home.rglob('*') if p.is_file()}
    before = tree()
    doc = load_task('t', home=home)
    assert tree() == before
    change = doc['changes'][0]
    assert change['source_commit'] == 'b' * 40
    assert change['files_changed'] == ['src/llama-context.cpp']
    assert change['engagement'] == {'fill_active': True}
    assert change['ab_result']['ratio'] == 1.1
    assert change['image_id'] == image
    assert 'built' in change['evidence_ids']
    assert doc['provenance']['task_id'] == 't'
    assert doc['totals']['demand_read_bytes'] == 5269782528
    assert 'Store API' in ' '.join(doc['notes'])
    assert render_html(doc)
