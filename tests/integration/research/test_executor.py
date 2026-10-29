"""Actual Linux executor probes. Missing delegation is a failed prerequisite.

These controlled host-mechanics jobs do not claim admission or live research
acceptance. Raw receipts retain actual confinement/resource observations.
"""
import hashlib
import asyncio
import json
import os
import tempfile
import uuid
import time
from pathlib import Path

import pytest

from jiuwenswarm.research.executor import ExecutionJob, RestrictedExecutor


@pytest.mark.asyncio
async def test_private_stdin_event_budget_hook_retains_raw_logs_and_empties_tree(actual_executor):
    from jiuwenswarm.research.builder_launcher import BuilderEvents
    executor, make, captured, work = actual_executor
    program = '''import json,sys,time
from pathlib import Path
data=sys.stdin.buffer.read()
Path('received-input').write_bytes(data)
print('partial controlled stderr',file=sys.stderr,flush=True)
for i in range(2):
    print(json.dumps({'type':'item.started','item':{'id':str(i),'type':'command_execution','command':'pwd'}}),flush=True)
time.sleep(30)
'''
    job=make(program,timeout=3)
    state=BuilderEvents(2)
    result=await executor._run_kernel(job,executor._sandbox(job),output_parent=work.parent,
        stdin_bytes='controlled unicode \u03bb'.encode(),stdout_line_observer=state.feed,stdout_line_limit=1024)
    assert result['termination_reason']=='budget_exceeded'
    assert state.tool_count==2 and not state.success
    assert (work/'received-input').read_bytes()=='controlled unicode \u03bb'.encode()
    assert b'"id": "1"' in captured[result['stdout_ref']['id']]
    assert captured[result['stderr_ref']['id']]==b'partial controlled stderr\n'
    assert executor.active=={}
    assert not (executor.cgroup_root/job.job_id/'cgroup.procs').read_text().strip()


@pytest.mark.asyncio
async def test_builder_parent_probe_never_claims_tool_network_qualification(actual_executor):
    from jiuwenswarm.research.builder_launcher import BuilderLauncher,BuilderStage
    executor,make,captured,work=actual_executor
    job=make("print('parent probe mechanics only')")
    resources=work.parent/'builder-resources';resources.mkdir(mode=0o555)
    home=work.parent/'builder-home';home.mkdir(mode=0o700);os.chown(home,10002,10002)
    # No CLI, credential, model or tool is invoked by this kernel mechanics test.
    launcher=BuilderLauncher(store=None,executor=executor,runtime=None,authorize=None)
    stage=BuilderStage(job.job_id,work.parent,work,resources)
    result=await executor._run_kernel(job,launcher._command(stage,home,job.argv),output_parent=work.parent)
    assert result['termination_reason']=='completed',captured[result['stderr_ref']['id']]
    proof=json.loads(captured[result['observed_limits']['isolation_probe_ref']['id']])
    assert proof['profile']=='builder-parent' and proof['ready']
    assert proof['network_namespace']==os.readlink('/proc/self/ns/net')
    assert proof['network'] is None and result['observed_limits']['network'] is None
    assert all(proof['denied_paths'].values()) and proof['executor_uid']==10002
    assert captured[result['stdout_ref']['id']]==b'parent probe mechanics only\n'


@pytest.mark.asyncio
async def test_cancellation_waits_for_actual_owned_kernel_tree(actual_executor):
    executor, make, captured, work = actual_executor
    job = make("from pathlib import Path; import time; Path('started').write_text('1'); time.sleep(20)", timeout=30)
    task = asyncio.create_task(executor.run(job))
    try:
        async with asyncio.timeout(5):
            while not (work / 'started').is_file():
                await asyncio.sleep(0.01)
        task.cancel()
        result = await task
        assert result['termination_reason'] == 'cancelled'
        assert not executor.active
        group = executor.cgroup_root / job.job_id
        assert not (group / 'cgroup.procs').read_text().strip()
        assert 'populated 0' in (group / 'cgroup.events').read_text()
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_rpc_refuses_kernel_execution_without_original_attempt_resources(actual_executor, tmp_path):
    from jiuwenswarm.research.executor_rpc import ClaimLedger, ExecutionOperations
    executor, make, captured, work = actual_executor
    job = make("from pathlib import Path; import time; Path('started').write_text('1'); time.sleep(20)", timeout=30)
    async def factory(contract, inputs, *, binding, **selection):
        return job
    executor.job_factory = factory
    request = {'contract_ref': job.contract_ref, 'invocation_id': job.invocation_id, 'execution_id': 'controlled-execution'}
    contract = {'run_id': job.run_id}
    async def authorize(payload):
        assert payload == request
        return {**request, 'contract': contract, 'execution_deadline_monotonic_s': time.monotonic()+30}
    async def containment(payload):
        assert payload == {'run_id': job.run_id, 'request_id': 'controlled-cancel'}
        return {**payload, 'authorized': True, 'invocation_ids': [job.invocation_id]}
    ledger = ClaimLedger(tmp_path / 'claims')
    owner = ExecutionOperations(backend=executor, authorize=authorize, resolve_inputs=lambda _: {}, ledger=ledger,
                                authorize_containment=containment)
    selection = {key: getattr(job, key) for key in ('role', 'repeat_index', 'seed', 'sequence', 'subject_ref', 'hardware_ref')}
    from jiuwenswarm.research.executor import ExecutorBlocked
    try:
        with pytest.raises(ExecutorBlocked, match='ORIGINAL_ACTIVE_ATTEMPT_RESOURCES_REQUIRED'):
            await owner.perform('measure_job', {**request, 'selection': selection})
        assert not executor.active and not (work / 'started').exists()
    finally:
        ledger.close()


@pytest.fixture
def actual_executor(request):
    configured = os.environ.get('AI4R_EXECUTOR_CGROUP_ROOT')
    if not configured:
        pytest.fail('Job-owned Linux cgroup delegation is required; use compose.executor-verify.yaml')
    root = Path(tempfile.mkdtemp(prefix='ai4r-executor-'))
    root.chmod(0o711)
    work = root / 'work'
    work.mkdir(mode=0o700)
    os.chown(work, 10002, 10002)
    captured = {}
    def capture(data, **kwargs):
        digest = hashlib.sha256(data).hexdigest()
        ref = {'id': 'blob:' + digest, 'sha256': digest}
        captured[ref['id']] = data
        return ref
    executor = RestrictedExecutor(workspace_root=root, cgroup_root=configured,
        authorize_job=lambda job: job, capture=capture)
    # Optional raw host-mechanics evidence; never used as product acceptance.
    results = []
    original_kernel = executor._run_kernel
    async def retain_kernel(*args, **kwargs):
        result = await original_kernel(*args, **kwargs)
        results.append(result)
        return result
    executor._run_kernel = retain_kernel
    assert executor.prerequisites() == []
    jobs = []
    def make(program, timeout=2, memory=64, pids=16):
        ref = {'id': 'controlled-fixture', 'sha256': 'a' * 64}
        identifier = 'probe-' + uuid.uuid4().hex
        jobs.append(identifier)
        return ExecutionJob(job_id=identifier, invocation_id='controlled-invocation', contract_ref=ref,
            run_id='controlled-run', node_id='controlled-node', attempt_id='controlled-attempt', sequence=len(jobs),
            role='baseline', repeat_index=0, seed=1, argv=('/usr/local/bin/python3', '-c', program), cwd=work,
            timeout_s=timeout, memory_mb=memory, pids_max=pids, baseline_ref=ref, validation_ref=ref,
            environment_ref=ref, subject_ref=ref, hardware_ref=ref)
    yield executor, make, captured, work
    if evidence := os.environ.get('AI4R_EXECUTOR_EVIDENCE_ROOT'):
        target = Path(evidence) / hashlib.sha256(request.node.nodeid.encode()).hexdigest()
        target.mkdir(mode=0o700, parents=True, exist_ok=False)
        (target / 'receipts.json').write_text(json.dumps({'test': request.node.nodeid,
            'scope': 'Controlled actual Linux kernel mechanics; no installed app or model acceptance',
            'results': results}, indent=2))
        for ref, data in captured.items():
            (target / ref.removeprefix('blob:')).write_bytes(data)
    for identifier in jobs:
        group = Path(configured) / identifier
        if group.exists():
            assert group.resolve().parent == Path(configured).resolve()
            assert not (group / 'cgroup.procs').read_text().strip()
            group.rmdir()


@pytest.mark.asyncio
async def test_actual_namespace_identity_network_and_workspace_write(actual_executor):
    executor, make, captured, work = actual_executor
    result = await executor.run(make("from pathlib import Path; Path('allowed').write_text('allowed'); print('actual permitted write')"))
    assert result['exit_code'] == 0 and result['termination_reason'] == 'completed', captured[result['stderr_ref']['id']].decode()
    assert work.joinpath('allowed').read_text() == 'allowed'
    assert captured[result['stdout_ref']['id']] == b'actual permitted write\n'
    proof = json.loads(captured[result['observed_limits']['isolation_probe_ref']['id']])
    assert proof['ready'] and proof['executor_uid'] == 10002 and proof['executor_gid'] == 10002
    assert proof['cap_effective'] == '0000000000000000'
    assert all(proof['denied_paths'].values()) and proof['network'] == 'none'
    assert result['observed_limits']['memory_max'] == str(64 * 1024 * 1024)
    assert result['observed_limits']['pids_max'] == '16'
    assert result['observed_limits']['network'] == 'none'


@pytest.mark.asyncio
async def test_actual_wall_timeout_kills_own_process_tree(actual_executor):
    executor, make, captured, work = actual_executor
    result = await executor.run(make('import time; time.sleep(60)', timeout=0.5))
    assert result['termination_reason'] == 'timeout', captured[result['stderr_ref']['id']].decode()
    assert result['exit_code'] != 0
    assert executor.active == {}


@pytest.mark.asyncio
async def test_actual_memory_exhaustion_is_observed_and_job_tree_is_empty(actual_executor):
    executor, make, captured, work = actual_executor
    result = await executor.run(make('allocation = bytearray(512 * 1024 * 1024)', memory=64))
    assert result['termination_reason'] == 'resource_limit_exceeded'
    assert any(line.startswith('oom_kill ') and int(line.split()[1]) > 0 for line in result['memory_events'].splitlines())
    assert result['exit_code'] != 0 and executor.active == {}


@pytest.mark.asyncio
async def test_actual_pid_exhaustion_is_observed_without_leaving_children(actual_executor):
    executor, make, captured, work = actual_executor
    program = '''import os, time
try:
    while True:
        if os.fork() == 0:
            time.sleep(30)
            os._exit(0)
except BlockingIOError:
    print("pid limit observed", flush=True)
'''
    result = await executor.run(make(program, pids=8))
    assert result['termination_reason'] == 'resource_limit_exceeded'
    assert any(line.startswith('max ') and int(line.split()[1]) > 0 for line in result['pids_events'].splitlines())
    assert executor.active == {}


@pytest.mark.asyncio
async def test_untrusted_process_cannot_read_protected_paths_or_reach_network(actual_executor):
    executor, make, captured, work = actual_executor
    program = '''import os, socket, json
paths = ["/var/lib/ai4r", "/var/lib/ai4r-accounts", "/run/ai4r", "/var/run/docker.sock", "/hidden-fixtures"]
result = {}
for index, path in enumerate(paths):
    alias = "escape_" + str(index)
    os.symlink(path, alias)
    try:
        fd = os.open(alias, os.O_RDONLY | os.O_NONBLOCK)
    except (FileNotFoundError, PermissionError):
        result[path] = "denied"
    else:
        os.close(fd)
        result[path] = "READABLE"
with socket.socket() as probe:
    probe.settimeout(.2)
    result["network_error"] = probe.connect_ex(("192.0.2.1", 9))
print(json.dumps(result))
'''
    result = await executor.run(make(program))
    assert result['exit_code'] == 0
    observed = json.loads(captured[result['stdout_ref']['id']])
    assert all(value == 'denied' for key, value in observed.items() if key != 'network_error')
    assert observed['network_error'] in {1, 13, 99, 101, 113}


@pytest.mark.asyncio
async def test_existing_host_canaries_and_live_listeners_remain_unreachable(actual_executor):
    """Positive controls exist outside the job; absence is not the fixture."""
    import socket
    executor, make, captured, work = actual_executor
    outside = executor.workspace_root / 'protected-host'
    outside.mkdir(mode=0o700)
    pins, paths = {}, {}
    for role, uid in [('state', 10001), ('account', 10001), ('library', 0), ('fixture', 12002)]:
        path = outside / role
        raw = ('synthetic-private-canary:' + role + ':' + uuid.uuid4().hex).encode()
        path.write_bytes(raw); path.chmod(0o600); os.chown(path, uid, uid)
        # The trusted controller proves each real file exists and is readable.
        pins[role] = hashlib.sha256(path.read_bytes()).hexdigest()
        paths[role] = str(path)
    with socket.socket(socket.AF_UNIX) as local, socket.socket() as tcp:
        local_path = outside / 'controlled-broker.sock'
        local.bind(str(local_path)); local.listen(2)
        tcp.bind(('127.0.0.1', 0)); tcp.listen(2)
        # Real positive-control connections prove both listeners were live.
        with socket.socket(socket.AF_UNIX) as control:
            control.connect(str(local_path)); peer, _ = local.accept(); peer.close()
        with socket.create_connection(tcp.getsockname(), timeout=1):
            peer, _ = tcp.accept(); peer.close()
        program = '''import json,os,socket
paths = %r
observed = {}
for role,path in paths.items():
    os.symlink(path, 'escape-' + role)
    try:
        with open('escape-' + role, 'rb') as stream: stream.read(1)
        observed[role] = 'READABLE'
    except (FileNotFoundError,PermissionError): observed[role] = 'denied'
for kind,address in [('broker',%r),('network',%r)]:
    with socket.socket(socket.AF_UNIX if kind == 'broker' else socket.AF_INET) as probe:
        probe.settimeout(.2)
        try: probe.connect(address); observed[kind] = 'CONNECTED'
        except OSError: observed[kind] = 'denied'
print(json.dumps(observed,sort_keys=True))
''' % (paths, str(local_path), tcp.getsockname())
        result = await executor.run(make(program, timeout=3))
        assert result['exit_code'] == 0
        observed = json.loads(captured[result['stdout_ref']['id']])
        assert observed == {name: 'denied' for name in [*paths, 'broker', 'network']}
        for listener in (local, tcp):
            listener.settimeout(.1)
            with pytest.raises(TimeoutError): listener.accept()
    assert {role: hashlib.sha256(Path(path).read_bytes()).hexdigest() for role, path in paths.items()} == pins
    assert executor.active == {}
