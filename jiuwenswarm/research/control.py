"""Authenticated native coordination; durable allocation precedes model work."""

from __future__ import annotations

import asyncio
import copy
import hashlib
import inspect
import uuid

from .contracts import Principal, ResearchError, validate
from .intake import extract_document, qualify_intake
from .state import json_bytes


def status_reasons(run,records):
    """Run reason plus the executor's real cause when a protected stop carries one."""
    reasons=[run['reason']] if run['reason'] else []
    for envelope in records:
        fault=envelope['record'].get('executor_fault') if envelope['kind']=='protected-invocation-stop' else None
        if isinstance(fault,dict):
            from .private_rpc import fault_cause_text
            reasons.append('executor fault in %s: %s %s at %s'%(envelope['record'].get('node_id'),fault.get('exception_class'),fault.get('code') or '',fault.get('frame'))+fault_cause_text(fault))
    return reasons


class ResearchService:
    def __init__(self,store,*,registry,model,executor=None,profiles=None,readiness=None,
                 compiler=None,binder=None,scheduler=None,workspaces=None,upload_manager=None,evidence=None,finite_e1=None):
        self.store,self.registry,self.model=store,registry,model
        self.executor,self.profiles,self._readiness=executor,profiles,readiness
        self.compiler,self.binder,self.scheduler=compiler,binder,scheduler
        self._workspaces={};self._tasks={};self._containments={};self.upload_manager=upload_manager
        self.evidence=evidence
        self.finite_e1=finite_e1
        if finite_e1 is not None:
            from .finite_evaluation import FiniteE1
            if type(finite_e1) is not FiniteE1 or finite_e1.store is not store:
                raise ResearchError('finite_e1_binding','Finite execution needs the installed exact owner/store')
        for (account_id,workspace_id),protected in (workspaces or {}).items():
            self.configure_workspace(account_id,workspace_id,**protected)

    def configure_workspace(self,account_id,workspace_id,**protected):
        key=(account_id,workspace_id)
        for name in ('configuration_ref','profile_ref','workspace_ref','input_directory_ref'):
            self.store.read_blob(protected[name])
        from .operator_config import OperatorConfiguration
        configuration=self.store.read_record(protected['configuration_ref'])
        operator=OperatorConfiguration.from_mapping(configuration.get('operator',configuration),resolve_profile=lambda ref:self.store.read_record(ref)).snapshot()
        for name,value in [('router',operator['cc']['router']),('plan_source',operator['cc']['plan_source'])]:
            if name in protected and protected[name]!=value:raise ResearchError('configuration_override','Workspace cannot override protected cc settings')
            protected[name]=value
        if key in self._workspaces and self._workspaces[key]!=protected:raise ResearchError('frozen_context','Protected workspace initialization cannot change in place')
        self._workspaces[key]=copy.deepcopy(protected)

    def _workspace(self,principal,workspace_id=None):
        choices=[(key,value) for key,value in self._workspaces.items() if key[0]==principal.account_id and key[1] in principal.workspace_ids]
        if workspace_id is None:
            if len(choices)!=1:raise ResearchError('validation','Select one authorized initialized workspace')
            return choices[0][0][1],choices[0][1]
        for key,value in choices:
            if key[1]==workspace_id:return workspace_id,value
        raise ResearchError('auth','Workspace has no protected initialization')

    def client_defaults(self,principal):
        principal.require('status')
        if not self._workspaces:
            return {'account_id':principal.account_id,'workspace_id':next(iter(principal.workspace_ids)) if len(principal.workspace_ids)==1 else None,
                    'configuration_ref':None,'plan_source':None,'profile_id':None,
                    'inputs_ready':self.upload_manager is not None,
                    'local_chat_ready':getattr(self,'local_chat_ready',False)}
        workspace,protected=self._workspace(principal)
        return {'account_id':principal.account_id,'workspace_id':workspace,'configuration_ref':copy.deepcopy(protected['configuration_ref']),
                'plan_source':protected.get('plan_source','static'),'profile_id':protected.get('profile_id'),
                'inputs_ready':self.upload_manager is not None,
                'local_chat_ready':getattr(self,'local_chat_ready',False)}

    async def ingest(self,principal,text,upload_refs=(),*,workspace_id=None):
        workspace,protected=self._workspace(principal,workspace_id);principal.require('submit',workspace)
        # Ingest is an internal part of authenticated native submit, not another
        # public bearer operation or a model-dispatch endpoint.
        qualified_principal=Principal(principal.account_id,principal.workspace_ids,principal.operations|{'ingest'},principal.audiences)
        # Upload reads, hash verification and durable captures are blocking I/O.
        # Keep them off the native Gateway loop so status/configuration replies
        # and the intake acknowledgement can continue to use the connection.
        return await asyncio.to_thread(qualify_intake,self.store,qualified_principal,text,
            copy.deepcopy(upload_refs),workspace_id=workspace,
            **{key:copy.deepcopy(protected[key]) for key in ('profile_ref','workspace_ref','input_directory_ref')})

    async def readiness(self,principal):
        principal.require('readiness')
        if self._readiness is None:raise ResearchError('unavailable','Protected readiness probes are not configured')
        value=self._readiness(principal) if callable(self._readiness) else self._readiness.report(principal)
        if inspect.isawaitable(value):value=await value
        validate('client-readiness',value);return value

    async def submit(self,principal,submission):
        if not isinstance(submission,dict):raise ResearchError('validation','Submission must be an object')
        normalized=dict(submission,account_id=principal.account_id)
        validate('client-submission',normalized)
        principal.require('submit',normalized['workspace_id'])
        _,protected=self._workspace(principal,normalized['workspace_id'])
        if normalized['configuration_ref']!=protected['configuration_ref']:raise ResearchError('auth','Configuration is not the protected approved snapshot')
        normalized.setdefault('plan_source',protected.get('plan_source','static'));normalized.setdefault('interaction_mode','interactive')
        if normalized.get('profile_id')!=protected.get('profile_id'):raise ResearchError('validation','Evaluation profile differs from protected target')
        if normalized.get('fault_id'):
            if self.profiles is None or not protected.get('profile_id') or not normalized.get('evaluation'):
                raise ResearchError('validation','Fault injection is not enabled for this protected evaluation target')
        if self._readiness is not None:
            readiness=await self.readiness(Principal(principal.account_id,principal.workspace_ids,principal.operations|{'readiness'},principal.audiences))
            if not readiness['ready']:raise ResearchError('unavailable','Target does not satisfy mandatory operation prerequisites')
        if self.evidence is not None:
            if self._readiness is None:raise ResearchError('unavailable','Protected real run pins are unavailable')
            protected=self.evidence.prepare(protected,readiness['pins'])
        if protected.get('profile_id') is not None:
            if self.profiles is None:raise ResearchError('unavailable','Protected evaluation profile is not initialized')
            self.profiles.validate_submission(normalized,protected,principal=principal)
        intake=self.store.read_record(normalized['intake_ref'],contract_id='qualified-intake')
        if intake['user_id']!=principal.account_id or any(intake[key]!=protected[key] for key in ('profile_ref','workspace_ref','input_directory_ref')):
            raise ResearchError('auth','Intake is outside this authenticated workspace/profile')
        uploads=[self.store.read_record(ref,contract_id='client-upload')['id'] for ref in intake['upload_refs']]
        fingerprint=hashlib.sha256(json_bytes(normalized)).hexdigest()
        run,fresh=self.store.allocate_run(principal.account_id,normalized['client_request_id'],fingerprint,
            'run:'+uuid.uuid4().hex,normalized['workspace_id'],normalized,uploads)
        if fresh:
            freeze_model = getattr(self, 'freeze_model_selection', None)
            if freeze_model is not None and not protected.get('profile_id') and protected.get('finite_e1_binding_ref') is None:
                try:
                    value = freeze_model(principal, run['id'])
                    if inspect.isawaitable(value): await value
                except Exception:
                    self.store.set_run_state(run['id'], 'halted', reason='model_selection_unavailable')
                    raise ResearchError('unavailable', 'The selected model could not be frozen for this run') from None
            # Retain the actual authenticated pre-capture context only for the
            # source-defined single new linked replan; it grants no replay.
            submission_context=copy.deepcopy(protected)
            self.store.append_record('client-submission',dict(normalized,id='submission:'+uuid.uuid4().hex,run_id=run['id']))
            if protected.get('profile_id') is not None:
                try:self.profiles.bind_run(run['id'],normalized,protected,principal=principal)
                except BaseException:
                    self.store.set_run_state(run['id'],'halted',reason='evaluation_binding_unavailable')
                    raise
            if protected.get('finite_e1_binding_ref') is not None:
                try:
                    from .finite_status import record_selection
                    record_selection(self.store,run['id'],protected)
                except BaseException:
                    self.store.set_run_state(run['id'],'halted',reason='finite_selection_unavailable')
                    raise
            if protected.get('finite_e1_binding_ref') is None and protected.get('profile_id') is None:
                try:
                    from .run_inputs import prepare_run_inputs
                    protected=prepare_run_inputs(self.store,run['id'],principal,protected)
                except Exception as error:
                    # Allocation is durable. Preserve an inspectable original
                    # failure without launching a hidden background attempt.
                    self.store.set_run_state(run['id'],'halted',reason='run_input_preparation_failed')
                    self.store.append_record('run-input-preparation-failure',{
                        'id':'run-input-failure:'+uuid.uuid4().hex,'run_id':run['id'],
                        'account_id':principal.account_id,'workspace_id':run['workspace_id'],
                        'intake_ref':normalized['intake_ref'],
                        'reason':getattr(error,'code',type(error).__name__)})
                    return await self.get(principal,run['id'])
            if self.evidence is not None:
                try:self.evidence.start(run['id'],protected)
                except Exception as error:
                    self.store.set_run_state(run['id'],'halted',reason='run_start_unavailable')
                    raise ResearchError('unavailable','Required protected run-start evidence could not be persisted') from error
            self._tasks[run['id']]=asyncio.create_task(self._execute(run['id'],copy.deepcopy(protected),
                submission_context=submission_context,principal=principal))
        return await self.get(principal,run['id'])

    async def _execute(self,run_id,protected,*,submission_context=None,principal=None):
        try:
            self.store.set_run_state(run_id,'running')
            finite_ref=protected.get('finite_e1_binding_ref')
            if finite_ref is not None:
                # A protected finite selection must never silently launch the
                # Compiler when its actual qualification/composition is absent.
                owner=self.finite_e1
                if owner is None or owner.binding_ref!=finite_ref or not callable(getattr(owner,'execute',None)):
                    raise ResearchError('unavailable','The protected finite qualification/execution owner is unavailable')
                value=owner.execute(run_id,protected,scheduler=self.scheduler)
                if inspect.isawaitable(value):await value
                return
            if self.compiler is None:raise ResearchError('unavailable','No protected compiler is initialized')
            result=self.compiler.run(run_id,protected) if hasattr(self.compiler,'run') else self.compiler(run_id,protected)
            if inspect.isawaitable(result):result=await result
            if not result or not result.get('accepted'):self.store.set_run_state(run_id,'halted',reason='compiler_did_not_release');return
            if self.scheduler is None:raise ResearchError('unavailable','No protected plan scheduler is initialized')
            value=self.scheduler.run(run_id,result['brief_ref'],protected)
            if inspect.isawaitable(value):value=await value
            if isinstance(value,dict) and value.get('linked_run_id'):
                linked=value['linked_run_id']
                from .planning import research_continuation
                if research_continuation(self.store,run_id)['continuation_run_id']!=linked:
                    raise ResearchError('integrity_fault','Scheduler continuation has no exact original planned allocation')
                if linked in self._tasks:raise ResearchError('identity_conflict','Linked compiler work already started')
                linked_protected=copy.deepcopy(protected)
                freeze_model = getattr(self, 'freeze_model_selection', None)
                if freeze_model is not None:
                    value = freeze_model(principal, linked, parent_run_id=run_id)
                    if inspect.isawaitable(value): await value
                if protected.get('finite_e1_binding_ref') is None and protected.get('profile_id') is None:
                    phase='run_input_preparation_failed'
                    try:
                        from .run_inputs import prepare_linked_run_inputs
                        linked_protected=prepare_linked_run_inputs(self.store,run_id,linked,protected,
                            principal=principal,base_protected=submission_context)
                        if self.evidence is not None:
                            phase='run_start_unavailable'
                            self.evidence.start(linked,linked_protected)
                    except Exception as error:
                        self.store.set_run_state(linked,'halted',reason=phase)
                        allocated=self.store.get_run(linked)
                        self.store.append_record('run-input-preparation-failure',{
                            'id':'run-input-failure:'+uuid.uuid4().hex,'run_id':linked,
                            'account_id':allocated['account_id'],'workspace_id':allocated['workspace_id'],
                            'intake_ref':allocated['submission']['intake_ref'],
                            'reason':getattr(error,'code',type(error).__name__)})
                        return
                self._tasks[linked]=asyncio.create_task(self._execute(linked,linked_protected,
                    submission_context=submission_context,principal=principal))
        except asyncio.CancelledError:
            self.store.append_record('execution-cancelled-pending',{'id':'cancel-pending:'+uuid.uuid4().hex,'run_id':run_id,
                'status':'containment_pending','uncertainty':'Local coordinator stopped; actual remote owner acknowledgments are still required'})
        except Exception as exc:
            code=exc.code if isinstance(exc,ResearchError) else type(exc).__name__
            self.store.append_record('escalation',{'id':'escalation:'+uuid.uuid4().hex,'run_id':run_id,'reason_code':code})
            self.store.set_run_state(run_id,'halted',reason=code)
        finally:
            if self.evidence is not None and not self.store.cancellation_requested(run_id):
                try:self.evidence.finish(run_id)
                except Exception as error:
                    self.store.append_record('escalation',{'id':'bundle-failure:'+uuid.uuid4().hex,'run_id':run_id,
                        'reason_code':'run_bundle_unavailable','failure_type':type(error).__name__})
                    self.store.set_run_state(run_id,'halted',reason='run_bundle_unavailable')
            self._tasks.pop(run_id,None)

    async def get(self,principal,run_id):
        # Internal submit may return status under its existing authenticated grant.
        if not ({'status','submit','reconcile'} & principal.operations):raise ResearchError('auth','Run status is outside this grant')
        run=self.store.get_run(run_id,account_id=principal.account_id);principal.require(next(op for op in ('status','submit','reconcile') if op in principal.operations),run['workspace_id'])
        records=list(self.store.iter_records(run_id=run_id));accepted=[];candidates=[];decision=None
        for envelope in records:
            value=envelope['record']
            if envelope['kind']=='gate-decision':
                decision=envelope['ref']
                if value['scope_kind']=='node' and value['action']=='advance':accepted.extend(value['accepted_refs'])
            if envelope['kind']=='invocation-observation':candidates.extend(value['output_refs'])
        accepted=[r for r in accepted if self.store.is_accepted(r,run_id=run_id)]
        candidates=[r for r in candidates if r not in accepted]
        states=self.store.node_states(run_id)
        lifecycle={'pending':'Pending','running':'Running','evaluating':'Evaluating','completed':'Completed','failed':'Failed','skipped':'Failed'}
        nodes=[{'node_id':n['node_id'],'attempt_id':n['attempt_id'],'lifecycle_status':lifecycle.get(n['state'],'Failed'),
                'skipped_because':n['reason'] if n['state']=='skipped' else None} for n in states]
        bundles=[envelope['ref'] for envelope in records if envelope['kind']=='run-bundle']
        from .status_stage import observed_stage
        stage=observed_stage(self.store,run,states,records)
        if stage is None:
            from .finite_status import selected_for_status
            stage='' if selected_for_status(self.store,run) else 'intention_compiler'
        result={'schema_version':'1.0.0','id':'status:'+run_id,'client_request_id':run['submission']['client_request_id'],'run_id':run_id,
                'revision':run['revision'],'stage':stage,
                'status':'in_progress' if run['state'] in {'pending','running'} else run['state'],
                'candidate_refs':candidates,'accepted_refs':accepted,'decision_ref':decision,
                'reasons':status_reasons(run,records),'bundle_ref':bundles[-1] if bundles else None,'node_statuses':nodes}
        validate('client-status',result);return result

    async def list(self,principal,*,client_request_id):
        principal.require('reconcile')
        return [await self.get(principal,r['id']) for r in self.store.list_runs(account_id=principal.account_id,request_id=client_request_id)]

    async def cancel(self,principal,run_id,request_id):
        principal.require('cancel');run=self.store.get_run(run_id,account_id=principal.account_id);principal.require('cancel',run['workspace_id'])
        record=self.store.request_cancellation(run_id,principal.account_id,request_id)
        if record['status']=='terminal':return record
        key=(run_id,request_id);pending=self._containments.get(key)
        if pending is None or pending.done() and record['status']!='terminal':
            pending=asyncio.create_task(self._contain_run(run_id,request_id));self._containments[key]=pending
        if record['status']!='terminal':await asyncio.shield(pending)
        return self.store.get_cancellation(run_id,request_id)

    async def _contain_run(self,run_id,request_id):
        task=self._tasks.get(run_id)
        if task is not None:task.cancel()
        async def contain(name,owner):
            try:
                method=getattr(owner,'contain_run',None)
                if method is None:raise ResearchError('containment_unavailable','Actual effect owner containment is unavailable')
                result=method(run_id,request_id)
                if inspect.isawaitable(result):result=await asyncio.wait_for(result,35)
                valid=isinstance(result,dict) and result.get('contained') is True and result.get('run_id')==run_id and result.get('request_id')==request_id
                return {'owner':name,'contained':valid,'reason':None if valid else 'No exact actual owner acknowledgment'}
            except Exception as exc:return {'owner':name,'contained':False,'reason':getattr(exc,'code',type(exc).__name__)}
        receipts=await asyncio.gather(contain('model',self.model),contain('executor',self.executor))
        if task is not None:await asyncio.gather(task,return_exceptions=True)
        confirmed=all(receipt['contained'] for receipt in receipts)
        self.store.append_record('execution-contained' if confirmed else 'containment-pending',{
            'id':'containment:'+uuid.uuid4().hex,'run_id':run_id,'request_id':request_id,'contained':confirmed,
            'owner_receipts':receipts,'preserved_effects':['Known or uncertain prior external effects and partial evidence are retained']})
        if confirmed:
            self.store.finish_cancellation(run_id,['Owned model and executor activity acknowledged contained; prior effects retained'])
            if self.evidence is not None:
                try:self.evidence.finish(run_id)
                except Exception as error:self.evidence.missing(run_id,'run-bundle','Contained run manifest persistence failed: '+type(error).__name__,blocking=True)

    async def artifact_bytes(self,principal,run_id,*,audience='researcher'):
        from .runner import _capture_off_loop
        return await _capture_off_loop(self._artifact_bytes,principal,run_id,audience=audience)

    def _artifact_bytes(self,principal,run_id,*,audience='researcher',include_contents=True):
        principal.require('export');run=self.store.get_run(run_id,account_id=principal.account_id);principal.require('export',run['workspace_id'])
        if audience not in principal.audiences or audience not in {'researcher','reviewer'}:raise ResearchError('auth','Audience is outside the authenticated grant')
        from .inspection import build_retrieval
        from .finite_evaluation import finite_evidence_refs
        from .run_evidence import RunEvidence
        native_evidence=RunEvidence(self.store,None)
        finite=finite_evidence_refs(self.store,run_id)
        public={'gate-decision','bound-check-plan','review-context','deterministic-check-result','verifier-assessment','invocation-observation','dispatch-record','dispatch-start','acceptance-commit','route-record','model-call','model-call-start','model-call-refused','plan-outcome','escalation','execution-contained','run-bundle','run-start','run-end','run-plan-binding','run-evidence-missing','run-evaluation-labels','fault-injection','fault-injection-outcome'}
        public|={'finite-e1-scope','classification-scoring-receipt'}
        files=[];refs=[];restricted={};delivery_files=[];records=list(self.store.iter_records(run_id=run_id))
        if finite is not None:
            for ref in finite['artifact_refs']:
                files.append({'path':'finite-originals/'+ref['sha256']+'/'+hashlib.sha256(ref['id'].encode()).hexdigest(),
                    'artifact_ref':ref,'media_type':self.store.artifact_metadata(ref)['media_type'],'audience':audience})
                refs.append(ref)
        media={(r['record']['artifact_ref']['id'],r['record']['artifact_ref']['sha256']):r['record']['media_type'] for r in records if r['kind']=='captured-output'}
        known={(r['ref']['id'],r['ref']['sha256']) for r in records};queue=list(records)
        def related(kind,ref):
            if ref is None or (ref['id'],ref['sha256']) in known:return
            value=self.store.read_record(ref,contract_id=kind);known.add((ref['id'],ref['sha256']))
            envelope={'kind':kind,'ref':ref,'record':value};records.append(envelope);queue.append(envelope)
        # Some canonical evidence contracts deliberately carry no run_id. Reach
        # them only through this owned run's exact protected references.
        while queue:
            envelope=queue.pop();value=envelope['record'];kind=envelope['kind']
            if kind=='gate-decision':
                related('node-execution-contract',value['node_contract_ref'])
                related('node-execution-contract' if value['scope_kind']=='node' else 'subnode-execution-contract',value['contract_ref'])
                for key,target in [('check_plan_ref','bound-check-plan'),('deterministic_result_ref','deterministic-check-result'),('assessment_ref','verifier-assessment')]:related(target,value.get(key))
                for reason in value.get('reasons',[]):
                    for ref in reason.get('evidence_refs',[]):
                        candidate=self.store.read_record(ref)
                        if 'check_plan_ref' in candidate and 'results' in candidate:related('deterministic-check-result',ref)
            elif kind=='deterministic-check-result':related('bound-check-plan',value['check_plan_ref'])
            elif kind=='verifier-assessment':related('review-context',value['review_context_ref'])
            elif kind in {'dispatch-record','dispatch-start'}:
                related('node-execution-contract',value.get('node_contract_ref'))
                related('run-plan',value.get('run_plan_ref'))
            elif kind=='run-plan-binding':related('run-plan',value.get('plan_ref'))
            elif kind=='subnode-execution-contract':related('node-execution-contract',value['node_contract_ref'])
            elif kind=='model-call-start':
                try:related('model-call',self.store.record_ref(value['call_id']))
                except ResearchError as exc:
                    if exc.code!='evidence_unavailable':raise
        # Only an externally committed Delivery manifest assigns file disclosure.
        # Its audience remains binding even when the same Ref appears in an
        # invocation's candidate inventory.
        from .workflow_inspection import accepted_paper_delivery_manifest
        paper = accepted_paper_delivery_manifest(self.store,run_id)
        for node in self.store.node_states(run_id):
            for ref in self.store.accepted_outputs(run_id,node['node_id']).values():
                try:value=self.store.read_record(ref)
                except (ResearchError,ValueError,UnicodeError):continue
                if isinstance(value,dict) and value.get('id')=='delivery_manifest':
                    if paper is not None and ref == paper['manifest_ref']:
                        validate('urn:ai4r:paper-delivery-manifest:1.0.0',value)
                    else:
                        validate('delivery-manifest',value)
                    for file in value['files']:
                        if not isinstance(file,dict) or not {'path','artifact_ref','media_type','audience'}.issubset(file):continue
                        key=(file['artifact_ref']['id'],file['artifact_ref']['sha256'])
                        if key in restricted and restricted[key]!=file['audience']:raise ResearchError('disclosure_conflict','One exact artifact has conflicting disclosure audiences')
                        restricted[key]=file['audience'];delivery_files.append({k:file[k] for k in ('path','artifact_ref','media_type','audience')})
        paths=set()
        for file in delivery_files:
            if file['path'] in paths:raise ResearchError('disclosure_conflict','Delivery lists a duplicate export path')
            paths.add(file['path']);files.append(file);refs.append(file['artifact_ref'])
        seen_outputs=set();export_files={file['path']:file for file in files}
        for envelope in records:
            if envelope['kind']=='run-evidence-file' and envelope['record']['role'] in {'output','run_end','node_gate','capsule','prompt','trace','workspace','gate','check','verifier'}:
                copied=envelope['record'];original=copied.get('source_ref');key=(original['id'],original['sha256']) if original else None
                if key in restricted and restricted[key]!=audience:continue
                ref=copied['artifact_ref'];path='records/'+ref['id']
                if path not in paths:
                    file={'path':path,'artifact_ref':ref,'media_type':copied['media_type'],'audience':audience}
                    paths.add(path);files.append(file);refs.append(ref);export_files[path]=file
                # Disclosure is resolved above before a native source index can
                # authorize any original event or packet. Projection is read-only.
                for projected in native_evidence.native_trace_export_files(run_id,copied):
                    original=projected['artifact_ref'];key=(original['id'],original['sha256'])
                    if key in restricted and restricted[key]!=audience:continue
                    path=projected['path'];prior=export_files.get(path)
                    if prior is not None:
                        if prior['artifact_ref']['sha256']!=projected['artifact_ref']['sha256']:
                            raise ResearchError('disclosure_conflict','Native export path names different original bytes')
                        continue
                    file={**projected,'audience':audience};paths.add(path);files.append(file)
                    refs.append(file['artifact_ref']);export_files[path]=file
            if envelope['kind'] not in public:continue
            ref=envelope['ref']
            # Descriptive paths depend only on the exact immutable identity.
            # Collection snapshots/receipts and genuinely late evidence must
            # not rename an already published record by shifting its ordinal.
            identity=hashlib.sha256(json_bytes(ref)).hexdigest()
            path=f'evidence/{envelope["kind"]}-{identity}.json'
            files.append({'path':path,'artifact_ref':ref,'media_type':'application/json','audience':audience})
            refs.append(ref)
            if envelope['kind']=='invocation-observation':
                for output in envelope['record']['output_refs']:
                    key=(output['id'],output['sha256'])
                    if key in restricted or key in seen_outputs:continue
                    seen_outputs.add(key);path='artifacts/'+output['sha256']
                    if path in paths:continue
                    paths.add(path);files.append({'path':path,'artifact_ref':output,'media_type':media.get(key,self.store.artifact_metadata(output)['media_type']),'audience':audience});refs.append(output)
        from .run_contracts import contract_export_files
        for file in contract_export_files(self.store,run,records,audience,restricted):
            if file['path'] in paths:raise ResearchError('disclosure_conflict','Contract export path is already assigned')
            files.append(file);refs.append(file['artifact_ref']);paths.add(file['path'])
        manifest,data=build_retrieval(self.store,principal,run_id,run['account_id'],audience,files,allowed_refs=refs,include_contents=include_contents)
        validate('client-retrieval',manifest);return manifest,data

    async def artifact(self,principal,run_id,*,audience='researcher'):
        manifest,_=await self.artifact_bytes(principal,run_id,audience=audience);return manifest

    async def upload(self,principal,kind,scope_id,filename,data):
        principal.require('upload',scope_id)
        if self.upload_manager is None:raise ResearchError('unavailable','Controlled uploads are not initialized')
        return await self.upload_manager.upload(principal,kind,scope_id,filename,data)
    def uploads(self,principal,scope_id):
        principal.require('list_uploads',scope_id)
        if self.upload_manager is None:raise ResearchError('unavailable','Controlled uploads are not initialized')
        return self.upload_manager.list(principal,scope_id)
    def delete_upload(self,principal,upload_id):
        principal.require('delete_upload')
        if self.upload_manager is None:raise ResearchError('unavailable','Controlled uploads are not initialized')
        return self.upload_manager.delete(principal,upload_id)
