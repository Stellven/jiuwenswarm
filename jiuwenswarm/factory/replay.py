"""Replay an explicit read-only subset against a disposable store copy."""
import argparse
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
from contextlib import contextmanager
from . import api, telemetry
from .store import Store

@contextmanager
def environment(**values):
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


READ_ONLY = {'evidence.query', 'evidence.read', 'builder.status', 'builder.result',
             'lab.status', 'lab.result', 'inspector.inspect'}


def replay(task_id, home=None, *, calls=None, out=None):
    home = telemetry.home_path(home)
    calls = list(calls if calls is not None else
                 (e for e in telemetry.read_events(home, task_id) if e['event'] == 'cc.call' and not e.get('replay') and e['capability'] in READ_ONLY))
    # Validate the complete selection before doing any work. Default selection skips mutations.
    if any(e['capability'] not in READ_ONLY for e in calls):
        raise ValueError('Replay refuses mutating or unknown capabilities')
    if any(e.get('inputs_redacted') for e in calls):
        raise ValueError('Replay refuses redacted inputs')
    with tempfile.TemporaryDirectory(prefix='factory-replay-') as temporary:
        copied = Path(temporary) / 'home'
        copied.mkdir()
        # Credentials and agent profiles are never needed by offline replay.
        paths = [home / 'factory.sqlite', home / 'factory.sqlite-wal']
        def stamps():
            return [(p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None for p in paths]
        for _ in range(5):
            before = stamps()
            for source in paths:
                target = copied / source.name
                target.unlink(missing_ok=True)
                if source.is_file():
                    shutil.copyfile(source, target)
            if before == stamps():
                break
        else:
            raise ValueError('Factory store changed during copy; retry replay')
        if (home / 'artifacts').is_dir():
            shutil.copytree(home / 'artifacts', copied / 'artifacts')
        results = []
        with Store(copied) as store, environment(FACTORY_HOME=str(copied), GIT_OPTIONAL_LOCKS='0'):
            task = store.get_task(task_id)
            reads = task.get('constraints', {})
            reads = reads.get('read_tasks', []) if isinstance(reads, dict) else []
            for e in calls:
                capability = e['capability']
                packet = dict(inputs=e['inputs'], capability=capability, resources=dict(e.get('resources', {})))
                started = time.perf_counter()
                try:
                    if capability == 'inspector.inspect':
                        from .inspector import dispatch as inspect_dispatch
                        # Probe only copied workspaces; Git cannot refresh the source index.
                        for handle, resource in list(packet['resources'].items()):
                            if resource.get('kind') == 'workspace':
                                source = Path(resource['path']).resolve()
                                destination = copied / 'replay-workspaces' / str(len(list(copied.glob('replay-workspaces/*'))))
                                destination.parent.mkdir(exist_ok=True)
                                shutil.copytree(source, destination, symlinks=True)
                                packet['resources'][handle] = dict(resource, path=str(destination))
                        result = inspect_dispatch(store.scoped(task_id), task_id, capability, packet)
                    elif capability.endswith(('.status', '.result')):
                        aid = packet['inputs']['attempt_id']
                        attempt = store._get('attempts', task_id, aid)
                        kind = 'lab' if capability.startswith('lab.') else 'build'
                        if attempt['kind'] != kind:
                            raise ValueError('Attempt belongs to another capability')
                        if capability.endswith('.status'):
                            outputs = attempt
                        else:
                            outputs = dict(attempt_id=aid, state=attempt['state'],
                                           result_refs=attempt['result_refs'] if attempt['state'] == 'succeeded' else [])
                            if kind == 'lab':
                                from .store import NotFound
                                try:
                                    evaluation = store._get('evaluations', task_id, aid + ':evaluation')
                                except NotFound:
                                    evaluation = None
                                outputs.update(evaluation=evaluation, evidence_refs=attempt['result_refs'],
                                    execution_outcome=evaluation['execution_outcome'] if evaluation else
                                    'cancelled' if attempt['state'] == 'cancelled' else 'upload_pending')
                        result = dict(outcome='ok', outputs=outputs)
                    else:
                        result = dict(outcome='ok', outputs=api.dispatch(store.scoped(task_id, reads), task_id, capability, packet))
                except Exception as exc:
                    result = dict(outcome='error', error=dict(code=getattr(exc, 'code', 'INVALID_INPUT'), message=api.input_reason(exc)))
                telemetry.call(out or copied, task_id, capability, packet, result, started, replay=True, store=store, turn=e.get('turn'))
                results.append(result)
        events = telemetry.read_events(out or copied, task_id)
        return dict(results=results, events=[e for e in events if e.get('replay')])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    parser.add_argument('--home')
    parser.add_argument('--out', help='telemetry destination home; default temporary copy (printed before deletion)')
    parser.add_argument('--capability', action='append', help='explicit selection; mutations are refused')
    args = parser.parse_args(argv)
    calls = [e for e in telemetry.read_events(args.home, args.task_id) if e['event'] == 'cc.call' and not e.get('replay')
             and e['capability'] in (args.capability or READ_ONLY)]
    if args.capability and set(args.capability) - READ_ONLY:
        parser.error('Replay refuses mutating or unknown capabilities')
    try:
        print(json.dumps(replay(args.task_id, args.home, calls=calls, out=args.out), ensure_ascii=False))
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
