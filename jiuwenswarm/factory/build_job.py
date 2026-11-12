"""Builder worker. Invoke only as a durable jobq command."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import uuid
import shutil
import subprocess
import sys
import time

from .config import ENGINE, RECIPE, BUILD_MIN_AVAIL_MIB, TOOL_TIMEOUT
from .jobs import metadata
from .store import Store


class PreparationError(Exception):
    def __init__(self, error):
        self.error = error
        super().__init__(error['code'])


def command(argv, *, required=True):
    actual = argv
    if argv[0] == 'docker' and os.environ.get('DOCKER_CMD_PREFIX'):
        actual = shlex.split(os.environ['DOCKER_CMD_PREFIX']) + [shlex.join(argv)]
    try:
        process = subprocess.run(actual, stdin=subprocess.DEVNULL, capture_output=True,
                                 text=True, timeout=TOOL_TIMEOUT)
    except (OSError, subprocess.TimeoutExpired) as exc:
        if required:
            raise PreparationError(dict(code='TOOLCHAIN_MISSING', tool=argv[0] if argv[0] != 'docker' else 'docker buildx',
                                        path=os.environ.get('PATH', ''))) from exc
        return dict(available=False, detail=type(exc).__name__)
    if process.returncode and required:
        raise PreparationError(dict(code='TOOLCHAIN_MISSING', tool=argv[0] if argv[0] != 'docker' else 'docker buildx',
                                    path=os.environ.get('PATH', ''), rc=process.returncode))
    return dict(available=process.returncode == 0, rc=process.returncode,
                stdout=process.stdout[-65536:], stderr=process.stderr[-65536:])


def prepare(root, prep):
    prep['toolchain'] = {}
    for tool in ('nvcc', 'gcc', 'cmake', 'ninja', 'docker'):
        location = shutil.which(tool)
        if not location:
            raise PreparationError(dict(code='TOOLCHAIN_MISSING', tool=tool,
                                        path=os.environ.get('PATH', '')))
        args = [tool, 'buildx', 'version'] if tool == 'docker' else [tool, '--version']
        prep['toolchain'][tool] = dict(path=location, **command(args))
    release = Path('/etc/nv_tegra_release')
    prep['nv_tegra_release'] = release.read_text() if release.exists() else None
    prep['nvidia-jetpack'] = command(['dpkg-query', '-W', '-f=${Version}', 'nvidia-jetpack'], required=False)
    prep['disk_free_bytes'] = shutil.disk_usage(root).free
    if prep['disk_free_bytes'] < BUILD_MIN_AVAIL_MIB * 1024 ** 2:
        raise PreparationError(dict(code='DISK_SPACE_LOW', free_bytes=prep['disk_free_bytes'], required_bytes=BUILD_MIN_AVAIL_MIB * 1024 ** 2))
    prep['ccache'] = command(['ccache', '-s', '-v'], required=False)
    match = re.search(r'^ARG BASE_RUNTIME=(\S+)', RECIPE.read_text(), re.M)
    reference = os.environ.get('BASE_RUNTIME') or (match.group(1) if match else '')
    if not re.fullmatch(r'nvcr.io/nvidia/l4t-cuda:12\.6\.11-runtime@sha256:[0-9a-f]{64}', reference):
        raise PreparationError(dict(code='BASE_IMAGE_NOT_PINNED'))
    inspected = command(['docker', 'image', 'inspect', reference], required=False)
    prep['base_images'] = {'runtime': {'reference': reference, 'cache_hit': inspected['available']}}
    prep['cache_hit'] = inspected['available']
    if not inspected['available']:
        pulled = command(['docker', 'pull', reference], required=False)
        if not pulled['available']:
            raise PreparationError(dict(code='BASE_IMAGE_PULL_FAILED', reference=reference, detail=pulled))
    prep['status'] = 'success'


def tail(path):
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 65536))
        return stream.read().decode('utf-8', errors='replace')


def prune_intermediates(out):
    """After a successful build the image lives in Docker; drop the staged tree and the
    image archive (~1.9 GiB together) so a multi-build task cannot exhaust the disk.
    The archive sha256 is kept in the build observation. FACTORY_KEEP_BUILD_INTERMEDIATES=1 opts out."""
    if os.environ.get('FACTORY_KEEP_BUILD_INTERMEDIATES') == '1':
        return {}
    pruned = {}
    archive = out / 'engine-image.docker.tar'
    if archive.is_file():
        digest = hashlib.sha256()
        with archive.open('rb') as stream:
            for block in iter(lambda: stream.read(1 << 20), b''):
                digest.update(block)
        pruned['engine-image.docker.tar'] = dict(sha256=digest.hexdigest(), bytes=archive.stat().st_size)
        archive.unlink()
    if (out / 'build').is_dir():
        shutil.rmtree(out / 'build', ignore_errors=True)
        pruned['build/'] = 'staged source tree'
    return pruned


def run(store, task_id, attempt_id, request):
    attempt = store.read(task_id, attempt_id)
    if attempt['request'] != request:
        raise ValueError('Worker request differs from persisted identity')
    root = store.home / 'builds' / attempt_id
    if root.exists() and any(root.iterdir()):
        root = root.with_name(root.name + '-' + uuid.uuid4().hex)
    out = root / 'engine'  # Must not exist when build_engine is started.
    stdout, stderr = root / 'stdout.log', root / 'stderr.log'
    prep = dict(status='failed', request_fingerprint=attempt['fingerprint'], cache_hit=None)
    record = {}
    error = {}
    rc = 1
    started = time.monotonic()
    def stop(signum, frame):
        raise SystemExit(128 + signum)
    previous = signal.signal(signal.SIGTERM, stop)
    try:
        root.mkdir(parents=True, exist_ok=True)
        stdout.touch()
        stderr.touch()
        engine = Path(os.environ.get('FACTORY_BUILD_ENGINE', ENGINE)).resolve()
        for path, expected in ((engine, request['engine_sha256']), (RECIPE, request['recipe_sha256'])):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise PreparationError(dict(code='INPUT_CHANGED', path=str(path)))
        if request.get('patch') and hashlib.sha256(Path(request['patch']).read_bytes()).hexdigest() != request['patch_sha256']:
            raise PreparationError(dict(code='INPUT_CHANGED', path=request['patch']))
        prepare(root, prep)
        # Persist preparation before compilation, including on abrupt termination.
        (root / 'prep.json').write_text(json.dumps(prep, indent=2) + '\n')
        argv = [sys.executable, str(engine), '--target', 'jetson-orin',
                '--source', request['source']['path'], '--commit', request['source']['commit'],
                '--tag', request['tag'], '--out', str(out)]
        if request.get('patch'):
            argv += ['--patch', request['patch']]
        with stdout.open('wb') as output, stderr.open('wb') as errors:
            rc = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=output, stderr=errors).returncode
        if (out / 'build-record.json').exists():
            record = json.loads((out / 'build-record.json').read_text())
        if rc == 0 and (record.get('status') != 'success' or not (record.get('image') or {}).get('Id')):
            rc = 1
            error = dict(code='BUILD_RECORD_INVALID')
    except PreparationError as exc:
        error = exc.error
        prep.update(status='failed', error=error)
    except (OSError, ValueError, KeyError) as exc:
        error = dict(code='BUILD_WORKER_ERROR', detail=str(exc))
    finally:
        signal.signal(signal.SIGTERM, previous)
        refs = []
        def artifact(name, data, media='application/json'):
            item = store.put_artifact(task_id, attempt_id + ':' + name, data, media, attempt_id)
            refs.append(item['artifact_id'])
            return {'artifact_id': item['artifact_id'], 'sha256': item['sha256']}
        prep_data = (json.dumps(prep, indent=2) + '\n').encode()
        if root.is_dir():
            (root / 'prep.json').write_bytes(prep_data)
        request_ref = artifact('request', json.dumps(dict(fingerprint=attempt['fingerprint'], request=request), sort_keys=True).encode())
        prep_ref = artifact('prep', prep_data)
        record_ref = None
        if (out / 'build-record.json').exists():
            record_ref = artifact('build-record', out / 'build-record.json')
        for name, path in (('stdout', stdout), ('stderr', stderr)):
            artifact(name, path if path.is_file() else b'', 'text/plain')
            artifact(name + '-tail', tail(path).encode() if path.is_file() else b'', 'text/plain')
        image_id = (record.get('image') or {}).get('Id')
        receipt = dict(request_fingerprint=attempt['fingerprint'], request=request_ref,
                       prep=prep_ref, build_record=record_ref, image_id=image_id)
        artifact('receipt', json.dumps(receipt, sort_keys=True).encode())
        pruned = prune_intermediates(out) if rc == 0 and image_id else {}
        values = dict(pruned_intermediates=pruned,status='success' if rc == 0 else 'failed',
            failure_stage=record.get('failure_stage') or (None if rc == 0 else 'prep' if prep['status'] != 'success' else 'build'),
            image_id=image_id, tag=request['tag'], source_commit=request['source']['commit'],
            source_tree=record.get('source', {}).get('tree', request['source']['tree']),
            patch_sha256=record.get('patch_sha256', request.get('patch_sha256')),
            toolchain=record.get('toolchain', prep.get('toolchain', {})),
            base_images=record.get('base_images', prep.get('base_images', {})),
            build_wall_seconds=record.get('build_wall_seconds', time.monotonic() - started),
            cache_hit=prep.get('cache_hit'))
        observation = store.append_observation(task_id, dict(obs_id=attempt_id + ':build-result',
            kind='build_result', values=values, error=error, source_artifacts=list(refs),
            host_run=dict(attempt_id=attempt_id, jobq_id=os.environ.get('JOBQ_JOB_ID'), receipt=receipt)))
        refs.append(observation['obs_id'])
        metadata(store, attempt, result_refs=refs)
    return 0 if rc == 0 else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--request', required=True, type=Path)
    args = parser.parse_args()
    with Store(Path(os.environ['FACTORY_HOME'])) as store:
        return run(store, args.task, args.attempt, json.loads(args.request.read_text()))


if __name__ == '__main__':
    raise SystemExit(main())
