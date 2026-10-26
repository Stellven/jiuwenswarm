"""Read-only current/finished stage attribution from original owned records.

This display projection never authorizes execution or infers process liveness.
"""
from __future__ import annotations

import json
import sqlite3

from .contracts import ResearchError


def _require(condition):
    if not condition:
        raise ResearchError('unavailable', 'Original execution chronology is unavailable')


def _original(store, ref, kind, *, run_id=None, node_id=None, attempt_id=None):
    _require(store.record_kind(ref) == kind)
    value = store.read_record(ref, contract_id=kind) if kind in {
        'node-execution-contract', 'subnode-execution-contract', 'run-plan', 'dispatch-record', 'gate-decision',
        'bound-check-plan', 'capsule-declaration', 'check-bundle', 'checking-profile'} else store.read_record(ref)
    with store._lock:
        row = store.connection.execute(
            'SELECT run_id,node_id,attempt_id FROM records WHERE id=?', (ref['id'],)).fetchone()
    _require(row is not None)
    if run_id is not None:
        _require(row['run_id'] == run_id and (kind == 'bound-check-plan' or value.get('run_id') == run_id))
    if node_id is not None:
        _require(row['node_id'] == node_id and (kind == 'bound-check-plan' or value.get('node_id') == node_id))
    if attempt_id is not None:
        _require(row['attempt_id'] == attempt_id and (kind == 'bound-check-plan' or value.get('attempt_id') == attempt_id))
    return value


def _flatten(parent):
    return [{'name': port['name'], 'ref': ref} for port in parent['inputs'] for ref in port['artifact_refs']]



def _templates(store, parent):
    work = []
    for assignment in parent['subnodes']:
        value = _original(store, assignment['template_ref'], 'subnode-template')
        _require(value['id'] == assignment['template_ref']['id']
                 and value['role'] == assignment['role'] and value['subnode_id'] == assignment['subnode_id']
                 and value['capsule_ref'] == assignment['capsule_ref']
                 and value['depends_on'] == assignment['depends_on'])
        if assignment['role'] == 'work':
            work.append(value)
    return work


def _pins(store, template):
    bundle = _original(store, template['check_bundle_ref'], 'check-bundle')
    profile = _original(store, template['checking_profile_ref'], 'checking-profile')
    return {'check_bundle_id': bundle['bundle_id'], 'check_bundle_version': bundle['version'],
            'check_bundle_sha256': template['check_bundle_ref']['sha256'], 'checking_profile_id': profile['profile_id'],
            'checking_profile_version': profile['version'], 'checking_profile_sha256': template['checking_profile_ref']['sha256']}


def _node_plan(store, ref, run, state, parent_ref, parent):
    value = _original(store, ref, 'bound-check-plan', run_id=run['id'], node_id=state['node_id'],
                      attempt_id=state['attempt_id'])
    _require(value['contract_ref'] == value['node_contract_ref'] == parent_ref
             and value['subnode_id'] is None and value['input_refs'] == parent['input_refs']
             and value['profile_ref'] == parent['checking_profile_ref'] and value['policy_ref'] == parent['policy_ref'])
    return value

def _start(store, envelope, run, state):
    value = _original(store, envelope['ref'], 'dispatch-start', run_id=run['id'], node_id=state['node_id'])
    _require(set(value) == {'id', 'run_id', 'node_id', 'recorded_at', 'node_contract_ref',
                           'run_plan_ref', 'predecessor_commits', 'bound_input_refs'}
             and value['id'] == envelope['ref']['id'])
    # dispatch-start deliberately has neither a body nor indexed attempt_id.
    return _context(store, value, run, state)


def _context(store, value, run, state):
    """Validate captured parent/plan ownership without interpreting a start."""
    _require(isinstance(state['attempt_id'], str) and bool(state['attempt_id']))
    parent_ref = value['node_contract_ref']
    parent = _original(store, parent_ref, 'node-execution-contract', run_id=run['id'],
                       node_id=state['node_id'], attempt_id=state['attempt_id'])
    _require(parent['configuration_ref'] == run['submission']['configuration_ref']
             and value['bound_input_refs'] == _flatten(parent)
             and parent['input_refs'] == [entry['ref'] for entry in _flatten(parent)])
    templates = _templates(store, parent)
    plan_ref = value['run_plan_ref']
    if plan_ref is None:
        _require(state['node_id'] in {'intention_compiler', 'planner'})
        plan = None
    else:
        plan = _original(store, plan_ref, 'run-plan')
        _require(plan['frozen'] is True and parent['configuration_ref'] == plan['configuration_ref']
                 and parent['policy_ref'] == plan['policy_ref'] and parent['template_ref'] == plan['source_ref'])
        matches = [node for node in plan['nodes'] if node['node_id'] == state['node_id']]
        work = [entry for entry in parent['subnodes'] if entry['role'] == 'work']
        _require(len(matches) == len(work) == 1)
        node = matches[0]
        template = templates[0]
        _require(parent['node_limits'] == node['limits'] and work[0]['subnode_id'] == node['node_id']
                 and work[0]['capsule_ref']['sha256'] == node['cc']['declaration_sha256']
                 and template['cc'] == node['cc'] and _pins(store, template) == node['check_pins'])
    return value, parent


def _dispatch(store, envelope, run, state, ownership, parent):
    value = _original(store, envelope['ref'], 'dispatch-record', run_id=run['id'],
                      node_id=state['node_id'], attempt_id=state['attempt_id'])
    _require(value['node_contract_ref'] == ownership['node_contract_ref']
             and value['run_plan_ref'] == ownership['run_plan_ref']
             and value['phase'] == ('pre_plan' if ownership['run_plan_ref'] is None else 'planned')
             and value['bound_input_refs'] == _flatten(parent)
             and value['attempt'] == 1)
    _node_plan(store, value['check_plan_ref'], run, state, ownership['node_contract_ref'], parent)
    if ownership['run_plan_ref'] is not None:
        plan = _original(store, ownership['run_plan_ref'], 'run-plan')
        node = next(node for node in plan['nodes'] if node['node_id'] == state['node_id'])
        _require(value['cc'] == node['cc'] and value['check_pins'] == node['check_pins'])
    elif state['node_id'] == 'intention_compiler':
        _require(value['cc'] is None and value['check_pins'] is None)
    else:
        work = _templates(store, parent)
        _require(len(work) == 1 and value['cc'] == work[0]['cc'] and value['check_pins'] == _pins(store, work[0]))
    gate_absent = value['outcome'] in {'failed', 'budget_exhausted', 'interrupted'}
    _require((value['gate_decision_ref'] is None) == gate_absent
             and bool(value['output_gate_decision_refs']) == (not gate_absent))
    if value['outcome'] == 'interrupted':
        _require(value['ended_at'] is None)
    else:
        _require(value['ended_at'] is not None)
    return value


def _prestart_dispatch(store, envelope, run, state):
    value = _original(store, envelope['ref'], 'dispatch-record', run_id=run['id'],
                      node_id=state['node_id'], attempt_id=state['attempt_id'])
    ownership, parent = _context(store, value, run, state)
    value = _dispatch(store, envelope, run, state, ownership, parent)
    from .attempt_inspection import validate_prestart_failure
    validate_prestart_failure(store, value['node_contract_ref'], parent, envelope['ref'], value)
    return value


def _node_gate(store, envelope, run, state, parent_ref, parent):
    value = _original(store, envelope['ref'], 'gate-decision', run_id=run['id'],
                      node_id=state['node_id'], attempt_id=state['attempt_id'])
    _require(value['scope_kind'] == 'node' and value['subnode_id'] is None
             and value['node_contract_ref'] == value['contract_ref'] == parent_ref)
    _node_plan(store, value['check_plan_ref'], run, state, parent_ref, parent)
    return value


def _execution_node_gates(store, envelopes, run, state, parent_ref, parent):
    """Separate the original node Gate from its protected Binder assessment reuse."""
    execution, bound = [], []
    for envelope in envelopes:
        gate = _original(store, envelope['ref'], 'gate-decision', run_id=run['id'],
                         node_id=state['node_id'], attempt_id=state['attempt_id'])
        plan = _original(store, gate['check_plan_ref'], 'bound-check-plan')
        target = execution if plan['contract_ref'] == plan['node_contract_ref'] == parent_ref else bound
        target.append(envelope)
    _require(len(execution) <= 1 and len(bound) <= 1)
    if not bound:
        return execution
    _require(state['node_id'] == 'planner' and len(execution) == 1)
    original_ref = execution[0]['ref']
    original = _node_gate(store, execution[0], run, state, parent_ref, parent)
    combined_ref = bound[0]['ref']
    combined = _original(store, combined_ref, 'gate-decision', run_id=run['id'],
                         node_id=state['node_id'], attempt_id=state['attempt_id'])
    links = [row for row in store.iter_records(kinds=('plan-acceptance-binding',))
             if row['record'].get('acceptance_ref') == combined_ref]
    _require(len(links) == 1)
    link = links[0]['record']
    _require(set(link) == {'id', 'source_ref', 'acceptance_ref', 'planner_gate_ref'}
             and link['id'] == links[0]['ref']['id'] and link['planner_gate_ref'] == original_ref)
    source_ref = link['source_ref']
    proposal = store.read_record(source_ref, contract_id='plan-proposal')
    _require(original['action'] == 'advance' and source_ref in original['accepted_refs']
             and store.is_accepted(source_ref, run_id=run['id']))
    changed = {'id', 'recorded_at', 'check_plan_ref', 'deterministic_result_ref', 'reasons'}
    _require({key: value for key, value in combined.items() if key not in changed}
             == {key: value for key, value in original.items() if key not in changed}
             and combined['id'] != original['id'] and combined['recorded_at'] >= original['recorded_at'])
    plan = _original(store, combined['check_plan_ref'], 'bound-check-plan')
    checked = store.read_record(combined['deterministic_result_ref'], contract_id='deterministic-check-result')
    work = _templates(store, parent)
    _require(len(work) == 1)
    profile = _original(store, work[0]['checking_profile_ref'], 'checking-profile')
    semantic = [criterion['criterion_id'] for criterion in profile['criteria']]
    ids = [result['check_id'] for result in checked['results']]
    from .binding import SHARED_CHECKS
    expected = ['plan_proposal_schema', *SHARED_CHECKS, 'suggested_checks_known']
    if any(check_id in {'finite_delivery_leaf_coverage_v1', 'finite_fixture_qualification_v1'} for check_id in ids):
        from .finite_evaluation import FINITE_PLAN_CHECKS
        expected = list(FINITE_PLAN_CHECKS)
    # Binder checks the four proposal resources. The producer additionally reads
    # its frozen capsule catalog; that is not a Binder input. Join each original
    # resource by its declared port rather than equating these different scopes.
    resource_ports = [('brief', 'brief_ref'), ('library_snapshot', 'library_snapshot_ref'),
                      ('resource_inventory', 'resource_inventory_ref'), ('plan_policy', 'policy_ref')]
    ports = {port['name']: port['artifact_refs'] for port in parent['inputs']}
    binder_inputs = [proposal[key] for _, key in resource_ports]
    _require(len(ports) == len(parent['inputs'])
             and all(ports.get(name) == [proposal[key]] for name, key in resource_ports))
    _require(plan['contract_ref'] == plan['node_contract_ref'] == checked['subject_ref'] == source_ref
             and checked['check_plan_ref'] == combined['check_plan_ref'] and plan['subnode_id'] is None
             and plan['input_refs'] == binder_inputs and plan['policy_ref'] == parent['policy_ref']
             and plan['profile_ref'] == work[0]['checking_profile_ref']
             and plan['mandatory_semantic'] == semantic and len(ids) == len(set(ids))
             and set(ids) == set(expected) and plan['mandatory_deterministic'] == ids
             and all(result['outcome'] == 'PASS' for result in checked['results']))
    _require(combined['reasons'] == [{'code': 'plan_checks_pass',
        'message': 'Bound host checks and the exact existing Planner assessment passed',
        'criterion_ids': semantic, 'evidence_refs': [combined['deterministic_result_ref'], original_ref]}])
    for ref in plan['runner_refs']:
        store.read_blob(ref)
    with store._lock:
        positions = [store.connection.execute('SELECT rowid FROM records WHERE id=?', (ref['id'],)).fetchone()
                     for ref in (original_ref, combined_ref, links[0]['ref'])]
    _require(all(row is not None for row in positions) and positions[0][0] < positions[1][0] < positions[2][0])
    return execution


def _claim_assignments(store, run, state, parent_ref, parent):
    """A terminal interruption cannot hide a substituted child claim."""
    with store._lock:
        rows = store.connection.execute(
            'SELECT subnode_id,state,contract_ref FROM attempts WHERE run_id=? AND node_id=? AND attempt_id=?',
            (run['id'], state['node_id'], state['attempt_id'])).fetchall()
    _require(rows)
    assigned = {item['subnode_id']: item for item in parent['subnodes']}
    for row in rows:
        child = _original(store, json.loads(row['contract_ref']), 'subnode-execution-contract',
                          run_id=run['id'], node_id=state['node_id'], attempt_id=state['attempt_id'])
        _require(row['subnode_id'] in assigned and child['subnode_id'] == row['subnode_id']
                 and child['node_contract_ref'] == parent_ref)
        assignment = assigned[row['subnode_id']]
        template = _original(store, assignment['template_ref'], 'subnode-template')
        _require(child['template_ref'] == assignment['template_ref'] and len(child['bindings']) == 1
                 and child['bindings'][0]['role'] == assignment['role']
                 and child['bindings'][0]['declaration_ref'] == assignment['capsule_ref']
                 and child['bindings'][0]['admission_ref'] == template['admission_ref']
                 and child['checking_profile_ref'] == template['checking_profile_ref'])


def _stopped_open(store, run, state, records, parent_ref, parent):
    if run['state'] == 'paused' and run['reason'] == 'interrupted':
        with store._lock:
            rows = store.connection.execute(
                'SELECT subnode_id,state,contract_ref FROM attempts WHERE run_id=? AND node_id=? AND attempt_id=?',
                (run['id'], state['node_id'], state['attempt_id'])).fetchall()
        _require(rows and any(row['state'] == 'paused' for row in rows)
                 and all(row['state'] in {'paused', 'accepted', 'rejected', 'observed', 'interrupted'} for row in rows))
        _claim_assignments(store, run, state, parent_ref, parent)
        return True
    if run['state'] in {'halted', 'failed', 'cancelled'}:
        # This is durable stopped-run provenance, never an owner/cessation claim.
        _require(bool(run['reason']))
        return True
    local = [row for row in records if row['kind'] == 'execution-cancelled-pending']
    if local:
        for envelope in local:
            value = _original(store, envelope['ref'], 'execution-cancelled-pending', run_id=run['id'])
            _require(value['status'] == 'containment_pending')
        return True
    return False


def observed_stage(store, run, states, records):
    """Return an attributed stage/explicit absence, or None before any node.

    Original record row order selects among genuine terminal attempts. Stored
    node order and second-resolution timestamps never select a stage.
    """
    try:
        starts = [row for row in records if row['kind'] == 'dispatch-start']
        dispatches = [row for row in records if row['kind'] == 'dispatch-record']
        node_gates = [row for row in records if row['kind'] == 'gate-decision'
                      and row['record'].get('scope_kind') == 'node']
        commits = [row for row in records if row['kind'] == 'acceptance-commit'
                   and row['record'].get('subnode_id') == '']
        by_node = {state['node_id']: state for state in states}
        _require(len(by_node) == len(states))
        for envelope in [*starts, *dispatches, *node_gates, *commits]:
            _require(envelope['record'].get('run_id') == run['id']
                     and envelope['record'].get('node_id') in by_node)
        order = {row['ref']['id']: index for index, row in enumerate(records)}
        active = []
        finished = []
        open_attempts = []
        for state in states:
            node_id = state['node_id']
            own_starts = [row for row in starts if row['record']['node_id'] == node_id]
            own_dispatches = [row for row in dispatches if row['record']['node_id'] == node_id]
            own_gates = [row for row in node_gates if row['record']['node_id'] == node_id]
            own_commits = [row for row in commits if row['record']['node_id'] == node_id]
            if state['state'] in {'pending', 'skipped'}:
                _require(not own_starts and not own_dispatches and not own_gates and not own_commits)
                continue
            if not own_starts:
                # An original failed Scheduler processing interval is a stage
                # observation. It supplies no Running/worker/cessation claim.
                _require(state['state'] == 'failed' and len(own_dispatches) == 1
                         and not own_gates and not own_commits)
                _prestart_dispatch(store, own_dispatches[0], run, state)
                finished.append((order[own_dispatches[0]['ref']['id']], node_id))
                continue
            _require(len(own_starts) == 1 and len(own_dispatches) <= 1)
            start, parent = _start(store, own_starts[0], run, state)
            own_gates = _execution_node_gates(store, own_gates, run, state, start['node_contract_ref'], parent)
            terminal = _dispatch(store, own_dispatches[0], run, state, start, parent) if own_dispatches else None
            if terminal is not None and terminal['outcome'] == 'interrupted':
                _claim_assignments(store, run, state, start['node_contract_ref'], parent)
            gates = [_node_gate(store, row, run, state, start['node_contract_ref'], parent) for row in own_gates]
            _require(all(order[own_starts[0]['ref']['id']] < order[row['ref']['id']]
                         for row in [*own_gates, *own_commits, *own_dispatches]))
            if terminal is not None and terminal['gate_decision_ref'] is not None:
                _require(len(own_gates) == 1 and terminal['gate_decision_ref'] == own_gates[0]['ref']
                         and terminal['check_plan_ref'] == gates[0]['check_plan_ref']
                         and terminal['output_gate_decision_refs'] == gates[0]['internal_decision_refs'])
            if state['state'] == 'completed':
                from .binding import committed_output_proof
                _require(len(own_commits) == len(own_gates) == 1)
                proof = committed_output_proof(store, run['id'], node_id, attempt_id=state['attempt_id'],
                                               parent_ref=start['node_contract_ref'])
                _require(proof['receipt_ref'] == own_commits[0]['ref']
                         and proof['receipt']['gate_decision_refs'] == [own_gates[0]['ref']]
                         and set(proof['outputs']) == set(parent['required_outputs'])
                         and order[own_gates[0]['ref']['id']] < order[proof['receipt_ref']['id']])
                _original(store, proof['receipt_ref'], 'acceptance-commit', run_id=run['id'],
                          node_id=node_id, attempt_id=state['attempt_id'])
                if terminal is not None:
                    _require(order[proof['receipt_ref']['id']] < order[own_dispatches[0]['ref']['id']]
                             and terminal['outcome'] == 'accepted'
                             and terminal['gate_decision_ref'] == own_gates[0]['ref']
                             and terminal['output_refs'] == gates[0]['accepted_refs'])
                finished.append((order[proof['receipt_ref']['id']], node_id))
            elif state['state'] == 'failed':
                _require(not own_commits and not store.accepted_outputs(run['id'], node_id))
                _require(all(gate['action'] != 'advance' for gate in gates))
                if terminal is not None:
                    _require(terminal['outcome'] != 'accepted' and not terminal['output_refs'])
                    if terminal['outcome'] in {'rejected', 'halted'}:
                        _require(len(own_gates) == 1 and terminal['gate_decision_ref'] == own_gates[0]['ref'])
                    finished.append((order[(own_gates[0] if own_gates else own_dispatches[0])['ref']['id']], node_id))
                else:
                    _require(len(own_gates) == 1)
                    finished.append((order[own_gates[0]['ref']['id']], node_id))
            elif state['state'] in {'running', 'evaluating'}:
                open_attempts.append(node_id)
                _require(not own_commits and terminal is None and not store.accepted_outputs(run['id'], node_id))
                _require(all(gate['action'] == 'advance' for gate in gates))
                if not _stopped_open(store, run, state, records, start['node_contract_ref'], parent):
                    _require(run['state'] in {'pending', 'running'})
                    active.append(node_id)
            else:
                _require(False)
        _require(len(active) <= 1 and len(open_attempts) <= 1)
        if active:
            return active[0]
        if finished:
            return max(finished)[1]
        return '' if states or starts or dispatches else None
    except (ResearchError, KeyError, TypeError, ValueError, UnicodeError, sqlite3.Error) as error:
        raise ResearchError('unavailable', 'Original execution chronology is unavailable') from error
