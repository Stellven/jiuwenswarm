"""Independent IF015 verifier. No side-system implementation is imported."""
from __future__ import annotations
import hashlib
import json
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import copy

CASES=tuple('RSIV-'+str(i) for i in range(1,14))
OPERATIONS=frozenset({'session_start','proposal','trial','oracle','package','admit','activate'})


def _need(value,message):
    if not value:raise ValueError('RSI security qualification: '+message)


def _ref(value):
    _need(isinstance(value,dict) and set(value)=={'id','sha256'} and isinstance(value['id'],str) and value['id']
          and isinstance(value['sha256'],str) and re.fullmatch('[0-9a-f]{64}',value['sha256']), 'exact original Ref required')
    return value


def _json(raw):
    def pairs(values):
        result={}
        for k,v in values:
            _need(k not in result,'duplicate JSON identity');result[k]=v
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,
                      parse_constant=lambda value:(_ for _ in ()).throw(ValueError('nonfinite qualification')))


class RSIQualification:
    def __init__(self,read,qualification_ref,*,kind_reader=None,scope_observer=None,
                 validation_profile=None,case_observer=None,public_key=None,key_id=None):
        self.read,self.ref,self.kind_reader,self.scope_observer=read,qualification_ref,kind_reader,scope_observer
        # Only installed finite owners may inject these handles. They are not
        # decoded from a qualification, candidate, request or operator YAML.
        # The full thirteen-case producer/observer has not been constructed;
        # production bootstrap intentionally supplies None and stays blocked.
        self.validation_profile=copy.deepcopy(validation_profile)
        self.case_observer,self.public_key,self.key_id=case_observer,public_key,key_id

    @classmethod
    def from_store(cls,store,qualification_ref,*,scope_observer=None,validation_profile=None,case_observer=None,public_key=None,key_id=None):
        # Only protected bootstrap supplies this Ref. It is never read from a
        # client request, candidate package or sidecar operation.
        return cls(store.read_blob,qualification_ref,kind_reader=store.record_kind,scope_observer=scope_observer,
                   validation_profile=validation_profile,case_observer=case_observer,public_key=public_key,key_id=key_id)

    def raw(self,ref):
        _ref(ref);raw=self.read(ref)
        _need(isinstance(raw,bytes) and 0<len(raw)<=16*1024*1024,'bounded original bytes required')
        _need(hashlib.sha256(raw).hexdigest()==ref['sha256'],'original bytes changed')
        return raw

    def get(self,ref):return _json(self.raw(ref))

    def _scope(self,qualification):
        scope=self.get(qualification['scope_ref'])
        fields={'schema','id','runtime_build_ref','environment_ref','worker_driver_ref','executor_ref','probe_ref','kernel_release','platform','worker_profile_refs'}
        _need(isinstance(scope,dict) and set(scope)==fields and scope['schema']=='ai4r-rsi-security-scope:1','closed scope required')
        _need(scope['id'] and scope['kernel_release'] and scope['platform'],'observed runtime identity missing')
        for key in ('runtime_build_ref','environment_ref','worker_driver_ref','executor_ref','probe_ref'):self.raw(scope[key])
        profiles=scope['worker_profile_refs']
        _need(isinstance(profiles,list) and profiles and len({json.dumps(_ref(p),sort_keys=True) for p in profiles})==len(profiles),'exact unique profiles required')
        _need(callable(self.scope_observer) and self.scope_observer(scope)==scope,'actual approved producer scope unavailable or stale')
        return scope

    def _receipt(self,qualification,scope):
        expected=self.validation_profile
        fields={'candidate_id','procedure_sha256','source_baseline_sha256','native_pins','interface_revisions',
                'profile_pins','assertion_manifest_sha256','required_case_ids'}
        _need(isinstance(expected,dict) and set(expected)==fields,'independently current verification profile unavailable')
        _need(all(expected.get(k) for k in fields),'independently current verification profile incomplete')
        _need(isinstance(expected['required_case_ids'],dict) and set(expected['required_case_ids'])==set(CASES)
              and len(set(expected['required_case_ids'].values()))==13,'current independent case inventory missing')
        receipt=self.get(qualification['verification_receipt_ref'])
        for key in fields-{'assertion_manifest_sha256','required_case_ids'}:
            _need(receipt.get(key)==expected[key],'stale or missing current '+key)
        _need(receipt.get('schema')=='m1-verification-result:1' and receipt.get('check_id')=='M1-008/V15'
              and receipt.get('outcome')=='PASS' and receipt.get('dependency_mode')=='real_boundary','complete real V15 receipt required')
        _need(receipt.get('command') and receipt.get('cwd') and receipt.get('started_at') and receipt.get('ended_at'),'actual command/time missing')
        start=datetime.fromisoformat(receipt['started_at'].replace('Z','+00:00'))
        end=datetime.fromisoformat(receipt['ended_at'].replace('Z','+00:00'))
        _need(start.tzinfo is not None and end.tzinfo is not None and end>=start,'invalid actual receipt interval')
        build=self.get(scope['runtime_build_ref']);environment=self.get(scope['environment_ref'])
        candidate=build.get('candidate_id',build.get('candidate_sha256'))
        _need(candidate and receipt.get('candidate_id')==candidate,'runtime build candidate differs')
        _need(environment.get('image_digest') and receipt.get('environment',{}).get('image_digest')==environment['image_digest']
              and receipt['environment'].get('platform')==scope['platform'],'actual image/platform differs')
        _need(re.fullmatch('sha256:[0-9a-f]{64}',environment['image_digest']),'actual image digest unavailable')
        artifacts={}
        for row in qualification['artifact_refs']:
            _need(isinstance(row,dict) and set(row)=={'path','ref'},'closed artifact binding required')
            path=row['path'];part=PurePosixPath(path)
            _need(isinstance(path,str) and path and not part.is_absolute() and '\\' not in path and '..' not in part.parts and path not in artifacts,'confined unique artifact path required')
            artifacts[path]=self.raw(row['ref'])
        junit=[];manifest=None;raw_seen=False;output_seen=False
        for row in receipt.get('artifacts',[]):
            raw=artifacts.get(row.get('path'))
            _need(raw is not None and hashlib.sha256(raw).hexdigest()==row.get('sha256'),'receipt artifact missing or swapped')
            if row.get('kind')=='junit':junit.append(raw)
            if row.get('kind')=='raw':raw_seen=True
            if row.get('kind') in {'stdout','stderr'}:output_seen=True
            if row.get('kind')=='assertion_manifest':
                _need(manifest is None,'ambiguous assertion manifest');manifest=_json(raw)
                _need(row['sha256']==expected['assertion_manifest_sha256'],'stale independent assertion manifest')
                _need(receipt.get('fixture_pins',{}).get(manifest.get('id'))==row['sha256'],'assertion fixture not frozen')
        _need(set(artifacts)=={row.get('path') for row in receipt.get('artifacts',[])},'unexpected or omitted original artifacts')
        _need(junit and manifest and raw_seen and output_seen,'original JUnit/assertions/raw/output required')
        _need(manifest.get('check_id')=='M1-008/V15' and manifest.get('procedure_sha256')==receipt.get('procedure_sha256'),'frozen V15 procedure differs')
        _need(manifest.get('required_dependency_mode')=='real_boundary','actual boundary mode required')
        assertions=receipt.get('assertions',{});required=manifest.get('required_assertion_ids',[])
        _need(set(required)==set(CASES) and len(required)==13 and assertions.get('required_ids')==required
              and set(assertions.get('passed_ids',[]))==set(CASES) and len(assertions['passed_ids'])==13
              and assertions.get('expected')==assertions.get('observed')==13,'all thirteen independent assertions required')
        observed=[]
        for raw in junit:
            _need(b'<!DOCTYPE' not in raw.upper(),'XML declarations unavailable')
            document=ET.fromstring(raw)
            for item in document.iter():
                if item.tag in {'testsuite','testsuites'}:_need(not any(int(item.get(k,'0')) for k in ('skipped','failures','errors')),'nonpassing raw suite')
                if item.tag=='testcase':
                    _need(not any(item.find(k) is not None for k in ('skipped','failure','error')),'nonpassing raw case')
                    observed.append(item.get('classname','')+'::'+item.get('name',''))
        required_cases=manifest.get('required_case_ids',[])
        _need(observed and len(set(observed))==len(observed) and len(required_cases)==13
              and len(set(required_cases))==13 and set(required_cases)==set(expected['required_case_ids'].values()) and set(required_cases)<=set(observed),'complete original case inventory required')
        _need(receipt.get('interface_revisions',{}).get('M1-IF-015')=='r1' and receipt.get('native_pins')
              and receipt.get('source_baseline_sha256') and receipt.get('profile_pins'),'current native/source/interface/profile pins required')

    def _cases(self,qualification,scope):
        from . import validate
        from .rsi import verify_signature
        _need(callable(self.kind_reader),'independent protected type index unavailable')
        indexed={};seen_halts=set()
        for case,refs in qualification['case_evidence_refs'].items():
            _need(isinstance(refs,list) and refs and len({json.dumps(_ref(p),sort_keys=True) for p in refs})==len(refs),'case original evidence missing')
            records=[(ref,self.kind_reader(ref),self.get(ref)) for ref in refs]
            halted=[(ref,value) for ref,kind,value in records if kind=='rsi-session-result' and value.get('outcome')=='SECURITY_HALTED']
            _need(len(halted)==1,'every violation requires its own durable SECURITY_HALTED')
            halt_ref,halt=halted[0];key=(halt_ref['id'],halt_ref['sha256'])
            _need(key not in seen_halts,'distinct cases reused a durable halt');seen_halts.add(key)
            indexed[case]=(records,halt_ref,halt)
        _need(callable(self.case_observer),'independent thirteen-case denial observer unavailable')
        _need(isinstance(self.public_key,bytes) and len(self.public_key)==32 and self.key_id,'operator-pinned custodian signature identity unavailable')
        attacks=set();sessions=set()
        for case,(records,halt_ref,halt) in indexed.items():
            validate('rsi-session-result',halt);verify_signature(halt,self.public_key,self.key_id)
            session=self.get(halt['session_ref']);validate('rsi-session',session)
            session_key=json.dumps(halt['session_ref'],sort_keys=True)
            _need(session_key not in sessions,'distinct attacks reused a session');sessions.add(session_key)
            target=self.get(session['target_profile_ref']);validate('rsi-target-profile',target)
            _need(halt['parent']==session['parent'] and halt['qualified_by']=='none' and halt['statistics'] is None,'halt changed parent or qualified a violation')
            _need(halt['attempts_used']==len(halt['attempt_refs'])<=session['limits']['max_attempts'],'incomplete durable attempt population')
            genesis=self.get(session['chain_root_ref'])
            _need(genesis.get('session_id')==session['session_id'] and genesis.get('target_ref')==session['target_profile_ref']
                  and genesis.get('hash_profile_ref')==session['hash_profile_ref'] and genesis.get('interface_revision')=='M1-IF-009@r2','case genesis changed')
            previous=None;attempts=[];seen=set()
            for sequence,ref in enumerate(halt['attempt_refs'],1):
                identity=json.dumps(_ref(ref),sort_keys=True);_need(identity not in seen,'case chain repeats an attempt');seen.add(identity)
                attempt=self.get(ref);validate('rsi-attempt',attempt)
                _need(attempt['sequence']==sequence and attempt['previous_ref']==previous and attempt['session_id']==session['session_id'],'case attempt chain differs')
                _need(all(attempt[k]==session[k] for k in ('configuration_ref','chain_root_ref','hash_profile_ref'))
                      and attempt['target_ref']==session['target_profile_ref'] and attempt['parent_ref']==target['parent_ref'],'case attempt scope differs')
                for evidence in attempt['failure_evidence_refs']+attempt['visible_evidence_refs']+attempt['observation_refs']:self.raw(evidence)
                previous=ref;attempts.append((ref,attempt))
            # The independent, installed case owner evaluates its specific OS,
            # authority or protocol denial predicate. A captured PASS/blocked
            # boolean is never a replacement. No such producer exists by default.
            proof=self.case_observer(case,scope,tuple(records))
            fields={'case_id','session_ref','worker_profile_ref','attack_id','denial_refs','attempt_ref'}
            _need(isinstance(proof,dict) and set(proof)==fields and proof['case_id']==case
                  and proof['session_ref']==halt['session_ref'],'independent denial has another case/session')
            _need(isinstance(proof['attack_id'],str) and proof['attack_id'] and proof['attack_id'] not in attacks,'distinct selected attack identity missing')
            attacks.add(proof['attack_id'])
            _need(proof['worker_profile_ref'] in scope['worker_profile_refs'],'case worker profile outside observed scope')
            profile=self.get(proof['worker_profile_ref'])
            _need(profile.get('session_ref')==halt['session_ref'] and profile.get('target_ref')==session['target_profile_ref'],'case worker profile changed session/target')
            violation=[attempt for ref,attempt in attempts if ref==proof['attempt_ref'] and attempt['violations']]
            if proof['attempt_ref'] is None:
                _need(not attempts and not any(kind in {'model-call-start','execution-receipt','rsi-proposer-start'} for _,kind,_ in records),
                      'pre-effect denial cannot erase an actual started attempt/effect')
            else:_need(len(violation)==1,'case denial does not join its actual violating attempt')
            denial_refs=proof['denial_refs']
            _need(isinstance(denial_refs,list) and denial_refs and len({json.dumps(_ref(ref),sort_keys=True) for ref in denial_refs})==len(denial_refs),'case actual denial evidence missing')
            attributable=(violation[0]['failure_evidence_refs']+violation[0]['visible_evidence_refs']+violation[0]['observation_refs']) if violation else [pin for pin,_,_ in records]
            for ref in denial_refs:
                _need(ref in attributable and any(pin==ref for pin,_,_ in records),'case denial is not original indexed attempt evidence');self.raw(ref)
            starts=[value for _,kind,value in records if kind=='model-call-start']
            executions=[value for _,kind,value in records if kind=='execution-receipt']
            for start in starts:
                _need(start.get('call_id') and start.get('call_claim_ref'),'started model identity absent')
                _need(any(kind=='model-run-contained' and value.get('contained') is True and value.get('run_id')==start.get('run_id')
                          and start.get('invocation_id') in value.get('invocation_ids',[]) for _,kind,value in records),'started model containment absent')
            for execution in executions:
                _need(execution.get('observed_runtime') is True and execution.get('identity',{}).get('executor_uid')==12003,'actual worker effect capture absent')
                _need(any(kind=='kernel-group-empty' and value.get('observed_runtime') is True and value.get('populated')==0
                          and value.get('job_id')==execution.get('job_id') for _,kind,value in records),'actual worker tree containment absent')

    def _subject(self,operation,session_ref,candidate_ref):
        from . import validate
        session=self.get(session_ref);validate('rsi-session',session)
        target=self.get(session['target_profile_ref']);validate('rsi-target-profile',target)
        _need(target['parent_declaration_ref']==session['parent_declaration_ref']
              and target['configuration_ref']==session['configuration_ref'],'current session/target parent differs')
        if candidate_ref is None:
            _need(operation in {'session_start','proposal'},'exact subject for this phase is unavailable')
            return session
        if candidate_ref in (target['parent_ref'],session['parent_declaration_ref']):
            _need(operation in {'trial','oracle'},'original parent cannot be published/admitted as a new child')
            self.raw(candidate_ref);return session
        # A source-complete proposed declaration can establish its own exact
        # changed-body/parent scope without becoming admitted. Bare new helper
        # bytes have no independently indexed declaration join yet and block.
        child=self.get(candidate_ref);validate('capsule-declaration',child)
        parent=self.get(session['parent_declaration_ref']);validate('capsule-declaration',parent)
        _need(child['identity'].get('lineage',{}).get('parent')==session['parent_declaration_ref'],'candidate belongs to another parent/session target')
        from ..library import version_matches
        _need(child['identity']['version_label']!=parent['identity']['version_label']
              and version_matches(child['identity']['version_label'],parent['identity']['version_label']+'.x'),'candidate version is outside original parent family')
        import fnmatch
        before={row['path']:row['sha256'] for row in parent['identity']['body']}
        after={row['path']:row['sha256'] for row in child['identity']['body']}
        changed={path for path in before.keys()|after.keys() if before.get(path)!=after.get(path)}
        globs=[item[6:] for item in parent['evolution']['may_change'] if item.startswith('files:')]
        _need(changed and changed<=set(target['mutable_paths'])
              and all(any(fnmatch.fnmatchcase(path,glob) for glob in globs) for path in changed),'candidate escapes original target body scope')
        stripped=[]
        for declaration in (parent,child):
            value=copy.deepcopy(declaration)
            for key in ('version_label','body','lineage'):value['identity'].pop(key,None)
            stripped.append(value)
        _need(stripped[0]==stripped[1],'candidate changed protected declaration identity/authority')
        return session

    def require(self,operation,*,session_ref,worker_profile_ref=None,candidate_ref=None):
        _need(operation in OPERATIONS,'unknown effect operation')
        _ref(session_ref)
        if candidate_ref is not None:_ref(candidate_ref)
        qualification=self.get(self.ref)
        _need(set(qualification)=={'schema','id','scope_ref','verification_receipt_ref','artifact_refs','case_evidence_refs'}
              and qualification['schema']=='ai4r-rsi-security-qualification:1' and qualification['id'],'closed qualification required')
        _need(isinstance(qualification['case_evidence_refs'],dict) and set(qualification['case_evidence_refs'])==set(CASES),'all thirteen case identities required')
        scope=self._scope(qualification);self._receipt(qualification,scope);self._cases(qualification,scope)
        session=self._subject(operation,session_ref,candidate_ref)
        profiles=[(ref,self.get(ref)) for ref in scope['worker_profile_refs']]
        matches=[(ref,p) for ref,p in profiles if p.get('session_ref')==session_ref and p.get('target_ref')==session['target_profile_ref'] and (worker_profile_ref is None or ref==worker_profile_ref)]
        _need(len(matches)==1,'exact session/profile is outside qualified scope')
        return {'qualification_ref':dict(self.ref),'scope_ref':dict(qualification['scope_ref'])}
