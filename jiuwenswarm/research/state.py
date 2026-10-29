"""Protected SQLite authority and exact-byte storage.

Blobs are durable before references are published. Only a committed acceptance
transaction grants scheduler eligibility; candidate files and projections do not.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import sqlite3
import stat
import threading
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from .contracts import validate
from .contracts.types import Ref, ResearchError


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                          separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError) as exc:
        raise ResearchError("invalid_json", "Only finite JSON data can be captured") from exc


def _fsync_directory(path: Path) -> None:
    if os.name == "posix":
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    def path_for(self, digest: str) -> Path:
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise ResearchError("integrity_fault", "Invalid content digest")
        path = self.root / digest[:2] / digest
        if not path.resolve().is_relative_to(self.root):
            raise ResearchError("integrity_fault", "Artifact path escapes protected root")
        return path

    def put(self, data: bytes) -> str:
        if not isinstance(data, bytes):
            raise TypeError("ArtifactStore accepts exact bytes only")
        digest = hashlib.sha256(data).hexdigest()
        path = self.path_for(digest)
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if path.exists():
            self.read(digest)
            return digest
        temporary = path.parent / (".capture-" + uuid.uuid4().hex)
        try:
            with temporary.open("xb") as stream:
                if os.name == "posix":
                    os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            # A same-digest concurrent capture has identical verified bytes.
            if path.exists():
                self.read(digest)
            else:
                os.replace(temporary, path)
                _fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)
        return digest

    def read(self, digest: str) -> bytes:
        try:
            data = self.path_for(digest).read_bytes()
        except OSError as exc:
            raise ResearchError("evidence_unavailable", "Captured bytes are unavailable") from exc
        if hashlib.sha256(data).hexdigest() != digest:
            raise ResearchError("integrity_fault", "Captured bytes no longer match their digest")
        return data


_DDL = """
CREATE TABLE IF NOT EXISTS artifacts (
 id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, media_type TEXT NOT NULL,
 provenance TEXT, captured_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS records (
 id TEXT PRIMARY KEY REFERENCES artifacts(id), kind TEXT NOT NULL,
 run_id TEXT, node_id TEXT, attempt_id TEXT, captured_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS records_kind_id ON records(kind,id);
CREATE TABLE IF NOT EXISTS requests (
 account_id TEXT NOT NULL, request_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
 run_id TEXT NOT NULL, PRIMARY KEY(account_id,request_id));
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL, workspace_id TEXT NOT NULL,
 state TEXT NOT NULL, revision INTEGER NOT NULL, submission TEXT NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, reason TEXT);
CREATE TABLE IF NOT EXISTS nodes (
 run_id TEXT NOT NULL REFERENCES runs(id), node_id TEXT NOT NULL,
 state TEXT NOT NULL, attempt_id TEXT, reason TEXT,
 PRIMARY KEY(run_id,node_id));
CREATE TABLE IF NOT EXISTS attempts (
 run_id TEXT NOT NULL REFERENCES runs(id), node_id TEXT NOT NULL, subnode_id TEXT NOT NULL,
 attempt_id TEXT NOT NULL, contract_ref TEXT NOT NULL, state TEXT NOT NULL,
 PRIMARY KEY(run_id,node_id,subnode_id,attempt_id));
CREATE TABLE IF NOT EXISTS acceptance (
 run_id TEXT NOT NULL REFERENCES runs(id), node_id TEXT NOT NULL, attempt_id TEXT NOT NULL,
 subnode_id TEXT NOT NULL, port TEXT NOT NULL, artifact_ref TEXT NOT NULL,
 commit_id TEXT NOT NULL, PRIMARY KEY(run_id,node_id,attempt_id,subnode_id,port));
CREATE TABLE IF NOT EXISTS cancellation (
 account_id TEXT NOT NULL, request_id TEXT NOT NULL, run_id TEXT NOT NULL,
 state TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(account_id,request_id));
CREATE TABLE IF NOT EXISTS uploads (
 id TEXT PRIMARY KEY, account_id TEXT NOT NULL, scope_id TEXT NOT NULL,
 record TEXT NOT NULL, original_path TEXT NOT NULL, extracted_path TEXT);
CREATE TABLE IF NOT EXISTS upload_uses (
 run_id TEXT NOT NULL, upload_id TEXT NOT NULL REFERENCES uploads(id),
 PRIMARY KEY(run_id,upload_id));
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS model_calls (
 run_id TEXT NOT NULL, invocation_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 node_id TEXT NOT NULL, call_id TEXT NOT NULL UNIQUE, claim_ref TEXT NOT NULL,
 PRIMARY KEY(run_id,invocation_id,ordinal));
CREATE TABLE IF NOT EXISTS tool_calls (
 run_id TEXT NOT NULL, invocation_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
 node_id TEXT NOT NULL, claim_ref TEXT NOT NULL,
 PRIMARY KEY(run_id,invocation_id,ordinal));
"""


class SQLiteRunStore:
    def __init__(self, root: str | Path, *, db_path: str | Path | None = None,
                 artifact_root: str | Path | None = None, input_root: str | Path | None = None,
                 recover: bool = False, fault: Callable[[str], None] | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = Path(db_path) if db_path else self.root / "state" / "research.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.blobs = ArtifactStore(artifact_root or self.root / "artifacts" / "sha256")
        self.input_root = Path(input_root or self.root / "inputs").resolve()
        self.input_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._lock = threading.RLock()
        self._fault = fault or (lambda _: None)
        self._material_index_records = {}
        self._material_index_sets = None
        self.connection = sqlite3.connect(self.db_path, timeout=5, isolation_level=None,
                                          check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=FULL")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.executescript(_DDL)
        if os.name == "posix":
            self.db_path.chmod(0o600)
        if recover:
            self.recover_interrupted()

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                yield self.connection
                self._fault("before_commit")
                self.connection.execute("COMMIT")
            except BaseException:
                self.connection.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self.connection.close()

    def _capture(self, data: bytes, *, record_id: str | None, media_type: str,
                 provenance: Any = None, kind: str | None = None,
                 scope: Mapping[str, Any] | None = None) -> Ref:
        digest = self.blobs.put(data)
        self._fault("after_blob_fsync")
        identity = record_id or "blob:" + digest
        if not identity or not isinstance(identity, str):
            raise ResearchError("validation", "A captured identity must be nonempty")
        now = utc_now()
        with self.transaction() as db:
            existing = db.execute("SELECT sha256 FROM artifacts WHERE id=?", (identity,)).fetchone()
            if existing and existing["sha256"] != digest:
                raise ResearchError("identity_conflict", "Immutable identity already names other bytes")
            db.execute("INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?)",
                       (identity, digest, media_type, None if provenance is None else json_bytes(provenance).decode(), now))
            if kind:
                scope = scope or {}
                db.execute("INSERT OR IGNORE INTO records VALUES(?,?,?,?,?,?)",
                           (identity, kind, scope.get("run_id"), scope.get("node_id"), scope.get("attempt_id"), now))
        return {"id": identity, "sha256": digest}

    def put_blob(self, data: bytes, *, media_type: str = "application/octet-stream",
                 provenance: Any = None, record_id: str | None = None) -> Ref:
        return self._capture(data, record_id=record_id, media_type=media_type, provenance=provenance)

    def read_blob(self, ref: Ref) -> bytes:
        validate("Ref", ref)
        with self._lock:
            row = self.connection.execute("SELECT sha256 FROM artifacts WHERE id=?", (ref["id"],)).fetchone()
        if row is None:
            raise ResearchError("evidence_unavailable", "Unknown captured reference")
        if row["sha256"] != ref["sha256"]:
            raise ResearchError("integrity_fault", "Reference identity/digest mismatch")
        return self.blobs.read(ref["sha256"])

    def put_record(self, contract_id: str, record: Mapping[str, Any], *,
                   record_id: str | None = None, scope: Mapping[str, Any] | None = None) -> Ref:
        validate(contract_id, dict(record))
        if record.get("synthetic") is True:
            raise ResearchError("synthetic_evidence", "Examples cannot become production records")
        return self._capture(json_bytes(record), record_id=record_id,
                             media_type="application/json", kind=contract_id, scope=scope or record)

    def append_record(self, kind: str, record: Mapping[str, Any]) -> Ref:
        # Protected host capture also retains intermediate/failure events that are
        # not complete public contract records. They confer no acceptance.
        return self._capture(json_bytes(record), record_id=record.get("id") or kind + ":" + uuid.uuid4().hex,
                             media_type="application/json", kind=kind, scope=record)

    def evaluation_binding(self,run_id):
        rows=list(self.iter_records(run_id=run_id,kinds=('evaluation-run-binding',)))
        if len(rows)>1:raise ResearchError('evaluation_identity','Ambiguous protected evaluation binding')
        return rows[0] if rows else None

    def mark_evaluation_material(self,run_id,ref):
        binding=self.evaluation_binding(run_id)
        if binding and binding['record'].get('invalid_for_product') is True:
            self.read_blob(ref)
            identity=hashlib.sha256(json_bytes([run_id,ref])).hexdigest()
            self.append_record('evaluation-material',{'id':'evaluation-material:'+identity,'run_id':run_id,
                'artifact_ref':ref,'binding_ref':binding['ref'],'invalid_for_product':True})

    def warm_product_material_index(self):
        """Read immutable origin markers once before publishing readiness."""
        self._product_material_index()

    def _product_material_index(self):
        """Refresh exact marker metadata; reopen only previously unseen bytes.

        SQLite is reread on every use, including captures from other processes.
        Verified immutable markers may accumulate restrictions, never lose them.
        The cache is classification data only and cannot authorize acceptance.
        """
        kinds=('evaluation-material','calibration-material','evaluation-context-origin',
               'evaluation-output-origin','measurement-captured-output')
        def exact_refs(value):
            if isinstance(value,dict):
                if (set(value)=={'id','sha256'} and isinstance(value['id'],str) and value['id']
                        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256'])):
                    yield value
                else:
                    for nested in value.values():yield from exact_refs(nested)
            elif isinstance(value,(list,tuple)):
                for nested in value:yield from exact_refs(nested)
        with self._lock:
            rows=self.connection.execute('''SELECT r.id,r.kind,a.sha256 FROM records r
                LEFT JOIN artifacts a ON a.id=r.id WHERE r.kind IN (?,?,?,?,?)''',kinds).fetchall()
            missing=set(self._material_index_records)
            changed=self._material_index_sets is None
            for row in rows:
                identity=row['id'];pin=(row['kind'],row['sha256'])
                cached=self._material_index_records.get(identity)
                if cached is not None:
                    if cached[:2]!=pin:
                        raise ResearchError('integrity_fault','An immutable material-origin marker changed its indexed identity or kind')
                    missing.discard(identity)
                else:
                    value=self.read_record({'id':identity,'sha256':row['sha256']})
                    self._material_index_records[identity]=(*pin,value)
                    self._material_index_sets=None
                    changed=True
            if missing:
                raise ResearchError('integrity_fault','An immutable material-origin marker disappeared from the protected index')
            if changed:
                records=tuple(self._material_index_records.values())
                prohibited={(value['artifact_ref']['id'],value['artifact_ref']['sha256'])
                    for kind,_,value in records if kind=='evaluation-material'}
                calibration={(value['artifact_ref']['id'],value['artifact_ref']['sha256'])
                    for kind,_,value in records if kind=='calibration-material' and value.get('calibration_only') is True}
                origins={(value['contract_ref']['id'],value['contract_ref']['sha256'])
                    for kind,_,value in records if kind=='evaluation-context-origin' and value.get('invalid_for_product') is True}
                for kind,_,value in records:
                    if kind not in {'evaluation-output-origin','measurement-captured-output'}:continue
                    contract=value.get('contract_ref')
                    if value.get('invalid_for_product') is True or contract and (contract['id'],contract['sha256']) in origins:
                        outputs=value.get('output_refs',value.get('artifact_ref',[]))
                        prohibited.update((ref['id'],ref['sha256']) for ref in exact_refs(outputs))
                self._material_index_sets=(frozenset(prohibited),frozenset(calibration),
                    frozenset(digest for _,digest in calibration))
            return self._material_index_sets

    def require_product_material(self,refs):
        prohibited,calibration,calibration_hashes=self._product_material_index()
        # IF016 indexed kinds are private. The ordinary scientific
        # evaluation-verdict remains a canonical product contract.
        private_kinds={
            'evaluation-runtime','evaluation-request','evaluation-node-context','evaluation-subnode-context',
            'evaluation-checking-basis','evaluation-scope','evaluation-assignment-grant','evaluation-call-claim',
            'evaluation-tool-claim','evaluation-event','evaluation-terminal','evaluation-export',
            'evaluation-invocation-observation','evaluation-deterministic-check-result','evaluation-review-context',
            'evaluation-verifier-assessment','evaluation-trial-measurement','evaluation-result','evaluation-failure',
            'evaluation-request-failure','evaluation-containment','evaluation-gate-record',
            'evaluation-recording-downstream-action','evaluation-context-origin','evaluation-output-origin',
            'evaluation-material','evaluation-run-binding'}
        def exact_refs(value):
            if isinstance(value,dict):
                if (set(value)=={'id','sha256'} and isinstance(value['id'],str) and value['id']
                        and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256'])):yield value
                else:
                    for nested in value.values():yield from exact_refs(nested)
            elif isinstance(value,(list,tuple)):
                for nested in value:yield from exact_refs(nested)
        def private_marker(value):
            if isinstance(value,dict):
                schema=value.get('schema')
                return (value.get('invalid_for_product') is True
                    or isinstance(schema,str) and schema.startswith('ai4r-evaluation-')
                    or any(private_marker(nested) for nested in value.values()))
            return isinstance(value,(list,tuple)) and any(private_marker(nested) for nested in value)
        queue=list(refs);seen=set()
        while queue:
            ref=queue.pop();validate('Ref',ref);identity=(ref['id'],ref['sha256'])
            if identity in seen:continue
            seen.add(identity)
            self.read_blob(ref)
            try:kind=self.record_kind(ref)
            except ResearchError as error:
                if error.code!='evidence_unavailable':raise
                kind=None
            if ref['sha256'] in calibration_hashes or kind=='calibration-material':
                raise ResearchError('calibration_only','Raw calibration-produced material cannot enter product intake, admission or RSI qualification')
            if identity in prohibited or kind in private_kinds:
                raise ResearchError('evaluation_only','Evaluation-produced material cannot enter product intake, admission or RSI qualification')
            # Exact independently admitted checking assets remain consumable by
            # existing Binder/Library rules. This does not make their raw case
            # evidence a generic resource or permit relabeling its bytes.
            raw=self.read_blob(ref)
            try:value=json.loads(raw.decode('utf-8'))
            except (ValueError,UnicodeError):
                if zipfile.is_zipfile(io.BytesIO(raw)):
                    # Classify the exported container itself. Its original
                    # source members acquire no new origin/hash restriction.
                    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                        if any(item.filename.casefold()=='evaluation_export.json' for item in archive.infolist()):
                            # The reserved private export name classifies the
                            # container even for malformed/ambiguous manifests.
                            # No untrusted member needs decompression to deny it.
                            raise ResearchError('evaluation_only','Claimed private evaluation export cannot become product material')
                continue
            if kind=='checking-asset-admission':
                with self._lock:
                    exists=self.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checking_asset_admissions'").fetchone()
                    indexed=self.connection.execute('SELECT receipt_ref FROM checking_asset_admissions').fetchall() if exists else []
                if (isinstance(value,dict) and value.get('status')=='admitted'
                        and any(json.loads(row['receipt_ref'])==ref for row in indexed)):continue
                raise ResearchError('calibration_only','Unpublished checking-asset receipts do not grant final admission material eligibility')
            if private_marker(value):
                raise ResearchError('evaluation_only','Private evaluation evidence cannot become product material')
            for nested in exact_refs(value):
                if (nested['id'],nested['sha256']) in calibration or nested['sha256'] in calibration_hashes:
                    raise ResearchError('calibration_only','Wrapped raw calibration evidence cannot become product material')
                with self._lock:known=self.connection.execute('SELECT 1 FROM artifacts WHERE id=?',(nested['id'],)).fetchone()
                if known:queue.append(nested)

    def capture_record_file(self, relative: str, raw: bytes, *, media_type='application/octet-stream', kind=None, scope=None) -> Ref:
        """Write-once source records/ file and immutable artifact publication.

        Raw trace files stay artifacts; only JSON records receive a record kind.
        No file presence creates acceptance or allows an arbitrary absolute path.
        """
        from pathlib import PurePosixPath
        if not isinstance(relative,str) or not relative or not isinstance(raw,bytes):
            raise ResearchError('record_path','A safe records-relative path and exact bytes are required')
        path=PurePosixPath(relative)
        if (path.is_absolute() or '\\' in relative
            or any(part in {'.','..',''} or any(ord(char)<32 for char in part) for part in relative.split('/'))):
            raise ResearchError('record_path','A safe records-relative path and exact bytes are required')
        if kind is not None:
            try:json.loads(raw.decode('utf-8'))
            except (ValueError,UnicodeError) as error:raise ResearchError('record_capture','Indexed record files must contain JSON') from error
        with self._lock:
            root=self.root/'records';root.mkdir(mode=0o700,exist_ok=True)
            if root.is_symlink():raise ResearchError('record_path','Records root cannot be a symbolic link')
            target=root
            for part in path.parts[:-1]:
                target=target/part
                if target.is_symlink():raise ResearchError('record_path','Records ancestry cannot be a symbolic link')
                target.mkdir(mode=0o700,exist_ok=True)
            target=target/path.name
            self._fault('before_record_file_publish')
            temporary=target.parent/('.capture-'+uuid.uuid4().hex)
            try:
                descriptor=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                self._fault('before_record_file_link')
                try:os.link(temporary,target,follow_symlinks=False)
                except FileExistsError:
                    observed=target.lstat()
                    if target.is_symlink() or not stat.S_ISREG(observed.st_mode) or observed.st_nlink!=1 or target.read_bytes()!=raw:
                        raise ResearchError('identity_conflict','Write-once record path already contains unsafe or different bytes')
                _fsync_directory(target.parent)
            finally:
                temporary.unlink(missing_ok=True)
            return self._capture(raw,record_id=relative,media_type=media_type,kind=kind,scope=scope)

    def publish_capsule_record(self,observation_ref: Ref,completed: Mapping,*,decision_refs=(),assessment_refs=())->dict:
        """Append the gate-completed copy without modifying its raw capture.

        This optional publication is called only after durable gate work. Its
        caller logs failures and preserves them as missing evidence; no release
        decision reads this journal or any derived record.
        """
        original=self.read_record(observation_ref,contract_id='invocation-observation')
        validate('invocation-observation',dict(completed))
        gate_fields={'failure_class','error_fingerprint','check_result_refs','verifier_assessment_ref','human_answer_ref'}
        if (completed.get('failure_class') is None
            or {key:value for key,value in original.items() if key not in gate_fields}
              !={key:value for key,value in completed.items() if key not in gate_fields}):
            raise ResearchError('record_completion_invalid','Completed capture changed a runner-owned observation field')
        for ref in decision_refs:
            decision=self.read_record(ref,contract_id='gate-decision')
            if observation_ref not in decision['invocation_refs']:
                raise ResearchError('record_completion_invalid','Gate does not name this exact original observation')
        for ref in [*completed['check_result_refs'],*assessment_refs]:self.read_blob(ref)
        with self._lock:
            previous=[row['record'] for row in self.iter_records(run_id=original['run_id'],kinds=('capsule-run-record-link',))
                      if row['record']['observation_ref']==observation_ref]
            if previous:
                if len(previous)!=1 or self.read_record(previous[0]['completed_ref'])!=completed:
                    raise ResearchError('record_completion_invalid','A prior immutable completion differs')
                return previous[0]
            root=self.root/'records';root.mkdir(mode=0o700,exist_ok=True)
            journal=root/'records.jsonl'
            if root.is_symlink() or journal.is_symlink():raise ResearchError('record_journal_custody','Record journal is not a regular owned path')
            raw=json_bytes(dict(completed))+b'\n'
            existing=journal.read_bytes() if journal.exists() else b''
            matching=[line for line in existing.splitlines() if json.loads(line).get('id')==completed['id']]
            if matching and (len(matching)!=1 or matching[0]+b'\n'!=raw):
                raise ResearchError('record_completion_invalid','Journal already has a different completion identity')
            self._fault('before_capsule_record_append')
            if not matching:
                fd=os.open(journal,os.O_WRONLY|os.O_CREAT|os.O_APPEND|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(fd,'ab') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
                _fsync_directory(root)
            snapshot=journal.read_bytes();digest=hashlib.sha256(snapshot).hexdigest()
            relative='snapshots/'+digest+'/records.jsonl';snapshot_path=root/relative
            snapshot_path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            if not snapshot_path.exists():
                with snapshot_path.open('xb') as stream:stream.write(snapshot);stream.flush();os.fsync(stream.fileno())
                _fsync_directory(snapshot_path.parent)
            elif snapshot_path.is_symlink() or snapshot_path.read_bytes()!=snapshot:
                raise ResearchError('record_journal_custody','Immutable journal snapshot differs')
            snapshot_ref=self._capture(snapshot,record_id=relative,media_type='application/x-ndjson',kind='capsule-records-snapshot')
            completed_ref=self._capture(json_bytes(dict(completed)),record_id='completed:'+completed['id'],
                media_type='application/json',kind='capsule-run-record',scope=completed)
            link={'id':'completion-link:'+uuid.uuid4().hex,'run_id':original['run_id'],'node_id':original['node_id'],
                  'observation_ref':observation_ref,'completed_ref':completed_ref,'decision_refs':list(decision_refs),
                  'assessment_refs':list(assessment_refs),'records_snapshot_ref':snapshot_ref,'recorded_at':utc_now()}
            self.append_record('capsule-run-record-link',link)
            return link

    def read_record(self, ref: Ref, *, contract_id: str | None = None) -> dict:
        try:
            value = json.loads(self.read_blob(ref).decode("utf-8"))
        except (ValueError, UnicodeError) as exc:
            raise ResearchError("integrity_fault", "Reference is not a JSON record") from exc
        if not isinstance(value, dict):
            raise ResearchError("integrity_fault", "Reference is not an object record")
        if contract_id:
            validate(contract_id, value)
        return value

    def record_ref(self,record_id: str)->Ref:
        with self._lock:
            row=self.connection.execute('SELECT sha256 FROM artifacts WHERE id=?',(record_id,)).fetchone()
        if row is None:raise ResearchError('evidence_unavailable','Protected record identity is unavailable')
        ref={'id':record_id,'sha256':row['sha256']};self.read_blob(ref);return ref

    def record_kind(self, ref: Ref) -> str:
        """Read protected capture metadata for one verified immutable reference."""
        self.read_blob(ref)
        with self._lock:
            row = self.connection.execute(
                'SELECT r.kind FROM records r JOIN artifacts a ON a.id=r.id '
                'WHERE r.id=? AND a.sha256=?', (ref['id'], ref['sha256'])).fetchone()
        if row is None:
            raise ResearchError('evidence_unavailable', 'Reference has no protected record kind')
        return row['kind']

    def artifact_metadata(self,ref: Ref)->dict:
        self.read_blob(ref)
        with self._lock:
            row=self.connection.execute('SELECT media_type FROM artifacts WHERE id=? AND sha256=?',(ref['id'],ref['sha256'])).fetchone()
        return {'media_type':row['media_type']}

    def iter_records(self, *, run_id: str | None = None, kinds: tuple[str, ...] | None = None) -> Iterator[dict]:
        query = "SELECT r.*, a.sha256 FROM records r JOIN artifacts a ON a.id=r.id"
        where, args = [], []
        if run_id is not None:
            where.append("r.run_id=?")
            args.append(run_id)
        if kinds:
            where.append("r.kind IN (" + ",".join("?" for _ in kinds) + ")")
            args.extend(kinds)
        if where:
            query += " WHERE " + " AND ".join(where)
        query += " ORDER BY r.rowid"
        with self._lock:
            rows = self.connection.execute(query, args).fetchall()
        for row in rows:
            ref = {"id": row["id"], "sha256": row["sha256"]}
            yield {"kind": row["kind"], "ref": ref, "record": self.read_record(ref),
                   "captured_at": row["captured_at"]}

    def ref_index(self) -> dict[str, dict[str, str]]:
        """Protected launcher export; never interpret an opaque Ref ID as a path."""
        with self._lock:
            rows = self.connection.execute("SELECT id,sha256 FROM artifacts").fetchall()
        return {r["id"]: {"sha256": r["sha256"],
                          "path": self.blobs.path_for(r["sha256"]).relative_to(self.blobs.root).as_posix()}
                for r in rows}

    def claim_request(self, account_id: str, request_id: str, fingerprint: str, run_id: str) -> tuple[str, bool]:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM requests WHERE account_id=? AND request_id=?",
                             (account_id, request_id)).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise ResearchError("identity_conflict", "Request ID was reused with different content")
                return row["run_id"], False
            db.execute("INSERT INTO requests VALUES(?,?,?,?)", (account_id, request_id, fingerprint, run_id))
        return run_id, True

    def allocate_run(self, account_id: str, request_id: str, fingerprint: str, run_id: str,
                     workspace_id: str, submission: Mapping, upload_ids: tuple[str, ...] | list[str] = ()) -> tuple[dict, bool]:
        """Claim identity, allocate run and reserve live inputs in one transaction."""
        now = utc_now()
        with self.transaction() as db:
            prior = db.execute("SELECT * FROM requests WHERE account_id=? AND request_id=?",
                               (account_id, request_id)).fetchone()
            if prior:
                if prior["fingerprint"] != fingerprint:
                    raise ResearchError("identity_conflict", "Request identity names different content")
                return self.get_run(prior["run_id"], account_id=account_id), False
            for upload_id in upload_ids:
                row = db.execute("SELECT record FROM uploads WHERE id=? AND account_id=? AND scope_id=?",
                                 (upload_id, account_id, workspace_id)).fetchone()
                if not row or json.loads(row["record"])["status"] != "uploaded":
                    raise ResearchError("not_found", "A qualified upload is no longer live in this workspace")
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
                       (run_id, account_id, workspace_id, "pending", 1, json_bytes(submission).decode(), now, now, None))
            db.execute("INSERT INTO requests VALUES(?,?,?,?)", (account_id, request_id, fingerprint, run_id))
            db.executemany("INSERT INTO upload_uses VALUES(?,?)", [(run_id, u) for u in upload_ids])
        return self.get_run(run_id), True

    def publish_upload(self, record: Mapping, original: bytes, extracted: bytes | None) -> dict:
        record = dict(record)
        validate("client-upload", record)
        if (record["status"] != "uploaded" or record["size_bytes"] != len(original)
                or record["content_sha256"] != hashlib.sha256(original).hexdigest()
                or record["text_sha256"] != (hashlib.sha256(extracted).hexdigest() if extracted is not None else None)):
            raise ResearchError("validation", "Upload content disagrees with its captured metadata")
        directory = self.input_root / record["kind"] / record["scope_id"]
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = directory / record["filename"]
        if not path.resolve().is_relative_to(self.input_root) or path.is_symlink():
            raise ResearchError("validation", "Upload path is outside the input root")
        extracted_path = self.input_root / ".extracted" / hashlib.sha256(record["id"].encode()).hexdigest()
        extracted_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Public source identity is independent of the private volume's host root.
        record["stored_path"] = "/".join(("workspace", "input", record["kind"], record["scope_id"], record["filename"]))
        written = []
        with self._lock:
            if path.exists():
                raise ResearchError("conflict", "An upload already occupies this filename")
            try:
                for target, data in ((path, original), (extracted_path, extracted)):
                    if data is None:
                        continue
                    with target.open("xb") as stream:
                        written.append(target)
                        if os.name == "posix":
                            os.fchmod(stream.fileno(), 0o600)
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    _fsync_directory(target.parent)
                with self.transaction() as db:
                    db.execute("INSERT INTO uploads VALUES(?,?,?,?,?,?)", (record["id"], record["user_id"],
                               record["scope_id"], json_bytes(record).decode(), str(path),
                               str(extracted_path) if extracted is not None else None))
            except BaseException:
                for target in written:
                    target.unlink(missing_ok=True)
                raise
        return record

    def get_upload(self, upload_id: str, account_id: str) -> dict:
        with self._lock:
            row = self.connection.execute("SELECT record FROM uploads WHERE id=? AND account_id=?",
                                          (upload_id, account_id)).fetchone()
        if not row:
            raise ResearchError("not_found", "Upload is unavailable in this account")
        return json.loads(row["record"])

    def list_uploads(self, account_id: str, scope_id: str) -> list[dict]:
        with self._lock:
            return [json.loads(r["record"]) for r in self.connection.execute(
                "SELECT record FROM uploads WHERE account_id=? AND scope_id=? ORDER BY id", (account_id, scope_id))]

    def read_upload(self, upload_id: str, account_id: str, *, extracted: bool = False) -> bytes:
        with self._lock:
            row = self.connection.execute("SELECT * FROM uploads WHERE id=? AND account_id=?",
                                          (upload_id, account_id)).fetchone()
            if not row or json.loads(row["record"])["status"] != "uploaded":
                raise ResearchError("not_found", "Upload bytes are unavailable")
            record = json.loads(row["record"])
            path = row["extracted_path"] if extracted else row["original_path"]
            if not path or not Path(path).resolve().is_relative_to(self.input_root):
                raise ResearchError("integrity_fault", "Upload path is invalid")
            try:
                data = Path(path).read_bytes()
            except OSError as exc:
                raise ResearchError("evidence_unavailable", "Upload bytes are unreadable") from exc
            expected = record["text_sha256"] if extracted else record["content_sha256"]
            if hashlib.sha256(data).hexdigest() != expected:
                raise ResearchError("integrity_fault", "Upload bytes changed after publication")
            return data

    def delete_upload(self, upload_id: str, account_id: str) -> dict:
        with self.transaction() as db:
            row = db.execute("SELECT * FROM uploads WHERE id=? AND account_id=?", (upload_id, account_id)).fetchone()
            if not row:
                raise ResearchError("not_found", "Upload is unavailable in this account")
            record = json.loads(row["record"])
            if record["status"] == "deleted":
                return record
            active = db.execute("SELECT 1 FROM upload_uses u JOIN runs r ON r.id=u.run_id WHERE u.upload_id=? AND r.state IN ('pending','running','paused')", (upload_id,)).fetchone()
            if active:
                raise ResearchError("upload_in_use", "A nonterminal run still uses this upload")
            for name in ("original_path", "extracted_path"):
                if row[name]:
                    path = Path(row[name])
                    if not path.resolve().is_relative_to(self.input_root) or path.is_symlink():
                        raise ResearchError("integrity_fault", "Upload deletion path is invalid")
                    path.unlink(missing_ok=True)
                    _fsync_directory(path.parent)
            record.update(status="deleted", deleted_at=utc_now())
            db.execute("UPDATE uploads SET record=? WHERE id=?", (json_bytes(record).decode(), upload_id))
        return record

    def reserve_uploads(self, run_id: str, upload_ids: list[str]) -> None:
        with self.transaction() as db:
            run = db.execute("SELECT account_id,workspace_id FROM runs WHERE id=?", (run_id,)).fetchone()
            if not run:
                raise ResearchError("not_found", "Unknown run")
            for upload_id in upload_ids:
                record = self.get_upload(upload_id, run["account_id"])
                if record["status"] != "uploaded" or record["scope_id"] != run["workspace_id"]:
                    raise ResearchError("not_found", "Upload is outside the live run scope")
                db.execute("INSERT OR IGNORE INTO upload_uses VALUES(?,?)", (run_id, upload_id))

    def release_uploads(self, run_id: str) -> None:
        # Historical association is retained. Only terminal run state releases deletion.
        if self.get_run(run_id)["state"] in {"pending", "running", "paused"}:
            raise ResearchError("upload_in_use", "Cannot release inputs of a nonterminal run")

    def request_cancellation(self, run_id: str, account_id: str, request_id: str) -> dict:
        with self.transaction() as db:
            self.get_run(run_id, account_id=account_id)
            prior = db.execute("SELECT run_id,record FROM cancellation WHERE account_id=? AND request_id=?", (account_id, request_id)).fetchone()
            if prior:
                if prior["run_id"] != run_id:
                    raise ResearchError("identity_conflict", "Cancellation identity names another run")
                return json.loads(prior["record"])
            record = {"schema_version": "1.0.0", "id": "cancel:" + uuid.uuid4().hex,
                      "request_id": request_id, "run_id": run_id, "status": "requested", "preserved_effects": []}
            validate("client-cancellation", record)
            db.execute("INSERT INTO cancellation VALUES(?,?,?,?,?)", (account_id, request_id, run_id, "requested", json_bytes(record).decode()))
            db.execute("UPDATE runs SET revision=revision+1,reason='cancellation_requested',updated_at=? WHERE id=?", (utc_now(), run_id))
        return record

    def cancellation_requested(self, run_id: str) -> bool:
        with self._lock:
            return self.connection.execute("SELECT 1 FROM cancellation WHERE run_id=?", (run_id,)).fetchone() is not None

    def get_cancellation(self,run_id: str,request_id: str)->dict:
        with self._lock:
            row=self.connection.execute('SELECT record FROM cancellation WHERE run_id=? AND request_id=?',(run_id,request_id)).fetchone()
        if row is None:raise ResearchError('containment_authorization','No exact durable cancellation request exists')
        return json.loads(row['record'])

    def finish_cancellation(self, run_id: str, preserved_effects: list[str]) -> None:
        with self.transaction() as db:
            for row in db.execute("SELECT account_id,request_id,record FROM cancellation WHERE run_id=?", (run_id,)).fetchall():
                record = json.loads(row["record"])
                record.update(status="terminal", preserved_effects=preserved_effects)
                db.execute("UPDATE cancellation SET state='terminal',record=? WHERE account_id=? AND request_id=?", (json_bytes(record).decode(), row["account_id"], row["request_id"]))
            db.execute("UPDATE runs SET state='halted',reason='cancelled',revision=revision+1,updated_at=? WHERE id=?", (utc_now(), run_id))

    def create_run(self, run_id: str, *, account_id: str, workspace_id: str, submission: Mapping) -> dict:
        now = utc_now()
        with self.transaction() as db:
            db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)",
                       (run_id, account_id, workspace_id, "pending", 1, json_bytes(submission).decode(), now, now, None))
        self.append_record("run-created", {"id": run_id + ":created", "run_id": run_id,
                                          "account_id": account_id, "workspace_id": workspace_id})
        return self.get_run(run_id)

    def get_run(self, run_id: str, *, account_id: str | None = None) -> dict:
        with self._lock:
            row = self.connection.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None or (account_id is not None and row["account_id"] != account_id):
            raise ResearchError("not_found", "Run is unavailable in this account")
        result = dict(row)
        result["submission"] = json.loads(result["submission"])
        return result

    def list_runs(self, *, account_id: str, request_id: str | None = None) -> list[dict]:
        with self._lock:
            if request_id:
                rows = self.connection.execute("SELECT run_id FROM requests WHERE account_id=? AND request_id=?",
                                               (account_id, request_id)).fetchall()
                ids = [r["run_id"] for r in rows]
            else:
                ids = [r["id"] for r in self.connection.execute("SELECT id FROM runs WHERE account_id=? ORDER BY created_at,id", (account_id,))]
        return [self.get_run(identity, account_id=account_id) for identity in ids]

    def set_run_state(self, run_id: str, state: str, *, reason: str | None = None) -> None:
        if state not in {"pending", "running", "completed", "halted", "partial", "paused"}:
            raise ResearchError("validation", "Unknown run lifecycle")
        with self.transaction() as db:
            count = db.execute("UPDATE runs SET state=?,revision=revision+1,updated_at=?,reason=? WHERE id=?",
                               (state, utc_now(), reason, run_id)).rowcount
            if not count:
                raise ResearchError("not_found", "Unknown run")

    def recover_interrupted(self) -> int:
        """Called by the sole application owner during startup, never a reader."""
        from .restart_recovery import capture_interrupted_dispatches
        with self.transaction() as db:
            run_ids = [row['id'] for row in db.execute("SELECT id FROM runs WHERE state='running'").fetchall()]
            now = utc_now()
            # Original claims are still distinguishable from inert prepared
            # reservations here. Capture no worker completion or new effects.
            capture_interrupted_dispatches(self, db, run_ids, now)
            count = db.execute("UPDATE runs SET state='paused',reason='interrupted',revision=revision+1,updated_at=? WHERE state='running'",
                               (now,)).rowcount
            db.execute("UPDATE attempts SET state='paused' WHERE state IN ('prepared','running')")
        return count

    def claim_attempt(self, contract_ref: Ref, contract: Mapping) -> bool:
        key = (contract["run_id"], contract["node_id"], contract["subnode_id"], contract["attempt_id"])
        with self.transaction() as db:
            row = db.execute("SELECT * FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?", key).fetchone()
            if row:
                if json.loads(row["contract_ref"]) != contract_ref:
                    raise ResearchError("integrity_fault", "Attempt identity names another frozen contract")
                return False
            run = db.execute("SELECT state,reason FROM runs WHERE id=?", (contract["run_id"],)).fetchone()
            cancelled = db.execute("SELECT 1 FROM cancellation WHERE run_id=?", (contract["run_id"],)).fetchone()
            if not run or run["state"] not in {"pending", "running"} or run["reason"] == "cancellation_requested" or cancelled:
                raise ResearchError("run_not_dispatchable", "Run cannot start another attempt")
            db.execute("INSERT INTO attempts VALUES(?,?,?,?,?,?)", (*key, json_bytes(contract_ref).decode(), "prepared"))
        return True

    def predecessor_snapshot(self,run_id,predecessors):
        """Original committed predecessor identities, without publishing start."""
        with self._lock:
            return self._predecessor_snapshot(self.connection,run_id,predecessors)

    def _predecessor_snapshot(self,db,run_id,predecessors):
        committed=[]
        for predecessor in predecessors:
            rows=db.execute("SELECT attempt_id,port,artifact_ref,commit_id FROM acceptance WHERE run_id=? AND node_id=? AND subnode_id=''",(run_id,predecessor)).fetchall()
            if not rows:raise ResearchError('unaccepted_predecessor','Successor requires committed predecessor acceptance')
            committed.extend({'node_id':predecessor,'attempt_id':row['attempt_id'],'port':row['port'],
                'artifact_ref':json.loads(row['artifact_ref']),'commit_id':row['commit_id']} for row in rows)
        return sorted(committed,key=lambda row:(row['node_id'],row['attempt_id'],row['port'],row['commit_id']))

    def prepare_dispatch(self,contract,dispatch):
        """Capture original frozen orchestration inputs without starting work.

        This internal audit supplies only a reconstructable plan association.
        It is never a dispatch-start, an effect permission or a lease receipt.
        """
        required={'run_id','node_id','node_contract_ref','run_plan_ref','predecessors','predecessor_commits','bound_input_refs'}
        if type(dispatch) is not dict or set(dispatch)!=required:
            raise ResearchError('integrity_fault','Malformed protected inert dispatch scope')
        parent_ref=dispatch['node_contract_ref']
        parent=self.read_record(parent_ref,contract_id='node-execution-contract')
        if ((parent['run_id'],parent['node_id'],parent_ref)!=(contract['run_id'],contract['node_id'],contract['node_contract_ref'])
                or dispatch['run_id']!=parent['run_id'] or dispatch['node_id']!=parent['node_id']
                or dispatch['bound_input_refs']!=[{'name':port['name'],'ref':ref} for port in parent['inputs'] for ref in port['artifact_refs']]):
            raise ResearchError('integrity_fault','Inert dispatch differs from its exact original whole parent')
        if dispatch['run_plan_ref'] is not None:
            plan=self.read_record(dispatch['run_plan_ref'],contract_id='run-plan')
            for binding_kind in ('run-plan-binding','finite-e1-plan-binding'):
                bindings=list(self.iter_records(run_id=parent['run_id'],kinds=(binding_kind,)))
                if len(bindings)>1 or (bindings and (bindings[0]['record'].get('run_id')!=parent['run_id']
                        or bindings[0]['record'].get('plan_ref')!=dispatch['run_plan_ref'])):
                    raise ResearchError('integrity_fault','Inert dispatch differs from the existing original run plan binding')
            nodes=[node for node in plan['nodes'] if node['node_id']==parent['node_id']]
            work=[item for item in parent['subnodes'] if item['role']=='work']
            if (not plan['frozen'] or len(nodes)!=1 or len(work)!=1
                    or plan['source_ref']!=parent['template_ref'] or plan['configuration_ref']!=parent['configuration_ref']
                    or plan['policy_ref']!=parent['policy_ref'] or nodes[0]['limits']!=parent['node_limits']
                    or nodes[0]['predecessors']!=dispatch['predecessors']
                    or work[0]['capsule_ref']['sha256']!=nodes[0]['cc']['declaration_sha256']
                    or self.read_record(work[0]['template_ref'])['cc']!=nodes[0]['cc']):
                raise ResearchError('integrity_fault','Inert dispatch does not join the original frozen plan node')
            self.read_record(plan['resource_inventory_ref'],contract_id='resource-inventory')
        for item in dispatch['bound_input_refs']:self.read_blob(item['ref'])
        with self.transaction() as db:
            run=db.execute('SELECT state,reason FROM runs WHERE id=?',(contract['run_id'],)).fetchone()
            cancelled=db.execute('SELECT 1 FROM cancellation WHERE run_id=?',(contract['run_id'],)).fetchone()
            if not run or run['state'] not in {'pending','running'} or run['reason']=='cancellation_requested' or cancelled:
                raise ResearchError('run_not_dispatchable','Stopped run cannot prepare dispatch')
            committed=self._predecessor_snapshot(db,contract['run_id'],dispatch['predecessors'])
            if committed!=dispatch['predecessor_commits']:
                raise ResearchError('unaccepted_predecessor','Prepared predecessor identities differ')
            body={'run_id':parent['run_id'],'node_id':parent['node_id'],'node_contract_ref':parent_ref,
                'run_plan_ref':dispatch['run_plan_ref'],'predecessor_commits':committed,'bound_input_refs':dispatch['bound_input_refs']}
            prior=[row for row in self.iter_records(run_id=parent['run_id'],kinds=('dispatch-preparation',))
                if row['record'].get('node_contract_ref')==parent_ref]
            if prior:
                if len(prior)!=1 or {key:prior[0]['record'].get(key) for key in body}!=body:
                    raise ResearchError('identity_conflict','Original inert dispatch association differs')
                return prior[0]['ref']
            record={'id':'dispatch-preparation:'+uuid.uuid4().hex,'recorded_at':utc_now(),**body}
            digest=self.blobs.put(json_bytes(record));ref={'id':record['id'],'sha256':digest}
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'dispatch-preparation',parent['run_id'],parent['node_id'],None,utc_now()))
        return ref

    def start_prepared_attempt(self,contract_ref,contract,preparation_ref,live_check,*,dispatch=None):
        """Consume one reservation and publish its real start in one SQL view.

        The callback is installed protected orchestration, never a CC argument.
        Its synchronous check observes the same actual owner/deadline under the
        write transaction; no RPC or await is hidden inside this CAS.
        """
        key=tuple(contract[name] for name in ('run_id','node_id','subnode_id','attempt_id'))
        with self.transaction() as db:
            live_check()
            run=db.execute('SELECT state,reason FROM runs WHERE id=?',(contract['run_id'],)).fetchone()
            cancelled=db.execute('SELECT 1 FROM cancellation WHERE run_id=?',(contract['run_id'],)).fetchone()
            if not run or run['state'] not in {'pending','running'} or run['reason']=='cancellation_requested' or cancelled:
                raise ResearchError('run_not_dispatchable','Stopped run cannot consume a prepared start')
            row=db.execute('SELECT contract_ref,state FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',key).fetchone()
            if row is None or row['state']!='prepared' or json.loads(row['contract_ref'])!=contract_ref:
                raise ResearchError('attempt_already_claimed','Prepared start was already consumed or replaced')
            if self.record_kind(preparation_ref)!='invocation-preparation':
                raise ResearchError('integrity_fault','Original preparation is unavailable')
            timing={'started_at':utc_now(),'started_monotonic_s':time.monotonic()}
            if dispatch is not None:
                preparations=[item for item in self.iter_records(run_id=contract['run_id'],kinds=('dispatch-preparation',))
                    if item['record'].get('node_contract_ref')==contract['node_contract_ref']]
                expected={'run_id':dispatch['run_id'],'node_id':dispatch['node_id'],'node_contract_ref':dispatch['node_contract_ref'],
                    'run_plan_ref':dispatch['run_plan_ref'],'predecessor_commits':dispatch['predecessor_commits'],
                    'bound_input_refs':dispatch['bound_input_refs']}
                if len(preparations)!=1 or {key:preparations[0]['record'].get(key) for key in expected}!=expected:
                    raise ResearchError('integrity_fault','Original inert dispatch proof is missing or differs')
                if (dispatch['run_id'],dispatch['node_id'],dispatch['node_contract_ref'])!=(contract['run_id'],contract['node_id'],contract['node_contract_ref']):
                    raise ResearchError('integrity_fault','Dispatch preparation belongs to another whole attempt')
                committed=self._predecessor_snapshot(db,contract['run_id'],dispatch['predecessors'])
                if committed!=dispatch['predecessor_commits']:
                    raise ResearchError('unaccepted_predecessor','Original predecessor acceptance changed during preparation')
                self.read_blob(dispatch['node_contract_ref'])
                if dispatch['run_plan_ref'] is not None:self.read_blob(dispatch['run_plan_ref'])
                for item in dispatch['bound_input_refs']:self.read_blob(item['ref'])
                record={'id':'dispatch-start:'+uuid.uuid4().hex,'run_id':contract['run_id'],'node_id':contract['node_id'],
                    'recorded_at':timing['started_at'],'node_contract_ref':dispatch['node_contract_ref'],
                    'run_plan_ref':dispatch['run_plan_ref'],'predecessor_commits':committed,
                    'bound_input_refs':dispatch['bound_input_refs']}
                digest=self.blobs.put(json_bytes(record));ref={'id':record['id'],'sha256':digest}
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
                db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'dispatch-start',contract['run_id'],contract['node_id'],None,utc_now()))
                db.execute("INSERT INTO nodes VALUES(?,?,?,?,?) ON CONFLICT(run_id,node_id) DO UPDATE SET state=excluded.state,attempt_id=excluded.attempt_id,reason=NULL",
                    (contract['run_id'],contract['node_id'],'running',contract['attempt_id'],None))
                timing['dispatch_ref']=ref
            self._fault('before_invocation_start')
            changed=db.execute("UPDATE attempts SET state='running' WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=? AND state='prepared'",key).rowcount
            if changed!=1:raise ResearchError('attempt_already_claimed','Prepared invocation CAS was lost')
            if (dispatch is None and contract['bindings'][0]['role']=='work'
                    and (node:=db.execute('SELECT state,attempt_id FROM nodes WHERE run_id=? AND node_id=?',key[:2]).fetchone()) is not None
                    and node['state']=='evaluating' and node['attempt_id']==contract['attempt_id']):
                # A later Compiler work child reuses its original whole-node
                # start; no second dispatch, allowance or attempt is created.
                # Admitted/isolated canonical measurement callers have no
                # ordinary Evaluating node and retain their existing starts.
                parent_ref=contract['node_contract_ref']
                parent=self.read_record(parent_ref,contract_id='node-execution-contract')
                assignment=[item for item in parent['subnodes'] if item['subnode_id']==contract['subnode_id']]
                child_meta=db.execute('SELECT kind,run_id,node_id,attempt_id FROM records WHERE id=?',(contract_ref['id'],)).fetchone()
                parent_meta=db.execute('SELECT kind,run_id,node_id,attempt_id FROM records WHERE id=?',(parent_ref['id'],)).fetchone()
                scope=tuple(contract[name] for name in ('run_id','node_id','attempt_id'))
                if (child_meta is None or parent_meta is None
                        or tuple(child_meta)!=('subnode-execution-contract',*scope)
                        or tuple(parent_meta)!=('node-execution-contract',*scope)
                        or self.read_record(contract_ref,contract_id='subnode-execution-contract')!=contract
                        or tuple(parent[name] for name in ('run_id','node_id','attempt_id'))!=scope
                        or len(assignment)!=1 or assignment[0]['role']!='work'
                        or assignment[0]['template_ref']!=contract['template_ref']
                        or assignment[0]['capsule_ref']!=contract['bindings'][0]['declaration_ref']):
                    raise ResearchError('integrity_fault','Subsequent work differs from its exact original parent')
                preparation=self.read_record(preparation_ref,contract_id='urn:ai4r:private:invocation-preparation:1')
                if preparation['contract_ref']!=contract_ref or preparation['assignment_grant_ref'] is not None:
                    raise ResearchError('integrity_fault','Subsequent work lacks its original canonical preparation')
                reservations=[item for item in self.iter_records(run_id=scope[0],kinds=('invocation-budget-reservation',))
                    if item['record'].get('contract_ref')==contract_ref]
                if (len(reservations)!=1 or any(reservations[0]['record'].get(name)!=preparation[name]
                        for name in ('contract_ref','invocation_id','execution_id'))):
                    raise ResearchError('integrity_fault','Subsequent work invocation differs from its original reservation')
                starts=[item for item in self.iter_records(run_id=contract['run_id'],kinds=('dispatch-start',))
                    if item['record'].get('node_id')==contract['node_id']]
                preparations=[item for item in self.iter_records(run_id=contract['run_id'],kinds=('dispatch-preparation',))
                    if item['record'].get('node_id')==contract['node_id']]
                node=db.execute('SELECT state,attempt_id FROM nodes WHERE run_id=? AND node_id=?',scope[:2]).fetchone()
                if (not starts or not preparations
                        or len(starts)==1 and starts[0]['record'].get('node_contract_ref')!=parent_ref
                        or len(preparations)==1 and preparations[0]['record'].get('node_contract_ref')!=parent_ref):
                    # Non-owning measurement starts gain no ordinary lifecycle
                    # obligation or state from another original parent.
                    return timing
                if (len(starts)!=1 or len(preparations)!=1
                        or starts[0]['record'].get('node_contract_ref')!=parent_ref
                        or any(starts[0]['record'].get(name)!=preparations[0]['record'].get(name)
                            for name in ('run_id','node_id','node_contract_ref','run_plan_ref','predecessor_commits','bound_input_refs'))
                        or node is None or node['state'] not in {'running','evaluating'} or node['attempt_id']!=scope[2]):
                    raise ResearchError('integrity_fault','Subsequent work lacks its original open whole-node start')
                for item,kind in ((starts[0],'dispatch-start'),(preparations[0],'dispatch-preparation')):
                    metadata=db.execute('SELECT kind,run_id,node_id,attempt_id FROM records WHERE id=?',(item['ref']['id'],)).fetchone()
                    if metadata is None or tuple(metadata)!=(kind,scope[0],scope[1],None):
                        raise ResearchError('integrity_fault','Subsequent work original dispatch scope differs')
                changed=db.execute("UPDATE nodes SET state='running' WHERE run_id=? AND node_id=? AND attempt_id=? AND state IN ('running','evaluating')",scope).rowcount
                if changed!=1:raise ResearchError('integrity_fault','Original subsequent-work lifecycle CAS was lost')
        return timing

    def mark_node_evaluating(self,contract_ref,contract,preparation_ref,*,invocation_id,execution_id):
        """Record the original returned work/check boundary, without authority.

        The canonical Runner calls this only after its actual work has closed.
        Original claims and immutable start/preparation joins independently
        constrain the write; this operation never starts or finishes an attempt.
        """
        def require(condition,message):
            if not condition:raise ResearchError('integrity_fault',message)
        with self.transaction() as db:
            def original(ref,kind,scope):
                value=self.read_record(ref)
                row=db.execute('SELECT kind,run_id,node_id,attempt_id FROM records WHERE id=?',(ref['id'],)).fetchone()
                require(row is not None and tuple(row)==(kind,*scope),'Lifecycle proof has another original indexed kind or scope')
                return value
            scope=tuple(contract[name] for name in ('run_id','node_id','attempt_id'))
            parent_ref=contract['node_contract_ref']
            child=original(contract_ref,'subnode-execution-contract',scope)
            parent=original(parent_ref,'node-execution-contract',scope)
            validate('subnode-execution-contract',child);validate('node-execution-contract',parent)
            require(child==contract and tuple(parent[name] for name in ('run_id','node_id','attempt_id'))==scope,
                'Returned work does not join its exact original whole attempt')
            run=db.execute('SELECT state,reason FROM runs WHERE id=?',(scope[0],)).fetchone()
            if (run is None or run['state'] not in {'pending','running'} or run['reason']=='cancellation_requested'
                    or db.execute('SELECT 1 FROM cancellation WHERE run_id=?',(scope[0],)).fetchone()):
                return False
            node=db.execute('SELECT state,attempt_id FROM nodes WHERE run_id=? AND node_id=?',scope[:2]).fetchone()
            if node is None or node['state'] not in {'running','evaluating'} or node['attempt_id']!=scope[2]:
                return False

            def work_child(ref,value):
                validate('subnode-execution-contract',value)
                require(value['node_contract_ref']==parent_ref
                    and tuple(value[name] for name in ('run_id','node_id','attempt_id'))==scope
                    and all(value[name]==parent[name] for name in ('configuration_ref','policy_ref','revision')),
                    'Work claim belongs to another original parent')
                assignments=[item for item in parent['subnodes'] if item['subnode_id']==value['subnode_id']]
                require(len(assignments)==1 and len(value['bindings'])==1,'Original work assignment is ambiguous')
                assignment=assignments[0];bound=value['bindings'][0]
                if assignment['role']!='work':
                    require(bound['role']=='verifier','Original child role differs from its parent')
                    return False
                template=original(assignment['template_ref'],'subnode-template',(None,None,None))
                require(bound['role']=='work' and value['template_ref']==assignment['template_ref']
                    and bound['declaration_ref']==assignment['capsule_ref']
                    and template['role']=='work' and template['subnode_id']==value['subnode_id']
                    and template['capsule_ref']==assignment['capsule_ref']
                    and template['admission_ref']==bound['admission_ref']
                    and template['checking_profile_ref']==value['checking_profile_ref'],
                    'Original work binding differs from its frozen assignment')
                return True
            require(work_child(contract_ref,child),'Verifier work cannot produce the returned-work lifecycle')
            attempt=db.execute('SELECT contract_ref,state FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?',
                (scope[0],scope[1],child['subnode_id'],scope[2])).fetchone()
            if attempt is None or attempt['state']!='running':return False
            require(json.loads(attempt['contract_ref'])==contract_ref,
                'Returned work lacks its original consumed once claim')
            preparation=original(preparation_ref,'invocation-preparation',(None,None,None))
            validate('urn:ai4r:private:invocation-preparation:1',preparation)
            require(preparation['contract_ref']==contract_ref and preparation['assignment_grant_ref'] is None
                and preparation['invocation_id']==invocation_id and preparation['execution_id']==execution_id,
                'Returned work lacks its exact original canonical invocation preparation')
            reservations=[item for item in self.iter_records(run_id=scope[0],kinds=('invocation-budget-reservation',))
                if item['record'].get('contract_ref')==contract_ref]
            require(len(reservations)==1,'Original invocation reservation is ambiguous')
            reservation=original(reservations[0]['ref'],'invocation-budget-reservation',(scope[0],scope[1],None))
            require(reservation.get('subnode_id')==child['subnode_id'] and reservation.get('invocation_id')==invocation_id
                and reservation.get('execution_id')==execution_id,'Returned work invocation identity differs from its original reservation')
            starts=[item for item in self.iter_records(run_id=scope[0],kinds=('dispatch-start',))
                if item['record'].get('node_id')==scope[1]]
            prepared=[item for item in self.iter_records(run_id=scope[0],kinds=('dispatch-preparation',))
                if item['record'].get('node_id')==scope[1]]
            if (not starts or not prepared
                    or len(starts)==1 and starts[0]['record'].get('node_contract_ref')!=parent_ref
                    or len(prepared)==1 and prepared[0]['record'].get('node_contract_ref')!=parent_ref):
                return False
            require(len(starts)==len(prepared)==1,'Original whole-node dispatch association is ambiguous')
            start=original(starts[0]['ref'],'dispatch-start',(scope[0],scope[1],None))
            dispatched=original(prepared[0]['ref'],'dispatch-preparation',(scope[0],scope[1],None))
            require(start.get('node_contract_ref')==parent_ref
                and all(start.get(name)==dispatched.get(name) for name in
                    ('run_id','node_id','node_contract_ref','run_plan_ref','predecessor_commits','bound_input_refs')),
                'Original consumed dispatch differs from its inert preparation')
            terminal=[item for item in self.iter_records(run_id=scope[0],kinds=('dispatch-record','gate-decision','acceptance-commit'))
                if item['record'].get('node_id')==scope[1] and
                (item['kind']=='dispatch-record' or item['kind']=='gate-decision' and item['record'].get('scope_kind')=='node'
                    or item['kind']=='acceptance-commit' and item['record'].get('subnode_id')=='')]
            if terminal:return False

            # Claim state spans both execution and checking. A prior original
            # worker observation proves that child has returned; absent that
            # proof conservatively retain Running for another consumed worker.
            observations=list(self.iter_records(run_id=scope[0],kinds=('invocation-observation',)))
            others=db.execute("SELECT contract_ref,subnode_id FROM attempts WHERE run_id=? AND node_id=? AND attempt_id=? AND state='running'",scope).fetchall()
            for other in others:
                ref=json.loads(other['contract_ref'])
                if ref==contract_ref:continue
                value=original(ref,'subnode-execution-contract',scope)
                require(value['subnode_id']==other['subnode_id'],'Other original claim identity differs')
                if not work_child(ref,value):continue
                observed=[item for item in observations if item['record'].get('contract_ref')==ref]
                require(len(observed)<=1,'Other work observation is ambiguous')
                if not observed:return False
                observation=original(observed[0]['ref'],'invocation-observation',scope)
                validate('invocation-observation',observation)
                require(observation['node_contract_ref']==parent_ref and observation['subnode_id']==value['subnode_id'],
                    'Other work observation belongs to another original attempt')
            changed=db.execute("UPDATE nodes SET state='evaluating' WHERE run_id=? AND node_id=? AND attempt_id=? AND state IN ('running','evaluating')",scope).rowcount
            require(changed==1,'Original evaluation lifecycle CAS was lost')
        return True

    def get_attempt(self, run_id: str, node_id: str, subnode_id: str, attempt_id: str) -> dict:
        with self._lock:
            row = self.connection.execute("SELECT * FROM attempts WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?",
                                          (run_id, node_id, subnode_id, attempt_id)).fetchone()
        if not row:
            raise ResearchError("not_found", "Unknown protected attempt")
        value = dict(row)
        value["contract_ref"] = json.loads(value["contract_ref"])
        return value

    def finish_attempt(self, contract: Mapping, state: str) -> None:
        with self.transaction() as db:
            db.execute("UPDATE attempts SET state=? WHERE run_id=? AND node_id=? AND subnode_id=? AND attempt_id=?",
                       (state, contract["run_id"], contract["node_id"], contract["subnode_id"], contract["attempt_id"]))

    def commit_acceptance(self, run_id: str, node_id: str, attempt_id: str,
                          outputs: Mapping[str, Ref], decisions: list[Ref], *, subnode_id: str = "") -> str:
        if not decisions or not outputs:
            raise ResearchError("missing_gate", "Acceptance requires actual advancing decisions and outputs")
        captured = [self.read_record(ref, contract_id="gate-decision") for ref in decisions]
        accepted = []
        for decision in captured:
            if (decision["run_id"], decision["node_id"], decision["attempt_id"]) != (run_id, node_id, attempt_id):
                raise ResearchError("integrity_fault", "Gate belongs to another attempt")
            if decision["action"] != "advance" or decision["verdict"] not in {"PASS", "PASS_WITH_KNOWN_LIMITATIONS"}:
                raise ResearchError("gate_halted", "Nonadvancing decision cannot release outputs")
            for ref in decision["invocation_refs"] + decision["accepted_refs"]:
                self.read_blob(ref)
            self.read_record(decision["deterministic_result_ref"], contract_id="deterministic-check-result")
            self.read_record(decision["assessment_ref"], contract_id="verifier-assessment")
            accepted.extend(decision["accepted_refs"])
        if any(ref not in accepted for ref in outputs.values()):
            raise ResearchError("integrity_fault", "Output was not accepted by its exact gate")
        commit_id = "commit:" + uuid.uuid4().hex
        receipt={'id':commit_id,'commit_id':commit_id,'run_id':run_id,'node_id':node_id,'attempt_id':attempt_id,
                 'subnode_id':subnode_id,'output_refs':dict(outputs),'gate_decision_refs':decisions,'committed_at':utc_now()}
        receipt_raw=json_bytes(receipt);receipt_digest=self.blobs.put(receipt_raw)
        with self.transaction() as db:
            run = db.execute("SELECT state,reason FROM runs WHERE id=?", (run_id,)).fetchone()
            cancelled = db.execute("SELECT 1 FROM cancellation WHERE run_id=?", (run_id,)).fetchone()
            if not run or run["state"] not in {"pending", "running"} or run["reason"] == "cancellation_requested" or cancelled:
                raise ResearchError("run_not_dispatchable", "Stopped run cannot release outputs")
            self._fault("before_acceptance")
            for port, ref in outputs.items():
                db.execute("INSERT INTO acceptance VALUES(?,?,?,?,?,?,?)",
                           (run_id, node_id, attempt_id, subnode_id, port, json_bytes(ref).decode(), commit_id))
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(commit_id,receipt_digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(commit_id,'acceptance-commit',run_id,node_id,attempt_id,utc_now()))
            if not subnode_id:
                db.execute("INSERT INTO nodes VALUES(?,?,?,?,?) ON CONFLICT(run_id,node_id) DO UPDATE SET state=excluded.state,attempt_id=excluded.attempt_id,reason=NULL",
                           (run_id, node_id, "completed", attempt_id, None))
            db.execute("UPDATE runs SET revision=revision+1,updated_at=? WHERE id=?", (utc_now(), run_id))
        return commit_id

    def accepted_outputs(self, run_id: str, node_id: str, *, subnode_id: str = "") -> dict[str, Ref]:
        with self._lock:
            rows = self.connection.execute("SELECT port,artifact_ref FROM acceptance WHERE run_id=? AND node_id=? AND subnode_id=?",
                                           (run_id, node_id, subnode_id)).fetchall()
        return {r["port"]: json.loads(r["artifact_ref"]) for r in rows}

    def authorize_dispatch(self, run_id: str, node_id: str, predecessors: list[str], bound_inputs: list[dict], *, contract_ref: Ref, plan_ref: Ref | None) -> Ref:
        """Capture causal predecessor commits before any successor execution.

        This protected internal receipt is evidence, not an acceptance grant.
        All predecessor rows must already be committed in the same SQLite view.
        """
        self.read_blob(contract_ref)
        if plan_ref is not None:self.read_blob(plan_ref)
        for item in bound_inputs:self.read_blob(item['ref'])
        with self.transaction() as db:
            run=db.execute('SELECT state,reason FROM runs WHERE id=?',(run_id,)).fetchone()
            if not run or run['state'] not in {'pending','running'} or run['reason']=='cancellation_requested':
                raise ResearchError('run_not_dispatchable','Stopped run cannot authorize successor work')
            committed=[]
            for predecessor in predecessors:
                rows=db.execute("SELECT attempt_id,port,artifact_ref,commit_id FROM acceptance WHERE run_id=? AND node_id=? AND subnode_id=''",(run_id,predecessor)).fetchall()
                if not rows:raise ResearchError('unaccepted_predecessor','Successor requires committed predecessor acceptance')
                committed.extend({'node_id':predecessor,'attempt_id':row['attempt_id'],'port':row['port'],
                    'artifact_ref':json.loads(row['artifact_ref']),'commit_id':row['commit_id']} for row in rows)
            record={'id':'dispatch-start:'+uuid.uuid4().hex,'run_id':run_id,'node_id':node_id,'recorded_at':utc_now(),
                'node_contract_ref':contract_ref,'run_plan_ref':plan_ref,'predecessor_commits':committed,'bound_input_refs':bound_inputs}
            raw=json_bytes(record);digest=self.blobs.put(raw);ref={'id':record['id'],'sha256':digest}
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'dispatch-start',run_id,node_id,None,utc_now()))
        return ref

    def is_accepted(self, ref: Ref, *, run_id: str | None = None) -> bool:
        with self._lock:
            query="SELECT artifact_ref FROM acceptance WHERE subnode_id=''" + (" AND run_id=?" if run_id else "")
            rows=self.connection.execute(query,(run_id,) if run_id else ()).fetchall()
        return any(json.loads(row['artifact_ref'])==ref for row in rows)

    def claim_model_call(self, context: Mapping, *, invocation_limit: int, node_limit: int, run_limit: int,
                         reserved_node_calls: int = 0, reserved_run_calls: int = 0) -> tuple[str, Ref]:
        ordinal=context['call_ordinal']
        if not isinstance(ordinal,int) or isinstance(ordinal,bool) or ordinal<1:
            raise ResearchError('model_call_authorization','Invalid protected call ordinal')
        if any(type(v) is not int or v<0 for v in (invocation_limit,node_limit,run_limit,reserved_node_calls,reserved_run_calls)):
            raise ResearchError('model_call_authorization','Invalid protected model-call ceiling or reserve')
        call_id='call:'+uuid.uuid4().hex
        record=dict(context,id=call_id+':claim',call_id=call_id,recorded_at=utc_now())
        raw=json_bytes(record);digest=self.blobs.put(raw);ref={'id':record['id'],'sha256':digest}
        with self.transaction() as db:
            run=db.execute('SELECT state,reason FROM runs WHERE id=?',(context['run_id'],)).fetchone()
            if not run or run['state'] not in {'pending','running'} or run['reason']=='cancellation_requested':
                raise ResearchError('run_not_dispatchable','Run cannot authorize a model call')
            if db.execute('SELECT 1 FROM model_calls WHERE run_id=? AND invocation_id=? AND ordinal=?',
                          (context['run_id'],context['invocation_id'],ordinal)).fetchone():
                raise ResearchError('model_call_already_claimed','Uncertain or duplicate call is never resent')
            invocation_used=db.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=? AND invocation_id=?',(context['run_id'],context['invocation_id'])).fetchone()[0]
            node_used=db.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=? AND node_id=?',(context['run_id'],context['node_id'])).fetchone()[0]
            run_used=db.execute('SELECT COUNT(*) FROM model_calls WHERE run_id=?',(context['run_id'],)).fetchone()[0]
            if ordinal!=invocation_used+1 or invocation_used>=invocation_limit or node_used+1+reserved_node_calls>node_limit or run_used+1+reserved_run_calls>run_limit:
                raise ResearchError('budget_exhausted','Protected model-call reservation exhausted')
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'model-call-claim',context['run_id'],context['node_id'],context['attempt_id'],utc_now()))
            db.execute('INSERT INTO model_calls VALUES(?,?,?,?,?,?)',(context['run_id'],context['invocation_id'],ordinal,context['node_id'],call_id,json_bytes(ref).decode()))
        return call_id,ref

    def claim_tool_call(self,context: Mapping,*,tool_limit: int)->Ref:
        ordinal=context['tool_ordinal']
        if type(ordinal) is not int or ordinal<1 or type(tool_limit) is not int or tool_limit<0:
            raise ResearchError('tool_authorization','Invalid protected tool claim')
        record=dict(context,id='tool-claim:'+uuid.uuid4().hex,recorded_at=utc_now())
        digest=self.blobs.put(json_bytes(record));ref={'id':record['id'],'sha256':digest}
        with self.transaction() as db:
            run=db.execute('SELECT state,reason FROM runs WHERE id=?',(context['run_id'],)).fetchone()
            if not run or run['state'] not in {'pending','running'} or run['reason']=='cancellation_requested':raise ResearchError('run_not_dispatchable','Stopped run cannot authorize a connector effect')
            if db.execute('SELECT 1 FROM tool_calls WHERE run_id=? AND invocation_id=? AND ordinal=?',(context['run_id'],context['invocation_id'],ordinal)).fetchone():raise ResearchError('tool_call_already_claimed','Uncertain tool effect is never resent')
            used=db.execute('SELECT COUNT(*) FROM tool_calls WHERE run_id=? AND invocation_id=?',(context['run_id'],context['invocation_id'])).fetchone()[0]
            if ordinal!=used+1 or used>=tool_limit:raise ResearchError('budget_exhausted','Invocation connector tool ceiling exhausted')
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'tool-call-claim',context['run_id'],context['node_id'],context['attempt_id'],utc_now()))
            db.execute('INSERT INTO tool_calls VALUES(?,?,?,?,?)',(context['run_id'],context['invocation_id'],ordinal,context['node_id'],json_bytes(ref).decode()))
        return ref

    def set_node_state(self, run_id: str, node_id: str, state: str, *, attempt_id: str | None = None,
                       reason: str | None = None) -> None:
        with self.transaction() as db:
            db.execute("INSERT INTO nodes VALUES(?,?,?,?,?) ON CONFLICT(run_id,node_id) DO UPDATE SET state=excluded.state,attempt_id=excluded.attempt_id,reason=excluded.reason",
                       (run_id, node_id, state, attempt_id, reason))

    def node_states(self, run_id: str) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.connection.execute("SELECT * FROM nodes WHERE run_id=? ORDER BY node_id", (run_id,))]
