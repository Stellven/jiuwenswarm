"""Diagnostic jobs through the existing durable queue and owned-container guard."""
from pathlib import Path
import json
import os
import selectors
import subprocess
import sys
import time
from .execution_binding import file_digest
from .experiments import validate_contract
from .jobs import Jobs
from .store import FactoryError
from .lab_lifecycle import OwnedContainerGuard, atomic_json


class ExperimentJobs:
    def __init__(self, store):
        self.store, self.jobs = store, Jobs(store)

    def submit(self, task_id, contract_id, idem_key):
        path = Path(contract_id)
        contract = validate_contract(json.loads(path.read_text()))
        task = self.store.get_task(task_id)
        if file_digest(path) != task['constraints']['benchmark_contract_sha256']:
            raise ValueError('Experiment contract changed')
        if 'process.exec' not in task['allowed_effects']:
            raise ValueError('process.exec grant required')
        gpu = contract['specification']['purpose'] != 'cpu_analysis'
        if gpu and 'gpu.use' not in task['allowed_effects']:
            raise ValueError('gpu.use grant required')
        argv = [os.environ.get('FACTORY_HOST_PYTHON',sys.executable), '-m', 'jiuwenswarm.factory.experiment_jobs',
                task_id, '{attempt_id}', str(path)]
        request=dict(adapter='factory-experiment-v1',contract_id=str(path),contract_sha256=file_digest(path))
        parent=task['constraints'].get('factory_loop_parent')
        if parent:
            from .mission_supervisor import mission_root
            request['quiet_root']=str(mission_root(self.store.home,parent))
        from .execution_binding import worker_environment
        environment=dict(FACTORY_HOME=str(self.store.home), **worker_environment(task['constraints']['execution_binding']))
        return self.jobs.submit(task_id, 'lab', request, idem_key, 'gpu' if gpu else 'cpu', argv,
            contract['campaign_timeout_s'] + 120, environment)

    def result(self, task_id, attempt_id):
        attempt = self.jobs.status(attempt_id)
        if attempt['task_id'] != task_id:
            raise ValueError('Attempt belongs to another task')
        path = self.store.home / 'experiment-spool' / attempt_id / 'result.json'
        # Terminal evidence comes from digest-checked retained artifacts, not mutable spool JSON.
        report = dict(status='incomplete_evidence', execution_outcome='unknown',
                      evidence_completeness='incomplete', promotion_authorized=False)
        if attempt['state'] in {'succeeded', 'failed', 'cancelled'}:
            try:
                report = json.loads(self.store.artifact_bytes(task_id, attempt_id + ':result.json'))
                for ref in attempt['result_refs']:
                    self.store.artifact_bytes(task_id, ref)
            except (ValueError, KeyError, OSError, FactoryError) as exc:
                report.update(status='incomplete_evidence', evidence_completeness='incomplete',
                              error='Retained evidence unavailable or changed: ' + str(exc)[:500])
        complete = evidence_complete(report)
        report['verified_complete'] = complete
        report['promotion_authorized'] = False
        state = attempt['state']
        if state == 'succeeded' and not complete:
            state = 'failed'
            report.update(status='incomplete_evidence', evidence_completeness='incomplete')
        return dict(attempt_id=attempt_id, state=state, queue_state=attempt['state'], analysis=report)


def evidence_complete(report):
    return (report.get('evidence_completeness') == 'complete'
            and report.get('artifact_copy_returncode') == 0
            and report.get('cleanup', {}).get('container_removed') is True)


def container_argv(contract, probe, guard):
    limits = contract['limits']
    args = ['docker','run','--pull=never','--network=none','--read-only','--no-healthcheck',
            '--cap-drop=ALL','--security-opt=no-new-privileges', '--user',f'{os.getuid()}:{os.getgid()}',
            '--name', guard.name, '--cpus',str(limits['cpus']), '--memory',str(limits['memory_bytes']),
            '--memory-swap',str(limits['memory_bytes']), '--pids-limit',str(limits['pids']),
            '--tmpfs','/tmp:rw,nosuid,nodev,size=67108864',
            '--tmpfs',f"/out:rw,nosuid,nodev,size={max(1,limits['output_bytes']//2)}"]
    for key,value in guard.labels.items():
        args += ['--label',key+'='+value]
    mounts = [(str(probe), '/probe')]
    if contract['model']:
        mounts.append((contract['model']['path'], '/model/weights'))
    for source,destination in mounts:
        if any(c in source for c in (',','\n','\0')):
            raise ValueError('Nonportable mount path')
        args += ['--mount',f'type=bind,src={source},dst={destination},readonly']
    if contract['specification']['purpose'] != 'cpu_analysis':
        args += ['--gpus','all']
    recipe = contract['specification']['recipe']
    return args + ['--entrypoint','/bin/sh',contract['image'],'/probe/factory-wrapper.sh',*recipe]


def bounded_run(argv, root, timeout, maximum, completed=None):
    """Stream both channels; stop at the combined byte cap, retaining partial logs."""
    started = time.monotonic()
    process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    reason, total, completed_rc = None, 0, None
    try:
        with selectors.DefaultSelector() as poll, (root/'stdout').open('wb') as out, (root/'stderr').open('wb') as err:
            for pipe, sink in [(process.stdout,out),(process.stderr,err)]:
                os.set_blocking(pipe.fileno(),False)
                poll.register(pipe,selectors.EVENT_READ,sink)
            while poll.get_map():
                if completed is not None:
                    completed_rc = completed()
                    if completed_rc is not None:
                        completed = None
                if time.monotonic()-started >= timeout:
                    reason='timeout'; break
                events = poll.select(.1)
                if not events and completed_rc is not None:
                    break
                for key,_ in events:
                    data=os.read(key.fileobj.fileno(),65536)
                    if not data:
                        poll.unregister(key.fileobj); continue
                    available=max(0,maximum-total)
                    key.data.write(data[:available]); key.data.flush()
                    total += len(data)
                    if total>maximum:
                        reason='output_limit'; break
                if reason: break
            if reason or completed_rc is not None:
                process.kill()
            try: rc=process.wait(timeout=max(.1,timeout-(time.monotonic()-started)))
            except subprocess.TimeoutExpired:
                reason='timeout';process.kill();rc=process.wait()
        return dict(returncode=completed_rc if completed_rc is not None else rc, stop_reason=reason, output_bytes=min(total,maximum), elapsed_s=time.monotonic()-started)
    finally:
        if process.poll() is None: process.kill();process.wait()
        process.stdout.close();process.stderr.close()


def run(store, task_id, attempt_id, contract_path):
    root=store.home/'experiment-spool'/attempt_id
    root.mkdir(parents=True,exist_ok=False)
    report=dict(status='failed', execution_outcome='not_started', evidence_completeness='incomplete',
                promotion_authorized=False, measured_whole_model_tokens_per_second=None)
    try:
        task=store.get_task(task_id)
        attempt=store.read(task_id,attempt_id)
        if attempt['request'].get('quiet_root'):
            from .strata_lab import wait_quiet
            report['quiet']=wait_quiet(store.home,attempt_id,quiet_root=attempt['request']['quiet_root'])
        if file_digest(contract_path)!=task['constraints']['benchmark_contract_sha256']:
            raise ValueError('Frozen contract changed')
        from .execution_binding import verify_task
        report['execution_binding_id']=verify_task(store,task_id)
        contract=validate_contract(json.loads(Path(contract_path).read_text()))
        from .execution_binding import digest
        actual_binding=task['constraints']['runtime_execution_binding']
        if (digest({k:v for k,v in actual_binding.items() if k!='binding_id'})!=actual_binding['binding_id']
                or actual_binding['runtime_image']!=contract['image']
                or actual_binding['experiment_sha256']!=file_digest(contract_path)
                or actual_binding['factory_binding_id']!=report['execution_binding_id']):
            raise ValueError('Actual runtime execution binding differs')
        report['runtime_execution_binding']=actual_binding

        if contract['model'] and file_digest(contract['model']['path'])!=contract['model']['sha256']:
            raise ValueError('Model changed after preparation')
        probe=root/'probe';probe.mkdir()
        for name,text in contract['specification']['artifacts'].items():
            (probe/name).write_text(text)
        (probe/'factory-wrapper.sh').write_text('''#!/bin/sh
"$@"
rc=$?
printf '%s' "$rc" > /out/.factory-exit
# Keep bounded tmpfs artifacts alive until host capture and exact-owner cleanup.
sleep 120
exit "$rc"
''')
        inspected=json.loads(subprocess.check_output(['docker','image','inspect',contract['image']],stdin=subprocess.DEVNULL,text=True,timeout=30))[0]
        if inspected['Id'] != contract['image']:
            raise ValueError('Image identity differs')
        limits=contract['limits']
        with OwnedContainerGuard(root/'owner',contract['image'],lease_root=store.home.parent/'lab-lease',
                kind='lab' if contract['specification']['purpose']!='cpu_analysis' else 'cpu', timeout_s=limits['timeout_s']) as guard:
            last_poll = [0.0]
            def completed():
                if time.monotonic()-last_poll[0] < .5: return None
                last_poll[0]=time.monotonic()
                status=subprocess.run(['docker','exec',guard.name,'cat','/out/.factory-exit'],
                    stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
                if status.returncode==0 and status.stdout.isdigit(): return int(status.stdout)
                return None
            result=bounded_run(container_argv(contract,probe,guard),root,limits['timeout_s'],max(1,limits['output_bytes']//2),completed)
            report.update(result)
            report['execution_outcome'] = 'ok' if result['returncode'] == 0 and not result['stop_reason'] else 'failed'
            inspection=subprocess.run(['docker','inspect',guard.name],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=15)
            if inspection.returncode==0:
                report['container_state']=json.loads(inspection.stdout)[0]['State']
            # /out lives in bounded tmpfs. Preserve it before the guard removes the container.
            try:
                copied=subprocess.run(['docker','cp',guard.name+':/out',str(root/'artifacts')],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
                report.update(artifact_copy_returncode=copied.returncode,
                              artifact_copy_stdout=copied.stdout[:4096], artifact_copy_stderr=copied.stderr[:4096])
            except subprocess.TimeoutExpired as exc:
                report.update(artifact_copy_returncode=None, artifact_copy_error='timeout',
                              artifact_copy_stderr=str(exc.stderr or '')[:4096])
            report['evidence_completeness'] = ('complete' if report.get('artifact_copy_returncode') == 0
                and inspection.returncode == 0 and result['stop_reason'] != 'output_limit' else 'incomplete')
        report['cleanup']=json.loads((root/'owner/report.json').read_text())
    except Exception as exc:
        report['error']=str(exc)[:2000]
        report['evidence_completeness']='incomplete'
    finally:
        if not evidence_complete(report):
            report.update(status='incomplete_evidence', evidence_completeness='incomplete')
        else:
            report['status'] = 'succeeded' if report['execution_outcome'] == 'ok' else 'failed'
        atomic_json(root/'result.json',report)
        refs=[]
        for path in sorted(root.rglob('*')):
            if path.is_file() and not path.is_symlink():
                name=path.relative_to(root).as_posix()
                artifact=store.put_artifact(task_id,attempt_id+':'+name,path,'application/octet-stream',attempt_id)
                refs.append(artifact['artifact_id'])
        from .jobs import metadata
        attempt=store.read(task_id,attempt_id)
        metadata(store,attempt,result_refs=refs)
    return 0 if report['status']=='succeeded' else 1


if __name__=='__main__':
    from .store import Store
    store=Store(os.environ['FACTORY_HOME'])
    try: sys.exit(run(store,*sys.argv[1:]))
    finally: store.close()
