import hashlib
import os

import pytest

from jiuwenswarm.research_records.original_bytes import OriginalBytes


def test_original_byte_index_preserves_opaque_identity_and_detects_tampering(tmp_path):
    root=tmp_path/'public';publisher=OriginalBytes(root,writable=True)
    raw=b'exact captured body';pin={'id':'opaque:body','sha256':hashlib.sha256(raw).hexdigest()}
    publisher.put_ref(pin,raw)
    assert OriginalBytes(root).read(pin)==raw
    with pytest.raises(ValueError):publisher.put_ref({**pin,'sha256':'a'*64},raw)
    target=root/(pin['sha256']+'.bytes');target.write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'):OriginalBytes(root).read(pin)


def test_original_byte_reader_rejects_a_link_even_with_the_right_bytes(tmp_path):
    raw=b'body';publisher=OriginalBytes(tmp_path/'public',writable=True)
    pin=publisher.put_bytes(raw);target=publisher.root/(pin['sha256']+'.bytes')
    outside=tmp_path/'outside';outside.write_bytes(raw);target.unlink()
    try:os.link(outside,target)
    except OSError:pytest.fail('BLOCKED: hard-link custody control requires supported filesystem')
    with pytest.raises(ValueError,match='Unsafe'):publisher.read(pin)
