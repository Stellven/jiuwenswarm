import json
import sys

import pytest

from jiuwenswarm.factory import spark_engine
from jiuwenswarm.factory.targets import labels


def test_non_native_build_refuses_before_commands(tmp_path, monkeypatch):
    out = tmp_path / 'out'
    monkeypatch.setattr(sys, 'argv', ['builder', '--target', 'spark-gb10', '--source', str(tmp_path),
        '--commit', 'a'*40, '--tag', 'factory/strata:test', '--out', str(out),
        '--dependency', str(tmp_path), '--dependency-commit', 'b'*40])
    monkeypatch.setattr(spark_engine.platform, 'machine', lambda: 'x86_64')
    def forbidden(*args, **kwargs):
        pytest.fail('Rejected architecture must not run a command')
    monkeypatch.setattr(spark_engine.subprocess, 'run', forbidden)
    with pytest.raises(ValueError, match='native ARM64'):
        spark_engine.main()
    record = json.loads((out/'build-record.json').read_text())
    assert record['status'] == 'failed'
    assert record['host_architecture'] == 'x86_64'
    assert record['phase_seconds'] == {}
    assert record['build_wall_seconds'] >= 0


def test_native_compile_script_has_valid_python():
    compile(spark_engine.NATIVE_COMPILE, '<native-compile>', 'exec')


def test_llama_target_uses_embedded_ggml_and_server_binary(tmp_path):
    flags=spark_engine.build_flags('llama-server',tmp_path)
    assert '-DGGML_CUDA=ON' in flags
    assert '-DLLAMA_BUILD_SERVER=ON' in flags
    assert '-DLLAMA_BUILD_UI=OFF' in flags
    assert '-DLLAMA_USE_PREBUILT_UI=OFF' in flags
    assert not any('STRATA' in value for value in flags)
    assert any('STRATA_GGML_DIR' in value for value in spark_engine.build_flags('strata-dsv41',tmp_path))
    assert "'bin/'+target if target=='llama-server'" in spark_engine.NATIVE_COMPILE


def test_image_build_flags_pin_the_revision_before_archiving(tmp_path):
    commit = 'a' * 40

    def run(phase, argv):
        assert phase == 'git-build-number'
        assert argv == ['git', '-C', tmp_path, 'rev-list', '--count', commit]
        return '1234'

    flags, build_number = spark_engine.image_build_flags(run, tmp_path, commit)
    assert flags == ['-DLLAMA_BUILD_NUMBER=1234', f'-DLLAMA_BUILD_COMMIT={commit}']
    assert build_number == 1234


@pytest.mark.parametrize('failure', [None, 'digest', 'revision', 'gpu', 'mount'])
def test_image_check_requires_the_exact_packaged_binary_and_gpu_free_container(tmp_path, monkeypatch, failure):
    commit, digest, image_id = 'a' * 40, 'b' * 64, 'sha256:' + 'c' * 64
    executable = '/opt/llamacpp/llama-server'
    driver = tmp_path / 'libcuda.so.1'
    driver.write_bytes(b'fake driver')
    driver_destination = '/run/factory-driver/libcuda.so.1'
    record = dict(image=dict(Id=image_id, Architecture='arm64',
                             Config=dict(Labels={**labels('spark-gb10'), 'factory.source': commit})),
                  source=dict(commit=commit), executable_sha256=digest)

    class Guard:
        name = 'factory-test-owner'
        labels = {'factory.lab.nonce': 'test'}

        def __init__(self, root, image, timeout_s):
            assert image == image_id and timeout_s == 30
            self.root = root

        def __enter__(self):
            self.root.mkdir()
            return self

        def __exit__(self, *exc):
            host = dict(Runtime='runc', NetworkMode='none', ReadonlyRootfs=True,
                        DeviceRequests=[{'Count': -1}] if failure == 'gpu' else [])
            mounts = [dict(Type='bind', Source=str(driver), Destination=driver_destination, RW=False)]
            if failure == 'mount':
                mounts.append(dict(Type='volume', Source='elsewhere', Destination='/models', RW=False))
            (self.root / 'inspect-final.json').write_text(json.dumps(dict(Image=image_id, HostConfig=host, Mounts=mounts)))
            (self.root / 'report.json').write_text(json.dumps(dict(container_removed=True)))

    def run(phase, argv, *, timeout=None):
        if phase == 'image-driver':
            assert argv == ['ldconfig', '-p']
            return f'libcuda.so.1 (libc6,AArch64) => {driver}'
        assert phase == 'image-check' and timeout == 30
        assert {'--network=none', '--pull=never', '--runtime=runc', '--read-only'} <= set(argv)
        assert not any(flag in argv for flag in ('--gpus', '--device', '--privileged', '--volume'))
        assert argv[argv.index('--mount') + 1] == f'type=bind,src={driver},dst={driver_destination},readonly'
        assert argv[argv.index('--name') + 1] == Guard.name
        assert argv[-6:] == ['/bin/sh', image_id, '-ec', '/usr/bin/sha256sum "$1"; exec "$1" --version',
                             'image-check', executable]
        reported_digest = 'd' * 64 if failure == 'digest' else digest
        reported_commit = 'e' * 40 if failure == 'revision' else commit
        return f'{reported_digest}  {executable}\nversion: 0.0.1234 (build 1234, commit {reported_commit})'

    monkeypatch.setattr('jiuwenswarm.factory.lab_lifecycle.OwnedContainerGuard', Guard)
    if failure:
        reason = {'digest': 'SHA-256', 'revision': 'version', 'gpu': 'isolation', 'mount': 'isolation'}[failure]
        with pytest.raises(ValueError, match=reason):
            spark_engine.verify_delivery_image(run, tmp_path, record, 1234)
    else:
        proof = spark_engine.verify_delivery_image(run, tmp_path, record, 1234)
        assert (proof['image_id'], proof['executable_sha256'], proof['source_commit']) == (image_id, digest, commit)
        assert proof['build_number'] == 1234 and proof['version'] == '0.0.1234'
        assert (proof['network'], proof['gpu_devices'], proof['model_mounts']) == ('none', [], [])
