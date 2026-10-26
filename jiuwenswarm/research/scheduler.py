"""Serial frozen-plan execution through native SwarmFlow and committed gates."""

from __future__ import annotations

import time
import asyncio
import copy
import uuid
from datetime import datetime,timezone

from .compiler import VerifierBindings,input_port
from .contracts import ResearchError
from .native import run_native_workflow
from .planning import selected_plan_source


def stamp():return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Scheduler:
    def __init__(self,store,runner,factory,binder,*,library,planning=None,progress_sink=None,evidence=None):
        self.store,self.runner,self.factory,self.binder=store,runner,factory,binder
        self.library,self.planning,self.progress_sink=library,planning,progress_sink
        self.evidence=evidence

    async def run(self,run_id,brief_ref,protected):
        run=self.store.get_run(run_id);submission=run['submission'];mode=selected_plan_source(submission)
        configuration=self.store.read_record(submission['configuration_ref'])
        operator=configuration.get('operator',configuration)
        # cc.* is read solely from the captured, validated operator record.
        from .operator_config import OperatorConfiguration
        approved=OperatorConfiguration.from_mapping(operator,resolve_profile=lambda ref:self.store.read_record(ref))
        settings=approved.snapshot()['cc']
        snapshot_ref=protected.get('library_snapshot_ref') or self.library.snapshot(candidate_pins=protected.get('candidate_pins',()))
        resources_ref=protected['resource_inventory_ref']
        source_ref=settings['static_template_ref'];acceptance_ref=None
        if mode=='planned':
            if self.planning is None:raise ResearchError('planner_unavailable','Native planned path is not initialized')
            proposed=await self.planning.run(run_id,brief_ref,snapshot_ref,resources_ref,settings['plan_policy_ref'],protected)
            if not proposed.get('accepted'):return proposed
            source_ref=proposed['proposal_ref'];acceptance_ref=proposed['decision_ref']
        try:
            plan_ref=self.binder.freeze(source_ref,brief_ref,snapshot_ref,resources_ref,settings['plan_policy_ref'],submission['configuration_ref'],
                plan_source=mode,acceptance_ref=acceptance_ref,run_inputs=protected.get('run_inputs',{}),authority_ceiling=protected.get('authority_ceiling'))
        except ResearchError as exc:
            if exc.code!='plan_infeasible' or not exc.details.get('check_result_ref'):raise
            from .planning import PlanOutcomeController
            checks=self.store.read_record(exc.details['check_result_ref'],contract_id='deterministic-check-result')
            reasons=[{'check_id':r['check_id'],'detail':r['reason'][:300]} for r in checks['results'] if r['outcome']!='PASS'][:20]
            outcome,linked=(self.planning.outcomes if self.planning else PlanOutcomeController(self.store)).record(run_id,plan_source=mode,brief_ref=brief_ref,
                trigger='proposal_rejected',reasons=reasons,source_ref=source_ref,check_result_ref=exc.details['check_result_ref'])
            return {'accepted':False,'outcome_ref':outcome,'linked_run_id':linked}
        return await self.execute_plan(run_id,plan_ref,protected)

    def _committed_node(self, run_id, node_id, plan):
        from .binding import committed_output_proof
        nodes = {node['node_id']: node for node in plan['nodes']}
        if node_id not in nodes:
            raise ResearchError('unaccepted_input', 'Producer is outside the frozen plan')
        node = nodes[node_id]
        proof = committed_output_proof(self.store, run_id, node_id)
        parents = []
        for _, gate in proof['gates']:
            ref = gate['node_contract_ref']
            parent = self.store.read_record(ref, contract_id='node-execution-contract')
            work = [item for item in parent['subnodes'] if item['role'] == 'work']
            if (parent['run_id'] != run_id or parent['node_id'] != node_id or parent['attempt_id'] != proof['receipt']['attempt_id']
                    or parent['configuration_ref'] != plan['configuration_ref'] or parent['policy_ref'] != plan['policy_ref']
                    or parent['template_ref'] != plan['source_ref'] or parent['node_limits'] != node['limits']
                    or len(work) != 1 or work[0]['subnode_id'] != node_id
                    or work[0]['capsule_ref']['sha256'] != node['cc']['declaration_sha256']):
                raise ResearchError('unaccepted_input', 'Committed producer contract differs from the frozen run/node')
            declaration = self.store.read_record(work[0]['capsule_ref'], contract_id='capsule-declaration')
            template = self.store.read_record(work[0]['template_ref'])
            if (declaration['identity']['name'] != node['cc']['cc_name']
                    or declaration['identity']['version_label'] != node['cc']['cc_version'] or template['cc'] != node['cc']):
                raise ResearchError('unaccepted_input', 'Committed producer has another selected declaration')
            parents.append((ref, parent))
        if len(parents) != 1:
            raise ResearchError('unaccepted_input', 'Node has no unique actual advancing parent contract')
        return dict(proof, parent_ref=parents[0][0], parent=parents[0][1])

    def _accepted_compiler_brief(self,run_id,plan):
        """Only this run's real externally committed Compiler Brief transfers."""
        from .binding import committed_output_proof
        from .contracts import contract_schema
        proof=committed_output_proof(self.store,run_id,'intention_compiler')
        if proof['outputs']!={'brief':plan['brief_ref']} or len(proof['gates'])!=1:
            raise ResearchError('unaccepted_input','Frozen Brief lacks its exact same-run Compiler commit')
        gate=proof['gates'][0][1];parent_ref=gate['node_contract_ref']
        parent=self.store.read_record(parent_ref,contract_id='node-execution-contract')
        run=self.store.get_run(run_id);brief=self.store.read_record(plan['brief_ref'],contract_id='research-brief')
        request=[item for item in parent['inputs'] if item['name']=='request']
        outputs=[item for item in parent['outputs'] if item['name']=='brief']
        if (self.store.record_kind(parent_ref)!='node-execution-contract' or gate['contract_ref']!=parent_ref
                or parent['run_id']!=run_id or parent['node_id']!='intention_compiler'
                or parent['attempt_id']!=proof['receipt']['attempt_id'] or parent['required_outputs']!=['brief']
                or parent['configuration_ref']!=plan['configuration_ref'] or parent['policy_ref']!=plan['policy_ref']
                or run['submission'].get('configuration_ref')!=plan['configuration_ref']
                or len(request)!=1 or request[0]['artifact_refs']!=[run['submission'].get('intake_ref')]
                or brief['intake_ref']!=run['submission'].get('intake_ref') or len(outputs)!=1
                or contract_schema(outputs[0]['contract_id'])!=contract_schema('research-brief')):
            raise ResearchError('unaccepted_input','Original Compiler Brief context/output/run provenance differs')
        intent=committed_output_proof(self.store,run_id,'intention_compiler',subnode_id='intent',parent_ref=parent_ref)
        if intent['outputs']!={'intent':brief['intent_ref']}:
            raise ResearchError('unaccepted_input','Compiler Brief names another internally committed Intent')
        self.store.read_record(brief['intake_ref'],contract_id='qualified-intake')
        return plan['brief_ref']

    def _derived_run_input(self,run_id,plan,node,port,ref,baseline):
        """Original protected Brief/scope derivation, never generic Ref access."""
        key=port.get('run_input_key')
        if key=='brief':
            return ref==self._accepted_compiler_brief(run_id,plan)
        if key!='search_scope':return False
        if (port['name']!='search_scope' or self.store.record_kind(ref)!='search-scope'
                or node not in plan['nodes'] or not plan['frozen']):
            raise ResearchError('input_authority','Search scope is not its exact indexed frozen node input')
        scope=self.store.read_record(ref,contract_id='search-scope')
        brief=self._accepted_compiler_brief(run_id,plan)
        bounds_ref=self.binder.search_bounds_ref
        if bounds_ref is None:raise ResearchError('input_authority','Original protected Search bounds are unavailable')
        bounds=self.store.read_record(bounds_ref)
        inventory=self.store.read_record(plan['resource_inventory_ref'],contract_id='resource-inventory')
        local=[item for item in inventory['resources'] if item['resource_key']=='local_document_buffer']
        documents=[]
        if 'local_documents' in scope['connectors']:
            if (len(local)!=1 or local[0]['available'] is not True or local[0]['kind'] not in {'file','dataset','repository'}
                    or local[0]['ref'] is None or local[0]['ref'] not in baseline):
                raise ResearchError('input_authority','Search local text is outside the original frozen inventory/read ceiling')
            buffer_ref=local[0]['ref'];self.store.read_blob(buffer_ref)
            try:kind=self.store.record_kind(buffer_ref)
            except ResearchError as error:
                if error.code!='evidence_unavailable':raise
                kind=None
            if kind=='local-document-buffer':
                from .run_inputs import local_document_refs
                actual_brief=self.store.read_record(brief,contract_id='research-brief')
                documents=local_document_refs(self.store,buffer_ref,inventory_ref=plan['resource_inventory_ref'],
                    intake_ref=actual_brief['intake_ref'],run_id=run_id)
                if not documents or any(ref not in baseline for ref in documents):
                    raise ResearchError('input_authority','Current run documents are empty or outside original reads')
            else:documents=[buffer_ref]
        source=self.store.read_record(plan['source_ref'],contract_id='static-template' if plan['plan_source']=='static' else 'plan-proposal')
        if (scope['brief_ref']!=brief or scope['local_document_refs']!=documents
                or bounds.get('schema')!='ai4r-search-bounds:1'
                or not isinstance(bounds.get('id'),str) or not bounds['id']
                or set(bounds)!={'schema','id','connectors','max_queries','max_hits_per_query'}
                or any(scope[name]!=bounds[name] for name in ('connectors','max_queries','max_hits_per_query'))
                or scope['topic_hints']!=([] if plan['plan_source']=='static' else source.get('topic_hints',[]))):
            raise ResearchError('input_authority','Original binder-created Search scope disagrees with frozen run inputs')
        return True

    @staticmethod
    def _ancestors(plan, predecessors):
        nodes = {node['node_id']: node for node in plan['nodes']}
        reached = set()
        pending = list(predecessors)
        while pending:
            key = pending.pop()
            if key not in nodes:
                raise ResearchError('unaccepted_input', 'Unknown frozen ancestor')
            if key not in reached:
                reached.add(key)
                pending.extend(nodes[key]['predecessors'])
        return reached

    def _host_ref(self,run_id,key,protected,predecessors,plan_ref,*,node=None):
        plan = self.store.read_record(plan_ref, contract_id='run-plan')
        if node is None or node not in plan['nodes']:
            raise ResearchError('host_record_unavailable', 'Host input has no exact frozen consumer node')
        if key=='run_configuration':
            if protected['configuration_ref'] != plan['configuration_ref']:
                raise ResearchError('host_record_unavailable', 'Prepared configuration differs from the frozen plan')
            return protected['configuration_ref']
        if key in {'screening_rubric','environment_lock'}:
            refs=protected.get('host_records',{})
            if key not in refs:raise ResearchError('host_record_unavailable','Protected host record is not initialized: '+key)
            ref = refs[key]
            if key == 'screening_rubric':
                row = self.library.get(node['cc']['cc_name'], node['cc']['cc_version'])
                if (node['cc']['cc_name'] != 'research.screening' or row['declaration_ref']['sha256'] != node['cc']['declaration_sha256']
                        or row['body_refs'].get('screening_rubric.json') != ref):
                    raise ResearchError('host_record_unavailable', 'Prepared rubric differs from selected admitted body')
                self.store.read_record(ref, contract_id='screening-rubric')
            else:
                inventory = self.store.read_record(plan['resource_inventory_ref'], contract_id='resource-inventory')
                matches = [item for item in inventory['resources'] if item['resource_key'] == key]
                if len(matches) != 1 or matches[0]['available'] is not True or matches[0]['ref'] != ref:
                    raise ResearchError('host_record_unavailable', 'Prepared lock differs from captured inventory')
                self.store.read_record(ref, contract_id='environment-lock')
            return ref
        ancestors = self._ancestors(plan, predecessors)
        proofs = {key: self._committed_node(run_id, key, plan) for key in plan['topological_order'] if key in ancestors}
        if key=='gate_decision_index':
            entries=[{'node_id':key,'gate_decision_ref':proofs[key]['gates'][0][0]} for key in plan['topological_order'] if key in proofs]
            return self.store.put_record('gate-decision-index',{'schema_version':'1.0.0','id':'gate_decision_index','run_plan_ref':plan_ref,'entries':entries},scope={'run_id':run_id})
        direct = {'screening_result': ('research.screening', 'screening_result'),
                  'execution_receipt': ('research.benchmark', 'execution_receipt'),
                  'provisioning_receipt': ('research.benchmark', 'provisioning_receipt')}
        if key in direct:
            producer, port = direct[key]
            matches = [proof['outputs'][port] for name, proof in proofs.items()
                       if next(item for item in plan['nodes'] if item['node_id'] == name)['cc']['cc_name'] == producer
                       and port in proof['outputs']]
            if len(matches) != 1:
                raise ResearchError('host_record_unavailable', 'Required host output has no exact accepted producer/port')
            return matches[0]
        if key == 'build_receipt':
            matches = []
            for name, proof in proofs.items():
                selected = next(item for item in plan['nodes'] if item['node_id'] == name)
                if selected['cc']['cc_name'] != 'research.builder':
                    continue
                producer_inputs = {port['name']: port['artifact_refs'][0] for port in proof['parent']['inputs']}
                for row in self.store.iter_records(run_id=run_id, kinds=('host-record-proposal',)):
                    offered = row['record']
                    if (offered.get('key') != key or offered.get('node_id') != name
                            or offered.get('attempt_id') != proof['receipt']['attempt_id'] or offered.get('subnode_id') != name):
                        continue
                    captures = [item['record'] for item in self.store.iter_records(run_id=run_id,kinds=('captured-output',))
                        if item['record']['node_id'] == name and item['record']['subnode_id'] == name
                        and item['record']['attempt_id'] == proof['receipt']['attempt_id']
                        and item['record']['invocation_id'] == offered.get('invocation_id')]
                    if (len(captures) != len(proof['outputs'])
                            or {item['output_port']:item['artifact_ref'] for item in captures} != proof['outputs']):
                        raise ResearchError('host_record_unavailable', 'Host proposal lacks its exact original invocation output capture')
                    observations = [observed['record'] for observed in self.store.iter_records(run_id=run_id,kinds=('invocation-observation',))
                        if observed['record']['node_contract_ref'] == proof['parent_ref'] and observed['record']['subnode_id'] == name
                        and observed['record']['attempt_id'] == proof['receipt']['attempt_id']
                        and observed['record']['outcome'] == 'success' and observed['record']['failure_reason_code'] is None
                        and set((ref['id'],ref['sha256']) for ref in observed['record']['output_refs']) == set((ref['id'],ref['sha256']) for ref in proof['outputs'].values())]
                    if len(observations) != 1:
                        raise ResearchError('host_record_unavailable', 'Host proposal has no exact accepted original producing observation')
                    observed = observations[0]
                    producing = self.store.read_record(observed['contract_ref'],contract_id='subnode-execution-contract')
                    starts = [item['record'] for item in self.store.iter_records(run_id=run_id,kinds=('model-call-start',))
                        if item['record'].get('contract_ref') == observed['contract_ref']
                        and item['record'].get('invocation_id') == offered.get('invocation_id')]
                    agent_builder = selected['cc']['cc_version'] in {'m1-14','m1-15','m1-16','m1-17','m1-18'}
                    loop_builder = (selected['cc']['cc_version'] == 'm1-13' and
                        self.store.read_record(producing['bindings'][0]['declaration_ref'])['identity']['carrier']['ref'] == 'builder_loop.py')
                    if (producing['node_contract_ref'] != proof['parent_ref'] or producing['subnode_id'] != name
                            or producing['bindings'][0]['role'] != 'work'
                            or producing['bindings'][0]['declaration_ref']['sha256'] != selected['cc']['declaration_sha256']
                            or not (1 <= len(starts) <= 20 if agent_builder else
                                    1 <= len(starts) <= 3 if loop_builder else len(starts) == 1)):
                        raise ResearchError('host_record_unavailable', 'Host proposal differs from the actual source/native producing attempt')
                    receipt_contract = ('urn:ai4r:prediction-build-receipt:4.0.0' if agent_builder else
                        'urn:ai4r:prediction-build-receipt:3.0.0' if loop_builder else 'urn:ai4r:prediction-build-receipt:2.0.0'
                        if selected['cc']['cc_version'] in {'m1-11', 'm1-12', 'm1-13'} else 'build-receipt')
                    receipt = self.store.read_record(offered['ref'], contract_id=receipt_contract)
                    if (receipt['manifest_ref'] != proof['outputs'].get('manifest') or receipt['archive_ref'] != proof['outputs'].get('bundle')
                            or receipt['blueprint_ref'] != producer_inputs.get('blueprint') or receipt['environment_ref'] != producer_inputs.get('lock')
                            or receipt['readiness'] != 'READY'
                            or (receipt['schema_version'] not in {'3.0.0', '4.0.0'} and (receipt['trial_executed'] or receipt['packages_installed']))
                            or (receipt['schema_version'] == '4.0.0' and (receipt['trial_executed'] is not True
                                or receipt['development_only'] is not True or receipt['model_call_count'] != len(starts)
                                or not 1 <= receipt['tool_operation_count'] <= 40 or not 0 <= receipt['execution_job_count'] <= 12))
                            or (receipt['schema_version'] == '3.0.0' and receipt['candidate_count'] != len(starts))):
                        raise ResearchError('host_record_unavailable', 'Host receipt differs from accepted manifest/bundle/input closure')
                    if receipt['schema_version'] == '4.0.0':
                        journal_ref = receipt['journal_ref']
                        if self.store.record_kind(journal_ref) != 'builder_agent_execution':
                            raise ResearchError('host_record_unavailable', 'Agent Builder receipt lacks its protected execution journal')
                        journal = self.store.read_record(journal_ref)
                        if (journal.get('schema') != 'ai4r-builder-agent-execution:1'
                                or journal.get('contract_ref') != observed['contract_ref']
                                or journal.get('invocation_id') != offered.get('invocation_id')
                                or journal.get('manifest_ref') != proof['outputs'].get('manifest')
                                or journal.get('archive_ref') != proof['outputs'].get('bundle')
                                or journal.get('snapshot_sha256') != receipt['workspace_sha256']
                                or journal.get('submitted_snapshot_sha256') != receipt['submitted_snapshot_sha256']):
                            raise ResearchError('host_record_unavailable', 'Agent Builder journal differs from its receipt and accepted artifacts')
                    matches.append(offered['ref'])
            if len(matches) == 1:
                return matches[0]
        raise ResearchError('host_record_unavailable','Required accepted typed host record is unavailable: '+key)


    async def execute_plan(self,run_id,plan_ref,protected):
        plan=self.store.read_record(plan_ref,contract_id='run-plan')
        if not plan['frozen']:raise ResearchError('unfrozen_plan','Dispatch requires the committed frozen graph')
        self.binder.validate_acceptance(plan)
        finite_owner=getattr(self.binder,'finite_e1',None)
        if finite_owner is not None and protected.get('finite_e1_binding_ref') is not None:
            finite_owner.validate_dispatch(run_id,plan,protected)
        if self.evidence is not None:self.evidence.bind_plan(run_id,plan_ref)
        nodes={node['node_id']:node for node in plan['nodes']};states={};started=time.monotonic()
        snapshot=self.store.read_record(plan['library_snapshot_ref'],contract_id='library-snapshot')
        entries={(e['cc_name'],e['cc_version'],e['declaration_sha256']):e for e in snapshot['entries']}
        for node in plan['nodes']:self.store.set_node_state(run_id,node['node_id'],'pending')
        async def dispatch(node_id):
            if finite_owner is not None and protected.get('finite_e1_binding_ref') is not None:
                finite_owner.validate_dispatch(run_id,plan,protected)
            if self.store.cancellation_requested(run_id):raise ResearchError('cancelled','No new dispatch after cancellation')
            if time.monotonic()-started>=plan['limits']['time_s']:raise ResearchError('budget_exhausted','Frozen run wall-clock limit exhausted')
            node=nodes[node_id]
            failures=[p for p in node['predecessors'] if states.get(p)!='accepted']
            if failures:
                states[node_id]='skipped';self.store.set_node_state(run_id,node_id,'skipped',reason=failures[0])
                return {'node_id':node_id,'outcome':'skipped'}
            entry=entries[tuple(node['cc'][k] for k in ('cc_name','cc_version','declaration_sha256'))]
            authority=protected.get('authority_ceiling')
            if authority is None:raise ResearchError('authority_unavailable','No protected run authority ceiling')
            authority=copy.deepcopy(authority)
            baseline=list(authority['resource_reads']);derived=[];bound=[]
            for port in node['inputs']:
                if port['source_kind']=='accepted_ref':
                    ref=port['accepted_ref']
                    if ref not in baseline:
                        if not self._derived_run_input(run_id,plan,node,port,ref,baseline):
                            raise ResearchError('input_authority','External accepted input exceeds the explicit protected base ceiling')
                        derived.append(ref)
                elif port['source_kind']=='future_output':
                    future=port['future']
                    producer=next((item for item in plan['nodes'] if item['node_id']==future['producer_node']),None)
                    if (producer is None or producer['node_id'] not in self._ancestors(plan,node['predecessors'])
                            or not any(item['name']==future['port'] and item['artifact_type']==future['artifact_type'] for item in producer['outputs'])):
                        raise ResearchError('unaccepted_input','Future edge is outside the exact frozen typed producer/dependency')
                    proof=self._committed_node(run_id,producer['node_id'],plan)
                    ref=proof['outputs'].get(future['port'])
                    if ref is None:raise ResearchError('unaccepted_input','Future port has no committed original output')
                    derived.append(ref)
                else:
                    key=port['run_input_key']
                    ref=self._host_ref(run_id,key,protected,node['predecessors'],plan_ref,node=node)
                    if key in {'run_configuration','screening_rubric','environment_lock'}:
                        if ref not in baseline:raise ResearchError('input_authority','Prepared host resource exceeds the explicit protected base ceiling')
                    else:derived.append(ref)
                own=next(p for p in entry['input_ports'] if p['name']==port['name'])
                bound.append(input_port(port['name'],own['schema_ref'],ref))
            for ref in derived:
                if ref not in authority['resource_reads']:authority['resource_reads'].append(ref)
            outputs=[{'name':p['name'],'contract_id':next(v['schema_ref'] for v in entry['output_ports'] if v['name']==p['name']),
                      'version':self.factory._version(next(v['schema_ref'] for v in entry['output_ports'] if v['name']==p['name'])),'required':p['required']} for p in node['outputs']]
            parent_ref=self.factory.prepare_parent(run_id,node_id,[{'subnode_id':node_id,'cc':node['cc'],'depends_on':[]}],inputs=bound,outputs=outputs,
                objective=node['objective'],requirement_ids=node['requirement_ids'] or node['deliverable_ids'],limits=node['limits'],policy_ref=plan['policy_ref'],
                configuration_ref=plan['configuration_ref'],template_ref=plan['source_ref'],authority_ceiling=authority)
            work_ref,check_plan_ref,bundle=self.factory.bind_subnode(parent_ref,node_id,bound,role='work')
            parent=self.store.read_record(parent_ref);assignments={self.store.read_record(s['template_ref'])['output_port']:s['subnode_id'] for s in parent['subnodes'] if s['role']=='verifier'}
            processing_began=stamp();processing_clock=time.monotonic()
            try:
                self.runner.prepare_node_check_plan(parent_ref)
                dispatch_scope={'run_id':run_id,'node_id':node_id,'node_contract_ref':parent_ref,'run_plan_ref':plan_ref,
                    'predecessors':list(node['predecessors']),
                    'predecessor_commits':self.store.predecessor_snapshot(run_id,node['predecessors']),
                    'bound_input_refs':[{'name':p['name'],'ref':ref} for p in bound for ref in p['artifact_refs']]}
                result=await self.runner.run(work_ref,check_plan_ref,bundle_id=bundle,
                    verifier_contract_refs=VerifierBindings(self.factory,parent_ref,work_ref,assignments),dispatch=dispatch_scope)
            except BaseException as error:
                timing=self.runner.dispatch_timing(parent_ref)
                began=timing['started_at'] if timing else processing_began
                clock=timing['started_monotonic_s'] if timing else processing_clock
                try:
                    self.runner.capture_start_failure(parent_ref,started_at=began,elapsed_s=time.monotonic()-clock,
                        error=error,phase='planned',run_plan_ref=plan_ref,cc=node['cc'],check_pins=node['check_pins'])
                except Exception as capture_error:
                    # Missing complete source closure stays explicit. No worker,
                    # plan, Gate or timestamp is invented to make it terminal.
                    self.store.append_record('dispatch-finalization-unavailable',{'id':'dispatch-unavailable:'+uuid.uuid4().hex,
                        'run_id':run_id,'node_id':node_id,'attempt_id':node_id+'-a1','node_contract_ref':parent_ref,
                        'reason':getattr(capture_error,'code',type(capture_error).__name__)})
                states[node_id]='failed'
                reason=getattr(error,'code',type(error).__name__)
                self.store.set_node_state(run_id,node_id,'failed',attempt_id=node_id+'-a1',reason=reason)
                if (isinstance(error,asyncio.CancelledError) or self.store.cancellation_requested(run_id)
                        or reason in {'integrity_fault','security_fault','AUDIT_UNAVAILABLE','CONTAINMENT_UNCERTAIN','protected_stop','run_budget_exhausted'}):
                    raise
                return {'node_id':node_id,'outcome':'failed'}
            timing=self.runner.dispatch_timing(parent_ref)
            if timing is None:raise ResearchError('integrity_fault','Completed worker has no actual Scheduler start boundary')
            began=timing['started_at'];clock=timing['started_monotonic_s']
            decision_ref=await self.runner.finalize_node(parent_ref,[result],dict(result.output_refs) if result.accepted else {})
            decision=self.store.read_record(decision_ref);accepted=decision['action']=='advance';states[node_id]='accepted' if accepted else 'rejected'
            observation=self.store.read_record(result.observation_ref)
            self.runner.capture_dispatch(parent_ref,decision_ref,[result],started_at=began,elapsed_s=time.monotonic()-clock,phase='planned',run_plan_ref=plan_ref,cc=node['cc'],check_pins=node['check_pins'])
            stop_ref=getattr(result,'protected_stop_ref',None)
            if stop_ref is not None:
                stopped=self.store.read_record(stop_ref)
                failed=self.store.read_record(stopped['failure_observation_ref'],contract_id='invocation-observation')
                if (self.store.record_kind(stop_ref)!='protected-invocation-stop'
                        or stopped.get('schema')!='ai4r-protected-invocation-stop:1' or stopped.get('run_id')!=run_id
                        or stopped.get('node_id')!=node_id or stopped.get('contract_ref')!=observation['contract_ref']
                        or stopped.get('worker_observation_ref')!=result.observation_ref
                        or any(failed[key]!=observation[key] for key in ('run_id','node_id','attempt_id','node_contract_ref'))
                        or stopped.get('reason_code') not in {'integrity_fault','security_fault','AUDIT_UNAVAILABLE','CONTAINMENT_UNCERTAIN','run_budget_exhausted'}):
                    raise ResearchError('protected_stop','Protected stop receipt does not join the exact completed invocation')
                raise ResearchError('protected_stop','An actual protected integrity/security/persistence/run-budget failure halts the whole run')
            if observation['failure_reason_code'] in {'integrity_fault','security_fault','AUDIT_UNAVAILABLE'}:
                raise ResearchError('protected_stop','A protected integrity/security/persistence fault halts the whole run')
            return {'node_id':node_id,'outcome':states[node_id],'decision_ref':decision_ref}
        try:
            await run_native_workflow(plan['topological_order'],dispatch,run_id=run_id,progress_sink=self.progress_sink)
        except BaseException:
            self.store.set_run_state(run_id,'halted',reason='protected_stop');raise
        terminal='completed' if all(value=='accepted' for value in states.values()) else 'partial'
        self.store.set_run_state(run_id,terminal)
        return {'status':terminal,'plan_ref':plan_ref,'node_states':states}
