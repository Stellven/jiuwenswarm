"""CI check: a capsule's files may not change without a new recorded release.

The catalog pins each capsule to the release recorded in factory/ccs/*migration.json. A commit
that edits capsule files must bump cc.yaml's version and record the new release with
scripts/factory/reseal_capsules.py; otherwise the UI reports a digest mismatch.
"""
import json
import shutil

import yaml

from jiuwenswarm.ccv2.ccv2 import load, release_manifest_bytes, sha, tree_files
from jiuwenswarm.gateway.channel_manager.web.capsule_catalog import CCS, CapsuleCatalog

FIX = 'run scripts/factory/reseal_capsules.py after bumping cc.yaml version'


def test_no_pinned_capsule_drifts_from_its_recorded_release():
    catalog = CapsuleCatalog()
    pins = catalog.release_pins()
    drift = []
    for relative in catalog.paths():
        expected = pins.get(relative, {}).get('new_release')
        if not expected:
            continue
        root = (CCS / relative).parent
        digest = sha(release_manifest_bytes(load(root / 'cc.yaml'), tree_files(root)))
        if digest != expected:
            drift.append(f'{relative}: recorded {expected[:12]}, files give {digest[:12]}')
    assert drift == [], f'Capsule files changed without a new sealed release ({FIX}): {drift}'
    rows = catalog.listing()['capsules']
    assert [row['name'] for row in rows if row['integrity'] == 'mismatch'] == []


def test_recorded_releases_bump_the_version_and_advance_from_the_previous_pin():
    for path in sorted(CCS.glob('*-migration.json')):
        for row in json.loads(path.read_text(encoding='utf-8'))['releases']:
            if 'to_release' in row and 'from_version' in row:
                assert row['from_version'] != row['to_version'], f'{path.name}: {row["path"]} kept its version'
                assert row['from_release'] != row['to_release'], f'{path.name}: {row["path"]} is not a new release'


def test_an_unrecorded_edit_is_reported_as_drift(tmp_path):
    name = 'lab_client'
    shutil.copytree(CCS / name, tmp_path / name)
    for migration in CCS.glob('*migration.json'):
        shutil.copyfile(migration, tmp_path / migration.name)
    catalog = CapsuleCatalog(root=tmp_path)
    assert catalog.summary(f'{name}/cc.yaml', catalog.release_pins()[f'{name}/cc.yaml'])['integrity'] == 'verified'
    # A version bump alone is not a release: the catalog still needs the recorded digest.
    declaration = yaml.safe_load((tmp_path / name / 'cc.yaml').read_text(encoding='utf-8'))
    declaration['version'] = '9.9.9'
    (tmp_path / name / 'cc.yaml').write_text(yaml.safe_dump(declaration, sort_keys=False), encoding='utf-8')
    (tmp_path / name / 'LLAMA-SPARK.md').write_text('edited without a release', encoding='utf-8')
    row = catalog.summary(f'{name}/cc.yaml', catalog.release_pins()[f'{name}/cc.yaml'])
    assert row['integrity'] == 'mismatch'


def test_every_capsule_has_a_recorded_release():
    # A capsule without a pin is "untracked": record its first release with --initial.
    catalog = CapsuleCatalog()
    pins = catalog.release_pins()
    untracked = [relative for relative in catalog.paths() if not pins.get(relative, {}).get('new_release')]
    assert untracked == [], f'Capsules without a recorded release (reseal_capsules.py --initial): {untracked}'
    rows = catalog.listing()['capsules']
    assert {row['integrity'] for row in rows} == {'verified'}, [
        (row['name'], row['integrity']) for row in rows if row['integrity'] != 'verified']


def test_every_capsule_seals_to_its_recorded_release(tmp_path):
    from jiuwenswarm.ccv2.ccv2 import Host
    host, pins = Host(tmp_path, session_grants=[]), CapsuleCatalog().release_pins()
    sealed = {path.parent.name: host.seal(path.parent) for path in sorted(CCS.glob('*/cc.yaml'))}
    assert len(sealed) == 58
    assert {name: digest for name, digest in sealed.items() if pins[f'{name}/cc.yaml']['new_release'] != digest} == {}
