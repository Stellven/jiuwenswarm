"""Finite public CC workbench projection; no workbench or Root capabilities.

An installation publisher must deliberately disclose this closed public schema.
Never point this adapter at a workbench record root, history export or ledger.
The web process cannot enter library_operator (which requires OS root). Human
actions require a separately installed authenticated operator broker and remain
unavailable here until that protected integration exists.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

MAX_PUBLIC_BYTES = 2 * 1024 * 1024
HASH = re.compile(r"[a-f0-9]{64}")


class ProjectionError(ValueError):
    pass


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ProjectionError("Public projection has unsupported fields")


def _text(value, *, nullable=False, limit=4096):
    if nullable and value is None:
        return
    if not isinstance(value, str) or len(value) > limit:
        raise ProjectionError("Public text exceeds its finite contract")


def _hash(value, *, nullable=False):
    if nullable and value is None:
        return
    if not isinstance(value, str) or not HASH.fullmatch(value):
        raise ProjectionError("Exact candidate hash is required")


def _rows(value, limit):
    if not isinstance(value, list) or len(value) > limit:
        raise ProjectionError("Public collection exceeds its finite contract")
    return value


def _gate(value, *, revision=False):
    _fields(value, "allowed blocker revision" if revision and isinstance(value, dict) and 'revision' in value else "allowed blocker")
    if type(value["allowed"]) is not bool:
        raise ProjectionError("Invalid action gate")
    _text(value["blocker"], nullable=True)
    if 'revision' in value:
        _hash(value['revision'])


def _ref(value):
    _fields(value, "id sha256")
    _text(value["id"])
    _hash(value["sha256"])


def validate_publication(value, *, workspace_id=None):
    """Reject accidental private/raw fields instead of recursively forwarding JSON."""
    scoped = isinstance(value, dict) and 'workspace_id' in value
    _fields(value, "workspace_id snapshot candidates" if scoped else "snapshot candidates")
    if scoped:
        _text(value['workspace_id'], limit=256)
        if not value['workspace_id']:
            raise ProjectionError('Public workspace identity is required')
    if workspace_id is not None and (not scoped or value['workspace_id'] != workspace_id):
        raise ProjectionError('Public workspace differs from fixed startup workspace')
    view = value["snapshot"]
    _fields(view, "schema_version revision generated_at availability blocker targets runs nodes")
    if view["schema_version"] != "1":
        raise ProjectionError("Unsupported CC publication version")
    for key in ("revision", "availability"):
        _text(view[key])
    for key in ("generated_at", "blocker"):
        _text(view[key], nullable=True)
    targets = {}
    for row in _rows(view["targets"], 64):
        _fields(row, "id name parent_hash active_hash run")
        for key in ("id", "name"):
            _text(row[key])
        _hash(row["parent_hash"], nullable=True)
        _hash(row["active_hash"], nullable=True)
        _gate(row["run"], revision=True)
        if row["id"] in targets:
            raise ProjectionError("Duplicate target")
        targets[row["id"]] = row
    runs = {}
    for row in _rows(view["runs"], 256):
        _fields(row, "id target_id stage status blockers budget activity")
        for key in ("id", "target_id", "stage", "status"):
            _text(row[key])
        if row["target_id"] not in targets or row["id"] in runs:
            raise ProjectionError("Run target or identity is unavailable")
        runs[row["id"]] = row
        for blocker in _rows(row["blockers"], 64):
            _text(blocker)
        budget = row["budget"]
        _fields(budget, "elapsed_seconds limit_seconds setup_calls diagnosis_calls proposal_calls generation_call_limit cost currency")
        for key, number in budget.items():
            if key == "currency":
                _text(number, nullable=True, limit=16)
            elif number is not None and (type(number) not in (int, float) or not math.isfinite(number) or number < 0 or number > 1e12):
                raise ProjectionError("Invalid measured budget")
            elif key.endswith('calls') or key == 'generation_call_limit':
                if number is not None and type(number) is not int:
                    raise ProjectionError("Call count must be a measured integer")
        for event in _rows(row["activity"], 512):
            _fields(event, "id at stage status summary")
            for item in event.values():
                _text(item)
    nodes = {}
    for row in _rows(view["nodes"], 512):
        fields = "id target_id run_id parent_id hash label evaluation_status admission_status activation_status correctness speed noise evidence_refs operator_receipts admit activate"
        if scoped or 'security_status' in row:
            fields += ' security_status'
        _fields(row, fields)
        security = row.get('security_status')
        if security is not None:
            _text(security, limit=64)
        if security is not None and security not in {'NOT_APPLICABLE', 'UNQUALIFIED', 'SECURITY_DEFERRED', 'QUALIFIED'}:
            raise ProjectionError('Unsupported capsule security status')
        generated = row['parent_id'] is not None or row['run_id'] is not None
        if generated and security == 'NOT_APPLICABLE':
            raise ProjectionError('Generated capsules require a security disposition')
        for key in ("id", "target_id", "label", "evaluation_status", "admission_status", "activation_status"):
            _text(row[key])
        for key in ("run_id", "parent_id", "correctness", "speed", "noise"):
            _text(row[key], nullable=True)
        _hash(row["hash"])
        if row["id"] in nodes or row["target_id"] not in targets:
            raise ProjectionError("Candidate target or identity is unavailable")
        if row["run_id"] is not None and (row["run_id"] not in runs or runs[row["run_id"]]["target_id"] != row["target_id"]):
            raise ProjectionError("Candidate run differs")
        for ref in _rows(row["evidence_refs"], 128):
            _ref(ref)
        for receipt in _rows(row['operator_receipts'], 64):
            _fields(receipt, 'action actor at receipt_ref')
            if receipt['action'] not in ('admit', 'activate'):
                raise ProjectionError('Unknown human receipt action')
            _text(receipt['actor']); _text(receipt['at']); _ref(receipt['receipt_ref'])
        _gate(row["admit"])
        _gate(row["activate"])
        if generated and security in {'UNQUALIFIED', 'SECURITY_DEFERRED'} and (
                row['admission_status'] != 'unadmitted' or row['activation_status'] != 'inactive'
                or row['operator_receipts'] or row['admit']['allowed'] or row['activate']['allowed']):
            raise ProjectionError('Unqualified development capsules cannot claim Library standing')
        nodes[row["id"]] = row
    for row in nodes.values():
        if row["parent_id"] is not None and (row["parent_id"] not in nodes or nodes[row["parent_id"]]["target_id"] != row["target_id"]):
            raise ProjectionError("Candidate parent differs")
        seen = {row["id"]}
        current = row
        while current["parent_id"] is not None:
            current = nodes[current["parent_id"]]
            if current["id"] in seen:
                raise ProjectionError("Capsule lineage is cyclic")
            seen.add(current["id"])
    captured = set()
    for row in _rows(value["candidates"], 512):
        _fields(row, "node_id candidate_hash path parent_code candidate_code rationale blocker")
        for key in ("node_id", "path"):
            _text(row[key])
        _hash(row["candidate_hash"])
        if row["node_id"] in captured or row["node_id"] not in nodes or nodes[row["node_id"]]["hash"] != row["candidate_hash"]:
            raise ProjectionError("Captured candidate identity differs")
        captured.add(row["node_id"])
        for key in ("parent_code", "candidate_code"):
            _text(row[key], nullable=True, limit=262144)
        if row["candidate_code"] is not None and hashlib.sha256(row["candidate_code"].encode("utf-8")).hexdigest() != row["candidate_hash"]:
            raise ProjectionError("Captured candidate bytes differ from exact hash")
        parent_id = nodes[row['node_id']]['parent_id']
        parent_hash = nodes[parent_id]['hash'] if parent_id else row['candidate_hash']
        if row['parent_code'] is not None and hashlib.sha256(row['parent_code'].encode('utf8')).hexdigest() != parent_hash:
            raise ProjectionError('Captured parent bytes differ from lineage hash')
        for key in ("rationale", "blocker"):
            _text(row[key], nullable=True)
    return value


def unavailable(reason):
    return {"schema_version": "1", "revision": "unavailable", "generated_at": None,
            "availability": "BLOCKED", "blocker": reason, "targets": [], "runs": [], "nodes": []}


def _root_ancestors(path):
    for parent in path.parents:
        meta = parent.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != 0 or meta.st_mode & 0o022:
            raise ProjectionError('Public CC publication ancestry custody differs')


def _readonly_mount(path, text):
    if len(text.encode('utf8')) > 1024 * 1024:
        return False
    wanted = PurePosixPath(str(path))
    covering = []
    for line in text.splitlines():
        fields = line.split(' - ', 1)[0].split()
        if len(fields) < 6:
            return False
        mount = PurePosixPath(re.sub(r'\\([0-7]{3})', lambda match: chr(int(match[1], 8)), fields[4]))
        if mount == wanted or mount in wanted.parents:
            covering.append((len(mount.parts), fields[5].split(','), mount))
    if not covering:
        return False
    depth = max(row[0] for row in covering)
    matches = [(flags, mount) for size, flags, mount in covering if size == depth]
    return (len(matches) == 1 and matches[0][1] in {wanted, wanted.parent}
            and 'ro' in matches[0][0] and 'rw' not in matches[0][0])


class CcRsiProjection:
    def __init__(self, publication_path=None, *, workspace_id=None):
        self.path = publication_path
        self.workspace_id = workspace_id if workspace_id is not None else os.environ.get('JIUWENSWARM_CC_RSI_WORKSPACE')

    def _read(self):
        if not self.path:
            raise ProjectionError("Public CC publisher is not installed. Protected runtime records are not browser-readable.")
        _text(self.workspace_id, limit=256)
        if not self.workspace_id:
            raise ProjectionError('Fixed startup CC workspace is not configured')
        path = Path(self.path)
        if not path.is_absolute() or '..' in path.parts:
            raise ProjectionError("Public CC publication path must be absolute")
        # Installed Linux publisher owns this file; web process has read-only
        # access. Refuse symlinks, hardlinks and app-writable publications.
        if os.name != "posix":
            raise ProjectionError("Protected public CC publisher requires the installed Unix runtime")
        _root_ancestors(path)
        if not _readonly_mount(path, Path('/proc/self/mountinfo').read_text(encoding='utf8')):
            raise ProjectionError('Public CC publication requires an explicit read-only mount')
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            meta = os.fstat(fd)
            if not stat.S_ISREG(meta.st_mode) or meta.st_nlink != 1 or meta.st_uid != 0 or meta.st_mode & 0o022 or meta.st_size > MAX_PUBLIC_BYTES:
                raise ProjectionError("Public CC publication custody differs")
            with os.fdopen(fd, "rb", closefd=False) as stream:
                raw = stream.read(MAX_PUBLIC_BYTES + 1)
            if len(raw) > MAX_PUBLIC_BYTES:
                raise ProjectionError("Public CC publication exceeds finite limit")
            return validate_publication(json.loads(raw), workspace_id=self.workspace_id)
        finally:
            os.close(fd)

    def snapshot(self, params):
        try:
            view = self._read()["snapshot"]
        except ProjectionError as error:
            return unavailable(str(error))
        except OSError:
            return unavailable("Public CC publication cannot be read. Check the installed read-only mount and app file permissions.")
        except ValueError:
            return unavailable("Public CC publication is invalid. Republish the approved finite view; no private records were exposed.")
        # Publication cannot grant web actions. An installed broker must first
        # authenticate the human and independently rerun the real Library gates.
        for row in view["targets"]:
            row["run"] = {"allowed": False, "blocker": "Authenticated finite run broker is not installed."}
        for row in view["nodes"]:
            for action in ("admit", "activate"):
                row[action] = {"allowed": False, "blocker": "Authenticated human operator broker is not installed."}
        return view

    def candidate(self, params):
        if set(params) - {"node_id", "candidate_hash", "session_id", "_rsi_session_id"}:
            raise ProjectionError("Only an exact candidate identity may be requested")
        _text(params.get("node_id"))
        _hash(params.get("candidate_hash"))
        publication = self._read()
        for row in publication["candidates"]:
            if row["node_id"] == params["node_id"] and row["candidate_hash"] == params["candidate_hash"]:
                return row
        raise ProjectionError("Captured code for this exact candidate is unavailable")

    def operator_action(self, params):
        raise ProjectionError("Authenticated human operator broker is not installed. Use the protected finite Library operator; the web process cannot assume OS root.")

    def run_start(self, params):
        raise ProjectionError("Authenticated finite run broker is not installed. No model call was made.")
