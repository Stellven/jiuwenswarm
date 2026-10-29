"""Real ordinary M1 processes in the app image; no host cgroup prerequisites."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import tempfile
import uuid

import pytest

from jiuwenswarm.research.executor import ExecutionJob, RestrictedExecutor, ReadonlyMount


@pytest.fixture
def actual_m1_process():
    assert os.geteuid() == 0, 'Run this test in the Docker verify image'
    assert Path('/resources').is_dir(), 'Supply the app /resources tmpfs'
    root = Path(tempfile.mkdtemp(prefix='m1-process-')); root.chmod(0o711)
    work = root/'work'; work.mkdir(mode=0o700); os.chown(work,10002,10002)
    captured = {}
    def capture(data, **kwargs):
        digest=hashlib.sha256(data).hexdigest(); captured[digest]=data
        return {'id':'blob:'+digest,'sha256':digest}
    ref={'id':'controlled-host-mechanics','sha256':'a'*64}
    executor=RestrictedExecutor(workspace_root=root,cgroup_root=None,authorize_job=lambda job:job,
        capture=capture,execution_mode='m1_app_process',runtime_ref=ref,allowed_asset_roots=[root])
    assert executor.prerequisites()==[]
    def make(source, *, timeout=3, output_limit=None, mounts=()):
        return ExecutionJob(job_id='m1-'+uuid.uuid4().hex,invocation_id='controlled-host-mechanics',
            contract_ref=ref,run_id='controlled-run',node_id='controlled-node',attempt_id='a1',
            sequence=1,role='baseline',repeat_index=0,seed=1,
            argv=('/usr/local/bin/python3','-c',source),cwd=work,
            timeout_s=timeout,memory_mb=128,pids_max=64,baseline_ref=ref,validation_ref=ref,
            environment_ref=ref,subject_ref=ref,hardware_ref=ref,
            output_limit_bytes=output_limit,readonly_mounts=mounts)
    return executor,make,captured,work,root


@pytest.mark.asyncio
async def test_real_m1_process_has_actual_uid_and_shared_namespace_without_cgroup(actual_m1_process):
    executor,make,captured,work,root=actual_m1_process
    raw=await executor.run(make("import os,json;print(json.dumps({'uid':os.geteuid(),'net':os.readlink('/proc/self/ns/net')}))"))
    assert raw['termination_reason']=='completed' and raw['exit_code']==0
    output=json.loads(captured[raw['stdout_ref']['sha256']])
    assert output=={'uid':10002,'net':os.readlink('/proc/self/ns/net')}
    limits=raw['observed_limits']
    assert limits['network']=='inherited' and limits['memory_max'] is None and limits['pids_max'] is None
    assert 'isolation_probe_ref' not in limits
    proof=json.loads(captured[limits['process_observation_ref']['sha256']])
    assert proof['no_new_privileges']=='1' and int(proof['cap_effective'],16)==0
    assert limits['cpu_affinity']==proof['cpu_affinity']
    assert executor.active=={}


@pytest.mark.asyncio
async def test_real_m1_timeout_and_descendant_cleanup(actual_m1_process):
    executor,make,captured,work,root=actual_m1_process
    raw=await executor.run(make('import os,time;os.fork();time.sleep(20)',timeout=.2))
    assert raw['termination_reason']=='timeout' and raw['wall_time_s']<4
    assert raw['observed_limits']['process_group_cleanup'] is True and not executor.active


@pytest.mark.asyncio
async def test_real_m1_output_limit_retains_bounded_bytes(actual_m1_process):
    executor,make,captured,work,root=actual_m1_process
    raw=await executor.run(make('print("x"*65536)',output_limit=256))
    assert raw['termination_reason']=='output_limit_exceeded'
    assert len(captured[raw['stdout_ref']['sha256']])==256


@pytest.mark.asyncio
async def test_real_m1_resource_paths_preserve_capture_and_are_removed(actual_m1_process):
    executor,make,captured,work,root=actual_m1_process
    resource=root/'validation';resource.mkdir(mode=0o755)
    data=resource/'data.json';data.write_text('{"digits":17}');data.chmod(0o444)
    resource.chmod(0o555)
    ref={'id':'captured-resource','sha256':hashlib.sha256(data.read_bytes()).hexdigest()}
    calls=[]
    executor.verify_mount=lambda mount:calls.append(mount.ref)
    mount=ReadonlyMount(resource,'/resources/validation',ref)
    raw=await executor.run(make("from pathlib import Path;print(Path('/resources/validation/data.json').read_text())",mounts=(mount,)))
    assert raw['exit_code']==0 and calls==[ref]
    assert json.loads(captured[raw['stdout_ref']['sha256']])=={'digits':17}
    assert not Path('/resources/validation').exists()
    assert data.read_text()=='{"digits":17}'


@pytest.mark.asyncio
async def test_real_m1_cancel_retains_terminal_receipt(actual_m1_process):
    executor,make,captured,work,root=actual_m1_process
    task=asyncio.create_task(executor.run(make("from pathlib import Path;import time;Path('started').write_text('1');time.sleep(20)")))
    async with asyncio.timeout(3):
        while not (work/'started').exists():
            await asyncio.sleep(.01)
    task.cancel();raw=await task
    assert raw['termination_reason']=='cancelled' and not executor.active
    assert (root/(raw['job_id']+'.capture')/'finished.json').is_file()
