"""Ordinary local subprocess interoperability; never confinement qualification."""
import asyncio
import base64
import copy
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets import registered_helper
from jiuwenswarm.research_rsi.targets.unrelated_helper import NORMALIZE_LABELS_PARENT
from jiuwenswarm.research_rsi.worker import (
    WorkerClient, WORKER_PROGRAM, timing_program, validate_profile, worker_program,
)

PIN = {'id': 'unit:pinned', 'sha256': 'a' * 64}
ROOT = Path(__file__).parents[3]


def ranking_input():
    return {'scores': [dict(idea_id=name, novelty=n, feasibility=3, compute_alignment=4, eligible=True)
                       for name, n in [('z', 5), ('a', 5), ('c', 1)]]}


def test_registry_is_finite_immutable_and_does_not_expand_input_contracts():
    helper = registered_helper('ranking-v1')
    assert helper.input_name == 'scores' and helper.entrypoint == 'rank_opportunities'
    assert helper.reference(ranking_input())['selected_idea_id'] == 'a'
    with pytest.raises(FrozenInstanceError): helper.entrypoint = 'eval'
    for name in ('module:untrusted', 'os.system', '', None, {}, 'normalize-labels-v2'):
        with pytest.raises(ValueError): registered_helper(name)
    for value in ({'scores': [{}] * 4}, {'scores': [], 'command': 'untrusted'}, {'labels': []}, {'scores': ['bad-shape']}):
        with pytest.raises(ValueError): helper.validate_inputs(value)
    # Empty lists and semantic negatives stay the candidate/mandatory oracle's
    # responsibility; structural validation does not replace parent behavior.
    assert helper.validate_inputs({'scores': []}) == {'scores': []}
    other = registered_helper('normalize-labels-v1')
    assert other.input_name == 'labels' and other.entrypoint == 'normalize_labels'
    assert other.reference({'labels': ['  Alpha  BETA', 'alpha beta', '', 'Straße', 'STRASSE']}) == {'labels': ['alpha beta', 'strasse']}
    for value in ({'labels': [1]}, {'labels': ['x'] * 257}, {'labels': ['x' * 257]}, {'scores': []}):
        with pytest.raises(ValueError): other.validate_inputs(value)


def test_profile_revision_two_adds_only_registered_fixed_responsibilities():
    profile = dict(schema='ai4r-rsi-worker-profile:1', target_kind='ranking-v1', session_ref=PIN,
                   target_ref=PIN, parent_ref=PIN, contract_ref=PIN, environment_ref=PIN,
                   hardware_ref=PIN, memory_mb=128, pids_max=8, timeout_s=2)
    assert validate_profile(profile) == profile
    with pytest.raises(ValueError): validate_profile(dict(profile, target_kind='normalize-labels-v1'))
    assert validate_profile(dict(profile, schema='ai4r-rsi-worker-profile:2', target_kind='normalize-labels-v1'))
    for changed in (dict(profile, schema='ai4r-rsi-worker-profile:3'),
                    dict(profile, schema='ai4r-rsi-worker-profile:2', target_kind='arbitrary'),
                    dict(profile, factory='untrusted')):
        with pytest.raises(ValueError): validate_profile(changed)


def test_visible_input_validator_is_strict_without_changing_worker_negative_fixture_access():
    helper = registered_helper('ranking-v1')
    assert helper.validate_visible_inputs(ranking_input()) == ranking_input()
    negative = [{'scores': []}]
    for name, invalid in [('idea_id', ''), ('idea_id', None), ('eligible', 1), ('novelty', True),
                          ('feasibility', 0), ('compute_alignment', 6), ('novelty', 1.0)]:
        data = ranking_input(); data['scores'][0][name] = invalid; negative.append(data)
    data = ranking_input(); data['scores'][0]['idea_id'] = data['scores'][1]['idea_id']; negative.append(data)
    data = ranking_input()
    for row in data['scores']: row['eligible'] = False
    negative.append(data)
    data = ranking_input(); data['scores'][0]['unapproved_detail'] = 'not in minimized projection'; negative.append(data)
    for data in negative:
        assert helper.validate_inputs(data) == data
        with pytest.raises(ValueError): helper.validate_visible_inputs(data)
    other = registered_helper('normalize-labels-v1')
    assert other.validate_visible_inputs({'labels': []}) == {'labels': []}
    with pytest.raises(ValueError): other.validate_visible_inputs({'labels': [1]})


def run_public_program(tmp_path, source, data, program):
    # Translate only the two fixed resource paths in the harness. The installed
    # generated program is executed unchanged in an ordinary local subprocess.
    (tmp_path / 'body.py').write_bytes(source)
    (tmp_path / 'input.json').write_text(json.dumps(data), encoding='utf-8')
    (tmp_path / 'program.py').write_bytes(program)
    harness = r'''
import builtins,pathlib,runpy,sys
root=pathlib.Path(sys.argv[1]);program=(root/'program.py').read_bytes()
original_open=builtins.open;original_run=runpy.run_path
def open_resource(path,*args,**kwargs):
    if path=='/resources/input.json':path=root/'input.json'
    return original_open(path,*args,**kwargs)
def run_resource(path,*args,**kwargs):
    assert path=='/resources/body.py'
    return original_run(str(root/'body.py'),*args,**kwargs)
builtins.open=open_resource;runpy.run_path=run_resource
exec(compile(program,'<installed-finite-worker-program>','exec'),{})
'''
    result = subprocess.run([sys.executable, '-I', '-B', '-c', harness, str(tmp_path)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize('kind', ['ranking-v1', 'normalize-labels-v1'])
@pytest.mark.parametrize('timed', [False, True])
def test_same_program_builder_executes_two_distinct_helper_responsibilities(tmp_path, kind, timed):
    data = ranking_input() if kind == 'ranking-v1' else {'labels': ['Alpha  BETA', ' alpha beta ', '', 'B']}
    source = (ROOT / 'jiuwenswarm/research/resources/capsules/ranking_parent.txt').read_bytes() if kind == 'ranking-v1' else NORMALIZE_LABELS_PARENT
    program = timing_program(4, kind) if timed else worker_program(kind)
    before = copy.deepcopy(data)
    assert run_public_program(tmp_path, source, data, program) == registered_helper(kind).reference(data)
    assert before == data


@pytest.mark.parametrize('kind', ['ranking-v1', 'normalize-labels-v1'])
def test_generated_timing_program_executes_exact_frozen_iterations(tmp_path, kind):
    helper = registered_helper(kind)
    source = f"calls=0\ndef {helper.entrypoint}(value):\n global calls\n calls+=1\n return {{'calls':calls}}\n".encode()
    data = ranking_input() if kind == 'ranking-v1' else {'labels': []}
    assert run_public_program(tmp_path, source, data, timing_program(7, kind)) == {'calls': 7}


def test_ranking_default_program_bytes_remain_historical():
    assert worker_program() == WORKER_PROGRAM
    expected = ("import json,runpy,sys\nmodule=runpy.run_path('/resources/body.py')\n"
                "value=json.load(open('/resources/input.json'))\n"
                "for _ in range(7):\n result=module['rank_opportunities'](value['scores'])\n"
                "sys.stdout.write(json.dumps(result,sort_keys=True,separators=(',',':'),allow_nan=False))\n").encode()
    assert timing_program(7) == expected
    for bad in (0, -1, True, 2.0):
        with pytest.raises(ValueError): timing_program(bad)
    with pytest.raises(ValueError): timing_program(1, 'arbitrary')
    with pytest.raises(ValueError): worker_program('arbitrary')


def unit_response(store, request, program, iterations):
    pins = [store.put_bytes(value) for value in (b'{"unit":"response transfer control"}', b'', b'{"unit":"no runtime observation"}')]
    return dict(schema='ai4r-rsi-worker-response:2', request=copy.deepcopy(request),
                receipt={'stdout_ref': pins[0], 'stderr_ref': pins[1], 'observed_limits': {'isolation_probe_ref': pins[2]}},
                captures=[{'ref': pin, 'bytes_base64': base64.b64encode(store.read(pin)).decode()} for pin in pins],
                program_sha256=hashlib.sha256(program).hexdigest(), batch_iterations=iterations)


@pytest.mark.parametrize('kind', ['ranking-v1', 'normalize-labels-v1'])
@pytest.mark.parametrize('timed', [False, True])
def test_actual_client_validates_program_request_and_exact_capture_transfer(tmp_path, kind, timed):
    store = RecordStore(tmp_path); client = object.__new__(WorkerClient)
    client.requests=store;client.profile_ref=PIN;client.session_ref=PIN;client.hidden=True
    client.timeout_s=2;client.target_kind=kind;client.batch_iterations=7
    async def rpc(operation, value, **kwargs):
        assert operation == ('run_timing_batch' if timed else 'run_helper')
        program = timing_program(7, kind) if timed else worker_program(kind)
        return unit_response(store, value, program, 7 if timed else 1)
    client.rpc = SimpleNamespace(call=rpc)
    data = ranking_input() if kind == 'ranking-v1' else {'labels': ['public']}
    result = asyncio.run(client.run(PIN, data, phase='hidden_final', reservation_ref=PIN, timing=timed))
    assert result['batch_iterations'] == (7 if timed else 1)
    store.close()


@pytest.mark.parametrize('field', ['schema', 'request', 'program_sha256', 'batch_iterations', 'captures', 'extra'])
def test_client_refuses_response_substitution_without_publishing_bad_capture(tmp_path, field):
    store = RecordStore(tmp_path); client = object.__new__(WorkerClient)
    client.requests=store;client.profile_ref=PIN;client.session_ref=PIN;client.hidden=True
    client.timeout_s=2;client.target_kind='ranking-v1';client.batch_iterations=7
    async def rpc(operation, value, **kwargs):
        result = unit_response(store, value, timing_program(7), 7)
        if field == 'schema': result['schema'] = 'ai4r-rsi-worker-response:1'
        elif field == 'request': result['request']['repeat_index'] = 1
        elif field == 'program_sha256': result[field] = 'b' * 64
        elif field == 'batch_iterations': result[field] = 8
        elif field == 'captures': result[field].reverse()
        else: result['factory'] = 'untrusted'
        return result
    client.rpc = SimpleNamespace(call=rpc)
    with pytest.raises(ValueError):
        asyncio.run(client.run(PIN, ranking_input(), phase='hidden_final', reservation_ref=PIN, timing=True))
    store.close()


def test_client_without_frozen_timing_count_refuses_before_rpc(tmp_path):
    store = RecordStore(tmp_path); client = object.__new__(WorkerClient)
    client.requests=store;client.profile_ref=PIN;client.session_ref=PIN;client.hidden=True
    client.timeout_s=2;client.target_kind='ranking-v1';client.batch_iterations=None
    async def unexpected(*args, **kwargs): raise AssertionError('No execution is authorized')
    client.rpc = SimpleNamespace(call=unexpected)
    with pytest.raises(ValueError, match='Frozen client timing batch count required'):
        asyncio.run(client.run(PIN, ranking_input(), phase='hidden_final', reservation_ref=PIN, timing=True))
    store.close()


@pytest.mark.parametrize('kind', ['ranking-v1', 'normalize-labels-v1'])
@pytest.mark.parametrize('timed', [False, True])
def test_same_broker_dispatches_registered_program_and_attests_exact_execution_bytes(tmp_path, monkeypatch, kind, timed):
    """Real broker dispatch + local subprocess double, no kernel qualification."""
    from jiuwenswarm.research_rsi.records import encoded
    from jiuwenswarm.research_rsi.worker import WorkerBroker
    from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
    source = (ROOT / 'jiuwenswarm/research/resources/capsules/ranking_parent.txt').read_bytes() if kind == 'ranking-v1' else NORMALIZE_LABELS_PARENT
    data = ranking_input() if kind == 'ranking-v1' else {'labels': [' B ', 'b', 'A']}
    store = RecordStore(tmp_path / 'public-unit-captures')
    broker = object.__new__(WorkerBroker); broker.root = tmp_path / 'broker'; broker.root.mkdir()
    for name in ('assets', 'work'): (broker.root / name).mkdir()
    broker.qualification=ControlledQualification();broker.hidden=True
    broker.claims=set();broker.lock=asyncio.Lock();broker.cancelled=set();broker.issued={};broker.job_sessions={};broker.tasks={}
    profile=dict(schema='ai4r-rsi-worker-profile:2', target_kind=kind, session_ref=PIN,
                 target_ref=PIN, parent_ref=PIN, contract_ref=PIN, environment_ref=PIN,
                 hardware_ref=PIN, memory_mb=128, pids_max=8, timeout_s=2)
    broker.profiles={encoded(PIN):validate_profile(profile)}
    reservation=dict(session_ref=PIN, candidate_ref=PIN, phase='hidden_final', operation='timing:unit' if timed else 'unit:ordinary')
    broker.public=SimpleNamespace(get=lambda pin:{'scoring':{'batch_iterations':7}}, read=lambda pin:source)
    broker.inputs=SimpleNamespace(get=lambda pin:reservation, read=lambda pin:encoded(data));broker.capture=store
    # UID ownership is deliberately a double in this ordinary execution test.
    monkeypatch.setattr('jiuwenswarm.research_rsi.worker.os.chown', lambda *args:None, raising=False)
    observed=[]
    async def ordinary_executor(job):
        files={mount.target:mount.source.read_bytes() for mount in job.readonly_mounts}
        observed.append(files['/resources/worker.py'])
        directory=tmp_path/'ordinary';directory.mkdir()
        output=run_public_program(directory,files['/resources/body.py'],json.loads(files['/resources/input.json']),files['/resources/worker.py'])
        stdout=store.put_bytes(encoded(output));stderr=store.put_bytes(b'')
        proof=store.put({'unit':'Ordinary subprocess double; confinement NOT_RUN'})
        return {'stdout_ref':stdout,'stderr_ref':stderr,'observed_limits':{'isolation_probe_ref':proof}}
    broker.executor=SimpleNamespace(run=ordinary_executor)
    request=dict(profile_ref=PIN,session_ref=PIN,candidate_ref=PIN,input_ref=PIN,reservation_ref=PIN,phase='hidden_final',repeat_index=0)
    response=asyncio.run(broker.run(request,timing=timed))
    expected=timing_program(7,kind) if timed else worker_program(kind)
    assert observed==[expected]
    assert response['schema']=='ai4r-rsi-worker-response:2' and response['request']==request
    assert response['program_sha256']==hashlib.sha256(expected).hexdigest()
    assert response['batch_iterations']==(7 if timed else 1)
    assert store.get(response['receipt']['stdout_ref'])==registered_helper(kind).reference(data)
    raw=[json.loads(path.read_bytes()) for path in store.root.glob('*.json') if path.read_bytes().startswith(b'{')]
    receipts=[value for value in raw if value.get('schema')=='ai4r-rsi-worker-receipt:1']
    assert len(receipts)==1 and set(receipts[0])=={'schema','request','receipt'}
    store.close()
