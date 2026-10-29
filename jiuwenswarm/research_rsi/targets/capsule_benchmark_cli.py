"""Model-free catalog benchmark command.

python -m jiuwenswarm.research_rsi.targets.capsule_benchmark_cli list
python -m jiuwenswarm.research_rsi.targets.capsule_benchmark_cli run --all --output /tmp/capsule-baselines

Runs the existing grant-bounded LocalDispatcher and paired batched protocol.
All measurements are explicitly unprotected; unsupported entries stay visible.
"""
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import os
from pathlib import Path
import shutil
import sys
import sysconfig
import time
import uuid

from ..records import RecordStore, encoded
from . import capsule_executor as executor
from .capsule_benchmark import benchmark_config, benchmark_job_count, benchmark_protocol, timing_batches
from .capsule_runtime import capture_runtime_manifest, verify_runtime
from .capsules import benchmark_spec, capsule_catalog, registered_capsule

SCHEMA = 'ai4r-rsi-capsule-catalog-benchmark:1'


def benchmark_inventory():
    """Every selected registry entry, including honest unsupported statuses."""
    rows = []
    for target in capsule_catalog():
        name = target['capsule_name']
        row = {'capsule_name': name, 'status': 'ready', 'reason': None,
               'release_module': target.get('release_module'), 'version_label': target.get('version_label')}
        try:
            if not target['public_evaluation_available']:
                row.update(status='skipped', reason=target.get('adapter_blocker') or 'No correctness adapter')
            elif benchmark_spec(name) is None:
                row.update(status='skipped', reason='No representative benchmark fixture specification')
            else:
                protocol = benchmark_protocol(name)
                row.update(workload_count=len(timing_batches(name)), protocol_sha256=executor.digest(encoded(protocol)))
        except Exception as error:
            row.update(status='error', reason=f'{type(error).__name__}: {error}')
        rows.append(row)
    return rows


def stage_local_runtime(destination, names):
    """Capture code/data and loaded installed dependencies, never an /opt runtime.

    Source staging is restricted to research packages and contract schemas.
    Installed dependency packages are copied as packages (native extensions and
    data included); fixtures, credentials, bytecode and test trees are excluded.
    The normal manifest/closure verifier remains the authority on completeness.
    """
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    for name in names:
        target = registered_capsule(name)
        for module in (getattr(target, 'selected_worker_module', None), getattr(target, 'checks_module', None)):
            if module:
                importlib.import_module(module)
        from .capsules import _carrier
        _carrier(name)
    source_root = Path(__file__).resolve().parents[2]
    package = destination / 'source/jiuwenswarm'
    package.mkdir(parents=True)
    shutil.copyfile(source_root / '__init__.py', package / '__init__.py')
    excluded = {'fixtures', '__pycache__', 'tests', '.git', 'credentials', 'accounts', 'auth'}
    for stem in ('research', 'research_records', 'research_contracts'):
        for source in (source_root / stem).rglob('*'):
            relative = source.relative_to(source_root)
            if source.is_file() and source.suffix in {'.py', '.json'} and not excluded.intersection(relative.parts):
                target = package / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
    dependencies = destination / 'dependencies'
    dependencies.mkdir()
    site_roots = {Path(sysconfig.get_path(key)).resolve() for key in ('purelib', 'platlib')}
    roots = set()
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        source = Path(filename).resolve()
        for site_root in site_roots:
            if source.is_relative_to(site_root):
                roots.add(site_root / source.relative_to(site_root).parts[0])
    for source in sorted(roots):
        target = dependencies / source.name
        if target.exists():
            continue
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns(*excluded, '*.pyc', '*.pyo'))
        else:
            shutil.copyfile(source, target)
    manifest = capture_runtime_manifest(destination, build_id='local-model-free-catalog-benchmark',
        dependency_environment={'distributions': [{'name': path.name, 'source': str(path)} for path in sorted(roots)]})
    return destination, json.loads(encoded(manifest))


def local_grant(name, manifest, config):
    fixtures = executor.evaluation_fixtures(name)
    target = registered_capsule(name)
    parent_path = 'source/jiuwenswarm/' + target.carrier_path
    parent_sha = next(row['sha256'] for row in manifest['files'] if row['path'] == parent_path)
    jobs = benchmark_job_count(name, config)
    return {'schema': executor.LOOP_GRANT_SCHEMA, 'bootstrap_schema': executor.BOOTSTRAP_SCHEMA,
        'run_id': 'local-benchmark-' + uuid.uuid4().hex, 'capsule_name': name,
        'runtime_manifest_sha256': executor.digest(encoded(manifest)), 'parent_sha256': parent_sha,
        'fixture_sha256': executor.digest(encoded(fixtures)), 'fixture_count': len(fixtures),
        'roles': ['parent', 'candidate'], 'max_executions': max(2 * len(fixtures), len(fixtures) + jobs),
        'iterations': 1, 'limits': {'timeout_s': 60, 'memory_mb': 1024, 'pids_max': 32, 'wall_s': 3600},
        'worker': {key: {'id': 'local:model-free-benchmark', 'sha256': '0' * 64}
                   for key in ('contract_ref', 'environment_ref', 'hardware_ref')},
        'expires_unix_s': int(time.time()) + 3600, 'scope': 'public_m1_development_only',
        'production_admission': 'UNKNOWN'}


async def run_baseline(name, *, runtime_root, manifest, output_root, overrides=None):
    """Real parent correctness evaluation, then A/A through the real benchmark."""
    from .capsule_local_dispatcher import LocalDispatcher
    config = benchmark_config(name, overrides)
    grant = local_grant(name, manifest, config)
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    grant_path = root / 'grant.json'
    grant_path.write_bytes(encoded(grant))
    evaluation_root = root / 'evaluator'
    evaluation_root.mkdir()
    captures = RecordStore(root / 'captures')
    dispatcher = None
    try:
        dispatcher = LocalDispatcher(root=evaluation_root, runtime_root=runtime_root, manifest=manifest,
            grant_path=grant_path, grant_sha256=executor.digest(grant_path.read_bytes()), captures=captures,
            benchmark=config)
        parent = await dispatcher.evaluate('parent', body=dispatcher.parent,
                                          candidate_ref=dispatcher.parent_ref, iteration=0)
        expected_count = len(executor.evaluation_fixtures(name))
        parent_passed = (parent.get('case_count') == parent.get('passed_count') == expected_count
                         and len(parent.get('rows', ())) == expected_count
                         and all(row.get('task_success') is True for row in parent['rows']))
        report = (await dispatcher.benchmark(dispatcher.parent, dispatcher.parent, iteration=0)
                  if parent_passed else None)
        tested = bool(parent_passed and report['correctness_passed'])
        reason = (None if tested else 'Current parent correctness evaluation incomplete or failing; benchmark not run'
                  if not parent_passed else report['summary'])
        result = {'status': 'tested' if tested else 'error', 'reason': reason,
            'kind': 'parent_a_a', 'scope': 'local_unprotected', 'model_calls': 0,
            'improvement_claimed': False, 'parent_correctness': parent, 'benchmark': report,
            'runtime_manifest_sha256': executor.digest(encoded(manifest)),
            'release_binding': manifest.get('target_bindings', {}).get(name),
            'evidence_directory': str(root.resolve())}
        (root / 'result.json').write_bytes(encoded(result))
        return result
    finally:
        if dispatcher is not None:
            dispatcher.close()
        captures.close()


async def run_catalog(*, output_root, selected=None, overrides=None, runtime_root=None, manifest=None):
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=False)
    inventory = benchmark_inventory()
    names = set(selected) if selected else {row['capsule_name'] for row in inventory}
    unknown = names - {row['capsule_name'] for row in inventory}
    if unknown:
        raise ValueError('Unknown capsule target(s): ' + ', '.join(sorted(unknown)))
    rows = [row for row in inventory if row['capsule_name'] in names]
    ready = [row['capsule_name'] for row in rows if row['status'] == 'ready']
    if ready and os.name != 'posix':
        for row in rows:
            if row['status'] == 'ready':
                row.update(status='skipped', reason='POSIX_LOCAL_DISPATCHER_REQUIRED; run in Linux/WSL')
        ready = []
    if ready:
        try:
            if runtime_root is None:
                runtime_root, manifest = stage_local_runtime(root / 'runtime', ready)
            else:
                if manifest is None:
                    raise ValueError('Captured manifest required with --runtime-root')
                verify_runtime(runtime_root, manifest)
            (root / 'runtime-manifest.json').write_bytes(encoded(manifest))
        except Exception as error:
            for row in rows:
                if row['status'] == 'ready':
                    row.update(status='error', reason=f'Runtime capture: {type(error).__name__}: {error}')
    for row in rows:
        if row['status'] != 'ready':
            continue
        try:
            row.update(await run_baseline(row['capsule_name'], runtime_root=runtime_root, manifest=manifest,
                output_root=root / row['capsule_name'], overrides=overrides))
        except Exception as error:
            row.update(status='error', reason=f'{type(error).__name__}: {error}')
    report = {'schema': SCHEMA, 'scope': 'local_unprotected', 'model_calls': 0,
        'improvement_claimed': False, 'rows': rows,
        'counts': {status: sum(row['status'] == status for row in rows) for status in ('tested', 'skipped', 'error')}}
    (root / 'report.json').write_bytes(encoded(report))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    run = commands.add_parser('run')
    selection = run.add_mutually_exclusive_group(required=True)
    selection.add_argument('--all', action='store_true')
    selection.add_argument('--capsule', action='append', dest='capsules')
    run.add_argument('--output', required=True, help='New evidence directory (never overwritten)')
    configuration = run.add_mutually_exclusive_group()
    configuration.add_argument('--config', help='Inline JSON benchmark overrides; absent uses frozen defaults')
    configuration.add_argument('--config-file', help='JSON file containing benchmark overrides')
    run.add_argument('--runtime-root', help='Optional previously captured code-only runtime')
    run.add_argument('--runtime-manifest', help='Required JSON manifest when reusing a runtime')
    args = parser.parse_args(argv)
    if args.command == 'list':
        print(json.dumps(benchmark_inventory(), indent=2))
        return 0
    if bool(args.runtime_root) != bool(args.runtime_manifest):
        parser.error('--runtime-root and --runtime-manifest must be supplied together')
    manifest = json.loads(Path(args.runtime_manifest).read_text('utf-8')) if args.runtime_manifest else None
    overrides = (json.loads(Path(args.config_file).read_text('utf-8')) if args.config_file
                 else json.loads(args.config) if args.config else None)
    report = asyncio.run(run_catalog(output_root=args.output, selected=args.capsules,
        overrides=overrides, runtime_root=args.runtime_root, manifest=manifest))
    print(json.dumps(report, indent=2))
    return 1 if report['counts']['error'] else 0


if __name__ == '__main__':
    raise SystemExit(main())
