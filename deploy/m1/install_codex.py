"""Install the pinned native CLI into the sandbox's immutable runtime closure.

Build-time only: no login, download, model request or runtime package discovery.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import uuid


def install_packaged_codex(destination: Path, receipt: Path):
    from codex_cli_bin import bundled_codex_path

    if importlib.metadata.version('openai-codex-cli-bin') != '0.163.0':
        raise ValueError('PINNED_CODEX_PACKAGE_REQUIRED')
    source = Path(bundled_codex_path())
    metadata = source.lstat()
    if source.is_symlink() or not stat.S_ISREG(metadata.st_mode):
        raise ValueError('NATIVE_CODEX_BINARY_REQUIRED')
    destination, receipt = Path(destination), Path(receipt)
    if (destination.exists() or destination.is_symlink() or receipt.exists() or receipt.is_symlink()
            or any(p.is_symlink() for p in (*destination.parents, *receipt.parents))):
        raise ValueError('NEW_IMMUTABLE_CODEX_DESTINATION_REQUIRED')
    temporary = destination.with_name('.codex-' + uuid.uuid4().hex)
    digest = hashlib.sha256()
    try:
        with source.open('rb') as original, temporary.open('xb') as stream:
            if original.read(4) != b'\x7fELF':
                raise ValueError('NATIVE_CODEX_BINARY_REQUIRED')
            original.seek(0)
            while chunk := original.read(1024 * 1024):
                stream.write(chunk)
                digest.update(chunk)
            after = os.fstat(original.fileno())
            if (original.tell() != metadata.st_size
                    or (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
                    != (metadata.st_dev, metadata.st_ino, metadata.st_size, metadata.st_mtime_ns)):
                raise ValueError('PACKAGED_CODEX_CHANGED_DURING_INSTALL')
            stream.flush()
            os.fsync(stream.fileno())
            os.fchmod(stream.fileno(), 0o555)
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    observed = subprocess.run([str(destination), '--version'], capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=10, check=False)
    if observed.returncode or observed.stdout.strip() != b'codex-cli 0.163.0':
        raise ValueError('PINNED_NATIVE_CODEX_EXECUTION_REQUIRED')
    value = {'schema': 'ai4r-packaged-codex:1', 'package_version': '0.163.0',
             'executable': str(destination), 'bytes': metadata.st_size,
             'sha256': digest.hexdigest(), 'mode': '0555',
             'version': observed.stdout.decode('utf-8').strip(),
             'model_access': 'NOT_RUN', 'tool_confinement': 'NOT_RUN'}
    with receipt.open('x', encoding='utf-8') as stream:
        stream.write(json.dumps(value, sort_keys=True, indent=2) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return value


if __name__ == '__main__':
    install_packaged_codex(Path('/usr/local/bin/codex'),
                          Path('/usr/local/share/ai4r-codex-runtime.json'))
