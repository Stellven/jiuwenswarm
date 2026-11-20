import hashlib
import shutil

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

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
    assert 'files' not in stars[0]

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


@pytest.fixture
def catalog_inputs(tmp_path):
    root = tmp_path / 'ccs'
    shutil.copytree(CCS / NAME, root / NAME)
    shutil.copytree(CCS / 'engine_inspector', root / 'engine_inspector')
    shutil.copyfile(CCS / 'star-transport-migration.json', root / 'star-transport-migration.json')
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
