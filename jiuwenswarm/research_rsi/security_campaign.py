"""Durable bookkeeping for independently observed finite security validation.

No boundary programs, probes, effects, model calls or qualification bypass are
implemented here. A protected Python composition may inject a fixed driver;
missing observations produce partial BLOCKED status. Only the installed neutral
observer can accept original evidence, and that acceptance grants no execution.
"""
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import os
from pathlib import Path
import shlex
import sqlite3
import stat
import sys
import threading
import traceback
from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.contracts import validate, ResearchError
from jiuwenswarm.research.contracts.rsi_security import CASES, RSIQualification
from jiuwenswarm.research.contracts.rsi_security_cases import CASE_TEST_IDS, FiniteCaseObserver
from .records import encoded
from .session_policy import validate_private
from .signing import verify
from .worker import validate_profile, ref

PLAN_SCHEMA = 'urn:ai4r:private:rsi-security-campaign-plan:1'


def _utc():
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def _protected_store(store):
    if sys.platform != 'linux' or os.geteuid() not in (0, 12002) or type(store) is not SQLiteRunStore:
        raise ValueError('Protected Linux security capture store required')
    path = store.root
    if not path.is_absolute() or any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('Original security capture root required')
    meta = path.stat()
    if meta.st_uid != os.geteuid() or not stat.S_ISDIR(meta.st_mode) or stat.S_IMODE(meta.st_mode) != 0o700:
        raise ValueError('Private owner-controlled security capture root required')


def _read_scope(store, scope_ref, bindings):
    scope = json.loads(store.read_blob(scope_ref))
    fields = {'schema','id','runtime_build_ref','environment_ref','worker_driver_ref','executor_ref','probe_ref',
              'kernel_release','platform','worker_profile_refs'}
    if (set(scope) != fields or scope['schema'] != 'ai4r-rsi-security-scope:1' or set(bindings) != set(CASES)
            or not scope['kernel_release'] or not scope['platform'] or not scope['id']):
        raise ValueError('Exact independently approved thirteen-case scope required')
    for name in ('runtime_build_ref','environment_ref','worker_driver_ref','executor_ref','probe_ref'):
        store.read_blob(scope[name])
    sessions = set(); profiles = set(); session_ids=set(); tested_profiles=[]
    for case in CASES:
        row = bindings[case]
        if not isinstance(row, dict) or set(row) != {'session_ref','worker_profile_ref'}:
            raise ValueError('Closed original security case binding required')
        for pin in row.values(): ref(pin)
        session = store.read_record(row['session_ref'], contract_id='rsi-session')
        profile = validate_profile(json.loads(store.read_blob(row['worker_profile_ref'])))
        target = store.read_record(session['target_profile_ref'], contract_id='rsi-target-profile')
        parent=store.read_record(session['parent_declaration_ref'],contract_id='capsule-declaration')
        genesis = json.loads(store.read_blob(session['chain_root_ref']))
        if (profile['schema'] != 'ai4r-rsi-worker-profile:3' or profile.get('process_policy') != 'single_process_seccomp_v1'
                or profile['session_ref'] != row['session_ref'] or profile['target_ref'] != session['target_profile_ref']
                or profile['parent_ref'] != target['parent_ref'] or target['parent_declaration_ref'] != session['parent_declaration_ref']
                or session['parent']!={'cc_name':parent['identity']['name'],'cc_version':parent['identity']['version_label'],
                                      'declaration_sha256':session['parent_declaration_ref']['sha256']}
                or any(target[name] != session[name] for name in ('configuration_ref','improver_ref','scoring_adapter_ref'))
                or any(genesis.get(name) != value for name,value in dict(session_id=session['session_id'],
                    target_ref=session['target_profile_ref'],hash_profile_ref=session['hash_profile_ref'],interface_revision='M1-IF-009@r2').items())):
            raise ValueError('Security session/profile does not match its original frozen scope')
        session_key = encoded(row['session_ref']); profile_key = encoded(row['worker_profile_ref'])
        if session_key in sessions or profile_key in profiles or session['session_id'] in session_ids:
            raise ValueError('Every security case requires its distinct original session/profile')
        sessions.add(session_key); profiles.add(profile_key);session_ids.add(session['session_id'])
        tested_profiles.append(profile)
    scope_profiles={encoded(pin) for pin in scope['worker_profile_refs']}
    if not profiles <= scope_profiles or len(scope_profiles)!=len(scope['worker_profile_refs']):
        raise ValueError('Security scope omits selected profiles or repeats an original identity')
    configuration_fields=('environment_ref','hardware_ref','process_policy','memory_mb','pids_max','timeout_s')
    expected={name:tested_profiles[0][name] for name in configuration_fields}
    for pin in scope['worker_profile_refs']:
        current=validate_profile(json.loads(store.read_blob(pin)))
        session=store.read_record(current['session_ref'],contract_id='rsi-session')
        target=store.read_record(session['target_profile_ref'],contract_id='rsi-target-profile')
        parent=store.read_record(session['parent_declaration_ref'],contract_id='capsule-declaration')
        genesis=json.loads(store.read_blob(session['chain_root_ref']))
        if (current['schema']!='ai4r-rsi-worker-profile:3'
                or any(current[name]!=value for name,value in expected.items())
                or current['target_ref']!=session['target_profile_ref'] or current['parent_ref']!=target['parent_ref']
                or target['parent_declaration_ref']!=session['parent_declaration_ref']
                or session['parent']!={'cc_name':parent['identity']['name'],'cc_version':parent['identity']['version_label'],
                    'declaration_sha256':session['parent_declaration_ref']['sha256']}
                or any(target[name]!=session[name] for name in ('configuration_ref','improver_ref','scoring_adapter_ref'))
                or current['memory_mb']>target['limits']['memory_mb']
                or current['timeout_s']>min(target['limits']['time_s'],session['limits']['per_call_s'])
                or any(genesis.get(name)!=value for name,value in dict(session_id=session['session_id'],target_ref=session['target_profile_ref'],
                    hash_profile_ref=session['hash_profile_ref'],interface_revision='M1-IF-009@r2').items())):
            raise ValueError('Additional scope profile has untested policy, resources or frozen context')
    return scope


def prepare_security_campaign_plan(store, *, scope_ref, case_bindings, observer_ref, driver_ref=None,
                                    verification_profile_ref=None, procedure_ref=None, assertion_manifest_ref=None):
    """Freeze references only; ``verification_profile_ref`` names source pins.

    It never names a caller-computed profile result. The fixed installed owner
    recomputes that result at completion. No driver or boundary is invoked here.
    """
    _protected_store(store)
    _read_scope(store, scope_ref, case_bindings)
    store.read_blob(observer_ref)
    for pin in (driver_ref, verification_profile_ref, procedure_ref, assertion_manifest_ref):
        if pin is not None: store.read_blob(pin)
    value = dict(schema='ai4r-rsi-security-campaign-plan:1', scope_ref=scope_ref, case_bindings=case_bindings,
                 observer_ref=observer_ref, driver_ref=driver_ref, verification_profile_ref=verification_profile_ref,
                 procedure_ref=procedure_ref, assertion_manifest_ref=assertion_manifest_ref)
    value['id'] = 'security-campaign-plan:' + _digest(value)
    validate_private(PLAN_SCHEMA, value)
    return store.append_record('rsi-security-campaign-plan', value)


class CampaignOutcomeUnknown(ValueError):
    pass


class CampaignLedger:
    """Once-only whole-campaign and per-case claims in protected SQLite."""
    def __init__(self, store):
        _protected_store(store)
        self.store = store; self.lock = threading.RLock()
        path = store.root/'security-campaign.sqlite'
        self.db = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
        os.chmod(path,0o600)
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('''
CREATE TABLE IF NOT EXISTS security_campaigns(lineage TEXT PRIMARY KEY,plan_ref TEXT NOT NULL,start_ref TEXT NOT NULL,result_ref TEXT);
CREATE TABLE IF NOT EXISTS security_cases(lineage TEXT,case_id TEXT,claim_ref TEXT NOT NULL,status TEXT NOT NULL,
 observation_ref TEXT,halt_ref TEXT,evidence_refs TEXT,proof_ref TEXT,PRIMARY KEY(lineage,case_id));
''')

    def lookup(self, lineage, plan_ref):
        row = self.db.execute('SELECT plan_ref,start_ref,result_ref FROM security_campaigns WHERE lineage=?',(lineage,)).fetchone()
        if row is None: return None
        if json.loads(row[0]) != plan_ref:
            raise CampaignOutcomeUnknown('Changed security plan cannot reset original test-session claims')
        return {'start_ref':json.loads(row[1]),'result_ref':json.loads(row[2]) if row[2] else None}

    def claim(self, lineage, plan_ref, start_ref):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                old = self.lookup(lineage,plan_ref)
                if old is None:self.db.execute('INSERT INTO security_campaigns VALUES(?,?,?,NULL)',
                    (lineage,encoded(plan_ref).decode(),encoded(start_ref).decode()))
                self.db.execute('COMMIT');return old is None
            except BaseException:self.db.execute('ROLLBACK');raise

    def claim_case(self, lineage, case, claim_ref):
        if case not in CASES: raise ValueError('Unknown finite security case')
        with self.lock:
            try:self.db.execute('INSERT INTO security_cases(lineage,case_id,claim_ref,status) VALUES(?,?,?,?)',
                (lineage,case,encoded(claim_ref).decode(),'OUTCOME_UNKNOWN'))
            except sqlite3.IntegrityError:raise CampaignOutcomeUnknown('Security case already started; replay forbidden') from None

    def complete_case(self,lineage,case,*,status,observation_ref=None,halt_ref=None,evidence_refs=(),proof_ref=None):
        changed=self.db.execute('UPDATE security_cases SET status=?,observation_ref=?,halt_ref=?,evidence_refs=?,proof_ref=? '
            'WHERE lineage=? AND case_id=? AND evidence_refs IS NULL',
            (status,encoded(observation_ref).decode() if observation_ref else None,encoded(halt_ref).decode() if halt_ref else None,
             encoded(list(evidence_refs)).decode(),encoded(proof_ref).decode() if proof_ref else None,lineage,case)).rowcount
        if changed!=1:raise CampaignOutcomeUnknown('Original security case outcome is immutable')

    def cases(self,lineage):
        rows=self.db.execute('SELECT case_id,claim_ref,status,observation_ref,halt_ref,evidence_refs,proof_ref '
                             'FROM security_cases WHERE lineage=? ORDER BY case_id',(lineage,)).fetchall()
        return {row[0]:dict(claim_ref=json.loads(row[1]),status=row[2],observation_ref=json.loads(row[3]) if row[3] else None,
            halt_ref=json.loads(row[4]) if row[4] else None,evidence_refs=json.loads(row[5]) if row[5] else [],
            proof_ref=json.loads(row[6]) if row[6] else None) for row in rows}

    def finish(self,lineage,plan_ref,result_ref):
        self.lookup(lineage,plan_ref)
        changed=self.db.execute('UPDATE security_campaigns SET result_ref=? WHERE lineage=? AND result_ref IS NULL',
            (encoded(result_ref).decode(),lineage)).rowcount
        if changed!=1:raise CampaignOutcomeUnknown('Original security campaign outcome is immutable')

    def close(self):self.db.close()


class SecurityCampaign:
    """Finite bookkeeping over externally supplied independently validated facts."""
    def __init__(self,store,*,ledger,signer,observer=None,driver=None,approved_plan_refs,
                 runtime_observer=None,installed_paths=None,public_key=None,key_id=None):
        _protected_store(store)
        if type(ledger) is not CampaignLedger or ledger.store is not store or not callable(getattr(signer,'sign',None)):
            raise ValueError('Original protected campaign ledger and existing signer required')
        public_key=public_key if public_key is not None else signer.public_bytes()
        key_id=key_id if key_id is not None else signer.key_id
        if not isinstance(public_key,bytes) or len(public_key)!=32 or not isinstance(key_id,str) or not key_id:
            raise ValueError('Separately pinned custodian public signing identity required')
        if observer is not None and (type(observer) is not FiniteCaseObserver or observer.read!=store.read_blob
                or observer.kind_reader!=store.record_kind or observer.public_key!=public_key or observer.key_id!=key_id):
            raise ValueError('Installed independent observer over this original store required')
        self.store,self.ledger,self.signer,self.observer,self.driver=store,ledger,signer,observer,driver
        self.approved=frozenset(encoded(pin) for pin in approved_plan_refs);self.lock=asyncio.Lock()
        self.runtime_observer=runtime_observer;self.installed_paths=dict(installed_paths or {})
        self.public_key,self.key_id=public_key,key_id
        if set(self.installed_paths)-{'package_root','installed_build_path','procedure_path','assertion_path'}:
            raise ValueError('Only finite root-installed verification paths are supported')

    def _records(self,observation_ref):
        obs=self.store.read_record(observation_ref)
        if self.store.record_kind(observation_ref)!='rsi-security-case-observation':
            raise ValueError('Original typed security observation required')
        refs=[observation_ref]+[obs[name] for name in ('input_ref','before_ref','after_ref','denial_ref','execution_ref','containment_ref','attempt_ref') if obs.get(name) is not None]
        records=[];seen=set()
        for pin in refs:
            key=encoded(pin)
            if key in seen:continue
            seen.add(key);records.append((pin,self.store.record_kind(pin),self.store.read_record(pin)))
        for entry in self.store.iter_records(kinds={'rsi-security-effect-start'}):
            value=entry['record']
            if value.get('session_ref')==obs.get('session_ref') or value.get('attack_id')==obs.get('attack_id'):
                if encoded(entry['ref']) not in seen:
                    seen.add(encoded(entry['ref']));records.append((entry['ref'],entry['kind'],value))
        return obs,records

    def _started_accounting(self,binding,claim_ref,attempts):
        """Retain actual starts without inventing a completed canonical attempt."""
        counts={'canonical_attempts':len(attempts),'started_attempts':0,'pending_started_attempts':0,
                'attempts_used':len(attempts),'accounting_status':'CANONICAL'}
        claim=self.store.read_record(claim_ref) if claim_ref is not None else None
        related=[]
        for entry in self.store.iter_records(kinds={'rsi-security-effect-start'}):
            value=entry['record']
            if (value.get('session_ref')==binding['session_ref']
                    or claim_ref is not None and value.get('case_claim_ref')==claim_ref
                    or claim is not None and value.get('attack_id')==claim.get('attack_id')):
                related.append(entry)
        if not related:return counts
        def unknown():
            return dict(counts,started_attempts=None,pending_started_attempts=None,attempts_used=None,
                        accounting_status='UNAVAILABLE')
        if len(related)!=1 or claim is None:return unknown()
        entry=related[0];start=entry['record']
        try:
            validate_private('urn:ai4r:private:rsi-security-effect-start:1',start)
            if (self.store.record_kind(claim_ref)!='rsi-security-case-claim'
                    or start['case_claim_ref']!=claim_ref or start['session_ref']!=binding['session_ref']
                    or start['worker_profile_ref']!=binding['worker_profile_ref']
                    or claim['session_ref']!=binding['session_ref'] or claim['worker_profile_ref']!=binding['worker_profile_ref']
                    or start['attack_id']!=claim['attack_id']):return unknown()
            self.store.read_blob(start['attack_source_ref'])
            timestamp=datetime.fromisoformat(start['recorded_at'].replace('Z','+00:00'))
            if timestamp.tzinfo is None:return unknown()
            session=self.store.read_record(binding['session_ref'],contract_id='rsi-session')
            for attempt in attempts:
                value=attempt['record'];validate('rsi-attempt',value)
                if (value.get('schema_version')!='2.0.0' or value['session_id']!=session['session_id']
                        or value['target_ref']!=session['target_profile_ref']
                        or any(value[name]!=session[name] for name in ('configuration_ref','hash_profile_ref','chain_root_ref'))):
                    return unknown()
        except (ValueError,KeyError,TypeError,OSError,ResearchError):return unknown()
        linked=[];ambiguous=False
        for attempt in attempts:
            value=attempt['record']
            evidence=value.get('observation_refs',[])+value.get('visible_evidence_refs',[])+value.get('failure_evidence_refs',[])
            if entry['ref'] in evidence:
                if value.get('child_ref')!=start['attack_source_ref']:return unknown()
                linked.append(attempt)
            elif value.get('child_ref')==start['attack_source_ref']:
                ambiguous=True
        if ambiguous or len(linked)>1:return unknown()
        counts['started_attempts']=1
        if not linked:
            counts.update(pending_started_attempts=1,attempts_used=len(attempts)+1,accounting_status='PENDING_STARTED_ATTEMPTS')
        return counts

    def _population(self,session_ref,obs,records,case_claim_ref=None):
        session=self.store.read_record(session_ref,contract_id='rsi-session')
        target=self.store.read_record(session['target_profile_ref'],contract_id='rsi-target-profile')
        attempts=[entry for entry in self.store.iter_records(kinds={'rsi-attempt'}) if entry['record'].get('session_id')==session['session_id']]
        attempts.sort(key=lambda entry:entry['record']['sequence'])
        after=self.store.read_record(obs['after_ref']);state=after['ledger']
        used=state['used'] if state is not None else 0
        if type(used) is not int or not 0<=used<=session['limits']['session_query_limit'] or len(attempts)>session['limits']['max_attempts']:
            raise ValueError('Actual protected security accounting is unavailable')
        previous=None;last_queries=0
        for sequence,entry in enumerate(attempts,1):
            value=entry['record'];validate('rsi-attempt',value)
            if (value['schema_version']!='2.0.0' or value['sequence']!=sequence or value['previous_ref']!=previous
                    or value['target_ref']!=session['target_profile_ref'] or value['parent_ref']!=target['parent_ref']
                    or any(value[name]!=session[name] for name in ('configuration_ref','hash_profile_ref','chain_root_ref'))
                    or not last_queries<=value['queries_used']<=used):
                raise ValueError('Original security attempt chain or accounting differs')
            previous=entry['ref'];last_queries=value['queries_used']
        accounting=self._started_accounting({'session_ref':session_ref,'worker_profile_ref':obs.get('worker_profile_ref')},
                                           case_claim_ref,attempts)
        if accounting['accounting_status']!='CANONICAL':
            raise CampaignOutcomeUnknown('Started security action lacks an attributable completed attempt; reconciliation required')
        if any(kind=='execution-receipt' for _,kind,_ in records) and accounting['started_attempts']!=1:
            raise CampaignOutcomeUnknown('Observed execution lacks its exact durable pre-effect start')
        if obs['attempt_ref'] is None:
            if attempts or any(kind in {'execution-receipt','model-call-start','rsi-proposer-start'} for _,kind,_ in records):
                raise ValueError('Pre-effect refusal cannot erase started attempts or effects')
        elif not any(entry['ref']==obs['attempt_ref'] and entry['record']['violations'] for entry in attempts):
            raise ValueError('Observed violation lacks its original attempted boundary action')
        refs=[entry['ref'] for entry in attempts]
        return session,refs,used

    async def _halt(self,plan_ref,case,observation_ref,obs,records,proof,case_claim_ref=None):
        session,attempts,used=self._population(obs['session_ref'],obs,records,case_claim_ref)
        identifier='security-halt:'+_digest([plan_ref,case,observation_ref,attempts,used])[:40]
        value=dict(schema_version='2.0.0',id=identifier,session_ref=obs['session_ref'],outcome='SECURITY_HALTED',
            parent=session['parent'],child=None,child_declaration_ref=None,attempt_refs=attempts,
            final_attempt_ref=None,referee_evidence_ref=None,qualified_by='none',statistics=None,
            attempts_used=len(attempts),queries_used=used,stop_reason='Independently observed prohibited security-validation action',
            limitations=['Finite security-validation halt; grants no qualification, activation or ordinary execution authority.'],recorded_at=_utc())
        original=encoded(value)
        signed=self.signer.sign(json.loads(original))
        if inspect.isawaitable(signed):signed=await signed
        validate('rsi-session-result',signed);verify(signed,self.public_key,self.key_id)
        if encoded({name:item for name,item in signed.items() if name not in {'signature','signer_key_id'}})!=original:
            raise ValueError('Custodian signer changed original security halt facts')
        return self.store.put_record('rsi-session-result',signed,record_id=identifier)

    async def run(self,plan_ref):
        async with self.lock:return await self._run(plan_ref)

    async def _run(self,plan_ref):
        _protected_store(self.store)
        if encoded(plan_ref) not in self.approved:raise ValueError('Root-approved security campaign plan required')
        plan=self.store.read_record(plan_ref);validate_private(PLAN_SCHEMA,plan)
        if self.store.record_kind(plan_ref)!='rsi-security-campaign-plan':raise ValueError('Original typed campaign plan required')
        scope=_read_scope(self.store,plan['scope_ref'],plan['case_bindings'])
        lineage=_digest(plan['case_bindings'])
        prior=self.ledger.lookup(lineage,plan_ref)
        if prior is not None:
            if prior['result_ref'] is not None:return prior['result_ref']
            raise CampaignOutcomeUnknown('Campaign has an unmatched durable start; automatic replay forbidden')
        started=_utc()
        start_ref=self.store.append_record('rsi-security-campaign-start',dict(schema='ai4r-rsi-security-campaign-start:1',
            plan_ref=plan_ref,scope_ref=plan['scope_ref'],started_at=started))
        if not self.ledger.claim(lineage,plan_ref,start_ref):raise CampaignOutcomeUnknown('Campaign was claimed concurrently')
        usable=(self.observer is not None and self.driver is not None and callable(getattr(self.driver,'observe',None))
            and getattr(self.driver,'plan_ref',None)==plan_ref and getattr(self.driver,'scope_ref',None)==plan['scope_ref']
            and getattr(self.driver,'descriptor_ref',None)==plan['driver_ref'] and plan['driver_ref'] is not None)
        if usable:
            for case in CASES:
                binding=plan['case_bindings'][case]
                claim=dict(schema='ai4r-rsi-security-case-claim:1',plan_ref=plan_ref,case_id=case,**binding,
                    attack_id='security-case-'+_digest([plan_ref,case])[:40],started_at=_utc())
                claim_ref=self.store.append_record('rsi-security-case-claim',claim)
                self.ledger.claim_case(lineage,case,claim_ref)
                observation_ref=None;records=[];failure_phase='driver_observation'
                try:
                    observation_ref=self.driver.observe(case,case_claim_ref=dict(claim_ref),
                        session_ref=dict(binding['session_ref']),worker_profile_ref=dict(binding['worker_profile_ref']))
                    if inspect.isawaitable(observation_ref):observation_ref=await observation_ref
                    if observation_ref is None:
                        self.ledger.complete_case(lineage,case,status='BLOCKED');continue
                    failure_phase='original_evidence_join'
                    ref(observation_ref)
                    obs,records=self._records(observation_ref)
                    if (obs.get('case_id')!=case or obs.get('session_ref')!=binding['session_ref']
                            or obs.get('worker_profile_ref')!=binding['worker_profile_ref'] or obs.get('attack_id')!=claim['attack_id']):
                        raise ValueError('Original observation differs from its root-approved case claim')
                    if obs.get('execution_ref') is not None:
                        execution=self.store.read_record(obs['execution_ref'])
                        if execution.get('job_id')!=claim['attack_id'] or execution.get('invocation_id')!=claim['attack_id']:
                            raise ValueError('Started observation is not joined to its durable case claim')
                    failure_phase='independent_observer'
                    proof=self.observer(case,scope,tuple(records))
                    fields={'case_id','session_ref','worker_profile_ref','attack_id','denial_refs','attempt_ref'}
                    if (not isinstance(proof,dict) or set(proof)!=fields or proof['case_id']!=case
                            or any(proof[name]!=obs[name] for name in ('session_ref','worker_profile_ref','attack_id','attempt_ref'))):
                        raise ValueError('Independent observer returned no exact original evidence join')
                    failure_phase='signed_halt'
                    halt_ref=await self._halt(plan_ref,case,observation_ref,obs,records,proof,claim_ref)
                    evidence=[pin for pin,_,_ in records]+[halt_ref]
                    for entry in self.store.iter_records(kinds={'rsi-attempt'}):
                        if entry['record'].get('session_id')==self.store.read_record(binding['session_ref'])['session_id'] and entry['ref'] not in evidence:evidence.append(entry['ref'])
                    failure_phase='proof_recording'
                    proof_ref=self.store.append_record('rsi-security-case-proof',dict(schema='ai4r-rsi-security-case-proof:1',
                        observation_ref=observation_ref,halt_ref=halt_ref,proof=proof))
                    failure_phase='case_finalization'
                    self.ledger.complete_case(lineage,case,status='OBSERVED',observation_ref=observation_ref,
                        halt_ref=halt_ref,evidence_refs=evidence,proof_ref=proof_ref)
                except BaseException as error:
                    retained=[pin for pin,_,_ in records]
                    try:ref(observation_ref)
                    except (ValueError,TypeError):observation_ref=None
                    # Private original diagnostics preserve the actual failure;
                    # they grant no observation, reconciliation or replay. Never
                    # capture stack locals or publish this through UI progress.
                    trace=''.join(traceback.TracebackException.from_exception(error,capture_locals=False).format())
                    raw=trace.encode('utf8',errors='backslashreplace')
                    limit=16*1024
                    diagnostic=self.store.append_record('rsi-security-case-failure',dict(
                        schema='ai4r-rsi-security-case-failure:1',plan_ref=plan_ref,case_claim_ref=claim_ref,
                        case_id=case,phase=failure_phase,observation_ref=observation_ref,
                        exception_module=type(error).__module__,exception_type=type(error).__qualname__,
                        traceback=raw[:limit].decode('utf8',errors='ignore'),traceback_truncated=len(raw)>limit,
                        recorded_at=_utc()))
                    retained.append(diagnostic)
                    self.ledger.complete_case(lineage,case,status='OUTCOME_UNKNOWN',
                        observation_ref=observation_ref,evidence_refs=retained)
                    if isinstance(error,(asyncio.CancelledError,KeyboardInterrupt,SystemExit)):raise
                    break
        cases=self.ledger.cases(lineage)
        counts={}
        for case in CASES:
            session=self.store.read_record(plan['case_bindings'][case]['session_ref'])
            attempts=[entry for entry in self.store.iter_records(kinds={'rsi-attempt'}) if entry['record'].get('session_id')==session['session_id']]
            row=cases.get(case,{})
            halt=self.store.read_record(row['halt_ref']) if row.get('halt_ref') else None
            accounting=self._started_accounting(plan['case_bindings'][case],row.get('claim_ref'),attempts)
            counts[case]={**accounting,'queries_used':halt['queries_used'] if halt else None}
        complete=len(cases)==13 and all(row['status']=='OBSERVED' for row in cases.values())
        verification=None
        completion_blockers=[]
        if not usable:completion_blockers.append('FIXED_DRIVER_OR_INDEPENDENT_OBSERVER_UNAVAILABLE')
        if complete:
            try:
                guard=RSIQualification(self.store.read_blob,None,kind_reader=self.store.record_kind,
                    case_observer=self.observer,public_key=self.public_key,key_id=self.key_id)
                guard._cases({'case_evidence_refs':{case:cases[case]['evidence_refs'] for case in CASES}},scope)
                verification=self._verification(plan,scope,cases,started)
            except (ImportError,ValueError,KeyError,TypeError,OSError,ResearchError):
                complete=False;completion_blockers.append('CURRENT_VERIFICATION_OWNER_OR_METADATA_UNAVAILABLE')
        result=self.store.append_record('rsi-security-campaign-status',dict(schema='ai4r-rsi-security-campaign-status:1',
            plan_ref=plan_ref,scope_ref=plan['scope_ref'],status='COMPLETE_OBSERVED' if complete else 'BLOCKED',
            cases=cases,actual_counts=counts,missing_cases=[case for case in CASES if case not in cases or cases[case]['status']!='OBSERVED'],
            completion_blockers=completion_blockers,verification=verification,started_at=started,ended_at=_utc(),
            limitations=['Observations and signed halts confer no operational qualification; protected independent installation remains required.']))
        self.ledger.finish(lineage,plan_ref,result)
        return result

    def _verification(self,plan,scope,cases,started):
        required=('verification_profile_ref','procedure_ref','assertion_manifest_ref')
        if any(plan[name] is None for name in required):raise ValueError('Independent current verification metadata unavailable')
        # Completion must use fixed current-source owners, never a supplied
        # profile dictionary or a driver's claimed result. An uncomposed owner
        # leaves original observations/halts available as partial evidence.
        from .security_scope import RuntimeScopeObserver
        from .security_profile import build_verification_profile
        if type(self.runtime_observer) is not RuntimeScopeObserver or self.runtime_observer(scope)!=scope:
            raise ValueError('Actual installed runtime scope observer unavailable')
        profile=build_verification_profile(self.store.read_blob,plan['verification_profile_ref'],**self.installed_paths)
        fields={'candidate_id','procedure_sha256','source_baseline_sha256','native_pins','interface_revisions','profile_pins',
                'assertion_manifest_sha256','required_case_ids'}
        if set(profile)!=fields or profile['required_case_ids']!=CASE_TEST_IDS:raise ValueError('Current finite verification identity required')
        procedure=self.store.read_blob(plan['procedure_ref']);assertions=self.store.read_blob(plan['assertion_manifest_ref'])
        manifest=json.loads(assertions)
        if (hashlib.sha256(procedure).hexdigest()!=profile['procedure_sha256']
                or hashlib.sha256(assertions).hexdigest()!=profile['assertion_manifest_sha256']
                or manifest.get('required_assertion_ids')!=list(CASES) or manifest.get('required_case_ids')!=list(CASE_TEST_IDS.values())):
            raise ValueError('Original independent procedure/assertions differ')
        suite=ET.Element('testsuite',name='ai4r.rsi.security',tests='13',failures='0',errors='0',skipped='0')
        for case in CASES:
            classname,name=CASE_TEST_IDS[case].split('::',1);ET.SubElement(suite,'testcase',classname=classname,name=name)
        artifacts=[]
        def add(path,kind,data):
            pin=self.store.put_blob(data,media_type='application/octet-stream')
            artifacts.append({'path':path,'kind':kind,'ref':pin,'sha256':pin['sha256']})
        add('junit.xml','junit',ET.tostring(suite,encoding='utf-8',xml_declaration=True))
        add('raw.json','raw',encoded({case:cases[case] for case in CASES}))
        add('stdout.log','stdout',''.join('independently observed '+case+'\n' for case in CASES).encode())
        add('stderr.log','stderr',b'')
        add('procedure.json','procedure',procedure);add('assertions.json','assertion_manifest',assertions)
        environment=json.loads(self.store.read_blob(scope['environment_ref']))
        receipt={key:profile[key] for key in fields-{'assertion_manifest_sha256','required_case_ids'}}
        receipt.update(schema='m1-verification-result:1',check_id='M1-008/V15',outcome='PASS',dependency_mode='real_boundary',
            command=shlex.join(sys.argv),cwd=os.getcwd(),started_at=started,ended_at=_utc(),environment=environment,
            assertions={'required_ids':list(CASES),'passed_ids':list(CASES),'expected':13,'observed':13},
            fixture_pins={manifest['id']:profile['assertion_manifest_sha256']},
            artifacts=[{key:row[key] for key in ('path','kind','sha256')} for row in artifacts])
        pin=self.store.append_record('m1-verification-result',receipt)
        return {'verification_receipt_ref':pin,'artifact_refs':[{'path':row['path'],'ref':row['ref']} for row in artifacts],
                'case_evidence_refs':{case:cases[case]['evidence_refs'] for case in CASES}}
