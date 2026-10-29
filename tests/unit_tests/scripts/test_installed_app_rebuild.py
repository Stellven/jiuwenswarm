"""Public build archive boundaries; no Docker, installation or inference."""
import importlib.util
import io
import json
from pathlib import Path
import tarfile

import pytest

spec = importlib.util.spec_from_file_location('image_rebuild', Path(__file__).parents[3]/'deploy/m1/installed_app_rebuild.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


def archive(path, names):
    with tarfile.open(path, 'w') as stream:
        for name, body in names:
            item = tarfile.TarInfo(name); item.size = len(body)
            stream.addfile(item, io.BytesIO(body))


def test_exact_public_archive_extracts_actual_bytes(tmp_path):
    source = tmp_path/'source.tar'; body = b'public frozen source\n'
    archive(source, [('jiuwenswarm/module.py', body)])
    rows = [{'path': 'jiuwenswarm/module.py', 'size': len(body), 'sha256': b.sha(body)}]
    b.extract_public(source, tmp_path/'out', rows)
    assert (tmp_path/'out/jiuwenswarm/module.py').read_bytes() == body
    with pytest.raises(ValueError): b.extract_public(source, tmp_path/'out', rows)


@pytest.mark.parametrize('name', ['../escape', '/absolute', 'a\\b', 'C:/escape', 'a/../b', '.'])
def test_archive_traversal_never_reaches_a_write(tmp_path, name):
    source = tmp_path/'source.tar'; archive(source, [(name, b'x')])
    with pytest.raises(ValueError):
        b.extract_public(source, tmp_path/'out', [{'path': name, 'size': 1, 'sha256': b.sha(b'x')}])
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('fault', ['changed', 'missing', 'extra', 'duplicate', 'link'])
def test_public_inventory_changes_are_rejected(tmp_path, fault):
    source = tmp_path/'source.tar'; rows = [{'path': 'file', 'size': 1, 'sha256': b.sha(b'x')}]
    names = [('file', b'y' if fault == 'changed' else b'x')]
    if fault == 'missing': names = []
    if fault in {'extra', 'duplicate'}: names += [('extra' if fault == 'extra' else 'file', b'x')]
    archive(source, names)
    if fault == 'link':
        with tarfile.open(source, 'w') as stream:
            item = tarfile.TarInfo('file'); item.type = tarfile.SYMTYPE; item.linkname = '/outside'; stream.addfile(item)
    with pytest.raises(ValueError): b.extract_public(source, tmp_path/'out', rows)


def test_manifest_identity_cannot_be_reused_for_different_bytes():
    value = {'schema': 'ai4r-installed-build:2', 'files': [], 'links': []}
    value['build_id'] = b.sha(b.encoded(value))
    assert b.checked_manifest(json.dumps(value).encode()) == value
    value['files'] = [{'changed': True}]
    with pytest.raises(ValueError): b.checked_manifest(json.dumps(value).encode())


def test_installed_inventory_order_is_relative_path_order(tmp_path):
    (tmp_path/'a').mkdir(); (tmp_path/'a/x.py').write_bytes(b'x')
    (tmp_path/'a.py').write_bytes(b'y')
    assert [row['path'] for row in b.inventory(tmp_path)['files']] == ['a.py', 'a/x.py']


def test_wheel_cannot_omit_or_add_compiled_browser_assets(tmp_path):
    (tmp_path/'index.html').write_bytes(b'index')
    wanted = [{'path': 'index.html', 'size': 5, 'sha256': b.sha(b'index')},
              {'path': 'app.js', 'size': 2, 'sha256': b.sha(b'js')}]
    with pytest.raises(ValueError): b.verify_frontend(tmp_path, wanted)
    (tmp_path/'app.js').write_bytes(b'js')
    b.verify_frontend(tmp_path, wanted)
    (tmp_path/'extra.js').write_bytes(b'x')
    with pytest.raises(ValueError): b.verify_frontend(tmp_path, wanted)
