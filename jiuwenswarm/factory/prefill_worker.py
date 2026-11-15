"""Bounded fresh-process native prefill worker; no experiment decisions."""
import argparse
import json
import os
from pathlib import Path
import signal
import time

from . import benchmark, lab_recorder, prefill_workbench as tools
from .benchmark_worker import admission, check_source_pins, _recover_partial, _seal, _successful
from .contract import atomic_json
from .engine_adapters import sha


def run(contract_path,output,task_id,attempt_id,contract_sha256):
    contract_path,output=Path(contract_path).resolve(),Path(output).resolve()
    if output.exists() or contract_path.is_relative_to(output):
        raise ValueError('Scoped output already exists or overlaps contract')
    output.mkdir(parents=True)
    started=time.monotonic();rc=1
    result=dict(schema_version=1,task_id=task_id,attempt_id=attempt_id,contract_sha256=contract_sha256,
        execution_outcome='measurement_failed',evidence_completeness='partial',cells=[],
        scope=tools.SCOPE,limitations=['Prefill microbenchmark only; no full-generation quality or overall speed claim.'])
    handlers={}
    for number in (signal.SIGTERM,signal.SIGINT):
        handlers[number]=signal.getsignal(number)
        signal.signal(number,lambda signum,frame:(_ for _ in ()).throw(SystemExit(128+signum)))
    try:
        if sha(contract_path)!=contract_sha256:raise ValueError('Frozen scoped contract changed')
        c=tools.validate_contract(json.loads(contract_path.read_text()))
        result['source_identity']=check_source_pins(c)
        result['stage']=c['stage']
        quiet=os.environ.get('FACTORY_PREFILL_QUIET_ROOT')
        if quiet:
            from .store import Store
            from .strata_lab import wait_quiet
            with Store(Path(os.environ['FACTORY_HOME'])) as store:
                attempt=store.read(task_id,attempt_id)
                if (attempt['request'].get('quiet_required') is not True or
                    attempt['request'].get('quiet_root')!=quiet or attempt['request']['contract_sha256']!=contract_sha256):
                    raise ValueError('Persisted scoped quiet request differs')
            result['quiet']=wait_quiet(Path(os.environ['FACTORY_HOME']),attempt_id,quiet_root=quiet)
        for model in c['workload'].values():
            model=Path(model).resolve()
            if output.is_relative_to(model) or model.is_relative_to(output):
                raise ValueError('Scoped output overlaps model assets')
        result['assets_before']=tools.verify_inputs(c)
        atomic_json(output/'config.json',dict(task_id=task_id,attempt_id=attempt_id,contract=c))
        lease=Path(os.environ.get('FACTORY_LAB_LEASE',str(Path(os.environ['FACTORY_HOME']).parent/'lab-lease')))
        for i,arm in enumerate(c['order'],1):
            check_source_pins(c)
            if sha(contract_path)!=contract_sha256:raise ValueError('Scoped contract changed during run')
            before=tools.verify_inputs(c)
            remaining=c['campaign_timeout_s']-(time.monotonic()-started)
            if remaining<=0:raise TimeoutError('Scoped campaign deadline')
            cell=dict(index=i,arm=arm,status='running',phases={})
            result['cells'].append(cell)
            phase=dict(status='running',admission=admission(c['image']['id']))
            cell['phases']['prefill']=phase
            atomic_json(output/'progress.json',dict(cell=i,arm=arm,stage=c['stage'],status='running'))
            path=output/f'cell-{i:03d}-{arm}'/'prefill';path.parent.mkdir()
            report=lab_recorder.run_container(benchmark.phase_args(c,arm,'speed'),output=path,
                image=c['image']['id'],mounts=[(v,v) for v in c['workload'].values()],gpu=True,
                environment=c['arms'][arm]['environment'],protocol=benchmark.protocol(tools.cases(c),arm,c),
                timeout_s=min(300,remaining),interval_ms=1000,guard_gib=8,memory_bytes=104*2**30,cpus=8,lease_root=lease)
            phase['collector']=report
            if report.get('reason')=='cancelled':raise SystemExit(143)
            if not _successful(report):raise RuntimeError('Scoped recorder failed: '+str(report.get('reason')))
            parsed=tools.verify_cell(c,arm,path)
            if tools.verify_inputs(c)!=before:raise ValueError('Scoped model/tokenizer identity changed')
            phase.update(parsed,status='completed');cell['status']='completed'
            atomic_json(path.parent/'cell.json',cell)
        result['assets_after']=tools.verify_inputs(c)
        if result['assets_after']!=result['assets_before']:raise ValueError('Scoped asset identity changed')
        result.update(execution_outcome='ok',evidence_completeness='complete');rc=0
    except BaseException as exc:
        result['error']=dict(type=type(exc).__name__,message=str(exc))
        if isinstance(exc,(SystemExit,KeyboardInterrupt)):result['execution_outcome']='cancelled'
        for cell in result['cells']:
            if cell['status']=='running':cell['status']='partial'
    finally:
        for number in handlers:signal.signal(number,signal.SIG_IGN)
        try:
            _recover_partial(output,result)
            if result.get('recovery_errors'):
                result.update(execution_outcome='measurement_failed',evidence_completeness='partial');rc=1
            result['elapsed_s']=time.monotonic()-started
            atomic_json(output/'progress.json',dict(status='completed' if rc==0 else 'partial',
                completed_cells=sum(c['status']=='completed' for c in result['cells'])))
            _seal(output,result)
        finally:
            for number,handler in handlers.items():signal.signal(number,handler)
    return rc


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('contract','output','task','attempt','contract-sha256'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args()
    return run(args.contract,args.output,args.task,args.attempt,args.contract_sha256)


if __name__=='__main__':raise SystemExit(main())
