"""Bounded native proposal generation, protected checking and outcome lineage."""

from __future__ import annotations


def capture_static_template(store,library,*,expected_ref=None):
    """Capture the authored installed release; never regenerate it at startup."""
    import hashlib
    import json
    from importlib.resources import files
    from .contracts import ResearchError,validate
    root=files('jiuwenswarm.research_assets')
    catalog=json.loads(root.joinpath('catalog.json').read_text('utf-8'))
    entry=catalog.get('static_template')
    if not isinstance(entry,dict) or entry.get('interface_revision')!='M1-IF-002@r2':
        raise ResearchError('static_template_pin','No current authored static release is installed')
    raw=root.joinpath(entry['path']).read_bytes()
    if hashlib.sha256(raw).hexdigest()!=entry['sha256']:
        raise ResearchError('static_template_pin','Installed static template differs from its frozen release pin')
    value=json.loads(raw.decode('utf-8'));validate('static-template',value)
    snapshot=store.read_record(library.snapshot(),contract_id='library-snapshot')
    entries={(e['cc_name'],e['cc_version'],e['declaration_sha256']):e for e in snapshot['entries']}
    for node in value['nodes']:
        pin=node['cc'];chosen=entries.get(tuple(pin[k] for k in ('cc_name','cc_version','declaration_sha256')))
        if chosen is None or any(node['limits'][k]>chosen['max_limits'][k] for k in ('time_s','model_calls','memory_mb')):
            raise ResearchError('static_template_pin','Authored static node lacks its exact eligible aggregate library allowance')
    required={'time_s':sum(n['limits']['time_s'] for n in value['nodes']),
              'model_calls':sum(n['limits']['model_calls'] for n in value['nodes']),
              'memory_mb':max(n['limits']['memory_mb'] for n in value['nodes'])}
    if any(required[k]>value['limits'][k] for k in required):raise ResearchError('static_template_pin','Authored aggregate exceeds unchanged overall static limits')
    ref=store.put_blob(raw,media_type='application/json')
    if expected_ref is not None and expected_ref!=ref:
        raise ResearchError('static_template_pin','Approved configuration names another static template; explicitly capture the current release',{'current_static_template_ref':ref})
    return ref

import json
import uuid
import time

from .binding import plan_checks
from .contracts import ResearchError,validate
from .state import json_bytes


def selected_plan_source(submission):
    value=submission.get('plan_source','static')
    if value not in {'static','planned'}:raise ResearchError('validation','Unknown preselected plan source')
    return value


def research_continuation(store, run_id):
    """Read the existing source-authorized replan allocation; never start work.

    The authenticated caller must first own ``run_id`` and its workspace. A
    proposed ID or a copied outcome is insufficient: the original allocation,
    accepted Compiler Brief and exact one-hop clone must all agree. A genuine
    child whose preparation failed is still returned so its failure stays
    visible to the person waiting in chat.
    """
    from .binding import committed_output_proof
    from .restart_recovery import _original, _ownership
    from .state import SQLiteRunStore
    import hashlib

    if type(store) is not SQLiteRunStore:
        raise ResearchError('continuation_unavailable', 'Continuation requires the original protected run store')

    def require(condition, message):
        if not condition:
            raise ResearchError('integrity_fault', message)

    result = {'schema': 'ai4r-workflow-continuation:1', 'run_id': run_id,
              'continuation_run_id': None, 'outcome_ref': None,
              'attempt_depth': None, 'max_attempt_depth': 2}
    with store._lock:
        db = store.connection
        original = store.get_run(run_id)
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_lineage'").fetchone() is None:
            return result
        lineage = db.execute('SELECT * FROM plan_lineage WHERE run_id=?', (run_id,)).fetchone()
        if lineage is None:
            return result
        require(lineage['depth'] in (1, 2), 'Continuation depth exceeds the source two-attempt ceiling')
        result['attempt_depth'] = lineage['depth']
        child_id = lineage['linked_run_id']
        if child_id is None:
            return result
        require(lineage['depth'] == 1 and lineage['root_run_id'] == run_id and child_id != run_id,
                'Continuation is not the original one-hop planned allocation')
        child_lineage = db.execute('SELECT * FROM plan_lineage WHERE run_id=?', (child_id,)).fetchone()
        parents = db.execute('SELECT run_id FROM plan_lineage WHERE linked_run_id=?', (child_id,)).fetchall()
        require(child_lineage is not None and len(parents) == 1 and parents[0]['run_id'] == run_id
                and child_lineage['root_run_id'] == run_id and child_lineage['depth'] == 2
                and child_lineage['linked_run_id'] is None,
                'Continuation has an ambiguous parent, root or attempt budget')
        child = store.get_run(child_id, account_id=original['account_id'])
        require(child['workspace_id'] == original['workspace_id']
                and original['submission'].get('plan_source') == child['submission'].get('plan_source') == 'planned'
                and original['submission'].get('profile_id') is None and child['submission'].get('profile_id') is None,
                'Continuation changed its account, workspace or selected product mode')
        require(db.execute("SELECT 1 FROM records WHERE run_id IN (?,?) AND kind IN "
                "('finite-e1-run-selection','finite-e1-plan-binding','evaluation-run-binding') LIMIT 1",
                (run_id, child_id)).fetchone() is None, 'Private evaluation cannot become an ordinary chat continuation')
        outcomes = list(store.iter_records(run_id=run_id, kinds=('plan-outcome',)))
        require(len(outcomes) == 1, 'Continuation lacks its unique original plan outcome')
        outcome_ref = outcomes[0]['ref']
        outcome, outcome_order = _original(store, db, outcome_ref, 'plan-outcome', contract='plan-outcome')
        require(outcome['id'] == outcome_ref['id'] and outcome['outcome'] == 'plan_infeasible'
                and outcome['attempt_depth'] == 1 and outcome['linked_attempt_id'] == child_id
                and outcome['next_stage'] == 'intention_compiler',
                'Continuation outcome does not name the exact next Compiler attempt')
        _ownership(store, db, original, outcome_order, allow_linked=False)
        governing = committed_output_proof(store, run_id, 'intention_compiler')
        require(governing['outputs'] == {'brief': outcome['brief_ref']} and len(governing['gates']) == 1,
                'Continuation does not retain the original accepted Compiler Brief')
        brief = store.read_record(outcome['brief_ref'], contract_id='research-brief')
        require(brief['intake_ref'] == original['submission']['intake_ref'],
                'Continuation governing Brief names another original intake')
        compiler = store.read_record(governing['gates'][0][1]['node_contract_ref'], contract_id='node-execution-contract')
        require(compiler['run_id'] == run_id and compiler['node_id'] == 'intention_compiler'
                and compiler['configuration_ref'] == original['submission']['configuration_ref']
                and compiler['required_outputs'] == ['brief'],
                'Continuation Compiler release belongs to another original configuration')
        original_intake_ref = original['submission']['intake_ref']
        child_intake_ref = child['submission']['intake_ref']
        original_intake, _ = _original(store, db, original_intake_ref, 'qualified-intake', contract='qualified-intake')
        child_intake, intake_order = _original(store, db, child_intake_ref, 'qualified-intake', contract='qualified-intake')
        require(outcome_order < intake_order and child_intake_ref != original_intake_ref
                and child_intake['id'] == child_intake_ref['id'] and child_intake['id'] != original_intake['id']
                and child['submission']['id'] != original['submission']['id']
                and child['submission']['client_request_id'] != original['submission']['client_request_id'],
                'Continuation reused an original request or intake identity')
        expected_intake = dict(original_intake, id=child_intake['id'], prior_plan_outcome_ref=outcome_ref)
        expected_submission = dict(original['submission'], id=child['submission']['id'],
            client_request_id=child['submission']['client_request_id'], intake_ref=child_intake_ref)
        validate('client-submission', child['submission'])
        require(store.read_blob(child_intake_ref) == json_bytes(expected_intake)
                and child['submission'] == expected_submission,
                'Continuation changed original request, resources, configuration, policy or limits')
        for ref, expected_run in ((outcome_ref, run_id), (child_intake_ref, child_id)):
            metadata = db.execute('SELECT r.run_id,r.node_id,r.attempt_id,r.captured_at,a.captured_at AS artifact_captured_at '
                'FROM records r JOIN artifacts a ON a.id=r.id WHERE r.id=?', (ref['id'],)).fetchone()
            require(metadata is not None and metadata['run_id'] == expected_run
                    and metadata['node_id'] is None and metadata['attempt_id'] is None
                    and metadata['captured_at'] == metadata['artifact_captured_at'] == child['created_at'],
                    'Continuation did not originate in the original protected allocation transaction')
        requests = db.execute('SELECT * FROM requests WHERE run_id=?', (child_id,)).fetchall()
        require(len(requests) == 1 and requests[0]['account_id'] == original['account_id']
                and requests[0]['request_id'] == child['submission']['client_request_id']
                and requests[0]['fingerprint'] == hashlib.sha256(json_bytes(expected_submission)).hexdigest(),
                'Continuation lacks its exact idempotent allocated request')
        expected_uploads = {store.read_record(ref, contract_id='client-upload')['id'] for ref in original_intake['upload_refs']}
        for current in (run_id, child_id):
            used = {row['upload_id'] for row in db.execute('SELECT upload_id FROM upload_uses WHERE run_id=?', (current,)).fetchall()}
            require(used == expected_uploads, 'Continuation changed the originally retained uploaded documents')
        result.update(continuation_run_id=child_id, outcome_ref=outcome_ref)
        return result


def parse_planner_reply(text):
    if not isinstance(text,str):raise ResearchError('planner_output_invalid','Planner reply is not text')
    if text.startswith('INFEASIBLE:'):
        if '\n' in text or '\r' in text or len(text)>300 or not text[len('INFEASIBLE:'):].strip():
            raise ResearchError('planner_output_invalid','Infeasibility must be one nonempty line at most300 characters')
        return 'infeasible',text
    try:value=json.loads(text,parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    except ValueError as exc:raise ResearchError('planner_output_invalid','Planner returned neither a proposal nor a bounded infeasibility') from exc
    validate('plan-proposal',value);return 'proposal',value


def planner_checks(ctx,inputs,outputs):
    refs={'brief_ref':ctx.input_ref('brief'),'library_snapshot_ref':ctx.input_ref('library_snapshot'),
          'resource_inventory_ref':ctx.input_ref('resource_inventory'),'policy_ref':ctx.input_ref('plan_policy')}
    _,results=plan_checks(outputs['plan_proposal'],inputs['brief'],inputs['library_snapshot'],inputs['resource_inventory'],inputs['plan_policy'],
                         plan_source='planned',expected_refs=refs,check_exists=ctx.store.check_exists if hasattr(ctx.store,'check_exists') else lambda key:False)
    if 'capsule_contracts' in inputs:
        from .planner_catalog import verify_captured_catalog
        try:
            verify_captured_catalog(ctx.store, inputs['capsule_contracts'], inputs['library_snapshot'], refs['library_snapshot_ref'])
        except ResearchError as error:
            for result in results:
                if result['check_id'] == 'library_membership':
                    result.update(outcome='FAIL', reason=str(error))
    # Source proposal port is named proposal in some admitted declarations. The
    # carrier registration binds one exact name; no fallback schema is guessed.
    return results


class PlanOutcomeController:
    def __init__(self,store):
        self.store=store
        with store.transaction() as db:
            db.execute('CREATE TABLE IF NOT EXISTS plan_lineage (run_id TEXT PRIMARY KEY, root_run_id TEXT NOT NULL, depth INTEGER NOT NULL, linked_run_id TEXT)')

    def record(self,run_id,*,plan_source,brief_ref,trigger,reasons,source_ref=None,check_result_ref=None,gate_decision_ref=None):
        if trigger not in {'proposal_rejected','plan_rejected','planner_reported_infeasible'}:
            raise ResearchError('plan_outcome_invalid','Runtime/model/budget failures are not plan infeasibility')
        if not reasons or len(reasons)>20:raise ResearchError('plan_outcome_invalid','Infeasibility needs bounded actual reasons')
        if not self.store.is_accepted(brief_ref,run_id=run_id):raise ResearchError('unaccepted_input','Plan outcome requires the accepted governing Brief')
        if trigger=='planner_reported_infeasible':
            if source_ref is not None or check_result_ref is not None or gate_decision_ref is not None:raise ResearchError('plan_outcome_invalid','No proposal or checks exist for an infeasibility reply')
        elif source_ref is None or check_result_ref is None:raise ResearchError('plan_outcome_invalid','Actual rejection checks must be retained')
        original=self.store.get_run(run_id)
        if original['state'] not in {'pending','running'}:raise ResearchError('plan_outcome_already_recorded','A terminal run cannot start new linked work')
        with self.store._lock:
            row=self.store.connection.execute('SELECT * FROM plan_lineage WHERE run_id=?',(run_id,)).fetchone()
        root=row['root_run_id'] if row else run_id;depth=row['depth'] if row else 1
        if row and row['linked_run_id'] is not None:raise ResearchError('plan_outcome_already_recorded','This outcome already linked new work')
        linked='run:'+uuid.uuid4().hex if plan_source=='planned' and depth<2 else None
        record={'schema_version':'1.0.0','id':'plan_outcome_'+uuid.uuid4().hex,'outcome':'plan_infeasible','trigger':trigger,
                'brief_ref':brief_ref,'source_ref':source_ref,'check_result_ref':check_result_ref,'gate_decision_ref':gate_decision_ref,
                'reasons':reasons,'attempt_depth':depth,'next_stage':'intention_compiler','linked_attempt_id':linked}
        validate('plan-outcome',record)
        outcome_bytes=json_bytes(record);outcome_digest=self.store.blobs.put(outcome_bytes);ref={'id':record['id'],'sha256':outcome_digest}
        intake=None;submission=None;intake_ref=None
        if linked:
            intake=self.store.read_record(original['submission']['intake_ref'],contract_id='qualified-intake')
            intake=dict(intake,id='intake:'+uuid.uuid4().hex,prior_plan_outcome_ref=ref)
            validate('qualified-intake',intake);digest=self.store.blobs.put(json_bytes(intake));intake_ref={'id':intake['id'],'sha256':digest}
            submission=dict(original['submission'],id='submission:'+uuid.uuid4().hex,client_request_id='linked:'+uuid.uuid4().hex,intake_ref=intake_ref)
            validate('client-submission',submission)
        from .state import utc_now
        now=utc_now()
        with self.store.transaction() as db:
            current=db.execute('SELECT state FROM runs WHERE id=?',(run_id,)).fetchone()
            if not current or current['state'] not in {'pending','running'}:raise ResearchError('plan_outcome_already_recorded','A terminal run cannot create another outcome')
            row=db.execute('SELECT * FROM plan_lineage WHERE run_id=?',(run_id,)).fetchone()
            if row and row['linked_run_id'] is not None:raise ResearchError('plan_outcome_already_recorded','This outcome already linked new work')
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],ref['sha256'],'application/json',None,now))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'plan-outcome',run_id,None,None,now))
            db.execute('INSERT INTO plan_lineage VALUES(?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET linked_run_id=excluded.linked_run_id', (run_id,root,depth,linked))
            if linked:
                db.execute('INSERT INTO plan_lineage VALUES(?,?,?,NULL)',(linked,root,depth+1))
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(intake_ref['id'],intake_ref['sha256'],'application/json',None,now))
                db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(intake_ref['id'],'qualified-intake',linked,None,None,now))
                db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?,?,?,?)',(linked,original['account_id'],original['workspace_id'],'pending',1,json_bytes(submission).decode(),now,now,None))
                db.execute('INSERT INTO requests VALUES(?,?,?,?)',(original['account_id'],submission['client_request_id'],__import__('hashlib').sha256(json_bytes(submission)).hexdigest(),linked))
                db.execute('INSERT INTO upload_uses SELECT ?,upload_id FROM upload_uses WHERE run_id=?',(linked,run_id))
            db.execute("UPDATE runs SET state='halted',reason='plan_infeasible',revision=revision+1,updated_at=? WHERE id=?",(now,run_id))
        if linked is None:self.store.append_record('escalation',{'id':'escalation:'+uuid.uuid4().hex,'run_id':run_id,'reason_code':'plan_infeasible',
            'outcome_ref':ref,'detail':'Static source rejected' if plan_source=='static' else 'The two-attempt planned limit is exhausted'})
        return ref,linked


class PlanningCoordinator:
    def __init__(self,store,runner,factory,*,planner_pin,template_ref,node_limits,authority_ceiling,outcomes=None):
        self.store,self.runner,self.factory=store,runner,factory
        self.planner_pin,self.template_ref,self.node_limits,self.authority=planner_pin,template_ref,node_limits,authority_ceiling
        self.outcomes=outcomes or PlanOutcomeController(store)

    async def run(self,run_id,brief_ref,snapshot_ref,resources_ref,policy_ref,protected):
        from .compiler import input_port,VerifierBindings
        if not self.store.is_accepted(brief_ref,run_id=run_id):raise ResearchError('unaccepted_input','Planner requires the externally committed Brief')
        refs={'brief':brief_ref,'library_snapshot':snapshot_ref,'resource_inventory':resources_ref,'plan_policy':policy_ref}
        contracts={'brief':'research-brief','library_snapshot':'library-snapshot','resource_inventory':'resource-inventory','plan_policy':'plan-policy'}
        declaration = self.factory._entry(self.planner_pin)[1]
        if any(port['name'] == 'capsule_contracts' for port in declaration['ports']['inputs']):
            from .planner_catalog import capture_catalog, SCHEMA
            refs['capsule_contracts'] = capture_catalog(self.store, self.factory.library, snapshot_ref)
            contracts['capsule_contracts'] = SCHEMA
        ports=[input_port(key,contracts[key],ref) for key,ref in refs.items()]
        parent_ref=self.factory.prepare_parent(run_id,'planner',[{'subnode_id':'planner','cc':self.planner_pin,'depends_on':[]}],inputs=ports,
            outputs=[{'name':'plan_proposal','contract_id':'plan-proposal:field-contract:3','version':'3.0.0','required':True}],
            objective='Propose a bounded data-only graph covering the accepted Research Brief',requirement_ids=['planned_graph'],limits=self.node_limits,
            policy_ref=policy_ref,configuration_ref=protected['configuration_ref'],template_ref=self.template_ref,
            authority_ceiling=dict(self.authority,resource_reads=list(refs.values())))
        cref,pref,bundle=self.factory.bind_subnode(parent_ref,'planner',ports,role='work')
        self.store.set_node_state(run_id,'planner','pending',attempt_id='planner-a1')
        self.runner.prepare_node_check_plan(parent_ref)
        dispatch_scope={'run_id':run_id,'node_id':'planner','node_contract_ref':parent_ref,'run_plan_ref':None,
            'predecessors':['intention_compiler'],
            'predecessor_commits':self.store.predecessor_snapshot(run_id,['intention_compiler']),
            'bound_input_refs':[{'name':p['name'],'ref':ref} for p in ports for ref in p['artifact_refs']]}
        from .state import utc_now
        processing_began=utc_now();processing_clock=time.monotonic();pins=self.factory._entry(self.planner_pin)[2]['check_pins']
        try:
            result=await self.runner.run(cref,pref,bundle_id=bundle,
                verifier_contract_refs=VerifierBindings(self.factory,parent_ref,cref,{'plan_proposal':'planner.verifier'}),dispatch=dispatch_scope)
        except BaseException as error:
            timing=self.runner.dispatch_timing(parent_ref)
            self.runner.capture_start_failure(parent_ref,started_at=timing['started_at'] if timing else processing_began,
                elapsed_s=time.monotonic()-(timing['started_monotonic_s'] if timing else processing_clock),
                error=error,phase='pre_plan',cc=self.planner_pin,check_pins=pins)
            self.store.set_node_state(run_id,'planner','failed',attempt_id='planner-a1',reason=getattr(error,'code',type(error).__name__))
            raise
        timing=self.runner.dispatch_timing(parent_ref)
        if timing is None:raise ResearchError('integrity_fault','Planner work has no actual start boundary')
        began=timing['started_at'];clock=timing['started_monotonic_s']
        decision=await self.runner.finalize_node(parent_ref,[result],dict(result.output_refs) if result.accepted else {})
        self.runner.capture_dispatch(parent_ref,decision,[result],started_at=began,elapsed_s=time.monotonic()-clock,phase='pre_plan',cc=self.planner_pin,check_pins=pins)
        if result.accepted:
            if self.store.read_record(decision)['action']=='advance':return {'accepted':True,'proposal_ref':result.output_refs['plan_proposal'],'decision_ref':decision}
        observation=self.store.read_record(result.observation_ref)
        reason=observation['failure_reason_code']
        if reason=='planner_reported_infeasible':
            proposals=[r['record'] for r in self.store.iter_records(run_id=run_id,kinds=('host-record-proposal',)) if r['record']['key']=='planner_infeasible' and r['record']['node_id']=='planner']
            if not proposals:raise ResearchError('integrity_fault','Planner infeasibility text was not captured')
            _,text=parse_planner_reply(self.store.read_blob(proposals[-1]['ref']).decode('utf-8'))
            outcome,linked=self.outcomes.record(run_id,plan_source='planned',brief_ref=brief_ref,trigger='planner_reported_infeasible',reasons=[{'check_id':None,'detail':text}])
            return {'accepted':False,'outcome_ref':outcome,'linked_run_id':linked}
        if reason is not None:
            self.store.set_run_state(run_id,'halted',reason=reason)
            return {'accepted':False,'failure_reason':reason}
        checks=self.store.read_record(result.deterministic_ref)['results']
        failing=[r for r in checks if r['outcome']!='PASS']
        trigger='proposal_rejected' if failing else 'plan_rejected'
        reasons=[{'check_id':r['check_id'],'detail':r['reason'][:300]} for r in failing][:20] or [{'check_id':None,'detail':'Pinned semantic review did not advance'}]
        source_ref=result.output_refs.get('plan_proposal')
        if source_ref is None:raise ResearchError('planner_failed','No proposal exists for a proposal rejection')
        outcome,linked=self.outcomes.record(run_id,plan_source='planned',brief_ref=brief_ref,trigger=trigger,reasons=reasons,
            source_ref=source_ref,check_result_ref=result.deterministic_ref,gate_decision_ref=result.decision_refs[0] if trigger=='plan_rejected' else None)
        return {'accepted':False,'outcome_ref':outcome,'linked_run_id':linked}
