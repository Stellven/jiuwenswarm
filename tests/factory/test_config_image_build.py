"""Test the configuration-only Builder path without starting a container."""
import hashlib
import json
from pathlib import Path

import pytest

from jiuwenswarm.factory import image_config_build
from jiuwenswarm.factory.evidence_digest import encoded
from jiuwenswarm.factory.targets import labels


def test_config_image_build_checks_binary_config_and_filesystem(tmp_path, monkeypatch):
    base_id = 'sha256:' + 'a' * 64
    image_id = 'sha256:' + 'b' * 64
    binary = b'fixture executable'
    launch = dict(format='factory.r9-launch/1', args=['--swa-full', '--ctx-checkpoints', '32'],
                  request={'cache_prompt': True})
    approved = dict(base_image_id=base_id, executable_sha256=hashlib.sha256(binary).hexdigest(), launch_config=launch)
    request = dict(target='spark-gb10', tag='factory/llamacpp:config-only-fixture', config_image=approved)
    normalized = image_config_build.normalize(request, approved)
    base = dict(Id=base_id, Architecture='arm64', RootFS={'Layers': ['base-layer']}, Config={
        'Entrypoint': [image_config_build.EXECUTABLE], 'Env': ['PATH=/bin'],
        'Labels': dict(labels('spark-gb10'), **{'factory.source': 'a' * 40}),
    })
    config_env = 'FACTORY_LAUNCH_CONFIG=' + encoded(launch).decode()
    child = dict(base, Id=image_id, Config=dict(base['Config'], Cmd=launch['args'], Env=['PATH=/bin', config_env]))
    commands = []
    tags = {base_id: base, image_id: child}

    def docker(args, log, allow_missing=False):
        commands.append(args)
        if args[:2] == ['image', 'inspect']:
            if allow_missing and args[2] not in tags:
                return None
            return json.dumps([tags[args[2]]])
        if args[:2] == ['image', 'tag']:
            tags[args[-1]] = child
        if args[:2] == ['container', 'commit']:
            assert args[2:4] == ['--change', "ENV FACTORY_LAUNCH_CONFIG='" + encoded(launch).decode() + "'"]
            assert args[4:6] == ['--change', 'CMD ' + json.dumps(launch['args'])]
            return image_id
        if args[:2] == ['container', 'cp']:
            Path(args[-1]).write_bytes(binary)

    monkeypatch.setattr(image_config_build, 'docker', docker)
    record = image_config_build.build(normalized, tmp_path / 'out', tmp_path / 'docker.log')
    assert record['image']['Id'] == image_id
    assert record['image']['RootFS'] == record['base_image']['RootFS']
    assert record['image_check']['executable_sha256'] == approved['executable_sha256']
    assert record['image_check']['container_started'] is False
    assert [argv[-1] for argv in commands if argv[:2] == ['container', 'create']] == [base_id, image_id]
    assert all('run' not in argv and 'start' not in argv for argv in commands)
    child['RootFS'] = {'Layers': ['base-layer', 'unapproved-layer']}
    with pytest.raises(ValueError, match='outside the approved configuration'):
        image_config_build.build(normalized, tmp_path / 'bad', tmp_path / 'docker.log')
    with pytest.raises(ValueError, match='task-owned approval'):
        image_config_build.normalize(dict(request, config_image=dict(approved, base_image_id=image_id)), approved)
