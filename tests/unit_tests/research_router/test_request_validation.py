import hashlib
import json

import pytest

from jiuwenswarm.research_router.request_validation import IntegrityFault, ProtectedData


def test_exact_bytes_and_root_boundary(tmp_path):
    original = b'{"a":1}\n'; (tmp_path / "input.json").write_bytes(original)
    reader = ProtectedData([tmp_path])
    ref = {"id": "input.json", "sha256": hashlib.sha256(original).hexdigest()}
    assert reader.read_ref(ref) == original
    (tmp_path / "input.json").write_bytes(b'{"a":1}')
    with pytest.raises(IntegrityFault): reader.read_ref(ref)
    with pytest.raises(IntegrityFault): reader.read_ref({"id": "../escape", "sha256": "a" * 64})


def test_symlink_and_nonfinite_json_rejected(tmp_path):
    (tmp_path / "bad.json").write_bytes(b'{"x":NaN}')
    with pytest.raises(IntegrityFault):
        ProtectedData([tmp_path]).read_json({"id": "bad.json", "sha256": hashlib.sha256(b'{"x":NaN}').hexdigest()})


def test_protected_captured_context_full_schema_and_forged_binding():
    from .test_bound_context import test_full_original_contracts_and_forged_context_rejected
    test_full_original_contracts_and_forged_context_rejected()

