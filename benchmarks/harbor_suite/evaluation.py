"""Host-only finite E3 launcher; the supported product runner owns execution.

The command and its control files are protected operator configuration. They
never enter the verifier image or acquire authority from an evidence projection.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path
import re
import signal

from .contracts import canonical, pin, read_json, regular, relative, require
from ..harbor_pilot.bridge import atomic, output_lock

ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$')
SCOPE = {'run_id', 'campaign_id', 'case_id', 'case_version', 'config_id', 'repeat_index'}


def validate_overlay(value):
    required = {'schema', 'case_id', 'variant_id', 'binding', 'criteria'}
    require(isinstance(value, dict) and required <= set(value) and not set(value)-required-{'prepared_inputs', 'transformations'}
            and value['schema'] == 'ai4r-harbor-evaluation-overlay:1', 'unsupported protected evaluation overlay')
    binding = value['binding']
    require(isinstance(binding, dict) and set(binding) == {'campaign_id', 'run_id', 'case_id', 'variant_id', 'run_scope', 'expected_request'},
            'exact frozen evaluation binding required')
    require(all(isinstance(binding[k], str) and ID.fullmatch(binding[k])
                for k in ('campaign_id', 'run_id', 'case_id', 'variant_id')), 'invalid evaluation identity')
    scope = binding['run_scope']; request = binding['expected_request']
    require(isinstance(scope, dict) and set(scope) == SCOPE
            and all(scope[k] == binding[k] for k in ('run_id', 'campaign_id', 'case_id'))
            and type(scope['case_version']) is int and scope['case_version'] >= 1
            and type(scope['repeat_index']) is int and scope['repeat_index'] >= 0
            and isinstance(scope['config_id'], str) and ID.fullmatch(scope['config_id']), 'evaluation run scope differs')
    require(isinstance(request, dict) and all(request.get(k) == binding[k] for k in ('campaign_id', 'case_id'))
            and isinstance(request.get('request_id'), str) and ID.fullmatch(request['request_id'])
            and isinstance(request.get('evaluation_profile_id'), str) and request['evaluation_profile_id'],
            'exact prepared evaluation request required')
    require(value['variant_id'] == binding['variant_id'] and isinstance(value['criteria'], dict)
            and value['variant_id'] in value['criteria'].get('variants', {}), 'evaluation overlay variant differs')
    variant = value['criteria']['variants'][value['variant_id']]; capsule = variant['binding']
    require((request.get('capsule_id'), request.get('capsule_version'), request.get('capsule_declaration_sha256')) ==
            (capsule['name'], capsule['version'], capsule['declaration_ref']['sha256']),
            'prepared request differs from frozen capsule criteria')
    require(sorted((p['port'], p['sha256']) for p in request['inputs']) ==
            sorted((name, ref['sha256']) for name, ref in variant['input_refs'].items()),
            'prepared request differs from frozen input criteria')
    if 'prepared_inputs' in value:
        require(isinstance(value['prepared_inputs'], dict) and value['prepared_inputs'], 'finite prepared public inputs required')
        for name, item in value['prepared_inputs'].items():
            relative(name)
            require(name.startswith('public/') and isinstance(item, dict) and set(item) == {'path', 'artifact_ref'},
                    'prepared public input fields differ')
            ref = item['artifact_ref']
            require(isinstance(ref, dict) and set(ref) == {'id', 'sha256'} and isinstance(ref['id'], str) and ref['id']
                    and Path(item['path']).is_absolute() and pin(item['path'])['sha256'] == ref['sha256'],
                    'prepared original public input bytes changed')
    canonical(value)
    return value


def load_config(path, task, suite):
    require(task.get('evaluation_controller_pins') and all(pin(Path(__file__).with_name(name)) == expected
                for name, expected in task['evaluation_controller_pins'].items()), 'frozen evaluation controller changed')
    path = regular(path); value = read_json(path)
    require(isinstance(value, dict) and set(value) == {'schema', 'task_key', 'command', 'cwd', 'result_root', 'control_files'}
            and value['schema'] == 'ai4r-harbor-evaluation-config:1'
            and value['task_key'] == task['task_key'], 'wrong host evaluation configuration')
    command = value['command']
    require(isinstance(command, list) and command and all(isinstance(v, str) and v and '\0' not in v for v in command)
            and Path(command[0]).is_absolute(), 'explicit absolute evaluation executable required')
    regular(command[0], 256*1024*1024)
    for key in ('cwd', 'result_root'):
        root = Path(value[key])
        require(root.is_absolute() and root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)),
                'existing absolute evaluation directory required')
        require(not root.is_relative_to(suite['bundle_root']) and not root.is_relative_to(suite['output_root'])
                and not suite['bundle_root'].is_relative_to(root) and not suite['output_root'].is_relative_to(root),
                'evaluation host directories must stay outside bundle/evidence')
    require(isinstance(value['control_files'], dict) and value['control_files'], 'frozen launcher control files required')
    for name, expected in value['control_files'].items():
        require(Path(name).is_absolute() and pin(name) == expected, 'evaluation launcher control file changed')
    # Every file argument, including the executable, is independently pinned.
    # Script arguments cannot silently change while retaining the same config.
    for argument in command:
        candidate = Path(argument)
        if candidate.is_absolute() and candidate.is_file():
            require(str(candidate) in value['control_files'] and pin(candidate) == value['control_files'][str(candidate)],
                    'evaluation command contains an unpinned file')
    value['config_pin'] = pin(path)
    return value


def snapshot(source, destination):
    """Retain exact finite runner bytes without importing its credential mounts."""
    source = Path(source); pending = [source]; files = []; total = 0
    while pending:
        for child in pending.pop().iterdir():
            require(not child.is_symlink(), 'symlink evaluation result')
            if child.is_dir():
                pending.append(child)
                continue
            regular(child, 128*1024*1024)
            name = relative(child.relative_to(source).as_posix())
            require(name not in {'suite-receipt.json', 'evaluation-host-inventory.json'}, 'reserved evaluation result path')
            total += child.stat().st_size
            require(len(files) < 10000 and total <= 1024*1024*1024, 'evaluation result exceeds finite snapshot bound')
            files.append((name, child.read_bytes()))
    require(files, 'evaluation runner retained no result bytes')
    inventory = []
    for name, raw in sorted(files):
        target = destination / name; target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            require(regular(target, 128*1024*1024).read_bytes() == raw, 'retained evaluation result changed')
        else:
            with target.open('xb') as stream:
                stream.write(raw)
        inventory.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)})
    atomic(destination / 'evaluation-host-inventory.json', {'schema': 'ai4r-harbor-evaluation-snapshot:1', 'files': inventory})


def observer_process_options(platform=None):
    platform = os.name if platform is None else platform
    require(platform in {'posix', 'nt'}, 'unsupported finite evaluation observer platform')
    return {'start_new_session': True} if platform == 'posix' else {
        'creationflags': 0x00000200 | 0x08000000}  # NEW_PROCESS_GROUP | NO_WINDOW


async def stop_observer(process, platform=None):
    """Contain the local observer tree; never claim remote model containment."""
    platform = os.name if platform is None else platform
    if process.returncode is not None:
        return
    if platform == 'nt':
        executable = str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'taskkill.exe')
        killer = await asyncio.create_subprocess_exec(executable, '/PID', str(process.pid), '/T', '/F',
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
            creationflags=0x08000000)
        code = await asyncio.wait_for(killer.wait(), timeout=15)
        require(code == 0 or process.returncode is not None,
                'Windows observer tree termination remains uncertain')
        await asyncio.wait_for(process.wait(), timeout=15)
        return
    require(platform == 'posix', 'unsupported finite evaluation observer platform')
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        await asyncio.wait_for(process.wait(), timeout=15)
    except TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()


async def dispatch(suite, task, identity):
    from .adapter import receipt
    from .evidence import normalize_single_cc
    process_options = observer_process_options()
    config = load_config(suite['evaluation_config'], task, suite)
    binding = task['evaluation_binding']; root = suite['output_root']
    folder = root / binding['campaign_id']
    frozen = {'task_sha256': hashlib.sha256(canonical(task)).hexdigest(), 'trial_identity': identity,
              'configuration': config, 'campaign_id': binding['campaign_id']}
    active = root / '.harbor-evaluation-active.json'
    folder.mkdir(exist_ok=True)
    with output_lock(root):
        require(not (root / '.harbor-pilot-active.json').exists(),
                'an unresolved ordinary product trial still owns this output root')
        if active.exists():
            require(read_json(active) == frozen, 'an unresolved evaluation trial still owns this output root')
            # A prior claim never authorizes another process or submission.
            snapshot(config['result_root'], folder)
            normalize_single_cc(folder, task)
            active.unlink()
            return folder, read_json(folder / 'suite-receipt.json'), None
        if (folder / 'suite-receipt.json').exists():
            normalized = normalize_single_cc(folder, task)
            require(normalized['execution']['terminal'], 'previous evaluation is unresolved')
            previous = read_json(folder / 'suite-receipt.json')
            require(previous.get('trial_identity') == identity, 'prepared evaluation belongs to another Harbor trial')
            return folder, previous, None
        atomic(active, frozen)
        row = receipt(task, status='observed', launched=True, custody='live', campaign_id=binding['campaign_id'],
                      trial_identity=identity, evaluation_state='delivery_unknown')
        atomic(folder / 'suite-receipt.json', row)
        logs = root / '.evaluation-observers'; logs.mkdir(exist_ok=True)
        tag = hashlib.sha256(identity.encode()).hexdigest()[:24]
        cancelled = None
        with (logs / (tag+'.stdout')).open('ab') as stdout, (logs / (tag+'.stderr')).open('ab') as stderr:
            process = await asyncio.create_subprocess_exec(*config['command'], cwd=config['cwd'], stdout=stdout, stderr=stderr,
                **process_options)
            try:
                code = await process.wait()
            except asyncio.CancelledError as error:
                cancelled = error; code = None
                await stop_observer(process)
        row.update(evaluation_state='observer_cancelled' if cancelled else 'observer_returned', runner_returncode=code)
        atomic(folder / 'suite-receipt.json', row)
        # A cancelled observer does not establish remote containment. Leave the
        # active pointer regardless of whether a partial result exists.
        if cancelled:
            return folder, row, cancelled
        snapshot(config['result_root'], folder)
        normalize_single_cc(folder, task)
        active.unlink()
        return folder, row, None
