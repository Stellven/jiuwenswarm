"""Operator-authorized, one-shot CPU fixture verification for the Muse revision 8 demo."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time

from . import capped_run
from .jobs import Jobs, KeyConflict
from .node_check import CheckError
from .store import ScopeDenied

TASK = 'muse-2bit-demo-r8'
NODE = 'wire_expert_scales'
CC = 'weights.build_expert_scale_wiring'
POLICY_FILE = 'wiring-fixture-approval.json'
RECIPE = 'wire_fixture'
ATTEMPT_KIND = 'wire_fixture'
ONCE_KEY = 'wire-expert-scales-fixture-v1'
FILES = {'tiny-bf16.gguf', 'tiny-nvfp4-f32.gguf', 'tiny-deqref-f32.gguf'}


def is_demo_check(request):
    verifier = request.get('verifier') or {}
    return request.get('task_id') == TASK and verifier.get('cc') == CC


def _policy(home):
    path = home / POLICY_FILE
    try:
        mode = path.lstat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_uid != os.getuid() or mode.st_mode & 0o022:
            raise CheckError(f'{POLICY_FILE} must be a regular file owned and writable only by the operator')
        policy = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise CheckError(f'Cannot read operator fixture approval {POLICY_FILE}: {exc}') from exc
    pins = policy.get('files') if isinstance(policy, dict) else None
    if (not isinstance(pins, dict) or set(pins) != FILES
            or any(not isinstance(v, str) or not re.fullmatch('[0-9a-f]{64}', v) for v in pins.values())
            or policy != dict(task_id=TASK, node_id=NODE, loads=7, files=pins)):
        raise CheckError(f'{POLICY_FILE} must authorize seven CPU fixture loads and pin all three fixture digests')
    return pins


def _approved_request(store, request, work):
    if (not is_demo_check(request) or request['node_id'] != NODE or request['output'] != 'change'
            or request['kind'] != 'diff' or request['entry'].get('stage') != 'runtime acceptance'
            or request['verifier']['capability'] != 'verify'):
        raise CheckError('Fixture approval applies only to the demo scale-wiring runtime verifier')
    task = store.get_task(TASK)
    if ('process.exec' not in task.get('allowed_effects', [])
            or not (task.get('constraints') or {}).get('model_runs')):
        raise CheckError('The demo task does not authorize model execution')
    checkout = capped_run._checkout(store, task).resolve()
    if (not checkout.is_relative_to((store.home / 'agent-workspace').resolve())
            or Path(request['checkout']).resolve() != checkout):
        raise CheckError('Fixture verification requires the owned demo checkout')
    root = (task.get('resources') or {}).get('verifier_inputs', {}).get('wiring_tiny_dir')
    if not root:
        raise CheckError('The demo task needs resources.verifier_inputs.wiring_tiny_dir')
    try:
        tiny_dir = capped_run._readable(store, task, root, 'scale-wiring fixture directory', 'dir')
        for name in FILES:
            if capped_run._readable(store, task, tiny_dir / name, 'scale-wiring fixture').parent != tiny_dir:
                raise CheckError('A fixture resolves outside the approved directory')
    except (ScopeDenied, ValueError) as exc:
        raise CheckError(str(exc)) from exc
    pins = _policy(store.home)
    options = dict(tiny_dir=str(tiny_dir), require_stage='runtime acceptance', jobs=4)
    given = dict(request['verifier_inputs'])
    expected = options | dict(base=request['head'])
    for field, value in given.items():
        if field not in expected or value != expected[field]:
            raise CheckError(f'Leave {field} to the host for the approved scale-wiring fixture check')
    patch = (Path(work) / 'patch.diff').read_bytes()
    if hashlib.sha256(patch).hexdigest() != request['diff_sha256']:
        raise CheckError('The scale-wiring patch changed after the check was requested')
    return dict(recipe=RECIPE, node_id=NODE, check=request, inputs=options, files=pins,
                patch=None if request['working'] else patch.decode('utf-8'))


def submit(store, request, work):
    """Use a dedicated attempt kind and stable idempotency key for the single authorization."""
    payload = _approved_request(store, request, work)
    python = os.environ.get('FACTORY_HOST_PYTHON', sys.executable)
    argv = [python, '-m', 'jiuwenswarm.factory.capped_run', '_exec', TASK, '{attempt_id}']
    env = {k: v for k, v in os.environ.items() if k in {
        'PATH', 'HOME', 'PYTHONPATH', 'LD_LIBRARY_PATH', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'}}
    env['FACTORY_HOME'] = str(store.home)
    jobs = Jobs(store)
    try:
        # The GPU queue serializes this CPU scope against full loads. Its attempt kind stays outside model_run.
        attempt = jobs.submit(TASK, ATTEMPT_KIND, payload, ONCE_KEY, 'gpu', argv,
                              capped_run.GATE_WAIT_S + 1800, env)
        attempt_id = attempt['attempt_id']
        while attempt['state'] in {'queued', 'running', 'cancel_requested'}:
            time.sleep(2)
            attempt = jobs.status(attempt_id)
    except (KeyConflict, subprocess.CalledProcessError) as exc:
        raise CheckError(f'The one-shot scale-wiring fixture job cannot be submitted or observed: {exc}') from exc
    result_path = store.home / 'runs' / attempt_id / 'result.json'
    result = json.loads(result_path.read_text()) if result_path.is_file() else {}
    if attempt['state'] != 'succeeded' or result.get('outcome') != 'ok':
        detail = (result.get('error') or {}).get('message') or attempt['state']
        raise CheckError(f'Scale-wiring capped attempt {attempt_id}: {detail}')
    return dict(result['result']['receipt'], capped_attempt_id=attempt_id)


def run_job(run):
    """Run the whole sealed verifier inside the owned scope, including all seven model subprocesses."""
    if (run.task_id != TASK or run.attempt['kind'] != ATTEMPT_KIND or run.attempt['idem_key'] != ONCE_KEY
            or run.req['node_id'] != NODE or run.req['files'] != _policy(run.store.home)):
        raise CheckError('Scale-wiring job does not match the operator authorization')
    try:
        (run.dir / 'fixture-started').touch(exist_ok=False)
    except FileExistsError as exc:
        raise CheckError('The scale-wiring fixture authorization has already been used') from exc
    run.cap = capped_run.CAP
    resources = run.task.get('resources') or {}
    run.task = dict(run.task, resources=dict(resources, memory_cap=run.cap,
                    need_available_gib=max(capped_run.NEED_GIB, resources.get('need_available_gib', 0)),
                    floor_gib=max(capped_run.FLOOR_GIB, resources.get('floor_gib', 0))))
    run.gate()
    if capped_run._gpu_apps(strict=True):
        raise capped_run.RunError('MACHINE_BUSY', 'GPU processes appeared after the scale-wiring gate passed')
    command = [sys.executable, '-m', 'jiuwenswarm.factory.wiring_fixture', run.attempt['attempt_id']]
    prefix = f"factory-wire-fixture-{run.attempt['attempt_id'][:8]}-"
    env = dict(FACTORY_TASK_ID=TASK, FACTORY_WIRING_FIXTURE_SCOPE=prefix,
               CUDA_VISIBLE_DEVICES='', HIP_VISIBLE_DEVICES='', ROCR_VISIBLE_DEVICES='')
    code, seconds = run.run(command, 'verifier.log', env=env, unit='wire-fixture')
    if code:
        raise capped_run.RunError('FIXTURE_SCOPE', f'Capped scale-wiring verifier exited {code}; see verifier.log')
    receipt = json.loads((run.dir / 'verifier.json').read_text())
    return dict(receipt=receipt, seconds=round(seconds, 1), approved_loads=7)


def _scoped_verify(attempt_id):
    from .node_check import NodeChecks
    from .store import Store
    from .ccs.expert_scale_wiring.helpers.fixture_scope import require_scope

    require_scope()
    home = Path(os.environ['FACTORY_HOME'])
    with Store(home) as store:
        attempt = store._get('attempts', TASK, attempt_id)
        request = attempt['request']
        if attempt['kind'] != ATTEMPT_KIND or attempt['idem_key'] != ONCE_KEY or request['recipe'] != RECIPE:
            raise CheckError('Invalid owned scale-wiring verification attempt')
        work = home / 'runs' / attempt_id
        manifest = work / 'tiny-packs.sha256.json'
        manifest.write_text(json.dumps(dict(files=request['files'])), encoding='utf-8')
        if request['patch'] is not None:
            (work / 'patch.diff').write_text(request['patch'], encoding='utf-8')
        inputs = dict(request['inputs'], work_dir=str(work / 'scratch'), tiny_packs_manifest=str(manifest))
        checks = NodeChecks(store)
        checks._same_work(request['check'])
        receipt = checks._call_verifier(request['check'], work, approved_inputs=inputs)
        detail = {key: receipt[key] for key in ('call', 'state', 'reason', 'diagnostics', 'outputs') if key in receipt}
        (work / 'verifier.json').write_text(json.dumps(detail), encoding='utf-8')


if __name__ == '__main__':
    _scoped_verify(sys.argv[1])
