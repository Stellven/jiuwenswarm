"""Actual root→product-UID store capture; no root-owned application artifacts."""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

from jiuwenswarm.research.bridge import BridgeError
from jiuwenswarm.research.store_custody import CustodyStore


def test_actual_writer_keeps_large_raw_bytes_and_sqlite_under_product_uid():
    root = Path(tempfile.mkdtemp(prefix="ai4r-custody-"))
    root.chmod(0o711)
    state, transfer = root / "state", root / "transfer"
    state.mkdir(mode=0o700)
    os.chown(state, 10001, 10001)
    proxy = CustodyStore(state, transfer, input_root=state / 'inputs')
    try:
        raw = b"exact raw output\n" * (300000)
        ref = proxy.put_blob(raw, media_type="text/plain")
        assert proxy.read_blob(ref) == raw  # exceeds IPC frame, no truncation
        record = {"id": "controlled-observation", "captured_ref": ref, "observed_runtime": True,
                  "kind": "builder_tool_qualification"}
        observed = proxy.append_record("controlled-kernel-observation", record)
        assert proxy.read_record(observed) == record
        assert proxy.record_kind(observed) == "controlled-kernel-observation"
        with pytest.raises(BridgeError, match="AUDIT_UNAVAILABLE"):
            proxy.record_kind(ref)
        for path in state.rglob("*"):
            assert path.stat().st_uid == 10001, path
        assert list(transfer.iterdir()) == []
    finally:
        proxy.close()
        shutil.rmtree(root)


def test_proxy_serves_read_only_scans_the_builder_host_needs():
    """The executor reaches the store through this proxy; the Builder host scans records by run and kind."""
    root = Path(tempfile.mkdtemp(prefix="ai4r-custody-"))
    root.chmod(0o711)
    state, transfer = root / "state", root / "transfer"
    state.mkdir(mode=0o700)
    os.chown(state, 10001, 10001)
    proxy = CustodyStore(state, transfer, input_root=state / 'inputs')
    try:
        ref = proxy.append_record("model-call-start", {"id": "start-1", "run_id": "run:scan", "call_id": "c1"})
        proxy.append_record("model-call-start", {"id": "start-other", "run_id": "run:other", "call_id": "c2"})
        proxy.append_record("model-call-output", {"id": "out-1", "run_id": "run:scan", "text": "{}"})
        rows = list(proxy.iter_records(run_id="run:scan", kinds=("model-call-start",)))
        assert [row["record"]["call_id"] for row in rows] == ["c1"]
        assert rows[0]["ref"] == ref and rows[0]["kind"] == "model-call-start"
        assert proxy.record_ref("start-1") == ref
        with pytest.raises(BridgeError, match="AUDIT_UNAVAILABLE"):
            proxy.record_ref("missing-record")
    finally:
        proxy.close()
        shutil.rmtree(root)
