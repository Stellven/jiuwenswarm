"""Operator-owned pre-dispatch control, inaccessible to generated scientific code."""
import asyncio
import json
import os
from pathlib import Path
import re
import stat
import time

from .contracts import ResearchError
from .state import json_bytes, utc_now


def protected(path, directory=False):
    path = Path(path)
    if path.is_symlink():
        raise ResearchError('auth', 'Protected dispatch control cannot be a symlink')
    info = path.stat()
    if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022 or (directory and not path.is_dir()):
        raise ResearchError('auth', 'Protected dispatch control requires root-owned immutable inputs')
    return path


def validate_control_root(path):
    root = Path(path)
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ResearchError('auth', 'Canonical protected dispatch root required')
    return protected(root, True)


class DependencyDenied(ResearchError):
    def __init__(self, evidence_ref):
        self.evidence_ref = evidence_ref
        super().__init__('dependency_unavailable', 'Protected host denied the required dispatch dependency')


async def before_dispatch(store, run_id, node_id, accepted_refs, root, timeout_s):
    root = validate_control_root(root)
    run = store.get_run(run_id)
    with store._lock:
        rows = store.connection.execute('SELECT request_id FROM requests WHERE run_id=? AND account_id=?',
                                        (run_id, run['account_id'])).fetchall()
    if len(rows) != 1:
        raise ResearchError('auth', 'Protected barrier requires the unique original request')
    request_id = rows[0]['request_id']
    if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,256}', request_id) or request_id in {'.', '..'}:
        raise ResearchError('auth', 'Unsafe original request identity')
    slot = root/'requests'/request_id
    if not (slot/'plan.json').exists():
        return
    protected(root/'requests', True); protected(slot, True)
    raw = protected(slot/'plan.json').read_bytes()
    if len(raw) > 16384:
        raise ResearchError('auth', 'Protected dispatch plan exceeds bound')
    plan = json.loads(raw)
    if (plan.get('schema') != 'protected-dispatch-barrier:1' or plan.get('request_id') != request_id
            or plan.get('node_id') != node_id or plan.get('action') not in {'deny', 'hold'}
            or not re.fullmatch('[0-9a-f]{64}', plan.get('plan_sha256', ''))):
        raise ResearchError('auth', 'Protected plan differs from the actual dispatch')
    for ref in accepted_refs:
        store.read_blob(ref)
    if not accepted_refs:
        raise ResearchError('auth', 'Protected barrier needs original accepted predecessor outputs')
    reached = dict(schema='protected-dispatch-barrier-reached:1', request_id=request_id,
                   app_run_id=run_id, node_id=node_id, accepted_refs=accepted_refs,
                   plan_sha256=plan['plan_sha256'], observed_at=utc_now())
    target = root/'events'/(request_id+'.json')
    if target.parent.is_symlink() or target.parent.stat().st_uid != os.geteuid():
        raise ResearchError('auth', 'Protected app event directory has another owner')
    with target.open('xb') as stream:
        stream.write(json_bytes(reached)); stream.flush(); os.fsync(stream.fileno())
    deadline = time.monotonic()+max(0, timeout_s)
    while True:
        if store.cancellation_requested(run_id):
            raise ResearchError('cancelled', 'Cancellation observed at protected pre-dispatch barrier')
        response_path = slot/'response.json'
        if response_path.exists():
            response = json.loads(protected(response_path).read_bytes())
            if (response.get('request_id') != request_id or response.get('app_run_id') != run_id
                    or response.get('action') not in {'release', 'deny_dependency'}):
                raise ResearchError('auth', 'Protected response differs from the original request/run')
            evidence = store.put_blob(json_bytes(dict(plan=plan, reached=reached, response=response)),
                                      media_type='application/json')
            if response['action'] == 'deny_dependency':
                raise DependencyDenied(evidence)
            return
        if time.monotonic() >= deadline:
            raise ResearchError('budget_exhausted', 'Protected dispatch barrier exhausted the frozen run budget')
        await asyncio.sleep(.05)
