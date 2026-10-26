"""Data-only interruption capture by the sole Store owner at startup.

Original consumed dispatch and canonical claims establish that the node began.
This module never reconstructs a worker completion, Gate, physical cessation,
native lease release or permission to replay an effect.
"""
from __future__ import annotations

import hashlib
import json

from .contracts import ResearchError, validate
from .state import json_bytes


def _require(condition):
    if not condition:
        raise ResearchError('restart_evidence_unavailable', 'Original interrupted dispatch closure is unavailable')


def _original(store, db, ref, kind, *, scope=None, contract=None):
    validate('Ref', ref)
    row = db.execute('SELECT rowid,* FROM records WHERE id=?', (ref['id'],)).fetchone()
    _require(row is not None and row['kind'] == kind)
    value = store.read_record(ref, **({'contract_id': contract} if contract else {}))
    _require(type(value) is dict)
    if scope:
        for key, expected in scope.items():
            _require(row[key] == expected and (kind == 'bound-check-plan' or value.get(key) == expected))
    return value, row['rowid']


def _pins(store, db, template):
    bundle, _ = _original(store, db, template['check_bundle_ref'], 'check-bundle', contract='check-bundle')
    profile, _ = _original(store, db, template['checking_profile_ref'], 'checking-profile', contract='checking-profile')
    return {'check_bundle_id': bundle['bundle_id'], 'check_bundle_version': bundle['version'],
        'check_bundle_sha256': template['check_bundle_ref']['sha256'],
        'checking_profile_id': profile['profile_id'], 'checking_profile_version': profile['version'],
        'checking_profile_sha256': template['checking_profile_ref']['sha256']}


def _source(store, db, ref, kind):
    # Installed typed source assets may be captured as unindexed original
    # blobs. A foreign indexed kind is never treated as that source asset.
    row = db.execute('SELECT kind FROM records WHERE id=?', (ref['id'],)).fetchone()
    _require(row is None or row['kind'] == kind)
    return store.read_record(ref, contract_id=kind)


def _declaration(store, db, assignment, template):
    ref = assignment['capsule_ref']
    declaration = _source(store, db, ref, 'capsule-declaration')
    identity = declaration['identity']
    pin = {'cc_name': identity['name'], 'cc_version': identity['version_label'],
        'declaration_sha256': ref['sha256']}
    admission, _ = _original(store, db, template['admission_ref'], 'library-admission', contract='library-admission')
    _require(admission['status'] == 'admitted' and admission['candidate_ref'] == ref
        and template['cc'] == admission['cc'] == pin and template['ports'] == declaration['ports'])
    for body in identity['body']:
        body_ref = template['body_refs'][body['path']]
        _require(body_ref['sha256'] == body['sha256'])
        store.read_blob(body_ref)
    for dependency in declaration['needs']['external']:
        for key in ('pin', 'lockfile'):
            if dependency.get(key):
                external = dependency[key]
                external_ref = template['body_refs'][external['ref']]
                _require(external_ref['sha256'] == external['sha256'])
                store.read_blob(external_ref)
    return declaration


def _rows(store, db, run_id, kinds, *, node_id=None):
    query = 'SELECT id,kind FROM records WHERE run_id=? AND kind IN (' + ','.join('?' for _ in kinds) + ')'
    args = [run_id, *kinds]
    if node_id is not None:
        query += ' AND node_id=?'
        args.append(node_id)
    result = []
    for row in db.execute(query + ' ORDER BY rowid', args).fetchall():
        ref = store.record_ref(row['id'])
        result.append({'kind': row['kind'], 'ref': ref, 'record': _original(store, db, ref, row['kind'])[0]})
    return result


def _ownership(store, db, run, parent_order, *, allow_linked=True):
    """Use the actual allocation producer; create_run is a separate old path."""
    run_id = run['id']
    validate('client-submission', run['submission'])
    submission = run['submission']
    _require(submission['account_id'] == run['account_id'] and submission['workspace_id'] == run['workspace_id'])
    created = db.execute("SELECT id FROM records WHERE run_id=? AND kind='run-created'", (run_id,)).fetchall()
    _require(len(created) <= 1)
    if created:
        created_ref = store.record_ref(created[0]['id'])
        value, order = _original(store, db, created_ref, 'run-created', scope={'run_id': run_id})
        _require(value['id'] == created_ref['id'] == run_id + ':created'
            and value['account_id'] == run['account_id'] and value['workspace_id'] == run['workspace_id']
            and order < parent_order)
    requests = db.execute('SELECT * FROM requests WHERE run_id=?', (run_id,)).fetchall()
    if requests:
        _require(len(requests) == 1 and requests[0]['account_id'] == run['account_id']
            and requests[0]['request_id'] == submission['client_request_id']
            and requests[0]['fingerprint'] == hashlib.sha256(json_bytes(submission)).hexdigest())
    events = _rows(store, db, run_id, ('client-submission',))
    _require(len(events) <= 1)
    if events:
        value, order = _original(store, db, events[0]['ref'], 'client-submission', scope={'run_id': run_id})
        _require(set(value) == set(submission) | {'run_id'} and value['id'] == events[0]['ref']['id']
            and all(value[key] == expected for key, expected in submission.items() if key != 'id')
            and order < parent_order)
    if not (created or requests and events):
        _require(allow_linked and requests)
        _linked_ownership(store, db, run, parent_order)
    intake, _ = _original(store, db, submission['intake_ref'], 'qualified-intake', contract='qualified-intake')
    _require(intake['user_id'] == run['account_id'])


def _linked_ownership(store, db, run, parent_order):
    """Read the already allocated ordinary depth1 -> depth2 transaction.

    No original event is synthesized. The parent must prove direct ownership,
    and this read can neither allocate another descendant nor renew a grant.
    """
    from .binding import committed_output_proof
    from .run_inputs import local_document_refs
    _require(db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='plan_lineage'").fetchone() is not None)
    child_id = run['id']
    child_lineage = db.execute('SELECT * FROM plan_lineage WHERE run_id=?', (child_id,)).fetchone()
    parents = db.execute('SELECT * FROM plan_lineage WHERE linked_run_id=?', (child_id,)).fetchall()
    _require(child_lineage is not None and len(parents) == 1)
    parent_lineage = parents[0]
    original_id = parent_lineage['run_id']
    _require(original_id != child_id and parent_lineage['depth'] == 1 and child_lineage['depth'] == 2
        and parent_lineage['root_run_id'] == original_id == child_lineage['root_run_id']
        and child_lineage['linked_run_id'] is None)
    original = store.get_run(original_id, account_id=run['account_id'])
    _require(original['workspace_id'] == run['workspace_id']
        and original['submission'].get('plan_source') == run['submission'].get('plan_source') == 'planned'
        and original['submission'].get('profile_id') is None and run['submission'].get('profile_id') is None)
    _require(db.execute("SELECT 1 FROM records WHERE run_id IN (?,?) AND kind IN "
        "('finite-e1-run-selection','finite-e1-plan-binding','evaluation-run-binding') LIMIT 1",
        (original_id, child_id)).fetchone() is None)
    child_intake_ref = run['submission']['intake_ref']
    child_intake, intake_order = _original(store, db, child_intake_ref, 'qualified-intake', contract='qualified-intake')
    outcome_ref = child_intake.get('prior_plan_outcome_ref')
    _require(outcome_ref is not None and child_intake['id'] == child_intake_ref['id'])
    outcomes = _rows(store, db, original_id, ('plan-outcome',))
    _require(len(outcomes) == 1 and outcomes[0]['ref'] == outcome_ref)
    outcome, outcome_order = _original(store, db, outcome_ref, 'plan-outcome', contract='plan-outcome')
    _require(outcome['id'] == outcome_ref['id'] and outcome['outcome'] == 'plan_infeasible'
        and outcome['attempt_depth'] == 1 and outcome['linked_attempt_id'] == child_id
        and outcome['next_stage'] == 'intention_compiler' and outcome_order < intake_order < parent_order)
    # These two bodies do not carry run_id. Their original SQL scope, and the
    # producer's single allocation timestamp, must be read independently.
    for ref, expected_run in ((outcome_ref, original_id), (child_intake_ref, child_id)):
        metadata = db.execute('SELECT r.run_id,r.node_id,r.attempt_id,r.captured_at,a.captured_at AS artifact_captured_at '
            'FROM records r JOIN artifacts a ON a.id=r.id WHERE r.id=?', (ref['id'],)).fetchone()
        _require(metadata is not None and metadata['run_id'] == expected_run
            and metadata['node_id'] is None and metadata['attempt_id'] is None
            and metadata['captured_at'] == metadata['artifact_captured_at'] == run['created_at'])
    _ownership(store, db, original, outcome_order, allow_linked=False)
    governing = committed_output_proof(store, original_id, 'intention_compiler')
    _require(governing['outputs'] == {'brief': outcome['brief_ref']})
    for key in ('source_ref', 'check_result_ref', 'gate_decision_ref'):
        if outcome[key] is not None:
            store.read_blob(outcome[key])
    original_intake_ref = original['submission']['intake_ref']
    original_intake, _ = _original(store, db, original_intake_ref, 'qualified-intake', contract='qualified-intake')
    _require(child_intake_ref != original_intake_ref and child_intake['id'] != original_intake['id']
        and run['submission']['id'] != original['submission']['id']
        and run['submission']['client_request_id'] != original['submission']['client_request_id'])
    expected_intake = dict(original_intake, id=child_intake['id'], prior_plan_outcome_ref=outcome_ref)
    expected_submission = dict(original['submission'], id=run['submission']['id'],
        client_request_id=run['submission']['client_request_id'], intake_ref=child_intake_ref)
    stored_submission = db.execute('SELECT submission FROM runs WHERE id=?', (child_id,)).fetchone()
    _require(store.read_blob(child_intake_ref) == json_bytes(expected_intake)
        and run['submission'] == expected_submission
        and stored_submission['submission'].encode('utf-8') == json_bytes(expected_submission))
    bindings = {}
    for current in (original, run):
        rows = _rows(store, db, current['id'], ('run-input-binding',))
        _require(len(rows) == 1)
        binding, binding_order = _original(store, db, rows[0]['ref'], 'run-input-binding', scope={'run_id': current['id']})
        local_document_refs(store, binding['buffer_ref'], inventory_ref=binding['resource_inventory_ref'],
            intake_ref=current['submission']['intake_ref'], run_id=current['id'])
        bindings[current['id']] = binding
        if current['id'] == original_id:
            _require(binding_order < outcome_order)
        else:
            starts = _rows(store, db, child_id, ('run-start',))
            _require(len(starts) == 1)
            start, start_order = _original(store, db, starts[0]['ref'], 'run-start', scope={'run_id': child_id})
            _require(intake_order < binding_order < start_order < parent_order
                and start['configuration_ref'] == run['submission']['configuration_ref'])
    _require(bindings[original_id]['base_resource_inventory_ref'] == bindings[child_id]['base_resource_inventory_ref'])
    expected_uploads = {store.read_record(ref, contract_id='client-upload')['id'] for ref in original_intake['upload_refs']}
    for current_id in (original_id, child_id):
        used = {row['upload_id'] for row in db.execute('SELECT upload_id FROM upload_uses WHERE run_id=?', (current_id,)).fetchall()}
        _require(used == expected_uploads)


def _port(parent, name, contract):
    from .binding import ContractFactory
    from .contracts import contract_schema
    matches = [port for port in parent['inputs'] if port['name'] == name]
    _require(len(matches) == 1)
    port = matches[0]
    _require(contract_schema(port['contract_id']) == contract_schema(contract)
        and port['version'] == ContractFactory._version(contract) and port['required'] is True
        and len(port['artifact_refs']) == 1)
    return port['artifact_refs'][0]


def _preplan(store, db, run, parent_ref, parent, templates, declarations, start, start_order):
    from .binding import committed_output_proof
    starts = _rows(store, db, run['id'], ('run-start',))
    _require(len(starts) == 1)
    original, order = _original(store, db, starts[0]['ref'], 'run-start', scope={'run_id': run['id']})
    _require(original['configuration_ref'] == parent['configuration_ref'] and order < start_order)
    validate('RunPins', original['pins'])
    snapshot_ref = original['library_snapshot_ref']
    snapshot, _ = _original(store, db, snapshot_ref, 'library-snapshot', contract='library-snapshot')
    _require(original['pins']['library_snapshot_sha256'] == snapshot_ref['sha256']
        and original['pins']['plan_policy_ref'] == parent['policy_ref'])
    fixed = {'intent': 'intent.compiler', 'requirements': 'requirements.compiler', 'planner': 'research.planner'}
    from .summary_planning import PAPER_CC_VERSION, PAPER_PLANNER_VERSION, PAPER_PLANNER_CC, is_document_summary_policy
    from .unified_planning import is_integrated_policy
    policy = _source(store, db, parent['policy_ref'], 'plan-policy')
    is_integrated_policy(policy)
    paper = is_document_summary_policy(policy)
    if paper:
        fixed['planner'] = PAPER_PLANNER_CC
    expected = {}
    for key, template in templates.items():
        if template['role'] == 'work':
            _require(key in fixed and template['cc']['cc_name'] == fixed[key])
            if paper and key == 'planner':
                _require(template['cc']['cc_version'] in {PAPER_CC_VERSION, PAPER_PLANNER_VERSION})
            depends = ['intent', 'intent.verifier'] if key == 'requirements' else []
            expected[key] = ('work', depends)
            for port in declarations[key]['ports']['outputs']:
                verifier = key + '.verifier' + ('.' + port['name'] if len(declarations[key]['ports']['outputs']) > 1 else '')
                expected[verifier] = ('verifier', [key])
                _require(verifier in templates and templates[verifier]['subject_subnode_id'] == key
                    and templates[verifier]['output_port'] == port['name']
                    and templates[verifier]['checking_profile_ref'] == template['checking_profile_ref'])
        else:
            _require(template['cc']['cc_name'] == 'research.verifier')
        entries = [entry for entry in snapshot['entries'] if all(entry[name] == value for name, value in template['cc'].items())]
        _require(len(entries) == 1)
        pins = _pins(store, db, template)
        if template['role'] == 'work':
            _require(entries[0]['check_pins'] == pins)
        else:
            _require(all(entries[0]['check_pins'][name] == pins[name]
                for name in ('check_bundle_id', 'check_bundle_version', 'check_bundle_sha256')))
    _require(set(templates) == set(expected) and all((item['role'], item['depends_on']) == expected[item['subnode_id']]
        and item['required'] is True for item in parent['subnodes']))
    store.read_blob(parent['template_ref'])
    if parent['node_id'] == 'intention_compiler':
        _require([item['subnode_id'] for item in parent['subnodes'] if item['role'] == 'work'] == ['intent', 'requirements']
            and [port['name'] for port in parent['inputs']] == ['request', 'defaults']
            and _port(parent, 'request', 'qualified-intake') == run['submission']['intake_ref']
            and parent['outputs'] in [[{'name': 'brief', 'contract_id': 'urn:jiuwenswarm:m1-design:research-brief:' + version,
                'version': version, 'required': True}] for version in ('2.0.0', '3.0.0')] and parent['required_outputs'] == ['brief']
            and parent['objective'] == 'Compile qualified user meaning into an accepted Research Brief'
            and parent['requirement_ids'] == ['qualified_intent', 'research_brief'] and start['predecessor_commits'] == [])
        policy = _source(store, db, _port(parent, 'defaults', 'default-policy'), 'default-policy')
        _require(policy['automatic_retries'] == 0 and policy['hardware_profile'] == 'single_gpu')
        return None, None
    _require(parent['node_id'] == 'planner' and [item['subnode_id'] for item in parent['subnodes'] if item['role'] == 'work'] == ['planner']
        and [port['name'] for port in parent['inputs']] == ['brief', 'library_snapshot', 'resource_inventory', 'plan_policy']
        and _port(parent, 'library_snapshot', 'library-snapshot') == snapshot_ref
        and _port(parent, 'plan_policy', 'plan-policy') == parent['policy_ref']
        and parent['outputs'] == [{'name': 'plan_proposal', 'contract_id': 'plan-proposal:field-contract:3',
            'version': '3.0.0', 'required': True}] and parent['required_outputs'] == ['plan_proposal']
        and parent['objective'] == 'Propose a bounded data-only graph covering the accepted Research Brief'
        and parent['requirement_ids'] == ['planned_graph'])
    brief_ref = _port(parent, 'brief', 'research-brief')
    proof = committed_output_proof(store, run['id'], 'intention_compiler')
    _require(proof['outputs'] == {'brief': brief_ref}
        and start['predecessor_commits'] == store._predecessor_snapshot(db, run['id'], ['intention_compiler']))
    inventory_ref = _port(parent, 'resource_inventory', 'resource-inventory')
    _source(store, db, inventory_ref, 'resource-inventory')
    inputs = _rows(store, db, run['id'], ('run-input-binding',))
    _require(len(inputs) == 1)
    from .run_inputs import local_document_refs
    local_document_refs(store, inputs[0]['record']['buffer_ref'], inventory_ref=inventory_ref,
        intake_ref=run['submission']['intake_ref'], run_id=run['id'])
    return templates['planner']['cc'], _pins(store, db, templates['planner'])


def _committed(store, db, run_id, node_id, plan):
    from .binding import committed_output_proof
    proof = committed_output_proof(store, run_id, node_id)
    selected = [item for item in plan['nodes'] if item['node_id'] == node_id]
    _require(len(selected) == len(proof['gates']) == 1)
    node = selected[0]
    parent_ref = proof['gates'][0][1]['node_contract_ref']
    parent, _ = _original(store, db, parent_ref, 'node-execution-contract', contract='node-execution-contract',
        scope={'run_id': run_id, 'node_id': node_id, 'attempt_id': proof['receipt']['attempt_id']})
    work = [item for item in parent['subnodes'] if item['role'] == 'work']
    _require(len(work) == 1 and work[0]['subnode_id'] == node_id
        and parent['configuration_ref'] == plan['configuration_ref'] and parent['policy_ref'] == plan['policy_ref']
        and parent['template_ref'] == plan['source_ref'] and parent['node_limits'] == node['limits'])
    template, _ = _original(store, db, work[0]['template_ref'], 'subnode-template')
    _require(template['cc'] == node['cc'] and template['capsule_ref'] == work[0]['capsule_ref']
        and work[0]['capsule_ref']['sha256'] == node['cc']['declaration_sha256'])
    _declaration(store, db, work[0], template)
    return dict(proof, parent_ref=parent_ref, parent=parent)


def _host_input(store, db, run_id, ref, key, plan_ref, plan, node, template, proofs):
    if key == 'run_configuration':
        _require(ref == plan['configuration_ref'])
        store.read_blob(ref)
    elif key == 'screening_rubric':
        _require(node['cc']['cc_name'] == 'research.screening' and template['body_refs'].get('screening_rubric.json') == ref)
        _source(store, db, ref, 'screening-rubric')
    elif key == 'environment_lock':
        inventory = _source(store, db, plan['resource_inventory_ref'], 'resource-inventory')
        matches = [item for item in inventory['resources'] if item['resource_key'] == key]
        _require(len(matches) == 1 and matches[0]['available'] is True and matches[0]['ref'] == ref)
        _source(store, db, ref, 'environment-lock')
    elif key == 'gate_decision_index':
        value, _ = _original(store, db, ref, 'gate-decision-index', contract='gate-decision-index')
        expected = [{'node_id': name, 'gate_decision_ref': proofs[name]['gates'][0][0]}
            for name in plan['topological_order'] if name in proofs]
        _require(value['run_plan_ref'] == plan_ref and value['entries'] == expected)
    elif key in {'screening_result', 'execution_receipt', 'provisioning_receipt'}:
        producer, port = {'screening_result': ('research.screening', 'screening_result'),
            'execution_receipt': ('research.benchmark', 'execution_receipt'),
            'provisioning_receipt': ('research.benchmark', 'provisioning_receipt')}[key]
        matches = [proof['outputs'][port] for name, proof in proofs.items()
            if next(item for item in plan['nodes'] if item['node_id'] == name)['cc']['cc_name'] == producer and port in proof['outputs']]
        _require(matches == [ref])
    elif key == 'build_receipt':
        matches = []
        for name, proof in proofs.items():
            selected = next(item for item in plan['nodes'] if item['node_id'] == name)
            if selected['cc']['cc_name'] != 'research.builder':
                continue
            producer_inputs = {port['name']: port['artifact_refs'][0] for port in proof['parent']['inputs']}
            for row in _rows(store, db, run_id, ('host-record-proposal',), node_id=name):
                offered = row['record']
                if (offered.get('key') != key or offered.get('attempt_id') != proof['receipt']['attempt_id']
                        or offered.get('subnode_id') != name):
                    continue
                captures = [item['record'] for item in _rows(store, db, run_id, ('captured-output',), node_id=name)
                    if item['record']['subnode_id'] == name and item['record']['attempt_id'] == proof['receipt']['attempt_id']
                    and item['record']['invocation_id'] == offered.get('invocation_id')]
                _require(len(captures) == len(proof['outputs'])
                    and {item['output_port']: item['artifact_ref'] for item in captures} == proof['outputs'])
                observations = [item['record'] for item in _rows(store, db, run_id, ('invocation-observation',), node_id=name)
                    if item['record']['node_contract_ref'] == proof['parent_ref'] and item['record']['subnode_id'] == name
                    and item['record']['attempt_id'] == proof['receipt']['attempt_id']
                    and item['record']['invocation_id'] == offered.get('invocation_id')
                    and item['record']['outcome'] == 'success' and item['record']['failure_reason_code'] is None
                    and {(pin['id'], pin['sha256']) for pin in item['record']['output_refs']}
                    == {(pin['id'], pin['sha256']) for pin in proof['outputs'].values()}]
                _require(len(observations) == 1)
                observed = observations[0]
                producing, _ = _original(store, db, observed['contract_ref'], 'subnode-execution-contract',
                    contract='subnode-execution-contract', scope={'run_id': run_id, 'node_id': name,
                        'attempt_id': proof['receipt']['attempt_id']})
                starts = [item for item in _rows(store, db, run_id, ('model-call-start',), node_id=name)
                    if item['record'].get('contract_ref') == observed['contract_ref']
                    and item['record'].get('invocation_id') == offered.get('invocation_id')]
                agent_builder = selected['cc']['cc_version'] in {'m1-14','m1-15','m1-16','m1-17','m1-18'}
                loop_builder = (selected['cc']['cc_version'] == 'm1-13' and
                    store.read_record(producing['bindings'][0]['declaration_ref'])['identity']['carrier']['ref'] == 'builder_loop.py')
                _require(producing['node_contract_ref'] == proof['parent_ref'] and producing['subnode_id'] == name
                    and producing['bindings'][0]['role'] == 'work'
                    and producing['bindings'][0]['declaration_ref']['sha256'] == selected['cc']['declaration_sha256']
                    and (1 <= len(starts) <= 20 if agent_builder else
                         1 <= len(starts) <= 3 if loop_builder else len(starts) == 1))
                receipt_kind = ('urn:ai4r:prediction-build-receipt:4.0.0' if agent_builder else
                    'urn:ai4r:prediction-build-receipt:3.0.0' if loop_builder
                    else 'urn:ai4r:prediction-build-receipt:2.0.0' if selected['cc']['cc_version'] in {'m1-11', 'm1-12', 'm1-13'} else 'build-receipt')
                receipt = _source(store, db, offered['ref'], receipt_kind)
                _require(receipt['manifest_ref'] == proof['outputs'].get('manifest')
                    and receipt['archive_ref'] == proof['outputs'].get('bundle')
                    and receipt['blueprint_ref'] == producer_inputs.get('blueprint')
                    and receipt['environment_ref'] == producer_inputs.get('lock')
                    and receipt['readiness'] == 'READY'
                    and (receipt['schema_version'] in {'3.0.0','4.0.0'} or (not receipt['trial_executed'] and not receipt['packages_installed']))
                    and (receipt['schema_version'] != '4.0.0' or (receipt['trial_executed'] is True
                        and receipt['development_only'] is True and receipt['model_call_count'] == len(starts)
                        and 1 <= receipt['tool_operation_count'] <= 40 and 0 <= receipt['execution_job_count'] <= 12))
                    and (receipt['schema_version'] != '3.0.0' or receipt['candidate_count'] == len(starts)))
                if receipt['schema_version'] == '4.0.0':
                    journal_ref = receipt['journal_ref']
                    _require(store.record_kind(journal_ref) == 'builder_agent_execution')
                    journal, _ = _original(store, db, journal_ref, 'builder_agent_execution')
                    _require(journal.get('schema') == 'ai4r-builder-agent-execution:1'
                        and journal.get('contract_ref') == observed['contract_ref']
                        and journal.get('invocation_id') == offered.get('invocation_id')
                        and journal.get('manifest_ref') == proof['outputs'].get('manifest')
                        and journal.get('archive_ref') == proof['outputs'].get('bundle')
                        and journal.get('snapshot_sha256') == receipt['workspace_sha256']
                        and journal.get('submitted_snapshot_sha256') == receipt['submitted_snapshot_sha256'])
                matches.append(offered['ref'])
        _require(matches == [ref])
    else:
        _require(False)


def _planned_inputs(store, db, run_id, parent, plan_ref, plan, node, template, snapshot):
    from .binding import ContractFactory
    entries = [entry for entry in snapshot['entries'] if all(entry[key] == value for key, value in node['cc'].items())]
    _require(len(entries) == 1)
    entry = entries[0]
    expected_outputs = [{'name': port['name'],
        'contract_id': next(item['schema_ref'] for item in entry['output_ports'] if item['name'] == port['name']),
        'version': ContractFactory._version(next(item['schema_ref'] for item in entry['output_ports'] if item['name'] == port['name'])),
        'required': port['required']} for port in node['outputs']]
    _require(parent['outputs'] == expected_outputs
        and parent['required_outputs'] == [item['name'] for item in expected_outputs if item['required']]
        and parent['objective'] == node['objective'] and parent['requirement_ids'] == (node['requirement_ids'] or node['deliverable_ids'])
        and [port['name'] for port in parent['inputs']] == [port['name'] for port in node['inputs']])
    nodes = {item['node_id']: item for item in plan['nodes']}
    ancestors = set()
    pending = list(node['predecessors'])
    while pending:
        name = pending.pop()
        _require(name in nodes)
        if name not in ancestors:
            ancestors.add(name)
            pending.extend(nodes[name]['predecessors'])
    proofs = {name: _committed(store, db, run_id, name, plan) for name in plan['topological_order'] if name in ancestors}
    for port in node['inputs']:
        declared = [item for item in entry['input_ports'] if item['name'] == port['name']]
        _require(len(declared) == 1)
        ref = _port(parent, port['name'], declared[0]['schema_ref'])
        if port['source_kind'] == 'accepted_ref':
            _require(ref == port['accepted_ref'])
        elif port['source_kind'] == 'future_output':
            future = port['future']
            _require(future['producer_node'] in ancestors and any(item['name'] == future['port']
                and item['artifact_type'] == future['artifact_type'] for item in nodes[future['producer_node']]['outputs'])
                and proofs[future['producer_node']]['outputs'].get(future['port']) == ref)
        else:
            _host_input(store, db, run_id, ref, port['run_input_key'], plan_ref, plan, node, template, proofs)


def _candidate(store, db, run, state):
    run_id, node_id, attempt_id = run['id'], state['node_id'], state['attempt_id']
    _require(state['state'] in {'running', 'evaluating'} and attempt_id == node_id + '-a1')
    scope = {'run_id': run_id, 'node_id': node_id, 'attempt_id': attempt_id}
    own = _rows(store, db, run_id, ('dispatch-record', 'gate-decision', 'dispatch-start',
        'dispatch-preparation', 'bound-check-plan', 'invocation-budget-reservation'), node_id=node_id)
    for row in own:
        if row['kind'] == 'gate-decision':
            _original(store, db, row['ref'], 'gate-decision', scope=scope, contract='gate-decision')
    _require(not any(row['kind'] == 'dispatch-record' or row['kind'] == 'gate-decision'
        and row['record'].get('scope_kind') == 'node' for row in own))
    _require(db.execute("SELECT 1 FROM acceptance WHERE run_id=? AND node_id=? AND subnode_id='' LIMIT 1",
        (run_id, node_id)).fetchone() is None)
    # Require current consumed-start format and its original inert association.
    # A legacy start without that original association is deliberately unknown.
    starts = [row for row in own if row['kind'] == 'dispatch-start']
    _require(len(starts) == 1)
    start_ref = starts[0]['ref']
    start, start_order = _original(store, db, start_ref, 'dispatch-start',
        scope={'run_id': run_id, 'node_id': node_id})
    fields = {'id', 'run_id', 'node_id', 'recorded_at', 'node_contract_ref',
        'run_plan_ref', 'predecessor_commits', 'bound_input_refs'}
    _require(set(start) == fields and start['id'] == start_ref['id']
        and start['id'].startswith('dispatch-start:'))
    parent_ref = start['node_contract_ref']
    parent, parent_order = _original(store, db, parent_ref, 'node-execution-contract',
        scope=scope, contract='node-execution-contract')
    _require(parent['configuration_ref'] == run['submission']['configuration_ref'])
    _ownership(store, db, run, parent_order)
    inputs = [{'name': port['name'], 'ref': ref} for port in parent['inputs'] for ref in port['artifact_refs']]
    _require(start['bound_input_refs'] == inputs and parent['input_refs'] == [item['ref'] for item in inputs])
    for ref in parent['input_refs']:
        store.read_blob(ref)
    preparations = [row for row in own if row['kind'] == 'dispatch-preparation']
    _require(len(preparations) == 1)
    preparation, preparation_order = _original(store, db, preparations[0]['ref'], 'dispatch-preparation',
        scope={'run_id': run_id, 'node_id': node_id})
    _require(set(preparation) == fields and preparation['id'] == preparations[0]['ref']['id']
        and preparation['id'].startswith('dispatch-preparation:')
        and all(preparation[key] == start[key] for key in fields - {'id', 'recorded_at'})
        and parent_order < preparation_order < start_order)
    plans = [row for row in own if row['kind'] == 'bound-check-plan'
        and row['record'].get('contract_ref') == parent_ref]
    _require(len(plans) == 1)
    check_ref = plans[0]['ref']
    checked, check_order = _original(store, db, check_ref, 'bound-check-plan', scope=scope, contract='bound-check-plan')
    profile = _source(store, db, parent['checking_profile_ref'], 'node-finalization-profile')
    _require(checked['contract_ref'] == checked['node_contract_ref'] == parent_ref
        and checked['subnode_id'] is None and checked['input_refs'] == parent['input_refs']
        and checked['profile_ref'] == parent['checking_profile_ref'] and checked['policy_ref'] == parent['policy_ref']
        and checked['mandatory_deterministic'] == profile['mandatory_deterministic']
        == ['internal_acceptance', 'external_output', 'aggregate_limits']
        and checked['mandatory_semantic'] == [] and len(checked['runner_refs']) == 1
        and parent_order < check_order < preparation_order)
    store.read_blob(checked['runner_refs'][0])
    assignments = {item['subnode_id']: item for item in parent['subnodes']}
    _require(len(assignments) == len(parent['subnodes']))
    templates = {}
    declarations = {}
    for key, assignment in assignments.items():
        template, _ = _original(store, db, assignment['template_ref'], 'subnode-template')
        _require(template['id'] == assignment['template_ref']['id'] and template['subnode_id'] == key
            and template['role'] == assignment['role'] and template['capsule_ref'] == assignment['capsule_ref']
            and template['depends_on'] == assignment['depends_on'])
        declarations[key] = _declaration(store, db, assignment, template)
        _pins(store, db, template)
        templates[key] = template
    first = [item for item in assignments.values() if item['role'] == 'work' and item['depends_on'] == []]
    _require(len(first) == 1)
    claims = db.execute('SELECT * FROM attempts WHERE run_id=? AND node_id=? AND attempt_id=?',
        (run_id, node_id, attempt_id)).fetchall()
    _require(claims and any(row['subnode_id'] == first[0]['subnode_id']
        and row['state'] in {'running', 'accepted', 'rejected', 'observed', 'interrupted'} for row in claims))
    _require(all(row['state'] in {'prepared', 'running', 'accepted', 'rejected', 'observed', 'interrupted'}
        for row in claims))
    for row in claims:
        assignment = assignments.get(row['subnode_id'])
        _require(assignment is not None)
        child_ref = json.loads(row['contract_ref'])
        child, child_order = _original(store, db, child_ref, 'subnode-execution-contract',
            scope=scope, contract='subnode-execution-contract')
        template = templates[row['subnode_id']]
        _require(child['node_contract_ref'] == parent_ref and child['subnode_id'] == row['subnode_id']
            and child['template_ref'] == assignment['template_ref'] and len(child['bindings']) == 1
            and child['bindings'][0]['role'] == assignment['role']
            and child['bindings'][0]['declaration_ref'] == assignment['capsule_ref']
            and child['bindings'][0]['admission_ref'] == template['admission_ref']
            and child['checking_profile_ref'] == template['checking_profile_ref']
            and all(child[key] == parent[key] for key in ('revision', 'policy_ref', 'configuration_ref')))
        declaration = declarations[row['subnode_id']]
        implementations = [template['body_refs'][body['path']] for body in declaration['identity']['body']]
        dependencies = [template['body_refs'][pin['ref']] for dependency in declaration['needs']['external']
            for key in ('pin', 'lockfile') if (pin := dependency.get(key))]
        _require(child['bindings'][0]['implementation_refs'] == implementations
            and child['bindings'][0]['dependency_refs'] == dependencies
            and child['input_refs'] == [ref for port in child['inputs'] for ref in port['artifact_refs']])
        from .binding import ContractFactory, validate_child_authority
        outputs = [{'name': port['name'], 'contract_id': port['schema_ref'],
            'version': ContractFactory._version(port['schema_ref']), 'required': port['required']}
            for port in declaration['ports']['outputs']]
        _require(child['outputs'] == outputs and child['required_outputs'] == [port['name'] for port in outputs if port['required']])
        admission, _ = _original(store, db, template['admission_ref'], 'library-admission', contract='library-admission')
        per = declaration['budget']['per_call']
        calls = per['invocations'] if any(item['service_key'] == 'audited_model_bridge' for item in declaration['needs']['injects']) else 0
        caps = {'time_s': min(per['wall_s'], parent['node_limits']['time_s']),
            'model_calls': min(calls, parent['node_limits']['model_calls']),
            'memory_mb': min(admission['memory_mb'], parent['node_limits']['memory_mb'])}
        if assignment['role'] == 'verifier':
            profile = _source(store, db, template['checking_profile_ref'], 'checking-profile')
            caps['time_s'] = min(caps['time_s'], profile['time_s'])
            caps['model_calls'] = min(caps['model_calls'], profile['model_call_limit'], 1)
        _require(child['bindings'][0]['limits'] == child['subnode_limits']
            and all(child['subnode_limits'][key] <= value for key, value in caps.items()))
        validate_child_authority(store, parent_ref, child['subnode_id'], child['inputs'],
            effective_authority=child['bindings'][0]['effective_authority'])
        if assignment['role'] == 'work':
            if node_id == 'intention_compiler':
                if child['subnode_id'] == 'intent':
                    _require([port['name'] for port in child['inputs']] == ['request']
                        and _port(child, 'request', 'qualified-intake') == _port(parent, 'request', 'qualified-intake'))
                else:
                    from .binding import committed_output_proof
                    intent = committed_output_proof(store, run_id, node_id, subnode_id='intent', parent_ref=parent_ref)
                    _require([port['name'] for port in child['inputs']] == ['intent', 'intake', 'defaults']
                        and _port(child, 'intent', 'intent-ir') == intent['outputs'].get('intent')
                        and _port(child, 'intake', 'qualified-intake') == _port(parent, 'request', 'qualified-intake')
                        and _port(child, 'defaults', 'default-policy') == _port(parent, 'defaults', 'default-policy'))
            else:
                _require(child['inputs'] == parent['inputs'])
        if row['subnode_id'] == first[0]['subnode_id']:
            budgets = [item for item in own if item['kind'] == 'invocation-budget-reservation'
                and item['record'].get('contract_ref') == child_ref]
            _require(len(budgets) == 1)
            budget, budget_order = _original(store, db, budgets[0]['ref'], 'invocation-budget-reservation',
                scope={'run_id': run_id, 'node_id': node_id})
            _require(budget['subnode_id'] == child['subnode_id'] and child_order < budget_order < start_order)
            invocations = []
            for item in db.execute("SELECT id FROM records WHERE kind='invocation-preparation' AND rowid>? AND rowid<? ORDER BY rowid",
                (budget_order, start_order)).fetchall():
                ref = store.record_ref(item['id'])
                value, order = _original(store, db, ref, 'invocation-preparation')
                validate('urn:ai4r:private:invocation-preparation:1', value)
                if value['contract_ref'] == child_ref:
                    invocations.append({'ref': ref, 'record': value})
            _require(len(invocations) == 1)
            original, invocation_order = _original(store, db, invocations[0]['ref'], 'invocation-preparation')
            validate('urn:ai4r:private:invocation-preparation:1', original)
            _require(original['assignment_grant_ref'] is None and original['contract_ref'] == child_ref
                and original['execution_id'] == budget['execution_id'] and original['invocation_id'] == budget['invocation_id']
                and budget_order < invocation_order < start_order)
    plan_ref = start['run_plan_ref']
    work = [item for item in assignments.values() if item['role'] == 'work']
    if plan_ref is None:
        _require(node_id in {'intention_compiler', 'planner'})
        cc, pins = _preplan(store, db, run, parent_ref, parent, templates, declarations, start, start_order)
    else:
        plan, _ = _original(store, db, plan_ref, 'run-plan', contract='run-plan')
        snapshot, _ = _original(store, db, plan['library_snapshot_ref'], 'library-snapshot', contract='library-snapshot')
        nodes = [item for item in plan['nodes'] if item['node_id'] == node_id]
        _require(plan['frozen'] is True and len(nodes) == len(work) == 1
            and plan['configuration_ref'] == parent['configuration_ref'] and plan['policy_ref'] == parent['policy_ref']
            and plan['source_ref'] == parent['template_ref'] and nodes[0]['limits'] == parent['node_limits']
            and work[0]['subnode_id'] == node_id and templates[node_id]['cc'] == nodes[0]['cc']
            and work[0]['capsule_ref']['sha256'] == nodes[0]['cc']['declaration_sha256']
            and _pins(store, db, templates[node_id]) == nodes[0]['check_pins'])
        for template in templates.values():
            _require(any(all(entry[key] == value for key, value in template['cc'].items())
                for entry in snapshot['entries']))
        _source(store, db, plan['resource_inventory_ref'], 'resource-inventory')
        store.read_blob(plan['source_ref'])
        store.read_blob(plan['acceptance_ref'])
        bindings = _rows(store, db, run_id, ('run-plan-binding', 'finite-e1-plan-binding'))
        _require(bindings and len({item['kind'] for item in bindings}) == len(bindings))
        for binding in bindings:
            original, binding_order = _original(store, db, binding['ref'], binding['kind'], scope={'run_id': run_id})
            _require(original.get('plan_ref') == plan_ref and binding_order < start_order)
            if binding['kind'] == 'run-plan-binding':
                _require(set(original) == {'id', 'run_id', 'plan_ref', 'recorded_at'}
                    and original['id'] == binding['ref']['id'] and original['id'].startswith('run-plan-binding:'))
            else:
                from .finite_evaluation import finite_evidence_refs
                proof = finite_evidence_refs(store, run_id)
                _require(proof is not None and proof['plan_binding_ref'] == binding['ref'])
        _require(start['predecessor_commits'] == store._predecessor_snapshot(db, run_id, nodes[0]['predecessors']))
        _planned_inputs(store, db, run_id, parent, plan_ref, plan, nodes[0], templates[node_id], snapshot)
        cc, pins = nodes[0]['cc'], nodes[0]['check_pins']
    identity = hashlib.sha256(json_bytes([start_ref, parent_ref])).hexdigest()[:40]
    dispatch = {'schema_version': '2.0.0', 'id': 'dispatch_recovered_' + identity,
        **scope, 'phase': 'pre_plan' if plan_ref is None else 'planned', 'run_plan_ref': plan_ref,
        'cc': cc, 'node_contract_ref': parent_ref, 'bound_input_refs': inputs,
        'check_pins': pins, 'check_plan_ref': check_ref, 'attempt': 1,
        'started_at': start['recorded_at'], 'ended_at': None, 'outcome': 'interrupted',
        'gate_decision_ref': None, 'output_gate_decision_refs': [], 'output_refs': [],
        'elapsed_s': None, 'model_calls_used': None}
    validate('dispatch-record', dispatch)
    return dispatch, start_ref


def capture_interrupted_dispatches(store, db, run_ids, recorded_at):
    """Append only sufficiently witnessed original starts in this startup CAS.

    Validation failures retain the existing unknown open node. All writes use
    the caller's recovery transaction, including the run/claim pause updates.
    """
    for run_id in run_ids:
        states = db.execute("SELECT * FROM nodes WHERE run_id=? AND state IN ('running','evaluating')", (run_id,)).fetchall()
        for state in states:
            try:
                run = store.get_run(run_id)
                dispatch, start_ref = _candidate(store, db, run, state)
            except (ResearchError, KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, StopIteration):
                continue
            ref = {'id': dispatch['id'], 'sha256': store.blobs.put(json_bytes(dispatch))}
            event = {'id': 'restart:' + dispatch['id'], 'run_id': run_id,
                'node_id': state['node_id'], 'attempt_id': state['attempt_id'],
                'reason_code': 'interrupted', 'recorded_at': recorded_at,
                'dispatch_start_ref': start_ref, 'dispatch_ref': ref,
                'missing_observations': {key: 'Process restart interrupted original observation; unavailable, never zero'
                    for key in ('ended_at', 'elapsed_s', 'model_calls_used')},
                'effects': 'Known and uncertain prior effects are retained; cessation and native lease release are unproved'}
            event_digest = store.blobs.put(json_bytes(event))
            for identity, digest, kind in ((ref['id'], ref['sha256'], 'dispatch-record'),
                (event['id'], event_digest, 'escalation')):
                db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)', (identity, digest, 'application/json', None, recorded_at))
                db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',
                    (identity, kind, run_id, state['node_id'], state['attempt_id'], recorded_at))
            db.execute("UPDATE nodes SET state='failed',reason='interrupted' WHERE run_id=? AND node_id=? AND attempt_id=?",
                (run_id, state['node_id'], state['attempt_id']))
