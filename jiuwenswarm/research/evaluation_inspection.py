"""Finite IF016r2 original evidence, independent of execution resources."""
from __future__ import annotations

import copy
import json
import math
import sqlite3
import time
from datetime import datetime

from .contracts import ResearchError, contract_schema, validate
from .evaluation_history import EvaluationReader, _strict_json, encoded
from .evaluation_projection import private_record, require
from .measurement import all_mandatory_pass, ordered_replay_outputs


def original(store, ref, kind, contract=None):
    require(store.record_kind(ref) == kind, 'Original evidence indexed kind differs', 'integrity_fault')
    value = store.read_record(ref, **({'contract_id': contract} if contract else {}))
    require(type(value) is dict, 'Original body is not a record', 'integrity_fault')
    return value


def private(store, ref, kind):
    value = private_record(store, ref, kind)
    require(value['id'] == ref['id'], 'Private body identity differs', 'integrity_fault')
    return value


def narrow(*values):
    return {key: min(value[key] for value in values) for key in ('time_s', 'model_calls', 'memory_mb')}


def finite(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def admitted_declaration(store, ref, admission_ref, snapshot=None):
    admission=original(store,admission_ref,'library-admission','library-admission')
    require(admission['status'] == 'admitted' and admission['candidate_ref'] == ref
        and admission['cc']['declaration_sha256'] == ref['sha256']
        and (snapshot is None or any(all(entry[key] == value for key,value in admission['cc'].items()) for entry in snapshot['entries'])),
        'Declaration has no exact original captured admission/snapshot','integrity_fault')
    with store._lock:
        row=store.connection.execute('SELECT kind FROM records WHERE id=?',(ref['id'],)).fetchone()
    require(row is None or row['kind'] == 'capsule-declaration','Admitted declaration has a foreign indexed kind','integrity_fault')
    declaration=store.read_record(ref,contract_id='capsule-declaration')
    identity=declaration['identity']
    require(admission['cc'] == {'cc_name':identity['name'],'cc_version':identity['version_label'],'declaration_sha256':ref['sha256']},
        'Admitted declaration body differs from original candidate pin','integrity_fault')
    return declaration,admission


def observation_identity(store, ref, observed, grant, child):
    # Source observations have their own immutable identity, not invocation_id.
    # The protected journal grant supplies that separate invocation association.
    from .checks.records import body_files_sha256
    binding=child['bindings'][0]
    declaration,_=admitted_declaration(store,binding['declaration_ref'],binding['admission_ref'])
    identity=declaration['identity']
    expected={**{key:child[key] for key in ('run_id','node_id','subnode_id','attempt_id','node_contract_ref','input_refs')},
        'id':ref['id'],'contract_ref':grant['contract_ref'],'binding_id':binding['id'],
        'cc_name':identity['name'],'cc_version':identity['version_label'],
        'declaration_sha256':binding['declaration_ref']['sha256'],'body_files_sha256':body_files_sha256(identity['body'])}
    require(all(observed[key] == value for key,value in expected.items()),
        'Original private observation differs from its exact assignment/body pins','integrity_fault')


def immutable_binding(store, binding, template_ref, declaration_ref, snapshot):
    """Only original captured admission/body pins; never current standing."""
    template = original(store, template_ref, 'subnode-template')
    require(binding['admission_ref'] == template['admission_ref'] and binding['declaration_ref'] == declaration_ref == template['capsule_ref'],
        'Original template/declaration admission association differs','integrity_fault')
    declaration,admission=admitted_declaration(store,declaration_ref,binding['admission_ref'],snapshot)
    identity = declaration['identity']
    pin = {'cc_name': identity['name'], 'cc_version': identity['version_label'],
           'declaration_sha256': declaration_ref['sha256']}
    require(binding['declaration_ref'] == declaration_ref and template['capsule_ref'] == declaration_ref
        and template['cc'] == pin and template['admission_ref'] == binding['admission_ref']
        and template['ports'] == declaration['ports'] and admission['cc'] == pin
        and admission['candidate_ref'] == declaration_ref and admission['status'] == 'admitted'
        and any(all(entry[key] == value for key, value in pin.items()) for entry in snapshot['entries']),
        'Original captured admission/template/snapshot differs', 'integrity_fault')
    body = [template['body_refs'][item['path']] for item in identity['body']]
    pins = [pin for row in declaration['needs']['external'] for key in ('pin', 'lockfile') if (pin := row.get(key))]
    dependencies = [template['body_refs'][pin['ref']] for pin in pins]
    require(binding['implementation_refs'] == body and binding['dependency_refs'] == dependencies
        and all(ref['sha256'] == item['sha256'] for ref, item in zip(body, identity['body']))
        and all(ref['sha256'] == item['sha256'] for ref, item in zip(dependencies, pins)),
        'Original implementation/dependency pins differ', 'integrity_fault')
    for ref in [*body, *dependencies]:
        store.read_blob(ref)
    return template, declaration, admission


def source_closure(store, runtime, request, scope):
    assets = original(store, runtime['assets_ref'], 'evaluation-assets')
    profile_record = original(store, runtime['profile_ref'], 'evaluation-profile', 'evaluation-profile')
    require(profile_record['library_snapshot_sha256'] == runtime['library_snapshot_ref']['sha256']
        and scope['limits'] == request['limits'], 'Original profile/scope limits differ', 'integrity_fault')
    cases = [case for case in assets['cases'] if case['case_id'] == request['case_id'] and case['entry_point'] == request['entry_point']]
    require(len(cases) == 1 and cases[0]['binding_ref'] == scope['source_binding_ref'],
        'Original approved case binding differs', 'integrity_fault')
    source = original(store, scope['source_contract_ref'], 'subnode-execution-contract', 'subnode-execution-contract')
    parent = original(store, source['node_contract_ref'], 'node-execution-contract', 'node-execution-contract')
    plan = original(store, scope['source_check_plan_ref'], 'bound-check-plan', 'bound-check-plan')
    snapshot = original(store, runtime['library_snapshot_ref'], 'library-snapshot', 'library-snapshot')
    require(len(source['bindings']) == 1 and source['bindings'][0]['role'] == 'work'
        and plan['contract_ref'] == scope['source_contract_ref'] and plan['node_contract_ref'] == source['node_contract_ref']
        and source['checking_profile_ref'] == plan['profile_ref']
        and source['configuration_ref'] == parent['configuration_ref'] == runtime['configuration_ref']
        and source['policy_ref'] == parent['policy_ref'] == plan['policy_ref'] == runtime['policy_ref'],
        'Original source/parent/check/configuration differs', 'integrity_fault')
    assignments = [entry for entry in parent['subnodes'] if entry['subnode_id'] == source['subnode_id']]
    require(len(assignments) == 1 and assignments[0]['role'] == 'work'
        and assignments[0]['template_ref'] == source['template_ref']
        and assignments[0]['capsule_ref'] == source['bindings'][0]['declaration_ref'],
        'Original source is not its exact parent assignment', 'integrity_fault')
    template, declaration, admission = immutable_binding(store, source['bindings'][0], source['template_ref'], assignments[0]['capsule_ref'], snapshot)
    require(template['subnode_id'] == source['subnode_id'] and template['role'] == 'work',
        'Original source template assignment differs', 'integrity_fault')
    for direction in ('inputs', 'outputs'):
        ports = {port['name']: port for port in declaration['ports'][direction]}
        names = [port['name'] for port in source[direction]]
        require(len(names) == len(set(names)) and set(names) <= set(ports)
            and {name for name, port in ports.items() if port['required']} <= set(names)
            and (direction != 'outputs' or set(names) == set(ports))
            and all(port['required'] == ports[port['name']]['required']
                and contract_schema(port['contract_id']) == contract_schema(ports[port['name']]['schema_ref']) for port in source[direction]),
            'Original source declared ports differ', 'integrity_fault')
    require(source['input_refs'] == [ref for port in source['inputs'] for ref in port['artifact_refs']]
        and source['required_outputs'] == [port['name'] for port in source['outputs'] if port['required']],
        'Original source concrete port inventory differs', 'integrity_fault')
    for ref in source['input_refs']:
        store.read_blob(ref)
    bundle = original(store, template['check_bundle_ref'], 'check-bundle', 'check-bundle')
    profile = original(store, plan['profile_ref'], 'checking-profile', 'checking-profile')
    mandatory = {row['check_id'] for row in bundle['checks'] if row['blocking']} | {'host_contract', 'host_identity', 'host_limits', 'host_authority'}
    require(mandatory <= set(plan['mandatory_deterministic']) and template['check_bundle_ref'] in plan['runner_refs']
        and set(plan['mandatory_semantic']) == {row['criterion_id'] for row in profile['criteria'] if row['blocking']},
        'Original source mandatory checking closure differs', 'integrity_fault')
    for ref in plan['runner_refs']:
        store.read_blob(ref)
    output_map, observed = {}, None
    if request['entry_point'] == 'E2':
        binding = original(store, scope['source_binding_ref'], 'evaluation-case-binding')
        legacy = {'id','contract_ref','check_plan_ref','output_refs','original_observation_ref','host_records','verifier_cc_id'}
        require(type(binding.get('output_refs')) is dict and 0 < len(binding['output_refs']) <= 64
            and all(isinstance(name,str) and bool(name) for name in binding['output_refs'])
            and (set(binding) == legacy or set(binding) == legacy | {'schema','selected_output_port'}
                and binding['schema'] == 'ai4r-node-replay-binding:2')
            and (set(binding) != legacy or len(binding['output_refs']) == 1)
            and binding['contract_ref'] == scope['source_contract_ref'] and binding['check_plan_ref'] == scope['source_check_plan_ref']
            and binding['original_observation_ref'] == scope['source_observation_ref'],
            'Original replay binding differs', 'integrity_fault')
        observed = original(store, scope['source_observation_ref'], 'invocation-observation', 'invocation-observation')
        output_map = ordered_replay_outputs(binding['output_refs'], observed['output_refs'])
        if set(binding) != legacy:
            require(isinstance(binding['selected_output_port'],str) and bool(binding['selected_output_port'])
                and binding['selected_output_port'] in output_map, 'Original explicit replay selection is malformed', 'integrity_fault')
        selected = binding['selected_output_port'] if set(binding) != legacy else next(iter(output_map))
        require(observed['contract_ref'] == scope['source_contract_ref']
            and list(output_map.values()) == scope['source_output_refs'] == observed['output_refs']
            and selected == scope['selected_output_port'], 'Original replay output/observation/selected port differs', 'integrity_fault')
    else:
        require(scope['source_binding_ref'] == scope['source_contract_ref'] and scope['source_observation_ref'] is None
            and not scope['source_output_refs'] and scope['selected_output_port'] is None,
            'Single source masquerades as replay', 'integrity_fault')
    return {'source': source, 'parent': parent, 'plan': plan, 'template': template, 'declaration': declaration,
            'admission': admission, 'snapshot': snapshot, 'profile': profile, 'case': cases[0], 'outputs': output_map, 'observed': observed}


def parent_projection(store, ref, request_ref, request, scope, source):
    value = private(store, ref, 'evaluation-node-context')
    expected = {key: copy.deepcopy(source['parent'][key]) for key in
        'node_id objective requirement_ids inputs outputs input_refs required_outputs evidence_obligations authority_ceiling subnodes checking_profile_ref policy_ref configuration_ref'.split()}
    expected.update(schema='ai4r-evaluation-node-context:1', id=value['id'], request_ref=request_ref,
        source_binding_ref=scope['source_binding_ref'], source_contract_ref=scope['source_contract_ref'],
        source_node_ref=source['source']['node_contract_ref'], source_template_ref=source['parent']['template_ref'],
        source_check_plan_ref=scope['source_check_plan_ref'], run_id=scope['private_run_id'],
        attempt_id=source['parent']['node_id'] + '-a1', revision=1,
        node_limits=narrow(source['parent']['node_limits'], request['limits']),
        started_unix_ns=request['started_unix_ns'], deadline_unix_ns=request['deadline_unix_ns'], accepted=False, invalid_for_product=True)
    require(value == expected, 'Private parent differs from its original projection', 'integrity_fault')
    return value


def assignment_proof(store, grant_ref, request_ref, scope_ref, request, scope, parent, source):
    grant = private(store, grant_ref, 'evaluation-assignment-grant')
    child = private(store, grant['contract_ref'], 'evaluation-subnode-context')
    basis = private(store, grant['check_plan_ref'], 'evaluation-checking-basis')
    with store._lock:
        row = store.connection.execute('SELECT * FROM evaluation_assignments WHERE execution_id=?', (grant['execution_id'],)).fetchone()
    require(row is not None and _strict_json(row['grant_ref'].encode()) == grant_ref and row['request_ref'] == encoded(request_ref)
        and row['role'] == grant['role'] == child['role'] and row['port'] == (grant['output_port'] or '')
        and grant['request_ref'] == request_ref == child['request_ref'] == basis['request_ref']
        and grant['scope_ref'] == scope_ref and child['node_contract_ref'] == scope['actual_node_ref']
        and basis['node_context_ref'] == scope['actual_node_ref'] and basis['assignment_context_ref'] == grant['contract_ref']
        and grant['source_contract_ref'] == scope['source_contract_ref'] == child['source_subject_ref'] == basis['source_contract_ref']
        and grant['output_port'] == child['output_port'] and grant['deadline_unix_ns'] == request['deadline_unix_ns'],
        'Private assignment durable ownership differs', 'integrity_fault')
    original_source, original_plan = source['source'], source['plan']
    if grant['role'] == 'worker':
        require(request['entry_point'] == 'E3' and grant['output_port'] is None, 'Private worker is outside its approved schedule', 'integrity_fault')
        expected = {key: copy.deepcopy(original_source[key]) for key in
            'node_id subnode_id objective requirement_ids bindings inputs outputs input_refs required_outputs evidence_obligations checking_profile_ref policy_ref configuration_ref'.split()}
        expected.update(schema='ai4r-evaluation-subnode-context:1', id=child['id'], request_ref=request_ref,
            node_contract_ref=scope['actual_node_ref'], source_subject_ref=scope['source_contract_ref'], source_template_ref=original_source['template_ref'],
            role='worker', output_port=None, run_id=parent['run_id'], attempt_id=parent['attempt_id'], revision=1,
            subnode_limits=narrow(original_source['subnode_limits'], request['limits']), accepted=False, invalid_for_product=True)
        expected['bindings'][0]['limits'] = narrow(original_source['bindings'][0]['limits'], expected['subnode_limits'])
        mandatory, runners, mode = original_plan['mandatory_deterministic'], original_plan['runner_refs'], 'worker_output'
    else:
        port = grant['output_port']
        require(request['entry_point'] == 'E2' and port == scope['selected_output_port'], 'Private reviewer is outside its approved schedule', 'integrity_fault')
        candidates = []
        for assignment in source['parent']['subnodes']:
            if assignment['role'] != 'verifier':
                continue
            template = original(store, assignment['template_ref'], 'subnode-template')
            if template.get('subject_subnode_id') == original_source['subnode_id'] and template.get('output_port') == port:
                candidates.append((assignment, template))
        require(len(candidates) == 1, 'No exact original selected reviewer', 'integrity_fault')
        assignment, template = candidates[0]
        _, declaration, admission = immutable_binding(store, child['bindings'][0], assignment['template_ref'], assignment['capsule_ref'], source['snapshot'])
        from .binding import ContractFactory
        outputs = [{'name': p['name'], 'contract_id': p['schema_ref'], 'version': ContractFactory._version(p['schema_ref']), 'required': p['required']} for p in declaration['ports']['outputs']]
        inputs = [{'name': name, 'contract_id': contract, 'version': ContractFactory._version(contract), 'required': True, 'artifact_refs': [ref]}
            for name, contract, ref in [('subject_declaration', 'capsule-declaration', original_source['bindings'][0]['declaration_ref']),
                                        ('subject_output', 'opaque-bytes', source['outputs'][port])]]
        limits = narrow({'time_s': min(declaration['budget']['per_call']['wall_s'], source['profile']['time_s']),
            'model_calls': 1, 'memory_mb': admission['memory_mb']}, parent['node_limits'], request['limits'])
        require(source['profile']['model_call_limit'] == 1 and limits['model_calls'] == 1, 'Original selected reviewer limits differ', 'integrity_fault')
        expected = {key: copy.deepcopy(original_source[key]) for key in ('node_id', 'objective', 'requirement_ids', 'evidence_obligations', 'policy_ref', 'configuration_ref')}
        authority = {'network': 'none', 'network_allowlist': [], 'resource_reads': [ref for p in inputs for ref in p['artifact_refs']], 'write_roots': [], 'tools': []}
        binding = copy.deepcopy(child['bindings'][0]); binding.update(id=assignment['subnode_id'] + '.binding', role='verifier', effective_authority=authority, limits=limits)
        expected.update(schema='ai4r-evaluation-subnode-context:1', id=child['id'], request_ref=request_ref,
            node_contract_ref=scope['actual_node_ref'], source_subject_ref=scope['source_contract_ref'], source_template_ref=assignment['template_ref'], role='verifier', output_port=port,
            run_id=scope['private_run_id'], subnode_id=assignment['subnode_id'], attempt_id=parent['attempt_id'], revision=1, bindings=[binding],
            inputs=inputs, outputs=outputs, input_refs=authority['resource_reads'], required_outputs=[p['name'] for p in outputs if p['required']],
            subnode_limits=limits, checking_profile_ref=template['checking_profile_ref'], accepted=False, invalid_for_product=True)
        bundle = original(store, template['check_bundle_ref'], 'check-bundle', 'check-bundle')
        mandatory = list(dict.fromkeys([*[row['check_id'] for row in bundle['checks'] if row['blocking']], 'host_contract', 'host_identity', 'host_limits', 'host_authority']))
        runners = list({ref['sha256']: ref for ref in [template['check_bundle_ref'], *[row['runner_ref'] for row in bundle['checks']]]}.values())
        mode = 'verifier_output'
    expected_basis = {'schema': 'ai4r-evaluation-checking-basis:1', 'id': basis['id'], 'request_ref': request_ref,
        'node_context_ref': scope['actual_node_ref'], 'assignment_context_ref': grant['contract_ref'],
        'source_contract_ref': scope['source_contract_ref'], 'source_check_plan_ref': scope['source_check_plan_ref'],
        'source_template_ref': child['source_template_ref'], 'mode': mode, 'input_refs': expected['input_refs'],
        'profile_ref': original_plan['profile_ref'], 'policy_ref': original_plan['policy_ref'], 'mandatory_deterministic': mandatory,
        'mandatory_semantic': [], 'runner_refs': runners, 'output_port': grant['output_port'], 'accepted': False, 'invalid_for_product': True}
    require(child == expected and basis == expected_basis and len(child['bindings']) == 1
        and grant['limits'] == child['bindings'][0]['limits'], 'Private child/checking basis differs from original projection', 'integrity_fault')
    return grant, child, basis, dict(row)


def supporting_proof(store, reader, request_ref, request, row, scope_ref, scope, source, parent, events, terminal, grants):
    """Validate exact supporting bodies for EVERY terminal state before use."""
    captured = [event for _, event in events if event['kind'] == 'captured']
    def owned(kind, ref):
        matches = [event for event in captured if event['capture_kind'] == kind and event['capture_ref'] == ref]
        require(matches and all(event['assignment_grant_ref'] == matches[0]['assignment_grant_ref'] for event in matches),
            'Supporting evidence has no unambiguous local original attribution', 'integrity_fault')
        return matches[0]
    for key, fields in [('result_ref', {'id', 'result', 'accepted', 'invalid_for_product'}),
                         ('failure_ref', {'id', 'reason', 'accepted', 'invalid_for_product'})]:
        ref = terminal[key]
        if ref is None:
            continue
        value = original(store, ref, 'evaluation-' + key.removesuffix('_ref'))
        require(set(value) == fields and value['accepted'] is False and value['invalid_for_product'] is True
            and owned(key.removesuffix('_ref'), ref)['assignment_grant_ref'] is None,
            'Supporting wrapper shape/attribution differs', 'integrity_fault')
        if key == 'failure_ref':
            require(isinstance(value['reason'], str) and bool(value['reason']), 'Missing original failure reason', 'integrity_fault')
    ref = terminal['containment_ref']
    if ref is not None:
        receipt = original(store, ref, 'evaluation-containment')
        require(set(receipt) == {'id', 'request_ref', 'scope_ref', 'cancel_id', 'no_started_assignments', 'receipts', 'accepted', 'invalid_for_product'}
            and receipt['request_ref'] == request_ref and receipt['scope_ref'] == scope_ref and receipt['cancel_id'] == row['cancel_id']
            and isinstance(receipt['cancel_id'], str) and bool(receipt['cancel_id'])
            and type(receipt['no_started_assignments']) is bool and type(receipt['receipts']) is list
            and receipt['accepted'] is False and receipt['invalid_for_product'] is True
            and owned('containment', ref)['assignment_grant_ref'] is None,
            'Original containment body/ownership differs', 'integrity_fault')
        started = [event for _, event in events if event['kind'] == 'assignment_started']
        require(receipt['no_started_assignments'] == (not started)
            and (not started or bool(receipt['receipts']))
            and all(type(item) is dict and item.get('contained') is True
                and item.get('run_id') == scope['private_run_id'] and item.get('request_id') == row['cancel_id'] for item in receipt['receipts']),
            'Original containment acknowledgments differ', 'integrity_fault')
    measured = []
    for ref in terminal['measurement_refs']:
        event = owned('measurement', ref)
        value = original(store, ref, 'evaluation-trial-measurement')
        require(set(value) == {'id','contract_ref','accepted','status','output_refs','deterministic_ref','observation_ref',
            'assessment_refs','verifier_check_refs','observation_refs','trace_refs','failure','elapsed_s','recorded_at'}
            and value['accepted'] is False and value['status'] in {'completed','failed','blocked','interrupted'}
            and finite(value['elapsed_s']) and type(value['output_refs']) is dict,
            'Original trial measurement shape differs', 'integrity_fault')
        worker = request['entry_point'] == 'E3'
        if worker:
            matches = [proof for proof in grants.values() if proof[0]['role'] == 'worker' and proof[0]['contract_ref'] == value['contract_ref']]
            require(len(matches) == 1 and event['assignment_grant_ref'] == _strict_json(matches[0][3]['grant_ref'].encode()),
                'Measurement belongs to another worker', 'integrity_fault')
            grant, child, basis, _ = matches[0]
            observation_event = owned('observation', value['observation_ref'])
            observed = original(store, value['observation_ref'], 'evaluation-invocation-observation', 'invocation-observation')
            observation_identity(store,value['observation_ref'],observed,grant,child)
            require(observed['contract_ref'] == grant['contract_ref']
                and observation_event['assignment_grant_ref'] == _strict_json(matches[0][3]['grant_ref'].encode())
                and observed['run_id'] == scope['private_run_id'] and observed['node_id'] == child['node_id']
                and observed['attempt_id'] == child['attempt_id']
                and sorted(encoded(ref) for ref in observed['output_refs']) == sorted(encoded(ref) for ref in value['output_refs'].values()),
                'Measurement original worker observation differs', 'integrity_fault')
            ordered_replay_outputs(value['output_refs'], observed['output_refs'])
            require(not set(value['output_refs']) - {port['name'] for port in child['outputs']}
                and (value['status'] != 'completed' or set(child['required_outputs']) <= set(value['output_refs'])),
                'Measurement named outputs differ from the original child ports', 'integrity_fault')
            for port, output in value['output_refs'].items():
                require(any(event['capture_kind'] == 'output' and event['capture_ref'] == output
                    and event['assignment_grant_ref'] == observation_event['assignment_grant_ref'] for event in captured),
                    'Named worker output lacks its original assignment capture', 'integrity_fault')
        else:
            require(value['contract_ref'] == scope['source_contract_ref'] and value['observation_ref'] == scope['source_observation_ref']
                and value['output_refs'] == source['outputs'], 'Replay measurement changed original source', 'integrity_fault')
            observed = source['observed']
        checked = original(store, value['deterministic_ref'], 'evaluation-deterministic-check-result', 'deterministic-check-result')
        check_event = owned('deterministic_result', value['deterministic_ref'])
        basis = private(store, checked['check_plan_ref'], 'evaluation-checking-basis')
        require(basis['request_ref'] == request_ref and basis['node_context_ref'] == scope['actual_node_ref']
            and basis['source_contract_ref'] == scope['source_contract_ref'] and basis['source_check_plan_ref'] == scope['source_check_plan_ref']
            and basis['mode'] == ('worker_output' if worker else 'replay_subject')
            and basis['assignment_context_ref'] == (value['contract_ref'] if worker else None)
            and basis['profile_ref'] == source['plan']['profile_ref'] and basis['policy_ref'] == source['plan']['policy_ref']
            and basis['mandatory_deterministic'] == source['plan']['mandatory_deterministic']
            and basis['runner_refs'] == source['plan']['runner_refs']
            and basis['source_template_ref'] == source['source']['template_ref']
            and basis['input_refs'] == source['source']['input_refs']
            and basis['output_port'] == (None if worker else scope['selected_output_port'])
            and basis['mandatory_semantic'] == ([] if worker else [row['criterion_id'] for row in source['profile']['criteria']
                if row['blocking'] and row['target_port'] in (None, scope['selected_output_port'])])
            and check_event['assignment_grant_ref'] == (observation_event['assignment_grant_ref'] if worker else None),
            'Measurement checking basis differs from its original source', 'integrity_fault')
        subjects = [ref for ref in observed['output_refs'] if ref in value['output_refs'].values()] or [value['observation_ref']]
        require(checked['subject_ref'] == subjects[0] and checked.get('subject_refs', [checked['subject_ref']]) == subjects
            and set(basis['mandatory_deterministic']) <= {item['check_id'] for item in checked['results']},
            'Measurement checks target another original subject', 'integrity_fault')
        for port, output in value['output_refs'].items():
            store.read_blob(output)
            if worker:
                owned('output', output)
        for kind, refs in [('assessment', value['assessment_refs']), ('verifier_check', value['verifier_check_refs']), ('observation', value['observation_refs'])]:
            for pin in refs:
                capture = owned(kind, pin)
                require(capture['assignment_grant_ref'] is not None and encoded(capture['assignment_grant_ref']) in grants,
                    'Reviewer evidence has no exact private assignment', 'integrity_fault')
                reader._capture(kind, pin, request_ref, scope_ref, scope, capture['assignment_grant_ref'])
        require(len(value['assessment_refs']) == len(value['verifier_check_refs']), 'Reviewer evidence inventories differ', 'integrity_fault')
        for assessment_ref, verifier_ref in zip(value['assessment_refs'], value['verifier_check_refs']):
            assessment_event = owned('assessment', assessment_ref)
            reviewer_grant, reviewer_child, reviewer_basis, _ = grants[encoded(assessment_event['assignment_grant_ref'])]
            assessment = original(store, assessment_ref, 'evaluation-verifier-assessment', 'verifier-assessment')
            review_ref = assessment['review_context_ref']
            require(owned('review_context', review_ref)['assignment_grant_ref'] == assessment_event['assignment_grant_ref'],
                'Review context belongs to another assignment', 'integrity_fault')
            review = original(store, review_ref, 'evaluation-review-context', 'review-context')
            output_ref = value['output_refs'][reviewer_grant['output_port']]
            require(review['contract_ref'] == value['contract_ref'] and review['check_plan_ref'] == checked['check_plan_ref']
                and review['subject_ref'] == output_ref and review['deterministic_result_ref'] == value['deterministic_ref']
                and review['observations'] == [value['observation_ref']], 'Review context targets another original subject', 'integrity_fault')
            from .gate import assemble_assessment, zip_projection
            if assessment['subject_ref'] != output_ref:
                require(store.read_blob(assessment['subject_ref']) == zip_projection(store.read_blob(output_ref)),
                    'Assessment targets different bytes', 'integrity_fault')
            criteria = [criterion for criterion in source['profile']['criteria'] if criterion['target_port'] in (None, reviewer_grant['output_port'])]
            body = {key: assessment[key] for key in ('uncertainties','limitations','required_correction')}
            body['findings'] = [{key: finding[key] for key in ('criterion_id','outcome','reason')} for finding in assessment['findings']]
            require(assemble_assessment(body, criteria, source['source']['bindings'][0]['declaration_ref'],
                assessment['subject_ref'], review_ref) == assessment, 'Assessment differs from the exact frozen profile', 'integrity_fault')
            verifier = original(store, verifier_ref, 'evaluation-deterministic-check-result', 'deterministic-check-result')
            require(owned('verifier_check', verifier_ref)['assignment_grant_ref'] == assessment_event['assignment_grant_ref']
                and verifier['check_plan_ref'] == reviewer_grant['check_plan_ref'] and verifier['subject_ref'] == assessment_ref
                and all_mandatory_pass(reviewer_basis, verifier['results']), 'Reviewer checks do not close the exact assessment', 'integrity_fault')
            observations = []
            for ref in value['observation_refs']:
                if owned('observation',ref)['assignment_grant_ref'] != assessment_event['assignment_grant_ref']:continue
                observation=original(store,ref,'evaluation-invocation-observation','invocation-observation')
                observation_identity(store,ref,observation,reviewer_grant,reviewer_child)
                observations.append(observation)
            require(observations and all(observation['contract_ref'] == reviewer_grant['contract_ref']
                and assessment_ref in observation['output_refs'] for observation in observations),
                'Reviewer original observations differ', 'integrity_fault')
        measured.append((ref, value, observed, checked))
    if terminal['result_ref'] is not None:
        require(len(measured) == 1, 'Original response needs exactly one measurement', 'integrity_fault')
        pin, value, observed, checked = measured[0]
        result = store.read_record(terminal['result_ref'])['result']
        require(type(result) is dict and result.get('invalid_for_product') is True
            and finite(result.get('duration_s')) and result['duration_s'] >= value['elapsed_s'],
            'Result duration/origin differs from its actual measurement', 'integrity_fault')
        if request['entry_point'] == 'E3':
            from .evaluation_provider import single_cc_check_results
            require(set(result) == {'invocation_id','status','output_refs','check_results','tool_effects_observed','model_calls','reason','duration_s','invalid_for_product'}
                and result['invocation_id'] == observed['id'] and result['status'] == value['status']
                and result['output_refs'] == value['output_refs']
                and result['check_results'] == single_cc_check_results(store,value)
                and result['tool_effects_observed'] == (observed['effects'] or None)
                and result['reason'] == (value['failure'] or ('Complete tool-effect observation unavailable' if not observed['effects'] else None)),
                'Result differs from original worker measurement', 'integrity_fault')
        else:
            eligible = all_mandatory_pass(source['plan'], checked['results'])
            assessment = value['assessment_refs'][0] if value['assessment_refs'] else None
            verdict = original(store, assessment, 'evaluation-verifier-assessment', 'verifier-assessment')['verdict'] if eligible and assessment and not value['failure'] else 'FAIL'
            action = 'advance' if verdict in {'PASS','PASS_WITH_KNOWN_LIMITATIONS'} and not value['failure'] else 'halt'
            decision = {'contract_ref': scope['source_contract_ref'], 'check_plan_ref': checked['check_plan_ref'],
                'output_port': scope['selected_output_port'], 'output_refs': [value['output_refs'][scope['selected_output_port']]],
                'deterministic_result_ref': value['deterministic_ref'], 'assessment_ref': assessment,
                'verifier_check_ref': value['verifier_check_refs'][0] if value['verifier_check_refs'] else None,
                'verdict': verdict, 'action': action, 'reasons': [value['failure'] or 'All mandatory checks and selected semantic criteria passed'],
                'accepted': False, 'invalid_for_product': True}
            require(set(result) == {'replay_id','tier1_verdict','tier2_verdict','gate_decision','advanced','persisted_at',
                'downstream_action','reason','evidence_refs','model_calls','duration_s','invalid_for_product'}
                and isinstance(result['replay_id'], str) and result['replay_id']
                and result['tier1_verdict'] == ('PASS' if eligible else 'FAIL')
                and result['tier2_verdict'] == (original(store, assessment, 'evaluation-verifier-assessment', 'verifier-assessment')['verdict'] if assessment else 'NOT_RUN')
                and result['gate_decision'] == decision and result['reason'] == value['failure'],
                'Replay result differs from original selected measurement', 'integrity_fault')
            if source['case']['record_gate']:
                require(len(result['evidence_refs']) == 2 and result['evidence_refs'][0] == pin, 'Recording evidence inventory differs', 'integrity_fault')
                gate_ref = result['evidence_refs'][1]; gate = original(store, gate_ref, 'evaluation-gate-record')
                require(owned('evaluation_gate', gate_ref)['assignment_grant_ref'] is None
                    and set(gate) == {'id','decision','persisted_at','invalid_for_product'} and gate['decision'] == decision
                    and gate['persisted_at'] == result['persisted_at'] and gate['invalid_for_product'] is True
                    and result['advanced'] is (action == 'advance') and result['downstream_action'] == ('started' if action == 'advance' else 'halted'),
                    'Recording Gate differs from its original decision', 'integrity_fault')
                actions = [original(store, event['capture_ref'], 'evaluation-recording-downstream-action') for event in captured
                    if event['capture_kind'] == 'recording_action']
                require(len(actions) == 1 and set(actions[0]) == {'id','gate_ref','at','action','scheduler_kind','invalid_for_product'}
                    and actions[0]['gate_ref'] == gate_ref and actions[0]['action'] == result['downstream_action']
                    and actions[0]['scheduler_kind'] == 'recording' and actions[0]['invalid_for_product'] is True,
                    'Recording action differs from its original Gate', 'integrity_fault')
            else:
                require(result['evidence_refs'] == [pin] and result['advanced'] is False and result['persisted_at'] is None
                    and result['downstream_action'] == 'locked', 'Unrecorded replay claims a downstream action', 'integrity_fault')
        calls = result.get('model_calls')
        require(type(calls) is list, 'Response ModelCall inventory is missing', 'integrity_fault')
        contracts = [original(store, ref, 'evaluation-invocation-observation', 'invocation-observation')['contract_ref']
            for ref in value['observation_refs']]
        if request['entry_point'] == 'E3':
            contracts.append(value['contract_ref'])
        starts = []
        for event in captured:
            if event['capture_kind'] != 'model_start':
                continue
            start = original(store, event['capture_ref'], 'model-call-start')
            if start['contract_ref'] in contracts:
                starts.append((event, start))
        require(len(calls) == len(starts), 'Response omitted an original measured ModelCall', 'integrity_fault')
        for call, (start_event, start) in zip(calls, starts):
            require(type(call) is dict and set(call) == {'call_ref','role','requested_model','effective_model','identity_basis',
                'duration_s','outcome','input_tokens','output_tokens','cost'}, 'Response ModelCall fields differ', 'integrity_fault')
            event = owned('model_call', call['call_ref'])
            require(event['assignment_grant_ref'] is not None and encoded(event['assignment_grant_ref']) in grants,
                'Response ModelCall has no owned original assignment', 'integrity_fault')
            grant, _, _, _ = grants[encoded(event['assignment_grant_ref'])]
            body = original(store, call['call_ref'], 'model-call', 'model-call')
            claim = private(store, start['call_claim_ref'], 'evaluation-call-claim')
            claim_event = owned('model_claim', start['call_claim_ref'])
            with store._lock:
                claimed = store.connection.execute('SELECT * FROM evaluation_calls WHERE execution_id=? AND call_id=?',
                    (grant['execution_id'], start['call_id'])).fetchone()
            require(claimed is not None and _strict_json(claimed['claim_ref'].encode()) == start['call_claim_ref']
                and claim['request_ref'] == request_ref and claim['scope_ref'] == scope_ref
                and claim['assignment_grant_ref'] == event['assignment_grant_ref'] == start_event['assignment_grant_ref'] == claim_event['assignment_grant_ref']
                and all(claim[k] == start[k] for k in ('execution_id','invocation_id','contract_ref','call_id'))
                and claim['call_ordinal'] == claimed['ordinal'] and body['id'] == start['call_id']
                and body['invocation_id'] == start['invocation_id'] and body['execution_id'] == start['execution_id'],
                'Response ModelCall differs from its original protected start/claim', 'integrity_fault')
            unknown = body['outcome'] == 'outcome_unknown'
            require((body['ended_at'] is None) == unknown, 'ModelCall completion chronology differs', 'integrity_fault')
            duration = None if unknown else (datetime.fromisoformat(body['ended_at'].replace('Z','+00:00'))
                - datetime.fromisoformat(body['started_at'].replace('Z','+00:00'))).total_seconds()
            cost = {'amount': body['usage']['cost_amount'], 'currency': body['usage']['currency']} if body['usage']['cost_amount'] is not None else None
            require(body['invocation_id'] == grant['invocation_id'] and body['execution_id'] == grant['execution_id']
                and call['role'] == (body['call_function'] if body['call_function'] in {'compiler','planner','worker','verifier','router','delivery'} else 'other')
                and call['duration_s'] == duration and (duration is None or finite(duration)) and call['cost'] == cost
                and call['outcome'] == body['outcome'] and call['requested_model'] == body['identity']['requested']
                and call['effective_model'] == body['identity']['effective'] and call['identity_basis'] == body['identity']['basis']
                and call['input_tokens'] == body['usage']['input_tokens'] and call['output_tokens'] == body['usage']['output_tokens'],
                'Response ModelCall differs from original native identity/usage', 'integrity_fault')


def _inspect_executor_binding(store, request, *, live_owner=None):
    fields = {'contract_ref', 'invocation_id', 'execution_id'}
    require(type(request) is dict and set(request) == fields
        and all(isinstance(request[key], str) and bool(request[key]) for key in ('invocation_id','execution_id')),
        'Malformed exact private inspection binding')
    validate('Ref', request['contract_ref'])
    if live_owner is not None:
        from .evaluation_authority import EvaluationAuthority
        require(type(live_owner) is EvaluationAuthority and live_owner.store is store
            and live_owner.runner.store is store, 'Actual same installed Store/Runner owner required')
    child = private(store, request['contract_ref'], 'evaluation-subnode-context')
    with store._lock:
        assignment = store.connection.execute('SELECT * FROM evaluation_assignments WHERE execution_id=?', (request['execution_id'],)).fetchone()
    require(assignment is not None, 'No exact registered private inspection assignment')
    grant_ref = _strict_json(assignment['grant_ref'].encode())
    grant = private(store, grant_ref, 'evaluation-assignment-grant')
    require(all(grant[key] == request[key] for key in fields) and child['request_ref'] == grant['request_ref'],
        'Inspection binding differs from exact original grant', 'integrity_fault')
    source_request = private(store, grant['request_ref'], 'evaluation-request')
    reader = EvaluationReader(store, runtime_ref=source_request['runtime_ref'])
    with store._lock:
        row = store.connection.execute('SELECT * FROM evaluation_requests WHERE request_ref=?', (encoded(grant['request_ref']),)).fetchone()
    require(row is not None, 'Private inspection has no exact original request')
    runtime, _, request_ref, actual_request, row, scope_ref, scope = reader._owned_row(dict(row), source_request['request_id'])
    require(request_ref == grant['request_ref'] and scope is not None and scope_ref == grant['scope_ref'],
        'Private inspection scope differs from its exact grant', 'integrity_fault')
    source = source_closure(store, runtime, actual_request, scope)
    parent = parent_projection(store, scope['actual_node_ref'], request_ref, actual_request, scope, source)
    _, events = reader._journal(request_ref, row, scope_ref)
    grants = {}
    for _, event in events:
        ref = event['assignment_grant_ref']
        if ref is not None and encoded(ref) not in grants:
            grants[encoded(ref)] = assignment_proof(store, ref, request_ref, scope_ref, actual_request, scope, parent, source)
    require(encoded(grant_ref) in grants, 'Binding grant has no original local journal attribution', 'integrity_fault')
    terminal = reader._terminal(request_ref, row, scope_ref, events)
    if terminal is not None:
        through = [index for index, (ref, _) in enumerate(events) if ref == terminal['through_event_ref']]
        require(len(through) == 1, 'Terminal original evidence prefix is unavailable', 'integrity_fault')
        original_events = events[:through[0] + 1]
        require(any(event['assignment_grant_ref'] == grant_ref for _,event in original_events),
            'Terminal binding has no original pre-publication assignment attribution', 'integrity_fault')
        supporting_proof(store, reader, request_ref, actual_request, row, scope_ref, scope, source, parent, original_events, terminal, grants)
        state = terminal['state']
    else:
        require(row['state'] in {'claimed','prepared','executing','cancelling'}, 'Unpublished row falsely claims a terminal', 'integrity_fault')
        state = 'outcome_unknown'
        if live_owner is not None:
            if live_owner in live_owner.runner._evaluation_owners and live_owner.runtime_ref == actual_request['runtime_ref']:
                with store._lock:
                    boot = store.connection.execute('SELECT boot FROM evaluation_owner_boots WHERE runtime=?', (row['runtime'],)).fetchone()
                execution = live_owner.runner._executions.get(request['execution_id'])
                deadline = live_owner._deadlines.get(encoded(request_ref))
                if (boot is not None and boot['boot'] == row['boot'] == live_owner._boot
                    and row['state'] == 'executing' and row['cancel_id'] is None and assignment['state'] == 'started'
                    and execution is not None and execution.get('evaluation_owner') is live_owner
                    and execution.get('evaluation_grant_ref') == grant_ref and execution.get('contract_ref') == request['contract_ref']
                    and execution.get('contract') == child and execution.get('invocation_id') == request['invocation_id']
                    and execution.get('closed') is False and finite(deadline) and time.monotonic() < deadline
                    and finite(execution.get('deadline')) and time.monotonic() < execution['deadline']
                    and time.time_ns() < actual_request['deadline_unix_ns']):
                    state = 'nonterminal'
    return {**copy.deepcopy(request), 'state': state, 'request_ref': request_ref, 'scope_ref': scope_ref,
        'assignment_grant_ref': grant_ref, 'terminal_ref': _strict_json(row['terminal_ref'].encode()) if row['terminal_ref'] else None,
        'containment_ref': terminal['containment_ref'] if terminal else None, 'cancel_id': row['cancel_id']}


def inspect_executor_binding(store, request, *, live_owner=None):
    try:
        return _inspect_executor_binding(store, request, live_owner=live_owner)
    except ResearchError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, UnicodeError, AttributeError, sqlite3.Error) as error:
        raise ResearchError('integrity_fault', 'Original private inspection closure is malformed or unavailable') from error
