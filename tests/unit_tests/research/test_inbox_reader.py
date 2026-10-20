"""Actual POSIX file custody tests; no candidate qualification is implied."""
import hashlib
import json
import os

import pytest

from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.contracts.inbox import SignedInboxReader


def published(tmp_path):
    root = tmp_path / 'published'; root.mkdir(mode=0o750)
    raw = b'exact public bytes; no private fixture or signing key'
    ref = {'id': 'opaque:../../not-a-filesystem-path', 'sha256': hashlib.sha256(raw).hexdigest()}
    data = root / (ref['sha256'] + '.bytes'); data.write_bytes(raw); data.chmod(0o640)
    index = root / 'original-byte-index.json'
    index.write_text(json.dumps({'schema': 'ai4r-original-bytes:1', 'refs': {ref['id']: ref['sha256']}}))
    index.chmod(0o640)
    reader = SignedInboxReader(root, custodian_uid=os.geteuid(), custodian_gid=os.getegid())
    return root, reader, ref, raw, data, index


def test_original_ref_id_is_an_opaque_index_key_and_bytes_stay_exact(tmp_path):
    _, reader, ref, raw, _, _ = published(tmp_path)
    assert reader.read(ref) == raw
    with pytest.raises(ResearchError): reader.read(ref | {'id': '/etc/passwd'})


@pytest.mark.parametrize('fault', ['digest', 'index_digest', 'file_link', 'index_link', 'hardlink', 'other_writer', 'index_writer', 'directory_writer', 'oversize'])
def test_read_only_original_bytes_reject_custody_and_integrity_faults(tmp_path, fault):
    root, reader, ref, _, data, index = published(tmp_path)
    if fault == 'digest': data.write_bytes(b'swapped bytes')
    elif fault == 'index_digest': index.write_text(json.dumps({'schema': 'ai4r-original-bytes:1', 'refs': {ref['id']: 'a' * 64}}))
    elif fault == 'file_link':
        target = tmp_path / 'original'; data.rename(target); data.symlink_to(target)
    elif fault == 'index_link':
        target = tmp_path / 'index'; index.rename(target); index.symlink_to(target)
    elif fault == 'hardlink': os.link(data, tmp_path / 'alias')
    elif fault == 'other_writer': data.chmod(0o660)
    elif fault == 'index_writer': index.chmod(0o660)
    elif fault == 'directory_writer': root.chmod(0o770)
    else:
        with data.open('wb') as stream: stream.truncate(SignedInboxReader.MAX_BYTES + 1)
    with pytest.raises(ResearchError): reader.read(ref)


def test_original_byte_root_refuses_symlink_ancestry(tmp_path):
    root, _, ref, _, _, _ = published(tmp_path)
    alias = tmp_path / 'alias'; alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(ResearchError):
        SignedInboxReader(alias, custodian_uid=os.geteuid(), custodian_gid=os.getegid()).read(ref)
