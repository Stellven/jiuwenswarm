"""One protected validator/binder for static and planned research graphs."""

from __future__ import annotations

import copy
import json
import uuid
from pathlib import Path

from .contracts import ResearchError, validate
from .capability_planning import is_capability_policy, layout_issues as capability_layout_issues
from .summary_planning import (PAPER_CC_VERSION, PAPER_PLANNER_VERSION, PAPER_DELIVERY_CC, PAPER_PLANNER_CC, is_document_summary_policy,
                               summary_layout_issues, validate_summary_documents)
from .unified_planning import is_integrated_policy, is_paper_graph, integrated_layout_issues, paper_workflow_allowed, AI4R_POLICY_ID


HOST_KEYS={'screening_rubric','build_receipt','gate_decision_index','screening_result',
           'execution_receipt','provisioning_receipt','environment_lock','run_configuration'}
SHARED_CHECKS=('brief_coverage','library_membership','port_type_compatibility','dependency_closure',
               'acyclicity','delivery_leaf_coverage','mandatory_check_bundle_present',
               'effects_within_policy','resource_feasibility','budget_ceilings')


def kahn_order(nodes: list[dict]) -> list[str]:
    ids=[n['node_id'] for n in nodes]
    if len(ids)!=len(set(ids)):
        raise ResearchError('acyclicity','Duplicate node identity')
    remaining={n['node_id']:set(n['predecessors']) for n in nodes}
    if any(not deps.issubset(ids) or key in deps for key,deps in remaining.items()):
        raise ResearchError('acyclicity','Unknown or self predecessor')
    order=[]
    while remaining:
        ready=next((key for key in ids if key in remaining and not remaining[key]),None)
        if ready is None:
            raise ResearchError('acyclicity','The predecessor graph has a cycle')
        order.append(ready); del remaining[ready]
        for deps in remaining.values():
            deps.discard(ready)
    return order


def expand_selectors(source: dict, brief: dict) -> dict:
    result=copy.deepcopy(source)
    selectors={'all_mandatory_requirements':('requirement','mandatory_requirements'),
               'all_deliverables':('deliverable','deliverables'),
               'all_evidence_obligations':('evidence_obligation','evidence_obligations')}
    for node in result['nodes']:
        for key,selector in [('requirement_ids','all_mandatory_requirements'),('deliverable_ids','all_deliverables')]:
            if node[key]==[selector]:
                node[key]=[v['id'] for v in brief[selectors[selector][1]]]
    expanded=[]
    for entry in result['coverage']:
        if 'selector' in entry:
            if entry['selector'] not in selectors or 'item_id' in entry or 'item_kind' in entry:
                raise ResearchError('brief_coverage','Invalid static coverage selector')
            kind,field=selectors[entry['selector']]
            expanded.extend({'item_id':v['id'],'item_kind':kind,'node_ids':list(entry['node_ids'])} for v in brief[field])
        else:
            expanded.append(entry)
    result['coverage']=expanded
    return result


def plan_checks(source: dict, brief: dict, library: dict, resources: dict, policy: dict, *,
                plan_source: str, expected_refs=None, check_exists=lambda key:False,
                pin_exists=lambda pins:True, finite_context=None) -> tuple[dict,list[dict]]:
    """Run every source check; diagnostics do not partially freeze a graph."""
    structure='template_structure' if plan_source=='static' else 'plan_proposal_schema'
    checks={key:[] for key in (structure,*SHARED_CHECKS,*(() if plan_source=='static' else ('suggested_checks_known',)))}
    def fail(key,message):checks[key].append(message)
    paper_summary = False
    try:
        validate('static-template' if plan_source=='static' else 'plan-proposal',source)
        integrated = is_integrated_policy(policy)
        capability = is_capability_policy(policy) or (integrated and policy['id'] == AI4R_POLICY_ID)
        paper_summary = is_document_summary_policy(policy) or ((integrated or capability) and is_paper_graph(source))
        if finite_context is not None:
            from .finite_evaluation import _FinitePlanContext
            if type(finite_context) is not _FinitePlanContext:
                raise ResearchError('finite_e1_binding','Unknown finite plan context')
            finite_context.validate_payloads(source,brief,library,resources,policy)
        if source['plan_source']!=plan_source or len(source['nodes'])>policy['max_nodes']:
            fail(structure,'Plan source or node ceiling differs from protected selection')
        # Preparation and research share the run/node/attempt namespace. The
        # Compiler always ran; the Planner ran only for a planned source.
        occupied={'intention_compiler'}|({'planner'} if plan_source=='planned' else set())
        if any(node['node_id'] in occupied for node in source['nodes']):
            fail(structure,'Research node ID reuses an existing pre-plan node identity')
        if any(p.get('accepted_ref') is not None for n in source['nodes'] for p in n['inputs']):
            fail(structure,'Source cannot set accepted artifact identities')
        if plan_source=='planned' and expected_refs and any(source.get(k)!=v for k,v in expected_refs.items()):
            fail(structure,'Planner input references differ from the exact accepted inputs')
    except (ResearchError,KeyError,TypeError) as exc:
        fail(structure,str(exc))
    if checks[structure]:
        return copy.deepcopy(source),[{'check_id':key,'outcome':'FAIL','reason':'; '.join(checks[structure]) if key==structure else 'Not evaluated: invalid source structure','evidence_refs':[]} for key in checks]
    if policy['max_attempts_per_node']!=1:fail('budget_ceilings','M1 permits exactly one dispatch attempt per node')
    try:
        bound=expand_selectors(source,brief) if plan_source=='static' else copy.deepcopy(source)
        nodes=bound['nodes']; ids=[n['node_id'] for n in nodes]; by_id={n['node_id']:n for n in nodes}
        if len(set(ids))!=len(ids):fail(structure,'Duplicate node IDs')
        order=kahn_order(nodes)
    except (ResearchError,KeyError,TypeError) as exc:
        bound=copy.deepcopy(source);nodes=bound.get('nodes',[]);by_id={n.get('node_id'):n for n in nodes};order=[]
        fail('acyclicity',str(exc))
    entries={(e['cc_name'],e['cc_version'],e['declaration_sha256']):e for e in library['entries']}
    resource_map={r['resource_key']:r for r in resources['resources']}
    resolved={}
    for node in nodes:
        nid=node['node_id'];pin=node['cc']; key=tuple(pin.get(k) for k in ('cc_name','cc_version','declaration_sha256'))
        entry=entries.get(key)
        if not entry or not entry['selectable_by_planner']:
            fail('library_membership',f'{nid}: CC pin is not selectable');continue
        resolved[nid]=entry
        if not entry['check_pins'] or not pin_exists(entry['check_pins']):
            fail('mandatory_check_bundle_present',f'{nid}: missing exact bundle/profile association')
        if entry['effect_class'] not in policy['allowed_effect_classes'] or (entry['network_mode']!='none' and not policy['allow_network']):
            fail('effects_within_policy',f'{nid}: effect/network exceeds policy')
        for need in entry['resource_needs']:
            resource=resource_map.get(need['resource_key'])
            if not resource or not resource['available'] or (need['min_quantity'] is not None and (resource['quantity'] is None or resource['quantity']<need['min_quantity'])):
                fail('resource_feasibility',f'{nid}: unavailable resource {need["resource_key"]}')
        for dimension in ('time_s','model_calls','memory_mb'):
            if node['limits'][dimension]>entry['max_limits'][dimension]:fail('budget_ceilings',f'{nid}: {dimension} exceeds admission')
        for direction in ('inputs','outputs'):
            port_map={p['name']:p for p in entry['input_ports' if direction=='inputs' else 'output_ports']}
            ports=node[direction];names=[p['name'] for p in ports]
            if len(names)!=len(set(names)) or any(p['required'] and p['name'] not in names for p in port_map.values()):
                fail('port_type_compatibility',f'{nid}: missing/duplicate {direction}')
            for port in ports:
                own=port_map.get(port['name'])
                if not own or own['artifact_type']!=port['artifact_type'] or (own['required'] and not port['required']):
                    fail('port_type_compatibility',f'{nid}: incompatible {direction} {port["name"]}')
                if direction=='outputs':continue
                kind=port['source_kind'];future=port['future'];key=port['run_input_key']
                if kind=='accepted_ref':
                    allowed={'brief','search_scope',*resource_map}
                    if finite_context is not None:allowed.update(finite_context.input_refs())
                    if key not in allowed or future is not None:fail('dependency_closure',f'{nid}: unknown accepted input key')
                elif kind=='host_record':
                    if key not in HOST_KEYS or future is not None:fail('dependency_closure',f'{nid}: unknown host input key')
                    if key!=port['artifact_type']:fail('port_type_compatibility',f'{nid}: host record type differs')
                    producers={'build_receipt':'research.builder','screening_result':'research.screening','execution_receipt':'research.benchmark','provisioning_receipt':'research.benchmark'}
                    if key in producers and not any(p in by_id and by_id[p]['cc']['cc_name']==producers[key] for p in node['predecessors']):
                        fail('dependency_closure',f'{nid}: host receipt producer is not a predecessor')
                elif kind=='future_output':
                    if key is not None or not future or future['producer_node'] not in node['predecessors'] or future['producer_node'] not in by_id:
                        fail('dependency_closure',f'{nid}: future producer is not a predecessor');continue
                    producer=by_id[future['producer_node']]
                    produced=next((p for p in producer['outputs'] if p['name']==future['port']),None)
                    producer_entry=entries.get(tuple(producer['cc'].get(k) for k in ('cc_name','cc_version','declaration_sha256')))
                    library_port=next((p for p in producer_entry['output_ports'] if p['name']==future['port']),None) if producer_entry else None
                    if not produced:fail('dependency_closure',f'{nid}: missing future output')
                    if not produced or not library_port or not own or not (future['artifact_type']==produced['artifact_type']==port['artifact_type']) or library_port['schema_ref']!=own['schema_ref']:
                        fail('port_type_compatibility',f'{nid}: future port contract mismatch')
                else:fail('dependency_closure',f'{nid}: unsupported source kind')
        for suggested in node.get('suggested_checks',[]):
            if not check_exists(suggested):fail('suggested_checks_known',f'{nid}: ignored unknown extra check {suggested}')
    try:
        kinds={'requirement':'mandatory_requirements','deliverable':'deliverables','evidence_obligation':'evidence_obligations'}
        inventory={kind:{v['id'] for v in brief[field]} for kind,field in kinds.items()}
        coverage={}
        for entry in bound['coverage']:
            if 'selector' in entry or entry.get('item_kind') not in kinds or entry.get('item_id') not in inventory[entry['item_kind']]:
                fail('brief_coverage','Unknown or unexpanded coverage entry');continue
            key=(entry['item_kind'],entry['item_id'])
            if key in coverage or len(set(entry['node_ids']))!=len(entry['node_ids']) or not set(entry['node_ids']).issubset(by_id):fail('brief_coverage','Duplicate or unknown coverage nodes')
            coverage[key]=set(entry['node_ids'])
        for node in nodes:
            if not node['requirement_ids'] and not node['deliverable_ids']:fail('brief_coverage','Node lacks obligation tags')
            for kind,tag in [('requirement','requirement_ids'),('deliverable','deliverable_ids')]:
                if not set(node[tag]).issubset(inventory[kind]):fail('brief_coverage','Unknown Brief tag')
        for kind,tag in [('requirement','requirement_ids'),('deliverable','deliverable_ids')]:
            for item in inventory[kind]:
                expected={n['node_id'] for n in nodes if item in n[tag]}
                if not expected or coverage.get((kind,item))!=expected:fail('brief_coverage','Coverage is not the exact inverse of tags')
        if capability:
            for item in inventory['evidence_obligation']:
                if not coverage.get(('evidence_obligation', item)):
                    fail('brief_coverage', 'Every evidence obligation needs an explicit nonempty node assignment')
        depended={p for n in nodes for p in n['predecessors']}; leaves=[n for n in nodes if n['node_id'] not in depended]
        delivery_cc = PAPER_DELIVERY_CC if paper_summary else 'research.delivery'
        if len(leaves)!=1 or (not capability and leaves[0]['cc']['cc_name']!=delivery_cc) or not inventory['deliverable'].issubset(leaves[0]['deliverable_ids']):
            fail('delivery_leaf_coverage','Exactly one Delivery leaf must cover every deliverable')
        elif not paper_summary and not capability:
            ancestors=set();pending=list(leaves[0]['predecessors'])
            while pending:
                key=pending.pop()
                if key not in ancestors and key in by_id:ancestors.add(key);pending.extend(by_id[key]['predecessors'])
            if sum(by_id[key]['cc']['cc_name']=='research.evaluation' for key in ancestors)!=1:fail('delivery_leaf_coverage','Delivery needs exactly one Scientific Evaluation ancestor')
        if paper_summary:
            for issue in summary_layout_issues(bound):
                fail('delivery_leaf_coverage', issue)
        if capability:
            for issue in capability_layout_issues(bound):
                fail('delivery_leaf_coverage', issue)
        if integrated:
            for issue in integrated_layout_issues(bound, policy):
                fail('delivery_leaf_coverage', issue)
        for required in policy['required_stages']:
            if sum(n['cc']['cc_name']==required for n in nodes)!=1:fail('delivery_leaf_coverage','A required stage is missing or duplicated')
        for dimension in ('time_s','model_calls','memory_mb'):
            minimum=max((n['limits'][dimension] for n in nodes),default=0) if dimension=='memory_mb' else sum(n['limits'][dimension] for n in nodes)
            if not minimum<=source['limits'][dimension]<=policy['aggregate_limits'][dimension]:fail('budget_ceilings',f'Aggregate {dimension} is outside source/policy bounds')
    except (KeyError,TypeError,ValueError) as exc:
        fail(structure,'Malformed cross-field structure: '+str(exc))
    results=[{'check_id':key,'outcome':'PASS' if not issues or key=='suggested_checks_known' else 'FAIL',
              'reason':'; '.join(issues) if issues else 'Exact protected invariant satisfied','evidence_refs':[]} for key,issues in checks.items()]
    if finite_context is not None:
        from .finite_evaluation import FINITE_PLAN_CHECKS
        results=[finite_context.terminal_result(bound,brief) if row['check_id']=='delivery_leaf_coverage' else row for row in results]
        results.append({'check_id':'finite_fixture_qualification_v1','outcome':'PASS',
            'reason':'Exact original qualification and protected finite source/context revalidated',
            'evidence_refs':[finite_context.qualification_ref]})
        if [row['check_id'] for row in results]!=list(FINITE_PLAN_CHECKS):
            raise ResearchError('finite_e1_binding','Finite check population differs from its versioned rule')
    return bound,results


class Binder:
    def __init__(self,store,library,check_registry,*,search_bounds_ref=None,finite_e1=None):
        self.store,self.library,self.check_registry=store,library,check_registry
        self.search_bounds_ref=copy.deepcopy(search_bounds_ref)
        self.finite_e1=finite_e1
        if finite_e1 is not None:
            from .finite_evaluation import FiniteE1
            if type(finite_e1) is not FiniteE1 or finite_e1.store is not store or finite_e1.library is not library:
                raise ResearchError('finite_e1_binding','Binder requires the installed exact finite owner/store/Library')

    def build_search_scope(self,source,brief_ref,resources,authority,*,plan_source,resource_inventory_ref=None):
        if self.search_bounds_ref is None:raise ResearchError('plan_infeasible','Protected Search bounds are unavailable')
        bounds=self.store.read_record(self.search_bounds_ref)
        if (set(bounds)!={'schema','id','connectors','max_queries','max_hits_per_query'}
            or bounds['schema']!='ai4r-search-bounds:1' or not isinstance(bounds['id'],str) or not bounds['id']):
            raise ResearchError('plan_infeasible','Invalid protected Search bounds capture')
        connectors=bounds['connectors']
        if (not isinstance(connectors,list) or not 1<=len(connectors)<=3 or len(connectors)!=len(set(connectors))
            or not set(connectors)<={'local_documents','arxiv','semantic_scholar'}
            or type(bounds['max_queries']) is not int or not 1<=bounds['max_queries']<=8
            or type(bounds['max_hits_per_query']) is not int or not 1<=bounds['max_hits_per_query']<=5):
            raise ResearchError('plan_infeasible','Search bounds exceed the source connector/query/hit constraints')
        selected=[n for n in source['nodes'] if n['cc']['cc_name']=='research.search']
        if len(selected)!=1:raise ResearchError('plan_infeasible','Search scope requires one exact selected Search capsule')
        pin=selected[0]['cc'];row=self.library.get(pin['cc_name'],pin['cc_version'])
        if row['declaration_ref']['sha256']!=pin['declaration_sha256']:raise ResearchError('plan_infeasible','Search declaration differs from the selected pin')
        declaration=self.store.read_record(row['declaration_ref'],contract_id='capsule-declaration')
        if bounds['max_queries']*len(connectors)>declaration['budget']['per_call']['tool_calls']:
            raise ResearchError('plan_infeasible','Search bounds exceed the immutable worker tool-call allowance')
        if not isinstance(authority,dict) or 'deepsearch' not in authority.get('tools',[]):
            raise ResearchError('plan_infeasible','Protected Search tool authority is unavailable')
        for connector,host in [('arxiv','export.arxiv.org'),('semantic_scholar','api.semanticscholar.org')]:
            if connector in connectors and (authority.get('network')!='allowlist' or host not in authority.get('network_allowlist',[])
                or declaration['needs']['network']['mode']!='allowlist' or host not in declaration['needs']['network']['allowlist']):
                raise ResearchError('plan_infeasible','External connector is outside the exact effective network authority')
        documents=[]
        if 'local_documents' in connectors:
            matches=[r for r in resources['resources'] if r['resource_key']=='local_document_buffer' and r['available'] and r['ref'] is not None]
            if len(matches)!=1:raise ResearchError('plan_infeasible','Exact available local document buffer is missing')
            ref=matches[0]['ref']
            try:kind=self.store.record_kind(ref)
            except ResearchError as error:
                if error.code!='evidence_unavailable':raise
                kind=None
            if kind=='local-document-buffer':
                from .run_inputs import local_document_refs
                brief=self.store.read_record(brief_ref,contract_id='research-brief')
                if resource_inventory_ref is None:raise ResearchError('plan_infeasible','Original run document inventory pin is unavailable')
                documents=local_document_refs(self.store,ref,inventory_ref=resource_inventory_ref,intake_ref=brief['intake_ref'])
                if not documents or any(item not in authority['resource_reads'] for item in [ref,*documents]):
                    raise ResearchError('plan_infeasible','Current qualified local document buffer is empty or exceeds original reads')
            else:
                raw=self.store.read_blob(ref)
                try:raw.decode('utf-8',errors='strict')
                except UnicodeError as error:raise ResearchError('plan_infeasible','Local document buffer is not canonical UTF-8 text') from error
                if raw.startswith(b'%PDF-') or not raw.strip():raise ResearchError('plan_infeasible','Local document requires qualified text extraction')
                documents.append(ref)
        hints=[] if plan_source=='static' else source.get('topic_hints',[])
        if (not isinstance(hints,list) or len(hints)>5 or any(not isinstance(x,str) or not 3<=len(x)<=100 for x in hints)
            or len(hints)!=len(set(hints))):raise ResearchError('plan_infeasible','Planner topic hints violate the source bounds')
        value={'schema_version':'1.0.0','id':'search_scope','brief_ref':brief_ref,'connectors':copy.deepcopy(connectors),
            'max_queries':bounds['max_queries'],'max_hits_per_query':bounds['max_hits_per_query'],'local_document_refs':documents,'topic_hints':hints}
        return self.store.put_record('search-scope',value)

    def validate_acceptance(self,plan,*,finite_context=None):
        """Reconcile immutable source-specific proof before any dispatch."""
        source=plan['source_ref'];acceptance=self.store.read_record(plan['acceptance_ref'])
        expected=['template_structure',*SHARED_CHECKS] if plan['plan_source']=='static' else ['plan_proposal_schema',*SHARED_CHECKS,'suggested_checks_known']
        if plan['plan_source']=='static':
            validate('deterministic-check-result',acceptance);checked=acceptance
        else:
            validate('gate-decision',acceptance)
            if acceptance['action']!='advance' or source not in acceptance['accepted_refs'] or not self.store.is_accepted(source):
                raise ResearchError('plan_acceptance','Planned source lacks exact committed advancing acceptance')
            checked=self.store.read_record(acceptance['deterministic_result_ref'],contract_id='deterministic-check-result')
            links=[r['record'] for r in self.store.iter_records(kinds=('plan-acceptance-binding',)) if r['record']['acceptance_ref']==plan['acceptance_ref']]
            if len(links)!=1 or links[0]['source_ref']!=source:
                raise ResearchError('plan_acceptance','No unique protected combined plan-gate provenance')
            original=self.store.read_record(links[0]['planner_gate_ref'],contract_id='gate-decision')
            if original['action']!='advance' or original['assessment_ref']!=acceptance['assessment_ref'] or original['contract_ref']!=acceptance['contract_ref'] or source not in original['accepted_refs']:
                raise ResearchError('plan_acceptance','Combined plan gate changed the original Planner review')
            self._planner_review(original,source,plan['library_snapshot_ref'],plan['configuration_ref'],plan['policy_ref'])
        finite=any(row['check_id'] in {'finite_delivery_leaf_coverage_v1','finite_fixture_qualification_v1'} for row in checked['results'])
        if finite:
            from .finite_evaluation import FINITE_PLAN_CHECKS
            if self.finite_e1 is None:raise ResearchError('plan_acceptance','Finite plan requires its exact installed owner')
            if finite_context is None:finite_context=self.finite_e1.context_for_plan(plan)
            self.finite_e1.validate_plan_inputs(finite_context,source_ref=plan['source_ref'],brief_ref=plan['brief_ref'],
                snapshot_ref=plan['library_snapshot_ref'],resources_ref=plan['resource_inventory_ref'],policy_ref=plan['policy_ref'],
                configuration_ref=plan['configuration_ref'],plan_source=plan['plan_source'])
            expected=list(FINITE_PLAN_CHECKS)
            qualification=next(row for row in checked['results'] if row['check_id']=='finite_fixture_qualification_v1')
            if qualification['evidence_refs']!=[finite_context.qualification_ref]:
                raise ResearchError('plan_acceptance','Finite proof names another qualification')
        elif finite_context is not None:
            raise ResearchError('plan_acceptance','A finite context cannot waive ordinary product checks')
        checkplan=self.store.read_record(checked['check_plan_ref'],contract_id='bound-check-plan')
        ids=[r['check_id'] for r in checked['results']]
        inputs=[plan[k] for k in ('brief_ref','library_snapshot_ref','resource_inventory_ref','policy_ref')]
        if (checked['subject_ref']!=source or len(ids)!=len(set(ids)) or set(ids)!=set(expected) or any(r['outcome']!='PASS' for r in checked['results'])
            or checkplan['contract_ref']!=source or checkplan['node_contract_ref']!=source or checkplan['subnode_id'] is not None
            or checkplan['policy_ref']!=plan['policy_ref'] or checkplan['input_refs']!=inputs
            or len(checkplan['mandatory_deterministic'])!=len(set(checkplan['mandatory_deterministic']))
            or set(checkplan['mandatory_deterministic'])!=set(expected)):
            raise ResearchError('plan_acceptance','Plan proof does not bind the exact complete frozen host checks')
        expected_runners=self._runner_refs(None if plan['plan_source']=='static' else acceptance,finite_context=finite_context)
        if (len(checkplan['runner_refs'])!=len(expected_runners)
            or any(ref not in checkplan['runner_refs'] for ref in expected_runners)):
            raise ResearchError('plan_acceptance','Plan checks do not pin the actual installed host/check implementations')
        if plan['plan_source']=='static' and (checkplan['profile_ref']!=source or checkplan['mandatory_semantic']):
            raise ResearchError('plan_acceptance','Static acceptance cannot substitute semantic review or another profile')
        if plan['plan_source']=='planned':
            profile_ref=self._planner_review(acceptance,source,plan['library_snapshot_ref'],plan['configuration_ref'],plan['policy_ref'])
            profile=self.store.read_record(profile_ref,contract_id='checking-profile')
            if (checkplan['profile_ref']!=profile_ref or len(checkplan['mandatory_semantic'])!=len(set(checkplan['mandatory_semantic']))
                or set(checkplan['mandatory_semantic'])!={c['criterion_id'] for c in profile['criteria']}):
                raise ResearchError('plan_acceptance','Bound plan must retain the exact independently pinned Planner criteria')

    def _runner_refs(self,planner_decision=None,*,finite_context=None):
        refs=[self.store.put_blob(Path(__file__).read_bytes(),media_type='text/x-python')]
        # The additional closed policy/graph rules are part of the exact host
        # checker implementation, rather than an unpinned request-time label.
        for filename in ('summary_planning.py', 'unified_planning.py', 'capability_planning.py'):
            refs.append(self.store.put_blob(Path(__file__).with_name(filename).read_bytes(),media_type='text/x-python'))
        if finite_context is not None:
            if self.finite_e1 is None:raise ResearchError('plan_acceptance','Finite checker owner is unavailable')
            self.finite_e1.validate_context(finite_context)
            refs.extend(ref for ref in self.finite_e1.implementation_refs() if ref not in refs)
        if planner_decision is not None:
            parent=self.store.read_record(planner_decision['contract_ref'])
            work=next(s for s in parent['subnodes'] if s['role']=='work')
            template=self.store.read_record(work['template_ref']);bundle_ref=template['check_bundle_ref']
            bundle=self.store.read_record(bundle_ref,contract_id='check-bundle')
            for ref in [bundle_ref,*[c['runner_ref'] for c in bundle['checks']]]:
                self.store.read_blob(ref)
                if ref not in refs:refs.append(ref)
        return refs

    def _planner_review(self,decision,source_ref,snapshot_ref,configuration_ref,policy_ref):
        parent=self.store.read_record(decision['contract_ref'],contract_id='node-execution-contract')
        if parent['configuration_ref']!=configuration_ref or parent['policy_ref']!=policy_ref or decision['scope_kind']!='node':
            raise ResearchError('plan_acceptance','Planner gate belongs to another configuration/policy or scope')
        subjects=[s for s in parent['subnodes'] if s['role']=='work']
        if len(subjects)!=1:raise ResearchError('plan_acceptance','Planner node has no unique work assignment')
        declaration=self.store.read_record(subjects[0]['capsule_ref'],contract_id='capsule-declaration')
        entries=self.store.read_record(snapshot_ref,contract_id='library-snapshot')['entries']
        paper = is_document_summary_policy(self.store.read_record(policy_ref,contract_id='plan-policy'))
        planner_name = PAPER_PLANNER_CC if paper else 'research.planner'
        matches=[e for e in entries if e['cc_name']==planner_name and e['declaration_sha256']==subjects[0]['capsule_ref']['sha256']]
        if (declaration['identity']['name']!=planner_name or len(matches)!=1
                or (paper and declaration['identity']['version_label'] not in {PAPER_CC_VERSION, PAPER_PLANNER_VERSION})):
            raise ResearchError('plan_acceptance','Planner review is not the exact frozen library assignment')
        template=self.store.read_record(subjects[0]['template_ref']);profile=template['checking_profile_ref']
        if profile['sha256']!=matches[0]['check_pins']['checking_profile_sha256'] or template['check_bundle_ref']['sha256']!=matches[0]['check_pins']['check_bundle_sha256']:
            raise ResearchError('plan_acceptance','Planner checking pins differ from frozen library')
        self.library.check_assets.require(template['check_bundle_ref'],profile)
        assessment=self.store.read_record(decision['assessment_ref'],contract_id='verifier-assessment')
        review=self.store.read_record(assessment['review_context_ref'],contract_id='review-context')
        if assessment['subject_ref']!=source_ref or review['subject_ref']!=source_ref or review['node_contract_ref']!=decision['contract_ref']:
            raise ResearchError('plan_acceptance','Existing Planner assessment reviews different proposal bytes')
        return profile

    def freeze(self,source_ref,brief_ref,library_snapshot_ref,resource_inventory_ref,policy_ref,configuration_ref,*,plan_source='static',acceptance_ref=None,run_inputs=None,authority_ceiling=None,finite_context=None):
        source=self.store.read_record(source_ref);brief=self.store.read_record(brief_ref,contract_id='research-brief')
        if finite_context is None:
            if not self.store.is_accepted(brief_ref):raise ResearchError('unaccepted_input','Binder requires an actually committed accepted Brief')
        else:
            if self.finite_e1 is None:raise ResearchError('finite_e1_binding','No installed finite Binder owner')
            self.finite_e1.validate_plan_inputs(finite_context,source_ref=source_ref,brief_ref=brief_ref,snapshot_ref=library_snapshot_ref,
                resources_ref=resource_inventory_ref,policy_ref=policy_ref,configuration_ref=configuration_ref,plan_source=plan_source)
            prior=self.finite_e1.claim_plan(finite_context)
            if prior is not None:
                self.validate_acceptance(self.store.read_record(prior,contract_id='run-plan'),finite_context=finite_context)
                return prior
        snapshot=self.store.read_record(library_snapshot_ref,contract_id='library-snapshot')
        resources=self.store.read_record(resource_inventory_ref,contract_id='resource-inventory');policy=self.store.read_record(policy_ref,contract_id='plan-policy')
        if (paper_workflow_allowed(policy) or is_capability_policy(policy)) and is_paper_graph(source):
            validate_summary_documents(self.store,brief,resources,resource_inventory_ref,authority_ceiling)
        refs={'brief_ref':brief_ref,'library_snapshot_ref':library_snapshot_ref,'resource_inventory_ref':resource_inventory_ref,'policy_ref':policy_ref}
        def pin_exists(pins):
            return all(any(row['ref']['sha256']==pins[key] for row in self.store.iter_records(kinds=(kind,))) for key,kind in [('check_bundle_sha256','check-bundle'),('checking_profile_sha256','checking-profile')])
        bound,results=plan_checks(source,brief,snapshot,resources,policy,plan_source=plan_source,expected_refs=refs,check_exists=self.check_registry.contains,pin_exists=pin_exists,finite_context=finite_context)
        original=None;profile_ref=source_ref;semantic=[]
        if plan_source=='planned':
            if acceptance_ref is None:raise ResearchError('plan_infeasible','Planned proposal has no committed advancing gate')
            original=self.store.read_record(acceptance_ref,contract_id='gate-decision')
            if original['action']!='advance' or source_ref not in original['accepted_refs'] or not self.store.is_accepted(source_ref):
                raise ResearchError('plan_infeasible','Planned gate did not accept these proposal bytes')
            profile_ref=self._planner_review(original,source_ref,library_snapshot_ref,configuration_ref,policy_ref)
            semantic=[c['criterion_id'] for c in self.store.read_record(profile_ref)['criteria']]
        check_plan={'schema_version':'2.0.0','id':'plan_checks:'+uuid.uuid4().hex,'contract_ref':source_ref,'node_contract_ref':source_ref,
            'input_refs':list(refs.values()),'profile_ref':profile_ref,'policy_ref':policy_ref,'mandatory_deterministic':[r['check_id'] for r in results],
            'mandatory_semantic':semantic,'runner_refs':self._runner_refs(original,finite_context=finite_context),'subnode_id':None}
        planref=self.store.put_record('bound-check-plan',check_plan)
        resultref=self.store.put_record('deterministic-check-result',{'schema_version':'1.0.0','subject_ref':source_ref,'check_plan_ref':planref,'results':results})
        if any(r['outcome']!='PASS' for r in results):raise ResearchError('plan_infeasible','Plan failed protected binding',{'check_result_ref':resultref,'results':results})
        if plan_source=='static':acceptance_ref=resultref
        else:
            from .state import utc_now
            original_ref=acceptance_ref
            decision=copy.deepcopy(original);decision.update(id='gate:'+uuid.uuid4().hex,recorded_at=utc_now(),check_plan_ref=planref,deterministic_result_ref=resultref)
            decision['reasons']=[{'code':'plan_checks_pass','message':'Bound host checks and the exact existing Planner assessment passed','criterion_ids':semantic,'evidence_refs':[resultref,original_ref]}]
            acceptance_ref=self.store.put_record('gate-decision',decision)
            self.store.append_record('plan-acceptance-binding',{'id':'plan-acceptance:'+uuid.uuid4().hex,'source_ref':source_ref,'acceptance_ref':acceptance_ref,'planner_gate_ref':original_ref})
        inputs=dict(run_inputs or {},brief=brief_ref)
        if finite_context is not None:
            qualified=finite_context.input_refs()
            if any(key not in qualified or qualified[key]!=ref for key,ref in inputs.items()):
                raise ResearchError('finite_fixture','Run input cannot replace or extend qualified finite inputs')
            inputs=qualified
        if any(p.get('run_input_key')=='search_scope' for n in bound['nodes'] for p in n['inputs']):
            scope=self.build_search_scope(source,brief_ref,resources,authority_ceiling,plan_source=plan_source,resource_inventory_ref=resource_inventory_ref)
            if 'search_scope' in inputs and inputs['search_scope']!=scope:raise ResearchError('plan_infeasible','A prebuilt scope cannot override the current protected Brief binding')
            inputs['search_scope']=scope
        for resource in resources['resources']:
            if resource['ref'] is not None:
                if finite_context is not None and resource['resource_key'] in inputs and inputs[resource['resource_key']]!=resource['ref']:
                    raise ResearchError('finite_fixture','Protected inventory would replace a qualified input')
                inputs[resource['resource_key']]=resource['ref']
        entries={(e['cc_name'],e['cc_version'],e['declaration_sha256']):e for e in snapshot['entries']}
        for node in bound['nodes']:
            entry=entries[tuple(node['cc'][k] for k in ('cc_name','cc_version','declaration_sha256'))]
            node['effect_class']=entry['effect_class'];node['check_pins']=copy.deepcopy(entry['check_pins']);node['max_attempts']=1
            node['extra_check_ids']=[key for key in node.pop('suggested_checks',[]) if self.check_registry.contains(key)]
            for port in node['inputs']:
                if port['source_kind']=='accepted_ref':
                    if finite_context is not None and port['run_input_key'] not in finite_context.input_refs():
                        raise ResearchError('finite_fixture','Finite external input is outside qualification')
                    if port['run_input_key'] not in inputs:raise ResearchError('plan_infeasible','Accepted run input not captured: '+port['run_input_key'])
                    port['accepted_ref']=inputs[port['run_input_key']];self.store.read_blob(port['accepted_ref'])
        record={'schema_version':'1.0.0','id':'plan_'+uuid.uuid4().hex,'plan_source':plan_source,**refs,'configuration_ref':configuration_ref,
            'source_ref':source_ref,'acceptance_ref':acceptance_ref,'nodes':bound['nodes'],'coverage':bound['coverage'],
            'topological_order':kahn_order(bound['nodes']),'limits':bound['limits'],'frozen':True}
        self.validate_acceptance(record,finite_context=finite_context)
        if finite_context is not None:return self.finite_e1.publish_plan(finite_context,record)
        return self.store.put_record('run-plan',record)


def committed_output_proof(store, run_id, node_id, *, subnode_id='', attempt_id=None, parent_ref=None):
    """Read the actual accepted map only with its immutable commit/Gate closure."""
    with store._lock:
        indexed = store.connection.execute(
            'SELECT port,artifact_ref,attempt_id,commit_id FROM acceptance WHERE run_id=? AND node_id=? AND subnode_id=?',
            (run_id, node_id, subnode_id)).fetchall()
    outputs = {row['port']: json.loads(row['artifact_ref']) for row in indexed}
    if not outputs:
        raise ResearchError('unaccepted_input', 'Required producer has no committed accepted outputs')
    rows = [row for row in store.iter_records(run_id=run_id, kinds=('acceptance-commit',))
            if row['record'].get('node_id') == node_id and row['record'].get('subnode_id') == subnode_id
            and (attempt_id is None or row['record'].get('attempt_id') == attempt_id)]
    if len(rows) != 1:
        raise ResearchError('unaccepted_input', 'Producer has no unique original acceptance commit')
    value = rows[0]['record']
    if (value.get('run_id') != run_id or value.get('output_refs') != outputs
            or value.get('id') != value.get('commit_id') or value.get('id') != rows[0]['ref']['id']
            or len(indexed) != len(outputs) or set(outputs) != set(value.get('output_refs', {}))
            or any(row['commit_id'] != value['id'] or row['attempt_id'] != value['attempt_id']
                   or json.loads(row['artifact_ref']) != value['output_refs'].get(row['port']) for row in indexed)
            or not value.get('gate_decision_refs')):
        raise ResearchError('unaccepted_input', 'Accepted table differs from its original commit')
    accepted = []
    gates = []
    for ref in value['gate_decision_refs']:
        gate = store.read_record(ref, contract_id='gate-decision')
        expected_scope = 'subnode' if subnode_id else 'node'
        if (gate['run_id'] != run_id or gate['node_id'] != node_id or gate['attempt_id'] != value['attempt_id']
                or gate['scope_kind'] != expected_scope or gate['subnode_id'] != (subnode_id or None)
                or gate['action'] != 'advance' or gate['verdict'] not in {'PASS', 'PASS_WITH_KNOWN_LIMITATIONS'}
                or parent_ref is not None and gate['node_contract_ref'] != parent_ref):
            raise ResearchError('unaccepted_input', 'Commit is not backed by its exact advancing Gate')
        accepted.extend(gate['accepted_refs'])
        gates.append((ref, gate))
    if any(ref not in accepted for ref in outputs.values()):
        raise ResearchError('unaccepted_input', 'Commit output differs from actual Gate acceptance')
    for ref in outputs.values():
        store.read_blob(ref)
    return {'outputs': outputs, 'receipt_ref': rows[0]['ref'], 'receipt': value, 'gates': gates}


def declaration_authority_ceiling(declaration, parent, *, role):
    """Narrow existing named permissions; no prose or model capability grants."""
    permitted = copy.deepcopy(parent)
    network = declaration['needs']['network']
    permitted['network'] = 'allowlist' if parent['network'] == 'allowlist' and network['mode'] == 'allowlist' else 'none'
    permitted['network_allowlist'] = [value for value in parent['network_allowlist'] if value in network['allowlist']] if permitted['network'] == 'allowlist' else []
    if role == 'verifier':
        permitted.update(network='none', network_allowlist=[], write_roots=[], tools=[])
        return permitted
    named = [row['identifier'] for row in declaration['needs']['external'] if row['kind'] in {'operator', 'tool'}]
    calls = declaration['budget']['per_call'].get('tool_calls')
    if named and (type(calls) is not int or calls <= 0 or any(name not in parent['tools'] for name in named)):
        raise ResearchError('authority_unavailable', 'Required named declared host tool lacks its explicit original budget/parent grant')
    permitted['tools'] = [value for value in parent['tools'] if value in named] if type(calls) is int and calls > 0 else []
    writable = [row['resource_key'] for row in declaration['needs']['resources'] if row['mode'] == 'write']
    permitted['write_roots'] = []
    if writable:
        # These exact current source modules already own this confined logical
        # workspace; no generic URI/effect-scope parser or fallback mapping.
        if (declaration['identity']['name'] not in {'research.builder', 'research.benchmark'}
                or set(writable) != {'poc_workspace'}
                or not any(row['resource_key'] == 'poc_workspace' for row in declaration['changes']['effects'])
                or declaration['changes']['effect_class'] in {'pure', 'read_only'}):
            raise ResearchError('authority_unavailable', 'Required writable resource has no supported exact protected source confinement mapping')
        root = '/workspace/poc'
        if root not in parent['write_roots']:
            raise ResearchError('authority_unavailable', 'Source-owned workspace lacks its explicit parent write-root grant')
        permitted['write_roots'] = [root]
    return permitted


def validate_child_authority(store, parent_ref, subnode_id, inputs, *, effective_authority=None):
    """Pure original-parent read/port validation, independently reused by Runner."""
    from .contracts import contract_schema
    parent = store.read_record(parent_ref, contract_id='node-execution-contract')
    matches = [row for row in parent['subnodes'] if row['subnode_id'] == subnode_id]
    if len(matches) != 1:
        raise ResearchError('input_authority', 'Child is not uniquely assigned by its original parent')
    assignment = matches[0]
    template = store.read_record(assignment['template_ref'])
    if template['role'] != assignment['role'] or template['capsule_ref'] != assignment['capsule_ref']:
        raise ResearchError('input_authority', 'Assignment and original template/declaration differ')
    declaration = store.read_record(assignment['capsule_ref'], contract_id='capsule-declaration')
    declared = {port['name']: port for port in declaration['ports']['inputs']}
    names = [port['name'] for port in inputs]
    if len(names) != len(set(names)) or set(names) - set(declared) or any(port['required'] and key not in names for key, port in declared.items()):
        raise ResearchError('input_authority', 'Concrete input inventory differs from selected declaration')
    for port in inputs:
        selected = declared[port['name']]
        same = port['contract_id'] == selected['schema_ref']
        if not same:
            same = contract_schema(port['contract_id']) == contract_schema(selected['schema_ref'])
        if (port['required'] != selected['required'] or not same
                or port['required'] and not port['artifact_refs']):
            raise ResearchError('input_authority', 'Concrete input type/requiredness is outside selected port')
    ceiling = parent['authority_ceiling']
    permitted = declaration_authority_ceiling(declaration, ceiling, role=assignment['role'])
    allowed = list(ceiling['resource_reads'])
    assignments = {row['subnode_id']: row for row in parent['subnodes']}
    if assignment['role'] == 'work':
        for dependency in assignment['depends_on']:
            source = assignments.get(dependency)
            if source is None:
                raise ResearchError('input_authority', 'Original dependency is missing')
            if source['role'] == 'work':
                proof = committed_output_proof(store, parent['run_id'], parent['node_id'],
                    subnode_id=dependency, attempt_id=parent['attempt_id'], parent_ref=parent_ref)
                allowed.extend(proof['outputs'].values())
    elif assignment['role'] == 'verifier':
        subject = template.get('subject_subnode_id')
        source = assignments.get(subject)
        if source is None or source['role'] != 'work' or assignment['depends_on'] != [subject]:
            raise ResearchError('input_authority', 'Verifier lacks its exact assigned work subject')
        by_name = {port['name']: port['artifact_refs'] for port in inputs}
        allowed_names = {'subject_declaration', 'subject_output'}
        evidence_ref = None
        if (not allowed_names.issubset(by_name) or set(by_name) - allowed_names - {'review_evidence'}
                or by_name['subject_declaration'] != [source['capsule_ref']] or len(by_name['subject_output']) != 1):
            raise ResearchError('input_authority', 'Verifier has another declaration/output subject')
        output_ref = by_name['subject_output'][0]
        observations = [row for row in store.iter_records(run_id=parent['run_id'], kinds=('invocation-observation',))
            if row['record']['node_contract_ref'] == parent_ref and row['record']['subnode_id'] == subject
            and row['record']['attempt_id'] == parent['attempt_id'] and output_ref in row['record']['output_refs']]
        if len(observations) != 1:
            raise ResearchError('input_authority', 'Verifier output has no unique actual subject observation')
        observed = observations[0]['record']
        work = store.read_record(observed['contract_ref'], contract_id='subnode-execution-contract')
        captures = [row for row in store.iter_records(run_id=parent['run_id'], kinds=('captured-output',))
            if row['record']['node_id'] == parent['node_id'] and row['record']['subnode_id'] == subject
            and row['record']['attempt_id'] == parent['attempt_id'] and row['record']['output_port'] == template['output_port']
            and row['record']['artifact_ref'] == output_ref]
        if (work['node_contract_ref'] != parent_ref or work['bindings'][0]['declaration_ref'] != source['capsule_ref']
                or work['bindings'][0]['role'] != 'work' or len(captures) != 1
                or observed['outcome'] != 'success' or observed['failure_reason_code'] is not None):
            raise ResearchError('input_authority', 'Verifier subject capture does not join original assigned work')
        proofs = []
        for row in store.iter_records(run_id=parent['run_id'], kinds=('deterministic-check-result',)):
            result = row['record']
            plan = store.read_record(result['check_plan_ref'], contract_id='bound-check-plan')
            ids = [item['check_id'] for item in result['results']]
            if (plan['contract_ref'] == observed['contract_ref'] and plan['node_contract_ref'] == parent_ref
                    and len(ids) == len(set(ids)) and set(plan['mandatory_deterministic']) <= set(ids)
                    and all(item['outcome'] == 'PASS' for item in result['results'] if item['check_id'] in plan['mandatory_deterministic'])
                    and output_ref in result.get('subject_refs', [result['subject_ref']])):
                proofs.append(row)
        if len(proofs) != 1:
            raise ResearchError('input_authority', 'Verifier subject lacks exact passing original Tier1 proof')
        from .evidence_review import MODE, PROFILE_VERSION
        source_template = store.read_record(source['template_ref'])
        source_profile_ref = source_template.get('checking_profile_ref')
        if source_profile_ref is None:
            raise ResearchError('input_authority', 'Verifier subject has no exact checking profile')
        source_profile = store.read_record(source_profile_ref, contract_id='checking-profile')
        source_is_evidence_aware = (source_profile.get('version') == PROFILE_VERSION
                                    and source_profile.get('review_mode') == MODE)
        if source_is_evidence_aware and 'review_evidence' not in by_name:
            raise ResearchError('input_authority', 'Evidence-aware subject requires its host-built verifier projection')
        if 'review_evidence' in by_name and not source_is_evidence_aware:
            raise ResearchError('input_authority', 'Legacy source profile cannot grant verifier access to evidence')
        if 'review_evidence' in by_name:
            # The optional third verifier input is accepted only for an exact
            # v2 work profile and only when its bytes reproduce the host's
            # projection from the original bound inputs and passing Tier 1.
            # This prevents caller-supplied evidence from widening review.
            from .evidence_review import build_review_evidence
            evidence_port = declared.get('review_evidence')
            if (evidence_port is None or evidence_port.get('required') is not False
                    or evidence_port.get('schema_ref') != 'opaque-bytes' or len(by_name['review_evidence']) != 1):
                raise ResearchError('input_authority', 'Evidence input is outside the exact optional v2 verifier boundary')
            evidence_ref = by_name['review_evidence'][0]
            try:
                evidence = json.loads(store.read_blob(evidence_ref).decode('utf-8'))
            except (UnicodeError, ValueError, TypeError):
                raise ResearchError('input_authority', 'Evidence projection is not valid retained JSON') from None
            proof_row = proofs[0]
            review_context = {'contract_ref': observed['contract_ref'], 'input_refs': work['input_refs'],
                              'check_plan_ref': proof_row['record']['check_plan_ref'],
                              'deterministic_result_ref': proof_row['ref']}
            if evidence != build_review_evidence(store, review_context, source_profile):
                raise ResearchError('input_authority', 'Evidence projection differs from original inputs and passing Tier 1 checks')
        allowed.extend([source['capsule_ref'], output_ref])
        if evidence_ref is not None:
            allowed.append(evidence_ref)
    else:
        raise ResearchError('input_authority', 'Unknown assigned child role')
    concrete = [ref for port in inputs for ref in port['artifact_refs']]
    if any(ref not in allowed for ref in concrete):
        raise ResearchError('input_authority', 'Concrete input exceeds the original parent/dependency read ceiling')
    for ref in concrete:
        store.read_blob(ref)
    if effective_authority is not None:
        actual = effective_authority
        if (set(actual) != set(ceiling) or any(ref not in allowed for ref in actual['resource_reads'])
                or any(ref not in actual['resource_reads'] for ref in concrete)
                or actual['network'] != 'none' and permitted['network'] != 'allowlist'
                or any(value not in permitted['network_allowlist'] for value in actual['network_allowlist'])
                or actual['network'] == 'none' and actual['network_allowlist']
                or any(value not in permitted[key] for key in ('write_roots', 'tools') for value in actual[key])
                or any(value not in actual[key] for key in ('write_roots', 'tools') for value in permitted[key])):
            raise ResearchError('input_authority', 'Effective child authority widens its original parent or declaration')


class ContractFactory:
    """Host-only node templates; concrete children point to a finalized parent."""
    def __init__(self,store,library,*,verifier_pin,finalization_profile_ref):
        self.store,self.library=store,library;self.verifier_pin=verifier_pin
        library.configure_verifier(verifier_pin)
        self.finalization_profile_ref=finalization_profile_ref
        profile=store.read_record(finalization_profile_ref,contract_id='node-finalization-profile')
        if set(profile['mandatory_deterministic'])!={'internal_acceptance','external_output','aggregate_limits'} or profile['additional_model_calls']!=0:
            raise ResearchError('node_profile_invalid','Node finalization is mechanical and requires all three source checks')

    @staticmethod
    def _version(contract):
        import re
        match=re.search(r'([0-9]+\.[0-9]+\.[0-9]+)$',contract)
        if match:return match.group(1)
        if ':field-contract:' in contract:
            from .contracts import contract_schema
            value=contract_schema(contract)['properties'].get('schema_version',{})
            if 'const' in value:return value['const']
            if value.get('enum'):return value['enum'][0]
        return '1.0.0'

    def _entry(self,pin):
        row=self.library.get(pin['cc_name'],pin['cc_version'])
        if row['declaration_ref']['sha256']!=pin['declaration_sha256']:raise ResearchError('library_membership','Declaration pin differs from admitted exact version')
        admission=self.store.read_record(row['admission_ref'],contract_id='library-admission')
        if admission['status']!='admitted':raise ResearchError('library_membership','Version was not admitted')
        declaration=self.store.read_record(row['declaration_ref'],contract_id='capsule-declaration')
        if declaration['identity'].get('overlays') or declaration['needs'].get('when'):
            raise ResearchError('unsupported_binding','M1 cannot execute overlays or conditional predicates')
        association=self.library.eligible_association(row['declaration_ref'])
        return row,declaration,admission,association

    def prepare_parent(self,run_id,node_id,work,*,inputs,outputs,objective,requirement_ids,limits,
                       policy_ref,configuration_ref,template_ref,authority_ceiling):
        self.store.get_run(run_id)
        if not requirement_ids:raise ResearchError('binding_invalid','Fixed work needs explicit protected obligation IDs')
        assignments=[];gates=[]
        verifier=self._entry(self.verifier_pin)
        for item in work:
            row,declaration,admission,association=self._entry(item['cc'])
            subnode_id=item['subnode_id'];depends=item.get('depends_on',[])
            template={'id':'template:'+uuid.uuid4().hex,'capsule_ref':row['declaration_ref'],
                'admission_ref':row['admission_ref'],'body_refs':row['body_refs'],'ports':declaration['ports'],
                'check_bundle_ref':association['bundle_ref'],'checking_profile_ref':association['profile_ref'],
                'role':'work','subnode_id':subnode_id,'depends_on':depends,'cc':item['cc']}
            tref=self.store.append_record('subnode-template',template)
            assignments.append({'subnode_id':subnode_id,'role':'work','template_ref':tref,'capsule_ref':row['declaration_ref'],'depends_on':depends,'required':True})
            gates.append({'gate_id':subnode_id+'.gate','subject_subnode_id':subnode_id,'profile_ref':association['profile_ref']})
            for port in declaration['ports']['outputs']:
                vid=subnode_id+'.verifier'+('.'+port['name'] if len(declaration['ports']['outputs'])>1 else '')
                vtemplate={'id':'template:'+uuid.uuid4().hex,'capsule_ref':verifier[0]['declaration_ref'],
                    'admission_ref':verifier[0]['admission_ref'],'body_refs':verifier[0]['body_refs'],'ports':verifier[1]['ports'],
                    'check_bundle_ref':verifier[3]['bundle_ref'],
                    'capsule_checking_profile_ref':verifier[3]['profile_ref'],
                    'subject_check_bundle_ref':association['bundle_ref'],
                    'checking_profile_ref':association['profile_ref'],'role':'verifier','subnode_id':vid,'depends_on':[subnode_id],
                    'subject_subnode_id':subnode_id,'output_port':port['name'],'cc':self.verifier_pin}
                vtref=self.store.append_record('subnode-template',vtemplate)
                assignments.append({'subnode_id':vid,'role':'verifier','template_ref':vtref,'capsule_ref':verifier[0]['declaration_ref'],'depends_on':[subnode_id],'required':True})
        kahn_order([{'node_id':a['subnode_id'],'predecessors':a['depends_on']} for a in assignments])
        record={'schema_version':'2.0.0','id':'node:'+uuid.uuid4().hex,'run_id':run_id,'node_id':node_id,'attempt_id':node_id+'-a1','revision':1,
                'objective':objective,'requirement_ids':requirement_ids,'inputs':inputs,'outputs':outputs,
                'input_refs':[r for p in inputs for r in p['artifact_refs']],'required_outputs':[p['name'] for p in outputs if p['required']],
                'evidence_obligations':['captured_input_and_output','invocation_observation','mandatory_checks','semantic_assessment','independently_budgeted_check_observation'],
                'checking_profile_ref':self.finalization_profile_ref,'policy_ref':policy_ref,'configuration_ref':configuration_ref,'template_ref':template_ref,
                'node_limits':limits,'authority_ceiling':authority_ceiling,'subnodes':assignments,
                'gate_assignments':gates+[{'gate_id':node_id+'.gate','subject_subnode_id':node_id,'profile_ref':self.finalization_profile_ref}]}
        return self.store.put_record('node-execution-contract',record,scope=record)

    def bind_subnode(self,parent_ref,subnode_id,inputs,*,role=None):
        parent=self.store.read_record(parent_ref,contract_id='node-execution-contract')
        matches=[s for s in parent['subnodes'] if s['subnode_id']==subnode_id]
        if len(matches)!=1:raise ResearchError('binding_invalid','Subnode is not assigned by frozen parent')
        assignment=matches[0];template=self.store.read_record(assignment['template_ref'])
        row,declaration,admission,association=self._entry(template['cc'])
        if role is not None and assignment['role']!=role:raise ResearchError('binding_invalid','Subnode role mismatch')
        validate_child_authority(self.store,parent_ref,subnode_id,inputs)
        # Verifier input is deliberately assembled after work capture and carries
        # only declaration+one exact output. It is not a predecessor work grant.
        for port in inputs:
            if port['required'] and not port['artifact_refs']:raise ResearchError('input_binding','Unbound required input')
            for ref in port['artifact_refs']:self.store.read_blob(ref)
        names=[port['name'] for port in inputs];expected={port['name']:port for port in declaration['ports']['inputs']}
        if len(names)!=len(set(names)) or set(names)-set(expected) or any(port['required'] and name not in names for name,port in expected.items()):
            raise ResearchError('input_binding','Named inputs must match the pinned declaration inventory')
        from .contracts import contract_schema
        for port in inputs:
            declared=expected[port['name']]
            same=port['contract_id']==declared['schema_ref']
            if not same:
                try:same=contract_schema(port['contract_id'])==contract_schema(declared['schema_ref'])
                except ResearchError:same=False
            if not same or port['required']!=declared['required']:
                raise ResearchError('input_binding','Input type or requiredness differs from the exact selected declaration')
        per=declaration['budget']['per_call'];profile=self.store.read_record(template['checking_profile_ref'],contract_id='checking-profile')
        limits={'time_s':min(per['wall_s'],parent['node_limits']['time_s']),'model_calls':per['invocations'] if any(i['service_key']=='audited_model_bridge' for i in declaration['needs']['injects']) else 0,'memory_mb':min(admission['memory_mb'],parent['node_limits']['memory_mb'])}
        if assignment['role']=='verifier':limits['time_s']=min(limits['time_s'],profile['time_s']);limits['model_calls']=1
        ceiling=declaration_authority_ceiling(declaration,parent['authority_ceiling'],role=assignment['role'])
        ceiling['resource_reads']=[r for p in inputs for r in p['artifact_refs']]
        outputs=[{'name':p['name'],'contract_id':p['schema_ref'],'version':self._version(p['schema_ref']),'required':p['required']} for p in declaration['ports']['outputs']]
        record={'schema_version':'1.0.0','id':'subnode:'+uuid.uuid4().hex,**{k:parent[k] for k in ('run_id','node_id','attempt_id','revision','objective','requirement_ids','policy_ref','configuration_ref')},
            'subnode_id':subnode_id,'node_contract_ref':parent_ref,'template_ref':assignment['template_ref'],'subnode_limits':limits,
            'checking_profile_ref':template['checking_profile_ref'],'bindings':[{'id':subnode_id+'.binding','role':assignment['role'],
                'declaration_ref':row['declaration_ref'],'implementation_refs':[row['body_refs'][body['path']] for body in declaration['identity']['body']],
                'dependency_refs':[row['body_refs'][pin['ref']] for dependency in declaration['needs']['external'] for key in ('pin','lockfile') if (pin:=dependency.get(key))],
                'admission_ref':row['admission_ref'],'effective_authority':ceiling,'limits':limits}],
            'inputs':inputs,'outputs':outputs,'input_refs':[r for p in inputs for r in p['artifact_refs']],
            'required_outputs':[p['name'] for p in outputs if p['required']],'evidence_obligations':parent['evidence_obligations']}
        contract_ref=self.store.put_record('subnode-execution-contract',record,scope=record)
        bundle=self.store.read_record(association['bundle_ref'],contract_id='check-bundle')
        plan={'schema_version':'2.0.0','id':'check_plan:'+uuid.uuid4().hex,'contract_ref':contract_ref,
            'input_refs':record['input_refs'],'profile_ref':template['checking_profile_ref'],'policy_ref':parent['policy_ref'],
            'mandatory_deterministic':list(dict.fromkeys([*[c['check_id'] for c in bundle['checks'] if c['blocking']],'host_contract','host_identity','host_limits','host_authority'])),
            'mandatory_semantic':[c['criterion_id'] for c in profile['criteria'] if c['blocking']],
            'runner_refs':list(dict((r['sha256'],r) for r in [association['bundle_ref'],*[c['runner_ref'] for c in bundle['checks']]]).values()),
            'node_contract_ref':parent_ref,'subnode_id':subnode_id}
        return contract_ref,self.store.put_record('bound-check-plan',plan,scope=record),bundle['bundle_id']
