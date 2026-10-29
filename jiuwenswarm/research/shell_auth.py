"""Scoped native M1 authentication; provider credentials never enter this store."""
from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import secrets
import stat
import re
import copy
import time
import sqlite3
import threading
from functools import wraps
from collections.abc import Mapping
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlsplit

from jiuwenswarm.research.contracts.types import Principal, ResearchError


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def _serialized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


class SessionAuthority:
    """Random grants with durable revocation and atomic one-use bootstrap.

    The caller supplies the protected principal. Browser IDs/query parameters
    are never inputs to grant construction. Revalidate native WS grants before
    every research message, including Settings RPC, rather than only handshake.
    """
    cookie_name = 'ai4r_ws'

    def __init__(self, directory: str | Path, origin: str, *, reusable_bootstrap: bool = False):
        parsed = urlsplit(origin)
        if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.path not in {'', '/'} or parsed.query or parsed.fragment:
            raise ValueError('one exact native origin is required')
        self.origin = f'{parsed.scheme}://{parsed.netloc}'
        self.host = parsed.netloc
        # Cookies are shared across ports on the same host. Keep the established
        # production cookie while isolating parallel local app instances.
        if parsed.port is not None and parsed.port != 5173:
            self.cookie_name = 'ai4r_ws_' + str(parsed.port)
        self.reusable_bootstrap = reusable_bootstrap
        if reusable_bootstrap:
            try:
                local = ipaddress.ip_address(parsed.hostname or '').is_loopback
            except ValueError:
                local = False
            if not local:
                raise ValueError('reusable login requires a loopback IP origin')
        self._lock = threading.RLock()
        supplied = Path(directory)
        if supplied.is_symlink():
            raise ResearchError('auth', 'Invalid credential directory')
        self.root = supplied.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise ResearchError('auth', 'Invalid credential directory')
        os.chmod(self.root, 0o700)
        self.token_path = self.root / 'session-token'
        self.reusable_path = self.root / 'reusable-bootstrap.json'
        db_path = self.root / 'native-sessions.sqlite3'
        if db_path.is_symlink():
            raise ResearchError('auth', 'Invalid session storage')
        self.db = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None)
        os.chmod(db_path, 0o600)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS grants (digest TEXT PRIMARY KEY, family TEXT NOT NULL, kind TEXT NOT NULL, principal TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS challenges (digest TEXT PRIMARY KEY, family TEXT NOT NULL, consumed INTEGER NOT NULL DEFAULT 0)')
        self.db.execute('CREATE TABLE IF NOT EXISTS evaluation_context (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL, family TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS evaluation_grants (id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, context TEXT NOT NULL, startup_sha256 TEXT NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS runner_grants (id TEXT PRIMARY KEY, digest TEXT UNIQUE NOT NULL, parent_digest TEXT NOT NULL, expires_at REAL NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS authority_settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)')
        self.db.execute("INSERT OR REPLACE INTO authority_settings VALUES('origin',?)",(self.origin,))
        self._run_lookup = None
        self._run_reconcile = None

    @_serialized
    def close(self) -> None:
        self.db.close()

    @staticmethod
    def _encode(principal: Principal) -> str:
        if not principal.account_id:
            raise ResearchError('auth', 'A protected product account is required')
        return json.dumps({'account_id': principal.account_id, 'workspace_ids': sorted(principal.workspace_ids),
                           'operations': sorted(principal.operations), 'audiences': sorted(principal.audiences)}, separators=(',', ':'))

    @_serialized
    def initialize(self, principal: Principal) -> str:
        token, challenge, family = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_hex(16)
        encoded = self._encode(principal)
        if self.reusable_bootstrap:
            saved = None
            try:
                fd = os.open(self.reusable_path, os.O_RDONLY | os.O_NOFOLLOW)
            except FileNotFoundError:
                pass
            else:
                with os.fdopen(fd, 'r', encoding='utf-8') as handle:
                    info = os.fstat(handle.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 8192
                            or os.name == 'posix' and (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o600)):
                        raise ResearchError('auth', 'Invalid reusable login custody')
                    saved = json.load(handle)
            if (isinstance(saved, dict) and set(saved) == {'challenge', 'origin', 'principal'}
                    and saved['origin'] == self.origin and saved['principal'] == encoded
                    and isinstance(saved['challenge'], str) and re.fullmatch(r'[A-Za-z0-9_-]{43}', saved['challenge'])):
                challenge = saved['challenge']
            temporary = self.root / ('.bootstrap-' + secrets.token_hex(12))
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
                    json.dump({'challenge': challenge, 'origin': self.origin, 'principal': encoded}, handle)
                    handle.flush(); os.fsync(handle.fileno())
                os.replace(temporary, self.reusable_path)
            finally:
                temporary.unlink(missing_ok=True)
        # Do not follow a planted token symlink or publish a broadly readable file.
        temporary = self.root / ('.session-' + secrets.token_hex(12))
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(token.encode('ascii')); handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, self.token_path)
            os.chmod(self.token_path, 0o600)
        finally:
            temporary.unlink(missing_ok=True)
        with self.db:
            self.db.execute('UPDATE grants SET revoked=1')
            self.db.execute('UPDATE challenges SET consumed=1')
            self.db.execute('DELETE FROM evaluation_context')
            self.db.execute('INSERT INTO grants(digest,family,kind,principal) VALUES(?,?,?,?)', (_digest(token), family, 'http', encoded))
            self.db.execute('INSERT OR REPLACE INTO challenges(digest,family) VALUES(?,?)', (_digest(challenge), family))
        return self.origin + '/#research_bootstrap=' + challenge

    def _check_origin(self, origin: str | None, host: str | None, *, required: bool = True) -> None:
        if host != self.host or (required and origin != self.origin) or (origin is not None and origin != self.origin):
            raise ResearchError('auth', 'Native origin is not authorized')

    @_serialized
    def bootstrap(self, challenge: str, *, origin: str | None, host: str | None) -> dict:
        self._check_origin(origin, host)
        if not isinstance(challenge, str) or not 20 <= len(challenge) <= 256:
            raise ResearchError('auth', 'Invalid bootstrap')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT family FROM challenges WHERE digest=? AND consumed=0', (_digest(challenge),)).fetchone()
            if row is None:
                raise ResearchError('auth', 'Bootstrap is unavailable')
            family = row[0]
            grant = self.db.execute('SELECT principal FROM grants WHERE family=? AND kind=? AND revoked=0', (family, 'http')).fetchone()
            if grant is None:
                raise ResearchError('auth', 'Bootstrap is unavailable')
            token = self.token_path.read_text(encoding='ascii')
            if self.db.execute('SELECT 1 FROM grants WHERE digest=? AND family=? AND kind=? AND revoked=0', (_digest(token), family, 'http')).fetchone() is None:
                raise ResearchError('auth', 'Bootstrap is unavailable')
            ws_token = secrets.token_urlsafe(32)
            self.db.execute('INSERT INTO grants(digest,family,kind,principal) VALUES(?,?,?,?)', (_digest(ws_token), family, 'ws', grant[0]))
            if not self.reusable_bootstrap:
                self.db.execute('UPDATE challenges SET consumed=1 WHERE digest=?', (_digest(challenge),))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        cookie = f'{self.cookie_name}={ws_token}; Path=/; HttpOnly; SameSite=Strict'
        if self.origin.startswith('https:'):
            cookie += '; Secure'
        return {'token': token, 'ws_token': ws_token, 'set_cookie': cookie}

    @_serialized
    def _lookup(self, token: str, kind: str, operation: str, workspace_id: str | None, audience: str | None) -> Principal:
        if not isinstance(token, str) or not 20 <= len(token) <= 256:
            raise ResearchError('auth', 'Authentication required')
        kinds = ('http', 'evaluation_http', 'runner_http') if kind == 'http' else (kind,)
        row = self.db.execute('SELECT principal,kind FROM grants WHERE digest=? AND kind IN (' + ','.join('?' for _ in kinds) + ') AND revoked=0', (_digest(token), *kinds)).fetchone()
        if row is None:
            raise ResearchError('auth', 'Authentication required')
        if row[1] == 'evaluation_http':
            self._evaluation_scope(token)
        if row[1] == 'runner_http':
            grant=self.db.execute('SELECT parent_digest,expires_at FROM runner_grants WHERE digest=?',(_digest(token),)).fetchone()
            if (grant is None or grant[1]<=time.time() or self.db.execute(
                    "SELECT 1 FROM grants WHERE digest=? AND kind='http' AND revoked=0",(grant[0],)).fetchone() is None):
                raise ResearchError('auth','Runner grant expired or its native startup was revoked',{'http_status':403})
        data = json.loads(row[0])
        principal = Principal(data['account_id'], frozenset(data['workspace_ids']), frozenset(data['operations']), frozenset(data['audiences']))
        try:
            principal.require(operation, workspace_id)
        except ResearchError as exc:
            raise ResearchError('auth', 'Operation or workspace is outside the authenticated grant', {'http_status': 403}) from exc
        if audience is not None and audience not in principal.audiences:
            raise ResearchError('auth', 'Audience is outside the authenticated grant', {'http_status': 403})
        return principal

    def authenticate(self, authorization: str | None, operation: str, workspace_id: str | None = None,
                     audience: str | None = None) -> Principal:
        if not authorization or not authorization.startswith('Bearer ') or authorization.count(' ') != 1:
            raise ResearchError('auth', 'Bearer authentication required')
        return self._lookup(authorization[7:], 'http', operation, workspace_id, audience)

    def authenticate_ws(self, headers: Mapping[str, str], operation: str, workspace_id: str | None = None) -> Principal:
        headers = {key.lower(): value for key, value in headers.items()}
        authorization = headers.get('authorization')
        self._check_origin(headers.get('origin'), headers.get('host'), required=not bool(authorization))
        if authorization:
            if not authorization.startswith('Bearer ') or authorization.count(' ') != 1:
                raise ResearchError('auth', 'Bearer authentication required')
            token = authorization[7:]
            row = self.db.execute('SELECT kind FROM grants WHERE digest=? AND revoked=0', (_digest(token),)).fetchone()
            if row is None or row[0] != 'http':
                raise ResearchError('auth', 'Native WebSocket grant required')
            return self._lookup(token, 'http', operation, workspace_id, None)
        cookie = SimpleCookie()
        try:
            cookie.load(headers.get('cookie', ''))
        except Exception as exc:
            raise ResearchError('auth', 'Native authentication required') from exc
        morsel = cookie.get(self.cookie_name)
        return self._lookup(morsel.value if morsel else '', 'ws', operation, workspace_id, None)

    @_serialized
    def revoke(self, token: str) -> None:
        with self.db:
            row = self.db.execute('SELECT family FROM grants WHERE digest=?', (_digest(token),)).fetchone()
            if row:
                self.db.execute('UPDATE grants SET revoked=1 WHERE family=?', (row[0],))
                self.db.execute('UPDATE challenges SET consumed=1 WHERE family=?', (row[0],))
                if self.reusable_bootstrap and self.reusable_path.exists():
                    saved = json.loads(self.reusable_path.read_text(encoding='utf-8'))
                    if self.db.execute('SELECT 1 FROM challenges WHERE digest=? AND family=?',
                                       (_digest(saved['challenge']), row[0])).fetchone():
                        self.reusable_path.unlink()


    @staticmethod
    def _canonical(value):
        return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)

    @staticmethod
    def _pin(value):
        return (isinstance(value,dict) and set(value)=={'id','sha256'} and isinstance(value['id'],str)
                and 0<len(value['id'])<=256 and isinstance(value['sha256'],str)
                and re.fullmatch('[a-f0-9]{64}',value['sha256']) is not None)

    @_serialized
    def configure_evaluation(self,context,*,run_lookup,run_reconcile,campaign_id=None,
                             runtime_ref=None,assets_ref=None):
        """Protected composition only: freeze actual startup, never HTTP input."""
        keys={'account_id','workspace_id','configuration_ref','profile_ref','profile_id'}
        if (not isinstance(context,dict) or set(context)!=keys or not callable(run_lookup) or not callable(run_reconcile)
                or any(not isinstance(context[k],str) or not context[k] or len(context[k])>256 for k in ('account_id','workspace_id','profile_id'))
                or not all(self._pin(context[k]) for k in ('configuration_ref','profile_ref'))
                or campaign_id is not None and (not isinstance(campaign_id,str) or not campaign_id or len(campaign_id)>256)):
            raise ResearchError('auth','Approved evaluation startup context is unavailable')
        if ((runtime_ref is None) != (assets_ref is None)
                or runtime_ref is not None and not all(self._pin(value) for value in (runtime_ref,assets_ref))):
            raise ResearchError('auth','Private evaluation startup requires both exact runtime and asset references')
        rows=self.db.execute("SELECT family,principal FROM grants WHERE kind='http' AND revoked=0").fetchall()
        if len(rows)!=1:raise ResearchError('auth','Approved native startup identity is unavailable')
        principal=json.loads(rows[0][1])
        if context['account_id']!=principal['account_id'] or context['workspace_id'] not in principal['workspace_ids']:
            raise ResearchError('auth','Evaluation context differs from the protected startup identity')
        captured=dict(context,campaign_id=campaign_id)
        if runtime_ref is not None:
            captured.update(runtime_ref=copy.deepcopy(runtime_ref),assets_ref=copy.deepcopy(assets_ref))
        value=self._canonical(captured)
        previous=self.db.execute('SELECT value,family FROM evaluation_context WHERE id=1').fetchone()
        if previous is not None and previous!=(value,rows[0][0]):
            self.db.execute("UPDATE grants SET revoked=1 WHERE kind='evaluation_http'")
        self.db.execute('INSERT OR REPLACE INTO evaluation_context VALUES(1,?,?)',(value,rows[0][0]))
        self._run_lookup,self._run_reconcile=run_lookup,run_reconcile

    def _startup_evaluation(self):
        row=self.db.execute('SELECT value,family FROM evaluation_context WHERE id=1').fetchone()
        if row is None or self.db.execute("SELECT 1 FROM grants WHERE family=? AND kind='http' AND revoked=0",(row[1],)).fetchone() is None:
            raise ResearchError('auth','Approved evaluation startup is unavailable',{'http_status':403})
        return json.loads(row[0]),hashlib.sha256(row[0].encode('utf-8')).hexdigest()

    def _evaluation_scope(self,token):
        row=self.db.execute('SELECT context,startup_sha256 FROM evaluation_grants WHERE digest=?',(_digest(token),)).fetchone()
        if row is None:raise ResearchError('auth','Evaluation grant context is unavailable')
        _,current=self._startup_evaluation()
        if current!=row[1]:raise ResearchError('auth','Evaluation grant is stale',{'http_status':403})
        return json.loads(row[0])

    @staticmethod
    def _operator_only():
        if os.name!='posix' or os.geteuid()!=0:
            raise ResearchError('auth','Only the OS operator may manage evaluation credentials',{'http_status':403})

    @_serialized
    def issue_evaluation(self,binding,output):
        """Root-only finite issuance; token leaves only through an exclusive file."""
        self._operator_only()
        context,startup=self._startup_evaluation()
        keys={'schema','workspace_id','configuration_ref','profile_ref','profile_id','campaign_id'}
        if (not isinstance(binding,dict) or set(binding)!=keys or binding['schema']!='ai4r-evaluation-grant:1'
                or not isinstance(binding['campaign_id'],str) or not 1<=len(binding['campaign_id'])<=256
                or any(binding[k]!=context[k] for k in ('workspace_id','configuration_ref','profile_ref','profile_id'))
                or context['campaign_id'] is not None and context['campaign_id']!=binding['campaign_id']):
            raise ResearchError('auth','Campaign binding differs from the approved startup',{'http_status':403})
        path=Path(output)
        if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
            raise ResearchError('auth','Credential output path is unsafe')
        parent=path.parent.stat()
        if not stat.S_ISDIR(parent.st_mode) or parent.st_uid!=0 or parent.st_mode&0o022:
            raise ResearchError('auth','Credential output requires protected operator custody')
        token=secrets.token_urlsafe(32);family=secrets.token_hex(16);ident='evaluation:'+secrets.token_hex(16)
        principal=Principal(context['account_id'],frozenset({context['workspace_id']}),
            frozenset({'readiness','submit','status','reconcile','cancel','export','evaluation_profile'}),frozenset({'researcher','reviewer'}))
        scope=dict(binding,account_id=context['account_id'])
        # These pins are protected startup metadata, not new public grant fields.
        # Their inclusion in the startup digest revokes grants on either change.
        for key in ('runtime_ref','assets_ref'):
            if key in context:scope[key]=copy.deepcopy(context[key])
        descriptor=None;created=False
        self.db.execute('BEGIN IMMEDIATE')
        try:
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600);created=True
            os.fchmod(descriptor,0o600);os.fchown(descriptor,11001,11001)
            with os.fdopen(descriptor,'wb') as stream:
                descriptor=None;stream.write(token.encode('ascii'));stream.flush();os.fsync(stream.fileno())
            self.db.execute('INSERT INTO grants(digest,family,kind,principal) VALUES(?,?,?,?)',(_digest(token),family,'evaluation_http',self._encode(principal)))
            self.db.execute('INSERT INTO evaluation_grants VALUES(?,?,?,?)',(ident,_digest(token),self._canonical(scope),startup))
            directory=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            try:os.fsync(directory)
            finally:os.close(directory)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            if descriptor is not None:os.close(descriptor)
            if created:path.unlink(missing_ok=True)
            raise
        return {'grant_id':ident,'status':'issued','token_file':str(path)}

    @_serialized
    def revoke_evaluation(self,grant_id):
        self._operator_only()
        row=self.db.execute('SELECT digest FROM evaluation_grants WHERE id=?',(grant_id,)).fetchone()
        if row is None:raise ResearchError('not_found','Evaluation grant is unavailable')
        self.db.execute("UPDATE grants SET revoked=1 WHERE digest=? AND kind='evaluation_http'",(row[0],))
        return {'grant_id':grant_id,'status':'revoked'}

    @_serialized
    def issue_runner(self,binding,output):
        """Root-only short-lived ordinary HTTP grant; never grants settings/WS."""
        self._operator_only()
        if (not isinstance(binding,dict) or set(binding)!={'schema','account_id','workspace_id','expires_in_s'}
                or binding['schema']!='ai4r-runner-grant:1' or type(binding['expires_in_s']) is not int
                or not 1<=binding['expires_in_s']<=7*86400):
            raise ResearchError('validation','An exact finite runner binding is required')
        rows=self.db.execute("SELECT digest,principal FROM grants WHERE kind='http' AND revoked=0").fetchall()
        if len(rows)!=1:raise ResearchError('auth','One active native startup identity is required')
        parent=json.loads(rows[0][1])
        operations=frozenset({'readiness','submit','status','reconcile','cancel','export','upload','list_uploads'})
        if (binding['account_id']!=parent['account_id'] or binding['workspace_id'] not in parent['workspace_ids']
                or not operations<=set(parent['operations']) or 'researcher' not in parent['audiences']):
            raise ResearchError('auth','Runner binding exceeds the actual native startup grant')
        path=Path(output)
        if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)):
            raise ResearchError('auth','Credential output path is unsafe')
        directory_info=path.parent.stat()
        if not stat.S_ISDIR(directory_info.st_mode) or directory_info.st_uid!=0 or directory_info.st_mode&0o022:
            raise ResearchError('auth','Credential output requires protected operator custody')
        token=secrets.token_urlsafe(32);ident='runner:'+secrets.token_hex(16);family=secrets.token_hex(16)
        expires=time.time()+binding['expires_in_s']
        principal=Principal(binding['account_id'],frozenset({binding['workspace_id']}),operations,frozenset({'researcher'}))
        created=False;descriptor=None
        self.db.execute('BEGIN IMMEDIATE')
        try:
            descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600);created=True
            os.fchmod(descriptor,0o600);os.fchown(descriptor,11001,11001)
            with os.fdopen(descriptor,'wb') as stream:
                descriptor=None;stream.write(token.encode('ascii'));stream.flush();os.fsync(stream.fileno())
            self.db.execute('INSERT INTO grants(digest,family,kind,principal) VALUES(?,?,?,?)',
                (_digest(token),family,'runner_http',self._encode(principal)))
            self.db.execute('INSERT INTO runner_grants VALUES(?,?,?,?)',(ident,_digest(token),rows[0][0],expires))
            directory=os.open(path.parent,os.O_RDONLY|getattr(os,'O_DIRECTORY',0))
            try:os.fsync(directory)
            finally:os.close(directory)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            if descriptor is not None:os.close(descriptor)
            if created:path.unlink(missing_ok=True)
            raise
        return {'grant_id':ident,'status':'issued','token_file':str(path),'expires_at':expires}

    @_serialized
    def revoke_runner(self,grant_id):
        self._operator_only()
        row=self.db.execute('SELECT digest FROM runner_grants WHERE id=?',(grant_id,)).fetchone()
        if row is None:raise ResearchError('not_found','Runner grant is unavailable')
        self.db.execute("UPDATE grants SET revoked=1 WHERE digest=? AND kind='runner_http'",(row[0],))
        return {'grant_id':grant_id,'status':'revoked'}

    @_serialized
    def authorize_evaluation(self,authorization,operation,*,submission=None,run_id=None,client_request_id=None):
        """Bind this request to its actual token; shared account is insufficient."""
        principal=self.authenticate(authorization,operation)
        token=authorization[7:]
        row=self.db.execute('SELECT kind FROM grants WHERE digest=? AND revoked=0',(_digest(token),)).fetchone()
        if row[0]=='runner_http' and operation=='submit' and submission is not None:
            if submission.get('profile_id') is not None or submission.get('evaluation') is not None or submission.get('fault_id') is not None:
                raise ResearchError('auth','Ordinary runner grants cannot submit evaluation work',{'http_status':403})
        if row[0]!='evaluation_http':return
        scope=self._evaluation_scope(token)
        def check(value,workspace,account):
            if (account!=scope['account_id'] or workspace!=scope['workspace_id'] or not isinstance(value,dict)
                    or value.get('profile_id')!=scope['profile_id'] or value.get('configuration_ref')!=scope['configuration_ref']
                    or not isinstance(value.get('evaluation'),dict) or value['evaluation'].get('campaign_id')!=scope['campaign_id']):
                raise ResearchError('auth','Run differs from the evaluation grant',{'http_status':403})
        if operation=='submit':
            check(submission,submission.get('workspace_id') if isinstance(submission,dict) else None,principal.account_id)
        elif operation in {'status','export','cancel','reconcile'}:
            if self._run_lookup is None or self._run_reconcile is None:raise ResearchError('auth','Protected run lookup is unavailable',{'http_status':403})
            try:
                rows=([self._run_lookup(run_id)] if run_id is not None else self._run_reconcile(principal.account_id,client_request_id))
            except (KeyError,ResearchError) as exc:raise ResearchError('not_found','Run is unavailable') from exc
            if not isinstance(rows,list):raise ResearchError('internal','Protected reconciliation is invalid')
            for run in rows:check(run.get('submission'),run.get('workspace_id'),run.get('account_id'))


    @_serialized
    def authorize_evaluation_entry(self,authorization,*,profile_id,workspace_id,campaign_id,configuration_ref,
                                   profile_ref=None,runtime_ref=None,assets_ref=None):
        """E2/E3/E4/E5 use their actual grant, without inventing an E1 body."""
        self.authenticate(authorization,'evaluation_profile',workspace_id)
        token=authorization[7:]
        row=self.db.execute('SELECT kind FROM grants WHERE digest=? AND revoked=0',(_digest(token),)).fetchone()
        if row is None or row[0]!='evaluation_http':
            raise ResearchError('auth','A separate evaluation-profile grant is required',{'http_status':403})
        scope=self._evaluation_scope(token)
        expected=[('profile_id',profile_id),('workspace_id',workspace_id),
                  ('campaign_id',campaign_id),('configuration_ref',configuration_ref)]
        if profile_ref is not None:
            if not self._pin(profile_ref):raise ResearchError('auth','Invalid stored evaluation profile',{'http_status':403})
            expected.append(('profile_ref',profile_ref))
        if runtime_ref is not None or assets_ref is not None:
            if not all(self._pin(value) for value in (runtime_ref,assets_ref)):
                raise ResearchError('auth','Invalid private evaluation binding',{'http_status':403})
            expected.extend([('runtime_ref',runtime_ref),('assets_ref',assets_ref)])
        if any(value!=scope.get(key) for key,value in expected):
            raise ResearchError('auth','Evaluation entry differs from its token context',{'http_status':403})
