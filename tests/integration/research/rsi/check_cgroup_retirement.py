"""Opt-in frozen-kernel cgroup lifecycle verification; no model or timing bench.

Run as root with a fresh, dedicated cgroup delegation (limit <= 4) and a new
output directory. This driver never changes cgroup quotas or existing evidence.
The caller provisions the delegation and retains all output records.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import time

from jiuwenswarm.research_rsi.records import RecordStore
from jiuwenswarm.research_rsi.targets.capsule_executor import (
    bounded_executor, executor_abi, load_v18_executor)
from jiuwenswarm.research_rsi.targets.cgroup_lifecycle import check_capacity, retire_owned_group


async def exercise(root, output):
    if os.geteuid() != 0:
        raise RuntimeError('ROOT_REQUIRED')
    root = root.resolve(strict=True)
    limit = (root / 'cgroup.max.descendants').read_text().strip()
    if limit == 'max' or not 1 <= int(limit) <= 4 or any(p.is_dir() for p in root.iterdir()):
        raise RuntimeError('FRESH_DEDICATED_SMALL_CGROUP_REQUIRED')
    output.mkdir(mode=0o711, parents=False, exist_ok=False)
    output.chmod(0o711)
    work_root = output / 'work'; work_root.mkdir(mode=0o711)
    store = RecordStore(output / 'records')
    kernel = load_v18_executor()
    abi = executor_abi(kernel.RestrictedExecutor, kernel.ExecutionJob, kernel.ReadonlyMount)
    issued = {}
    def authorize(job):
        if issued.get(job.job_id) != job:
            raise RuntimeError('UNISSUED_VERIFICATION_JOB')
        return job
    executor = bounded_executor(kernel.RestrictedExecutor)(workspace_root=output,
        cgroup_root=root, authorize_job=authorize,
        capture=lambda raw, **kwargs: store.put_bytes(raw), executor_uid=12003, executor_gid=12003)
    if executor.prerequisites():
        raise RuntimeError(str(executor.prerequisites()))
    pin = store.put({'purpose': 'native lifecycle mechanics; no optimization claim'})
    rows = []
    for index, kind in enumerate(('success', 'nonzero', 'success', 'timeout', 'cancel', 'success')):
        deadline = time.monotonic() + 10
        while True:
            try:
                capacity = check_capacity(root)
                break
            except ValueError as exc:
                if str(exc) != 'CGROUP_CAPACITY_EXHAUSTED' or time.monotonic() >= deadline:
                    raise
                await asyncio.sleep(.05)
        ident = f'lifecycle-check-{index + 1}'
        work = work_root / ident; work.mkdir(mode=0o700); os.chown(work, 12003, 12003)
        if kind == 'cancel':
            body = "import time; from pathlib import Path; Path('cancel-ready').write_text('ready'); time.sleep(30)"
        elif kind == 'timeout':
            body = "import time; time.sleep(30)"
        elif kind == 'nonzero':
            body = "import sys; print('native-lifecycle'); sys.exit(7)"
        else:
            body = "print('native-lifecycle')"
        subject = store.put_bytes(body.encode())
        job = kernel.ExecutionJob(job_id=ident, invocation_id=ident, contract_ref=pin,
            run_id='cgroup-lifecycle-verification', node_id='native-mechanics', attempt_id=kind,
            sequence=index + 1, role='treatment', repeat_index=0, seed=0,
            argv=('/usr/local/bin/python3', '-I', '-c', body), cwd=work,
            timeout_s=2 if kind == 'timeout' else 10, memory_mb=128, pids_max=16,
            baseline_ref=pin, validation_ref=pin, environment_ref=pin,
            subject_ref=subject, hardware_ref=pin)
        issued[ident] = job
        start_ref = store.put({'job_id': ident, 'candidate_ref': subject, 'purpose': kind})
        task = asyncio.create_task(executor.run(job))
        if kind == 'cancel':
            # The trusted probe is flushed before exec. A marker written by
            # the body proves cancellation cannot race probe/startup latency.
            marker = work / 'cancel-ready'
            deadline = time.monotonic() + 5
            while not task.done() and time.monotonic() < deadline:
                try:
                    ready = marker.read_text() == 'ready'
                except FileNotFoundError:
                    ready = False
                if ready:
                    task.cancel()
                    break
                await asyncio.sleep(.01)
            # If startup never reached the marker, let the executor's bounded
            # timeout finish and capture its actual terminal evidence below.
        receipt = await task
        receipt_ref = store.put(receipt)
        store.put({'schema': 'ai4r-cgroup-native-job-observed:1', 'job_id': ident,
                   'kind': kind, 'start_ref': start_ref, 'receipt_ref': receipt_ref})
        stdout = store.read(receipt['stdout_ref'])
        stderr = store.read(receipt['stderr_ref'])
        proof = json.loads(store.read(receipt['observed_limits']['isolation_probe_ref']))
        if proof.get('ready') is not True:
            raise AssertionError(('NATIVE_PROBE_NOT_READY', kind, proof, receipt_ref))
        expected = {'timeout': 'timeout', 'cancel': 'cancelled'}.get(kind, 'completed')
        if receipt['termination_reason'] != expected:
            raise AssertionError((kind, receipt['termination_reason'], stderr, receipt_ref))
        if kind in ('success', 'nonzero'):
            expected_exit = 7 if kind == 'nonzero' else 0
            if receipt['exit_code'] != expected_exit or stdout != b'native-lifecycle\n':
                raise AssertionError(('NATIVE_OUTPUT_OR_EXIT_DIFFERS', kind, receipt, stdout))
        retirement = retire_owned_group(executor, job, receipt=receipt, start_ref=start_ref, store=store)
        if (root / ident).exists() or executor.active or store.get(retirement['receipt_ref']) != receipt:
            raise AssertionError('RETIREMENT_OR_EVIDENCE_FAILED')
        rows.append({'kind': kind, 'job_id': ident, 'termination': receipt['termination_reason'],
                     'exit_code': receipt['exit_code'], 'retirement': retirement,
                     'capacity_before': capacity, 'remaining_live_directories': len([p for p in root.iterdir() if p.is_dir()])})
        print(json.dumps(rows[-1]), flush=True)
    summary = {'schema': 'ai4r-cgroup-native-verification:1', 'abi': abi, 'limit': int(limit),
               'jobs': rows, 'passed': True, 'model_calls': 0}
    ref = store.put(summary)
    (output / 'summary.json').write_text(json.dumps({'summary_ref': ref, **summary}, indent=2) + '\n')
    store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cgroup-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(exercise(args.cgroup_root, args.out))
