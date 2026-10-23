"""Protected source evidence capture and immutable run-bundle publication."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import platform
import stat
import uuid
from importlib.resources import files
from pathlib import PurePosixPath

from .contracts import ResearchError, validate
from .state import json_bytes, utc_now


def check_bundle_digest(snapshot):
    digests=sorted({entry['check_pins']['check_bundle_sha256'] for entry in snapshot['entries'] if entry['check_pins'] is not None})
    return hashlib.sha256(''.join(value+'\n' for value in digests).encode('utf-8')).hexdigest()


def component(value):
    return value.replace(':','_')


class RunEvidence:
    def __init__(self, store, library):
        self.store,self.library=store,library

    def prepare(self, protected, pins):
        """Freeze actual protected readiness pins, never client-supplied data."""
        validate('RunPins',pins)
        snapshot_ref=self.library.snapshot(candidate_pins=protected.get('candidate_pins',()))
        snapshot=self.store.read_record(snapshot_ref,contract_id='library-snapshot')
        configuration=self.store.read_record(protected['configuration_ref'])
        operator=configuration.get('operator',configuration);settings=operator['cc']
        if (not isinstance(pins,dict) or pins.get('library_snapshot_sha256')!=snapshot_ref['sha256']
            or pins.get('check_bundle_set_sha256')!=check_bundle_digest(snapshot)
            or pins.get('plan_policy_ref')!=settings['plan_policy_ref']
            or pins.get('router_enabled')!=settings['router']['enabled']
            or (pins.get('router_version') is None)!= (pins.get('router_enabled') is False)):
            raise ResearchError('bundle_pins','Protected run pins differ from the exact configuration/library snapshot')
        self.store.read_record(pins['plan_policy_ref'],contract_id='plan-policy')
        # Validate the shared RunPins shape through its canonical enclosing
        # contract when publishing; do not invent a standalone public schema.
        context=copy.deepcopy(protected)
        context.update(library_snapshot_ref=snapshot_ref,run_pins=copy.deepcopy(pins))
        return context

    def _one(self,run_id,kind,*,optional=False):
        rows=list(self.store.iter_records(run_id=run_id,kinds=(kind,)))
        if len(rows)!=1:
            if optional and not rows:return None
            raise ResearchError('run_evidence_identity','Run evidence has no unique exact '+kind)
        return rows[0]

    def _file(self,run_id,relative,raw,*,role,media_type='application/octet-stream',source_ref=None,kind=None):
        if isinstance(relative,str) and relative and isinstance(raw,bytes):
            ref={'id':relative,'sha256':hashlib.sha256(raw).hexdigest()}
            record={'id':'evidence-file:'+hashlib.sha256(relative.encode()).hexdigest(),
                'run_id':run_id,'artifact_ref':ref,'role':role,'source_ref':source_ref,'media_type':media_type}
            if self._reuse_file(run_id,relative,raw,ref,record,media_type,kind):return ref
        ref=self.store.capture_record_file(relative,raw,media_type=media_type,kind=kind,scope={'run_id':run_id})
        self.store.append_record('run-evidence-file',{'id':'evidence-file:'+hashlib.sha256(relative.encode()).hexdigest(),
            'run_id':run_id,'artifact_ref':ref,'role':role,'source_ref':source_ref,'media_type':media_type})
        return ref

    def _reuse_file(self,run_id,relative,raw,ref,record,media_type,kind):
        """Reopen an exact completed publication; never trust a cached success."""
        path=PurePosixPath(relative)
        if (path.is_absolute() or '\\' in relative
                or any(part in {'.','..',''} or any(ord(char)<32 for char in part) for part in relative.split('/'))):
            return False  # The original publisher reports malformed paths.
        with self.store._lock:
            rows=self.store.connection.execute(
                'SELECT a.id,a.sha256,a.media_type,r.kind,r.run_id,r.node_id,r.attempt_id '
                'FROM artifacts a LEFT JOIN records r ON r.id=a.id WHERE a.id IN (?,?)',
                (relative,record['id'])).fetchall()
            indexed={row['id']:row for row in rows}
            if len(indexed)!=2:return False  # Missing/partial publications use the original path.
            original=indexed[relative];evidence=indexed[record['id']]
            if evidence['kind'] is None or kind is not None and original['kind'] is None:return False
            expected_scope=(kind,run_id if kind else None,None,None)
            require=(original['sha256']==ref['sha256'] and original['media_type']==media_type
                and tuple(original[key] for key in ('kind','run_id','node_id','attempt_id'))==expected_scope
                and evidence['media_type']=='application/json'
                and tuple(evidence[key] for key in ('kind','run_id','node_id','attempt_id'))==('run-evidence-file',run_id,None,None))
            evidence_ref={'id':record['id'],'sha256':evidence['sha256']}
            if (not require or self.store.read_blob(ref)!=raw
                    or self.store.read_blob(evidence_ref)!=json_bytes(record)):
                raise ResearchError('identity_conflict','Existing evidence publication differs from exact bytes or original scope')
            target=self.store.root/'records'
            try:
                for part in (None,*path.parts[:-1]):
                    if part is not None:target=target/part
                    if target.is_symlink():raise ResearchError('record_path','Records ancestry cannot be a symbolic link')
                    if not target.is_dir():return False
                target=target/path.name;metadata=target.lstat()
                if (stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode)
                        or metadata.st_nlink!=1 or target.read_bytes()!=raw):
                    raise ResearchError('identity_conflict','Existing evidence file contains unsafe or different bytes')
            except FileNotFoundError:
                return False
            return True

    def missing(self,run_id,item,reason,*,blocking=False):
        self.store.append_record('run-evidence-missing',{'id':'missing:'+uuid.uuid4().hex,'run_id':run_id,
            'obligation_id':item,'reason':reason,'blocking':blocking})

    def start(self,run_id,protected):
        run=self.store.get_run(run_id)
        prior=self._one(run_id,'run-start',optional=True)
        if prior:
            if any(prior['record'][key]!=protected[key] for key in ('configuration_ref','library_snapshot_ref')) or prior['record']['pins']!=protected['run_pins']:
                raise ResearchError('run_evidence_identity','Run start cannot replace frozen configuration or pins')
            return prior['ref']
        self.store.read_blob(protected['library_snapshot_ref']);self.store.read_blob(protected['configuration_ref'])
        workflow=files('jiuwenswarm.research').joinpath('native.py').read_bytes()
        workflow_ref=self.store.put_blob(workflow,media_type='text/x-python')
        host={'scope':'application_process','operating_system':platform.platform(),'cpu_model':platform.processor() or None,
            'cpu_cores':os.cpu_count(),'memory_bytes':None,'gpu':None,'gpu_driver':None}
        try:host['memory_bytes']=os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES')
        except (ValueError,OSError,AttributeError):pass
        record={'id':'run-start:'+uuid.uuid4().hex,'run_id':run_id,'started_at':utc_now(),
            'configuration_ref':protected['configuration_ref'],'library_snapshot_ref':protected['library_snapshot_ref'],
            'pins':protected['run_pins'],'workflow_script_ref':workflow_ref,'host_facts':host,
            'workspace_ref':protected.get('workspace_ref'),'evaluation_profile_id':protected.get('profile_id'),
            'fault_ids':[],'effective_seed':None,'state_at_start':run['state']}
        ref=self._file(run_id,'runs/'+component(run_id)+'/run-start.json',json_bytes(record),role='run_start',media_type='application/json',kind='run-start')
        if host['cpu_model'] is None:self.missing(run_id,'host-cpu-model','The application process did not report a CPU model')
        self.missing(run_id,'host-gpu','No protected GPU model/driver observation is available to this capture')
        return ref

    def bind_plan(self,run_id,plan_ref):
        start=self._one(run_id,'run-start')['record'];plan=self.store.read_record(plan_ref,contract_id='run-plan')
        if (not plan['frozen'] or plan['configuration_ref']!=start['configuration_ref']
            or plan['library_snapshot_ref']!=start['library_snapshot_ref'] or plan['policy_ref']!=start['pins']['plan_policy_ref']):
            raise ResearchError('bundle_pins','Frozen plan does not use the exact run-start pins')
        self.store.read_blob(plan['acceptance_ref'])
        prior=self._one(run_id,'run-plan-binding',optional=True)
        if prior:
            if prior['record']['plan_ref']!=plan_ref:raise ResearchError('frozen_context','Run cannot replace its frozen plan')
            return prior['ref']
        return self.store.append_record('run-plan-binding',{'id':'run-plan-binding:'+uuid.uuid4().hex,'run_id':run_id,
            'plan_ref':plan_ref,'recorded_at':utc_now()})

    def capture_invocation_start(self,contract_ref,contract):
        run_id=contract['run_id'];binding=contract['bindings'][0]
        prefix='/'.join(['runs',component(run_id),component(contract['node_id']),component(contract['attempt_id']),component(contract['subnode_id'])])
        declaration=self.store.read_record(binding['declaration_ref'],contract_id='capsule-declaration')
        self._file(run_id,prefix+'/capsule/declaration.json',self.store.read_blob(binding['declaration_ref']),role='capsule',source_ref=binding['declaration_ref'],media_type='application/json')
        by_sha={ref['sha256']:ref for ref in binding['implementation_refs']}
        for body in declaration['identity']['body']:
            ref=by_sha.get(body['sha256'])
            if ref is None:raise ResearchError('capture_identity','Exact declared body is missing from frozen invocation')
            self._file(run_id,prefix+'/capsule/body/'+body['path'],self.store.read_blob(ref),role='capsule',source_ref=ref)
        for ref in contract['input_refs']:
            self._file(run_id,prefix+'/inputs/'+ref['sha256'],self.store.read_blob(ref),role='input',source_ref=ref)

    def capture_prompt(self,contract,ordinal,text):
        if type(ordinal) is not int or ordinal<1 or not isinstance(text,str):raise ResearchError('capture_identity','Exact governed prompt ordinal/text required')
        raw=text.encode('utf-8');source=self.store.put_blob(raw,media_type='text/plain')
        prefix='/'.join(['runs',component(contract['run_id']),component(contract['node_id']),component(contract['attempt_id']),component(contract['subnode_id'])])
        return self._file(contract['run_id'],prefix+('/prompt.txt' if ordinal==1 else '/prompt.'+str(ordinal)+'.txt'),raw,
            role='prompt',source_ref=source,media_type='text/plain')

    def invocation_trace_refs(self,contract):
        prefix='/'.join(['runs',component(contract['run_id']),component(contract['node_id']),component(contract['attempt_id']),component(contract['subnode_id'])])+'/'
        return [r['record']['artifact_ref'] for r in self.store.iter_records(run_id=contract['run_id'],kinds=('run-evidence-file',))
            if r['record']['role'] in {'capsule','prompt','trace','workspace'} and r['record']['artifact_ref']['id'].startswith(prefix)
            and ('/trace/native/' not in r['record']['artifact_ref']['id'] or r['record']['artifact_ref']['id'].endswith(('/index.json','/index.v2.json')))]

    def capture_invocation_traces(self,contract,invocation_id):
        records=self.store.iter_records(run_id=contract['run_id'],kinds=('model-call-start',))
        for row in records:
            if row['kind']!='model-call-start' or row['record'].get('invocation_id')!=invocation_id:continue
            start=row['record']
            if start.get('contract_ref') is None:continue
            if self.store.read_record(start['contract_ref'])!=contract:raise ResearchError('capture_identity','Native trace start names another contract')
            try:call_ref=self.store.record_ref(start['call_id'])
            except ResearchError:continue
            call=self.store.read_record(call_ref,contract_id='model-call')
            observation={key:contract[key] for key in ('run_id','node_id','subnode_id','attempt_id')};observation['contract_ref']=start['contract_ref']
            for ref in call['evidence_refs']:
                if self.store.record_kind(ref)=='native-governed-trace':self.capture_native_trace(observation,row['ref'],call_ref,ref)

    def _native_trace(self,observation,start_ref,call_ref,summary_ref):
        """Reopen the complete original packet closure without making copies."""
        def require(condition):
            if not condition:raise ResearchError('capture_identity','Native trace is not the exact protected invocation/call packet closure')
        start=self.store.read_record(start_ref);call=self.store.read_record(call_ref);summary=self.store.read_record(summary_ref)
        require(self.store.record_kind(start_ref)=='model-call-start' and self.store.record_kind(call_ref)=='model-call'
            and self.store.record_kind(summary_ref)=='native-governed-trace' and summary_ref in call['evidence_refs'])
        scope={key:observation[key] for key in ('run_id','node_id','subnode_id','attempt_id','contract_ref')}
        scope.update({key:start[key] for key in ('invocation_id','execution_id','call_id')});scope['model_call_start_ref']=start_ref
        require(start['contract_ref']==observation['contract_ref'] and start['run_id']==observation['run_id']
            and call['id']==start['call_id'] and all(call[key]==start[key] for key in ('invocation_id','execution_id')))
        require(isinstance(summary,dict) and set(summary)=={'schema','scope','status','event_refs'}
            and summary['schema']=='ai4r-native-governed-trace:1' and summary['scope']==scope
            and summary['status'] in {'completed','failed','interrupted'} and isinstance(summary['event_refs'],list))
        captured=[]
        for sequence,event_ref in enumerate(summary['event_refs']):
            event=self.store.read_record(event_ref)
            require(self.store.record_kind(event_ref)=='native-governed-trace-event' and isinstance(event,dict)
                and set(event)=={'schema','scope','sequence','direction','method','raw_ref'}
                and event['schema']=='ai4r-native-governed-trace-event:1' and event['scope']==scope
                and type(event['sequence']) is int and event['sequence']==sequence
                and event['direction'] in {'in','out'} and isinstance(event['method'],str))
            validate('Ref',event['raw_ref']);self.store.read_blob(event['raw_ref'])
            captured.append((event_ref,event))
        run_id=observation['run_id']
        prefix='/'.join(['runs',component(run_id),component(observation['node_id']),component(observation['attempt_id']),
            component(observation['subnode_id']),'trace','native',call_ref['sha256']])
        return prefix,summary,captured

    def _native_trace_index(self,start_ref,call_ref,summary_ref,summary_file_ref,summary,captured):
        return {'schema':'ai4r-native-trace-file-index:2','call_ref':call_ref,
            'model_call_start_ref':start_ref,'summary_ref':summary_ref,'summary_file_ref':summary_file_ref,
            'status':summary['status'],'events':[{'sequence':event['sequence'],
                'event_ref':event_ref,'raw_ref':event['raw_ref']} for event_ref,event in captured]}

    def capture_native_trace(self,observation,start_ref,call_ref,summary_ref):
        prefix,summary,captured=self._native_trace(observation,start_ref,call_ref,summary_ref)
        run_id=observation['run_id']
        summary_file=self._file(run_id,prefix+'/summary.json',self.store.read_blob(summary_ref),
            role='trace',source_ref=summary_ref,media_type='application/json')
        # Original packets/events are already durable under their exact Refs.
        # Optional readable copies must not delay checking or successor release.
        # This versioned index states actual source Refs, never nonexistent files.
        index=self._native_trace_index(start_ref,call_ref,summary_ref,summary_file,summary,captured)
        index_file=self._file(run_id,prefix+'/index.v2.json',json_bytes(index),role='trace',media_type='application/json')
        return [summary_file,index_file]

    def native_trace_export_files(self,run_id,copied):
        """Project original bytes only after the caller's disclosure check.

        Legacy v1 indexes retain their existing physical-file export. Version 2
        projects the same descriptive packet paths without modifying the Store.
        """
        ref=copied['artifact_ref']
        if copied['role']!='trace' or '/trace/native/' not in ref['id'] or not ref['id'].endswith('/index.v2.json'):
            return []
        index=self.store.read_record(ref)
        if (copied['run_id']!=run_id or not isinstance(index,dict)
                or index.get('schema')!='ai4r-native-trace-file-index:2'):
            raise ResearchError('capture_identity','Native source index differs from its owned run')
        summary=self.store.read_record(index['summary_ref'])
        observation={key:summary['scope'][key] for key in ('run_id','node_id','subnode_id','attempt_id','contract_ref')}
        if observation['run_id']!=run_id:
            raise ResearchError('capture_identity','Native source index names another run')
        prefix,summary,captured=self._native_trace(observation,index['model_call_start_ref'],index['call_ref'],index['summary_ref'])
        summary_file={'id':prefix+'/summary.json','sha256':index['summary_ref']['sha256']}
        expected=self._native_trace_index(index['model_call_start_ref'],index['call_ref'],index['summary_ref'],summary_file,summary,captured)
        if (ref['id']!=prefix+'/index.v2.json' or index!=expected
                or self.store.read_blob(summary_file)!=self.store.read_blob(index['summary_ref'])):
            raise ResearchError('capture_identity','Native source index is not the complete original packet closure')
        result=[]
        for event_ref,event in captured:
            filename=str(event['sequence']).zfill(8)
            result.extend([{'path':'records/'+prefix+'/'+filename+'.event.json','artifact_ref':event_ref,'media_type':'application/json'},
                {'path':'records/'+prefix+'/'+filename+'.packet','artifact_ref':event['raw_ref'],'media_type':'application/octet-stream'}])
        return result

    def capture_invocation_end(self,observation_ref):
        observation=self.store.read_record(observation_ref,contract_id='invocation-observation');run_id=observation['run_id']
        prefix='/'.join(['runs',component(run_id),component(observation['node_id']),component(observation['attempt_id']),component(observation['subnode_id'])])
        for ref in observation['output_refs']:
            self._file(run_id,prefix+'/outputs/'+ref['sha256'],self.store.read_blob(ref),role='output',source_ref=ref,
                media_type=self.store.artifact_metadata(ref)['media_type'])
        records=self.records(run_id,kinds=('model-call-start','gate-decision'))
        invocation_ids={row['record']['invocation_id'] for row in records if row['kind']=='model-call-start' and row['record'].get('contract_ref')==observation['contract_ref']}
        calls=[row for row in records if row['kind']=='model-call' and row['record']['invocation_id'] in invocation_ids]
        if calls:
            self._file(run_id,prefix+'/trace/model_calls.jsonl',b''.join(self.store.read_blob(row['ref'])+b'\n' for row in calls),role='trace',media_type='application/x-ndjson')
            for row in calls:
                starts=[r['record'] for r in records if r['kind']=='model-call-start' and r['record'].get('call_id')==row['record']['id']]
                if len(starts)!=1:raise ResearchError('capture_identity','Model prompt has no unique protected actual start')
                claim=self.store.read_record(starts[0]['call_claim_ref']);ordinal=claim['call_ordinal']
                for ref in row['record']['evidence_refs']:
                    if self.store.record_kind(ref)=='model-call-input':
                        captured=self.capture_prompt(self.store.read_record(observation['contract_ref']),ordinal,self.store.read_record(ref)['prompt'])
                        self.store.append_record('prompt-call-link',{'id':'prompt-call:'+row['record']['id'],'run_id':run_id,
                            'prompt_ref':captured,'model_call_input_ref':ref,'call_ref':row['ref']})
                    elif self.store.record_kind(ref)=='native-governed-trace':
                        start_refs=[r['ref'] for r in records if r['kind']=='model-call-start' and r['record'].get('call_id')==row['record']['id']]
                        self.capture_native_trace(observation,start_refs[0],row['ref'],ref)
        else:self.missing(run_id,'prompt:'+observation['id'],'No actual governed model prompt was produced by this invocation')
        self.missing(run_id,'workspace:'+observation['id'],'An original worker workspace snapshot was not supplied by the effect owner')
        self.missing(run_id,'trace:'+observation['id'],'Captured per-call native protocol packets and governed records do not supply an original complete invocation/tool trace')
        gates=[row for row in records if row['kind']=='gate-decision' and observation_ref in row['record']['invocation_refs']]
        if gates:
            evidence={'observation_ref':observation_ref,'decision_refs':[row['ref'] for row in gates],
                'check_result_refs':list({json.dumps(row['record']['deterministic_result_ref'],sort_keys=True):row['record']['deterministic_result_ref'] for row in gates}.values())}
            self._file(run_id,prefix+'/gate/evidence.json',json_bytes(evidence),role='gate',media_type='application/json')
            for ref in evidence['check_result_refs']:
                result=self.store.read_record(ref,contract_id='deterministic-check-result')
                for check in result['results']:
                    self._file(run_id,prefix+'/gate/checks/'+component(check['check_id'])+'.out',json_bytes(check),role='check',source_ref=ref,media_type='application/json')
            assessments=[]
            for row in gates:
                ref=row['record'].get('assessment_ref')
                if row['record']['scope_kind']=='subnode' and ref is not None and ref not in assessments:assessments.append(ref)
            for ordinal,assessment_ref in enumerate(assessments):
                relevant=[row['record'] for row in gates if row['record'].get('assessment_ref')==assessment_ref]
                reviewers=[]
                for decision in relevant:
                    for ref in decision['invocation_refs']:
                        observed=self.store.read_record(ref,contract_id='invocation-observation')
                        contract=self.store.read_record(observed['contract_ref'])
                        if contract.get('bindings',[{}])[0].get('role')=='verifier' and ref not in reviewers:reviewers.append(ref)
                texts=[]
                for ref in reviewers:
                    reviewer=self.store.read_record(ref);starts=[r['record'] for r in records if r['kind']=='model-call-start' and r['record'].get('contract_ref')==reviewer['contract_ref']]
                    ids={r['invocation_id'] for r in starts}
                    for row in records:
                        if row['kind']=='model-call' and row['record']['invocation_id'] in ids:
                            for item in row['record']['evidence_refs']:
                                if self.store.record_kind(item)=='model-call-output' and item not in [pair[0] for pair in texts]:
                                    value=self.store.read_record(item)
                                    if value.get('call_id')!=row['record']['id']:raise ResearchError('capture_identity','Verifier output belongs to another actual call')
                                    texts.append((item,value['text'].encode('utf-8')))
                if len(texts)==1:
                    ref,raw=texts[0]
                    self._file(run_id,prefix+('/verifier/output.txt' if ordinal==0 else '/verifier/output.'+str(ordinal+1)+'.txt'),raw,
                        role='verifier',source_ref=ref,media_type='text/plain;charset=utf-8')
                else:self.missing(run_id,'verifier-output:'+assessment_ref['sha256'],'A unique complete original governed verifier output was not available')

    def capture_node_gate(self,decision_ref):
        decision=self.store.read_record(decision_ref,contract_id='gate-decision')
        if decision['scope_kind']!='node':raise ResearchError('capture_identity','Only an actual node decision belongs in node-gate')
        prefix='/'.join(['runs',component(decision['run_id']),component(decision['node_id']),component(decision['attempt_id']),'node-gate'])
        return self._file(decision['run_id'],prefix+'/decision.json',self.store.read_blob(decision_ref),role='node_gate',
            source_ref=decision_ref,media_type='application/json')

    def records(self,run_id,*,kinds=None):
        rows=list(self.store.iter_records(run_id=run_id,kinds=kinds));seen={(row['ref']['id'],row['ref']['sha256']) for row in rows}
        for row in tuple(rows):
            if row['kind']!='model-call-start':continue
            try:ref=self.store.record_ref(row['record']['call_id'])
            except ResearchError as error:
                if error.code=='evidence_unavailable':continue
                raise
            call=self.store.read_record(ref,contract_id='model-call');start=row['record']
            if call['invocation_id']!=start.get('invocation_id') or call['execution_id']!=start.get('execution_id'):
                raise ResearchError('bundle_identity','Model call does not join its exact protected run start')
            if (ref['id'],ref['sha256']) not in seen:
                rows.append({'kind':'model-call','ref':ref,'record':call});seen.add((ref['id'],ref['sha256']))
        return rows

    def finish(self,run_id):
        rows=self.records(run_id);prefix='runs/'+component(run_id)+'/run-end/'
        if self._one(run_id,'run-end',optional=True) is None:
            log=[row for row in rows if row['kind'] in {'dispatch-record','gate-decision','escalation','execution-contained','execution-cancelled-pending'}]
            self._file(run_id,prefix+'run-log.jsonl',b''.join(self.store.read_blob(row['ref'])+b'\n' for row in log),role='run_end',media_type='application/x-ndjson')
            self.store.append_record('run-end',{'id':'run-end:'+uuid.uuid4().hex,'run_id':run_id,'ended_at':utc_now(),
                'state':self.store.get_run(run_id)['state'],'source_refs':[row['ref'] for row in log]})
            self.missing(run_id,'run-trace','The original full native workflow trace was not supplied before cleanup')
            self.missing(run_id,'run-log','The retained run-log contains protected host events only; the original full native workflow log was not supplied')
        return self.build(run_id,final=True)

    def build(self,run_id,*,final=False):
        if final:
            prior=self._one(run_id,'run-bundle',optional=True)
            if prior:return prior['ref']
        run=self.store.get_run(run_id);start=self._one(run_id,'run-start')['record']
        snapshot=self.store.read_record(start['library_snapshot_ref'],contract_id='library-snapshot');pins=start['pins']
        if pins['library_snapshot_sha256']!=start['library_snapshot_ref']['sha256'] or pins['check_bundle_set_sha256']!=check_bundle_digest(snapshot):
            raise ResearchError('bundle_pins','Run pins do not match exact original snapshot bytes')
        if (pins['router_version'] is None)!=(pins['router_enabled'] is False):raise ResearchError('bundle_pins','Router pin is inconsistent')
        binding=self._one(run_id,'run-plan-binding',optional=True);plan=None
        if binding:
            plan=self.store.read_record(binding['record']['plan_ref'],contract_id='run-plan')
            if (plan['library_snapshot_ref']!=start['library_snapshot_ref'] or plan['policy_ref']!=pins['plan_policy_ref']
                or plan['configuration_ref']!=start['configuration_ref']):raise ResearchError('bundle_pins','Frozen plan pin differs from run start')
        rows=self.records(run_id);missing=[]
        def absent(item,reason,blocking=False):
            value={'obligation_id':item,'reason':reason,'blocking':blocking}
            if value not in missing:missing.append(value)
        for row in rows:
            if row['kind']=='run-evidence-missing':absent(row['record']['obligation_id'],row['record']['reason'],row['record']['blocking'])
        if plan is None:absent('run-plan','No run plan has been committed and frozen')
        if self._one(run_id,'run-end',optional=True) is None:absent('run-end','Run-end capture has not been produced')
        decisions=[];dispatches=[];observations=[];calls=[];routes=[];artifacts=[];attempts=set();previous_end=None
        for row in rows:
            value=row['record'];kind=row['kind'];ref=row['ref']
            if kind in {'gate-decision','dispatch-record','invocation-observation','route-record'} and value.get('run_id')!=run_id:
                raise ResearchError('bundle_identity','Evidence record belongs to another run')
            if kind=='gate-decision':
                validate(kind,value);decisions.append({key:value[key] for key in ('node_id','subnode_id','scope_kind','verdict','action','recorded_at')}|{'decision_ref':ref,'output_port':value.get('output_port')})
            elif kind=='dispatch-record':
                validate(kind,value)
                if value['attempt_id'] in attempts or dispatches and (previous_end is None or value['started_at']<previous_end):
                    raise ResearchError('bundle_dispatch','Dispatch attempts are duplicated or overlap')
                attempts.add(value['attempt_id']);previous_end=value['ended_at']
                dispatches.append({key:value[key] for key in ('node_id','attempt_id','started_at','ended_at','outcome')}|{'dispatch_record_ref':ref})
            elif kind=='invocation-observation':validate(kind,value);observations.append(ref)
            elif kind=='planner_attempt':
                artifacts.append(ref)
                for key in ('candidate_ref', 'diagnostics_ref'):
                    self.store.read_blob(value[key]);artifacts.append(value[key])
            elif kind=='model-call':calls.append(ref)
            elif kind=='route-record':validate(kind,value);routes.append(ref)
            elif kind=='run-evidence-file' and value['role'] in {'input','output','run_end','node_gate'}:
                self.store.read_blob(value['artifact_ref']);artifacts.append(value['artifact_ref'])
        from .finite_evaluation import finite_evidence_refs
        finite=finite_evidence_refs(self.store,run_id)
        if finite is not None:
            artifacts.extend(finite['artifact_refs'])
            scheduled=set(finite['stages'])
            ordinary=('intention_compiler','planner','search','screening','hypothesis','builder','benchmark','evaluation','delivery')
            omissions=[{'stage':stage,'reason':'This approved finite evaluation did not schedule this product stage; no invocation, dispatch or product completion is claimed'}
                for stage in ordinary if 'research.'+stage not in scheduled]
            diagnostic={'schema':'ai4r-finite-e1-scope:1','id':'finite-scope:'+hashlib.sha256(json_bytes([run_id,finite['qualification_ref'],finite['plan_binding_ref']])).hexdigest(),
                'run_id':run_id,'qualification_ref':finite['qualification_ref'],'plan_binding_ref':finite['plan_binding_ref'],
                'stages':finite['stages'],'omissions':omissions,'invalid_for_product':True}
            artifacts.append(self.store.append_record('finite-e1-scope',diagnostic))
            for omitted in omissions:absent('finite-scope:'+omitted['stage'],omitted['reason'])
            absent('finite-scope:protected-policy-withheld','The whole protected case policy/schedule and other cases are withheld; only this owned run original inputs and exact references are exported')
        final_calls={self.store.read_record(ref)['id'] for ref in calls}
        for row in rows:
            if row['kind']=='model-call-start' and row['record']['call_id'] not in final_calls:
                absent('model-call:'+row['record']['call_id'],'Started model call has no terminal canonical record; outcome remains unknown')
        if plan:
            outputs={item['node_id']:self.store.accepted_outputs(run_id,item['node_id']) for item in plan['nodes']}
            for node in plan['nodes']:
                for port in node['outputs']:
                    if port['required'] and port['name'] not in outputs[node['node_id']]:
                        absent(node['node_id']+'.'+port['name'],'Required planned output is not committed accepted evidence')
        status='in_progress' if run['state'] in {'pending','running'} else run['state'] if run['state'] in {'completed','partial','halted','paused'} else 'halted'
        if status=='completed':
            if any(not any(g['node_id']==d['node_id'] and g['scope_kind']=='node' and g['action']=='advance' for g in decisions) for d in dispatches):
                raise ResearchError('bundle_gate','Completed run lacks an advancing stored node gate for a dispatch')
        injections=[r for r in rows if r['kind']=='fault-injection']
        fault_ids=list(dict.fromkeys(r['record']['fault_id'] for r in injections))
        if fault_ids and start['evaluation_profile_id'] is None:raise ResearchError('bundle_faults','Faults require a protected evaluation profile')
        evaluation=self.store.evaluation_binding(run_id)
        if evaluation:
            value=evaluation['record']
            if value['evaluation_profile_id']!=start['evaluation_profile_id'] or any(r['record']['evaluation_profile_id']!=value['evaluation_profile_id'] for r in injections):
                raise ResearchError('bundle_faults','Actual injection belongs to another frozen evaluation profile')
            labels={'run_id':run_id,'evaluation_profile_id':value['evaluation_profile_id'],'profile_ref':value['profile_ref'],
                'invalid_for_product':value['invalid_for_product'],'injection_refs':[r['ref'] for r in injections]}
            labelref=self.store.capture_record_file('bundles/'+component(run_id)+'/evaluation-labels-'+uuid.uuid4().hex+'.json',
                json_bytes(labels),media_type='application/json',kind='run-evaluation-labels',scope={'run_id':run_id})
            artifacts.append(labelref)
        bundle={'schema_version':'1.0.0','id':'bundle:'+uuid.uuid4().hex,'run_id':run_id,'exported_at':utc_now(),'status':status,
            'plan_source':plan['plan_source'] if plan else None,'run_plan_ref':binding['record']['plan_ref'] if binding else None,
            'configuration_ref':start['configuration_ref'],'evaluation_profile_id':start['evaluation_profile_id'],'pins':pins,
            'effective_seed':start['effective_seed'],'artifact_refs':list({(ref['id'],ref['sha256']):ref for ref in artifacts}.values()),
            'decision_refs':[row['decision_ref'] for row in decisions],'gate_decisions':decisions,'node_dispatches':dispatches,
            'observation_refs':observations,'model_call_refs':calls,'route_record_refs':routes,'fault_ids':fault_ids,
            'missing_evidence':missing,'redactions':[]}
        validate('run-bundle',bundle)
        path='bundles/'+component(run_id)+('/manifest.json' if final else '/snapshots/'+component(bundle['id'])+'.json')
        return self.store.capture_record_file(path,json_bytes(bundle),media_type='application/json',kind='run-bundle' if final else 'run-bundle-snapshot',scope={'run_id':run_id})
