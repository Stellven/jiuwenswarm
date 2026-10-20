"""Protected exact-byte native trajectory journal beside the native read store.

The native display store can coalesce, truncate and shed its queue. This
synchronous FULL SQLite journal records each native record/frame and every
content-addressed sequence before returning to the producer. It never drops
or truncates evidence. A capture fault latches unavailable and must prevent
further governed work; a successful display projection cannot clear it.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import sqlite3
import threading
from pathlib import Path


class CaptureUnavailable(RuntimeError):
    pass


def _fields(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return value
    return vars(value)


class LosslessTrajectoryJournal:
    def __init__(self, root):
        supplied = Path(root)
        if supplied.is_symlink() or any(p.is_symlink() for p in supplied.parents):
            raise CaptureUnavailable("TRAJECTORY_CUSTODY_INVALID")
        supplied.mkdir(parents=True, mode=0o700, exist_ok=True)
        supplied.chmod(0o700)
        self.path = supplied / "native-capture.sqlite3"
        if self.path.is_symlink():
            raise CaptureUnavailable("TRAJECTORY_CUSTODY_INVALID")
        self._lock = threading.RLock()
        self._failed = self._closed = False
        try:
            self.db = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
            self.path.chmod(0o600)
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("CREATE TABLE IF NOT EXISTS blobs (sha256 TEXT PRIMARY KEY, content BLOB NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS entries (sequence INTEGER PRIMARY KEY, kind TEXT NOT NULL, correlation TEXT NOT NULL, payload_sha256 TEXT NOT NULL REFERENCES blobs(sha256), addressed_sequences TEXT NOT NULL)")
            if self.db.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise ValueError("native capture integrity check failed")
        except Exception:
            self._failed = True
            raise CaptureUnavailable("TRAJECTORY_INITIALIZATION_FAILED") from None

    @property
    def healthy(self):
        with self._lock:
            return not self._failed and not self._closed

    @property
    def count(self):
        with self._lock:
            return self.db.execute("SELECT count(*) FROM entries").fetchone()[0]

    def _blob(self, payload, expected=None):
        if not isinstance(payload, bytes):
            raise ValueError("native capture requires exact bytes")
        digest = hashlib.sha256(payload).hexdigest()
        if expected is not None and digest != expected:
            raise ValueError("native sequence hash mismatch")
        self.db.execute("INSERT OR IGNORE INTO blobs VALUES (?,?)", (digest, payload))
        stored = self.db.execute("SELECT content FROM blobs WHERE sha256=?", (digest,)).fetchone()[0]
        if stored != payload:
            raise ValueError("native capture hash conflict")
        return digest

    def _capture(self, kind, record):
        with self._lock:
            if not self.healthy:
                raise CaptureUnavailable("TRAJECTORY_CAPTURE_UNAVAILABLE")
            try:
                self.db.execute("BEGIN IMMEDIATE")
                if kind == "frame":
                    payload = json.dumps(_fields(record), sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
                else:
                    payload = record.raw_json
                payload_hash = self._blob(payload)
                sequences = []
                for sequence in getattr(record, "sequences", ()):
                    for digest, blob in sequence.blobs.items():
                        self._blob(blob, expected=digest)
                    sequences.append({"key": sequence.key, "seq_hash": sequence.seq_hash, "depth": sequence.depth,
                                      "logical_bytes": sequence.logical_bytes,
                                      "nodes": [_fields(node) for node in sequence.nodes]})
                correlation = {key: getattr(record, key, None) for key in
                    ("trace_id", "span_id", "session_id", "request_id", "run_id", "record_revision", "update_kind")}
                self.db.execute("INSERT INTO entries(kind,correlation,payload_sha256,addressed_sequences) VALUES (?,?,?,?)",
                    (kind, json.dumps(correlation, sort_keys=True, allow_nan=False), payload_hash,
                     json.dumps(sequences, sort_keys=True, allow_nan=False)))
                self.db.execute("COMMIT")
            except Exception:
                if self.db.in_transaction:
                    self.db.execute("ROLLBACK")
                self._failed = True
                raise CaptureUnavailable("TRAJECTORY_CAPTURE_FAILED") from None

    def consume(self, record):
        self._capture("record", record)

    def consume_snapshot(self, record):
        self._capture("snapshot", record)

    def consume_stream_frame(self, record):
        self._capture("frame", record)

    def close(self):
        with self._lock:
            if not self._closed:
                self._closed = True
                self.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.db.close()


_journal = _processor = None


def start_native_capture(root):
    """Start native provider/read projection and the required raw journal."""
    global _journal, _processor
    if _journal is not None:
        if not _journal.healthy:
            raise CaptureUnavailable("TRAJECTORY_CAPTURE_UNAVAILABLE")
        return _journal
    from openjiuwen.extensions.observability.config import ObservabilityConfig
    from openjiuwen.harness.observability import acquire_observability
    from jiuwenswarm.observability.config import load_trajectory_store_settings
    from jiuwenswarm.observability.runtime import start_trajectory_runtime, _get_core_span_record_processor
    root = Path(root)
    journal = LosslessTrajectoryJournal(root / "raw")
    processor = _get_core_span_record_processor()
    try:
        acquire_observability(ObservabilityConfig(enabled=True, exporter="file", service_name="jiuwenswarm-m1",
            traces_dir=str(root / "traces"), sample_rate=1.0, attribute_value_max_length=4 * 1024 * 1024))
        start_trajectory_runtime(dataclasses.replace(load_trajectory_store_settings(), enabled=True,
            discard_final_span_frames=False))
        processor.register_consumer(journal)
    except Exception:
        journal.close()
        raise CaptureUnavailable("TRAJECTORY_INITIALIZATION_FAILED") from None
    _journal, _processor = journal, processor
    return journal


def capture_healthy():
    return _journal is not None and _journal.healthy


def stop_native_capture():
    global _journal, _processor
    if _journal is None:
        return
    _processor.unregister_consumer(_journal)
    _journal.close()
    _journal = _processor = None
    from jiuwenswarm.observability.runtime import shutdown_trajectory_runtime
    from openjiuwen.harness.observability import release_observability
    if not shutdown_trajectory_runtime():
        raise CaptureUnavailable("TRAJECTORY_DRAIN_FAILED")
    release_observability()
