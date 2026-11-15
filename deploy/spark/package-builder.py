"""Seal the existing native ARM64 compiler into an owned offline build context."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

PACKAGES = ['gcc-13', 'g++-13', 'gcc-13-aarch64-linux-gnu', 'g++-13-aarch64-linux-gnu',
            'cpp-13', 'cpp-13-aarch64-linux-gnu', 'binutils', 'binutils-aarch64-linux-gnu',
            'libc6-dev', 'linux-libc-dev', 'libgcc-13-dev', 'libstdc++-13-dev', 'git']


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--cmake-data', type=Path, required=True)
    p.add_argument('--ninja', type=Path, required=True)
    p.add_argument('--cuda', type=Path, default=Path('/usr/local/cuda-13.0'))
    a = p.parse_args()
    if os.uname().machine != 'aarch64' or a.output.exists():
        raise ValueError('A new ARM64 build context is required')
    a.output.mkdir(parents=True)
    system = a.output / 'system'
    candidates = set()
    versions = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}=${Version}\n', *PACKAGES], text=True)
    for package in PACKAGES:
        for value in subprocess.check_output(['dpkg-query', '-L', package], text=True).splitlines():
            path = Path(value)
            if path.is_file() and not str(path).startswith('/usr/share/'):
                candidates.add(path)
    for executable in list(candidates) + [a.ninja, a.cmake_data / 'bin/cmake',
                                          a.cuda / 'bin/nvcc', a.cuda / 'nvvm/bin/cicc']:
        if not executable.is_file() or not os.access(executable, os.X_OK):
            continue
        result = subprocess.run(['ldd', str(executable)], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            value = parts[2] if '=>' in parts and len(parts) > 2 else parts[0] if parts else ''
            if value.startswith('/') and Path(value).is_file():
                candidates.add(Path(value))
    for path in sorted(candidates):
        relative = path.relative_to('/')
        if relative.parts[0] == 'lib':
            relative = Path('usr') / relative
        destination = system / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    shutil.copytree(a.cuda, system / a.cuda.relative_to('/'), symlinks=True,
                    ignore=shutil.ignore_patterns('doc', 'docs', 'DOCS', 'compute-sanitizer', 'nsight*'))
    shutil.copytree(a.cmake_data, a.output / 'cmake', symlinks=True)
    (a.output / 'bin').mkdir()
    shutil.copy2(a.ninja, a.output / 'bin/ninja')
    manifest = dict(architecture='aarch64', packages=versions.splitlines(),
                    cuda_root=str(a.cuda), versions={
                        'nvcc': subprocess.check_output([str(a.cuda / 'bin/nvcc'), '--version'], text=True),
                        'cmake': subprocess.check_output([str(a.cmake_data / 'bin/cmake'), '--version'], text=True),
                        'ninja': subprocess.check_output([str(a.ninja), '--version'], text=True)}, files={})
    for path in sorted(a.output.rglob('*')):
        if path.is_file():
            with path.open('rb') as stream:
                manifest['files'][str(path.relative_to(a.output))] = hashlib.file_digest(stream, 'sha256').hexdigest()
    (a.output / 'toolchain.json').write_text(json.dumps(manifest, indent=2) + '\n')
    shutil.copy2(Path(__file__).with_name('Builder.Dockerfile'), a.output / 'Dockerfile')
    print(json.dumps(dict(packages=len(PACKAGES), files=len(manifest['files']), output=str(a.output))))


if __name__ == '__main__':
    main()
