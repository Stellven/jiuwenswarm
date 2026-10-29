"""Separate finite custody for validation halts, never operational RSI signing.

The root client publishes a bounded explicit evidence projection and sends only
references. Only UID12002 can open the already-existing private key. No ordinary
session, model, oracle, evaluation, package or promotion operation is exposed.
"""
from __future__ import annotations

import base64
import asyncio
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import stat
from datetime import datetime, timezone

from jiuwenswarm.research.contracts import ResearchError, validate
from jiuwenswarm.research.contracts.rsi_security_cases import CASES, FiniteCaseObserver
from jiuwenswarm.research.private_rpc import PrivateRPCClient, PrivateRPCServer
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research_records.original_bytes import OriginalBytes
from .records import RecordStore, encoded
from .security_campaign import SecurityCampaign, _read_scope, _digest
from .session_policy import validate_private
from .signing import Signer, verify

CONFIG_FILE=Path('/run/ai4r-rsi-validation-custody.json')
PUBLIC_ROOT=Path('/run/ai4r-rsi-validation-evidence')
PRIVATE_ROOT=Path('/var/lib/ai4r-rsi-validation-custody')
KEY_FILE=PRIVATE_ROOT/'signing.key'
SOCKET=Path('/run/ai4r-rsi-validation-custody/sign.sock')
PROTOCOL='ai4r-rsi-validation-halt:1'
CONFIG_SCHEMA='urn:ai4r:private:rsi-validation-custody:1'
EVIDENCE_SCHEMA='urn:ai4r:private:rsi-validation-evidence:1'
MAX_TOTAL=64*1024*1024


def _need(value):
    if not value:raise ValueError('Exact independently observed validation halt authority unavailable')


def _path(path):
    value=Path(path)
    _need(value.is_absolute() and '..' not in value.parts and not any(item.is_symlink() for item in (value,*value.parents)))
    return value


def _root_public():
    path=_path(PUBLIC_ROOT);meta=path.stat()
    _need(stat.S_ISDIR(meta.st_mode) and meta.st_uid==0 and meta.st_gid==13000 and stat.S_IMODE(meta.st_mode)==0o2750)
    return path


def _public_file(path,maximum):
    raw=_raw(path,0,0o640,maximum,allow_empty=True)
    meta=Path(path).stat()
    _need(meta.st_uid==0 and meta.st_gid==13000 and stat.S_ISREG(meta.st_mode)
        and stat.S_IMODE(meta.st_mode)==0o640 and meta.st_nlink==1)
    return raw


def _raw(path,uid,mode,maximum,*,allow_empty=False):
    path=_path(path);descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
    try:
        meta=os.fstat(descriptor)
        _need(stat.S_ISREG(meta.st_mode) and meta.st_uid==uid and stat.S_IMODE(meta.st_mode)==mode
            and meta.st_nlink==1 and (meta.st_size>=0 if allow_empty else meta.st_size>0) and meta.st_size<=maximum)
        with os.fdopen(descriptor,'rb',closefd=False) as stream:data=stream.read(maximum+1)
        _need(len(data)<=maximum);return data
    finally:os.close(descriptor)


def _kind(store,pin):
    try:return store.record_kind(pin)
    except ResearchError as error:
        if error.code!='evidence_unavailable':raise
        metadata=store.artifact_metadata(pin);raw=store.read_blob(pin)
        _need(isinstance(metadata,dict) and hashlib.sha256(raw).hexdigest()==pin['sha256'])
        return 'original-bytes'


def _claim_binding(view,claim_ref,plan_ref,case,binding,obs):
    """Reconcile original root claim identity; this performs no boundary action."""
    claim=view.read_record(claim_ref)
    expected_attack='security-case-'+_digest([plan_ref,case])[:40]
    _need(obs['case_id']==case and obs['session_ref']==binding['session_ref']
        and obs['worker_profile_ref']==binding['worker_profile_ref']
        and claim['plan_ref']==plan_ref and claim['case_id']==case
        and claim['attack_id']==obs['attack_id']==expected_attack
        and claim['session_ref']==binding['session_ref'] and claim['worker_profile_ref']==binding['worker_profile_ref']
        and view.record_kind(claim_ref)=='rsi-security-case-claim')
    if obs.get('execution_ref') is not None:
        execution=view.read_record(obs['execution_ref'])
        _need(execution.get('job_id')==expected_attack and execution.get('invocation_id')==expected_attack)


class _View:
    """Root-published finite typed closure, not a caller-selected read path."""
    def __init__(self,publication,rows):
        self.publication=publication;self.rows={};self.ids={};self.total=0;self.cache={}
        for row in rows:
            key=encoded(row['ref']);_need(key not in self.rows and row['ref']['id'] not in self.ids)
            self.rows[key]=row;self.ids[row['ref']['id']]=row['ref']['sha256']
    def read_blob(self,pin):
        key=encoded(pin);_need(key in self.rows)
        if key not in self.cache:
            _public_file(self.publication.root/'original-byte-index.json',4*1024*1024)
            _public_file(self.publication.root/(pin['sha256']+'.bytes'),4*1024*1024)
            raw=self.publication.read(pin);self.total+=len(raw);_need(self.total<=MAX_TOTAL)
            self.cache[key]=raw
        return self.cache[key]
    def record_kind(self,pin):self.read_blob(pin);return self.rows[encoded(pin)]['kind']
    def read_record(self,pin,contract_id=None):
        value=json.loads(self.read_blob(pin))
        if contract_id is not None:validate(contract_id,value)
        return value
    def iter_records(self,*,kinds=None):
        for row in self.rows.values():
            if kinds is None or row['kind'] in kinds:
                yield {'ref':row['ref'],'kind':row['kind'],'record':self.read_record(row['ref'])}


class ValidationHaltSigner:
    """Root-only client; the private signing key never enters this process."""
    def __init__(self,store,*,plan_ref,scope_ref,attack_pins_ref,public_key,key_id,rpc_session_id,capability):
        _need(hasattr(os,'geteuid') and os.geteuid()==0 and type(store) is SQLiteRunStore
            and isinstance(public_key,bytes) and len(public_key)==32)
        self.store,self.plan_ref,self.scope_ref,self.attack_pins_ref=store,plan_ref,scope_ref,attack_pins_ref
        self.key_id=key_id;self._public=public_key
        self.rpc=PrivateRPCClient(SOCKET,protocol=PROTOCOL,session_id=rpc_session_id,capability=capability,
            peer_uid=12002,socket_mode=0o660)
    def public_bytes(self):return self._public

    def _projection(self,record=None):
        plan=self.store.read_record(self.plan_ref)
        _need(plan['scope_ref']==self.scope_ref)
        scope=_read_scope(self.store,self.scope_ref,plan['case_bindings'])
        rows={};total=0
        def add(pin):
            nonlocal total
            key=encoded(pin)
            if key not in rows:
                raw=self.store.read_blob(pin);total+=len(raw)
                _need(len(raw)<=4*1024*1024 and total<=MAX_TOTAL and len(rows)<1024)
                rows[key]={'ref':dict(pin),'kind':_kind(self.store,pin),'bytes':raw}
            return json.loads(rows[key]['bytes'])
        def raw(pin):
            nonlocal total
            key=encoded(pin)
            if key not in rows:
                value=self.store.read_blob(pin);total+=len(value)
                # add() decodes JSON; raw originals are separately bounded.
                _need(len(value)<=4*1024*1024 and total<=MAX_TOTAL and len(rows)<1024)
                rows[key]={'ref':dict(pin),'kind':_kind(self.store,pin),'bytes':value}
            return rows[key]['bytes']
        add(self.plan_ref);add(self.scope_ref);pins=add(self.attack_pins_ref)
        for name in ('runtime_build_ref','environment_ref','worker_driver_ref','executor_ref','probe_ref'):
            raw(scope[name])
        raw(pins['program_prefix_ref'])
        for pin in pins['attacks'].values():raw(pin)
        for profile_ref in scope['worker_profile_refs']:
            worker=add(profile_ref);session=add(worker['session_ref']);target=add(session['target_profile_ref'])
            add(session['parent_declaration_ref']);raw(target['parent_ref']);add(session['chain_root_ref'])
            raw(session['hash_profile_ref'])
        selected=None;observation_ref=claim_ref=record_ref=None
        if record is not None:
            selected=[case for case,binding in plan['case_bindings'].items() if binding['session_ref']==record.get('session_ref')]
            _need(len(selected)==1);selected=selected[0]
            observations=[entry for entry in self.store.iter_records(kinds={'rsi-security-case-observation'})
                if entry['record'].get('case_id')==selected and entry['record'].get('session_ref')==record['session_ref']]
            _need(len(observations)==1);observation_ref=observations[0]['ref'];obs=add(observation_ref)
            claims=[entry for entry in self.store.iter_records(kinds={'rsi-security-case-claim'})
                if entry['record'].get('plan_ref')==self.plan_ref and entry['record'].get('case_id')==selected
                and entry['record'].get('attack_id')==obs['attack_id']]
            _need(len(claims)==1);claim_ref=claims[0]['ref'];add(claim_ref)
            for name in ('input_ref','before_ref','after_ref','denial_ref','execution_ref','containment_ref','attempt_ref'):
                if obs[name] is not None:add(obs[name])
            for name in ('attack_source_ref','probe_ref','stdout_ref','stderr_ref'):
                if obs[name] is not None:raw(obs[name])
            for state_ref in (obs['before_ref'],obs['after_ref']):
                for canary in add(state_ref)['canaries']:raw(canary['content_ref'])
            inputs=add(obs['input_ref'])
            if selected=='RSIV-4':
                for change in inputs['changes']:raw(change['body_ref'])
            elif selected=='RSIV-6':raw(inputs['prompt_ref']);raw(inputs['response_ref'])
            elif selected=='RSIV-11':raw(inputs['record_ref'])
            sid=add(record['session_ref'])['session_id']
            for entry in self.store.iter_records(kinds={'rsi-attempt','rsi-security-effect-start'}):
                value=entry['record']
                if value.get('session_id')==sid or value.get('session_ref')==record['session_ref']:
                    add(entry['ref'])
                    if entry['kind']=='rsi-attempt':
                        for field in ('child_ref','diff_ref'):
                            if value.get(field) is not None:raw(value[field])
                        for field in ('failure_evidence_refs','visible_evidence_refs','observation_refs'):
                            for pin in value[field]:raw(pin)
            record_ref=self.store.put_blob(encoded(record));add(record_ref)
        _need(len(rows)<=1024 and sum(len(row['bytes']) for row in rows.values())<=MAX_TOTAL)
        closure={'schema':'ai4r-rsi-validation-evidence:1','plan_ref':self.plan_ref,'scope_ref':self.scope_ref,
            'attack_pins_ref':self.attack_pins_ref,'case_id':selected,'record_ref':record_ref,'observation_ref':observation_ref,
            'case_claim_ref':claim_ref,'originals':[{'ref':row['ref'],'kind':row['kind']} for row in rows.values()]}
        validate_private(EVIDENCE_SCHEMA,closure)
        publication=OriginalBytes(_root_public(),writable=True)
        for row in rows.values():publication.put_ref(row['ref'],row['bytes'])
        closure_ref=publication.put(closure)
        return closure_ref,record_ref,observation_ref,claim_ref

    async def authorized(self):
        closure_ref,_,_,_=self._projection()
        result=await self.rpc.call('validation_readiness',{'closure_ref':closure_ref},timeout_s=30)
        expected={'plan_ref':self.plan_ref,'scope_ref':self.scope_ref,'attack_pins_ref':self.attack_pins_ref,
            'custodian_key_id':self.key_id,'public_key_sha256':hashlib.sha256(self._public).hexdigest(),
            'allowed_purpose':'security_validation_halt_only'}
        _need(result==expected);return True

    async def sign(self,record):
        closure_ref,record_ref,observation_ref,claim_ref=self._projection(record)
        result=await self.rpc.call('sign_validation_halt',{'closure_ref':closure_ref,'record_ref':record_ref,
            'observation_ref':observation_ref,'case_claim_ref':claim_ref},timeout_s=30)
        _need(isinstance(result,dict) and set(result)=={'signed_record','signed_ref'})
        signed=result['signed_record'];verify(signed,self._public,self.key_id)
        _need({key:value for key,value in signed.items() if key not in {'signature','signer_key_id'}}==record
            and hashlib.sha256(encoded(signed)).hexdigest()==result['signed_ref']['sha256'])
        return signed


def load_validation_config():
    _need(hasattr(os,'geteuid') and os.geteuid()==12002)
    config=json.loads(_raw(CONFIG_FILE,0,0o640,65536));validate_private(CONFIG_SCHEMA,config)
    return config


class ValidationCustody:
    def __init__(self,config):
        _need(hasattr(os,'geteuid') and os.geteuid()==12002)
        validate_private(CONFIG_SCHEMA,config)
        current=load_validation_config();_need(current==config)
        root=_path(PRIVATE_ROOT);meta=root.stat()
        _need(stat.S_ISDIR(meta.st_mode) and meta.st_uid==12002 and stat.S_IMODE(meta.st_mode)==0o700)
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key=_raw(KEY_FILE,12002,0o600,32);_need(len(key)==32)
        self.signer=Signer(Ed25519PrivateKey.from_private_bytes(key),config['custodian_key_id'])
        expected=base64.b64decode(config['custodian_public_key']+'='*(-len(config['custodian_public_key'])%4),altchars=b'-_',validate=True)
        _need(self.signer.public_bytes()==expected)
        self.config=config;self.records=RecordStore(root)
        self.records.db.execute('CREATE TABLE IF NOT EXISTS validation_halt_signatures(session TEXT PRIMARY KEY,record_ref TEXT NOT NULL,closure_ref TEXT NOT NULL,signed_ref TEXT)')

    def _view(self,closure_ref):
        _need(load_validation_config()==self.config)
        publication=OriginalBytes(_root_public())
        _public_file(publication.root/'original-byte-index.json',4*1024*1024)
        _public_file(publication.root/(closure_ref['sha256']+'.bytes'),4*1024*1024)
        closure=publication.get(closure_ref)
        validate_private(EVIDENCE_SCHEMA,closure)
        _need(all(closure[name]==self.config[name] for name in ('plan_ref','scope_ref','attack_pins_ref')))
        view=_View(publication,closure['originals']);plan=view.read_record(closure['plan_ref'])
        validate_private('urn:ai4r:private:rsi-security-campaign-plan:1',plan)
        _need(plan['scope_ref']==closure['scope_ref'])
        scope=_read_scope(view,closure['scope_ref'],plan['case_bindings'])
        pins=view.read_record(closure['attack_pins_ref'])
        observer=FiniteCaseObserver(view.read_blob,view.record_kind,attack_pins=pins,
            public_key=self.signer.public_bytes(),key_id=self.signer.key_id)
        return closure,view,plan,scope,observer

    def readiness(self,request):
        _need(set(request)=={'closure_ref'})
        closure,_,_,_,_=self._view(request['closure_ref'])
        _need(closure['case_id'] is None and all(closure[name] is None for name in ('record_ref','observation_ref','case_claim_ref')))
        return {name:self.config[name] for name in ('plan_ref','scope_ref','attack_pins_ref','custodian_key_id')}|{
            'public_key_sha256':hashlib.sha256(self.signer.public_bytes()).hexdigest(),'allowed_purpose':'security_validation_halt_only'}

    def sign(self,request):
        _need(set(request)=={'closure_ref','record_ref','observation_ref','case_claim_ref'})
        closure,view,plan,scope,observer=self._view(request['closure_ref'])
        _need(all(closure[name]==request[name] for name in ('record_ref','observation_ref','case_claim_ref')))
        case=closure['case_id'];_need(case in CASES)
        checker=object.__new__(SecurityCampaign);checker.store=view
        obs,records=checker._records(request['observation_ref'])
        binding=plan['case_bindings'][case]
        _claim_binding(view,request['case_claim_ref'],closure['plan_ref'],case,binding,obs)
        observer(case,scope,tuple(records))
        session,attempts,used=checker._population(obs['session_ref'],obs,records,request['case_claim_ref'])
        unsigned=view.read_record(request['record_ref'])
        fields={'schema_version','id','session_ref','outcome','parent','child','child_declaration_ref','attempt_refs','final_attempt_ref',
            'referee_evidence_ref','qualified_by','statistics','attempts_used','queries_used','stop_reason','limitations','recorded_at'}
        _need(set(unsigned)==fields)
        fixed=dict(schema_version='2.0.0',session_ref=obs['session_ref'],outcome='SECURITY_HALTED',parent=session['parent'],
            child=None,child_declaration_ref=None,attempt_refs=attempts,final_attempt_ref=None,referee_evidence_ref=None,
            qualified_by='none',statistics=None,attempts_used=len(attempts),queries_used=used,
            stop_reason='Independently observed prohibited security-validation action',
            limitations=['Finite security-validation halt; grants no qualification, activation or ordinary execution authority.'])
        _need(all(unsigned[name]==value for name,value in fixed.items()))
        _need(unsigned['id']=='security-halt:'+_digest([closure['plan_ref'],case,request['observation_ref'],attempts,used])[:40])
        recorded=datetime.fromisoformat(unsigned['recorded_at'].replace('Z','+00:00'))
        session_key=encoded(unsigned['session_ref']).decode();record_ref=request['record_ref']
        with self.records.lock:
            self.records.db.execute('BEGIN IMMEDIATE')
            try:
                old=self.records.db.execute('SELECT record_ref,closure_ref,signed_ref FROM validation_halt_signatures WHERE session=?',(session_key,)).fetchone()
                if old is not None:
                    _need(json.loads(old[0])==record_ref and json.loads(old[1])==request['closure_ref'])
                    _need(old[2] is not None)
                    pin=json.loads(old[2]);value=self.records.get(pin)
                    verify(value,self.signer.public_bytes(),self.signer.key_id)
                    self.records.db.execute('COMMIT');return {'signed_record':value,'signed_ref':pin}
                _need(recorded.tzinfo is not None and abs((datetime.now(timezone.utc)-recorded).total_seconds())<=300)
                self.records.db.execute('INSERT INTO validation_halt_signatures VALUES(?,?,?,NULL)',
                    (session_key,encoded(record_ref).decode(),encoded(request['closure_ref']).decode()))
                self.records.db.execute('COMMIT')
            except BaseException:self.records.db.execute('ROLLBACK');raise
        signed=self.signer.sign(unsigned);validate('rsi-session-result',signed);verify(signed,self.signer.public_bytes(),self.signer.key_id)
        signed_ref=self.records.put(signed)
        changed=self.records.db.execute('UPDATE validation_halt_signatures SET signed_ref=? WHERE session=? AND signed_ref IS NULL',
            (encoded(signed_ref).decode(),session_key)).rowcount
        _need(changed==1);return {'signed_record':signed,'signed_ref':signed_ref}

    def server(self):
        return PrivateRPCServer(SOCKET,protocol=PROTOCOL,session_id=self.config['rpc_session_id'],capability=self.config['rpc_capability'],
            handlers={'validation_readiness':self.readiness,'sign_validation_halt':self.sign},allowed_uids={0},
            socket_mode=0o660,directory_mode=0o710,group_id=13000)

    def close(self):self.records.close()


async def serve():
    """Fixed-config UID12002 service; independent of normal RSI assembly."""
    service=ValidationCustody(load_validation_config());server=None
    try:
        server=await service.server().start()
        await asyncio.Event().wait()
    finally:
        if server is not None:await server.close()
        service.close()


def service_main():return asyncio.run(serve())
