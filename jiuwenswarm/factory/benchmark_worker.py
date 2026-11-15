"""Bounded native Strata benchmark campaign worker.

This worker makes no experiment decisions and never edits its frozen contract.
It runs the admitted order, records partial failures, and leaves comparison and
quality scoring to the independent benchmark analyser after model execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from . import lab_recorder
from .lab_lifecycle import atomic_json, recover_run

_REQUIRED_SOURCES = {'benchmark_worker.py', 'benchmark.py', 'lab_recorder.py', 'lab_lifecycle.py'}


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _benchmark_tools():
    from . import benchmark
    return benchmark


def check_source_pins(contract, directory=None):
    directory = Path(directory or Path(__file__).parent).resolve()
    pins = contract.get('execution_sha256', {})
    if not isinstance(pins, dict) or not _REQUIRED_SOURCES.issubset(pins):
        raise ValueError('Worker, parser, recorder and lifecycle source identities are required')
    for name, expected in pins.items():
        if Path(name).name != name or not name.endswith('.py') or sha(directory/name) != expected:
            raise ValueError('Admitted benchmark execution source changed: ' + name)
    return dict(pins)


def admission(image):
    from .targets import validate_image
    info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], text=True, timeout=15))[0]
    if info['Id'] != image:
        raise ValueError('Local benchmark image identity changed')
    validate_image('spark-gb10', info, 'spark-gb10')
    gpu = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid,process_name',
                                   '--format=csv,noheader'], text=True, timeout=15).strip()
    available = lab_recorder.host_available()
    result = dict(gpu_processes=gpu, available_bytes=available, minimum_bytes=108*2**30)
    if gpu or available < result['minimum_bytes']:
        raise ValueError('Benchmark requires idle GPU and at least 108 GiB host available memory')
    return result


def _successful(report):
    return (report.get('reason') == 'completed' and report.get('container_exit_code') == 0
            and report.get('quiescent') is True and report.get('container_removed') is True
            and report.get('evidence_completeness') == 'complete'
            and report.get('container_oom_killed') is not True)


def _seal(output, result):
    atomic_json(output/'campaign.json', result)
    files = {}
    for path in sorted(output.rglob('*')):
        if (path.is_file() and path != output/'manifest.json' and not path.name.endswith('.lock')
                and not path.name.startswith('.')):
            files[str(path.relative_to(output))] = sha(path)
    atomic_json(output/'manifest.json', dict(schema_version=1, state=result['evidence_completeness'],
        task_id=result['task_id'], attempt_id=result['attempt_id'], files=files))


def _recover_partial(output, result):
    """Only exact intents written below this attempt are eligible for cleanup."""
    errors = []
    for path in sorted(output.glob('cell-*/*/intent.json')):
        phase = path.parent
        report_path = phase/'report.json'
        try:
            report = json.loads(report_path.read_text()) if report_path.exists() else {}
            if report.get('container_removed') is not True:
                recover_run(phase, reason='benchmark_worker_interrupted')
        except Exception as exc:
            errors.append(dict(phase=str(phase.relative_to(output)), error=type(exc).__name__+': '+str(exc)))
    if errors:
        result['recovery_errors'] = errors


def run(contract_path, output, task_id, attempt_id, *, contract_sha256, phase_names=('quality', 'speed')):
    contract_path, output = Path(contract_path).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Benchmark attempt output already exists; reconcile instead of replaying execution')
    if contract_path.is_relative_to(output):
        raise ValueError('Output may not contain its operator contract')
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    result = dict(schema_version=1, task_id=task_id, attempt_id=attempt_id,
        contract_sha256=contract_sha256, execution_outcome='measurement_failed', evidence_completeness='partial',
        stage='setup', cells=[], limitations=['Bounded native benchmark; independent analyser decides quality/speed.',
            'First-after-initialization is not cold SSD.', 'Host reboot and power-loss recovery are not qualified.'])
    old_handlers = {}
    for number in (signal.SIGTERM, signal.SIGINT):
        old_handlers[number] = signal.getsignal(number)
        signal.signal(number, lambda signum, frame: (_ for _ in ()).throw(SystemExit(128+signum)))
    rc = 1
    try:
        if sha(contract_path) != contract_sha256:
            raise ValueError('Frozen benchmark contract changed')
        contract = json.loads(contract_path.read_text())
        tools = _benchmark_tools()
        tools.validate_contract(contract)
        result['stage'] = contract.get('stage', 'main')
        result['source_identity'] = check_source_pins(contract)
        quiet_root = os.environ.get('FACTORY_BENCHMARK_QUIET_ROOT')
        if quiet_root:
            from .store import Store
            from .strata_lab import wait_quiet
            with Store(Path(os.environ['FACTORY_HOME'])) as store:
                attempt = store.read(task_id, attempt_id)
                if (attempt['request'].get('quiet_required') is not True
                        or attempt['request'].get('quiet_root') != quiet_root
                        or attempt['request'].get('contract_sha256') != contract_sha256):
                    raise ValueError('Persisted benchmark quiet request differs')
            result['quiet'] = wait_quiet(Path(os.environ['FACTORY_HOME']), attempt_id, quiet_root=quiet_root)
        dataset_path = Path(contract['dataset_path']).resolve()
        if dataset_path.is_relative_to(output) or sha(dataset_path) != contract['dataset_sha256']:
            raise ValueError('Pinned benchmark dataset changed or overlaps output')
        dataset = json.loads(dataset_path.read_text())
        phase_cases = dict(quality=dataset['pilot'] if result['stage'] == 'pilot' else dataset['quality'],
                           speed=dataset['speed'][:2] if result['stage'] == 'pilot' else dataset['speed'])
        if contract.get('adapter') in ('strata-benchmark-v3','strata-benchmark-v4','strata-benchmark-v5'):
            phase_cases = {phase: tools.phase_cases(contract, dataset, phase) for phase in ('quality', 'speed')}
        if tuple(phase_names) not in (('quality', 'speed'), ('quality',), ('speed',)):
            raise ValueError('Unsupported phase selection')
        # Non-default phase selection is for an explicitly frozen contract, not an agent override.
        if tuple(phase_names) != tuple(contract.get('phases', ('quality', 'speed'))):
            raise ValueError('Executed phases differ from frozen contract')
        work = contract['workload']
        for value in (work['pack'], work['model_root']):
            model = Path(value).resolve()
            if output.is_relative_to(model) or model.is_relative_to(output):
                raise ValueError('Benchmark output overlaps read-only model assets')
        limits = contract['limits']
        lease_root = (Path(os.environ['FACTORY_LAB_LEASE']) if os.environ.get('FACTORY_LAB_LEASE')
                      else Path(os.environ['FACTORY_HOME']).parent/'lab-lease')
        total_timeout = contract.get('campaign_timeout_s', 5400)
        if not isinstance(total_timeout, (int, float)) or not 1 <= total_timeout <= 10800:
            raise ValueError('Campaign timeout outside bounds')
        result['assets_before'] = tools.validate_assets(contract)
        atomic_json(output/'config.json', dict(task_id=task_id, attempt_id=attempt_id, contract=contract))
        for index, arm in enumerate(contract['order'], 1):
            cell = dict(index=index, arm=arm, status='running', phases={})
            result['cells'].append(cell)
            profile = contract['arms'][arm]
            for phase in phase_names:
                if time.monotonic()-started >= total_timeout:
                    raise TimeoutError('Benchmark campaign deadline')
                check_source_pins(contract)
                if sha(contract_path) != contract_sha256 or sha(dataset_path) != contract['dataset_sha256']:
                    raise ValueError('Frozen inputs changed during campaign')
                assets_before = tools.validate_assets(contract)
                phase_output = output/f'cell-{index:03d}-{arm}'/phase
                phase_output.parent.mkdir(parents=True, exist_ok=True)
                phase_record = dict(status='running', case_ids=[c['id'] for c in phase_cases[phase]],
                                    eos=1 if phase == 'quality' else -1, assets_before=assets_before)
                cell['phases'][phase] = phase_record
                atomic_json(output/'progress.json', dict(task_id=task_id, attempt_id=attempt_id,
                    completed_cells=index-1, cell=index, arm=arm, phase=phase, status='running'))
                phase_record['admission'] = admission(contract['image']['id'])
                wire = (tools.protocol(phase_cases[phase], arm, contract) if contract.get('adapter') in ('strata-benchmark-v2', 'strata-benchmark-v3', 'strata-benchmark-v4', 'strata-benchmark-v5')
                        else tools.protocol(phase_cases[phase], arm))
                report = lab_recorder.run_container(tools.phase_args(contract, arm, phase), output=phase_output,
                    image=contract['image']['id'], mounts=[(work['pack'],work['pack']), (work['model_root'],work['model_root'])],
                    gpu=True, environment=profile['environment'], protocol=wire,
                    timeout_s=min(limits[phase+'_timeout_s'], max(0.001, total_timeout-(time.monotonic()-started))), interval_ms=1000, guard_gib=limits['guard_gib'],
                    memory_bytes=limits['memory_bytes'], cpus=limits['cpus'],
                    lease_root=lease_root)
                phase_record['collector'] = report
                if report.get('reason') == 'cancelled':
                    raise SystemExit(143)
                if not _successful(report):
                    raise RuntimeError(f'{phase} recorder failed: ' + str(report.get('reason')))
                parsed = tools.parse_native((phase_output/'stdout.log').read_text(),
                                            (phase_output/'stderr.log').read_text(), phase_cases[phase])
                if contract.get('adapter') in ('strata-benchmark-v2', 'strata-benchmark-v3', 'strata-benchmark-v4', 'strata-benchmark-v5'):
                    tools.verify_prefill_engagement(contract, arm, parsed, (phase_output/'stderr.log').read_text())
                if len(parsed.get('requests', [])) != len(phase_cases[phase]):
                    raise ValueError('Parsed request count differs from frozen dataset')
                if phase == 'speed' and any(1 in row['ids'] for row in parsed['requests']):
                    raise ValueError('EOS emitted in fixed-token speed test')
                if phase == 'speed' and any(row['generated_tokens'] != 128 for row in parsed['requests']):
                    raise ValueError('Fixed-token speed test did not generate exactly 128 tokens')
                phase_record.update(parsed)
                phase_record['assets_after'] = tools.validate_assets(contract)
                if phase_record['assets_before'] != phase_record['assets_after']:
                    raise ValueError('Model asset identity changed')
                phase_record['status'] = 'completed'
                atomic_json(phase_output.parent/(phase+'-result.json'), phase_record)
            cell['status'] = 'completed'
            atomic_json(output/f'cell-{index:03d}-{arm}'/'cell.json', cell)
            atomic_json(output/'progress.json', dict(task_id=task_id, attempt_id=attempt_id,
                completed_cells=index, total_cells=len(contract['order']), status='running'))
        result['assets_after'] = tools.validate_assets(contract)
        if result['assets_after'] != result['assets_before']:
            raise ValueError('Campaign asset identity changed')
        result.update(execution_outcome='ok', evidence_completeness='complete')
        rc = 0
    except BaseException as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            result['execution_outcome'] = 'cancelled'
            rc = exc.code if isinstance(exc, SystemExit) and isinstance(exc.code, int) else 130
        for cell in result['cells']:
            if cell['status'] == 'running': cell['status'] = 'partial'
    finally:
        for number in old_handlers:
            signal.signal(number, signal.SIG_IGN)
        try:
            _recover_partial(output, result)
            if result.get('recovery_errors'):
                result.update(execution_outcome='measurement_failed', evidence_completeness='partial')
                rc = 1
            atomic_json(output/'progress.json', dict(task_id=task_id, attempt_id=attempt_id,
                completed_cells=sum(cell['status'] == 'completed' for cell in result['cells']),
                status='completed' if rc == 0 else 'partial'))
            result['elapsed_s'] = time.monotonic()-started
            _seal(output, result)
        finally:
            for number, handler in old_handlers.items(): signal.signal(number, handler)
    return rc


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for field in ('contract', 'output', 'task', 'attempt', 'contract-sha256'):
        p.add_argument('--'+field, required=True)
    args = p.parse_args()
    return run(args.contract, args.output, args.task, args.attempt, contract_sha256=args.contract_sha256)


if __name__ == '__main__':
    raise SystemExit(main())
