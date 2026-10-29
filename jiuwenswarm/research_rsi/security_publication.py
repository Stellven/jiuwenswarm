"""Root-only immutable publication after complete independent qualification.

No key is generated or imported. No program, campaign, worker, model or scope
service is started. Missing current full evidence leaves the mounted directory
untouched. The fixed installation manifest becomes visible last.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import stat

from jiuwenswarm.research.contracts import rsi_installation as installation
from jiuwenswarm.research.contracts import ResearchError
from jiuwenswarm.research.contracts.rsi_security import RSIQualification
from jiuwenswarm.research.contracts.rsi_security_cases import FiniteCaseObserver
from .records import encoded, _install_exclusive
from .security_profile import build_verification_profile
from .security_scope import RuntimeScopeObserver, _root_bytes
from .session_policy import validate_private
from .profiles import freeze_profile
from .worker import validate_profile

MAX_TOTAL=128*1024*1024


def _need(value):
    if not value:raise ValueError('Complete independently current security installation evidence unavailable')


def _root_empty():
    _need(os.name=='posix' and hasattr(os,'geteuid') and os.geteuid()==0)
    root=installation.ROOT
    _need(root.is_absolute() and '..' not in root.parts and not any(path.is_symlink() for path in (root,*root.parents)))
    for parent in root.parents:
        meta=parent.stat();_need(meta.st_uid==0 and (not meta.st_mode&0o022 or meta.st_mode&stat.S_ISVTX))
    meta=root.stat()
    _need(stat.S_ISDIR(meta.st_mode) and meta.st_uid==0 and meta.st_gid==13000 and stat.S_IMODE(meta.st_mode)==0o750)
    _need(not any(root.iterdir()))
    return root


class _Originals:
    def __init__(self,rows,read,kind_reader):
        self.rows={};self.raw={};self.used=set();self.kinds={};total=0;ids=set()
        for row in rows:
            pin=row['ref'];key=encoded(pin)
            _need(key not in self.rows and pin['id'] not in ids)
            ids.add(pin['id']);self.rows[key]=copy.deepcopy(row)
            actual_kind=kind_reader(pin)
            _need(actual_kind==row['kind'] and not any(word in actual_kind.replace('_','-') for word in
                ('private-key','signing-key','signer-key','credential','account-journal','event-store')))
            value=read(pin)
            _need(isinstance(value,bytes) and 0<=len(value)<=installation.MAX_ORIGINAL
                  and hashlib.sha256(value).hexdigest()==pin['sha256'])
            total+=len(value);_need(total<=MAX_TOTAL)
            self.raw[key]=value;self.kinds[key]=row['kind']

    def read(self,pin):
        key=encoded(pin);_need(key in self.raw);self.used.add(key);return self.raw[key]

    def kind(self,pin):
        self.read(pin);return self.kinds[encoded(pin)]

    def get(self,pin):return json.loads(self.read(pin))


def _validated(manifest,*,read,kind_reader,authority,current_observer,installed_paths):
    validate_private(installation.SCHEMA,manifest)
    _need(type(authority) is RSIQualification and type(current_observer) is RuntimeScopeObserver
          and authority.scope_observer is current_observer and authority.ref==manifest['qualification_ref']
          and authority.read==read and authority.kind_reader==kind_reader)
    public=base64.b64decode(manifest['custodian_public_key']+'='*(-len(manifest['custodian_public_key'])%4),altchars=b'-_',validate=True)
    _need(len(public)==32 and authority.public_key==public and authority.key_id==manifest['custodian_key_id'])
    originals=_Originals(manifest['originals'],read,kind_reader)
    qualification=originals.get(manifest['qualification_ref']);scope=originals.get(manifest['scope_ref'])
    _need(qualification['scope_ref']==manifest['scope_ref'])
    validate_private('urn:ai4r:private:rsi-security-qualification:1',qualification)
    validate_private('urn:ai4r:private:rsi-security-scope:1',scope)
    _need(current_observer(scope)==scope)
    runtime=originals.read(manifest['runtime_observation_ref'])
    validate_private('urn:ai4r:private:rsi-runtime-observation:1',json.loads(runtime))
    # This path belongs to the exact installed observer instance; no manifest
    # field or caller configuration selects a filesystem path here.
    _need(runtime==_root_bytes(current_observer._capture_file,65536))
    pins=originals.get(manifest['validation_profile_ref'])
    _need(pins['assertion_manifest_ref']==manifest['assertion_manifest_ref']
          and pins['attack_pins_ref']==manifest['attack_pins_ref'] and pins['worker_profile_refs']==scope['worker_profile_refs'])
    profile=build_verification_profile(originals.read,manifest['validation_profile_ref'],**installed_paths)
    _need(authority.validation_profile==profile)
    attack_pins=originals.get(manifest['attack_pins_ref'])
    observer=FiniteCaseObserver(originals.read,originals.kind,attack_pins=attack_pins,public_key=public,key_id=manifest['custodian_key_id'])
    guard=RSIQualification(originals.read,manifest['qualification_ref'],kind_reader=originals.kind,
        scope_observer=current_observer,validation_profile=profile,case_observer=observer,
        public_key=public,key_id=manifest['custodian_key_id'])
    from .session_policy import _contracts
    for pin in scope['worker_profile_refs']:
        worker=validate_profile(originals.get(pin));session=originals.get(worker['session_ref'])
        target=originals.get(session['target_profile_ref']);parent=originals.get(session['parent_declaration_ref'])
        freeze_profile(target,parent,_contracts().validate)
        # require() independently checks current scope, complete receipt,
        # thirteen original cases, signatures and this exact subject/profile.
        expected={'qualification_ref':manifest['qualification_ref'],'scope_ref':manifest['scope_ref']}
        _need(authority.require('session_start',session_ref=worker['session_ref'],worker_profile_ref=pin)==expected)
        _need(guard.require('session_start',session_ref=worker['session_ref'],worker_profile_ref=pin)==expected)
        guard.raw(worker['parent_ref'])
    _need(originals.used==set(originals.rows))
    _need(current_observer(scope)==scope and runtime==_root_bytes(current_observer._capture_file,65536))
    return originals


def _write_new(path,data):
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
    try:
        os.fchown(descriptor,0,13000);os.fchmod(descriptor,0o640)
        with os.fdopen(descriptor,'wb',closefd=False) as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
    finally:os.close(descriptor)


def _sync(path):
    descriptor=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(descriptor)
    finally:os.close(descriptor)


def _publish_verified(manifest,originals):
    """Filesystem mechanics only, called exclusively after full validation."""
    root=_root_empty();created=[];directory=None;committed=False
    claim=root/'.publication-claim'
    try:
        _write_new(claim,b'Root security installation publication in progress\n');created.append(claim)
        directory=root/'originals';directory.mkdir(mode=0o750);os.chown(directory,0,13000);os.chmod(directory,0o750)
        seen=set()
        for key,row in originals.rows.items():
            digest=row['ref']['sha256']
            if digest in seen:continue
            path=directory/(digest+'.bytes');_write_new(path,originals.raw[key]);created.append(path);seen.add(digest)
        index={'schema':'ai4r-original-bytes:1','refs':{row['ref']['id']:row['ref']['sha256'] for row in originals.rows.values()}}
        path=directory/'original-byte-index.json';_write_new(path,encoded(index));created.append(path);_sync(directory)
        runtime=root/'runtime-observation.json';_write_new(runtime,originals.raw[encoded(manifest['runtime_observation_ref'])]);created.append(runtime)
        pending=root/'.installation-pending';_write_new(pending,encoded(manifest));created.append(pending)
        # Any other publisher now sees a nonempty root and refuses it. The
        # installation manifest is the final authoritative visible artifact.
        claim.unlink();created.remove(claim)
        _install_exclusive(pending,root/'installation.json');created.remove(pending);committed=True
        try:_sync(root)
        except OSError:
            return {'status':'OUTCOME_UNKNOWN','qualification_ref':manifest['qualification_ref'],'scope_ref':manifest['scope_ref'],
                    'reason':'Verified manifest became visible but final directory durability is unresolved; replacement is forbidden.'}
        return {'status':'PUBLISHED','qualification_ref':manifest['qualification_ref'],'scope_ref':manifest['scope_ref']}
    finally:
        # Never remove originals beneath a manifest that became visible just
        # before an interrupt or an uncertain filesystem acknowledgement.
        if not committed and not (root/'installation.json').exists():
            for path in reversed(created):path.unlink(missing_ok=True)
            if directory is not None and directory.exists() and not any(directory.iterdir()):directory.rmdir()
            _sync(root)


def publish_security_installation(manifest,*,read,kind_reader,authority,current_observer,installed_paths=None):
    """Publish only at the fixed root after independently current full proof."""
    try:
        _root_empty()
        paths=dict(installed_paths or {})
        _need(not set(paths)-{'package_root','installed_build_path','procedure_path','assertion_path'})
        _need(len(encoded(manifest))<=4*1024*1024)
        originals=_validated(manifest,read=read,kind_reader=kind_reader,authority=authority,
            current_observer=current_observer,installed_paths=paths)
        return _publish_verified(manifest,originals)
    except (ValueError,KeyError,TypeError,OSError,AttributeError,ImportError,RecursionError,ResearchError):
        return {'status':'BLOCKED','reason':'Complete independently current qualification, exact typed originals or empty fixed root unavailable; no live installation was replaced.'}
