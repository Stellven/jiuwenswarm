"""Contract format 2, the lab mailbox, the lab manager and the stand-in lab agents."""
import copy
import json
from pathlib import Path
import sys
import time

import pytest

from jiuwenswarm.factory import contract, contract_v2
from jiuwenswarm.factory.api import dispatch
from jiuwenswarm.factory.lab_agent import CommandAdapter, LabAgent, QueueAdapter, serve
from jiuwenswarm.factory.lab_mailbox import Mailbox, MailboxError
from jiuwenswarm.factory.lab_manager import LabManager, report_problems
from jiuwenswarm.factory.manager import Manager
from jiuwenswarm.factory.store import ScopeDenied

from test_lab import IMAGE, lab  # noqa: F401  (fixture)

REPO = Path(__file__).resolve().parents[2]
V2 = REPO / 'jiuwenswarm/factory/contracts/star-deepseek-v2.json'
EXE = 'e' * 64


def v2():
    return json.loads(V2.read_text(encoding='utf-8'))


# ---- contract format 2 -----------------------------------------------------------------
def test_star_contract_v2_is_valid_and_loads_through_the_contract_loader():
    loaded = contract.load('star-deepseek-v2')
    assert loaded['schema'] == 'factory.contract/2' and contract_v2.problems(dict(loaded)) == []
    assert contract_v2.arms_for(loaded, ['candidate']) == ['C1', 'C2', 'C3', 'C4', 'C5']
    assert not contract_v2.is_frozen(loaded)


def test_contract_v2_inputs_match_the_repository_prompt_files():
    document = v2()
    binding = dict(model='/lab/model.gguf', inputs={name: str(REPO / spec['repo_path'])
                                                    for name, spec in document['inputs'].items()})
    assert contract_v2.verify_inputs(document, binding) == []
    resolved = contract_v2.resolve(document, binding)
    assert resolved['argv'][:2] == ['-m', '/lab/model.gguf']
    assert resolved['requests'][1]['input_path'].endswith('2048.txt')
    with pytest.raises(ValueError, match='no location'):
        contract_v2.resolve(document, dict(inputs={}))


@pytest.mark.parametrize('change,message', [
    (lambda d: d['workload']['argv'].__setitem__(1, '/home/someone/model.gguf'), 'absolute host path'),
    (lambda d: d['arms'].append(dict(d['arms'][0])), "arm id 'A' is declared twice"),
    (lambda d: d['measurement'].__setitem__('primary', 'tokens'), 'not a declared metric'),
    (lambda d: d['correctness']['checks'][0].__setitem__('applies_to', ['nobody']), 'neither an arm nor a role'),
    (lambda d: d['workload']['requests'][0].__setitem__('input', 'prompt_9'), 'unknown input'),
    (lambda d: d['correctness']['reference'].__setitem__('output_sha256', 'a' * 64), 'needs frozen_at and run_ref'),
    (lambda d: d.__setitem__('notes', 'free text'), 'Additional properties'),
    (lambda d: d['measurement']['derived']['gap_closed'].__setitem__('uses', ['client_ttft_ms', 'Q']), 'neither a metric nor an arm'),
])
def test_contract_v2_names_each_problem(change, message):
    document = v2()
    change(document)
    assert any(message in problem for problem in contract_v2.problems(document)), contract_v2.problems(document)


def test_contract_v2_extensions_hold_anything_and_host_paths_there_are_allowed():
    document = v2()
    document['extensions']['spark.binding'] = {'model': '/home/lab/model.gguf'}
    assert contract_v2.problems(document) == []


def test_contract_v2_freezes_once(tmp_path):
    path = tmp_path / 'c.json'
    path.write_text(V2.read_text(encoding='utf-8'), encoding='utf-8')
    frozen = contract_v2.freeze(path, 'b' * 64, 'run-1')
    assert contract_v2.is_frozen(frozen) and contract_v2.is_frozen(json.loads(path.read_text()))
    with pytest.raises(ValueError, match='version\\+1'):
        contract_v2.freeze(path, 'c' * 64, 'run-2')
    assert not (tmp_path / 'c.json.lock').exists()


def test_story_header_names_the_format_2_model():
    from jiuwenswarm.factory.story import header
    data = dict(tasks=[dict(task_id='t', target='spark-gb10')], _contract=v2(),
                _meta=dict(budget_used=dict(turns=0, wall_clock_s=0), outcome=None))
    assert 'DeepSeek V4.1 Flash' in ''.join(header(data))


def test_factory_lab_queue_refuses_format_2(store, tmp_path):
    store.create_task(dict(task_id='q', objective='x', contract_id='star-deepseek-v2'))
    admission = dict(task_id='q', admission_id='admission:fixture', image=dict(tag='t', id=IMAGE))
    store.put_artifact('q', 'admission:fixture', json.dumps(admission).encode(), 'application/json', None)
    with pytest.raises(ValueError, match='lab_manager'):
        Manager(store, tmp_path / 'spool').submit_run('q', 'admission:fixture', 'star-deepseek-v2', {'env': {}}, 'k')


# ---- the lab manager with an operator lab agent ---------------------------------------
def build(store, task_id, executable=EXE):
    attempt = store.create_attempt(task_id, dict(kind='build', idem_key='b-' + executable[:6], fingerprint='f', request={}))
    receipt = dict(delivery='native', executable=dict(sha256=executable))
    store.put_artifact(task_id, attempt['attempt_id'] + ':receipt', json.dumps(receipt).encode(), 'application/json', attempt['attempt_id'])
    store.transition_attempt(task_id, attempt['attempt_id'], 'running')
    store.transition_attempt(task_id, attempt['attempt_id'], 'succeeded')
    return attempt['attempt_id']


@pytest.fixture
def setup(store, tmp_path, monkeypatch):
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    store.create_task(dict(task_id='lt', objective='measure the cache build', contract_id='star-deepseek-v2'))
    stock, candidate = build(store, 'lt', 'a' * 64), build(store, 'lt', EXE)
    subjects = dict(stock=dict(kind='native_build', identity=dict(executable_sha256='a' * 64), build_attempt_id=stock),
                    cache=dict(kind='native_build', identity=dict(executable_sha256=EXE), build_attempt_id=candidate))
    manager = LabManager(store)
    agent = LabAgent(manager.mailbox, 'spark-lab', 'operator', 'spark-gb10')
    return manager, agent, subjects


def lab_task(subjects):
    return dict(schema='factory.lab-task/1', lab_task_id='ewc-01', purpose='Keep or drop the cache build.',
                contract=dict(id='star-deepseek-v2'), subjects=subjects,
                arms=dict(A=dict(subject='stock'), C3=dict(subject='cache', env={'LLAMA_EXPERT_WEIGHT_CACHE': '1'})),
                tests=[dict(id='parity', check='gate_unset_parity', arms=['C3']),
                       dict(id='ttft', measure=['client_ttft_ms'], arms=['A', 'C3'], requests=['p512'])],
                deliverables=dict(raw_samples=True, files=[dict(name='samples')]))


def good_report():
    return dict(outcome='completed', summary='C3 first token sooner at 512 tokens.',
                results=[dict(test_id='ttft', arm='A', request='p512', metric='client_ttft_ms', unit='ms', samples=[50.0, 49.0]),
                         dict(test_id='ttft', arm='C3', request='p512', metric='client_ttft_ms', unit='ms', samples=[23.0, 24.0])],
                checks=[dict(test_id='parity', check='gate_unset_parity', arm='C3', verdict='pass')],
                limits=['Two repeats in this test.'])


def test_draft_compose_send_report_and_ask(setup, tmp_path):
    manager, agent, subjects = setup
    draft = manager.draft_task('lt', dict(A='stock', C3='cache'), subjects)
    assert draft['problems'] == [] and [t['id'] for t in draft['lab_task']['tests']] == ['gate_unset_parity', 'gate_set_activation', 'server_token_count', 'measure']

    composed = manager.compose('lt', lab_task(subjects))
    assert composed['subjects']['cache']['verified'] and composed['contract_sha256'] == contract_v2.file_sha256(V2)
    assert manager.compose('lt', lab_task(subjects))['package_id'] == composed['package_id']
    sent = manager.send('lt', composed['package_id'], 'first')
    request = sent['request_id']
    assert sent['state'] == 'requested' and manager.send('lt', composed['package_id'], 'first')['request_id'] == request
    assert [row['request_id'] for row in agent.inbox()] == [request]
    assert LabAgent(manager.mailbox, 'jetson', 'operator', 'jetson-orin').inbox() == []

    agent.accept(request, 'on the Spark under the memory cap')
    question = manager.ask('lt', request, 'Send the raw samples.', dict(files=['samples']))['question']
    assert manager.reply('lt', request, question)['state'] == 'pending'

    bad = good_report()
    bad['results'][0]['unit'] = 's'
    del bad['checks'][0]
    with pytest.raises(MailboxError) as error:
        agent.report(request, bad, {'samples': tmp_path / 'missing'})
    assert 'not the contract unit' in str(error.value) and 'no verdict for check gate_unset_parity' in str(error.value)

    samples = tmp_path / 'samples.json'
    samples.write_text('[50, 49, 23, 24]')
    agent.report(request, good_report(), {'samples': samples})
    assert manager.status('lt', request)['state'] == 'reported'
    assert serve(agent, None, once=True, log=lambda line: None) is None
    answered = manager.reply('lt', request, question)
    assert answered['state'] == 'answered' and answered['files'][0]['name'] == 'samples'

    recorded = manager.report('lt', request)
    assert recorded['valid'] and recorded['report']['outcome'] == 'completed'
    observation = manager.store.read('lt', recorded['evidence_id'])
    assert observation['kind'] == 'lab_report' and observation['values']['checks'][0]['verdict'] == 'pass'
    assert manager.report('lt', request)['evidence_id'] == recorded['evidence_id']
    stored = manager.store.artifact_bytes('lt', recorded['report']['files'][0]['artifact_id'])
    assert stored == samples.read_bytes()


def test_lab_task_problems_are_named(setup):
    manager, _, subjects = setup
    task = lab_task(subjects)
    task['arms']['Z'] = dict(subject='nobody')
    task['tests'][0]['arms'] = ['A']
    task['tests'][1]['measure'] = ['tokens']
    with pytest.raises(ValueError) as error:
        manager.compose('lt', task)
    text = str(error.value)
    assert "arms/Z: not an arm of the contract" in text and "unknown subject 'nobody'" in text
    assert 'does not apply to arm A' in text and "'tokens' is not a metric" in text


def test_subject_must_match_its_build_receipt(setup):
    manager, _, subjects = setup
    subjects['cache']['identity']['executable_sha256'] = 'f' * 64
    with pytest.raises(ValueError, match='differs from the build receipt'):
        manager.compose('lt', lab_task(subjects))


def test_requests_are_task_scoped_and_reports_reserved(setup, store):
    manager, _, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    store.create_task(dict(task_id='other', objective='x', contract_id='star-deepseek-v2'))
    with pytest.raises(ScopeDenied):
        manager.status('other', request)
    with pytest.raises(ScopeDenied):
        dispatch(store.scoped('lt'), 'lt', 'evidence.publish',
                 {'inputs': dict(type='observation', record=dict(kind='lab_report', values={}))})
    response = dispatch(store.scoped('lt'), 'lt', 'lab_manager.status', {'inputs': dict(request_id=request)})
    assert response['state'] == 'requested'


def test_report_with_tampered_attachment_is_recorded_invalid(setup, tmp_path):
    manager, agent, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    agent.accept(request)
    samples = tmp_path / 'samples.json'
    samples.write_text('[1]')
    message = agent.report(request, good_report(), {'samples': samples})
    (manager.mailbox.root / 'requests' / request / 'files' / message['files'][0]['sha256']).write_text('[2]')
    recorded = manager.report('lt', request)
    assert not recorded['valid'] and 'differs from its digest' in ' '.join(recorded['problems'])
    assert manager.store.read('lt', recorded['evidence_id'])['values']['valid'] is False


# ---- the mailbox protocol --------------------------------------------------------------
def opened(tmp_path):
    mailbox = Mailbox(tmp_path / 'm')
    request = 'labreq-' + '1' * 24
    mailbox.open_request(request, dict(package_id='p', origin=dict(task_id='t')))
    mailbox.post(request, 'factory', 'request', {})
    return mailbox, request


def test_mailbox_state_machine_and_cancel(tmp_path):
    mailbox, request = opened(tmp_path)
    with pytest.raises(MailboxError, match='cannot send report while the request is requested'):
        mailbox.post(request, 'lab', 'report', {})
    with pytest.raises(MailboxError, match='factory may not send accepted'):
        mailbox.post(request, 'factory', 'accepted', {})
    mailbox.post(request, 'lab', 'accepted', {})
    mailbox.post(request, 'factory', 'cancel', {})
    assert mailbox.thread(request)['state'] == 'cancel_requested'
    mailbox.post(request, 'lab', 'cancelled', {})
    assert mailbox.thread(request)['state'] == 'cancelled'
    with pytest.raises(MailboxError, match='already cancelled'):
        mailbox.post(request, 'factory', 'cancel', {})
    with pytest.raises(MailboxError):
        mailbox.open_request(request, dict(package_id='other'))


def test_mailbox_ignores_malformed_and_out_of_order_files(tmp_path):
    mailbox, request = opened(tmp_path)
    messages = mailbox.root / 'requests' / request / 'messages'
    (messages / 'lab-000009.json').write_text('{"not": "a message"}')
    (messages / 'notes.txt').write_text('x')
    forged = dict(json.loads((messages / 'factory-000001.json').read_text()), sender='lab', id='lab-000002', seq=2, type='report')
    (messages / 'lab-000002.json').write_text(json.dumps(forged))
    thread = mailbox.thread(request)
    assert thread['state'] == 'requested'
    assert {row['file'] for row in thread['invalid']} == {'lab-000009.json', 'notes.txt'}
    assert thread['ignored'][0]['id'] == 'lab-000002'


def test_each_side_writes_only_its_own_message_names(tmp_path):
    mailbox, request = opened(tmp_path)
    mailbox.post(request, 'lab', 'accepted', {})
    mailbox.post(request, 'factory', 'question', dict(text='?'))
    names = sorted(p.name for p in (mailbox.root / 'requests' / request / 'messages').iterdir())
    assert names == ['factory-000001.json', 'factory-000002.json', 'lab-000001.json']


# ---- stand-in lab agents ---------------------------------------------------------------
def test_command_lab_agent_delivers_a_checked_report(setup, tmp_path):
    manager, agent, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    source = tmp_path / 'report-source.json'
    source.write_text(json.dumps(good_report()))
    script = tmp_path / 'lab.py'
    script.write_text('import json, shutil, sys\n'
                      'from pathlib import Path\n'
                      'package = json.load(open(sys.argv[1]))\n'
                      'out = Path(sys.argv[2])\n'
                      'assert package["lab_task"]["lab_task_id"] == "ewc-01"\n'
                      '(out / "files" / "samples").write_text("[1, 2]")\n'
                      f'shutil.copyfile({str(source)!r}, out / "report.json")\n')
    adapter = CommandAdapter(f'"{sys.executable}" "{script}" {{package}} {{output}}', tmp_path / 'work')
    command = LabAgent(manager.mailbox, 'cmd-lab', 'command')
    serve(command, adapter, once=True, log=lambda line: None)
    serve(command, adapter, once=True, log=lambda line: None)
    assert manager.status('lt', request)['state'] == 'reported'
    assert manager.report('lt', request)['valid']


def test_command_lab_agent_reports_failure(setup, tmp_path):
    manager, _, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    adapter = CommandAdapter(f'"{sys.executable}" -c "import sys; sys.exit(3)"', tmp_path / 'work')
    command = LabAgent(manager.mailbox, 'cmd-lab', 'command')
    for _ in range(2):
        serve(command, adapter, once=True, log=lambda line: None)
    status = manager.status('lt', request)
    assert status['state'] == 'failed' and 'exited 3' in status['messages'][-1]['note']
    assert manager.report('lt', request)['report'] is None


def test_queue_lab_agent_runs_a_format_1_contract(lab, worker, tmp_path, monkeypatch):  # noqa: F811
    manager, build_attempt, _ = lab
    store = manager.store
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    labs = LabManager(store, route='mailbox')
    task = dict(schema='factory.lab-task/1', lab_task_id='parity-01', purpose='Reference parity on the factory lab.',
                contract=dict(id='fixture-v1'),
                subjects=dict(image=dict(kind='container_image', identity=dict(tag='fixture:engine', id=IMAGE),
                                         build_attempt_id=build_attempt['attempt_id'])),
                arms=dict(ref=dict(subject='image')),
                tests=[dict(id='parity', check='reference_parity', arms=['ref'])])
    request = labs.send('t', labs.compose('t', task, contract_id='fixture-v1')['package_id'], 'q')['request_id']
    queue = LabAgent(labs.mailbox, 'factory-queue', 'queue')
    adapter = QueueAdapter(store.home, tmp_path / 'lab-state')
    serve(queue, adapter, once=True, log=lambda line: None)
    serve(queue, adapter, once=True, log=lambda line: None)
    assert labs.status('t', request)['state'] == 'running'
    worker()
    deadline = time.monotonic() + 20
    while labs.status('t', request)['state'] != 'reported' and time.monotonic() < deadline:
        serve(queue, adapter, once=True, log=lambda line: None)
        time.sleep(0.1)
    recorded = labs.report('t', request)
    assert recorded['valid'], recorded['problems']
    assert recorded['report']['checks'][0]['verdict'] == 'pass' and recorded['report']['lab']['kind'] == 'queue'


def test_stand_ins_act_only_on_requests_they_accepted(setup, tmp_path):
    manager, agent, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    agent.accept(request)
    other = LabAgent(manager.mailbox, 'cmd-lab', 'command')
    serve(other, CommandAdapter(f'"{sys.executable}" -c "pass"', tmp_path / 'work'), once=True, log=lambda line: None)
    assert manager.status('lt', request)['state'] == 'accepted'


def test_interrupted_command_run_fails_cleanly(setup, tmp_path):
    manager, _, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    command = LabAgent(manager.mailbox, 'cmd-lab', 'command')
    command.accept(request)
    command.progress(request, 'lab command started')
    serve(command, CommandAdapter(f'"{sys.executable}" -c "pass"', tmp_path / 'work'), once=True, log=lambda line: None)
    status = manager.status('lt', request)
    assert status['state'] == 'failed' and 'interrupted' in status['messages'][-1]['note']


def test_factory_judges_against_its_sealed_package(setup, tmp_path):
    manager, agent, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    path = manager.mailbox.root / 'requests' / request / 'package.json'
    package = json.loads(path.read_text())
    package['lab_task']['tests'] = package['lab_task']['tests'][:1]
    path.write_text(json.dumps(package))
    with pytest.raises(ScopeDenied, match='differs from the sealed package'):
        manager.status('lt', request)


def test_factory_cli_passes_lab_agent_options_through(setup, capsys):
    from jiuwenswarm.factory.cli import main
    manager, _, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    with pytest.raises(SystemExit) as done:
        main(['lab-agent', '--profile', 'spark-gb10', 'inbox'])
    assert done.value.code == 0 and json.loads(capsys.readouterr().out)[0]['request_id'] == request
    with pytest.raises(SystemExit):
        main(['lab-agent', '--lab', 'spark-lab', 'accept', request, '--note', 'taken'])
    assert manager.status('lt', request)['lab']['name'] == 'spark-lab'


def test_queue_lab_agent_rejects_what_it_cannot_run(setup, tmp_path):
    manager, _, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    queue = LabAgent(manager.mailbox, 'factory-queue', 'queue')
    serve(queue, QueueAdapter(tmp_path, tmp_path / 'state'), once=True, log=lambda line: None)
    status = manager.status('lt', request)
    assert status['state'] == 'rejected' and 'format-1 contracts only' in status['messages'][-1]['note']


def test_report_problems_requires_every_test(setup):
    manager, agent, subjects = setup
    request = manager.send('lt', manager.compose('lt', lab_task(subjects))['package_id'], 'k')['request_id']
    package = manager.mailbox.package(request)
    report = agent.complete_report(request, good_report(), [dict(name='samples', sha256='0' * 64, size=1)])
    assert report_problems(report, package) == []
    partial = copy.deepcopy(report)
    partial['results'] = []
    problems = report_problems(partial, package)
    assert any('no result for client_ttft_ms' in p for p in problems)
    partial['not_run'] = [dict(test_id='ttft', reason='GPU busy')]
    assert any('use partial' in p for p in report_problems(partial, package))


def test_queue_route_runs_a_format_1_contract_without_a_lab_agent(lab, worker, tmp_path, monkeypatch):  # noqa: F811
    """The default route for a local mailbox: the factory lab queue (the lab CC system) does the work."""
    manager, build_attempt, _ = lab
    monkeypatch.setenv('FACTORY_LAB_MAILBOX', str(tmp_path / 'mailbox'))
    labs = LabManager(manager.store)
    assert labs.route == 'queue'
    task = dict(schema='factory.lab-task/1', lab_task_id='parity-02', purpose='Reference parity, routed to the queue.',
                contract=dict(id='fixture-v1'),
                subjects=dict(image=dict(kind='container_image', identity=dict(tag='fixture:engine', id=IMAGE),
                                         build_attempt_id=build_attempt['attempt_id'])),
                arms=dict(ref=dict(subject='image')),
                tests=[dict(id='parity', check='reference_parity', arms=['ref'])])
    sent = labs.send('t', labs.compose('t', task, contract_id='fixture-v1')['package_id'], 'auto')
    assert sent['state'] == 'accepted' and sent['route'] == 'factory lab queue'
    assert labs.status('t', sent['request_id'])['state'] == 'running'
    worker()
    deadline = time.monotonic() + 20
    while labs.status('t', sent['request_id'])['state'] != 'reported' and time.monotonic() < deadline:
        time.sleep(0.1)
    recorded = labs.report('t', sent['request_id'])
    assert recorded['valid'], recorded['problems']
    assert recorded['report']['lab']['name'] == 'factory-queue' and recorded['report']['checks'][0]['verdict'] == 'pass'
