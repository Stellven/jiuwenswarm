"""Freeze public source and build a bounded clean image using cached dependencies.

Creates a new receipt directory only. It never modifies running containers,
volumes, external case stores, registry credentials, or the selected base tag.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
from pathlib import Path
import subprocess
import tarfile


def docker_prefix():
    if os.environ.get('AI4R_WSL_DISTRO'):
        return ['wsl', '-d', os.environ['AI4R_WSL_DISTRO'], '-u', 'root', '--exec', 'docker']
    return ['docker']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('role', choices=['ai4r', 'benchmark-runner'])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--dependency-image', required=True)
    parser.add_argument('--expected-dependency-id', required=True)
    parser.add_argument('--platform', choices=('linux/amd64', 'linux/arm64'),
                        default='linux/arm64' if platform.machine().lower() in {'arm64', 'aarch64'} else 'linux/amd64')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    docker = docker_prefix()
    observed = subprocess.check_output(docker + ['image', 'inspect', args.dependency_image, '--format', '{{.Id}}'], text=True).strip()
    if observed != args.expected_dependency_id:
        raise ValueError('DEPENDENCY_IMAGE_CHANGED')
    # A fresh unique output tag prevents accidentally replacing an existing pin.
    exists = subprocess.run(docker + ['image', 'inspect', args.tag], capture_output=True)
    if exists.returncode == 0:
        raise ValueError('OUTPUT_IMAGE_TAG_ALREADY_EXISTS')
    app = args.role == 'ai4r'
    roots = ['pyproject.toml', 'uv.lock', 'LICENSE', 'OPEN_SOURCE_SOFTWARE_NOTICE.md',
             'jiuwenswarm', 'jiuwenbox', 'packages/jiuwenswarm-tui', 'scripts', 'deploy/m1'] if app else [
             'uv.lock', 'jiuwenswarm/research_sidecar', 'jiuwenswarm/research_records',
             'jiuwenswarm/research_contracts', 'deploy/m1']
    denied = {'.git', '__pycache__', 'node_modules', 'dist', '.venv', 'private', 'protected', 'evidence'}
    inventory = []
    paths = set()
    for name in roots:
        start = root / name
        if start.is_file():
            paths.add(start)
            continue
        for parent, dirs, files in os.walk(start):
            dirs[:] = [n for n in dirs if n not in denied and not (app and n == 'research_sidecar')]
            for filename in files:
                path = Path(parent) / filename
                if (filename in {'auth.json', 'credentials.json', 'secrets.json', '.env'}
                        or filename.startswith('.env.') and filename != '.env.template'
                        or path.suffix in {'.key', '.pem', '.p12', '.pyc'}):
                    continue
                paths.add(path)
    if app:
        generated = root / 'jiuwenswarm/channels/web/frontend/dist'
        if not (generated / 'index.html').is_file():
            raise ValueError('CURRENT_BUILT_FRONTEND_REQUIRED')
        paths.update(path for path in generated.rglob('*') if path.is_file()
                     and path.name not in {'auth.json', 'credentials.json', 'secrets.json', '.env'}
                     and not path.name.startswith('.env.')
                     and path.suffix not in {'.key', '.pem', '.p12', '.pyc'}
                     and not set(path.relative_to(generated).parts).intersection(denied))
    context = output / 'context.tar'
    with tarfile.open(context, 'x') as archive:
        for path in sorted(paths):
            if path.is_symlink() or not path.is_file():
                raise ValueError('PUBLIC_CONTEXT_NONREGULAR_FILE')
            raw = path.read_bytes()
            relative = path.relative_to(root).as_posix()
            inventory.append({'path': relative, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
            info = tarfile.TarInfo(relative)
            info.size, info.mode, info.mtime = len(raw), 0o644, 0
            archive.addfile(info, io.BytesIO(raw))
    dockerfile = 'deploy/m1/Dockerfile.app-cached' if app else 'deploy/m1/Dockerfile.runner-cached'
    command = docker + ['build', '--platform', args.platform, '--file', dockerfile,
                        '--target', 'production' if app else 'benchmark-runner',
                        '--build-arg', 'DEPENDENCY_IMAGE=' + args.dependency_image,
                        '--build-arg', 'DEPENDENCY_IMAGE_ID=' + observed,
                        '--tag', args.tag, '--progress', 'plain', '-']
    receipt = {'schema': 'ai4r-two-image-build:1', 'role': args.role, 'tag': args.tag,
               'dependency_image_id': observed, 'files': inventory,
               'context_sha256': hashlib.sha256(context.read_bytes()).hexdigest(),
               'context_bytes': context.stat().st_size, 'command': command}
    (output / 'source.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('role', 'tag', 'context_bytes', 'context_sha256')}), flush=True)
    with context.open('rb') as source, (output / 'build.log').open('xb') as log:
        result = subprocess.run(command, stdin=source, stdout=log, stderr=subprocess.STDOUT)
    receipt['returncode'] = result.returncode
    if not result.returncode:
        receipt['image_id'] = subprocess.check_output(docker + ['image', 'inspect', args.tag, '--format', '{{.Id}}'], text=True).strip()
    (output / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({key: receipt[key] for key in ('role', 'tag', 'returncode', 'image_id') if key in receipt}))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
