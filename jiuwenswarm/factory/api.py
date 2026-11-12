"""Native CC packet entry point for task-scoped evidence capabilities."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
import sqlite3
import sys

from .store import FactoryError, NotFound, ScopeDenied, Store


def fields(value, allowed, required=()):
    if not isinstance(value, dict) or set(value) - set(allowed) or set(required) - set(value):
        raise ValueError('Invalid or missing input fields')


def artifact_source(record, packet):
    if ('path' in record) == ('text' in record):
        raise ValueError('Supply exactly one of path or text')
    if 'text' in record:
        if not isinstance(record['text'], str):
            raise ValueError('text must be a string')
        return record['text'].encode('utf-8')
    if not isinstance(record['path'], str) or not record['path']:
        raise ValueError('path must be a nonempty string')
    roots = [Path(value).expanduser().resolve() for value in
             (packet.get('output_dir'), os.environ.get('FACTORY_WORKSPACE')) if isinstance(value, str) and value]
    candidate = Path(record['path']).expanduser()
    if not candidate.is_absolute():
        if not roots:
            raise ScopeDenied('Artifact publication requires an authorized directory')
        candidate = roots[0] / candidate
    candidate = candidate.resolve()
    if not any(candidate.is_relative_to(root) for root in roots):
        raise ScopeDenied('Artifact path is outside output_dir and workspace')
    if not candidate.is_file():
        raise ValueError('Artifact path must name an existing file')
    return candidate


def dispatch(store, task_id, capability, packet):
    inputs = packet.get('inputs', {})
    if capability.startswith('lab.'):
        from .manager import Manager
        operation = capability.removeprefix('lab.')
        if operation not in {'submit', 'status', 'cancel', 'result'}:
            raise ValueError('Unknown lab capability')
        if hasattr(store, '_check'):
            store._check(task_id, write=True)
            host = store._store
        else:
            host = store
        manager = Manager(host, host.home / 'lab-spool')
        if operation == 'submit':
            fields(inputs, {'image', 'build_attempt_id', 'contract_id', 'run_config', 'idem_key'},
                   {'image', 'build_attempt_id', 'contract_id', 'run_config', 'idem_key'})
            admission = manager.admit(task_id, inputs['image'], inputs['build_attempt_id'])
            attempt = manager.submit_run(task_id, admission['admission_id'], inputs['contract_id'],
                                         inputs['run_config'], inputs['idem_key'])
            return dict(admission=admission, **{k: attempt[k] for k in ('attempt_id', 'state', 'jobq_id')})
        fields(inputs, {'attempt_id'}, {'attempt_id'})
        attempt = manager.jobs._get(inputs['attempt_id'])
        if attempt['task_id'] != task_id or attempt['kind'] != 'lab':
            raise ScopeDenied('Lab attempt belongs to another task or capability')
        return getattr(manager, operation)(inputs['attempt_id'])
    if capability.startswith('builder.'):
        from .builder import Builder
        operation = capability.removeprefix('builder.')
        if operation not in {'submit', 'status', 'cancel', 'result'}:
            raise ValueError('Unknown builder capability')
        # Unwrap only after enforcing the current task's write boundary. Read
        # grants must never allow cancellation or use of another task's build.
        if hasattr(store, '_check'):
            store._check(task_id, write=True)
            host = store._store
        else:
            host = store
        builder = Builder(host)
        if operation == 'submit':
            fields(inputs, {'request', 'idem_key'}, {'request', 'idem_key'})
            attempt = builder.submit(task_id, inputs['request'], inputs['idem_key'])
            return {key: attempt[key] for key in ('attempt_id', 'state', 'jobq_id')}
        fields(inputs, {'attempt_id'}, {'attempt_id'})
        attempt = builder.jobs._get(inputs['attempt_id'])
        if attempt['task_id'] != task_id:
            raise ScopeDenied('Attempt belongs to another task')
        return getattr(builder, operation)(inputs['attempt_id'])
    if capability == 'evidence.query':
        fields(inputs, {'kinds', 'text', 'since', 'limit', 'task_id'})
        options = dict(inputs)
        target = options.pop('task_id', task_id)
        return store.query(target, **options)
    if capability == 'evidence.read':
        fields(inputs, {'id', 'task_id'}, {'id'})
        if not isinstance(inputs['id'], str) or not inputs['id']:
            raise ValueError('id must be a nonempty string')
        if 'task_id' in inputs:
            return store.read(inputs['task_id'], inputs['id'])
        # The advertised interface needs only an evidence id. Prefer the
        # current task, then search explicitly granted tasks in stable order.
        for target in [task_id, *sorted(store.readable - {task_id})]:
            try:
                return store.read(target, inputs['id'])
            except NotFound:
                continue
        raise NotFound('Record not found')
    if capability != 'evidence.publish':
        raise ValueError('Unknown evidence capability')
    fields(inputs, {'type', 'record', 'expected_rev'}, {'type', 'record'})
    record = inputs['record']
    if not isinstance(record, dict):
        raise ValueError('record must be an object')
    record = dict(record)
    if record.get('task_id', task_id) != task_id:
        raise ScopeDenied('Publication belongs to another task')
    if inputs['type'] == 'observation':
        if 'expected_rev' in inputs:
            raise ValueError('expected_rev applies only to decisions')
        return store.append_observation(task_id, record)
    if inputs['type'] == 'decision':
        if 'expected_rev' in record and 'expected_rev' in inputs and record['expected_rev'] != inputs['expected_rev']:
            raise ValueError('Conflicting expected_rev values')
        expected_rev = record.pop('expected_rev', inputs.get('expected_rev'))
        return store.advance_decision(task_id, expected_rev, record)
    if inputs['type'] == 'artifact':
        if 'expected_rev' in inputs:
            raise ValueError('expected_rev applies only to decisions')
        fields(record, {'task_id', 'artifact_id', 'path', 'text', 'media_type', 'producer_attempt'})
        source = artifact_source(record, packet)
        return store.put_artifact(task_id, record.get('artifact_id'), source,
                                  record.get('media_type', 'text/plain' if 'text' in record else 'application/octet-stream'),
                                  record.get('producer_attempt', packet.get('attempt')))
    raise ValueError('type must be observation, decision or artifact')


def input_reason(exc):
    """Keep actionable validation text while redacting configured credentials."""
    message = str(exc)
    for key, value in os.environ.items():
        if value and re.search(r'(?i)(secret|token|password|credential|api_key|private_key)', key):
            message = message.replace(value, '[redacted]')
    message = re.sub(r'(?i)(bearer\s+)[\w.\-]+', r'\1[redacted]', message)
    return message[:300]


def main():
    try:
        if len(sys.argv) != 2:
            raise ValueError('One capability argument is required')
        packet = json.load(sys.stdin)
        if not isinstance(packet, dict):
            raise ValueError('Packet must be an object')
        if packet.get('capability', sys.argv[1]) != sys.argv[1]:
            raise ValueError('Packet capability differs from command')
        task_id = os.environ.get('FACTORY_TASK_ID', '').strip()
        if not task_id:
            raise ValueError('FACTORY_TASK_ID is required')
        readable = frozenset(t.strip() for t in os.environ.get('FACTORY_READ_TASKS', '').split(',') if t.strip())
        with Store(Path(os.environ.get('FACTORY_HOME', '~/.jiuwenswarm-factory'))) as store:
            # Inspector dispatch: returns a native envelope, including failed
            # probes with their observation/artifact references (F04).
            if sys.argv[1].startswith('inspector.'):
                from .inspector import dispatch as inspector_dispatch
                result = inspector_dispatch(store.scoped(task_id), task_id, sys.argv[1], packet)
                print(json.dumps(result, ensure_ascii=False, allow_nan=False))
                return
            # End inspector dispatch.
            outputs = dispatch(store.scoped(task_id, readable), task_id, sys.argv[1], packet)
        result = {'outcome': 'ok', 'outputs': outputs}
    except FactoryError as exc:
        result = {'outcome': 'error', 'error': {'code': exc.code, 'message': str(exc)}}
    except (ValueError, TypeError, KeyError, OverflowError, sqlite3.ProgrammingError) as exc:
        result = {'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': input_reason(exc)}}
    except (OSError, sqlite3.Error):
        result = {'outcome': 'error', 'error': {'code': 'PERSISTENCE_FAILED', 'message': 'Evidence persistence failed'}}
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
