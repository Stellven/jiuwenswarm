#!/usr/bin/env python3
"""Freeze and launch one real JiuwenSwarm CPU-only branch investigation.

Run freeze after manual evidence and new CC packages are ready; inspect its
manifest/task, then run. No model, CC, benchmark or GPU work occurs at import.
The existing subscription profile is linked privately and never exported.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import stat
import sys
import time

LAUNCHER = Path(__file__).resolve()
SOURCE = LAUNCHER.parents[1]
DEFAULT_ROOT = LAUNCHER.parent if (LAUNCHER.parent / 'manifest.json').is_file() else SOURCE.parents[1] / 'night-branch-jiuwen-v1'
DEFAULT_ENGINE = SOURCE.parents[1] / 'night-branch-engine-v2/run-001/analysis.json'
PACKAGES = ('branch_workbench', 'evidence', 'memory_residency_lab', 'inference_lab',
            'methodology_followup', 'strata_prefill_chunk', 'strata_budget_workbench',
            'cc_workflow_lab', 'methodology_transfer_lab')
CPU_CAPABILITIES = {
    'branch_workbench': {'create','fork','refine','attach','record','prune','status','ready','compare'},
    'evidence': {'query','read','publish','plan_get','plan_patch'},
    'memory_residency_lab': {'plan','verify'},
    'inference_lab': {'test_scope','diagnose','propose','cache_protocol','ablation','followup','profile_plan','analyze_profile','evaluate_prediction'},
    'methodology_followup': {'followup'},
    'strata_prefill_chunk': {'apply','coverage'},
    'strata_budget_workbench': {'apply','verify_startup','summarize_memory'},
    'cc_workflow_lab': {'analyze_receipts','design_workflow','run_batch'},
    'methodology_transfer_lab': {'assess_transfer','design_trial','analyze_abba'},
}
TASK_ID = 'night-branch-jiuwen-v1'
LATEST_STOP_UTC = '2026-11-15T08:00:00+00:00'
LATEST_STOP = datetime.fromisoformat(LATEST_STOP_UTC).timestamp()
MIN_START_SECONDS = 600
CLEANUP_SECONDS = 30


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    temporary.replace(path)


def tree(root):
    return {p.relative_to(root).as_posix(): digest(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc'}


def read_regular(path, max_bytes=2 * 1024**2):
    path = Path(path).expanduser()
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > max_bytes:
            raise ValueError('Evidence must be a regular file at most 2 MiB: ' + str(path))
        data = stream.read(max_bytes + 1)
        after = os.fstat(stream.fileno())
        if len(data) > max_bytes or len(data) != before.st_size or before.st_mtime_ns != after.st_mtime_ns or before.st_size != after.st_size:
            raise ValueError('Evidence changed while reading: ' + str(path))
    return data


def freeze(args):
    root = args.root.resolve()
    if root.exists():
        raise ValueError('Mission root already exists; preserve it and select a fresh --root')
    if len(args.extra_evidence) > 8:
        raise ValueError('At most eight extra evidence files are admitted')
    primary_data = read_regular(args.engine_evidence)
    evidence = args.engine_evidence.resolve(strict=True)
    extras = [(Path(path).resolve(strict=True), read_regular(path)) for path in args.extra_evidence]
    packages = list(dict.fromkeys([*PACKAGES, *args.package]))
    for name in packages:
        if name not in PACKAGES:
            raise ValueError('Mission accepts bounded CPU packages only: ' + name)
        if not (SOURCE / 'jiuwenswarm/factory/ccs' / name / 'cc.yaml').is_file():
            raise ValueError('Package unavailable: ' + name)
    runtime = root / 'runtime'
    # Source snapshot keeps the existing JiuwenSwarm facade and subscription
    # integration. Only the explicit CPU CC subset is discoverable by its MCP.
    shutil.copytree(SOURCE / 'jiuwenswarm', runtime / 'jiuwenswarm',
        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'node_modules', 'frontend', 'dist', 'ccs'))
    ccs = runtime / 'jiuwenswarm/factory/ccs'
    declarations = {}
    import yaml
    for name in packages:
        shutil.copytree(SOURCE / 'jiuwenswarm/factory/ccs' / name, ccs / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'build', '*.o'))
        declaration = ccs / name / 'cc.yaml'
        original_sha = digest(declaration)
        data = yaml.safe_load(declaration.read_text())
        data['capabilities'] = {key:value for key,value in data['capabilities'].items() if key in CPU_CAPABILITIES[name]}
        if not data['capabilities'] or any(set(cap.get('changes', [])) - {'process.exec'} for cap in data['capabilities'].values()):
            raise ValueError('Unexpected effects in selected CPU package: ' + name)
        # Restriction changes the sealed release hash and is recorded explicitly.
        # Source package files remain untouched; no new capability is introduced.
        declaration.write_text(yaml.safe_dump(data, sort_keys=False))
        declarations[name] = dict(source_manifest_sha256=original_sha,
            frozen_manifest_sha256=digest(declaration), allowed_capabilities=sorted(data['capabilities']))
    shutil.copy2(Path(__file__), root / 'launch.py')
    workspace = root / 'factory/agent-workspace'
    inputs = workspace / 'inputs'
    inputs.mkdir(parents=True)
    (inputs / 'engine-analysis.json').write_bytes(primary_data)
    copied = {'engine-analysis.json': digest(inputs / 'engine-analysis.json')}
    extra_sources = []
    for index, (path, data) in enumerate(extras, 1):
        name = 'extra-' + str(index) + '-' + path.name
        target = inputs / name
        target.write_bytes(data)
        copied[name] = digest(target)
        extra_sources.append(dict(source=str(path), workspace_path='inputs/' + name, sha256=copied[name], bytes=len(data)))
    total = 0
    for raw in sorted(evidence.parent.rglob('*')):
        if not raw.is_file() or raw.is_symlink() or raw.suffix not in {'.json', '.txt', '.log', '.stdout', '.stderr', '.out', '.err'}:
            continue
        size = raw.stat().st_size
        if size > 2 * 1024**2 or total + size > 32 * 1024**2:
            continue
        target = inputs / 'engine-raw' / raw.relative_to(evidence.parent)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(raw, target)
        copied[target.relative_to(inputs).as_posix()] = digest(target)
        total += size
    for name in packages:
        package = ccs / name
        for filename in ('ROUND1.json', 'EXAMPLES.json', 'EXAMPLE.json'):
            path = package / filename
            if path.is_file():
                target = inputs / (name + '-' + filename)
                shutil.copy2(path, target)
                copied[target.name] = digest(target)
    objective = '''Explore at least two genuinely different solution branches and one evidence-driven continuation using the new branch workbench. You are the decision maker. Read the fixed task and input evidence before selecting hypotheses; no host plan prescribes their content. The operator's manual engine evidence is in inputs/engine-analysis.json and native capsule manual rounds/examples are in inputs/. Read every inputs/extra-* evidence file: these are separately pinned later long-prefill or factory-overhead measurements; preserve their distinct workloads, scopes and dates, and do not rewrite or pool the original manual round. First cc_list, read the branch workbench skill/method plus relevant capsule materials, query evidence, and publish a justified decision. Read branch status for graph_rev (the host seeds an unrelated suggestion graph; branch rev is not assumed zero). Create/fork at least two alternatives, each within its explicit reservation. A branch may use multiple admitted CCs. Actually call new CPU capsules, including engine.memory_residency_lab plan/verify (do not call native_experiment or build a binary), engine.strata_budget_workbench to inspect native startup and measured memory, factory.cc_workflow_lab to analyze pinned real or explicitly historical fixture costs (no new benchmark_fixture or performance measurements), and factory.methodology_transfer_lab to assess transfer or design the next bounded experiment. Use at least three of those new capsules when the evidence supports it; other listed pure CPU methods are available. The copied engine-raw directory provides native startup, resource and raw cell records when present. You may use engine.strata_prefill_chunk.coverage to check whether proposed quality prompts exercise different chunk counts; a matched short-output sample that stays inside one chunk is insufficient treatment coverage. Save real receipt outputs as observations with evidence.publish, then attach those qualitative findings to the corresponding branches. Explain which evidence changed your hypothesis, refine a completed parent into a continuation, call another useful capsule and attach the new evidence. Prune at least one unsupported alternative with an evidence-based reason. Run compare and retain unknown speed/memory/quality values; advice, synthetic examples, and configuration checks do not establish accepted engine gains. Do not infer engine speed from component ratios or make up timing, quality, costs, or measurements. Use record only for actual current-task branch_measurement evidence with explicit scope/key/metrics/cost; attach is appropriate otherwise. Read ready/status between revisions. Publish decisions with observations, hypothesis, uncertainty, next bounded action, expected evidence, budget and stop condition; cite actual evidence IDs. End with a report_inconclusive decision explaining branch outcomes, actual measurements, missing prerequisites, Pareto unknowns and the next useful bounded experiment. No GPU tools, inference launch, jobs, Docker, compilation, native_experiment, source changes, changed contracts, network commands, commits, promotion or arbitrary execution. Shell/file operations only read input files or write local report artifacts inside this workspace. Do not edit runtime, launcher, task, factory database, MCP configuration, credentials or manifests.'''
    task = dict(task_id=TASK_ID, objective=objective,
        constraints={'methodology_driven': True, 'branch_workbench': {'max_branches': 8, 'cpu_seconds': 60, 'gpu_seconds': 0},
                     'mission': {'cpu_only': True, 'no_jobs': True, 'no_source_edits': True, 'no_promotion': True,
                                 'selected_packages': packages, 'input_sha256': copied, 'latest_stop_utc': LATEST_STOP_UTC,
                                 'minimum_start_seconds': MIN_START_SECONDS}},
        allowed_effects=['process.exec'], target='spark-gb10', budget={'max_turns': 6, 'wall_clock_s': 1500},
        contract_id='branch-methodology-cpu-v1', initial_run_config={}, component_cc='factory.branch_workbench',
        source={'subpath': 'inputs', 'pre_integration_commit': 'read-only-evidence'},
        operator_labels={'purpose': 'real JiuwenSwarm branch exploration; separate from engine benchmarking',
                         'model': 'gpt-6.1-sol', 'promotion': False})
    dump(root / 'task.json', task)
    dump(root / 'manifest.json', dict(schema='factory.branch-mission/1', task_id=TASK_ID,
        runtime_files=tree(runtime), task_sha256=digest(root / 'task.json'), input_sha256=copied,
        launcher_sha256=digest(root / 'launch.py'), source_launcher_sha256=digest(Path(__file__)),
        engine_evidence_source=str(evidence), engine_evidence_sha256=hashlib.sha256(primary_data).hexdigest(), extra_evidence=extra_sources, packages=packages, package_capability_restrictions=declarations,
        requested_model='gpt-6.1-sol', requested_effort='max', execution_scope='CPU only', promotion=False))
    return dict(root=str(root), frozen=True, task=str(root / 'task.json'), manifest=str(root / 'manifest.json'),
                next_command=f'{sys.executable} {root}/launch.py --root {root} run')


def verify(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    if digest(root / 'task.json') != manifest['task_sha256']:
        raise ValueError('Frozen task changed')
    if digest(root / 'launch.py') != manifest['launcher_sha256']:
        raise ValueError('Frozen launcher changed')
    if tree(root / 'runtime') != manifest['runtime_files']:
        raise ValueError('Frozen runtime changed')
    for name, expected in manifest['input_sha256'].items():
        if digest(root / 'factory/agent-workspace/inputs' / name) != expected:
            raise ValueError('Frozen evidence input changed: ' + name)
    return manifest


def setup(root):
    runtime = root / 'runtime'
    sys.path.insert(0, str(runtime))
    # Private dependency environment remains external to the frozen source tree.
    pythonpath = os.pathsep.join([str(runtime), *filter(None, os.environ.get('PYTHONPATH', '').split(os.pathsep))])
    os.environ.update(FACTORY_HOME=str(root / 'factory'), FACTORY_TASK_ID=TASK_ID,
        FACTORY_TARGET_PROFILE='spark-gb10', PYTHONPATH=pythonpath, PYTHONDONTWRITEBYTECODE='1',
        JIUWENSWARM_CODEX_MODEL='gpt-6.1-sol', FACTORY_CODEX_MODEL='gpt-6.1-sol',
        JIUWENSWARM_CODEX_AGENT_EFFORT='max', JIUWENSWARM_SKIP_DOTENV='1')
    # This launcher uses the ordinary local subprocess transport, not a prior
    # campaign's remote executor, HTTP MCP or execution receipt.
    for key in ('CODEX_EXEC_SERVER_URL', 'JIUWENSWARM_CODEX_EXEC_RECEIPT',
                'JIUWENSWARM_FACTORY_MCP_HTTP_RECEIPT', 'FACTORY_BRIDGE_DIR', 'FACTORY_HOST_PYTHON'):
        os.environ.pop(key, None)


def read_receipts(root):
    """Retain crash-damaged rows as typed, hashed records; never trust shape."""
    import sqlite3
    receipts, incomplete, counts, manifest_errors = [], [], {}, []
    database = root / 'factory/ccstore/calls.sqlite'
    if not database.is_file():
        return dict(receipts=[], incomplete=[], counts={}, manifest_errors=[])
    with sqlite3.connect('file:' + str(database) + '?mode=ro', uri=True) as db:
        rows = db.execute('SELECT rowid,receipt FROM calls ORDER BY rowid').fetchall()
    for index, raw in rows:
        payload = raw if isinstance(raw, bytes) else raw.encode('utf-8') if isinstance(raw, str) else b'<sqlite-null>' if raw is None else repr(raw).encode()
        failure = dict(rowid=index, sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
        try:
            receipt = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))
        except (TypeError, ValueError, UnicodeDecodeError) as exc:
            incomplete.append(dict(failure, reason='invalid_json', error_type=type(exc).__name__))
            continue
        if not isinstance(receipt, dict):
            incomplete.append(dict(failure, reason='nonobject_receipt', value_type=type(receipt).__name__))
            continue
        receipts.append(receipt)
        required = {'state','release','capability'}
        missing = sorted(required - receipt.keys())
        release, capability, state = (receipt.get(key) for key in ('release','capability','state'))
        valid_release = isinstance(release, str) and re.fullmatch('[0-9a-f]{64}', release)
        valid_capability = isinstance(capability, str) and bool(capability)
        if missing or not valid_release or not valid_capability or not isinstance(state, str) or state not in {'succeeded','failed','blocked'}:
            incomplete.append(dict(failure, reason='incomplete_receipt', missing_fields=missing,
                state=state if isinstance(state, str) else None,
                valid_release=bool(valid_release), valid_capability=valid_capability))
        name = release if valid_release else '<invalid-release>'
        if valid_release:
            declaration_file = root / 'factory/ccstore/releases' / release / 'manifest.json'
            try:
                data = json.loads(declaration_file.read_bytes())
                declaration = data.get('declaration') if isinstance(data, dict) else None
                if not isinstance(declaration, dict) or not isinstance(declaration.get('id'), str):
                    raise ValueError('Invalid declaration shape')
                name = declaration['id']
            except (OSError, TypeError, ValueError, UnicodeDecodeError) as exc:
                manifest_errors.append(dict(release=release, error_type=type(exc).__name__, receipt_rowid=index))
        label = name + '.' + (capability if valid_capability else '<invalid-capability>')
        count = counts.setdefault(label, {'succeeded':0,'other':0})
        count['succeeded' if state == 'succeeded' and valid_release and valid_capability else 'other'] += 1
    return dict(receipts=receipts, incomplete=incomplete, counts=counts, manifest_errors=manifest_errors)


def export_run(root, store, report):
    """Write a minimal result first; each optional export has its own failure boundary."""
    report = dict(report, export_errors=[])
    attempt = root / 'controller-attempts' / (str(time.time_ns()) + '.json')
    report['retained_attempt'] = str(attempt)
    def persist():
        try:
            dump(root / 'controller-result.json', report)
            dump(attempt, report)
        except Exception as exc:
            report['export_errors'].append(dict(stage='result_persistence', error_type=type(exc).__name__))
            try:
                dump(root / 'controller-result-minimal.json', report)
            except Exception as fallback:
                print(json.dumps(dict(event='mission_result_persistence_failed',primary_error=report.get('error'),
                    error_type=type(exc).__name__,fallback_type=type(fallback).__name__)), file=sys.stderr)
    persist()
    def capture(name, function):
        try:
            value = function()
            dump(root / (name + '.json'), value)
            return value
        except Exception as exc:
            report['export_errors'].append(dict(stage=name, error_type=type(exc).__name__))
            return None
    snapshot = capture('evidence-snapshot', lambda: store.dump(TASK_ID))
    receipts = capture('native-receipts', lambda: read_receipts(root))
    if receipts is not None:
        report.update(native_receipt_counts=receipts['counts'], incomplete_receipts=receipts['incomplete'],
            incomplete_receipt_count=len(receipts['incomplete']), receipt_manifest_errors=receipts['manifest_errors'])
    from jiuwenswarm.factory.branch_workbench import status, compare
    branch_status = capture('branches', lambda: status(store, TASK_ID))
    capture('pareto', lambda: compare(store, TASK_ID))
    if snapshot is not None and branch_status is not None:
        try:
            operations = [row.get('values', {}).get('operation') for row in snapshot['observations']
                if row['kind'] == 'branch_workbench_operation']
            report['exploration_obligations'] = dict(two_or_more_branches=len(branch_status['branches']) >= 2,
                explicit_fork='fork' in operations, continuation='refine' in operations, retained_pruning='prune' in operations,
                evidence_attachment=any(op in operations for op in ('attach','record')),
                comparison_called=bool(receipts and receipts['counts'].get('factory.branch_workbench.compare', {}).get('succeeded')))
        except Exception as exc:
            report['export_errors'].append(dict(stage='exploration_obligations',error_type=type(exc).__name__))
    persist()
    return report


async def run(root, auth_source):
    if time.time() + MIN_START_SECONDS + CLEANUP_SECONDS >= LATEST_STOP:
        raise ValueError('Insufficient time before the operator latest stop: ' + LATEST_STOP_UTC)
    manifest = verify(root)
    manifest_hash = digest(root / 'manifest.json')
    setup(root)
    from jiuwenswarm.factory.controller import Controller, configure_agent
    from jiuwenswarm.factory.store import NotFound
    from jiuwenswarm.server.runtime.codex_subscription.service import get_service
    from jiuwenswarm.server.runtime.codex_subscription.transport import CodexError
    task = json.loads((root / 'task.json').read_text())
    controller = Controller(home=root / 'factory', grants=task['allowed_effects'])
    try:
        try:
            controller.store.get_task(TASK_ID)
        except NotFound:
            controller.init_task(root / 'task.json')
        # Import verified manual evidence as an observation and as a content
        # addressed artifact. This is operator evidence, never a new benchmark.
        if not controller.store.query(TASK_ID, kinds=['operator_manual_evidence'], limit=1)['items']:
            payload = (root / 'factory/agent-workspace/inputs/engine-analysis.json').read_bytes()
            artifact = controller.store.put_artifact(TASK_ID, 'manual-engine-analysis', payload, 'application/json', None)
            controller.store.append_observation(TASK_ID, dict(obs_id='manual-engine-evidence', kind='operator_manual_evidence',
                source_artifacts=[artifact['artifact_id']], values={'analysis': json.loads(payload),
                    'source_sha256': manifest['engine_evidence_sha256'], 'scope':'operator manual engine evidence, not an autonomous run'},
                limitations='Read the exact original measurement scope and gates; no promotion authority.'))
        for index, extra in enumerate(manifest.get('extra_evidence', []), 1):
            observation_id = 'operator-extra-' + str(index)
            try:
                controller.store.read(TASK_ID, observation_id)
                continue
            except NotFound:
                pass
            extra_path = root / 'factory/agent-workspace' / extra['workspace_path']
            payload = read_regular(extra_path)
            try:
                value = json.loads(payload)
                media_type = 'application/json'
            except (ValueError, UnicodeDecodeError):
                value = {'text': payload.decode('utf-8', errors='replace')}
                media_type = 'text/plain'
            artifact = controller.store.put_artifact(TASK_ID, observation_id + '-artifact', payload, media_type, None)
            controller.store.append_observation(TASK_ID, dict(obs_id=observation_id, kind='operator_extra_evidence',
                source_artifacts=[artifact['artifact_id']], values={'evidence':value, 'sha256':extra['sha256'],
                    'workspace_path':extra['workspace_path'], 'scope':'separate pinned operator evidence; inspect original scope'},
                limitations='Do not pool different workloads, measurement scopes or fixture types.'))
        configure_agent(task, task['allowed_effects'], root / 'factory')
        service = get_service()
        auth_source = auth_source.resolve(strict=True)
        auth = service.root / 'codex-home/auth.json'
        auth.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if auth.exists() or auth.is_symlink():
            raise ValueError('Unexpected mission auth file; refuse overwrite')
        auth.symlink_to(auth_source)
        identities, usage, reroutes = [], {}, []
        owner = asyncio.current_task()
        def observe(method, params):
            if method == 'thread/tokenUsage/updated':
                usage[params.get('threadId', 'unknown')] = params.get('tokenUsage')
            elif method == 'model/rerouted':
                reroutes.append({k:params.get(k) for k in ('fromModel','toModel','reason')})
                if params.get('toModel') != 'gpt-6.1-sol':
                    owner.cancel('Unexpected model reroute')
        service.transport.listeners.add(observe)
        original_request = service.transport.request
        async def observed_request(method, params=None, **kwargs):
            result = await original_request(method, params, **kwargs)
            if method in {'thread/start','thread/resume'}:
                identities.append({k:result.get(k) for k in ('model','modelProvider','reasoningEffort')})
                if method == 'thread/start' and result.get('model') != 'gpt-6.1-sol':
                    raise CodexError('MISSION_MODEL_MISMATCH')
            return result
        service.transport.request = observed_request
        started, result, error = time.time(), None, None
        try:
            result = await asyncio.wait_for(controller.run(TASK_ID), timeout=min(1560, max(1, LATEST_STOP - time.time() - CLEANUP_SECONDS)))
            return result
        except BaseException as exc:
            error = {'type':type(exc).__name__, 'code':str(exc)[:120] if isinstance(exc,CodexError) else type(exc).__name__}
            raise
        finally:
            primary_error = error
            cleanup_error = None
            try:
                await asyncio.wait_for(service.transport.close(), timeout=20)
            except BaseException as exc:
                cleanup_error = type(exc).__name__
                if error is None:
                    error = {'type':'CleanupFailed', 'code':cleanup_error}
            finally:
                try:
                    if auth.is_symlink():
                        auth.unlink()
                except OSError as exc:
                    cleanup_error = cleanup_error or type(exc).__name__
            report = dict(schema='factory.branch-live-mission/1', task_id=TASK_ID,
                started_at=started, finished_at=time.time(), result=result, error=error, provider_identities=identities,
                provider_reroutes=reroutes, usage_by_thread=usage, cost_usd=None,
                requested_model='gpt-6.1-sol', requested_effort='max', latest_stop_utc=LATEST_STOP_UTC,
                manifest_sha256=manifest_hash, auth_symlink_removed=not auth.exists(),
                cleanup_error=cleanup_error, promotion=False)
            try:
                exported = export_run(root, controller.store, report)
            except Exception as exc:
                # Even an unexpected exporter bug must not mask the model/tool
                # failure. Retain the minimal primary report independently.
                report['export_errors'] = [dict(stage='export_run', error_type=type(exc).__name__)]
                try:
                    dump(root / 'controller-result.json', report)
                except Exception:
                    print(json.dumps(dict(event='mission_minimal_result_failed',primary_error=error,
                        export_error=type(exc).__name__)), file=sys.stderr)
                exported = report
            if primary_error is None and (cleanup_error or exported.get('export_errors')):
                raise RuntimeError('Mission cleanup/export incomplete; inspect retained controller-result.json')
    finally:
        controller.store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--engine-evidence', type=Path, default=DEFAULT_ENGINE)
    parser.add_argument('--auth', type=Path, default=Path('/home/user2/.codex/auth.json'))
    parser.add_argument('--package', action='append', default=[])
    parser.add_argument('--extra-evidence', type=Path, action='append', default=[])
    parser.add_argument('operation', choices=['freeze', 'verify', 'run', 'status'])
    args = parser.parse_args()
    root = args.root.resolve()
    if args.operation == 'freeze':
        result = freeze(args)
    elif args.operation == 'verify':
        result = dict(verified=True, manifest_sha256=digest(root / 'manifest.json'), packages=verify(root)['packages'])
    elif args.operation == 'run':
        result = asyncio.run(run(root, args.auth))
    else:
        setup(root)
        from jiuwenswarm.factory.controller import Controller
        controller = Controller(home=root / 'factory')
        try:
            result = controller.status(TASK_ID)
        finally:
            controller.store.close()
    print(json.dumps(result, indent=2, default=str))


if __name__ == '__main__':
    main()
