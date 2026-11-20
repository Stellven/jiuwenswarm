"""Cut a recorded release for factory CCs whose files changed after their pinned release.

The catalog pins each capsule to the release digest recorded in ``factory/ccs/*migration.json``.
When a capsule's files change, its ``cc.yaml`` version must be bumped and the new release must be
recorded, otherwise the catalog reports a digest mismatch.  This script seals the current capsule
with the CC-v2 host (``Host.seal``), walks Git history to find the commit and version of the pinned
release, and writes ``<name>-migration.json`` with ``from_release`` -> ``to_release``.

    python scripts/factory/reseal_capsules.py --name factory-worker-reseal \
        --reason "..." builder lab_client
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import yaml

from jiuwenswarm.ccv2.ccv2 import IGNORED, Host, load, release_manifest_bytes, tree_files
from jiuwenswarm.gateway.channel_manager.web.capsule_catalog import CCS, CapsuleCatalog

REPO = CCS.parents[2]


def git(*args, binary=False):
    result = subprocess.run(['git', '-C', str(REPO), *args], capture_output=True, check=True)
    return result.stdout if binary else result.stdout.decode()


def committed_release(commit, directory):
    """Release digest and version of a capsule directory exactly as committed."""
    prefix = (CCS / directory).relative_to(REPO).as_posix() + '/'
    rows, declaration, files = [], None, {}
    for line in git('ls-tree', '-r', '-l', commit, '--', prefix).splitlines():
        meta, path = line.split('\t', 1)
        relative = path[len(prefix):]
        if any(part in IGNORED for part in relative.split('/')):
            continue
        data = git('cat-file', 'blob', meta.split()[2], binary=True)
        files[relative] = hashlib.sha256(data).hexdigest()
        rows.append(dict(path=relative, sha256=files[relative], size=len(data)))
        if relative == 'cc.yaml':
            with tempfile.TemporaryDirectory() as scratch:
                (Path(scratch) / 'cc.yaml').write_bytes(data)
                try:
                    declaration = load(Path(scratch) / 'cc.yaml')
                except Exception:  # older releases used the legacy declaration format
                    declaration = load(Path(scratch) / 'cc.yaml', legacy=True)
    if declaration is None:
        return None, None, {}
    return hashlib.sha256(release_manifest_bytes(declaration, rows)).hexdigest(), declaration['version'], files


def history(directory, pinned):
    """Walk back from HEAD to the commit whose content is the pinned release."""
    path = (CCS / directory).relative_to(REPO).as_posix()
    versions = []
    for commit in git('log', '--format=%H', 'HEAD', '--', path).split():
        release, version, files = committed_release(commit, directory)
        if release == pinned:
            return dict(commit=commit, version=version, files=files), versions
        versions.append(dict(commit=commit, version=version, release=release))
    raise SystemExit(f'{directory}: pinned release {pinned} is not reachable in Git history')


def reseal(directories, name, reason):
    pins = CapsuleCatalog().release_pins()
    records = []
    with tempfile.TemporaryDirectory() as store:
        host = Host(store, session_grants=[])
        for directory in directories:
            relative = f'{directory}/cc.yaml'
            pinned = pins.get(relative, {}).get('new_release')
            if not pinned:
                raise SystemExit(f'{directory}: no pinned release to advance from')
            release = host.seal(CCS / directory)
            if release == pinned:
                raise SystemExit(f'{directory}: already matches its pinned release')
            version = yaml.safe_load((CCS / relative).read_text(encoding='utf-8'))['version']
            base, unrecorded = history(directory, pinned)
            if version == base['version']:
                raise SystemExit(f'{directory}: files changed but version {version} was not bumped')
            current = {row['path']: row['sha256'] for row in tree_files(CCS / directory)}
            changed = sorted(path for path in set(base['files']) | set(current)
                             if current.get(path) != base['files'].get(path))
            records.append(dict(
                path=relative, from_version=base['version'], from_release=pinned, from_commit=base['commit'],
                to_version=version, to_release=release, changed_files=changed,
                unrecorded_versions=[row for row in unrecorded if row['release'] != release],
                reason=reason))
    target = CCS / f'{name}-migration.json'
    if target.exists():
        raise SystemExit(f'{target.name} already exists; choose a new release name')
    document = dict(format='factory-cc-migration/1', releases=records)
    target.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8', newline='\n')
    return target, document


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('directories', nargs='+', help='capsule directories relative to factory/ccs')
    parser.add_argument('--name', required=True, help='migration file stem, e.g. factory-worker-reseal')
    parser.add_argument('--reason', required=True, help='why the content changed')
    args = parser.parse_args()
    target, document = reseal(args.directories, args.name, args.reason)
    for row in document['releases']:
        print(f"{row['path']}: {row['from_version']} {row['from_release'][:12]} -> "
              f"{row['to_version']} {row['to_release'][:12]} ({', '.join(row['changed_files'])})")
    print('wrote', target.relative_to(REPO))


if __name__ == '__main__':
    main()
