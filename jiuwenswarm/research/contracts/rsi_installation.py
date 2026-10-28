"""OS-root RSI authority installation and current producer observation.

Only fixed read-only mount locations are consumed. The root-owned typed index
is distinct from new live subjects supplied by trusted Python composition.
No installation field selects Python code, a callback, command or filesystem
path. This core module never imports the RSI implementation.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct

from .validators import validate
from .rsi_security import RSIQualification
from .types import ResearchError

ROOT=Path('/run/ai4r-rsi-security')
INSTALLATION_FILE=ROOT/'installation.json'
ORIGINALS_ROOT=ROOT/'originals'
RUNTIME_OBSERVATION_FILE=ROOT/'runtime-observation.json'
SCOPE_SOCKET=Path('/run/ai4r-rsi-security-ipc/scope.sock')
SCOPE_PROTOCOL='ai4r-rsi-current-scope:1'
SCHEMA='urn:ai4r:private:rsi-security-installation:1'
MAX_ORIGINAL=16*1024*1024
MAX_FRAME=65536


class InstallationUnavailable(ValueError):pass


def _need(value):
    if not value:raise InstallationUnavailable('Protected RSI security installation or current producer evidence is unavailable')


def _json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            _need(key not in result);result[key]=value
        return result
    return json.loads(raw.decode('utf8'),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(InstallationUnavailable('Nonfinite installation capture')))


def _encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def _ref(pin):
    _need(isinstance(pin,dict) and set(pin)=={'id','sha256'} and isinstance(pin['id'],str) and pin['id']
          and isinstance(pin['sha256'],str) and re.fullmatch('[a-f0-9]{64}',pin['sha256']))


def _path(path):
    path=Path(path)
    _need(path.is_absolute() and '..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)))
    for parent in path.parents:
        meta=parent.stat()
        _need(meta.st_uid==0 and (not meta.st_mode&0o022 or meta.st_mode&stat.S_ISVTX))
    return path


def _root_file(path,maximum):
    path=_path(path)
    descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(descriptor)
        _need(stat.S_ISREG(meta.st_mode) and meta.st_uid==0 and meta.st_gid==13000
              and stat.S_IMODE(meta.st_mode)==0o640 and meta.st_nlink==1 and 0<=meta.st_size<=maximum)
        with os.fdopen(descriptor,'rb',closefd=False) as stream:raw=stream.read(maximum+1)
        _need(len(raw)<=maximum);return raw
    finally:os.close(descriptor)


class SecurityInstallation:
    """Immutable root manifest; every read rechecks exact installed originals."""
    def __init__(self,raw):
        value=_json(raw);validate(SCHEMA,value)
        self._raw=raw;self._value=value;self._rows={};self._identities={}
        for row in value['originals']:
            pin=row['ref'];identity=_encoded(pin)
            _need(identity not in self._rows)
            # One opaque identity cannot select two originals in the root index.
            _need(pin['id'] not in self._identities)
            self._rows[identity]=copy.deepcopy(row)
            self._identities[pin['id']]=pin['sha256']
        self._public_index_raw=_root_file(ORIGINALS_ROOT/'original-byte-index.json',4*1024*1024)
        public_index=_json(self._public_index_raw)
        _need(public_index=={'schema':'ai4r-original-bytes:1',
            'refs':{row['ref']['id']:row['ref']['sha256'] for row in value['originals']}})
        self.qualification_ref=copy.deepcopy(value['qualification_ref'])
        self.scope_ref=copy.deepcopy(value['scope_ref'])
        self.key_id=value['custodian_key_id']
        self.public_key=base64.b64decode(value['custodian_public_key']+'='*(-len(value['custodian_public_key'])%4),altchars=b'-_',validate=True)
        _need(len(self.public_key)==32)
        for name in ('qualification_ref','scope_ref','validation_profile_ref','assertion_manifest_ref','attack_pins_ref','runtime_observation_ref'):
            self.read(value[name])
        self.scope=self.get(self.scope_ref)
        validate('urn:ai4r:private:rsi-security-scope:1',self.scope)
        qualification=self.get(self.qualification_ref)
        validate('urn:ai4r:private:rsi-security-qualification:1',qualification)
        _need(qualification['scope_ref']==self.scope_ref)
        self.current_runtime_observation()

    def assert_current(self):
        _need(_root_file(INSTALLATION_FILE,4*1024*1024)==self._raw)
        if hasattr(self,'_public_index_raw'):
            _need(_root_file(ORIGINALS_ROOT/'original-byte-index.json',4*1024*1024)==self._public_index_raw)

    def read(self,pin):
        _ref(pin);self.assert_current()
        row=self._rows.get(_encoded(pin));_need(row is not None)
        raw=_root_file(ORIGINALS_ROOT/(pin['sha256']+'.bytes'),MAX_ORIGINAL)
        _need(hashlib.sha256(raw).hexdigest()==pin['sha256']);return raw

    def get(self,pin):return _json(self.read(pin))

    def record_kind(self,pin):
        self.read(pin);return self._rows[_encoded(pin)]['kind']

    def current_runtime_observation(self):
        self.assert_current()
        raw=_root_file(RUNTIME_OBSERVATION_FILE,65536)
        pin=self._value['runtime_observation_ref']
        _need(hashlib.sha256(raw).hexdigest()==pin['sha256'] and self.read(pin)==raw)
        value=_json(raw);validate('urn:ai4r:private:rsi-runtime-observation:1',value)
        _need(all(value[key]==self.scope[key] for key in ('runtime_build_ref','environment_ref','worker_profile_refs')))
        return value

    def scope_request(self):
        self.assert_current()
        return {'protocol':SCOPE_PROTOCOL,'session_id':self._value['rpc_session_id'],
            'capability':self._value['rpc_capability'],'operation':'current_scope',
            'payload':{'scope_ref':copy.deepcopy(self.scope_ref)}}


def load_installation():
    """Return None only for absent fixed installation; malformed data rejects."""
    if not INSTALLATION_FILE.exists() and not INSTALLATION_FILE.is_symlink():return None
    try:
        directory=_path(ROOT).stat()
        _need(stat.S_ISDIR(directory.st_mode) and directory.st_uid==0 and directory.st_gid==13000
              and stat.S_IMODE(directory.st_mode)==0o750)
        return SecurityInstallation(_root_file(INSTALLATION_FILE,4*1024*1024))
    except (ValueError,KeyError,TypeError,OSError,AttributeError,RecursionError,ResearchError):
        raise InstallationUnavailable('Protected RSI security installation is unavailable') from None


def _receive(sock,size):
    parts=[]
    while size:
        raw=sock.recv(size);_need(bool(raw));parts.append(raw);size-=len(raw)
    return b''.join(parts)


def _scope_socket_path():
    path=_path(SCOPE_SOCKET);directory=path.parent.stat();meta=path.lstat()
    _need(stat.S_ISDIR(directory.st_mode) and directory.st_uid==0 and directory.st_gid==13000
          and stat.S_IMODE(directory.st_mode)==0o710 and stat.S_ISSOCK(meta.st_mode)
          and meta.st_uid==0 and meta.st_gid==13000 and stat.S_IMODE(meta.st_mode)==0o660)
    return path


class LiveProducerScopeObserver:
    """Fresh root-peer observation of the actual producer on every require."""
    def __init__(self,installation):
        _need(type(installation) is SecurityInstallation);self._installation=installation
    def __call__(self,scope):
        try:
            installation=self._installation;installation.assert_current()
            _need(scope==installation.scope)
            installation.current_runtime_observation()
            path=_scope_socket_path()
            _need(hasattr(socket,'SO_PEERCRED'))
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(15);client.connect(str(path))
                _,uid,_=struct.unpack('3i',client.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12));_need(uid==0)
                raw=_encoded(installation.scope_request());_need(len(raw)<=MAX_FRAME)
                client.sendall(struct.pack('!I',len(raw))+raw)
                size=struct.unpack('!I',_receive(client,4))[0];_need(0<size<=MAX_FRAME)
                reply=_json(_receive(client,size))
            _need(set(reply)=={'protocol','result'} and reply['protocol']==SCOPE_PROTOCOL and reply['result']==scope)
            installation.assert_current();return copy.deepcopy(scope)
        except (ValueError,KeyError,TypeError,OSError,AttributeError,RecursionError,ResearchError):
            raise InstallationUnavailable('Current root-owned RSI producer scope is unavailable') from None


class _QualificationRecords:
    def __init__(self,installation,store):self.installation,self.store=installation,store
    def read(self,pin):
        # Installed qualification originals cannot be shadowed by a live body.
        _ref(pin)
        if _encoded(pin) in self.installation._rows:return self.installation.read(pin)
        _need(pin['id'] not in self.installation._identities)
        self.installation.assert_current();_need(self.store is not None)
        read=getattr(self.store,'read_blob',None) or self.store.read
        raw=read(pin);_ref(pin)
        _need(isinstance(raw,bytes) and 0<=len(raw)<=MAX_ORIGINAL and hashlib.sha256(raw).hexdigest()==pin['sha256'])
        return raw
    def record_kind(self,pin):
        if _encoded(pin) in self.installation._rows:return self.installation.record_kind(pin)
        self.read(pin);_need(self.store is not None and callable(getattr(self.store,'record_kind',None)))
        return self.store.record_kind(pin)


class InstalledQualification:
    """Recompose current independent authority for every new effect check."""
    def __init__(self,installation,*,scope_observer,store=None,candidate_resolver=None):
        _need(type(installation) is SecurityInstallation)
        self.installation=installation;self.scope_observer=scope_observer
        self.records=_QualificationRecords(installation,store);self.candidate_resolver=candidate_resolver

    def verification_profile(self):
        # Installed module identity, never an installation-selected factory.
        from .rsi_security_profile import recompute_validation_profile
        installation=self.installation
        pins=installation.get(installation._value['validation_profile_ref'])
        _need(pins['assertion_manifest_ref']==installation._value['assertion_manifest_ref']
              and pins['attack_pins_ref']==installation._value['attack_pins_ref']
              and pins['worker_profile_refs']==installation.scope['worker_profile_refs'])
        return recompute_validation_profile(installation.read,installation._value['validation_profile_ref'])

    def require(self,operation,*,session_ref,worker_profile_ref=None,candidate_ref=None):
        # These owner identities are fixed in code. No caller receipt or ready
        # boolean replaces current source/profile/case recomputation.
        from .rsi_security_cases import FiniteCaseObserver
        installation=self.installation;installation.assert_current()
        installation.current_runtime_observation()
        profile=self.verification_profile()
        pins=installation.get(installation._value['attack_pins_ref'])
        observer=FiniteCaseObserver(self.records.read,self.records.record_kind,attack_pins=pins,
            public_key=installation.public_key,key_id=installation.key_id)
        authority=RSIQualification(self.records.read,installation.qualification_ref,kind_reader=self.records.record_kind,
            scope_observer=self.scope_observer,validation_profile=profile,case_observer=observer,
            public_key=installation.public_key,key_id=installation.key_id,candidate_resolver=self.candidate_resolver)
        return authority.require(operation,session_ref=session_ref,worker_profile_ref=worker_profile_ref,candidate_ref=candidate_ref)


def installed_consumer_qualification(store=None,*,candidate_resolver=None):
    """Core/controller/custodian authority with fresh producer IPC observation."""
    installation=load_installation()
    if installation is None:return None
    return InstalledQualification(installation,scope_observer=LiveProducerScopeObserver(installation),
        store=store,candidate_resolver=candidate_resolver)


def installation_public_roots():
    """Only the fixed root-approved publication may augment worker readers."""
    return (str(ORIGINALS_ROOT),) if load_installation() is not None else ()
