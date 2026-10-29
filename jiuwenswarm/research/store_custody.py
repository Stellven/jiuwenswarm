"""Root-broker store access through a fixed, unprivileged native writer.

SQLite, WAL and captured artifact files are always created as the product UID.
The private inherited pipes are absent from every generated-code child.
"""
from __future__ import annotations
import hashlib
import json
import logging
import os
import re
import select
import stat
import struct
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from .bridge import BridgeError
from .router_client import MAX_IPC_FRAME_BYTES, encode_frame


def _exact(stream, count):
    parts = []
    while count:
        part = stream.read(count)
        if not part:
            raise BridgeError("AUDIT_UNAVAILABLE")
        parts.append(part)
        count -= len(part)
    return b"".join(parts)


def _read(stream):
    size = struct.unpack("!I", _exact(stream, 4))[0]
    if not 0 < size <= MAX_IPC_FRAME_BYTES:
        raise BridgeError("AUDIT_UNAVAILABLE")
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result
    return json.loads(_exact(stream, size), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))


class CustodyStore:
    def __init__(self, state, transfers, *, environment=None, uid=10001, gid=10001, input_root='/workspace/input',
                 scientific_receipt_publisher=None):
        if os.geteuid() != 0:
            raise BridgeError("AUDIT_UNAVAILABLE")
        self.transfers = Path(transfers)
        self.transfers.mkdir(mode=0o710, parents=True, exist_ok=True)
        if self.transfers.is_symlink():
            raise BridgeError("AUDIT_UNAVAILABLE")
        os.chown(self.transfers, 0, gid)
        self.transfers.chmod(0o710)
        self.gid = gid
        self.state = Path(state).resolve()
        self.lock = threading.Lock()
        self._scientific_receipt_publisher = scientific_receipt_publisher
        def identity():
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
        self.worker = subprocess.Popen([sys.executable, "-m", "jiuwenswarm.research.store_custody",
            "--worker", str(Path(state)), str(self.transfers), str(input_root)], env=environment,
            # Keep stdout exclusively framed; safe refusal diagnostics use the
            # existing protected parent's stderr sink, without another log file.
            preexec_fn=identity, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=None,
            close_fds=True)
        os.set_blocking(self.worker.stdin.fileno(), False)
        os.set_blocking(self.worker.stdout.fileno(), False)

    def _call(self, operation, args, kwargs=None):
        with self.lock:
            try:
                deadline = time.monotonic() + 30
                frame = memoryview(encode_frame({"operation": operation, "args": list(args), "kwargs": kwargs or {}}))
                while frame:
                    if not select.select([], [self.worker.stdin.fileno()], [], max(0, deadline-time.monotonic()))[1]:
                        raise BridgeError("AUDIT_UNAVAILABLE")
                    frame = frame[os.write(self.worker.stdin.fileno(), frame):]
                def read_exact(count):
                    chunks = []
                    while count:
                        if not select.select([self.worker.stdout.fileno()], [], [], max(0, deadline-time.monotonic()))[0]:
                            raise BridgeError("AUDIT_UNAVAILABLE")
                        chunk = os.read(self.worker.stdout.fileno(), count)
                        if not chunk:
                            raise BridgeError("AUDIT_UNAVAILABLE")
                        chunks.append(chunk)
                        count -= len(chunk)
                    return b"".join(chunks)
                size = struct.unpack("!I", read_exact(4))[0]
                if not 0 < size <= MAX_IPC_FRAME_BYTES:
                    raise BridgeError("AUDIT_UNAVAILABLE")
                import io
                value = _read(io.BytesIO(struct.pack("!I", size) + read_exact(size)))
                if (operation == 'attempt_resource_disposition'
                        and value == {'error':'FROZEN_RESOURCE_INVENTORY_MISMATCH'}):
                    from .contracts import ResearchError
                    raise ResearchError('attempt_resources',
                        'Supplied resource inventory differs from the original frozen plan')
                if not isinstance(value, dict) or set(value) != {"result"}:
                    raise BridgeError("AUDIT_UNAVAILABLE")
                return value["result"]
            except (OSError, ValueError):
                raise BridgeError("AUDIT_UNAVAILABLE") from None

    def put_blob(self, data, **kwargs):
        if not isinstance(data, bytes):
            raise TypeError("exact captured bytes required")
        path = self.transfers / uuid.uuid4().hex
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o640)
        try:
            os.fchown(descriptor, 0, self.gid)
            os.fchmod(descriptor, 0o640)
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        finally:
            os.close(descriptor)
        try:
            return self._call("put_blob", [path.name, hashlib.sha256(data).hexdigest()], kwargs)
        finally:
            path.unlink()

    def read_blob(self, ref):
        value = self._call("read_blob", [ref])
        digest = ref["sha256"]
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise BridgeError("AUDIT_UNAVAILABLE")
        path = self.state / "artifacts" / "sha256" / digest[:2] / digest
        if value != {"path": str(path)} or any(p.is_symlink() for p in (path, *path.parents)):
            raise BridgeError("AUDIT_UNAVAILABLE")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise BridgeError("AUDIT_UNAVAILABLE")
            data = stream.read()
        if hashlib.sha256(data).hexdigest() != ref["sha256"]:
            raise BridgeError("AUDIT_UNAVAILABLE")
        return data

    def read_record(self, ref, **kwargs):
        return self._call("read_record", [ref], kwargs)

    def record_kind(self, ref):
        return self._call("record_kind", [ref])

    def validate_evaluation_executor_binding(self, request, response):
        """Read-only private ownership check; no registration, claim or effect."""
        return self._call("validate_evaluation_executor_binding", [request, response])

    def validate_invocation_preparation(self, preparation_ref, response):
        return self._call('validate_invocation_preparation', [preparation_ref, response])

    def attempt_resource_disposition(self, parent_ref, *, resource_inventory_ref=None):
        from .attempt_resources import AttemptResourceDisposition
        value = self._call('attempt_resource_disposition', [parent_ref, resource_inventory_ref])
        if type(value) is not dict or set(value) != {'parent_ref','parent_identity','requires_broker','assignment_refs','resource_uses'}:
            raise BridgeError('AUDIT_UNAVAILABLE')
        return AttemptResourceDisposition(tuple(value['parent_ref']),tuple(value['parent_identity']),
            value['requires_broker'],tuple(tuple(row) for row in value['assignment_refs']),
            tuple(tuple(row) for row in value['resource_uses']))

    def resolve_original_run_inputs(self,parent_ref):
        from .run_inputs import OriginalRunInputInventory
        value=self._call('resolve_original_run_inputs',[parent_ref])
        return None if value is None else OriginalRunInputInventory.from_record(value)

    async def publish_scientific_start_receipt(self, kind, record, preparation_ref):
        if kind not in {'scientific-attempt-preflight','scientific-attempt-activation'} or self._scientific_receipt_publisher is None:
            raise BridgeError('SCIENTIFIC_RECEIPT_PUBLISHER_UNAVAILABLE')
        # This separately installed finite root-authenticated callback owns the
        # actual Runner/Store relationship. The inherited custody pipe retains
        # all existing generic capture/read duties; no public writer is added.
        return await self._scientific_receipt_publisher(kind, record, preparation_ref)

    def put_record(self, kind, record, **kwargs):
        return self._call("put_record", [kind, record], kwargs)

    def append_record(self, kind, record):
        return self._call("append_record", [kind, record])

    def close(self):
        self.worker.stdin.close()
        try:
            self.worker.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.worker.terminate()
            try:
                self.worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.worker.kill()
                self.worker.wait(timeout=5)
        self.worker.stdout.close()


def worker(state, transfers, input_root):
    from .state import SQLiteRunStore
    if os.geteuid() != 10001:
        raise BridgeError("AUDIT_UNAVAILABLE")
    store = SQLiteRunStore(state, input_root=input_root, recover=False)
    transfers = Path(transfers)
    try:
        while True:
            if not sys.stdin.buffer.peek(1):
                return
            request = _read(sys.stdin.buffer)
            try:
                if not isinstance(request, dict) or set(request) != {"operation", "args", "kwargs"}:
                    raise ValueError
                operation, args, kwargs = request["operation"], request["args"], request["kwargs"]
                allowed = {"read_record", "record_kind", "put_record", "append_record", "read_blob", "put_blob",
                           "validate_evaluation_executor_binding",'validate_invocation_preparation','attempt_resource_disposition',
                           'resolve_original_run_inputs'}
                if operation not in allowed or not isinstance(args, list) or not isinstance(kwargs, dict):
                    raise ValueError
                if operation == 'validate_invocation_preparation':
                    if len(args) != 2 or kwargs:
                        raise ValueError
                    from .invocation_start import validate_invocation_preparation
                    result = validate_invocation_preparation(store, *args)
                elif operation == 'attempt_resource_disposition':
                    if len(args) != 2 or kwargs:
                        raise ValueError
                    from dataclasses import asdict
                    from .attempt_resources import attempt_resource_disposition
                    result = asdict(attempt_resource_disposition(store,args[0],resource_inventory_ref=args[1]))
                elif operation == 'resolve_original_run_inputs':
                    if len(args) != 1 or kwargs:
                        raise ValueError
                    from .run_inputs import resolve_original_run_inputs
                    provenance=resolve_original_run_inputs(store,args[0])
                    result=None if provenance is None else provenance.record
                elif operation == 'validate_evaluation_executor_binding':
                    if len(args) != 2 or kwargs:
                        raise ValueError
                    from .evaluation_authority import validate_evaluation_executor_binding
                    result = validate_evaluation_executor_binding(store, *args)
                elif operation == "put_blob":
                    name, digest = args
                    if not re.fullmatch(r"[a-f0-9]{32}", name):
                        raise ValueError
                    fd = os.open(transfers / name, os.O_RDONLY | os.O_NOFOLLOW)
                    try:
                        meta = os.fstat(fd)
                        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != 0 or meta.st_nlink != 1 or stat.S_IMODE(meta.st_mode) != 0o640:
                            raise ValueError
                        with os.fdopen(fd, "rb", closefd=False) as source:
                            raw = source.read()
                    finally:
                        os.close(fd)
                    if hashlib.sha256(raw).hexdigest() != digest:
                        raise ValueError
                    result = store.put_blob(raw, **kwargs)
                elif operation == "read_blob":
                    store.read_blob(*args, **kwargs)
                    result = {"path": str(store.blobs.path_for(args[0]["sha256"]))}
                else:
                    result = getattr(store, operation)(*args, **kwargs)
                response = {"result": result}
            except Exception as error:
                from .contracts import ResearchError
                if (isinstance(request,dict) and request.get('operation')=='attempt_resource_disposition'
                        and isinstance(error,ResearchError) and error.code=='attempt_resources'
                        and error.message=='Supplied resource inventory differs from the original frozen plan'):
                    response={'error':'FROZEN_RESOURCE_INVENTORY_MISMATCH'}
                else:
                    operations = {'read_record', 'record_kind', 'put_record', 'append_record', 'read_blob', 'put_blob',
                        'validate_evaluation_executor_binding', 'validate_invocation_preparation',
                        'attempt_resource_disposition', 'resolve_original_run_inputs'}
                    codes = {'budget_exhausted', 'executor_preparation_authorization', 'attempt_resources',
                        'run_inputs', 'contract_invalid', 'evidence_unavailable', 'integrity_fault',
                        'input_authority', 'check_binding', 'AUDIT_UNAVAILABLE'}
                    types = {'ResearchError', 'ContractError', 'BridgeError', 'ValueError', 'TypeError',
                        'KeyError', 'UnicodeError', 'UnicodeDecodeError', 'OSError', 'PermissionError',
                        'FileNotFoundError', 'RuntimeError', 'TimeoutError', 'IntegrityError', 'OperationalError'}
                    operation = request.get('operation') if isinstance(request, dict) else None
                    code = getattr(error, 'code', None)
                    error_type = type(error).__name__
                    logging.getLogger(__name__).warning(
                        'custody_validation_refused operation=%s code=%s type=%s',
                        operation if type(operation) is str and operation in operations else 'invalid_operation',
                        code if type(code) is str and code in codes else 'unclassified',
                        error_type if error_type in types else 'Exception')
                    response = {"error": "AUDIT_UNAVAILABLE"}
            sys.stdout.buffer.write(encode_frame(response))
            sys.stdout.buffer.flush()
    finally:
        store.close()


if __name__ == "__main__":
    if len(sys.argv) != 5 or sys.argv[1] != "--worker":
        raise SystemExit(2)
    worker(sys.argv[2], sys.argv[3], sys.argv[4])
