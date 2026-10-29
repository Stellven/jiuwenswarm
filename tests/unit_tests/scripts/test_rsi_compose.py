"""Finite private Compose helper guards; no network, installation or daemon."""
import importlib.util
import io
from pathlib import Path
import tarfile

import pytest

SOURCE = Path(__file__).resolve().parents[3] / 'deploy/m1/rsi_compose.py'
spec = importlib.util.spec_from_file_location('rsi_compose_test',SOURCE)
compose = importlib.util.module_from_spec(spec); spec.loader.exec_module(compose)


def test_archive_exact_bytes_are_required_before_extraction(monkeypatch):
    original = dict(compose.PACKAGE)
    monkeypatch.setattr(compose,'PACKAGE',original | {'bytes':3,'sha256':compose.sha(b'abc')})
    monkeypatch.setattr(compose,'read',lambda path:b'abc')
    assert compose.verified_archive(Path('/unused-unit.deb')) == b'abc'
    monkeypatch.setattr(compose,'read',lambda path:b'abd')
    with pytest.raises(ValueError,match='ARCHIVE_HASH'): compose.verified_archive(Path('/unused-unit.deb'))
    monkeypatch.setattr(compose,'read',lambda path:b'abcd')
    with pytest.raises(ValueError,match='ARCHIVE_HASH'): compose.verified_archive(Path('/unused-unit.deb'))


def test_partial_or_existing_prefix_cannot_be_overridden(tmp_path,monkeypatch):
    monkeypatch.setattr(compose,'PREFIX',tmp_path)
    monkeypatch.setattr(compose,'root_identity',lambda:None)
    def forbidden(): pytest.fail('Existing prefix must be refused before metadata or download')
    monkeypatch.setattr(compose,'metadata',forbidden)
    with pytest.raises(ValueError,match='PREFIX_ALREADY_EXISTS'): compose.plan()


@pytest.mark.parametrize('name,link',[('../escape',None),('safe','/outside'),('safe','../../outside')])
def test_shared_extractor_refuses_escaping_archive_paths(tmp_path,name,link):
    body = io.BytesIO()
    with tarfile.open(fileobj=body,mode='w:') as archive:
        member = tarfile.TarInfo(name)
        if link is None:
            member.size = 1; archive.addfile(member,io.BytesIO(b'x'))
        else:
            member.type = tarfile.SYMTYPE; member.linkname = link; archive.addfile(member)
    with pytest.raises(ValueError): compose.host.extract_payload(body.getvalue(),tmp_path)


def test_read_refuses_symlink_and_unprotected_ancestor(tmp_path):
    path = tmp_path/'file'; path.write_bytes(b'unit')
    link = tmp_path/'alias'; link.symlink_to(path)
    with pytest.raises(ValueError,match='UNSAFE_HOST_PATH'): compose.read(link)
    # The test temporary tree has /tmp as a writable ancestor. That is not
    # acceptable custody for the operational Root-private helper.
    with pytest.raises(ValueError,match='UNPROTECTED_HOST_ANCESTRY'): compose.read(path)
