"""Independent closure predicates on explicit fixtures; never image proof."""
from copy import deepcopy
import base64
import json
from pathlib import Path
import subprocess

import pytest

from scripts.research_image_closure_probe import CHECKS, encoded, sha, verify


def fixture(tmp_path):
    site = tmp_path / 'site'; native = site / 'jiuwenswarm'; tui = site / 'jiuwenswarm_tui'
    native.mkdir(parents=True); tui.mkdir()
    project = b'[tool.setuptools.package-data]\njiuwenswarm=["resources/**"]\n'
    tui_project = b'[tool.setuptools.package-data]\njiuwenswarm_tui=["resources/**"]\n'
    source = {'pyproject.toml': project, 'uv.lock': b'locked requirements',
        'packages/jiuwenswarm-tui/pyproject.toml': tui_project,
        'jiuwenswarm/__init__.py': b'', 'jiuwenswarm/module.py': b'value=1\n',
        'jiuwenswarm/resources/info.json': b'{"public":true}',
        'packages/jiuwenswarm-tui/jiuwenswarm_tui/__init__.py': b'',
        'jiuwenswarm/channels/web/frontend/package-lock.json': b'{"lockfileVersion":3}',
        'jiuwenswarm/channels/tui/frontend/package-lock.json': b'{"lockfileVersion":3}'}
    native_files = {'__init__.py': b'', 'module.py': b'value=1\n', 'resources/info.json': b'{"public":true}',
        'channels/web/frontend/dist/assets/app.js': b'compiled web',
        'channels/tui/frontend/dist/main.js': b'compiled tui',
        'channels/tui/frontend/node_modules/example/index.js': b'locked Node dependency'}
    for root, files in ((native, native_files), (tui, {'__init__.py': b''})):
        for name, raw in files.items():
            path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    def row(name, raw): return {'path': name, 'bytes': len(raw), 'sha256': sha(raw)}
    manifest = {'schema': 'ai4r-installed-build:2', 'files': [row(name, raw) for name, raw in sorted(native_files.items())], 'links': [],
        'components': {'jiuwenswarm_tui': {'files': [row('__init__.py', b'')], 'links': []}},
        'dependencies': [{'name': 'example', 'version': '1.2'}], 'uv_lock_sha256': sha(source['uv.lock']), 'pyproject_sha256': sha(project)}
    manifest['build_id'] = sha(encoded(manifest))
    manifest_path = tmp_path / 'manifest.json'; manifest_path.write_bytes(encoded(manifest))
    metadata = site / 'example-1.2.dist-info'; metadata.mkdir()
    (metadata / 'METADATA').write_bytes(b'Metadata-Version: 2.1\nName: example\nVersion: 1.2\n')
    candidate = {'schema_version': '1.0.0', 'base_head': None, 'scope': [], 'files': [row(name, raw) for name, raw in sorted(source.items())]}
    candidate['candidate_id'] = sha(encoded(candidate))
    value = {'schema': 'ai4r-installed-closure-input:1', 'candidate': candidate,
        'source_build_receipt_sha256': 'a' * 64, 'context_sha256': 'b' * 64, 'snapshot_sha256': 'c' * 64,
        'image_id': 'sha256:' + 'd' * 64, 'platform': 'linux/amd64', 'build_id': manifest['build_id'],
        'source_payloads': {'pyproject.toml': base64.b64encode(project).decode(),
            'packages/jiuwenswarm-tui/pyproject.toml': base64.b64encode(tui_project).decode()}}
    paths = {'manifest': manifest_path, 'native': native, 'tui': tui, 'site': site}
    return value, paths, manifest


def refreeze(value, paths, manifest):
    manifest['build_id'] = sha(encoded({key: item for key, item in manifest.items() if key != 'build_id'}))
    paths['manifest'].write_bytes(encoded(manifest)); value['build_id'] = manifest['build_id']


def test_independent_fixture_checks_all_bytes_metadata_and_generated_lineage_without_product_import(tmp_path):
    value, paths, _ = fixture(tmp_path)
    # These files must never execute, including Python's normal .pth mechanism.
    (paths['site'] / 'hostile.pth').write_text("raise AssertionError('pth executed')", encoding='utf8')
    hostile = paths['site'] / 'example'; hostile.mkdir(); (hostile / '__init__.py').write_text("raise AssertionError('package imported')", encoding='utf8')
    result = verify(value, fixture_paths=paths)
    assert result['qualified'] and result['mode'] == 'fixture' and set(result['assertions']) == set(CHECKS)
    assert all(result['assertions'].values()) and result['source_files_matched'] == 4
    assert result['generated_outputs']['channels/web/frontend/dist/']['kind'] == 'compiled_web'
    assert result['generated_outputs']['channels/tui/frontend/node_modules/']['kind'] == 'locked_tui_dependency'
    assert result['joins']['candidate_id'] == value['candidate']['candidate_id']


@pytest.mark.parametrize('change', ['bytes', 'extra', 'bytecode', 'missing', 'manifest_identity', 'source', 'lock', 'metadata', 'unidentified_output'])
def test_any_installed_source_manifest_lock_or_dependency_drift_stays_false(tmp_path, change):
    value, paths, manifest = fixture(tmp_path)
    if change == 'bytes': (paths['native'] / 'module.py').write_bytes(b'different source')
    elif change == 'extra': (paths['native'] / 'extra.py').write_bytes(b'extra installed code')
    elif change == 'bytecode':
        path = paths['native'] / '__pycache__/module.cpython-312.pyc'; path.parent.mkdir(); path.write_bytes(b'unchecked executable bytecode')
    elif change == 'missing': (paths['tui'] / '__init__.py').unlink()
    elif change == 'manifest_identity': manifest['build_id'] = 'f' * 64; paths['manifest'].write_bytes(encoded(manifest))
    elif change == 'source':
        raw = b'changed installed source with refrozen installed manifest'
        (paths['native'] / 'module.py').write_bytes(raw)
        next(row for row in manifest['files'] if row['path'] == 'module.py').update(bytes=len(raw), sha256=sha(raw))
        refreeze(value, paths, manifest)
    elif change == 'lock': manifest['uv_lock_sha256'] = 'e' * 64; refreeze(value, paths, manifest)
    elif change == 'metadata': (paths['site'] / 'example-1.2.dist-info/METADATA').write_bytes(b'Name: example\nVersion: 9.9\n')
    else:
        (paths['native'] / 'unknown.bin').write_bytes(b'unknown')
        manifest['files'].append({'path': 'unknown.bin', 'bytes': 7, 'sha256': sha(b'unknown')}); refreeze(value, paths, manifest)
    result = verify(value, fixture_paths=paths)
    assert result['qualified'] is False and result.get('error')


def test_declared_resource_missing_from_both_installed_files_and_manifest_is_still_required(tmp_path):
    value, paths, manifest = fixture(tmp_path)
    (paths['native'] / 'resources/info.json').unlink()
    manifest['files'] = [row for row in manifest['files'] if row['path'] != 'resources/info.json']
    refreeze(value, paths, manifest)
    result = verify(value, fixture_paths=paths)
    assert result['qualified'] is False and result['error'] == 'REQUIRED_FROZEN_SOURCE_MISSING'


def test_generated_assets_require_the_original_frozen_package_lock(tmp_path):
    value, paths, _ = fixture(tmp_path)
    candidate = value['candidate']
    candidate['files'] = [row for row in candidate['files'] if row['path'] != 'jiuwenswarm/channels/web/frontend/package-lock.json']
    candidate['candidate_id'] = sha(encoded({key: item for key, item in candidate.items() if key != 'candidate_id'}))
    result = verify(value, fixture_paths=paths)
    assert not result['qualified'] and result['error'] == 'GENERATED_OUTPUT_LOCK_MISSING'


def test_alias_escape_and_duplicate_member_do_not_verify(tmp_path):
    value, paths, manifest = fixture(tmp_path)
    original = paths['native'] / 'module.py'; original.unlink(); original.symlink_to(paths['site'] / 'example-1.2.dist-info/METADATA')
    assert verify(value, fixture_paths=paths)['error'] == 'FILE_ALIAS'
    original.unlink(); original.write_bytes(b'value=1\n')
    manifest['files'].append(deepcopy(manifest['files'][0])); refreeze(value, paths, manifest)
    assert verify(value, fixture_paths=paths)['error'] == 'DUPLICATE_COMPONENT_PATH'


def host_fixture(tmp_path):
    from scripts.research_candidate import capture_candidate
    from scripts.research_build import context_tar, file_sha
    from scripts.research_image_closure import _linux
    value, installed_paths, manifest = fixture(tmp_path)
    root = tmp_path / 'source'; root.mkdir()
    payloads = {'pyproject.toml': base64.b64decode(value['source_payloads']['pyproject.toml']),
        'packages/jiuwenswarm-tui/pyproject.toml': base64.b64decode(value['source_payloads']['packages/jiuwenswarm-tui/pyproject.toml']),
        'uv.lock': b'locked requirements', 'jiuwenswarm/__init__.py': b'', 'jiuwenswarm/module.py': b'value=1\n',
        'jiuwenswarm/resources/info.json': b'{"public":true}',
        'packages/jiuwenswarm-tui/jiuwenswarm_tui/__init__.py': b'',
        'jiuwenswarm/channels/web/frontend/package-lock.json': b'{"lockfileVersion":3}',
        'jiuwenswarm/channels/tui/frontend/package-lock.json': b'{"lockfileVersion":3}',
        'deploy/m1/Dockerfile.app': b'controlled fixture Dockerfile', 'deploy/m1/Dockerfile.app.dockerignore': b'controlled fixture ignore',
        'docs/code/Missions/M1/source-baseline.json': b'{"fixture":true}'}
    for name, raw in payloads.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    proof = tmp_path / 'proof'; proof.mkdir()
    candidate = capture_candidate(root, snapshot=proof / 'source.zip')
    context = context_tar(candidate, proof / 'source.zip', proof / 'context.tar')
    (proof / 'candidate.json').write_bytes(encoded(candidate))
    for name in ('build.stdout.log', 'build.stderr.log', 'build-metadata.json', 'runtime.stdout.json'):
        (proof / name).write_bytes(b'{}')
    record = {'schema': 'ai4r-source-build:1', 'job_id': 'ai4r-build-unit', 'target': 'app-production',
        'platform': 'linux/amd64', 'image': {'image_id': value['image_id'], 'platform': 'linux/amd64'},
        'tag': 'ai4r-app:fixture', 'outcome': 'BUILT', 'context_unchanged': True, 'output_tag_unchanged': True,
        'producer_completed': True, 'build': {'returncode': 0, 'timed_out': False},
        'candidate_id': candidate['candidate_id'], 'candidate_manifest_sha256': file_sha(proof / 'candidate.json'),
        'snapshot_sha256': candidate['snapshot']['sha256'], 'context': context,
        'source_baseline_sha256': sha(payloads['docs/code/Missions/M1/source-baseline.json']),
        'runtime': {'observation': {'build': {'sha256': file_sha(installed_paths['manifest'])}}},
        'artifacts': [{'path': name, 'bytes': (proof / name).stat().st_size, 'sha256': file_sha(proof / name)}
                      for name in ('candidate.json', 'context.tar', 'build.stdout.log', 'build.stderr.log', 'build-metadata.json', 'runtime.stdout.json')]}
    record['command'] = ['docker', '--context', 'default', 'buildx', 'build', '--builder', 'default', '--platform', 'linux/amd64',
        '--file', 'deploy/m1/Dockerfile.app', '--target', 'production', '--tag', record['tag'], '--load', '--progress', 'plain',
        '--metadata-file', _linux(proof / 'build-metadata.json'), '--label', 'ai4r.owner=' + record['job_id'],
        '--label', 'ai4r.candidate=' + candidate['candidate_id'], '--label', 'ai4r.source-context=' + context['sha256'], '-']
    path = proof / 'receipt.json'; path.write_bytes(encoded(record))
    profile = {'job_id': 'ai4r-closure-unit', 'image_id': value['image_id'], 'platform': 'linux/amd64',
               'build_id': manifest['build_id'], 'candidate_id': candidate['candidate_id']}
    pin = {'path': str(path), 'sha256': file_sha(path)}
    return root, proof, record, profile, pin, installed_paths


class ClosureHost:
    """Explicit synthetic Docker transcript, including a fixture observation."""
    def __init__(self, root, paths, profile, output):
        self.root, self.paths, self.profile, self.output = root, paths, profile, output
        self.commands = []; self.mutation = None
    def json(self, args):
        self.commands.append(args)
        assert args == ['image', 'inspect', self.profile['image_id']]
        return [{'Id': self.profile['image_id'], 'Os': 'linux', 'Architecture': 'amd64'}]
    def run(self, args, **kwargs):
        self.commands.append(args)
        if args[:2] == ['container', 'inspect']:
            return subprocess.CompletedProcess(args, 1, b'', b'Error: No such object: probe')
        assert args[0] == 'run' and args[-4:-1] == ['-I', '-S', '-c']
        source = json.loads((self.output / 'image-closure-input.json').read_bytes())
        value = verify(source, fixture_paths=self.paths)
        # This conversion exists only in the explicitly fake Docker test host.
        value['mode'] = 'installed'
        if self.mutation == 'fixture': value['mode'] = 'fixture'
        elif self.mutation == 'assertions': value['assertions'] = {'manifest_identity': True}
        elif self.mutation == 'join': value['joins']['context_sha256'] = '0' * 64
        return subprocess.CompletedProcess(args, 0, encoded(value), b'')


@pytest.mark.parametrize('mutation', [None, 'fixture', 'assertions', 'join'])
def test_host_consumer_binds_original_proof_actual_image_and_full_independent_population(tmp_path, mutation):
    from scripts.research_image_closure import inspect_closure
    root, _, _, profile, pin, paths = host_fixture(tmp_path)
    output = tmp_path / 'output'; output.mkdir()
    host = ClosureHost(root, paths, profile, output); host.mutation = mutation
    result = inspect_closure(host, profile, pin, output)
    assert result['qualified'] is (mutation is None)
    assert result['current_candidate_qualified'] is False
    assert result['cleanup']['confirmed']
    command = next(command for command in host.commands if command[0] == 'run')
    assert command[command.index('--user') + 1] == '65534:65534'
    assert command[command.index('--network') + 1] == 'none'
    assert '--cap-add' not in command and '--privileged' not in command
    assert command[-5] == profile['image_id']


@pytest.mark.parametrize('mutation', ['artifact', 'outcome', 'command', 'receipt_hash'])
def test_host_consumer_rejects_changed_or_inconsistent_source_proof_before_any_docker_effect(tmp_path, mutation):
    from scripts.research_image_closure import inspect_closure
    from scripts.research_build import file_sha
    root, proof, record, profile, pin, paths = host_fixture(tmp_path)
    if mutation == 'artifact': (proof / 'build.stdout.log').write_bytes(b'changed raw evidence')
    elif mutation == 'outcome': record['outcome'] = 'OUTCOME_UNKNOWN'
    elif mutation == 'command': record['command'].append('--push')
    else: pin['sha256'] = 'a' * 64
    if mutation in {'outcome', 'command'}:
        Path(pin['path']).write_bytes(encoded(record)); pin['sha256'] = file_sha(pin['path'])
    output = tmp_path / 'output'; output.mkdir()
    host = ClosureHost(root, paths, profile, output)
    result = inspect_closure(host, profile, pin, output)
    assert result['qualified'] is False and result.get('error')
    assert host.commands == []
