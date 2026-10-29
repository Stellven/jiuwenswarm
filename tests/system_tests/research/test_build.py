"""Synthetic archive/host-driver boundaries; never image qualification."""
from copy import deepcopy
import json
from pathlib import Path
import stat
import subprocess
import tarfile
import zipfile
import warnings

import pytest

from scripts import research_build as build
from scripts.research_candidate import DEFAULT_SCOPE, capture_candidate


def fixture(tmp_path):
    root = tmp_path / 'source'; root.mkdir()
    files = {'LICENSE': b'public license\n', 'uv.lock': b'locked fixture\n',
             'jiuwenswarm/component.py': b'public source\n'}
    for dockerfile, _, _ in build.TARGETS.values():
        files[dockerfile] = b'FROM fixture AS production\n'
        files[dockerfile + '.dockerignore'] = b'**\n!jiuwenswarm/**\n'
    receipt = {'path': 'source.txt', 'bytes': 17, 'sha256': build.sha(b'controlled source')}
    (root / 'source.txt').write_bytes(b'controlled source')
    baseline = {'architecture': {'files': [receipt]}, 'prd': receipt, 'qa': [], 'invoked_prompt': receipt}
    files['docs/code/Missions/M1/source-baseline.json'] = build.encoded(baseline)
    for name, raw in files.items():
        path = root / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    snapshot = tmp_path / 'source.zip'
    manifest = capture_candidate(root, snapshot=snapshot)
    candidate = tmp_path / 'candidate.json'; candidate.write_bytes(build.encoded(manifest))
    return root, manifest, candidate, snapshot


def rewrite(snapshot, rows):
    snapshot.unlink()
    with zipfile.ZipFile(snapshot, 'x') as archive:
        for name, raw, mode in rows:
            info = zipfile.ZipInfo(name); info.external_attr = mode << 16
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', message='Duplicate name:', category=UserWarning)
                archive.writestr(info, raw)


def contents(snapshot):
    with zipfile.ZipFile(snapshot) as archive:
        return [(x.filename, archive.read(x), x.external_attr >> 16) for x in archive.infolist()]


def reidentify(manifest):
    manifest['candidate_id'] = build.sha(build.encoded({k: manifest[k] for k in ('schema_version', 'base_head', 'scope', 'files')}))


def test_exact_snapshot_becomes_deterministic_original_byte_tar(tmp_path):
    _, manifest, _, snapshot = fixture(tmp_path)
    first, second = tmp_path / 'a.tar', tmp_path / 'b.tar'
    a = build.context_tar(manifest, snapshot, first)
    b = build.context_tar(manifest, snapshot, second)
    assert a == b and first.read_bytes() == second.read_bytes()
    with tarfile.open(first) as tar:
        assert tar.getnames() == sorted(row['path'] for row in manifest['files'])
        for item in tar:
            assert item.isfile() and item.mode == 0o644 and item.uid == item.gid == item.mtime == 0
            assert item.uname == item.gname == ''
            raw = tar.extractfile(item).read()
            original = next(row for row in manifest['files'] if row['path'] == item.name)
            assert len(raw) == original['bytes'] and build.sha(raw) == original['sha256']
    with pytest.raises(FileExistsError):
        build.context_tar(manifest, snapshot, first)


@pytest.mark.parametrize('mutation', ['extra', 'duplicate', 'missing', 'symlink', 'directory', 'traversal',
    'absolute', 'backslash', 'noncanonical', 'private', 'case', 'digest', 'size'])
def test_archive_rejects_every_nonexclusive_or_changed_member_before_context(tmp_path, mutation):
    _, manifest, _, snapshot = fixture(tmp_path)
    rows = contents(snapshot)
    name, raw, mode = rows[0]
    if mutation == 'extra': rows.append(('scripts/extra.py', b'extra', mode))
    elif mutation == 'duplicate': rows.append(rows[0])
    elif mutation == 'missing': rows.pop()
    elif mutation == 'symlink': rows[0] = (name, raw, stat.S_IFLNK | 0o644)
    elif mutation == 'directory': rows[0] = (name + '/', raw, stat.S_IFDIR | 0o644)
    elif mutation == 'traversal': rows[0] = ('scripts/../outside', raw, mode)
    elif mutation == 'absolute': rows[0] = ('/scripts/source', raw, mode)
    elif mutation == 'backslash': rows[0] = ('scripts\\outside', raw, mode)
    elif mutation == 'noncanonical': rows[0] = ('scripts//source', raw, mode)
    elif mutation == 'private': rows.append(('jiuwenswarm/auth.json', b'private', mode))
    elif mutation == 'case': rows.append(('license', raw, mode))
    elif mutation == 'digest': rows[0] = (name, bytes([raw[0] ^ 1]) + raw[1:], mode)
    elif mutation == 'size': rows[0] = (name, raw + b'x', mode)
    rewrite(snapshot, rows)
    manifest['snapshot']['sha256'] = build.file_sha(snapshot)  # Even a repinned bad ZIP must fail its inventory.
    with pytest.raises(build.BuildBlocked):
        build.context_tar(manifest, snapshot, tmp_path / 'context.tar')
    assert not (tmp_path / 'context.tar').exists()


def test_candidate_full_scope_identity_and_snapshot_pin_are_independent(tmp_path):
    _, manifest, _, snapshot = fixture(tmp_path)
    for change, message in [('identity', 'IDENTITY'), ('scope', 'FULL_DEFAULT'), ('hash', 'SNAPSHOT_HASH')]:
        altered = deepcopy(manifest)
        if change == 'identity': altered['candidate_id'] = 'a' * 64
        elif change == 'scope': altered['scope'] = ['jiuwenswarm']; reidentify(altered)
        else: altered['snapshot']['sha256'] = 'a' * 64
        with pytest.raises(build.BuildBlocked, match=message):
            build.context_tar(altered, snapshot, tmp_path / (change + '.tar'))
    with pytest.raises(build.BuildBlocked, match='NONCANONICAL'):
        build.logical_name('scripts/./source.py')
    with pytest.raises(build.BuildBlocked, match='PRIVATE'):
        build.logical_name('jiuwenswarm/resources/elsewhere/.env.template')


def test_archive_alias_and_hardlink_are_rejected(tmp_path):
    _, manifest, _, snapshot = fixture(tmp_path)
    alias = tmp_path / 'alias.zip'; alias.symlink_to(snapshot)
    with pytest.raises(build.BuildBlocked, match='ALIAS'):
        build.context_tar(manifest, alias, tmp_path / 'context.tar')
    alias.unlink(); alias.hardlink_to(snapshot)
    with pytest.raises(build.BuildBlocked, match='SINGLE_LINK'):
        build.context_tar(manifest, snapshot, tmp_path / 'context.tar')


@pytest.mark.parametrize('hidden', ['prefix', 'suffix', 'comment'])
def test_archive_cannot_hide_bytes_outside_its_declared_member_population(tmp_path, hidden):
    _, manifest, _, snapshot = fixture(tmp_path)
    if hidden == 'prefix': snapshot.write_bytes(b'undeclared prefix' + snapshot.read_bytes())
    elif hidden == 'suffix':
        with snapshot.open('ab') as stream: stream.write(b'undeclared suffix')
    else:
        with zipfile.ZipFile(snapshot, 'a') as archive: archive.comment = b'undeclared comment'
    manifest['snapshot']['sha256'] = build.file_sha(snapshot)
    with pytest.raises(build.BuildBlocked, match='EXTRA_ARCHIVE'):
        build.context_tar(manifest, snapshot, tmp_path / 'context.tar')


class FakeHost:
    """Explicit synthetic Docker transcript, never accepted runtime proof."""
    def __init__(self, root, config):
        self.root, self.config, self.prefix = root, config, ['fixture-docker']
        self.commands, self.images = [], {}
        self.change, self.fail, self.timeout, self.bad_platform, self.parent_drift = None, False, False, False, False

    def run(self, args, **kwargs):
        self.commands.append(self.prefix + args)
        stdout, stderr, code = b'', b'', 0
        if args[:2] == ['image', 'inspect']:
            row = self.images.get(args[2]); code = 0 if row else 1
            stdout = build.encoded([row]) if row else b''
            if not row: stderr = b'Error response from daemon: No such image: ' + args[2].encode()
        elif args[:2] == ['image', 'tag']:
            source = next(row for row in self.images.values() if row['Id'] == args[2])
            self.images[args[3]] = deepcopy(source)
        elif args[:2] == ['container', 'inspect']: code, stderr = 1, b'Error: No such object: ' + args[2].encode()
        elif args[0] == 'run': stdout = build.encoded({'schema': 'ai4r-image-runtime-observation:1', 'synthetic': True})
        else: raise AssertionError(args)
        return subprocess.CompletedProcess(args, code, stdout, stderr)

    def json(self, args):
        assert args == ['context', 'inspect', 'default']
        self.commands.append(self.prefix + args)
        return [{'Endpoints': {'docker': {'Host': 'unix:///var/run/docker.sock'}}}]

    def build(self, args, context, output, timeout):
        self.commands.append(self.prefix + args)
        tag = args[args.index('--tag') + 1]
        labels = dict(args[index + 1].split('=', 1) for index, item in enumerate(args) if item == '--label')
        with tarfile.open(context) as tar:
            assert tar.getnames() and all(x.isfile() for x in tar)
        if not self.fail:
            self.images[tag] = {'Id': 'sha256:' + 'b' * 64, 'Os': 'linux',
                'Architecture': 'arm64' if self.bad_platform else 'amd64', 'Config': {'Labels': labels}, 'RepoDigests': []}
        if self.change: self.change()
        if self.parent_drift: self.images['ai4r-app:parent']['Id'] = 'sha256:' + 'c' * 64
        build.write_new(output / 'build.stdout.log', b'synthetic build transcript\n')
        build.write_new(output / 'build.stderr.log', b'')
        build.write_new(output / 'build-metadata.json', {'synthetic': True})
        return {'returncode': 1 if self.fail else (None if self.timeout else 0), 'timed_out': self.timeout}


def invoke(tmp_path, *, change=None, target='app-production', timeout=False, fail=False, bad_platform=False, parent_drift=False):
    root, manifest, candidate, snapshot = fixture(tmp_path)
    host = FakeHost(root, tmp_path)
    host.change = (lambda: (root / 'jiuwenswarm/component.py').write_bytes(b'changed during Docker build')) if change else None
    host.timeout, host.fail, host.bad_platform, host.parent_drift = timeout, fail, bad_platform, parent_drift
    parent = 'ai4r-app:parent' if build.TARGETS[target][2] else None
    if parent: host.images[parent] = {'Id': 'sha256:' + 'a' * 64, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {'Labels': {}}}
    kwargs = dict(root=root, candidate=candidate, snapshot=snapshot, target=target, platform='linux/amd64',
        tag='ai4r-image:unique', job_id='ai4r-build-unit', output=tmp_path / 'result', parent_image=parent,
        host_factory=lambda *_: host)
    return build.produce(**kwargs), host, kwargs, manifest


@pytest.mark.parametrize('target', list(build.TARGETS))
def test_closed_targets_only_send_validated_context_and_owned_local_identity(tmp_path, target):
    result, host, kwargs, manifest = invoke(tmp_path, target=target)
    assert result['outcome'] == 'BUILT' and result['qualification'] == 'NOT_ASSESSED' and result['checkout_current'] is True
    assert result['candidate_id'] == manifest['candidate_id'] and result['context_unchanged'] is True
    assert host.config == tmp_path  # The synthetic host deliberately does not read production Docker config.
    command = result['command']; dockerfile, stage, parent = build.TARGETS[target]
    assert command[command.index('--file') + 1] == dockerfile and command[command.index('--target') + 1] == stage
    assert command[-1] == '-' and '--push' not in command and '--secret' not in command and '--network' not in command
    if parent:
        assert result['parent']['unchanged'] and 'APP_IMAGE=ai4r-m1-parent:ai4r-build-unit' in command
        assert result['parent']['before']['image_id'] == 'sha256:' + 'a' * 64
    assert json.loads((kwargs['output'] / 'receipt.json').read_bytes()) == result


@pytest.mark.parametrize('failure', ['fail', 'timeout', 'bad_platform', 'parent_drift'])
def test_failed_unknown_wrong_platform_and_parent_drift_never_become_built(tmp_path, failure):
    result, _, _, _ = invoke(tmp_path, target='rsi-production' if failure == 'parent_drift' else 'app-production', **{failure: True})
    assert result['outcome'] == ('OUTCOME_UNKNOWN' if failure == 'timeout' else 'FAILED')
    assert result['qualification'] == 'NOT_ASSESSED'


def test_checkout_edit_preserves_frozen_build_but_records_staleness(tmp_path):
    result, _, _, manifest = invoke(tmp_path, change=True)
    assert result['outcome'] == 'BUILT' and result['checkout_current'] is False
    assert result['candidate_id'] == manifest['candidate_id']
    assert result['changed_execution_inputs'] == ['jiuwenswarm/component.py']


def test_bad_or_currentness_inputs_never_dispatch_docker_and_output_is_exclusive(tmp_path):
    root, _, candidate, snapshot = fixture(tmp_path)
    def forbidden(*_): raise AssertionError('Docker must not start')
    common = dict(root=root, candidate=candidate, snapshot=snapshot, target='app-production', platform='linux/amd64',
        tag='ai4r-image:unique', job_id='ai4r-build-unit', host_factory=forbidden)
    for key, bad in [('target', 'other'), ('platform', 'windows/amd64'), ('tag', 'registry.example/ai4r:x'),
                     ('tag', '--push'), ('job_id', '../outside'), ('parent_image', 'ai4r-app:parent'), ('timeout_s', 0)]:
        with pytest.raises(build.BuildBlocked):
            build.produce(**{**common, key: bad}, output=tmp_path / 'not-created')
        assert not (tmp_path / 'not-created').exists()
    (root / 'jiuwenswarm/component.py').write_bytes(b'changed before build')
    result = build.produce(**common, output=tmp_path / 'result')
    assert result['outcome'] == 'BLOCKED' and result['error']['code'] == 'CHECKOUT_DIFFERS_FROM_FROZEN_CANDIDATE'
    with pytest.raises(FileExistsError): build.produce(**common, output=tmp_path / 'result')


def test_existing_output_image_is_not_overwritten(tmp_path):
    root, _, candidate, snapshot = fixture(tmp_path)
    host = FakeHost(root, tmp_path)
    host.images['ai4r-image:exists'] = {'Id': 'sha256:' + 'a' * 64, 'Os': 'linux', 'Architecture': 'amd64', 'Config': {}}
    result = build.produce(root=root, candidate=candidate, snapshot=snapshot, target='app-production', platform='linux/amd64',
        tag='ai4r-image:exists', job_id='ai4r-build-unit', output=tmp_path / 'result', host_factory=lambda *_: host)
    assert result['outcome'] == 'BLOCKED' and result['error']['code'] == 'OUTPUT_IMAGE_TAG_ALREADY_EXISTS'
    assert not any('buildx' in command for command in host.commands)


def test_lookup_failure_is_never_treated_as_a_new_unused_image_tag(tmp_path):
    class Unavailable(FakeHost):
        def run(self, args, **kwargs):
            if args[:2] == ['image', 'inspect']:
                return subprocess.CompletedProcess(args, 1, b'', b'Cannot connect to the Docker daemon')
            return super().run(args, **kwargs)
    root, _, candidate, snapshot = fixture(tmp_path)
    host = Unavailable(root, tmp_path)
    result = build.produce(root=root, candidate=candidate, snapshot=snapshot, target='app-production', platform='linux/amd64',
        tag='ai4r-image:new', job_id='ai4r-build-unit', output=tmp_path / 'result', host_factory=lambda *_: host)
    assert result['outcome'] == 'BLOCKED' and result['error']['code'] == 'LOCAL_IMAGE_LOOKUP_FAILED'
    assert not any('buildx' in command for command in host.commands)


def test_production_client_uses_new_empty_configuration_without_inherited_registry_auth(tmp_path):
    config = tmp_path / 'docker-client'; config.mkdir()
    host = build.FrozenDockerHost(tmp_path, config)
    assert 'DOCKER_CONFIG=' + build.linux_path(config) in host.prefix
    assert host.prefix[-3:] == ['docker', '--context', 'default']
    assert list(config.iterdir()) == []


def test_control_failure_after_dispatch_is_unknown_even_without_returned_build_result(tmp_path):
    class LostControl(FakeHost):
        def build(self, *args):
            raise RuntimeError('Synthetic dispatch connection lost')
    root, _, candidate, snapshot = fixture(tmp_path)
    host = LostControl(root, tmp_path)
    result = build.produce(root=root, candidate=candidate, snapshot=snapshot, target='app-production', platform='linux/amd64',
        tag='ai4r-image:new', job_id='ai4r-build-unit', output=tmp_path / 'result', host_factory=lambda *_: host)
    assert result['outcome'] == 'OUTCOME_UNKNOWN' and result['error']['code'] == 'RuntimeError'
    assert result['build_dispatch']['status'] == 'ISSUED' and 'build' not in result


@pytest.mark.parametrize('foreign', [False, True])
def test_inspector_timeout_retains_cleanup_truth_and_never_removes_foreign_container(tmp_path, foreign):
    class TimedInspector(FakeHost):
        def __init__(self, *args):
            super().__init__(*args); self.present = False
        def run(self, args, **kwargs):
            if args[0] == 'run':
                self.present = True
                raise build.BuildBlocked('LOCAL_DOCKER_UNAVAILABLE_OR_TIMEOUT')
            if args[:2] == ['container', 'inspect'] and self.present:
                self.commands.append(self.prefix + args)
                rows = [{'Config': {'Labels': {'ai4r.owner': 'foreign-job' if foreign else 'ai4r-build-unit'}}}]
                return subprocess.CompletedProcess(args, 0, build.encoded(rows), b'')
            if args[:3] == ['container', 'rm', '--force']:
                self.commands.append(self.prefix + args); self.present = False
                return subprocess.CompletedProcess(args, 0, b'', b'')
            return super().run(args, **kwargs)
    host = TimedInspector(tmp_path, tmp_path)
    result = build.runtime_observation(host, 'sha256:' + 'a' * 64, 'ai4r-build-unit', tmp_path)
    assert result['available'] is False and result['error'] == 'BuildBlocked'
    assert result['cleanup']['attempted'] is (not foreign)
    assert result['cleanup']['confirmed'] is (not foreign)
    if foreign:
        assert result['cleanup']['error'] == 'INSPECTION_CLEANUP_OWNERSHIP_CHANGED'
        assert not any(command[1:3] == ['container', 'rm'] for command in host.commands)
