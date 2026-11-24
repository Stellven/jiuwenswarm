"""Validate sealed lab packages and messages produced by the protocol clients."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

from jiuwenswarm.factory.lab_agent import LabAgent
from jiuwenswarm.factory.lab_mailbox import Mailbox, SENDERS
from jiuwenswarm.factory.lab_manager import LabManager

from test_lab_manager import EXE, build, good_report, lab_task


SCHEMAS = Path(__file__).resolve().parents[2] / 'jiuwenswarm/factory/schemas'


@pytest.fixture
def validators():
    documents = [json.loads((SCHEMAS / f'lab-{name}-1.schema.json').read_text(encoding='utf-8'))
                 for name in ('task', 'report', 'package', 'message')]
    for document in documents:
        Draft202012Validator.check_schema(document)
    return {document['$id']: Draft202012Validator(
        document, format_checker=Draft202012Validator.FORMAT_CHECKER)
        for document in documents}


def test_lab_protocol_schemas(store, tmp_path, validators):
    store.create_task(dict(task_id='lt', objective='measure the cache build',
                           contract_id='star-deepseek-v2'))
    subjects = dict(
        stock=dict(kind='native_build', identity=dict(executable_sha256='a' * 64),
                   build_attempt_id=build(store, 'lt', 'a' * 64)),
        cache=dict(kind='native_build', identity=dict(executable_sha256=EXE),
                   build_attempt_id=build(store, 'lt', EXE)))
    store.put_artifact('lt', 'input-data', b'protocol fixture', 'application/octet-stream', None)
    subjects['data'] = dict(kind='artifact', identity=dict(artifact_id='input-data'), transfer='attach')
    manager = LabManager(store, mailbox=Mailbox(tmp_path / 'mailbox'), route='mailbox')
    agent = LabAgent(manager.mailbox, 'schema-lab', 'operator')
    composed = manager.compose('lt', lab_task(subjects), node_id='schema-node')
    requests = []

    def send(key):
        request = manager.send('lt', composed['package_id'], key)['request_id']
        requests.append(request)
        return request

    request = send('report')
    package = manager.mailbox.package(request)
    package_validator = validators['factory.lab-package/1']
    package_validator.validate(package)
    validators['factory.lab-task/1'].validate(package['lab_task'])
    assert package['origin']['node_id'] == 'schema-node'
    assert package['subjects']['stock']['verification']['verified']
    assert not package['subjects']['data']['verification']['verified']
    assert package['subjects']['data']['payload']['format'] == 'file'

    agent.accept(request, 'Starting the protocol fixture.')
    agent.progress(request, 'Collecting samples.', data=dict(completed=1))
    question = manager.ask('lt', request, 'Send the samples.',
                           wants=dict(files=['samples'], metrics=['client_ttft_ms'], tests=['ttft']))['question']
    assert manager.reply('lt', request, question)['state'] == 'pending'
    samples = tmp_path / 'samples.json'
    samples.write_text('[50.0, 49.0]', encoding='utf-8')
    agent.answer(request, question, 'Samples attached.', data=dict(repeats=2), files={'samples': samples})
    assert manager.reply('lt', request, question)['state'] == 'answered'
    agent.report(request, good_report(), files={'samples': samples})
    recorded = manager.report('lt', request)
    assert recorded['valid'], recorded['problems']

    agent.reject(send('reject'), 'Lab unavailable.')
    agent.fail(send('fail'), 'Measurement failed.', problems=['Device unavailable.'])
    cancelled = send('cancel')
    manager.cancel('lt', cancelled, 'Stop the fixture.')
    agent.cancelled(cancelled)

    messages = []
    for request_id in requests:
        package_validator.validate(manager.mailbox.package(request_id))
        thread = manager.mailbox.thread(request_id)
        assert not thread['invalid'] and not thread['ignored']
        messages.extend(thread['messages'])
    assert {(message['sender'], message['type']) for message in messages} == {
        (sender, kind) for sender, kinds in SENDERS.items() for kind in kinds}
    message_validator = validators['factory.lab-message/1']
    for message in messages:
        message_validator.validate(message)
        if message['type'] == 'report':
            validators['factory.lab-report/1'].validate(message['body'])

    broken_package = copy.deepcopy(package)
    broken_package['contract']['sha256'] = 'not-a-digest'
    with pytest.raises(ValidationError):
        package_validator.validate(broken_package)

    broken_message = copy.deepcopy(manager.mailbox.latest(request, 'answer'))
    del broken_message['body']['question']
    with pytest.raises(ValidationError):
        message_validator.validate(broken_message)
