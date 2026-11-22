import hashlib
import json
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from jiuwenswarm.ccv2.ccv2 import load, release_manifest_bytes, tree_files
from jiuwenswarm.gateway.channel_manager.web.capsule_catalog import CCS, CapsuleCatalog
from jiuwenswarm.gateway.channel_manager.web.factory_http import FactoryHttpService, attach_factory_routes

PREFIX = '/api/factory/capsules'
NAME = 'batch_layout_mapper'
CAPSULE_ID = 'engine.build_batch_layout_mapper'


def client(catalog=None):
    app = FastAPI()
    attach_factory_routes(app, service=FactoryHttpService(roots=[], capsule_catalog=catalog))
    return TestClient(app)


def test_catalog_detail_and_file_use_retained_release_pins():
    api = client()
    catalog = api.get(PREFIX).json()
    capsules = catalog['capsules']
    stars = [capsule for capsule in capsules if capsule['starred']]
    assert len(stars) == 5 and len(capsules) > len(stars)
    assert all(row['kind'] == 'builder' and row['integrity'] == 'verified' for row in stars)
    assert all(row['expected_digest'] == row['digest'] for row in stars)
    cache = next(row for row in stars if row['name'] == 'expert_weight_cache')
    assert cache['version'] == '1.4.2'
    assert cache['expected_digest'] == 'f6a96f164ff78ae35c3f285a3cf041bfbc4893829b9b722919a8da773d06f654'
    assert 'files' not in stars[0]
    kinds = {capsule['id']: capsule['kind'] for capsule in capsules}
    assert kinds['factory.builder'] == 'factory-support'
    assert kinds['factory.deep_profile'] == 'analysis'
    assert kinds['factory.numerical_investigation_lab'] == 'analysis'
    assert kinds['engine.performance_baseline'] == 'analysis'

    analysis = api.get(f'{PREFIX}/factory.deep_profile').json()
    assert analysis['sections']['method'] == 'METHOD.md'
    assert analysis['capability_descriptions']['analyze'].startswith('Parse scoped')
    assert analysis['evidence']['analyses'] == []

    detail = api.get(f'{PREFIX}/{CAPSULE_ID}').json()
    assert detail['name'] == NAME
    assert detail['ontology']['entities']['regions']['L3'] == 'generation_loop'
    assert detail['component_spec']['kind'] == 'builder_spec'
    assert 'verify' in detail['capabilities']
    assert detail['sections']['verifier'] == 'run.py'
    assert detail['contract_id'] == catalog['contract']['id']
    assert set(detail['contract_clauses']) <= {clause['id'] for clause in catalog['contract']['clauses']}
    assert all(row['integrity'] == 'verified' for row in detail['files'])

    content = api.get(f'{PREFIX}/{NAME}/file', params={'path': detail['sections']['ontology']}).json()
    assert content['parsed'] == detail['ontology']
    assert content['integrity'] == 'verified'
    assert content['expected_sha256'] == hashlib.sha256(content['content'].encode()).hexdigest()

    contract = catalog['contract']
    raw = api.get(f'{PREFIX}/{NAME}/file', params={'path': contract['raw']['path']}).json()
    assert raw['parsed']['contract_id'] == contract['id']
    readable = api.get(f'{PREFIX}/{NAME}/file', params={'path': contract['readable']['path']}).json()
    assert 'Star DeepSeek contract v1' in readable['content']


def test_cache_method_drift_uses_the_exact_current_retained_inventory(tmp_path):
    name = 'expert_weight_cache'
    capsule = tmp_path / name
    shutil.copytree(CCS / name, capsule)
    for migration in CCS.glob('*migration.json'):
        shutil.copyfile(migration, tmp_path / migration.name)
    document = 'DIRECT-SEED.md'
    original = hashlib.sha256((capsule / document).read_bytes()).hexdigest()
    (capsule / document).write_text('Unsealed method change')
    api = client(CapsuleCatalog(root=tmp_path))
    detail = api.get(f'{PREFIX}/{name}').json()
    assert detail['integrity'] == 'mismatch'
    assert detail['expected_digest'] == 'f6a96f164ff78ae35c3f285a3cf041bfbc4893829b9b722919a8da773d06f654'
    files = {row['path']: row for row in detail['files']}
    assert files[document]['integrity'] == 'mismatch'
    assert files[document]['expected_sha256'] == original
    assert files['cc.yaml']['integrity'] == 'verified'
    displayed = api.get(f'{PREFIX}/{name}/file', params={'path': document}).json()
    assert displayed['integrity'] == 'mismatch'
    assert displayed['content'] == 'Unsealed method change'


@pytest.fixture
def catalog_inputs(tmp_path):
    root = tmp_path / 'ccs'
    shutil.copytree(CCS / NAME, root / NAME)
    shutil.copytree(CCS / 'engine_inspector', root / 'engine_inspector')
    capsule = root / NAME
    manifest = release_manifest_bytes(load(capsule / 'cc.yaml'), tree_files(capsule))
    digest = hashlib.sha256(manifest).hexdigest()
    state = capsule / '.cc-state'
    state.mkdir(exist_ok=True)
    (state / 'fixture.manifest.json').write_bytes(manifest)
    (root / 'star-transport-migration.json').write_text(json.dumps({'releases': [{
        'path': f'{NAME}/cc.yaml', 'old_release': digest, 'new_release': digest,
    }]}))
    owner = tmp_path / 'owner'
    owner.mkdir()
    return root, owner


def test_missing_and_changed_files_remain_visible(catalog_inputs):
    root, owner = catalog_inputs
    api = client(CapsuleCatalog(root=root, owner_ontology=owner))
    capsule_path = root / NAME
    (capsule_path / 'METHOD.md').write_text('Changed capsule method')
    (capsule_path / 'GUIDE.md').unlink()
    detail = api.get(f'{PREFIX}/{NAME}').json()
    assert detail['integrity'] == 'mismatch'
    assert detail['expected_digest'] != detail['digest']
    files = {row['path']: row for row in detail['files']}
    assert files['METHOD.md']['integrity'] == 'mismatch'
    assert files['GUIDE.md']['integrity'] == 'missing'
    displayed = api.get(f'{PREFIX}/{NAME}/file', params={'path': 'METHOD.md'}).json()
    assert displayed['content'] == 'Changed capsule method'
    assert displayed['integrity'] == 'mismatch'

    (capsule_path / 'cc.yaml').write_text('malformed: [')
    catalog = api.get(PREFIX).json()
    assert next(row for row in catalog['capsules'] if row['name'] == NAME)['integrity'] == 'mismatch'
    assert any(row['name'] == 'engine_inspector' for row in catalog['capsules'])


def test_files_confined_to_capsule_and_pinned_ontology(catalog_inputs, tmp_path):
    root, owner = catalog_inputs
    outside = tmp_path / 'outside.txt'
    outside.write_text('Outside file')
    capsule_path = root / NAME
    (capsule_path / '.private.txt').write_text('Hidden file')
    (capsule_path / 'escape.txt').symlink_to(outside)
    (owner / 'unlisted.md').write_text('Unlisted owner file')
    (owner / 'overview.md').write_text('Pinned ontology overview')
    (owner / 'link.md').symlink_to(outside)
    expected = hashlib.sha256((owner / 'overview.md').read_bytes()).hexdigest()
    (owner / 'SHA256SUMS').write_text(f'{expected}  overview.md\n{expected}  link.md\n{expected}  ../outside.txt\n')
    api = client(CapsuleCatalog(root=root, owner_ontology=owner))

    owner_files = {row['path']: row['integrity'] for row in api.get(PREFIX).json()['owner_ontology']}
    assert owner_files == {'owner-ontology/SHA256SUMS': 'untracked', 'owner-ontology/overview.md': 'verified',
                           'owner-ontology/link.md': 'missing'}
    response = api.get(f'{PREFIX}/{NAME}/file', params={'path': 'owner-ontology/overview.md'})
    assert response.json()['content'] == 'Pinned ontology overview'
    assert response.json()['integrity'] == 'verified'

    for path in (str(outside), '../engine_inspector/cc.yaml', 'escape.txt', '.private.txt',
                 'owner-ontology/unlisted.md', 'owner-ontology/link.md', 'owner-ontology/../outside.txt'):
        assert api.get(f'{PREFIX}/{NAME}/file', params={'path': path}).status_code == 404
    assert api.get(f'{PREFIX}/engine_inspector/file', params={'path': 'owner-ontology/overview.md'}).status_code == 404
    assert api.get(f'{PREFIX}/missing/file', params={'path': 'cc.yaml'}).status_code == 404


def test_file_sanitization_preserves_the_original_byte_digest(catalog_inputs):
    root, owner = catalog_inputs
    content = b'{"password":"short-value","sample":12}'
    (root / NAME / 'samples' / 'redaction.json').write_bytes(content)
    api = client(CapsuleCatalog(root=root, owner_ontology=owner))

    body = api.get(f'{PREFIX}/{NAME}/file', params={'path': 'samples/redaction.json'}).json()
    assert body['sha256'] == hashlib.sha256(content).hexdigest()
    assert 'short-value' not in body['content']
    assert body['parsed'] == {'password': '<redacted>', 'sample': 12}


def test_declarative_analysis_metadata_and_follow_up_release_pin(catalog_inputs):
    root, owner = catalog_inputs
    capsule = root / NAME
    manifest = capsule / 'cc.yaml'
    initial = CapsuleCatalog(root=root, owner_ontology=owner).detail(NAME)
    manifest.write_text(manifest.read_text().replace(f"version: {initial['version']}", 'version: 8.2.0', 1))
    updated = hashlib.sha256(release_manifest_bytes(load(manifest), tree_files(capsule))).hexdigest()
    (root / 'capability-verifier-migration.json').write_text(json.dumps({'releases': [{
        'path': f'{NAME}/cc.yaml', 'from_release': initial['digest'], 'to_release': updated,
    }]}))

    analysis = root / 'engine_inspector'
    manifest = analysis / 'cc.yaml'
    text = manifest.read_text().replace('materials:\n', 'materials:\n  analysis:\n    path: ANALYSIS.json\n', 1)
    manifest.write_text(text)
    (analysis / 'ANALYSIS.json').write_text(json.dumps({'kind': 'analysis', 'title': 'Phase contributions'}))

    api = client(CapsuleCatalog(root=root, owner_ontology=owner))
    detail = api.get(f'{PREFIX}/{NAME}').json()
    assert detail['expected_digest'] == detail['digest'] == updated
    assert detail['integrity'] == 'verified'
    analysis_view = api.get(f'{PREFIX}/engine_inspector').json()
    assert analysis_view['kind'] == 'analysis'
    assert analysis_view['title'] == 'Phase contributions'
    assert analysis_view['sections']['analysis'] == 'ANALYSIS.json'
