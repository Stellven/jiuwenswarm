"""Durable store (PAS-M1-001 B04): SQLite records, content-addressed blobs, traces.

Everything lives under the declared data directory (SIMLAB_DATA_DIR), which must
be outside any repository (ARCH Placement; PRD SL-8.S). Submitted experiments
and bound manifests are write-once (SQLite triggers reject UPDATE and DELETE);
attempt rows append only and change exactly once, from RUNNING to terminal, or
to INVALID/corrupted_record when an integrity check finds a damaged record.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from simlab.contracts import SimlabError, canonical

SCHEMA = r"""
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS manifests(
  manifest_id TEXT PRIMARY KEY, manifest_sha256 TEXT NOT NULL UNIQUE, body TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS manifests_immutable_u BEFORE UPDATE ON manifests BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TRIGGER IF NOT EXISTS manifests_immutable_d BEFORE DELETE ON manifests BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TABLE IF NOT EXISTS experiments(
  experiment_id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, body TEXT NOT NULL, manifest_id TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS experiments_immutable_u BEFORE UPDATE ON experiments BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TRIGGER IF NOT EXISTS experiments_immutable_d BEFORE DELETE ON experiments BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TABLE IF NOT EXISTS drafts(
  draft_id TEXT PRIMARY KEY, header TEXT NOT NULL, parent TEXT, bound_manifest_id TEXT, bound_experiment_id TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS draft_artifacts(
  draft_id TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL, extension_point TEXT, sha256 TEXT NOT NULL,
  bytes INTEGER NOT NULL, updated_at TEXT NOT NULL, PRIMARY KEY(draft_id, path));
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT PRIMARY KEY, experiment_id TEXT NOT NULL, run_kind TEXT NOT NULL, parent TEXT, replay_of TEXT,
  status TEXT NOT NULL, status_reason TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT,
  identity TEXT, hardware TEXT, resources TEXT, cancel_requested INTEGER NOT NULL DEFAULT 0, options TEXT);
CREATE TABLE IF NOT EXISTS trials(
  trial_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, ordinal INTEGER NOT NULL, purpose TEXT NOT NULL, arm_id TEXT NOT NULL,
  condition_id TEXT NOT NULL, replicate INTEGER NOT NULL, episode INTEGER NOT NULL, pair_id TEXT, seeds TEXT NOT NULL,
  params TEXT NOT NULL, check_id TEXT);
CREATE TABLE IF NOT EXISTS attempts(
  attempt_id TEXT PRIMARY KEY, trial_id TEXT NOT NULL, run_id TEXT NOT NULL, purpose TEXT NOT NULL, status TEXT NOT NULL,
  invalid_reason TEXT, reason TEXT NOT NULL DEFAULT '', seeds TEXT NOT NULL, started_at TEXT, ended_at TEXT,
  stop TEXT, state_digest TEXT, exec TEXT);
CREATE TRIGGER IF NOT EXISTS attempts_no_delete BEFORE DELETE ON attempts BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TRIGGER IF NOT EXISTS attempts_once BEFORE UPDATE ON attempts
  WHEN NOT (OLD.status = 'RUNNING' OR (NEW.status = 'INVALID' AND NEW.invalid_reason = 'corrupted_record'
            AND OLD.status IN ('COMPLETED','LIMIT_REACHED','INVALID')))
  BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TABLE IF NOT EXISTS measurements(
  run_id TEXT NOT NULL, trial_id TEXT, attempt_id TEXT, measurement_id TEXT NOT NULL, scope TEXT NOT NULL,
  key TEXT NOT NULL DEFAULT '{}', value TEXT NOT NULL, unit TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'primary');
CREATE INDEX IF NOT EXISTS measurements_run ON measurements(run_id, trial_id);
CREATE TABLE IF NOT EXISTS checks(
  run_id TEXT NOT NULL, check_id TEXT NOT NULL, check_kind TEXT NOT NULL, required INTEGER NOT NULL, status TEXT NOT NULL,
  observed TEXT NOT NULL, affected TEXT NOT NULL, PRIMARY KEY(run_id, check_id));
CREATE TABLE IF NOT EXISTS checkpoints(
  checkpoint_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, trial_id TEXT NOT NULL, attempt_id TEXT NOT NULL, point TEXT NOT NULL,
  time_s REAL NOT NULL, state_sha256 TEXT NOT NULL, files TEXT NOT NULL, model_sha256 TEXT NOT NULL, meta TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS checkpoints_immutable_u BEFORE UPDATE ON checkpoints BEGIN SELECT RAISE(ABORT,'E_IMMUTABLE'); END;
CREATE TABLE IF NOT EXISTS traces(
  ref TEXT PRIMARY KEY, run_id TEXT NOT NULL, trial_id TEXT NOT NULL, attempt_id TEXT NOT NULL, arm_id TEXT NOT NULL,
  signal TEXT NOT NULL, unit TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL, n INTEGER NOT NULL,
  dim INTEGER NOT NULL, t_start REAL, t_end REAL, kind TEXT NOT NULL DEFAULT 'signal');
CREATE INDEX IF NOT EXISTS traces_run ON traces(run_id, trial_id, signal);
CREATE TABLE IF NOT EXISTS events(
  run_id TEXT NOT NULL, trial_id TEXT NOT NULL, attempt_id TEXT NOT NULL, t REAL NOT NULL, event_id TEXT NOT NULL,
  kind TEXT NOT NULL, detail TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, trial_id);
CREATE TABLE IF NOT EXISTS registry(
  capability TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL, evidence_ref TEXT,
  version TEXT, updated_at TEXT NOT NULL);
"""


def now() -> str:
    t = time.time()
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) + f".{int((t % 1) * 1e6):06d}Z"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:20]}"


def inside_repository(path: Path) -> Path | None:
    """Return the repository root containing `path`, if any (a .git entry above it)."""
    p = path.resolve()
    for parent in [p, *p.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def resolve_data_dir(value: str | os.PathLike | None = None, *, create: bool = True) -> Path:
    raw = value or os.environ.get("SIMLAB_DATA_DIR")
    if not raw:
        raise SimlabError("E_DATA_DIR", "SIMLAB_DATA_DIR is not declared")
    path = Path(raw).expanduser()
    if create:
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise SimlabError("E_DATA_DIR", f"data directory {path} does not exist")
    repo = inside_repository(path)
    if repo is not None:
        raise SimlabError("E_DATA_DIR", f"data directory {path} is inside the repository {repo}; run data must live outside it")
    if not os.access(path, os.W_OK):
        raise SimlabError("E_DATA_DIR", f"data directory {path} is not writable")
    return path.resolve()


def safe_name(signal: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in signal)


class Store:
    def __init__(self, data_dir: str | os.PathLike | None = None):
        self.root = resolve_data_dir(data_dir)
        self.db_path = self.root / "simlab.sqlite"
        self.blobs = self.root / "blobs" / "sha256"
        self.runs_dir = self.root / "runs"
        self.drafts_dir = self.root / "drafts"
        for d in (self.blobs, self.runs_dir, self.drafts_dir):
            d.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._wlock = threading.RLock()
        with self._wlock:
            con = self.db()
            con.executescript(SCHEMA)
            con.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema','simlab-store:1')")

    # ------------------------------------------------------------------ connections
    def db(self) -> sqlite3.Connection:
        con = getattr(self._local, "con", None)
        if con is None:
            con = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA foreign_keys=ON")
            con.execute("PRAGMA busy_timeout=30000")
            self._local.con = con
        return con

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        with self._wlock:
            con = self.db()
            con.execute("BEGIN IMMEDIATE")
            try:
                yield con
            except BaseException:
                con.execute("ROLLBACK")
                raise
            else:
                con.execute("COMMIT")

    def q(self, sql: str, args: tuple = ()) -> list[sqlite3.Row]:
        return self.db().execute(sql, args).fetchall()

    def q1(self, sql: str, args: tuple = ()) -> sqlite3.Row | None:
        return self.db().execute(sql, args).fetchone()

    # ------------------------------------------------------------------ blobs
    def blob_path(self, sha: str) -> Path:
        return self.blobs / sha[:2] / sha

    def put_blob(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        p = self.blob_path(sha)
        if p.exists():
            if hashlib.sha256(p.read_bytes()).hexdigest() != sha:
                raise SimlabError("E_INTERNAL", f"stored blob {sha} is damaged")
            return sha
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f".{sha}.{uuid.uuid4().hex[:8]}")
        tmp.write_bytes(data)
        os.chmod(tmp, 0o444)
        os.replace(tmp, p)
        return sha

    def get_blob(self, sha: str, *, verify: bool = True) -> bytes:
        p = self.blob_path(sha)
        if not p.is_file():
            raise SimlabError("E_UNKNOWN_REF", f"no blob {sha}")
        data = p.read_bytes()
        if verify and hashlib.sha256(data).hexdigest() != sha:
            raise SimlabError("E_SEMANTIC_ASSET_HASH", f"blob {sha} does not match its hash")
        return data

    # ------------------------------------------------------------------ manifests and experiments
    def put_manifest(self, manifest: dict) -> None:
        body = canonical(manifest).decode()
        with self.tx() as db:
            row = db.execute("SELECT body FROM manifests WHERE manifest_id=?", (manifest["manifest_id"],)).fetchone()
            if row is not None:
                if row["body"] != body:
                    raise SimlabError("E_IMMUTABLE", f"manifest {manifest['manifest_id']} is bound and cannot change")
                return
            db.execute("INSERT INTO manifests(manifest_id,manifest_sha256,body,created_at) VALUES(?,?,?,?)",
                       (manifest["manifest_id"], manifest["manifest_sha256"], body, now()))

    def get_manifest(self, manifest_id: str) -> dict | None:
        row = self.q1("SELECT body FROM manifests WHERE manifest_id=?", (manifest_id,))
        return json.loads(row["body"]) if row else None

    def put_experiment(self, experiment: dict) -> bool:
        """Insert a submitted experiment; True if new. Different content under an existing ID is E_IMMUTABLE."""
        body = canonical(experiment).decode()
        sha = hashlib.sha256(body.encode()).hexdigest()
        with self.tx() as db:
            row = db.execute("SELECT sha256 FROM experiments WHERE experiment_id=?", (experiment["experiment_id"],)).fetchone()
            if row is not None:
                if row["sha256"] != sha:
                    raise SimlabError("E_IMMUTABLE", f"experiment {experiment['experiment_id']} was submitted with other content")
                return False
            db.execute("INSERT INTO experiments(experiment_id,sha256,body,manifest_id,created_at) VALUES(?,?,?,?,?)",
                       (experiment["experiment_id"], sha, body, experiment["assets"]["manifest_id"], now()))
            return True

    def get_experiment(self, experiment_id: str) -> dict | None:
        row = self.q1("SELECT body FROM experiments WHERE experiment_id=?", (experiment_id,))
        return json.loads(row["body"]) if row else None

    # ------------------------------------------------------------------ runs
    def create_run(self, experiment_id: str, run_kind: str, *, parent: dict | None = None, replay_of: str | None = None,
                   identity: dict | None = None, hardware: dict | None = None, options: dict | None = None) -> str:
        run_id = new_id("run")
        with self.tx() as db:
            db.execute("INSERT INTO runs(run_id,experiment_id,run_kind,parent,replay_of,status,created_at,identity,hardware,options)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (run_id, experiment_id, run_kind, json.dumps(parent) if parent else None, replay_of, "QUEUED", now(),
                        json.dumps(identity or {}), json.dumps(hardware or {}), json.dumps(options or {})))
        (self.runs_dir / run_id).mkdir(parents=True, exist_ok=True)
        return run_id

    def run_row(self, run_id: str) -> sqlite3.Row:
        row = self.q1("SELECT * FROM runs WHERE run_id=?", (run_id,))
        if row is None:
            raise SimlabError("E_UNKNOWN_RUN", f"no run {run_id}")
        return row

    def set_run(self, run_id: str, **fields: Any) -> None:
        cols, vals = [], []
        for k, v in fields.items():
            cols.append(f"{k}=?")
            vals.append(json.dumps(v) if isinstance(v, (dict, list)) else v)
        with self.tx() as db:
            db.execute(f"UPDATE runs SET {','.join(cols)} WHERE run_id=?", (*vals, run_id))

    def add_trial(self, run_id: str, trial: dict) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO trials(trial_id,run_id,ordinal,purpose,arm_id,condition_id,replicate,episode,pair_id,seeds,params,check_id)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                       (trial["trial_id"], run_id, trial["ordinal"], trial.get("purpose", "counted"), trial["arm_id"],
                        trial["condition"], trial["replicate"], trial["episode"], trial.get("pair_id"),
                        json.dumps(trial["seeds"]), json.dumps(trial["params"], sort_keys=True), trial.get("check_id")))

    def start_attempt(self, run_id: str, trial_id: str, seeds: dict, purpose: str = "counted") -> str:
        attempt_id = new_id("att")
        with self.tx() as db:
            db.execute("INSERT INTO attempts(attempt_id,trial_id,run_id,purpose,status,seeds,started_at) VALUES(?,?,?,?,?,?,?)",
                       (attempt_id, trial_id, run_id, purpose, "RUNNING", json.dumps(seeds), now()))
        return attempt_id

    def blocked_attempt(self, run_id: str, trial_id: str, seeds: dict, reason: str, purpose: str = "counted") -> str:
        attempt_id = new_id("att")
        t = now()
        with self.tx() as db:
            db.execute("INSERT INTO attempts(attempt_id,trial_id,run_id,purpose,status,reason,seeds,started_at,ended_at,stop)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (attempt_id, trial_id, run_id, purpose, "BLOCKED", reason, json.dumps(seeds), t, t, "blocked"))
        return attempt_id

    def end_attempt(self, attempt_id: str, status: str, *, invalid_reason: str | None = None, reason: str = "",
                    stop: str | None = None, state_digest: str | None = None, exec_info: dict | None = None) -> None:
        if (status == "INVALID") != (invalid_reason is not None):
            raise SimlabError("E_INTERNAL", "invalid_reason is required exactly when status is INVALID")
        with self.tx() as db:
            db.execute("UPDATE attempts SET status=?,invalid_reason=?,reason=?,ended_at=?,stop=?,state_digest=?,exec=? WHERE attempt_id=?",
                       (status, invalid_reason, reason, now(), stop, state_digest, json.dumps(exec_info or {}), attempt_id))

    def mark_corrupted(self, attempt_id: str, reason: str) -> None:
        with self.tx() as db:
            db.execute("UPDATE attempts SET status='INVALID', invalid_reason='corrupted_record', reason=? WHERE attempt_id=?",
                       (reason, attempt_id))

    def add_trace(self, row: dict) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO traces(ref,run_id,trial_id,attempt_id,arm_id,signal,unit,path,sha256,n,dim,t_start,t_end,kind)"
                       " VALUES(:ref,:run_id,:trial_id,:attempt_id,:arm_id,:signal,:unit,:path,:sha256,:n,:dim,:t_start,:t_end,:kind)", row)

    def add_events(self, run_id: str, trial_id: str, attempt_id: str, events: list[dict]) -> None:
        with self.tx() as db:
            db.executemany("INSERT INTO events(run_id,trial_id,attempt_id,t,event_id,kind,detail) VALUES(?,?,?,?,?,?,?)",
                           [(run_id, trial_id, attempt_id, float(e["t"]), e["event_id"], e["kind"],
                             json.dumps(e.get("detail", {}), sort_keys=True)) for e in events])

    def add_measurements(self, rows: list[dict]) -> None:
        with self.tx() as db:
            db.executemany("INSERT INTO measurements(run_id,trial_id,attempt_id,measurement_id,scope,key,value,unit,note,source)"
                           " VALUES(:run_id,:trial_id,:attempt_id,:measurement_id,:scope,:key,:value,:unit,:note,:source)",
                           [{"trial_id": None, "attempt_id": None, "key": "{}", "unit": "", "note": "", "source": "primary",
                             **r, "value": json.dumps(r["value"])} for r in rows])

    def put_check(self, run_id: str, check: dict) -> None:
        with self.tx() as db:
            db.execute("INSERT OR REPLACE INTO checks(run_id,check_id,check_kind,required,status,observed,affected) VALUES(?,?,?,?,?,?,?)",
                       (run_id, check["check_id"], check["check_kind"], int(check["required"]), check["status"],
                        json.dumps(check.get("observed", {}), sort_keys=True, default=str),
                        json.dumps(check.get("affected_measurements", []))))

    def add_checkpoint(self, row: dict) -> None:
        with self.tx() as db:
            db.execute("INSERT INTO checkpoints(checkpoint_id,run_id,trial_id,attempt_id,point,time_s,state_sha256,files,model_sha256,meta)"
                       " VALUES(?,?,?,?,?,?,?,?,?,?)",
                       (row["checkpoint_id"], row["run_id"], row["trial_id"], row["attempt_id"], row["point"], row["time_s"],
                        row["state_sha256"], json.dumps(row["files"], sort_keys=True), row["model_sha256"],
                        json.dumps(row.get("meta", {}), sort_keys=True)))

    def get_checkpoint(self, checkpoint_id: str) -> dict | None:
        row = self.q1("SELECT * FROM checkpoints WHERE checkpoint_id=?", (checkpoint_id,))
        if row is None:
            return None
        d = dict(row)
        d["files"], d["meta"] = json.loads(d["files"]), json.loads(d["meta"])
        return d

    # ------------------------------------------------------------------ registry
    def set_capability(self, capability: str, kind: str, status: str, reason: str, evidence_ref: str | None = None,
                       version: str | None = None) -> None:
        with self.tx() as db:
            db.execute("INSERT OR REPLACE INTO registry(capability,kind,status,reason,evidence_ref,version,updated_at) VALUES(?,?,?,?,?,?,?)",
                       (capability, kind, status, reason, evidence_ref, version, now()))
