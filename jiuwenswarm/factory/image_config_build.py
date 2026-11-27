"""Build an image configuration from an immutable local runtime image."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
from uuid import uuid4

from .evidence_digest import encoded
from .targets import validate_image


CONFIG_ENV = 'FACTORY_LAUNCH_CONFIG'
EXECUTABLE = '/opt/llamacpp/llama-server'
IMAGE_ID = r'sha256:[a-f0-9]{64}'


def normalize(request, approved):
    if set(request) - {'target', 'tag', 'deadline_s', 'config_image'}:
        raise ValueError('Unknown config image build fields')
    config = request['config_image']
    if not isinstance(config, dict) or set(config) != {'base_image_id', 'executable_sha256', 'launch_config'}:
        raise ValueError('Expected immutable base, executable and launch configuration')
    if config != approved:
        raise ValueError('Config image request differs from the task-owned approval')
    if not re.fullmatch(IMAGE_ID, config['base_image_id']) or not re.fullmatch(r'[a-f0-9]{64}', config['executable_sha256']):
        raise ValueError('Invalid base image or binary digest')
    launch = config['launch_config']
    if (set(launch) != {'format', 'args', 'request'} or launch['format'] != 'factory.r9-launch/1'
            or launch['request'] != {'cache_prompt': True} or launch['request']['cache_prompt'] is not True
            or not isinstance(launch['args'], list) or not 1 <= len(launch['args']) <= 128
            or not all(isinstance(arg, str) and re.fullmatch(r'[A-Za-z0-9._:=,/-]{1,128}', arg) for arg in launch['args'])):
        raise ValueError('Invalid config image launch arguments or request settings')
    if request.get('target') != 'spark-gb10' or not re.fullmatch(r'factory/llamacpp:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}', request.get('tag', '')):
        raise ValueError('Config image must use the Spark factory/llamacpp namespace')
    deadline = request.get('deadline_s', 300)
    if type(deadline) is not int or not 1 <= deadline <= 600:
        raise ValueError('Config image deadline must be 1..600 seconds')
    env = {'PATH': os.environ.get('PATH', os.defpath)}
    return dict(request, verify_image=True, mode='config_image', deadline_s=deadline, env=env,
                engine_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def docker(args, log, *, allow_missing=False):
    argv = ['docker', *args]
    if prefix := os.environ.get('DOCKER_CMD_PREFIX'):
        argv = shlex.split(prefix) + [shlex.join(argv)]
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=90)
    with log.open('a') as output:
        output.write(shlex.join(['docker', *args]) + '\n')
        output.write(result.stderr)
    if allow_missing and result.returncode and ('No such image' in result.stderr or 'No such object' in result.stderr or 'No such container' in result.stderr):
        return None
    if result.returncode:
        raise ValueError(f'Docker {args[0]} failed (exit {result.returncode}): {result.stderr.strip()[-400:]}')
    return result.stdout.strip()


def inspect(image, log, *, allow_missing=False):
    result = docker(['image', 'inspect', image], log, allow_missing=allow_missing)
    if result is None:
        return None
    inspected, = json.loads(result)
    return inspected


def scratch_container(image_id, name, log):
    docker(['container', 'create', '--pull=never', '--network=none', '--read-only',
            '--runtime=runc', '--name', name, image_id], log)


def verify_config(base, image, config, image_id):
    validate_image('spark-gb10', image)
    base_config = base['Config']
    env = CONFIG_ENV + '=' + encoded(config).decode()
    if (base_config['Entrypoint'] != [EXECUTABLE] or base['Id'] == image_id or image['Id'] != image_id
            or image['RootFS'] != base['RootFS']
            or image['Config'] != dict(base_config, Cmd=config['args'], Env=[*base_config['Env'], env])):
        raise ValueError('Derivative image changed properties outside the approved configuration')


def build(request, out, log):
    """Apply ENV and CMD to an unstarted snapshot of the local AQB image."""
    out.mkdir()
    approved = request['config_image']
    config = approved['launch_config']
    base_id = approved['base_image_id']
    base = inspect(base_id, log)
    validate_image('spark-gb10', base)
    if base['Id'] != base_id or not re.fullmatch(IMAGE_ID, base_id):
        raise ValueError('Local image does not match the approved immutable base')
    if any(item.startswith(CONFIG_ENV + '=') for item in base['Config']['Env']):
        raise ValueError('Base already contains a factory launch configuration')

    tag = request['tag']
    image = inspect(tag, log, allow_missing=True)
    if image is None:
        name = 'factory-config-' + uuid4().hex
        try:
            scratch_container(base_id, name, log)
            env = CONFIG_ENV + '=' + shlex.quote(encoded(config).decode())
            cmd = 'CMD ' + json.dumps(config['args'])
            image_id = docker(['container', 'commit', '--change', 'ENV ' + env, '--change', cmd, name], log)
        finally:
            docker(['container', 'rm', name], log, allow_missing=True)
        image = inspect(image_id, log)
    else:
        image_id = image['Id']
    if not re.fullmatch(IMAGE_ID, image_id):
        raise ValueError('Docker did not produce an immutable image ID')
    verify_config(base, image, config, image_id)

    name = 'factory-config-check-' + uuid4().hex
    extracted = out / 'llama-server'
    try:
        scratch_container(image_id, name, log)
        docker(['container', 'cp', name + ':' + EXECUTABLE, str(extracted)], log)
        with extracted.open('rb') as stream:
            executable_sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    finally:
        extracted.unlink(missing_ok=True)
        docker(['container', 'rm', name], log, allow_missing=True)
    if executable_sha != approved['executable_sha256']:
        raise ValueError('Derivative image executable differs from AQB')
    docker(['image', 'tag', image_id, tag], log)
    if inspect(tag, log)['Id'] != image_id:
        raise ValueError('Derivative image tag does not resolve to the checked image')

    source_commit = base['Config']['Labels']['factory.source']
    check = dict(format='factory.config-image-check/1', status='passed', image_id=image_id,
                 base_image_id=base_id, source_commit=source_commit, executable=EXECUTABLE,
                 executable_sha256=executable_sha, launch_config_sha256=hashlib.sha256(encoded(config)).hexdigest(),
                 network='none', gpu_devices=[], model_mounts=[], container_started=False)
    inspect_fields = ('Id', 'RootFS', 'Config')
    return dict(status='success', mode='config_image', target='spark-gb10', executable_sha256=executable_sha,
                image_check=check, base_image_id=base_id, source=dict(commit=source_commit),
                base_image={key: base[key] for key in inspect_fields}, image={key: image[key] for key in inspect_fields})
