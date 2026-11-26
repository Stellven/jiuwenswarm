"""Demo board replay event builder. Every record here is a SYNTHETIC fixture (no real run data)."""
import copy
import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from jiuwenswarm.factory import demo_board as board
from jiuwenswarm.factory.node_finalize import diff, digest

T0 = 1_800_000_000.0
TASK = 'synthetic-board'
STEP = 'step checkpoint: the final node contract is ready; release the node to run it'


def prelim(node_id, preds=(), review=True):
    return dict(node_id=node_id, kind='build', objective=f'SYNTHETIC objective of {node_id}', predecessors=list(preds),
                inputs=[], outputs=[dict(name='out', kind='evidence', criteria=['keeps the planned criterion'])],
                node_limits=dict(turns=5), work=dict(eligible_ccs=['cc.alpha', 'cc.beta']),
                verifiers=[dict(output='out', verifier='cc.alpha.verify', stage='runtime acceptance', review=review,
                                inputs=dict(margin_pts=5))],
                stage='preliminary', bounds={'verifiers.out.inputs.margin_pts': 'lower'},
                slots=[dict(id='bind', at='work.bound_ccs', kind='ccs', **{'from': 'catalog'}),
                       dict(id='size', at='outputs.out.criteria', kind='criteria', **{'from': 'the census'})],
                briefing=dict(summary=f'SYNTHETIC briefing for {node_id}', facts=['a fact'], pitfalls=['a pitfall'],
                              how_to_fill=['bind: cc.alpha']))


def final_of(p):
    f = copy.deepcopy(p)
    f['stage'] = 'final'
    f.pop('slots')
    f.pop('bounds')
    f['work']['bound_ccs'] = ['cc.alpha']
    f['outputs'][0]['criteria'].append('the pack is about 269 GB')
    f['verifiers'][0]['inputs']['margin_pts'] = 4
    return f


def obs(kind, values, t, obs_id=None):
    return dict(obs_id=obs_id or f'{kind}:{t}', task_id=TASK, kind=kind, values=values, created=t)


def patch(rev, origin, body, t):
    return obs('taskgraph_patch', dict(task_id=TASK, rev=rev, parent_rev=rev - 1, decision_rev=0, origin=origin,
                                       patch=body, created=t), t, f'{TASK}:plan:{rev}')


def gnode(node_id, deps=()):
    return dict(node_id=node_id, kind='build', title=f'SYNTHETIC {node_id}', node_contract=node_id, depends_on=list(deps),
                attempt_ids=[], evidence_ids=[], inputs=[], capability=None, state='proposed', reason='')


def fixture():
    """A SYNTHETIC three-step run: finalize, refusal, step hold, release, capped job, advisory check, done,
    pause and resume, then an operator revise that removes one step, adds one and rewires another."""
    a, b, c = prelim('a'), prelim('b', ['a'], review='advisory'), prelim('c', ['b'])
    fa = final_of(a)
    record = dict(node_id='a', node_contract='a', digest=digest(fa), preliminary_digest=digest(a), final=fa,
                  diff=diff(a, fa), rationale='Bind cc.alpha for the build. For the size slot, the census says 269 GB.',
                  by='scheduler-agent', cc_versions={'cc.alpha': '1.0.0'}, created=T0 + 20)
    check_spec = dict(outputs=[dict(name='out', kind='evidence', required=True, review=True)])
    observations = [
        patch(1, 'seed', dict(add=[gnode('a'), gnode('b', ['a']), gnode('c', ['b'])]), T0),
        obs('node_contract_refusal', dict(node_id='a', node_contract='a', by='operator-test', rationale='loosen the margin',
                                          problems=['verifiers.out.inputs.margin_pts: 8 is above 5; it may only go down']), T0 + 10),
        obs('node_contract_final', record, T0 + 20),
        patch(2, 'scheduler', dict(finalize=[dict(node_id='a', digest=record['digest'], check=check_spec)]), T0 + 20.5),
        patch(3, 'operator', dict(hold=[dict(node_id='a', reason=STEP)]), T0 + 21),
        patch(4, 'operator', dict(release=[dict(node_id='a', reason='step checkpoint passed')]), T0 + 30),
        obs('capped_run', dict(attempt_id='job1', node_id='a', recipe='quantize', outcome='ok', seconds=8160.0,
                               memory_cap='96G', request=dict(recipe='quantize', node_id='a', name='pack'),
                               result=dict(bytes=267_217_592_800, probe=False), error=None), T0 + 8240),
        obs('node_check', dict(node_id='a', output='out', state='running', passed=False, kind='evidence', key='k1'), T0 + 8250),
        obs('node_check', dict(node_id='a', output='out', state='finished', passed=False, kind='evidence', key='k1',
                               reason='reviewer found 1 blocker(s): show the text',
                               review=dict(verdict='fail', summary='no text shown', findings=[dict(severity='blocker', problem='show the text')])),
            T0 + 8260),
        obs('node_check', dict(node_id='a', output='out', state='finished', passed=True, kind='evidence', key='k2', reason='passed',
                               verifier=dict(cc='cc.alpha', capability='verify', passed=True, stage_reached='runtime acceptance',
                                             checks=[dict(name='x', status='pass')]),
                               review=dict(verdict='fail', summary='style nit', advisory=True,
                                           findings=[dict(severity='blocker', problem='rename a variable')]),
                               entry=dict(review='advisory')), T0 + 8300),
        patch(5, 'decision', dict(update=[dict(node_id='a', state='done', evidence_ids=['e1'])]), T0 + 8400),
        obs('operator_pause', dict(action='pause', reason='replan', by='operator', at=T0 + 8500, cancel_jobs=False), T0 + 8500),
        patch(6, 'operator', dict(revise=[
            dict(node_id='c', action='cancel', reason='rev 8 drops c'),
            dict(node_id='d', action='add', reason='rev 8 adds d', node=gnode('d', ['b'])),
            dict(node_id='b', action='update', reason='rev 8 rewires b', depends_on=['a'], unfinalize=True)]), T0 + 8600),
        obs('operator_pause', dict(action='resume', reason='rev 8 applied', by='operator', at=T0 + 8700), T0 + 8700),
    ]
    attempts = [dict(attempt_id='job1', task_id=TASK, kind='model_run', state='succeeded', started=T0 + 80, ended=T0 + 8240,
                     request=dict(recipe='quantize', node_id='a', name='pack'),
                     history=[dict(state='queued', created=T0 + 70), dict(state='running', created=T0 + 80),
                              dict(state='succeeded', created=T0 + 8240)])]
    data = dict(tasks=[dict(task_id=TASK, objective='SYNTHETIC', contract_id='synthetic', created=T0)],
                observations=observations, attempts=attempts, decisions=[], _meta=dict(budget_used=dict(turns=3)))
    current = ('synthetic rev 8', dict(contract_id='synthetic', version=8, title='SYNTHETIC rev 8',
                                       arms=[dict(id='A', role='baseline', summary='cited')],
                                       extensions={'factory.node-contracts': dict(nodes=[a, b, prelim('d', ['b']), prelim('e', ['d'])])}))
    return data, current


def build(**extra):
    data, current = fixture()
    return board.build_replay(data, current=current, **extra)


def at(result, kind, node=None):
    return [e for e in result['events'] if e['kind'] == kind and (node is None or e['node'] == node)]


def test_events_are_ordered_and_plain():
    result = build()
    times = [e['t'] for e in result['events']]
    assert times == sorted(times)
    assert [e['i'] for e in result['events']] == list(range(len(result['events'])))
    kinds = [e['kind'] for e in result['events']]
    for kind in ('plan', 'refusal', 'finalize', 'step_hold', 'release', 'run_start', 'run', 'check', 'done', 'pause',
                 'revise', 'resume'):
        assert kind in kinds, kind
    assert kinds.index('refusal') < kinds.index('finalize') < kinds.index('step_hold') < kinds.index('release')
    run = at(result, 'run')[0]
    assert run['title'] == 'Quantization (pack) finished in 2 h 16 min, wrote 267.2 GB'
    refusal = at(result, 'refusal')[0]
    assert 'never weaker' in refusal['title'] and 'operator-test' in refusal['detail']


def test_node_states_follow_the_run():
    result = build()
    state = lambda kind, node='a', n=0: at(result, kind, node)[n]['states'][node]
    assert at(result, 'plan')[0]['states'] == {'a': 'ready', 'b': 'waiting', 'c': 'waiting', 'e': 'planned'}
    assert state('finalize') == 'working'
    assert state('step_hold') == 'held'
    assert state('run_start') == 'running'
    assert state('check_start') == 'checking'
    assert state('check', n=0) == 'fixing'
    assert state('check', n=1) == 'working'
    assert state('done') == 'done'
    last = result['events'][-1]['states']
    assert last['c'] == 'removed' and last['d'] == 'waiting' and last['b'] == 'ready' and last['e'] == 'planned'


def test_run_state_banner():
    result = build()
    assert at(result, 'step_hold')[0]['run']['state'] == 'step'
    job = at(result, 'run_start')[0]['run']
    assert job['state'] == 'job' and job['since'] == T0 + 80 and job['node'] == 'a'
    paused = at(result, 'pause')[0]['run']
    assert paused['state'] == 'paused' and 'replan' in paused['text']
    assert at(result, 'revise')[0]['run']['state'] == 'paused'
    assert at(result, 'resume')[0]['run']['state'] != 'paused'


def test_revise_is_one_graph_revision_with_its_changes():
    result = build()
    revise = at(result, 'revise')[0]
    assert revise['graph_rev'] == 6
    assert {(c['node'], c['action']) for c in revise['changes']} == {('c', 'cancel'), ('d', 'add'), ('b', 'update')}
    assert 'removed c' in revise['detail'] and 'added d' in revise['detail']
    assert result['skipped_ops'] == {}


def test_contract_view_prelim_vs_final():
    result = build()
    a = next(n for n in result['nodes'] if n['node_id'] == 'a')
    final = a['finals'][0]
    assert 'digest matches' in final['preliminary_source']
    assert final['preliminary']['briefing']['summary'] == 'SYNTHETIC briefing for a'
    assert [b['cc'] for b in final['bound_ccs']] == ['cc.alpha'] and final['bound_ccs'][0]['version'] == '1.0.0'
    slots = {s['id']: s for s in final['slots']}
    assert slots['bind']['value'] == ['cc.alpha']
    assert slots['size']['value'] == ['the pack is about 269 GB']
    assert 'census says 269 GB' in slots['size']['why']
    added = [c for c in final['changes'] if c['path'] == 'outputs.out.criteria'][0]
    assert added['added'] == ['the pack is about 269 GB']
    assert a['refusals'][0]['why'].startswith('never weaker')


def test_checks_mark_advisory_reviews():
    result = build()
    a = next(n for n in result['nodes'] if n['node_id'] == 'a')
    blocking, advisory = [c for c in a['checks'] if c['state'] == 'finished']
    assert blocking['review']['advisory'] is False and blocking['review']['blockers'] == ['show the text']
    assert advisory['passed'] and advisory['review']['advisory'] is True
    assert 'does not block' in at(result, 'check')[1]['detail']


def test_planned_and_dropped_steps_from_the_current_contract():
    data, current = fixture()
    data['observations'] = [o for o in data['observations'] if o['obs_id'] != f'{TASK}:plan:6']
    result = board.build_replay(data, current=current)
    nodes = {n['node_id']: n for n in result['nodes']}
    assert nodes['c']['dropped'] and 'synthetic rev 8' in nodes['c']['dropped']
    assert nodes['d']['planned'] and nodes['e']['planned']
    assert 'planned' in nodes['d']['preliminary_source']
    assert result['contract']['arms'][0]['id'] == 'A' and result['contract']['version'] == 8


def test_lenient_replay_matches_taskgraph():
    from jiuwenswarm.factory.taskgraph import replay
    data, _ = fixture()
    history = [o['values'] for o in data['observations'] if o['kind'] == 'taskgraph_patch' and o['values']['rev'] <= 5]
    graphs, skipped = board.replay_graph(history)
    for rev in range(1, 6):
        strict = {n['node_id']: n for n in replay(TASK, history, rev)['nodes']}
        for key, node in strict.items():
            for field in ('state', 'depends_on', 'hold', 'final_contract', 'evidence_ids'):
                assert graphs[rev][key].get(field) == node.get(field), (rev, key, field)
    assert not skipped
    unknown = dict(history[0], rev=6, parent_rev=5, origin='operator', patch=dict(teleport=[dict(node_id='a')]))
    assert board.replay_graph(history + [unknown])[1] == {6: ['teleport']}


def test_rebuild_preliminary_round_trip():
    p = prelim('a')
    f = final_of(p)
    rebuilt = board.rebuild_preliminary(f, diff(p, f))
    assert digest(rebuilt) == digest(p)


def test_formatting():
    assert board.human_bytes(528_942_162_176) == '528.9 GB'
    assert board.human_bytes(10_836_780_032) == '10.8 GB'
    assert board.human_bytes(1_200_000_000_000) == '1.2 TB'
    assert board.human_seconds(38.5) == '38 s'
    assert board.human_seconds(1082.9) == '18 min'
    assert board.human_seconds(8197.1) == '2 h 17 min'
    assert board.refusal_kind(['an identical final contract already ran']).startswith('repeat rule')
    assert board._scrub_paths({'p': '/home/someone/muse-demo/x'}) == {'p': '~/muse-demo/x'}


def test_read_briefs_from_scheduler_transcript(tmp_path):
    def result(outputs):
        return json.dumps(dict(status='completed', result=dict(content=[dict(type='text', text=json.dumps(dict(state='succeeded', outputs=outputs)))])))
    sid = f'{TASK}-scheduler-a-1'
    lines = [dict(t=T0, event='turn.start', node_id='a', model='gpt-6.2-astra', attempt=1),
             dict(t=T0 + 1, event_type='chat.tool_call', session_id=sid, tool_call=dict(tool_call_id='c1', name='cc.cc_call',
                  arguments=dict(cc='factory.scheduler', capability='brief', inputs=dict(node_id='a')))),
             dict(t=T0 + 2, event_type='chat.tool_result', session_id=sid, tool_call_id='c1',
                  result=result(dict(brief=dict(schema='factory.finalize-brief/2', node_id='a', task=dict(title='x'),
                                                capsules=dict(alpha='docs' * 100), briefing=dict(summary='s'))))),
             dict(t=T0 + 3, event_type='chat.tool_call', session_id=sid, tool_call=dict(tool_call_id='c2', name='cc.cc_call',
                  arguments=dict(cc='factory.scheduler', capability='propose', inputs=dict(node_id='a')))),
             dict(t=T0 + 4, event_type='chat.tool_result', session_id=sid, tool_call_id='c2',
                  result=result(dict(result=dict(admitted=False, problems=['8 is above 5'])))),
             dict(t=T0 + 5, event_type='chat.final', session_id=sid, content='Refused; I will not loosen the margin.')]
    (tmp_path / 'sessions').mkdir()
    (tmp_path / 'sessions' / f'{TASK}.scheduler.jsonl').write_text('\n'.join(json.dumps(x) for x in lines), encoding='utf-8')
    [session] = board.read_briefs(tmp_path, TASK)
    assert session['node_id'] == 'a' and session['model'] == 'gpt-6.2-astra'
    sections = [s['name'] for s in session['briefs'][0]['sections']]
    assert sections[0] == 'capsules' and 'briefing' in sections and 'schema' not in sections
    assert session['proposals'] == [dict(t=T0 + 4, admitted=False, problems=['8 is above 5'], digest=None, state='succeeded')]
    assert session['said'].startswith('Refused')


def test_operator_argv_is_narrow(tmp_path):
    argv = board.operator_argv(tmp_path, TASK, dict(action='release', node='a'))
    assert argv[-4:] == ['release', TASK, 'a', 'step checkpoint passed'] and '--home' in argv
    with pytest.raises(ValueError):
        board.operator_argv(tmp_path, TASK, dict(action='reopen', node='a', reason='x'))
    with pytest.raises(ValueError):
        board.operator_argv(tmp_path, TASK, dict(action='note', text=' '))
    with pytest.raises(ValueError):
        board.operator_argv(tmp_path, TASK, dict(action='release', node='a; rm -rf /'))


@pytest.mark.parametrize('operator', [False, True])
def test_operator_endpoint(tmp_path, operator):
    ran = []
    try:
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), board.make_handler(tmp_path, TASK, operator=operator,
                                                                         runner=lambda argv, home: ran.append(argv) or dict(returncode=0)))
    except PermissionError:
        pytest.skip('Environment prohibits socket creation')
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = Request(f'http://127.0.0.1:{server.server_port}/api/operator', method='POST',
                          data=json.dumps(dict(action='note', text='SYNTHETIC note')).encode(),
                          headers={'Content-Type': 'application/json', 'X-Board-Operator': '1'})
        if operator:
            with urlopen(request, timeout=10) as response:
                assert json.loads(response.read())['returncode'] == 0
            assert ran and ran[0][-3:] == ['note', TASK, 'SYNTHETIC note']
        else:
            with pytest.raises(HTTPError) as error:
                urlopen(request, timeout=10)
            assert error.value.code == 403 and not ran
        with urlopen(f'http://127.0.0.1:{server.server_port}/', timeout=10) as response:
            page = response.read().decode('utf-8')
        assert 'Factory demo board' in page and 'innerHTML' not in page and 'https://' not in page
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
