"""Synthetic original-wheel format controls; actual pinned archives are separate evidence."""
import base64
import csv
import hashlib
import io
import stat
import zipfile

import pytest

from scripts.research_offline_assets import AssetError, audit_distribution, audit_wheel


def distribution(tmp_path, *, vendor=True, directories=False, fault=None):
    """Small setuptools-shaped fixture, never a claim about the original archive."""
    info = 'setuptools-82.0.1.dist-info/'
    files = {
        'setuptools/__init__.py': b'fixture = True\n',
        info + 'METADATA': b'Metadata-Version: 2.4\nName: setuptools\nVersion: 82.0.1\n',
        info + 'WHEEL': b'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n',
    }
    if vendor:
        files.update({
            'setuptools/_vendor/sample-1.0.dist-info/METADATA': b'Name: sample\nVersion: 1.0\n',
            'setuptools/_vendor/sample-1.0.dist-info/RECORD': b'vendored metadata is ordinary payload\n',
        })
    if fault == 'second_root':
        files['foreign-1.0.dist-info/METADATA'] = b'Name: foreign\nVersion: 1.0\n'
    if fault == 'empty_second_root':
        files['foreign-1.0.dist-info/NOTICE'] = b'foreign root\n'
    if fault == 'wrong_root':
        files = {name.replace(info, 'foreign-82.0.1.dist-info/'): raw for name, raw in files.items()}
        info = 'foreign-82.0.1.dist-info/'
    if fault == 'traversal':
        files['../outside.py'] = b'forbidden\n'
    if fault == 'ancestor_file':
        files['setuptools'] = b'not a directory\n'
    if fault == 'unlisted':
        unlisted = ('unlisted.py', b'uncaptured member\n')
    else:
        unlisted = None
    rows = []
    for name, raw in files.items():
        digest = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode()
        rows.append([name, digest, str(len(raw))])
    if fault == 'record_hash':
        rows[0][1] = 'sha256=' + 'A' * 43
    if fault == 'record_size':
        rows[0][2] = '999'
    if fault == 'duplicate_record':
        rows.append(rows[0])
    if fault == 'missing_record_member':
        rows.append(['missing.py', 'sha256=' + 'A' * 43, '1'])
    rows.append([info + 'RECORD', '', ''])
    text = io.StringIO(newline='')
    csv.writer(text, lineterminator='\n').writerows(rows)
    files[info + 'RECORD'] = text.getvalue().encode()
    if unlisted:
        files[unlisted[0]] = unlisted[1]
    path = tmp_path / 'setuptools-82.0.1-py3-none-any.whl'
    with zipfile.ZipFile(path, 'w') as archive:
        if directories or fault in {'directory_payload', 'directory_alias', 'directory_special', 'directory_file'}:
            name = 'setuptools//' if fault == 'directory_alias' else 'setuptools/'
            entry = zipfile.ZipInfo(name)
            entry.external_attr = (stat.S_IFCHR if fault == 'directory_special' else stat.S_IFDIR) << 16
            archive.writestr(entry, b'not empty' if fault == 'directory_payload' else b'')
            if fault == 'directory_file':
                archive.writestr('setuptools', b'collision')
        for name, raw in files.items():
            entry = zipfile.ZipInfo(name)
            entry.external_attr = (stat.S_IFLNK if fault == 'link' and name.endswith('__init__.py') else stat.S_IFREG) << 16
            archive.writestr(entry, raw)
        if fault == 'duplicate_member':
            with pytest.warns(UserWarning, match='Duplicate'):
                archive.writestr(info + 'METADATA', files[info + 'METADATA'])
    return path


@pytest.mark.parametrize('directories', [False, True])
def test_general_distribution_uses_one_root_and_keeps_nested_vendor_bytes(tmp_path, directories):
    path = distribution(tmp_path, directories=directories)
    before = path.read_bytes()
    result = audit_distribution(path, expected_name='setuptools', expected_version='82.0.1')
    assert result['metadata']['name'] == 'setuptools' and result['metadata']['version'] == '82.0.1'
    assert result['members']['setuptools/_vendor/sample-1.0.dist-info/METADATA']['sha256']
    assert result['members']['setuptools/_vendor/sample-1.0.dist-info/RECORD']['bytes'] > 0
    assert result['sha256'] == hashlib.sha256(before).hexdigest()
    assert path.read_bytes() == before


def test_delivered_native_auditor_still_refuses_vendor_metadata_and_directories(tmp_path):
    for kwargs, reason in [({'vendor': True}, 'DIST_INFO'), ({'vendor': False, 'directories': True}, 'PATH')]:
        path = distribution(tmp_path, **kwargs)
        with pytest.raises(AssetError, match=reason):
            audit_wheel(path, expected_name='setuptools')


@pytest.mark.parametrize('fault,reason', [
    ('second_root', 'DIST_INFO'), ('empty_second_root', 'DIST_INFO'), ('wrong_root', 'IDENTITY'),
    ('traversal', 'PATH'), ('ancestor_file', 'COLLISION'), ('unlisted', 'RECORD_CLOSURE'),
    ('record_hash', 'RECORD_HASH'), ('record_size', 'RECORD_HASH'), ('duplicate_record', 'RECORD_CLOSURE'),
    ('missing_record_member', 'RECORD_CLOSURE'), ('directory_payload', 'DIRECTORY'),
    ('directory_alias', 'PATH'), ('directory_special', 'DIRECTORY'), ('directory_file', 'COLLISION'),
    ('link', 'LINK'), ('duplicate_member', 'DUPLICATE'),
])
def test_general_original_distribution_rejects_ambiguous_or_forged_archives(tmp_path, fault, reason):
    path = distribution(tmp_path, fault=fault)
    with pytest.raises(AssetError, match=reason):
        audit_distribution(path, expected_name='setuptools', expected_version='82.0.1')


def test_general_identity_cannot_be_taken_from_vendor_or_caller(tmp_path):
    path = distribution(tmp_path)
    with pytest.raises(AssetError, match='METADATA_NAME'):
        audit_distribution(path, expected_name='sample')
    with pytest.raises(AssetError, match='METADATA_VERSION'):
        audit_distribution(path, expected_name='setuptools', expected_version='1.0')


def identity_distribution(tmp_path, *, metadata_name='Friendly.Bard',
                          root_name='Friendly.Bard', filename_name='Friendly.Bard',
                          root_version='1.0', filename_version='1.0',
                          filename_build=None, wheel_build=None,
                          filename_tags='py3-none-any', wheel_tags=('py3-none-any',)):
    """Original-format fixture with independently selectable identity fields."""
    info = root_name + '-' + root_version + '.dist-info/'
    wheel = 'Wheel-Version: 1.0\nRoot-Is-Purelib: true\n'
    wheel += ''.join('Tag: ' + tag + '\n' for tag in wheel_tags)
    if wheel_build is not None:
        wheel += 'Build: ' + wheel_build + '\n'
    files = {
        'friendly_bard/__init__.py': b'fixture = True\n',
        info + 'METADATA': ('Metadata-Version: 2.4\nName: ' + metadata_name + '\nVersion: 1.0\n').encode(),
        info + 'WHEEL': wheel.encode(),
    }
    rows = [[name, 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).rstrip(b'=').decode(), str(len(raw))]
            for name, raw in files.items()]
    rows.append([info + 'RECORD', '', ''])
    record = io.StringIO(newline='')
    csv.writer(record, lineterminator='\n').writerows(rows)
    files[info + 'RECORD'] = record.getvalue().encode()
    build = '-' + filename_build if filename_build is not None else ''
    path = tmp_path / (filename_name + '-' + filename_version + build + '-' + filename_tags + '.whl')
    with zipfile.ZipFile(path, 'w') as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return path


@pytest.mark.parametrize('metadata_name,root_name,filename_name', [
    ('Friendly.Bard', 'Friendly.Bard', 'Friendly.Bard'),
    ('friendly-bard', 'FRIENDLY_BARD', 'Friendly.Bard'),
    ('Friendly_Bard', 'friendly-bard', 'FRIENDLY_bard'),
    ('FrIeNdLy-._.-BaRd', 'friendly__bard', 'friendly.bard'),
])
def test_general_identity_normalizes_names_without_rewriting_originals(tmp_path, metadata_name, root_name, filename_name):
    path = identity_distribution(tmp_path, metadata_name=metadata_name, root_name=root_name, filename_name=filename_name)
    original = path.read_bytes()
    result = audit_distribution(path, expected_name='friendly-bard', expected_version='1.0')
    assert result['metadata']['name'] == metadata_name
    assert result['sha256'] == hashlib.sha256(original).hexdigest()
    assert path.read_bytes() == original
    # The product's stricter native representation contract is unchanged.
    with pytest.raises(AssetError, match='IDENTITY'):
        audit_wheel(path, expected_name='friendly-bard', expected_version='1.0')


@pytest.mark.parametrize('kwargs,reason', [
    ({'root_name': 'foreign'}, 'IDENTITY'),
    ({'filename_name': 'foreign'}, 'IDENTITY'),
    ({'root_version': '1.1'}, 'IDENTITY'),
    ({'filename_version': '1.1'}, 'IDENTITY'),
    ({'filename_build': '1'}, 'BUILD'),
    ({'wheel_build': '1'}, 'BUILD'),
    ({'filename_build': '1', 'wheel_build': '2'}, 'BUILD'),
    ({'filename_build': 'invalid', 'wheel_build': 'invalid'}, 'BUILD'),
])
def test_general_identity_refuses_distinct_root_filename_version_or_build(tmp_path, kwargs, reason):
    path = identity_distribution(tmp_path, **kwargs)
    with pytest.raises(AssetError, match=reason):
        audit_distribution(path, expected_name='friendly-bard', expected_version='1.0')


def test_general_build_identity_is_exact(tmp_path):
    path = identity_distribution(tmp_path, filename_build='12abc', wheel_build='12abc')
    assert audit_distribution(path, expected_name='friendly-bard')['metadata']['version'] == '1.0'


@pytest.mark.parametrize('wheel_tags', [
    ('py2.py3-none-linux_x86_64.manylinux1_x86_64',),
    ('py2-none-linux_x86_64', 'py2-none-manylinux1_x86_64',
     'py3-none-linux_x86_64', 'py3-none-manylinux1_x86_64'),
])
def test_general_compares_the_full_expanded_tag_set(tmp_path, wheel_tags):
    path = identity_distribution(tmp_path, filename_tags='py2.py3-none-linux_x86_64.manylinux1_x86_64', wheel_tags=wheel_tags)
    result = audit_distribution(path, expected_name='friendly-bard')
    assert result['wheel_tags'] == [
        'py2-none-linux_x86_64', 'py2-none-manylinux1_x86_64',
        'py3-none-linux_x86_64', 'py3-none-manylinux1_x86_64',
    ]
    assert result['filename_tags'] == result['wheel_tags']
    assert result['tag_consistency'] == 'equal'


def test_general_preserves_original_upstream_tag_mismatch_explicitly(tmp_path):
    """A structural original audit is separate from target eligibility."""
    path = identity_distribution(tmp_path, filename_tags='py3-none-manylinux1_x86_64')
    original = path.read_bytes()
    result = audit_distribution(path, expected_name='friendly-bard')
    assert result['filename_tags'] == ['py3-none-manylinux1_x86_64']
    assert result['wheel_tags'] == ['py3-none-any']
    assert result['tag_consistency'] == 'mismatch'
    assert result['sha256'] == hashlib.sha256(original).hexdigest()
    assert path.read_bytes() == original
    # Neither declaration is replaced or broadened to make the two agree.
    assert result['filename_tags'] != result['wheel_tags']


@pytest.mark.parametrize('kwargs', [
    {'filename_tags': 'py3-none-'},
    {'wheel_tags': ('py3-none-',)},
    {'wheel_tags': ('py3-none-any.extra-',)},
])
def test_general_rejects_malformed_tags_before_reporting_compatibility(tmp_path, kwargs):
    path = identity_distribution(tmp_path, **kwargs)
    with pytest.raises(AssetError, match='TAG_MISMATCH'):
        audit_distribution(path, expected_name='friendly-bard')


def test_native_tag_set_equality_stays_strict(tmp_path):
    path = identity_distribution(tmp_path, metadata_name='friendly-bard', root_name='friendly_bard',
        filename_name='friendly_bard', filename_tags='py3-none-manylinux1_x86_64')
    with pytest.raises(AssetError, match='TAG_MISMATCH'):
        audit_wheel(path, expected_name='friendly-bard')
