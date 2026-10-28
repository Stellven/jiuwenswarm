"""Whole real capsule import/execute in an ordinary isolated subprocess.

This is public local interoperability, not protected worker qualification.
"""
import copy
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from jiuwenswarm.research_rsi.targets.capsules import public_fixtures
from jiuwenswarm.research_rsi.targets.capsule_runtime import (
    capture_runtime_manifest, capsule_job_assets, capsule_worker_program,
    check_capsule_output, inventory_runtime, validate_runtime_manifest, verify_runtime,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def installed_runtime(tmp_path_factory):
    # Test-only source closure uses the actual research packages and actual
    # installed jsonschema native dependencies; no API/type/validator shims.
    import jsonschema
    import jiuwenswarm.research.capsule_extensions.calculate.worker
    import jiuwenswarm.research.capsule_extensions.calculate.checks
    import jiuwenswarm.research.capsule_extensions.table_normalize.worker
    import jiuwenswarm.research.capsule_extensions.table_normalize.checks
    runtime = tmp_path_factory.mktemp('actual-capsule-runtime')
    package = runtime / 'source/jiuwenswarm'; package.mkdir(parents=True)
    shutil.copyfile(ROOT / 'jiuwenswarm/__init__.py', package / '__init__.py')
    source_root = ROOT / 'jiuwenswarm'
    sources = set((source_root / 'research_contracts').rglob('*.json'))
    for module in tuple(sys.modules.values()):
        filename = getattr(module, '__file__', None)
        if not filename:
            continue
        source = Path(filename).resolve()
        if source.is_relative_to(source_root) and source.suffix == '.py':
            relative = source.relative_to(source_root)
            if relative.parts[0] in {'research', 'research_records', 'research_contracts'}:
                sources.add(source)
    for source in sources:
        target = package / source.relative_to(source_root)
        target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, target)
    dependencies = runtime / 'dependencies'; dependencies.mkdir()
    dependency_root = Path(jsonschema.__file__).resolve().parent.parent
    for name in ('attr', 'attrs', 'jsonschema', 'jsonschema_specifications', 'referencing', 'rpds'):
        shutil.copytree(dependency_root / name, dependencies / name,
            ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'tests', 'fixtures'))
    shutil.copyfile(dependency_root / 'typing_extensions.py', dependencies / 'typing_extensions.py')
    manifest = capture_runtime_manifest(runtime, build_id='public-local-interoperability-only',
        dependency_environment={'distributions': [{'name': 'actual-local-review-dependencies', 'purpose': 'test_only'}]})
    return runtime, manifest


@pytest.mark.parametrize('name', ['utility.calculate', 'utility.table_normalize'])
@pytest.mark.parametrize('corrupt', [False, True, 'mutate_nested', 'replace_input'])
def test_fixed_runtime_program_executes_real_production_carrier_with_real_dependencies(installed_runtime, tmp_path, name, corrupt):
    runtime, manifest = installed_runtime
    fixture = public_fixtures(name)[-1]  # Both serialize substantially above 8 KiB.
    stem = 'calculate' if name.endswith('calculate') else 'table_normalize'
    body = (ROOT / f'jiuwenswarm/research/capsule_extensions/{stem}/worker.py').read_bytes()
    if corrupt in ('mutate_nested', 'replace_input'):
        injection = (b"    packet['data']['mutation'] = True\n" if corrupt == 'mutate_nested'
                     else b"    inputs['packet'] = dict(packet, unexpected=True)\n")
        body = body.replace(b"    packet = inputs['packet']\n", b"    packet = inputs['packet']\n" + injection)
    elif corrupt:
        before, after = ((b'result[column] = metrics', b'result[column] = {}') if stem == 'calculate'
                         else (b"return {'columns': columns, 'rows': rows}", b"return {'columns': columns, 'rows': list(reversed(rows))}"))
        assert body.count(before) == 1
        body = body.replace(before, after)
    assets = capsule_job_assets(name, runtime_root=runtime, manifest=manifest,
        candidate=body, inputs={'packet': fixture['packet']})
    resources = tmp_path / 'resources'; resources.mkdir()
    # Resource-path translation only, matching existing helper interoperability
    # tests. Generated production bootstrap is otherwise executed unmodified.
    shutil.copytree(runtime, resources / 'capsule-runtime')
    for filename, raw in assets['files'].items():
        (resources / filename).write_bytes(raw)
    # This ordinary Windows subprocess does not claim Linux seccomp/UID
    # confinement. The operational asset builder always emits that policy.
    program = capsule_worker_program(name, manifest_sha256=assets['runtime_manifest_sha256'],
        candidate_sha256=hashlib.sha256(body).hexdigest(),
        input_sha256=hashlib.sha256(assets['files']['input.json']).hexdigest(), process_policy=None)
    assert b'install_process_policy()' in assets['files']['worker.py']
    program = program.replace(b'/resources/', (resources.as_posix() + '/').encode())
    program = program.replace(b"'/resources/capsule-runtime'", repr((resources / 'capsule-runtime').as_posix()).encode())
    # A local denial control proves these real pure async carriers do not need
    # an event-loop socketpair. Linux kernel confinement remains separate.
    program = (b"import socket\ndef denied_socketpair(*a,**k):\n raise RuntimeError('test denies socketpair')\nsocket.socketpair=denied_socketpair\n" + program)
    (resources / 'worker.py').write_bytes(program)
    completed = subprocess.run([sys.executable, '-I', '-S', '-B', str(resources / 'worker.py')],
        capture_output=True, timeout=30)
    if corrupt in ('mutate_nested', 'replace_input'):
        assert completed.returncode != 0
        assert b'capsule input mutation refused' in completed.stderr
        assert completed.stdout == b''
        return
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    checked = check_capsule_output(name, inputs={'packet': fixture['packet']}, output=completed.stdout,
        expected_checks_sha256=assets['checks_sha256'])
    assert checked['task_success'] is (not corrupt)
    assert checked['output_bytes'] > 8192
    assert checked['output_bytes'] < assets['output_limit_bytes'] == 2 * 1024 * 1024
    assert assets['mutable_path'] == f'research/capsule_extensions/{stem}/worker.py'
    assert assets['production_admission'] == 'UNKNOWN'


def test_frozen_inventory_rejects_changed_missing_and_unexpected_files(installed_runtime, tmp_path):
    runtime, manifest = installed_runtime
    assert verify_runtime(runtime, manifest) == manifest
    changed = copy.deepcopy(manifest); changed['files'][0]['sha256'] = '0' * 64
    with pytest.raises(ValueError): verify_runtime(runtime, changed)
    changed = copy.deepcopy(manifest); changed['files'].pop()
    with pytest.raises(ValueError): verify_runtime(runtime, changed)
    root = tmp_path / 'runtime'; (root / 'source').mkdir(parents=True)
    (root / 'source/body.py').write_text('source')
    expected = inventory_runtime(root)
    (root / 'source/extra.py').write_text('unexpected')
    assert inventory_runtime(root) != expected


def test_manifest_rejects_traversal_collisions_shadow_packages_and_unknown_targets(installed_runtime):
    _, manifest = installed_runtime
    for path in ('../escape.py', 'source/../escape.py', 'source\\body.py', 'accounts/token.json',
                 'source/fixtures/data.json', 'source/__pycache__/module.pyc'):
        changed = copy.deepcopy(manifest); changed['files'][0]['path'] = path
        with pytest.raises(ValueError): validate_runtime_manifest(changed)
    changed = copy.deepcopy(manifest)
    head, tail = changed['files'][0]['path'].rsplit('/', 1)
    changed['files'].append(dict(changed['files'][0], path=head + '/' + tail.upper()))
    with pytest.raises(ValueError): validate_runtime_manifest(changed)
    changed = copy.deepcopy(manifest); changed['target_modules']['research.builder'] = 'arbitrary'
    with pytest.raises(ValueError): validate_runtime_manifest(changed)
    changed = copy.deepcopy(manifest); changed['files'].append({'path': 'dependencies/jiuwenswarm/__init__.py', 'sha256': 'a' * 64, 'size_bytes': 0})
    with pytest.raises(ValueError): validate_runtime_manifest(changed)


def test_child_program_and_check_owner_do_not_accept_arbitrary_targets_or_unbounded_bytes():
    pins = dict(manifest_sha256='a' * 64, candidate_sha256='b' * 64, input_sha256='c' * 64)
    with pytest.raises(ValueError): capsule_worker_program('research.builder', **pins)
    with pytest.raises(ValueError): capsule_worker_program('utility.calculate', iterations=True, **pins)
    with pytest.raises(ValueError): check_capsule_output('utility.calculate', inputs={'packet': {}}, output=b'x' * (2 * 1024 * 1024 + 1))
    with pytest.raises(ValueError): check_capsule_output('utility.calculate', inputs={'packet': {}}, output=b'{"a":1,"a":2}')
