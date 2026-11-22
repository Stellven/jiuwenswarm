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
import sys
import tempfile

import yaml

# Seal and record this checkout's capsules, not those of an installed jiuwenswarm package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

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


def retain_manifest(directory, pinned, version):
    """Keep the release manifest beside the capsule when its pinned release kept one.

    The catalog reads ``.cc-state/*.manifest.json`` to show which files drifted from the pinned
    release; a capsule that retains its pinned manifest must retain the next one as well.
    """
    state = CCS / directory / '.cc-state'
    if not any(hashlib.sha256(path.read_bytes()).hexdigest() == pinned for path in state.glob('*.manifest.json')):
        return None
    target = state / f'{version}.manifest.json'
    target.write_bytes(release_manifest_bytes(load(CCS / directory / 'cc.yaml'), tree_files(CCS / directory)))
    return target


def reseal(directories, name, reason):
    pins = CapsuleCatalog().release_pins()
    records = []
    retained = []
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
            retained.append((directory, pinned, version))
    target = CCS / f'{name}-migration.json'
    if target.exists():
        raise SystemExit(f'{target.name} already exists; choose a new release name')
    for row in retained:
        if manifest := retain_manifest(*row):
            print('retained', manifest.relative_to(REPO))
    document = dict(format='factory-cc-migration/1', releases=records)
    target.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8', newline='\n')
    return target, document


def initial(directories):
    """Record the first release of capsules that have no pinned release yet."""
    pins = CapsuleCatalog().release_pins()
    target = CCS / 'migration.json'
    document = json.loads(target.read_text(encoding='utf-8'))
    records = []
    with tempfile.TemporaryDirectory() as store:
        host = Host(store, session_grants=[])
        for directory in directories:
            relative = f'{directory}/cc.yaml'
            if pins.get(relative, {}).get('new_release'):
                raise SystemExit(f'{directory}: already has a pinned release; advance it without --initial')
            release = host.seal(CCS / directory)
            records.append(dict(path=relative, old_release=release, new_release=release,
                                initial_canonical_release=release))
    document['releases'].extend(records)
    target.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8', newline='\n')
    return target, records


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('directories', nargs='+', help='capsule directories relative to factory/ccs')
    parser.add_argument('--initial', action='store_true', help='record the first release of untracked capsules')
    parser.add_argument('--name', help='migration file stem, e.g. factory-worker-reseal')
    parser.add_argument('--reason', help='why the content changed')
    args = parser.parse_args()
    if args.initial:
        target, records = initial(args.directories)
        for row in records:
            print(f"{row['path']}: first release {row['new_release'][:12]}")
        print('updated', target.relative_to(REPO))
        return
    if not (args.name and args.reason):
        parser.error('--name and --reason are required unless --initial is given')
    target, document = reseal(args.directories, args.name, args.reason)
    for row in document['releases']:
        print(f"{row['path']}: {row['from_version']} {row['from_release'][:12]} -> "
              f"{row['to_version']} {row['to_release'][:12]} ({', '.join(row['changed_files'])})")
    print('wrote', target.relative_to(REPO))


if __name__ == '__main__':
    main()
