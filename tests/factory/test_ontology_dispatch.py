"""F21 offline evidence/dispatch checks; no engine, Docker, compiler or GPU."""
import json
from pathlib import Path

import jsonschema
import pytest

from jiuwenswarm.factory import components, ontology
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.builder import Builder
from jiuwenswarm.factory.expert_streaming import applicability, parse_engagement
from jiuwenswarm.factory.jobs import Jobs
from jiuwenswarm.factory.manager import Manager
from jiuwenswarm.factory.taskgraph import plan_get, plan_patch


def node(key, **fields):
    return dict(node_id=key, kind='inspect', title=key, **fields)


def test_ontology_and_component_ids():
    vocab = ontology.load()
    assert (vocab['id'], vocab['version'], vocab['status']) == ('satay.engine-ontology', '0.1', 'provisional')
    assert len(ontology.PATH.read_text().splitlines()) <= 150
    schema = json.loads((ontology.PATH.parents[2] / 'schemas/component.schema.json').read_text())
    for path in components.ROOT.glob('*/component.yaml'):
        material = components.load(path.parent.name)
        assert all(material[field] for field in ('implements', 'modifies_region', 'quantities'))
        jsonschema.validate(material, schema)
        for field, bad in [('implements', 'expert_streaming.unknown'), ('modifies_region', 'L99'), ('quantities', 'unknown.value')]:
            with pytest.raises(ValueError, match='ontology'):
                ontology.validate_component(dict(material, **{field: [bad]}))
    distinct = ['prediction.recall_at_k', 'readiness.ready_bytes_predicted', 'faults.minflt', 'decode.ms_per_token']
    for q in distinct:
        assert set(distinct) - {q} <= set(vocab['quantities'][q]['distinct_from'])


def test_applicability_ranks_evidence_gaps_and_signals(tmp_path):
    # Unavailable headers do not prevent useful, explicitly heuristic suggestions.
    result = applicability(tmp_path / 'missing.gguf', [], tmp_path / 'missing-meminfo')
    candidates = result['candidates']
    assert candidates and all('→ implements ' in c['explanation'] and '→ modifies_region ' in c['explanation']
                              and '→ quantity ' in c['explanation'] and 'ONTOLOGY.yaml' in c['explanation'] for c in candidates)
    assert [c['score'] for c in candidates] == sorted((c['score'] for c in candidates), reverse=True)
    observed = {q: 0 for q in ontology.load()['quantities']}
    observed['readiness.duplicate_demand_bytes'] = 4096
    ranked = applicability(tmp_path / 'missing.gguf', [], tmp_path / 'missing-meminfo', observed=observed)['candidates']
    join = next(c for c in ranked if c['component'] == 'inflight_join')
    assert join['bottleneck'] == ['readiness.duplicate_demand_bytes'] and not join['unmeasured']
    assert join['score'] > next(c for c in ranked if c['component'] == 'thread_names')['score']


def test_engagement_labels_and_missing_required(store):
    required = ['readiness.ready_bytes_predicted', 'readiness.missing_bytes_predicted', 'faults.minflt', 'decode.ms_per_token']
    stderr = ('expert_readiness: stats decode_ready_bytes_predicted=0\n'
              'expert_phase: stats minflt=0 tok_ns_p95=123\n'
              'eval time = 12 ms / 2 runs ( 6.00 ms per token )\n')
    parsed = parse_engagement(stderr, required)
    assert parsed['missing_required'] == ['readiness.missing_bytes_predicted']
    assert parsed['readiness']['labels']['decode_ready_bytes_predicted'] == dict(
        quantity=required[0], unit='bytes', phase='decode')
    assert parsed['phase']['labels']['minflt'] == dict(quantity='faults.minflt', unit='count', phase='decode')
    assert parsed['timings']['decode']['unit'] == 'ms/token'
    assert parse_engagement('', required)['missing_required'] == required
    fixture = (Path(__file__).parent / 'fixtures/expert_streaming/stderr.txt').read_text()
    for block in parse_engagement(fixture).values():
        if isinstance(block, dict) and 'counters' in block:
            assert all(set(row) <= block['labels'].keys() for row in block['counters'])
    attempt = store.create_attempt('t', dict(kind='lab', idem_key='e', fingerprint='e', request={}))
    inputs = dict(attempt_id=attempt['attempt_id'], requires_evidence=required)
    empty = dispatch(store.scoped('t'), 't', 'expert_streaming.engagement', dict(inputs=inputs))
    assert empty['missing_required'] == required
    artifact = store.put_artifact('t', attempt['attempt_id'] + ':stderr.txt', stderr.encode(),
                                  'text/plain', attempt['attempt_id'])
    store._db.execute('UPDATE attempts SET result_refs=? WHERE attempt_id=?',
                      (json.dumps([artifact['artifact_id']]), attempt['attempt_id']))
    result = dispatch(store.scoped('t'), 't', 'expert_streaming.engagement', dict(inputs=inputs))
    assert result['missing_required'] == parsed['missing_required']


@pytest.fixture
def submissions(store, monkeypatch):
    """Exercise real submission request creation with the queue/admission replaced."""
    calls = []
    def queue(self, task_id, kind, request, idem_key, *args):
        calls.append(request)
        return self.store.create_attempt(task_id, dict(kind=kind, request=request, idem_key=idem_key, fingerprint=idem_key))
    monkeypatch.setattr(Jobs, 'submit', queue)
    monkeypatch.setattr(Builder, '_request', lambda self, r: dict(r, deadline_s=1, env={}))
    monkeypatch.setattr(Manager, 'admit', lambda self, task, image, build: dict(admission_id='admitted', image=image))
    monkeypatch.setattr(Manager, '_admission', lambda *args: dict(admission_id='admitted'))
    monkeypatch.setattr('jiuwenswarm.factory.contract.load', lambda _: dict(
        contract_id='fixture', workload=dict(argv=[], env={}, tool='llama-cli')))
    monkeypatch.setattr('jiuwenswarm.factory.contract.reference_info', lambda _: dict(stdout_sha256='a' * 64))
    store.advance_decision('t', 0, dict(hypothesis='Use evidence before submission'))
    return calls


def submission(capability, node_id=None):
    image = dict(tag='factory/llamacpp:offline', id='sha256:' + 'a' * 64)
    if capability == 'builder.submit':
        inputs = dict(request=dict(target='jetson-orin', tag=image['tag']), idem_key='build')
    elif capability == 'lab.submit':
        inputs = dict(image=image, build_attempt_id='offline', contract_id='fixture', run_config={}, idem_key='lab')
    else:
        image = dict(image, build_attempt_id='offline')
        inputs = dict(base_image=image, candidate_image=image, base_env={}, candidate_env={},
                      rounds=1, component='thread_names', contract_id='fixture', idem_key='ab')
    if node_id is not None:
        inputs['node_id'] = node_id
    return dict(inputs=inputs)


@pytest.mark.parametrize('capability', ['builder.submit', 'lab.submit', 'lab.ab_submit'])
def test_dispatch_preconditions_and_request_link(store, submissions, capability):
    plan_patch(store, 't', {'add': [node('old'), node('replacement'), node('dependency'),
        node('ready-later', depends_on=['dependency']), node('done', state='done', evidence_ids=['t']),
        node('failed', state='failed'), node('cancelled')]}, 0, 1)
    plan_patch(store, 't', {'supersede': [dict(node_id='old', by='replacement', reason='changed approach')],
        'cancel': [dict(node_id='cancelled', reason='unneeded')]}, 1, 1)
    for key, reason in [('absent', 'does not exist'), ('old', 'superseded'), ('cancelled', 'cancelled'),
                        ('done', 'done'), ('failed', 'failed'), ('ready-later', 'dependency is proposed')]:
        with pytest.raises(ValueError, match=reason):
            dispatch(store.scoped('t'), 't', capability, submission(capability, key))
    assert not submissions
    plan_patch(store, 't', {'update': [dict(node_id='dependency', state='done', evidence_ids=['t']),
                                      dict(node_id='ready-later', state='ready')]}, 2, 1)
    result = dispatch(store.scoped('t'), 't', capability, submission(capability, 'ready-later'))
    assert store.read('t', result['attempt_id'])['request']['node_id'] == 'ready-later'


@pytest.mark.parametrize('capability', ['builder.submit', 'lab.submit', 'lab.ab_submit'])
def test_submissions_without_node_keep_existing_behavior(store, submissions, capability):
    result = dispatch(store.scoped('t'), 't', capability, submission(capability))
    assert 'node_id' not in store.read('t', result['attempt_id'])['request']


def test_pending_revision_keeps_attempt_links_and_validates_vocabulary(store):
    attempt = store.create_attempt('t', dict(kind='build', idem_key='pending', fingerprint='pending', request={}))
    store.advance_decision('t', 0, dict(hypothesis='Revise unfinished work'))
    fields = dict(outcome='Make weights ready', entities=['model:<run5:model_id>'],
                  requires_evidence=['readiness.missing_bytes_predicted'], resources={'class': 'cpu'})
    plan_patch(store, 't', {'add': [node('existing', attempt_ids=[attempt['attempt_id']], **fields), node('other')]}, 0, 1)
    graph = plan_patch(store, 't', {'update': [dict(node_id='existing', depends_on=['other'],
        outcome='Observe readiness before retrying', requires_evidence=['readiness.ready_bytes_predicted'],
        resources={'class': 'gpu'}, attempt_ids=[attempt['attempt_id']])]}, 1, 1)
    assert graph['nodes'][0]['attempt_ids'] == [attempt['attempt_id']]
    assert graph['nodes'][0]['entities'] == fields['entities']
    assert plan_get(store, 't', 1)['nodes'][0]['outcome'] == fields['outcome']
    for change in [dict(requires_evidence=['unknown.quantity']), dict(resources={'class': 'unknown'})]:
        with pytest.raises(ValueError):
            plan_patch(store, 't', {'update': [dict(node_id='existing', **change)]}, 2, 1)
