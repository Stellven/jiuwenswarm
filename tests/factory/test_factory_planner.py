"""Planner projection tests use detached records and never launch the factory."""
from hashlib import sha256
import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jiuwenswarm.factory.node_finalize import diff, digest
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes
from jiuwenswarm.gateway.channel_manager.web.factory_planner import ARTIFACT_PATH, project


def observation(id, kind, created, values, task_id='run'):
    return dict(obs_id=id, task_id=task_id, kind=kind, created=created, values=values)


def node(id, dependencies=()):
    return dict(node_id=id, node_contract=id, title=f'Plan {id}', depends_on=list(dependencies))


def test_only_native_revisions_mark_membership_and_order_edits():
    a, b, c, e = node('a'), node('b'), node('c'), node('e')
    d = node('d')
    data = dict(tasks=[dict(task_id='run')], observations=[
        observation('seed', 'taskgraph_patch', 2, dict(origin='seed', rev=1, patch=dict(add=[a, b, c, e]))),
        observation('b-done', 'taskgraph_patch', 3, dict(origin='decision', rev=2,
                    patch=dict(update=[dict(node_id='b', state='done')]))),
        observation('e-done', 'taskgraph_patch', 4, dict(origin='decision', rev=3,
                    patch=dict(update=[dict(node_id='e', state='done')]))),
        observation('edits', 'taskgraph_patch', 5, dict(origin='operator', rev=4, patch=dict(revise=[
            dict(node_id='a', action='update', depends_on=['b']),
            dict(node_id='c', action='cancel'),
            dict(node_id='d', action='add', node=d),
        ]))),
    ])
    graph = dict(nodes=[dict(a, depends_on=['b']), dict(b, state='done'), dict(c, state='cancelled'),
                        dict(e, state='done'), d])
    plan = project(data, graph, [])
    assert plan['plan_order'] == ['a', 'b', 'c', 'e']
    assert plan['run_order'] == ['b', 'e', 'a', 'd']
    nodes = {row['node_id']: row for row in plan['nodes']}
    assert {name: row['change'] for name, row in nodes.items()} == dict(
        a='reordered', b='unchanged', c='removed', d='added', e='unchanged',
    )
    assert {nodes[name]['change_source']['origin'] for name in ('a', 'c', 'd')} == {'operator'}
    assert {nodes[name]['change_source']['id'] for name in ('a', 'c', 'd')} == {'edits'}


def preliminary(title):
    return dict(node_id='a', stage='preliminary', objective=title, outputs=[], verifiers=[],
                work=dict(helpful_ccs=['cc.suggested'], bound_ccs=[]))


def document(node, version):
    return dict(contract_id='contract', version=version, extensions={'factory.node-contracts': dict(nodes=[node])})


def test_draft_uses_original_contract_and_finals_keep_native_before_values_and_refusals():
    original, revised = preliminary('before the scheduler'), preliminary('operator updated the objective')
    old_doc, new_doc = document(original, 1), document(revised, 2)
    final = dict(revised, stage='final', work=dict(helpful_ccs=['cc.suggested'], bound_ccs=['cc.bound']))
    a, b = node('a'), node('b')
    data = dict(tasks=[dict(task_id='run')], _contract=new_doc, observations=[
        observation('foreign', 'planner_read_receipt', 0, {}, task_id='other'),
        observation('read', 'planner_read_receipt', 1, dict(artifact_id='source')),
        observation('seed', 'taskgraph_patch', 2, dict(origin='seed', rev=1, planner='native',
                    patch=dict(add=[a, b]))),
        observation('late', 'planner_read_receipt', 3, dict(artifact_id='later')),
        observation('contract-revision', 'operator_contract_revision', 4, dict(previous_sha256='old')),
        observation('refusal', 'node_contract_refusal', 5, dict(node_id='a', problems=['host refused'])),
        observation('final', 'node_contract_final', 6, dict(
            node_id='a', node_contract='a', final=final, digest=digest(final),
            preliminary_digest=digest(revised), diff=diff(revised, final),
        )),
        observation('bad', 'node_contract_final', 7, dict(
            node_id='a', final=final, digest='wrong', preliminary_digest='unmatched', diff=[],
        )),
    ])
    contracts = [
        dict(document=old_doc, source=dict(kind='contract-file', path='old.json', sha256='old')),
        dict(document=new_doc, source=dict(kind='contract-file', path='new.json', sha256='new')),
    ]
    output = project(data, dict(nodes=[a, b]), contracts, 'records/observations.json')
    a, b = output['nodes']
    assert a['draft'] == original
    assert a['draft_source']['digest'] == digest(original)
    assert a['suggested_ccs'] == ['cc.suggested']
    assert b['draft'] is None
    assert [row['id'] for row in output['read_receipts']] == ['read']
    admitted, tampered = a['finals']
    assert admitted['never_weaker']['status'] == 'admitted'
    assert admitted['preliminary'] == revised and admitted['preliminary_source']['path'] == 'new.json'
    assert admitted['diff'] == diff(revised, final)
    assert tampered['never_weaker']['status'] == 'unverified' and tampered['preliminary'] is None
    assert a['refusals'][0]['never_weaker']['status'] == 'refused'
    assert a['refusals'][0]['problems'] == ['host refused']
    assert output['artifact']['sha256'] == sha256(output['_file']['content'].encode()).hexdigest()
    assert 'cc.bound' not in output['_file']['content']


def test_exact_final_diff_can_recover_its_draft_when_contract_is_missing():
    manual = preliminary('before')
    final = dict(manual, stage='final')
    data = dict(tasks=[dict(task_id='run')], observations=[
        observation('seed', 'taskgraph_patch', 1, dict(origin='seed', rev=1, patch=dict(add=[node('a')]))),
        observation('native-final', 'node_contract_final', 2,
                    dict(node_id='a', final=final, preliminary_digest=digest(manual),
                         digest=digest(final), diff=diff(manual, final))),
    ])
    result, = project(data, dict(nodes=[node('a')]), [])['nodes']
    assert result['draft'] is None
    final_row, = result['finals']
    assert final_row['preliminary'] == manual
    assert final_row['preliminary_source']['kind'] == 'diff-reconstruction'
    assert final_row['preliminary_source']['id'] == 'native-final'


def test_virtual_plan_file_uses_generic_http_file_reader(tmp_path):
    bundle = tmp_path / 'bundle'
    (bundle / 'records').mkdir(parents=True)
    (bundle / 'records/tasks.json').write_text(json.dumps([dict(task_id='run', objective='Read plan')]))
    native_node = dict(node('a'), kind='inspect')
    seed = observation('run:plan:1', 'taskgraph_patch', 1, dict(
        origin='seed', task_id='run', rev=1, parent_rev=0, decision_rev=0, created=1,
        planner='native', patch=dict(add=[native_node]),
    ))
    (bundle / 'records/observations.json').write_text(json.dumps([seed]))
    manifest = {p.relative_to(bundle).as_posix(): sha256(p.read_bytes()).hexdigest()
                for p in bundle.rglob('*') if p.is_file()}
    (bundle / 'MANIFEST.json').write_text(json.dumps(manifest))
    svc = FactoryHttpService(roots=[bundle])
    app = FastAPI()
    attach_factory_routes(app, service=svc)
    api = TestClient(app)
    run, = api.get('/api/factory/runs').json()['runs']
    url = f"/api/factory/runs/{run['id']}"
    detail = api.get(url).json()
    metadata = detail['planner_plan']['artifact']
    assert metadata['path'] == ARTIFACT_PATH
    response = api.get(url + '/file', params={'path': metadata['path']})
    assert response.status_code == 200
    file = response.json()
    assert sha256(file['content'].encode()).hexdigest() == metadata['sha256']
    assert json.loads(file['content'])['source']['id'] == seed['obs_id']
    assert not (bundle / ARTIFACT_PATH).exists()
