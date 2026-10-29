"""Actual finite CLI producer. Missing live resources fail, never skip/pass.

The live case requires a pure installed qualified image, dedicated credential,
external budget/revocation and captured closed operator binding. It produces only
tool qualification; a normal governed Builder/cap/fault run remains required by
the complete M1-001/V13 procedure. No model access occurs in the parent-control
negative probe.
"""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

import pytest

from jiuwenswarm.research.builder_qualification import (PREFIX, PROBE_PATH, PositiveControls,
    add_parent_controls, qualify_builder_tools, validate_probe)
from jiuwenswarm.research.builder_launcher import BuilderKernelJob, BuilderLauncher, BuilderStage, _custody
from jiuwenswarm.research.executor import ExecutorBlocked, RestrictedExecutor
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


@pytest.mark.asyncio
async def test_pinned_cli_builder_tool_sandbox_qualification():
    locator = os.environ.get('AI4R_BUILDER_QUALIFICATION_PROFILE')
    if not locator:
        pytest.fail('BLOCKED: dedicated live Builder qualification profile/credential/budget/revocation are unavailable; no CLI launched')
    _custody(Path(locator), owner=0, mode=0o600)
    profile = json.loads(Path(locator).read_bytes())
    if set(profile) != {'schema', 'job_id', 'build_id', 'store_root', 'binding_ref'} or profile['schema'] != 'ai4r-builder-qualification-target:1':
        pytest.fail('BLOCKED: closed Builder qualification target is invalid')
    if not isinstance(profile['job_id'], str) or not re.fullmatch(r'ai4r-builder-qual-[a-z0-9-]{1,64}', profile['job_id']):
        pytest.fail('BLOCKED: qualification job identity is outside its fixed scope')
    store_root = Path('/var/lib/ai4r-builder-qualification') / profile['job_id'] / 'state'
    if Path(profile['store_root']) != store_root:
        pytest.fail('BLOCKED: isolated qualification store is outside its fixed owned root')
    _custody(store_root, owner=0, mode=0o700, directory=True)
    configured = os.environ.get('AI4R_EXECUTOR_CGROUP_ROOT')
    if not configured:
        pytest.fail('BLOCKED: actual owned cgroup delegation is unavailable')
    from jiuwenswarm.research.native_ports import verify_installed_build
    assert verify_installed_build() == profile['build_id'], 'BLOCKED: exact pure installed build is required'
    store = SQLiteRunStore(store_root)
    executor = RestrictedExecutor(workspace_root='/var/lib/ai4r-executor/qualification', cgroup_root=configured,
        authorize_job=lambda _: (_ for _ in ()).throw(ExecutorBlocked('NO_GENERAL_EXECUTION_AUTHORITY')), capture=store.put_blob)
    from jiuwenswarm.research.trajectory import start_native_capture, stop_native_capture
    from jiuwenswarm.research.native_logging import configure_native_logging
    configure_native_logging(store_root / 'logs')
    start_native_capture(store_root / 'trajectory')
    try:
        result = await qualify_builder_tools(store=store, executor=executor, binding_ref=profile['binding_ref'], build_id=profile['build_id'])
        proof = store.read_record(result['qualification_ref'])
        assert proof['observed_runtime'] is True and proof['tool_network'] == 'none'
        assert store.record_kind(result['producer_ref']) == 'builder_tool_qualification'
        assert store.read_record(result['model_call_ref'])['outcome'] == 'completed'
        assert not executor.active
    finally:
        # No shared branch deletion. Only empty exact child groups issued here.
        for identifier, owned in executor.owned_groups.items():
            group = Path(owned['path'])
            assert group.parent.resolve() == Path(configured).resolve() and group.stat().st_ino == owned['inode']
            assert not (group / 'cgroup.procs').read_text().strip()
            group.rmdir()
        stop_native_capture()
        store.close()


@pytest.mark.asyncio
async def test_builder_parent_probe_cannot_certify_cli_tool_network_denial():
    """Actual permissive parent is the negative control, without a CLI/model."""
    configured = os.environ.get('AI4R_EXECUTOR_CGROUP_ROOT')
    if not configured:
        pytest.fail('BLOCKED: job-owned cgroup delegation required; no model call')
    base = Path('/var/lib/ai4r-executor/qualification')
    base.mkdir(mode=0o711, parents=True, exist_ok=True)
    parent = base / ('negative-' + uuid.uuid4().hex); parent.mkdir(mode=0o711)
    work = parent / 'work'; work.mkdir(mode=0o700); os.chown(work, 10002, 10002)
    resources = parent / 'resources'; resources.mkdir(mode=0o755)
    home = parent / 'home'; home.mkdir(mode=0o700); os.chown(home, 10002, 10002)
    captured = {}
    def capture(raw, **kwargs):
        digest = hashlib.sha256(raw).hexdigest(); ref = {'id': 'blob:' + digest, 'sha256': digest}
        captured[ref['id']] = raw
        return ref
    executor = RestrictedExecutor(workspace_root=base, cgroup_root=configured, authorize_job=lambda _: None, capture=capture)
    job_id = 'builder-negative-' + uuid.uuid4().hex
    ref = {'id': 'controlled-parent-negative', 'sha256': 'a' * 64}
    job = BuilderKernelJob(job_id, ref, 'controlled-parent-negative',
        ('/usr/local/bin/python3', '-I', '/resources/qualification_probe.py', '/resources/probe_inputs.json'), 10, 64, 16)
    stage = BuilderStage(job_id, parent, work, resources)
    try:
        with PositiveControls(parent, 'a' * 64) as controls:
            (resources / 'qualification_probe.py').write_bytes(PROBE_PATH.read_bytes())
            (resources / 'probe_inputs.json').write_bytes(json_bytes(controls.inputs()))
            for path in resources.iterdir(): path.chmod(0o444)
            resources.chmod(0o555)
            command = BuilderLauncher(store=None, executor=executor, runtime=None, authorize=None)._command(stage, home, job.argv)
            command = add_parent_controls(command, controls)
            result = await executor._run_kernel(job, command, output_parent=parent)
            assert result['termination_reason'] == 'completed' and result['exit_code'] == 0
            assert controls.consume_parent_positive() == {'ipv4': True, 'ipv6': True}
            raw = captured[result['stdout_ref']['id']].decode().strip()
            assert raw.startswith(PREFIX)
            observed = json.loads(raw[len(PREFIX):])
            assert observed['uid'] == observed['gid'] == 10002
            assert all(observed['denied_paths'].values()) and observed['workspace_write']
            assert all(value['denied'] is False for value in observed['network'].values())
            with pytest.raises(ExecutorBlocked): validate_probe(observed, 'a' * 64)
            for listener in controls.sockets.values():
                accepted, _ = listener.accept(); accepted.close()
            controls.verify()
            proof = json.loads(captured[result['observed_limits']['isolation_probe_ref']['id']])
            assert proof['profile'] == 'builder-parent' and proof['network'] is None
            assert proof['parent_connectivity'] == {'ipv4': True, 'ipv6': True}
            if Path('/evidence').is_dir():
                target = Path('/evidence/builder-parent-negative.json')
                with target.open('x') as output:
                    json.dump({'model_calls': 0, 'cli_launched': False, 'parent_probe': observed, 'kernel_receipt': result}, output, indent=2)
    finally:
        group = Path(configured) / job_id
        if group.exists():
            assert not (group / 'cgroup.procs').read_text().strip(); group.rmdir()
        # Exact job-owned tree only; preserve shared qualification root/branch.
        assert parent.resolve().parent == base.resolve()
        shutil.rmtree(parent)
