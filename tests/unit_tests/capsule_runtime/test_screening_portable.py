"""Screening (m1-4) through the portable runtime: same pins, checks and verifier as the pipeline, fake models only."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.capsule_runtime import Runtime
from jiuwenswarm.research.state import json_bytes

from .test_intent_portable import verdict
from .test_evaluation_portable import tamper

SOURCE = Path('tests/fixtures/research/pipeline/source-valid')
SCREEN = 'research.screening'


def load(name):
    value = json.loads((SOURCE / (name + '.json')).read_text('utf-8'))
    value.pop('ext', None)
    return value


def sha(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def inputs():
    brief = json.loads(Path('tests/fixtures/research/compiler/research_brief.json').read_text('utf-8'))
    return {'brief': brief, 'candidate_set': load('candidate_set')}


def reply(mutate=None):
    value = {'scores': copy.deepcopy(load('screening_result')['scores']),
             'opportunity_statement': load('opportunity_card')['opportunity_statement']}
    if mutate:
        mutate(value)
    return value


class Worker:
    def __init__(self, value):
        self.text = value if isinstance(value, str) else json.dumps(value)
        self.calls = []

    async def __call__(self, prompt, system=None):
        self.calls.append((prompt, system))
        return self.text


@pytest.fixture(scope='module')
def rt():
    runtime = Runtime()
    result = runtime.admit(SCREEN)
    assert result['passed'], result['failures']
    return runtime


def run(rt, value, verifier=verdict(), given=None):
    return rt.invoke(SCREEN, given if given is not None else inputs(), worker_model=Worker(value), verifier_model=verifier)


def test_valid_reply_delivers_what_the_pipeline_would_capture(rt):
    given = inputs()
    out = rt.invoke('research.screening', given, worker_model=Worker(reply()), verifier_model=verdict())
    assert out['status'] == 'delivered', out.get('halt')
    result, card = out['outputs']['screening_result'], out['outputs']['opportunity_card']
    fixture, fixture_card = load('screening_result'), load('opportunity_card')
    # Same scores, ranking and selection as the pipeline fixture; only the bound refs are real.
    assert result['candidate_ref']['sha256'] == sha(given['candidate_set']) and result['brief_ref']['sha256'] == sha(given['brief'])
    for key in ('scores', 'ranking', 'selected_idea_id'):
        assert result[key] == fixture[key]
    assert card['screening_ref'] == {'id': 'blob:' + sha(result), 'sha256': sha(result)}
    for key in ('idea_id', 'opportunity_statement', 'scores', 'rank', 'other_dispositions'):
        assert card[key] == fixture_card[key], key
    idea = next(i for i in given['candidate_set']['ideas'] if i['idea_id'] == result['selected_idea_id'])
    for key in ('title', 'summary', 'citation_ids', 'assumptions', 'risks'):  # the carrier copies these from the selected idea
        assert card[key] == idea[key], key
    assert set(card['constraints']) >= {c['text'] for c in given['brief']['constraints']}
    receipt = out['receipt']
    assert receipt['capability_id'] == SCREEN and receipt['version'] == 'm1-4'
    assert all(c['outcome'] == 'PASS' for c in receipt['checks']) and len(receipt['checks']) >= 12
    assert {'candidate_binding', 'rubric_pinned', 'ranking_deterministic', 'selected_is_top1'} <= {c['check_id'] for c in receipt['checks']}
    assert receipt['verifiers']['semantic'] == 'pass' and receipt['semantic_verifier']['status'] == 'reviewed'
    assert len(receipt['semantic_verifier']['reviews']) == 2
    assert {row['check'] for row in receipt['not_applicable_outside_pipeline']} >= {'input_provenance', 'host_record_custody'}
    assert len(receipt['model_calls']) == 1


def test_invalid_reply_halts_at_the_worker_with_the_product_code(rt):
    out = run(rt, 'not json')
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'worker' and out['halt']['code'] == 'invalid_output'
    out = run(rt, reply(lambda v: v['scores'][0].update(novelty='high')))
    assert out['halt']['stage'] == 'worker' and 'integers in 1..5' in out['halt']['reason']


def test_bad_scores_halt_at_the_ranker_or_the_stage_check(rt):
    out = run(rt, reply(lambda v: v.update(scores=v['scores'][1:])))  # an idea left out of the ranking
    assert out['status'] == 'halted' and out['halt']['stage'] == 'worker' and 'outputs' not in out
    out = run(rt, reply(lambda v: v['scores'][0].update(citation_ids=['not-a-citation-of-this-idea'])))
    assert out['halt']['stage'] == 'verifier' and out['halt']['code'] == 'check_failed' and 'score_citations_in_idea' in out['halt']['reason']
    assert 'outputs' not in out


def test_verifier_fail_halts_and_delivers_nothing(rt):
    out = run(rt, reply(), verifier=verdict('FAIL'))
    assert out['status'] == 'halted' and 'outputs' not in out
    assert out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'semantic_fail'


def test_no_verifier_model_is_never_delivered(rt):
    out = rt.invoke(SCREEN, inputs(), worker_model=Worker(reply()))
    assert out['status'] == 'halted' and out['halt']['stage'] == 'semantic_verifier' and out['halt']['code'] == 'no_model'


def test_input_guard(rt):
    broken = inputs()
    del broken['candidate_set']['ideas']
    for bad, code in [({}, 'missing_input'), ({'brief': inputs()['brief']}, 'missing_input'),
                      ({**inputs(), 'screening_rubric': {}}, 'unknown_input'), (broken, None)]:
        worker = Worker(reply())
        out = rt.invoke(SCREEN, bad, worker_model=worker, verifier_model=verdict())
        assert out['halt']['stage'] == 'input_guard'
        if code:
            assert out['halt']['code'] == code
        assert worker.calls == []


@pytest.mark.parametrize('target', ['research/capsules/screening.py', 'research/capsules/ranking.py',
                                    'research/resources/capsules/screening_rubric.json', 'research/checks/research.py'])
def test_tampered_pin_refuses_at_call_time(rt, monkeypatch, target):
    tamper(monkeypatch, target)
    worker = Worker(reply())
    out = run(rt, worker.text)
    assert out['status'] == 'halted' and out['halt']['stage'] == 'pin'


def test_tampered_pin_refuses_at_load(monkeypatch):
    tamper(monkeypatch, 'research/resources/capsules/screening_prompt.txt')
    fresh = Runtime()
    assert next(r for r in fresh.list() if r['id'] == SCREEN)['status'] == 'refused'
    out = fresh.invoke(SCREEN, inputs(), worker_model=Worker(reply()), require_admission=False)
    assert out['halt']['stage'] == 'pin'


def test_describe_and_mcp_schema(rt):
    from jiuwenswarm.capsule_runtime.mcp import Server, tool_for
    tool = tool_for(rt, SCREEN)
    props = tool['inputSchema']['properties']
    assert set(props) == {'brief', 'candidate_set'} and sorted(tool['inputSchema']['required']) == ['brief', 'candidate_set']
    assert 'task_objective' not in props and all(p['description'] for p in props.values())
    info = rt.describe(SCREEN)
    assert info['needs_model'] and 'semantic verifier: applies' in ' '.join(info['verifier_stages'])
    server = Server(rt, verdict())
    server.client_sampling = True
    assert SCREEN in server.visible()


def test_runtime_without_builtin_has_no_stage_capsules():
    assert SCREEN not in Runtime([], include_builtin=False).capsules
