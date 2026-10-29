"""Account-scoped projections of the installed workflow and its actual releases.

These views cannot install assets, dispatch work, or interpret a scientific
verdict. Private verifier instructions, model prompts and credentials stay out.
"""
from __future__ import annotations

import json
import re
from importlib.resources import files

from .contracts import ResearchError


STAGES = ('intent', 'requirements', 'planner', 'search', 'screening', 'hypothesis',
          'builder', 'benchmark', 'evaluation', 'delivery', 'verifier')


def _declarations(store, core):
    root = files('jiuwenswarm.research_assets')
    catalog = json.loads(root.joinpath('catalog.json').read_text('utf-8'))
    result = {stage: json.loads(root.joinpath(entry['declaration_path']).read_text('utf-8'))
              for stage, entry in catalog['capsules'].items()}
    from .capsules.assets import source_metadata, STAGE_VERSIONS
    for stage, entry in source_metadata().items():
        result[stage] = dict(entry['declaration'], identity=dict(entry['declaration']['identity'], version_label=STAGE_VERSIONS[stage]))
    # Show the exact prepared/installed declarations, including a new authored
    # local release. Display must not silently substitute an older version.
    for stage, asset in getattr(core, 'installed', {}).items():
        if stage in result or stage in {'paper_summary', 'paper_delivery'}:
            result[stage] = store.read_record(asset['declaration_ref'], contract_id='capsule-declaration')
    return result


async def runtime_snapshot(channel, principal):
    principal.require('status')
    service = channel.research_service
    attachment = channel.research_composition
    core = attachment.composition
    declarations = _declarations(service.store, core)
    capsules = []
    stages = STAGES + tuple(stage for stage in ('paper_summary', 'paper_delivery') if stage in declarations)
    for stage in stages:
        declaration = declarations[stage]
        identity = declaration['identity']
        row = {'stage': stage, 'name': identity['name'], 'version': identity['version_label'],
               'standing': 'not_installed', 'eligible': False, 'checks': [], 'criteria': []}
        if core is not None:
            try:
                installed = core.library.get(row['name'], row['version'])
                row['standing'] = installed['standing']
                association = core.library.eligible_association(installed['declaration_ref'])
                admission = service.store.read_record(installed['admission_ref'], contract_id='library-admission')
                row['eligible'] = admission['status'] == 'admitted' and installed['standing'] == 'active'
                bundle = service.store.read_record(association['bundle_ref'], contract_id='check-bundle')
                profile = service.store.read_record(association['profile_ref'], contract_id='checking-profile')
                row['checks'] = [item['check_id'] for item in bundle['checks']]
                row['criteria'] = [item['criterion_id'] for item in profile['criteria']]
            except ResearchError:
                # Membership and independently measured guard eligibility differ.
                # A bundled declaration alone is never an installed capability.
                pass
        capsules.append(row)
    diagnostics = [{'code': item['code'], 'detail': item['detail']} for item in attachment.diagnostics]
    readiness = None
    try:
        readiness = await service.readiness(principal)
    except ResearchError as exc:
        diagnostics.append({'code': exc.code, 'detail': 'Protected runtime readiness is unavailable.'})
    prerequisites = list(readiness['prerequisites']) if readiness else []
    # Missing catalog pins must not hide independently observable runtime facts.
    # These are status observations, never substitutes for complete readiness.
    ports = attachment.runtime_ports
    if readiness is None and ports is not None and 'readiness' in principal.operations:
        integrated_scope = False
        try:
            from .unified_planning import is_integrated_policy
            options = (ports.bindings or {}).get('protected_options', {})
            policy = service.store.read_record(ports.operator.snapshot()['cc']['plan_policy_ref'], contract_id='plan-policy')
            integrated_scope = options.get('integrated_workflows') is True and is_integrated_policy(policy)
        except (ResearchError, AttributeError, KeyError, TypeError):
            pass
        try:
            selected = await ports.status_client.call('model_settings', {
                'account_id': principal.account_id, 'action': 'get', 'values': {},
                'include_chatgpt_models': False}, timeout_s=15)
            state = await ports.status_client.call('subscription_status',
                {} if selected.get('selected_id') in {'codex', 'chatgpt_ai4r'} else {'include_subscription': False}, timeout_s=10)
            model_ready = (selected.get('local_ready') is True if selected.get('selected_id') == 'auto'
                else state.get('state') == 'ready' if selected.get('selected_id') == 'codex'
                else selected.get('api_ready') is True)
            if selected.get('selected_id') == 'chatgpt_ai4r':
                model_ready = selected.get('local_ready') is True and state.get('state') == 'ready'
            observations = [('model', model_ready)]
            if not integrated_scope:
                observations.append(('builder', state.get('builder_qualified') is True))
            for name, ok in observations:
                prerequisites.append({'name': name, 'status': 'ready' if ok else 'unavailable',
                    'reason': 'Observed by the native runtime owner.' if ok else 'The native runtime owner reports this prerequisite unavailable.'})
        except Exception:
            prerequisites.append({'name': 'model', 'status': 'unavailable', 'reason': 'Native runtime status could not be observed.'})
        try:
            state = await (ports.executor.read_only_prerequisites() if integrated_scope else ports.executor.prerequisites())
            reason = ('Protected executor broker is reachable; scientific qualification is checked for selected scientific work.'
                if integrated_scope else 'Restricted executor prerequisites passed.')
            prerequisites.append({'name': 'isolation', 'status': 'ready' if state.get('ready') is True else 'unavailable',
                'reason': reason if state.get('ready') is True else 'Restricted executor prerequisites are incomplete.'})
        except Exception:
            prerequisites.append({'name': 'isolation', 'status': 'unavailable', 'reason': 'Restricted executor status could not be observed.'})
    defaults = service.client_defaults(principal)
    # A captured operator configuration can exist before catalog installation.
    captured = getattr(core, 'runner', None)
    configuration = getattr(channel, 'research_refusal_reason', None) is None and captured is not None
    return {'schema': 'ai4r-workflow-runtime:1', 'configured': configuration,
            'development_mode':core is not None and core.library.development_mode,
            'qualification_status':'not_run' if core is not None and core.library.development_mode else 'governed',
            'ready': readiness is not None and readiness['ready'] is True,
            'plan_source': defaults.get('plan_source') or getattr(service, 'captured_plan_source', None), 'capsules': capsules,
            'diagnostics': diagnostics, 'prerequisites': prerequisites, 'defaults': defaults,
            'example_available': getattr(service, 'local_example_ref', None) is not None}


def workflow_example(service, principal):
    """An operator-captured tutorial is source material, never run evidence."""
    from .contracts import validate
    principal.require('status')
    ref = getattr(service, 'local_example_ref', None)
    if ref is None:
        raise ResearchError('unavailable', 'This deployment has no captured research example')
    example = service.store.read_record(ref)
    if example.get('schema') != 'ai4r-local-research-example:1':
        raise ResearchError('unavailable', 'Captured research example is invalid')
    validate('Ref', example['guide_ref'])
    return {'schema': example['schema'], 'title': example['title'], 'description': example['description'],
            'filename': example['filename'], 'request': example['request'], 'guide_ref': example['guide_ref'],
            'guide': service.store.read_blob(example['guide_ref']).decode('utf-8')}


def run_timeline(service, principal, run_id):
    principal.require('status')
    run = service.store.get_run(run_id, account_id=principal.account_id)
    principal.require('status', run['workspace_id'])
    events = []
    records = list(service.store.iter_records(run_id=run_id))
    # Public ModelCall records carry an invocation ID, not a run ID. Resolve
    # only exact call Refs captured by observations of this owned run.
    seen_calls = {entry['ref']['id'] for entry in records if entry['kind'] == 'model-call'}
    for entry in list(records):
        if entry['kind'] != 'invocation-observation':
            continue
        for ref in entry['record']['trace_refs']:
            if ref['id'] in seen_calls:
                continue
            try:
                kind = service.store.record_kind(ref)
            except ResearchError as exc:
                if exc.code != 'evidence_unavailable':
                    raise
                continue  # Raw native trace blobs have no record kind.
            if kind == 'model-call':
                call = service.store.read_record(ref, contract_id='model-call')
                records.append({'kind': 'model-call', 'ref': ref, 'record': call})
                seen_calls.add(ref['id'])
    routes = {entry['record']['route_id']: entry for entry in records if entry['kind'] == 'route-record'}
    starts = {(entry['record']['call_id'], entry['record']['invocation_id'], entry['record']['execution_id']): entry['record']
              for entry in records if entry['kind'] == 'model-call-start'}
    for envelope in records:
        kind, record = envelope['kind'], envelope['record']
        if kind == 'invocation-observation':
            events.append({'kind': 'invocation', 'ref': envelope['ref'], 'node_id': record['node_id'],
                           'subnode_id': record.get('subnode_id'), 'outcome': record['outcome'],
                           'reason': record.get('failure_reason_code'), 'accepted': False})
        elif kind == 'model-call':
            # ModelCall deliberately has no node/route fields. Join the exact
            # host-captured start and RouteRecord, rather than inventing them.
            start = starts.get((record['id'], record['invocation_id'], record['execution_id']))
            routed = routes.get(start['route_id']) if start else None
            if routed is None or routed['ref'] != start['route_ref']:
                raise ResearchError('integrity_fault', 'Model call has no exact captured route')
            route = routed['record']
            identity = record.get('identity', {})
            events.append({'kind': 'model_call', 'ref': envelope['ref'], 'node_id': route['node_id'],
                'subnode_id': route.get('subnode_id'), 'outcome': record['outcome'],
                'function': record.get('call_function'), 'requested_model': identity.get('requested'),
                'effective_model': identity.get('effective'), 'route_source': route.get('decision_source'),
                'route_id': route.get('route_id'), 'reason': record.get('provider_error_code')})
        elif kind == 'gate-decision':
            checks = []
            ref = record.get('deterministic_result_ref')
            if ref is not None:
                checked = service.store.read_record(ref, contract_id='deterministic-check-result')
                checks = [{key: item.get(key) for key in ('check_id', 'outcome', 'reason')}
                          for item in checked['results']]
            findings = []
            ref = record.get('assessment_ref')
            if ref is not None:
                assessed = service.store.read_record(ref, contract_id='verifier-assessment')
                findings = [{key: item.get(key) for key in ('criterion_id', 'outcome', 'reason')}
                            for item in assessed['findings']]
            events.append({'kind': 'gate', 'ref': envelope['ref'], 'node_id': record['node_id'],
                           'subnode_id': record.get('subnode_id'), 'scope': record['scope_kind'],
                           'action': record['action'], 'verdict': record.get('verdict'),
                           'checks': checks, 'findings': findings,
                           'accepted_refs': record['accepted_refs'] if record['action'] == 'advance' else []})
    return {'schema': 'ai4r-workflow-timeline:1', 'run_id': run_id, 'revision': run['revision'], 'events': events}


def _public_plan_outcome(store, run):
    """Project original ordinary-run infeasibility without exporting its refs."""
    from .binding import committed_output_proof

    def require(condition):
        if not condition:
            raise ResearchError('integrity_fault', 'Original plan outcome does not match its owned run lineage')

    # Private evaluation context is not an ordinary user-facing plan result.
    if run['submission'].get('profile_id') is not None or store.evaluation_binding(run['id']) is not None:
        return None
    rows = list(store.iter_records(run_id=run['id'], kinds=('plan-outcome',)))
    require(len(rows) == 1)
    ref = rows[0]['ref']
    outcome = store.read_record(ref, contract_id='plan-outcome')
    require(store.record_kind(ref) == 'plan-outcome' and outcome['id'] == ref['id']
            and outcome['outcome'] == 'plan_infeasible' and outcome['attempt_depth'] in (1, 2)
            and outcome['next_stage'] == 'intention_compiler')
    proof = committed_output_proof(store, run['id'], 'intention_compiler')
    require(proof['outputs'] == {'brief': outcome['brief_ref']} and len(proof['gates']) == 1)
    brief = store.read_record(outcome['brief_ref'], contract_id='research-brief')
    require(brief['intake_ref'] == run['submission']['intake_ref'])
    reasons = []
    for reason in outcome['reasons'][:20]:
        detail = reason['detail']
        if detail.startswith('INFEASIBLE:'):
            detail = detail[len('INFEASIBLE:'):]
        detail = detail.strip()[:300]
        require(bool(detail))
        reasons.append(detail)
    require(bool(reasons))
    return {'outcome': 'plan_infeasible', 'reasons': reasons}


def _public_compiler_outcome(store, run):
    """Explain an original Compiler halt; never release its candidate output."""
    from .attempt_inspection import _original
    from .gate import assemble_assessment

    def require(condition):
        if not condition:
            raise ResearchError('integrity_fault', 'Compiler explanation does not match its owned original attempt')

    if run['submission'].get('profile_id') is not None or store.evaluation_binding(run['id']) is not None:
        return None
    states = [row for row in store.node_states(run['id']) if row['node_id'] == 'intention_compiler']
    require(len(states) == 1 and states[0]['state'] == 'failed' and states[0]['attempt_id'])
    scope = {key: states[0][key] for key in ('run_id', 'node_id', 'attempt_id')}
    gates = [row for row in store.iter_records(run_id=run['id'], kinds=('gate-decision',))
             if row['record'].get('node_id') == scope['node_id']
             and row['record'].get('attempt_id') == scope['attempt_id']
             and row['record'].get('scope_kind') == 'node']
    require(len(gates) == 1)
    gate = _original(store, gates[0]['ref'], 'gate-decision', 'gate-decision', scope=scope)
    parent_ref = gate['contract_ref']
    parent = _original(store, parent_ref, 'node-execution-contract', 'node-execution-contract', scope=scope)
    require(all(parent[key] == gate[key] == value for key, value in scope.items())
            and gate['action'] == 'halt' and not gate['accepted_refs']
            and gate['node_contract_ref'] == parent_ref and gate['subnode_id'] is None
            and parent['configuration_ref'] == run['submission']['configuration_ref']
            and any(port['name'] == 'request' and port['artifact_refs'] == [run['submission']['intake_ref']]
                    for port in parent['inputs'])
            and not store.accepted_outputs(run['id'], scope['node_id']))
    node_plan = _original(store, gate['check_plan_ref'], 'bound-check-plan', 'bound-check-plan', scope=scope)
    node_checks = _original(store, gate['deterministic_result_ref'], 'deterministic-check-result',
                            'deterministic-check-result', scope=scope)
    require(node_plan['contract_ref'] == node_plan['node_contract_ref'] == parent_ref
            and node_plan['profile_ref'] == parent['checking_profile_ref']
            and node_plan['policy_ref'] == gate['policy_ref'] == parent['policy_ref']
            and node_checks['check_plan_ref'] == gate['check_plan_ref']
            and gate['internal_decision_refs'])
    reasons = []

    def add(reason):
        # An identifier-only infrastructure failure is not a clarification.
        text = reason.strip()
        if text and not re.fullmatch(r'[a-z][a-z0-9_]*(?::[a-z0-9_]+)*', text):
            text = text[:300]
            if text not in reasons and len(reasons) < 20:
                reasons.append(text)

    for ref in gate['internal_decision_refs']:
        child_gate = _original(store, ref, 'gate-decision', 'gate-decision', scope=scope)
        require(child_gate['scope_kind'] == 'subnode' and child_gate['node_contract_ref'] == parent_ref
                and all(child_gate[key] == value for key, value in scope.items()))
        if child_gate['action'] == 'advance':
            continue
        require(child_gate['action'] == 'halt' and not child_gate['accepted_refs'])
        child_ref = child_gate['contract_ref']
        child = _original(store, child_ref, 'subnode-execution-contract', 'subnode-execution-contract', scope=scope)
        assignments = [row for row in parent['subnodes'] if row['subnode_id'] == child['subnode_id']]
        require(len(assignments) == 1 and assignments[0]['role'] == 'work'
                and child['subnode_id'] in {'intent', 'requirements'}
                and child['subnode_id'] == child_gate['subnode_id']
                and child['node_contract_ref'] == parent_ref and len(child['bindings']) == 1
                and child['bindings'][0]['role'] == 'work' and child['template_ref'] == assignments[0]['template_ref']
                and child['bindings'][0]['declaration_ref'] == assignments[0]['capsule_ref']
                and all(child[key] == parent[key] for key in (*scope, 'configuration_ref', 'policy_ref')))
        template = _original(store, child['template_ref'], 'subnode-template')
        plan = _original(store, child_gate['check_plan_ref'], 'bound-check-plan', 'bound-check-plan', scope=scope)
        require(template['role'] == 'work' and template['subnode_id'] == child['subnode_id']
                and template['capsule_ref'] == assignments[0]['capsule_ref']
                and plan['contract_ref'] == child_ref and plan['node_contract_ref'] == parent_ref
                and plan['subnode_id'] == child['subnode_id']
                and plan['profile_ref'] == child['checking_profile_ref'] == template['checking_profile_ref']
                and plan['policy_ref'] == child_gate['policy_ref'] == child['policy_ref']
                and plan['input_refs'] == child_gate['input_refs'] == child['input_refs'])
        checked = _original(store, child_gate['deterministic_result_ref'], 'deterministic-check-result',
                            'deterministic-check-result', scope=scope)
        subjects = checked.get('subject_refs', [checked['subject_ref']])
        require(checked['check_plan_ref'] == child_gate['check_plan_ref']
                and (subjects == child_gate['output_refs'] or not child_gate['output_refs']
                     and subjects == child_gate['invocation_refs'][:1]))
        observations = [_original(store, pin, 'invocation-observation', 'invocation-observation', scope=scope)
                        for pin in child_gate['invocation_refs']]
        workers = [row for row in observations if row['contract_ref'] == child_ref]
        require(len(workers) == 1 and workers[0]['node_contract_ref'] == parent_ref
                and workers[0]['subnode_id'] == child['subnode_id']
                and all(pin in workers[0]['output_refs'] for pin in child_gate['output_refs']))
        for pin in child_gate['output_refs']:
            store.read_blob(pin)
        for row in checked['results']:
            if row['check_id'] in plan['mandatory_deterministic'] and row['outcome'] != 'PASS':
                add(row['reason'])
        if child_gate['assessment_ref'] is not None:
            assessment = _original(store, child_gate['assessment_ref'], 'verifier-assessment', 'verifier-assessment')
            review = _original(store, assessment['review_context_ref'], 'review-context', 'review-context')
            profile = _original(store, plan['profile_ref'], 'checking-profile', 'checking-profile')
            require(len(child_gate['output_refs']) == 1 and assessment['subject_ref'] == child_gate['output_refs'][0]
                    and review['subject_ref'] == assessment['subject_ref'] and review['contract_ref'] == child_ref
                    and review['node_contract_ref'] == parent_ref and review['subnode_id'] == child['subnode_id']
                    and review['check_plan_ref'] == child_gate['check_plan_ref']
                    and review['deterministic_result_ref'] == child_gate['deterministic_result_ref']
                    and review['criteria'] == plan['mandatory_semantic']
                    and plan['mandatory_semantic'] == [row['criterion_id'] for row in profile['criteria'] if row['blocking']])
            criteria = [row for row in profile['criteria'] if row['target_port'] in (None, child_gate['output_port'])]
            body = {key: assessment[key] for key in ('uncertainties', 'limitations', 'required_correction')}
            body['findings'] = [{key: row[key] for key in ('criterion_id', 'outcome', 'reason')}
                                for row in assessment['findings']]
            require(assemble_assessment(body, criteria, child['bindings'][0]['declaration_ref'],
                                        assessment['subject_ref'], assessment['review_context_ref']) == assessment)
            blocking = {row['criterion_id'] for row in criteria if row['blocking']}
            for row in assessment['findings']:
                if row['criterion_id'] in blocking and row['outcome'] != 'PASS':
                    add(row['reason'])
        elif not reasons and any(row['message'] == 'blocking_uncertainty' for row in child_gate['reasons']):
            require(len(child_gate['output_refs']) == 1 and len(child['outputs']) == 1)
            candidate = store.read_record(child_gate['output_refs'][0], contract_id=child['outputs'][0]['contract_id'])
            for row in [*candidate.get('uncertainties', []), *candidate.get('unresolved_items', [])]:
                if row['blocking']:
                    add(row['clarification'])
            if not reasons and candidate.get('readiness', {}).get('status') == 'needs_clarification':
                add(candidate['readiness']['reason'])
    return {'outcome': 'compiler_halted', 'reasons': reasons} if reasons else None


def accepted_paper_delivery_manifest(store, run_id):
    """Read only the exact committed delivery of the protected paper workflow.

    A manifest-shaped artifact or an installed Capsule never selects this path.
    The original frozen policy, graph, declaration and acceptance select it.
    """
    from .binding import committed_output_proof

    def require(condition):
        if not condition:
            raise ResearchError('integrity_fault', 'Paper delivery differs from its original frozen acceptance')

    bindings = list(store.iter_records(run_id=run_id, kinds=('run-plan-binding',)))
    if not bindings:
        return None
    require(len(bindings) == 1)
    binding = bindings[0]['record']
    require(binding['run_id'] == run_id)
    plan = store.read_record(binding['plan_ref'], contract_id='run-plan')
    policy = store.read_record(plan['policy_ref'], contract_id='plan-policy')
    from .unified_planning import paper_workflow_allowed, is_paper_graph
    if not paper_workflow_allowed(policy) or not is_paper_graph(plan):
        return None
    require(plan['frozen'] is True and plan['plan_source'] == 'planned')
    run = store.get_run(run_id)
    require(plan['configuration_ref'] == run['submission']['configuration_ref'])
    summary_nodes = [node for node in plan['nodes'] if node['cc']['cc_name'] == 'research.paper_summary']
    delivery_nodes = [node for node in plan['nodes'] if node['cc']['cc_name'] == 'research.paper_summary_delivery']
    versions = {node['cc']['cc_version'] for node in plan['nodes']}
    # Reading a committed historical result must use its original frozen
    # declarations. New planning separately requires the current release.
    require(len(plan['nodes']) == 2 and len(summary_nodes) == len(delivery_nodes) == 1
            and len(versions) == 1 and versions <= {'paper-m1-1', 'paper-m1-2', 'paper-m1-3', 'paper-m1-4', 'paper-m1-5'})
    summary_node, node = summary_nodes[0], delivery_nodes[0]
    require(node['predecessors'] == [summary_node['node_id']]
            and plan['topological_order'] == [summary_node['node_id'], node['node_id']])
    states = [state for state in store.node_states(run_id) if state['node_id'] == node['node_id']]
    require(len(states) == 1)
    if states[0]['state'] != 'completed':
        require(not store.accepted_outputs(run_id, node['node_id']))
        return None
    def committed(node, contracts, *, attempt_id=None):
        proof = committed_output_proof(store, run_id, node['node_id'], attempt_id=attempt_id)
        require(set(proof['outputs']) == set(contracts) and len(proof['gates']) == 1)
        gate_ref, gate = proof['gates'][0]
        parent_ref = gate['node_contract_ref']
        require(store.record_kind(gate_ref) == 'gate-decision'
                and store.record_kind(parent_ref) == 'node-execution-contract' and gate['contract_ref'] == parent_ref)
        parent = store.read_record(parent_ref, contract_id='node-execution-contract')
        work = [assignment for assignment in parent['subnodes'] if assignment['role'] == 'work']
        require(parent['run_id'] == run_id and parent['node_id'] == node['node_id']
                and parent['attempt_id'] == proof['receipt']['attempt_id']
                and parent['configuration_ref'] == plan['configuration_ref'] and parent['policy_ref'] == plan['policy_ref']
                and parent['template_ref'] == plan['source_ref'] and parent['node_limits'] == node['limits']
                and set(parent['required_outputs']) == set(proof['outputs']) and len(work) == 1
                and work[0]['subnode_id'] == node['node_id']
                and work[0]['capsule_ref']['sha256'] == node['cc']['declaration_sha256'])
        declaration = store.read_record(work[0]['capsule_ref'], contract_id='capsule-declaration')
        template = store.read_record(work[0]['template_ref'])
        require(declaration['identity']['name'] == node['cc']['cc_name']
                and declaration['identity']['version_label'] == node['cc']['cc_version'] and template['cc'] == node['cc']
                and {port['name']: port['contract_id'] for port in parent['outputs']} == contracts)
        return proof, parent

    proof, parent = committed(node, {'research_report': 'urn:ai4r:paper-report:1.0.0',
                                    'delivery_manifest': 'urn:ai4r:paper-delivery-manifest:1.0.0'},
                              attempt_id=states[0]['attempt_id'])
    manifest_ref = proof['outputs']['delivery_manifest']
    manifest = store.read_record(manifest_ref, contract_id='urn:ai4r:paper-delivery-manifest:1.0.0')
    summary, _ = committed(summary_node, {'summary': 'urn:ai4r:paper-summary:1.0.0'})
    require(manifest['id'] == 'delivery_manifest' and manifest['report_ref'] == proof['outputs']['research_report']
            and manifest['brief_ref'] == plan['brief_ref'] and manifest['brief_ref'] in parent['input_refs']
            and manifest['summary_ref'] in summary['outputs'].values()
            and manifest['summary_ref'] in parent['input_refs'])
    reports = [item for item in manifest['files'] if item['role'] == 'report']
    require(len(reports) == 1 and reports[0]['artifact_ref'] == manifest['report_ref']
            and reports[0]['media_type'] == 'text/markdown' and reports[0]['audience'] == 'researcher')
    return {'manifest_ref': manifest_ref, 'manifest': manifest, 'report': reports[0]}


def accepted_research_delivery_manifest(store, run_id):
    """Resolve one original accepted POC report without exporting native traces.

    This reads immutable acceptance and frozen source links. It does not run
    scientific checks again, alter their verdicts or infer an accepted output
    from a filename. Full technical evidence retrieval remains independent.
    """
    from .binding import committed_output_proof, kahn_order
    from .contracts import contract_schema

    def require(condition):
        if not condition:
            raise ResearchError('integrity_fault', 'Research delivery differs from its original frozen acceptance')

    run = store.get_run(run_id)
    if run['submission'].get('profile_id') is not None or store.evaluation_binding(run_id) is not None:
        return None
    bindings = list(store.iter_records(run_id=run_id, kinds=('run-plan-binding',)))
    if len(bindings) != 1:
        return None
    plan = store.read_record(bindings[0]['record']['plan_ref'], contract_id='run-plan')
    stages = [item['cc']['cc_name'] for item in plan['nodes']]
    known_poc = {'research.search', 'research.screening', 'research.hypothesis', 'research.builder',
                 'research.benchmark', 'research.evaluation', 'research.delivery'}
    if len(stages) != 7 or set(stages) != known_poc:
        return None  # Preserve the existing generic path for other legitimate graphs.
    require(bindings[0]['record']['run_id'] == run_id)
    delivery = [node for node in plan['nodes'] if node['cc']['cc_name'] == 'research.delivery']
    if not delivery:
        return None
    require(run['state'] == 'completed' and len(delivery) == 1
            and plan['frozen'] is True and plan['configuration_ref'] == run['submission']['configuration_ref']
            and plan['topological_order'] == kahn_order(plan['nodes']))
    nodes = {node['node_id']: node for node in plan['nodes']}
    node = delivery[0]
    depended = {key for item in plan['nodes'] for key in item['predecessors']}
    require([item['node_id'] for item in plan['nodes'] if item['node_id'] not in depended] == [node['node_id']])
    ancestors = set()
    pending = list(node['predecessors'])
    while pending:
        key = pending.pop()
        require(key in nodes)
        if key not in ancestors:
            ancestors.add(key)
            pending.extend(nodes[key]['predecessors'])
    require(ancestors == set(nodes) - {node['node_id']})
    evaluation = [nodes[key] for key in ancestors if nodes[key]['cc']['cc_name'] == 'research.evaluation']
    require(len(evaluation) == 1)
    policy = store.read_record(plan['policy_ref'], contract_id='plan-policy')
    require(all(sum(item['cc']['cc_name'] == name for item in plan['nodes']) == 1
                for name in policy['required_stages']))
    accepted_plan = store.read_record(plan['acceptance_ref'])
    if plan['plan_source'] == 'planned':
        require(accepted_plan['run_id'] == run_id and accepted_plan['action'] == 'advance'
                and accepted_plan['scope_kind'] == 'node' and accepted_plan['node_id'] == 'planner'
                and plan['source_ref'] in accepted_plan['accepted_refs']
                and store.is_accepted(plan['source_ref'], run_id=run_id))
        plan_checks = store.read_record(accepted_plan['deterministic_result_ref'], contract_id='deterministic-check-result')
    else:
        plan_checks = store.read_record(plan['acceptance_ref'], contract_id='deterministic-check-result')
    require(plan_checks['subject_ref'] == plan['source_ref']
            and plan_checks['results'] and all(item['outcome'] == 'PASS' for item in plan_checks['results']))
    snapshot = store.read_record(plan['library_snapshot_ref'], contract_id='library-snapshot')
    compiler = committed_output_proof(store, run_id, 'intention_compiler')
    require(compiler['outputs'] == {'brief': plan['brief_ref']} and len(compiler['gates']) == 1)
    compiler_parent = store.read_record(compiler['gates'][0][1]['node_contract_ref'], contract_id='node-execution-contract')
    brief = store.read_record(plan['brief_ref'], contract_id='research-brief')
    require(compiler_parent['run_id'] == run_id
            and compiler_parent['configuration_ref'] == plan['configuration_ref']
            and compiler_parent['policy_ref'] == plan['policy_ref']
            and brief['intake_ref'] == run['submission']['intake_ref']
            and any(port['name'] == 'request' and port['artifact_refs'] == [brief['intake_ref']]
                    for port in compiler_parent['inputs']))
    states = {item['node_id']: item for item in store.node_states(run_id)}
    proofs, parents = {}, {}
    for key in plan['topological_order']:
        item = nodes[key]
        require(key in states and states[key]['state'] == 'completed')
        proof = committed_output_proof(store, run_id, key, attempt_id=states[key]['attempt_id'])
        require(len(proof['gates']) == 1 and set(proof['outputs']) == {port['name'] for port in item['outputs']})
        gate = proof['gates'][0][1]
        parent_ref = gate['node_contract_ref']
        parent = store.read_record(parent_ref, contract_id='node-execution-contract')
        work = [assignment for assignment in parent['subnodes'] if assignment['role'] == 'work']
        entries = [entry for entry in snapshot['entries'] if all(entry[field] == item['cc'][field]
                   for field in ('cc_name', 'cc_version', 'declaration_sha256'))]
        require(gate['contract_ref'] == parent_ref and parent['run_id'] == run_id and parent['node_id'] == key
                and parent['attempt_id'] == proof['receipt']['attempt_id']
                and parent['configuration_ref'] == plan['configuration_ref'] and parent['policy_ref'] == plan['policy_ref']
                and parent['template_ref'] == plan['source_ref'] and parent['node_limits'] == item['limits']
                and set(parent['required_outputs']) == set(proof['outputs']) and len(work) == len(entries) == 1
                and work[0]['subnode_id'] == key and work[0]['capsule_ref']['sha256'] == item['cc']['declaration_sha256']
                and entries[0]['check_pins'] == item['check_pins'])
        declaration = store.read_record(work[0]['capsule_ref'], contract_id='capsule-declaration')
        template = store.read_record(work[0]['template_ref'])
        require(declaration['identity']['name'] == item['cc']['cc_name']
                and declaration['identity']['version_label'] == item['cc']['cc_version']
                and template['cc'] == item['cc'] and template['capsule_ref'] == work[0]['capsule_ref']
                and {port['name']: port['contract_id'] for port in parent['outputs']}
                    == {port['name']: port['schema_ref'] for port in entries[0]['output_ports']})
        inputs = {port['name']: port['artifact_refs'] for port in parent['inputs']}
        for port in item['inputs']:
            if port['source_kind'] == 'future_output':
                future = port['future']
                require(future['producer_node'] in proofs
                        and inputs.get(port['name']) == [proofs[future['producer_node']]['outputs'][future['port']]])
            elif port['source_kind'] == 'accepted_ref':
                require(inputs.get(port['name']) == [port['accepted_ref']])
        proofs[key], parents[key] = proof, parent
    proof, parent = proofs[node['node_id']], parents[node['node_id']]
    require(set(proof['outputs']) == {'research_report', 'delivery_manifest'})
    report_contracts = {port['name']: port['contract_id'] for port in parent['outputs']}
    require(contract_schema(report_contracts['research_report']) == contract_schema('research-report')
            and contract_schema(report_contracts['delivery_manifest']) == contract_schema('delivery-manifest'))
    manifest_ref = proof['outputs']['delivery_manifest']
    manifest = store.read_record(manifest_ref, contract_id='delivery-manifest')
    evaluation_proof = proofs[evaluation[0]['node_id']]
    require(set(evaluation_proof['outputs']) == {'evaluation_verdict'})
    verdict_ref = evaluation_proof['outputs']['evaluation_verdict']
    verdict = store.read_record(verdict_ref, contract_id='evaluation-verdict')
    gate_refs = [proofs[key]['gates'][0][0] for key in plan['topological_order'] if key in ancestors]
    parent_inputs = {port['name']: port['artifact_refs'] for port in parent['inputs']}
    require(manifest['id'] == 'delivery_manifest'
            and manifest['brief_ref'] == plan['brief_ref'] == verdict['brief_ref']
            and manifest['report_ref'] == proof['outputs']['research_report']
            and manifest['verdict_ref'] == verdict_ref
            and manifest['gate_decision_refs'] == gate_refs
            and parent_inputs.get('brief') == [plan['brief_ref']]
            and parent_inputs.get('evaluation_verdict') == [verdict_ref]
            and parent_inputs.get('hypothesis_blueprint') == [verdict['blueprint_ref']]
            and parent_inputs.get('benchmark_payload') == [verdict['benchmark_ref']])
    reports = [file for file in manifest['files'] if file['role'] == 'report']
    require(len(reports) == 1 and reports[0]['artifact_ref'] == manifest['report_ref']
            and reports[0]['media_type'] == 'text/markdown' and reports[0]['audience'] == 'researcher')
    return {'manifest_ref': manifest_ref, 'manifest': manifest, 'report': reports[0]}


async def run_result(service, principal, run_id):
    """Return an accepted report or bounded original public halt explanation."""
    principal.require('export')
    store = service.store
    run = store.get_run(run_id, account_id=principal.account_id)
    principal.require('export', run['workspace_id'])
    result = {'schema': 'ai4r-workflow-result:1', 'run_id': run_id, 'status': run['state'], 'report': None}
    if run['state'] != 'completed':
        if run['state'] == 'halted' and run['reason'] == 'plan_infeasible':
            outcome = _public_plan_outcome(store, run)
            if outcome is not None:
                result['plan_outcome'] = outcome
        elif run['state'] == 'halted' and run['reason'] == 'compiler_did_not_release':
            outcome = _public_compiler_outcome(store, run)
            if outcome is not None:
                result['compiler_outcome'] = outcome
        return result
    paper = accepted_paper_delivery_manifest(store, run_id)
    delivery = paper if paper is not None else accepted_research_delivery_manifest(store, run_id)
    reports = [delivery['report']] if delivery is not None else []
    for node in (() if delivery is not None else store.node_states(run_id)):
        for ref in store.accepted_outputs(run_id, node['node_id']).values():
            try:
                manifest = store.read_record(ref, contract_id='delivery-manifest')
            except (ResearchError, ValueError, UnicodeError):
                continue
            # The report is both released by its node and named by its accepted
            # manifest. Candidate output and a plausible filename never suffice.
            accepted = store.accepted_outputs(run_id, node['node_id'])
            if manifest['report_ref'] not in accepted.values():
                raise ResearchError('integrity_fault', 'Delivery report lacks its exact node release')
            for item in manifest['files']:
                if item['role'] == 'report' and item['artifact_ref'] == manifest['report_ref'] and item['audience'] == 'researcher':
                    reports.append(item)
    if len(reports) != 1:
        raise ResearchError('unavailable', 'Completed workflow has no unique accepted researcher report')
    if delivery is not None:
        # Display/history needs this one released report, not a second complete
        # technical trace export. The same retrieval rules still verify it.
        from .inspection import build_retrieval
        file = {key: delivery['report'][key] for key in ('path', 'artifact_ref', 'media_type', 'audience')}
        exported, contents = build_retrieval(store, principal, run_id, run['account_id'], 'researcher',
                                             [file], allowed_refs=[file['artifact_ref']])
    else:
        exported, contents = await service.artifact_bytes(principal, run_id, audience='researcher')
    matches = [item for item in exported['files'] if item['path'] == reports[0]['path'] and item['media_type'] == 'text/markdown']
    if len(matches) != 1:
        raise ResearchError('unavailable', 'Accepted report is unavailable under the current disclosure policy')
    view = matches[0]
    result['report'] = {'content': contents[view['path']].decode('utf-8'), 'path': view['path'],
                        'accepted_ref': reports[0]['artifact_ref'], 'display_ref': view['artifact_ref'],
                        'redacted': view['artifact_ref'] != reports[0]['artifact_ref']}
    return result
