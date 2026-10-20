"""Protected metadata cannot be asserted by fields in captured JSON bytes."""
import pytest

from jiuwenswarm.research.contracts.types import ResearchError
from jiuwenswarm.research.state import SQLiteRunStore, json_bytes


def test_record_kind_uses_protected_capture_not_payload(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        forged = {'kind': 'builder_tool_qualification', 'result': 'PASS'}
        raw = store.put_blob(json_bytes(forged))
        with pytest.raises(ResearchError, match='protected record kind'):
            store.record_kind(raw)
        other = store.append_record('unrelated_diagnostic', forged)
        assert store.record_kind(other) == 'unrelated_diagnostic'
        genuine = store.append_record('builder_tool_qualification', {'result': 'BLOCKED'})
        assert store.record_kind(genuine) == 'builder_tool_qualification'
    finally:
        store.close()


def test_record_kind_checks_identity_hash_and_actual_bytes(tmp_path):
    store = SQLiteRunStore(tmp_path)
    try:
        captured = store.append_record('builder_tool_qualification', {'result': 'BLOCKED'})
        changed = {**captured, 'sha256': '0' * 64}
        with pytest.raises(ResearchError, match='identity/digest mismatch'):
            store.record_kind(changed)
        store.blobs.path_for(captured['sha256']).write_bytes(b'altered')
        with pytest.raises(ResearchError, match='no longer match'):
            store.record_kind(captured)
    finally:
        store.close()
