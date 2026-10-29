"""Package a committed AI4Research source release, preserving pinned checkout bytes.

Uses Git objects only: local credentials, builds and working files cannot enter
the bundle. Explicit .gitattributes EOL rules are applied because research assets
hash checkout bytes, whereas plain `git archive` exports normalized Git blobs.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def git(*args: str, input: bytes | None = None) -> bytes:
    return subprocess.check_output(['git', *args], cwd=ROOT, input=input)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref', default='HEAD')
    parser.add_argument('--name', default='AI4Research-M1')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', args.name):
        parser.error('name must be a portable filename')
    commit = git('rev-parse', '--verify', f'{args.ref}^{{commit}}').decode().strip()
    epoch = int(git('show', '-s', '--format=%ct', commit))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    notes = git('show', f'{commit}:releases/AI4Research-M1.md')
    paths = git('ls-tree', '-r', '--name-only', '-z', commit)
    attributes = git('check-attr', f'--source={commit}', '-z', '--stdin', 'eol', 'text', input=paths).split(b'\0')
    attrs: dict[str, dict[str, str]] = {}
    for i in range(0, len(attributes) - 1, 3):
        attrs.setdefault(attributes[i].decode(), {})[attributes[i + 1].decode()] = attributes[i + 2].decode()
    date = dt.datetime.fromtimestamp(max(epoch, 315532800), dt.timezone.utc)
    inventory = []
    lfs = []
    excluded = []
    zip_path = output / f'{args.name}.zip'
    tgz_path = output / f'{args.name}.tar.gz'
    with tempfile.TemporaryFile() as raw:
        subprocess.run(['git', 'archive', '--format=tar', commit], cwd=ROOT, stdout=raw, check=True)
        raw.seek(0)
        with (tarfile.open(fileobj=raw, mode='r|') as source,
              tgz_path.open('xb') as compressed,
              gzip.GzipFile(filename='', mode='wb', fileobj=compressed, mtime=epoch) as gz,
              tarfile.open(fileobj=gz, mode='w|', format=tarfile.PAX_FORMAT) as target,
              zipfile.ZipFile(zip_path, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf):
            for member in source:
                relative = member.name.rstrip('/')
                parts = Path(relative).parts
                if (relative == 'benchmarks/output' or relative.startswith('benchmarks/output/')
                        or parts and parts[0] == 'benchmarks' and 'internal' in parts):
                    if member.isfile() or member.issym():
                        excluded.append(relative)
                    continue
                member.name = f'{args.name}/{relative}'
                member.pax_headers = {}
                member.uid = member.gid = 0
                member.uname = member.gname = ''
                member.mtime = epoch
                zi = zipfile.ZipInfo(member.name + ('/' if member.isdir() else ''), date.timetuple()[:6])
                zi.create_system = 3
                zi.external_attr = ((0o120000 if member.issym() else 0o040000 if member.isdir() else 0o100000)
                                    | member.mode) << 16
                zi.compress_type = zipfile.ZIP_DEFLATED
                if member.isdir():
                    target.addfile(member)
                    zf.writestr(zi, b'')
                    continue
                if member.issym():
                    target.addfile(member)
                    zf.writestr(zi, member.linkname.encode())
                    inventory.append({'path': relative, 'symlink': member.linkname})
                    continue
                if not member.isfile():
                    raise ValueError(f'Unsupported Git archive entry: {relative}')
                stream = source.extractfile(member)
                assert stream is not None
                data = stream.read()
                rules = attrs.get(relative, {})
                # Explicit -text overrides inherited eol, including frozen
                # architecture inputs whose raw bytes must never be rewritten.
                normalize = rules.get('text') != 'unset' and (
                    rules.get('text') != 'auto' or b'\0' not in data[:8000])
                if normalize and rules.get('eol') == 'crlf':
                    data = data.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')
                elif normalize and rules.get('eol') == 'lf':
                    data = data.replace(b'\r\n', b'\n')
                if data.startswith(b'version https://git-lfs.github.com/spec/v1\n') or data.startswith(
                        b'version https://git-lfs.github.com/spec/v1\r\n'):
                    lfs.append(relative)
                member.size = len(data)
                target.addfile(member, io.BytesIO(data))
                zf.writestr(zi, data)
                inventory.append({'path': relative, 'bytes': len(data),
                                  'sha256': hashlib.sha256(data).hexdigest()})
    (output / 'RELEASE_NOTES.md').write_bytes(notes)
    manifest = {'schema': 'ai4r-source-release:1', 'name': args.name, 'commit': commit,
                'tree': git('rev-parse', f'{commit}^{{tree}}').decode().strip(),
                'parents': git('show', '-s', '--format=%P', commit).decode().split(),
                'distribution': 'source; build Docker images using deploy/m1/OPERATIONS.md',
                'checkout_bytes': 'explicit Git eol attributes applied; executable bits and symlinks preserved',
                'exclusions': ['benchmarks/output/', 'benchmarks/**/internal/'],
                'excluded_tracked_files': excluded,
                'lfs_pointer_files': lfs, 'files': inventory}
    (output / 'release-manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    sums = []
    for path in sorted(output.iterdir()):
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        sums.append(f'{digest}  {path.name}\n')
    (output / 'SHA256SUMS').write_text(''.join(sums), encoding='ascii')
    print(json.dumps({'commit': commit, 'output': str(output), 'files': len(inventory),
                      'lfs_pointer_files': lfs}, ensure_ascii=False))


if __name__ == '__main__':
    main()
