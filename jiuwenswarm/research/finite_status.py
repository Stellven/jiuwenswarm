"""Original finite mode provenance for display; never execution authority."""
from __future__ import annotations

import hashlib

from .contracts import ResearchError, validate
from .state import json_bytes

_SELECTION_KEYS = {'schema', 'id', 'run_id', 'account_id', 'workspace_id', 'submission_sha256',
                   'binding_ref', 'configuration_ref', 'intake_ref', 'evaluation_binding_ref', 'invalid_for_product'}
_BINDING_KEYS = {'schema', 'id', 'profile_ref', 'configuration_ref', 'template_ref', 'policy_ref', 'qualification_policy_ref'}
_POLICY_KEYS = {'schema', 'id', 'profile_ref', 'template_ref', 'plan_policy_ref', 'stages', 'terminal_ports', 'limits', 'cases'}
_QUALIFICATION_KEYS = {'schema', 'id', 'run_id', 'binding_ref', 'intake_ref', 'case_id', 'upload_refs',
                       'input_refs', 'visible_refs', 'body_refs', 'results', 'status', 'reason', 'invalid_for_product'}


def _require(condition):
    if not condition:
        raise ResearchError('unavailable', 'Original finite status provenance is unavailable')


def _closed(value, keys):
    _require(type(value) is dict and set(value) == keys)


def _original(store, ref, kind=None, contract=None):
    validate('Ref', ref)
    if kind is not None:
        _require(store.record_kind(ref) == kind)
    return store.read_record(ref, contract_id=contract) if contract else store.read_record(ref)


def _context(store, run, binding_ref, *, evaluation_ref=None):
    """Open immutable source joins, without current owner/Library callbacks."""
    submission = run['submission']
    _require(submission.get('plan_source') == 'static')
    evaluation = store.evaluation_binding(run['id'])
    _require(evaluation is not None)
    if evaluation_ref is not None:
        _require(evaluation['ref'] == evaluation_ref)
    actual = _original(store, evaluation['ref'], 'evaluation-run-binding')
    _require(actual == evaluation['record'] and actual['run_id'] == run['id']
             and actual['account_id'] == run['account_id'] and actual['workspace_id'] == run['workspace_id']
             and actual['configuration_ref'] == submission['configuration_ref']
             and actual['submission_sha256'] == hashlib.sha256(json_bytes(submission)).hexdigest()
             and actual['evaluation'] == submission.get('evaluation') and actual['invalid_for_product'] is True)
    binding = _original(store, binding_ref, 'finite-e1-binding')
    _closed(binding, _BINDING_KEYS)
    for key in _BINDING_KEYS - {'schema', 'id'}: validate('Ref', binding[key])
    _require(isinstance(binding['id'], str) and bool(binding['id'].strip()))
    _require(binding['schema'] == 'ai4r-finite-e1-binding:1'
             and binding['configuration_ref'] == submission['configuration_ref']
             and binding['profile_ref'] == actual['profile_ref'])
    configuration = _original(store, binding['configuration_ref'])
    _require(type(configuration) is dict)
    operator = configuration.get('operator', configuration)
    _require(type(operator) is dict)
    settings = operator.get('cc')
    _require(type(settings) is dict)
    _require(settings['evaluation_profile_ref'] == binding['profile_ref']
             and settings['static_template_ref'] == binding['template_ref']
             and settings['plan_policy_ref'] == binding['policy_ref'] and settings['plan_source'] == 'static')
    profile = _original(store, binding['profile_ref'], 'evaluation-profile', 'evaluation-profile')
    _require(profile['profile_id'] == submission.get('profile_id') == actual['evaluation_profile_id']
             and profile['invalid_for_product'] is True and profile['plan_source'] == 'static'
             and 'E1' in profile['allowed_entry_points']
             and profile['library_snapshot_sha256'] == actual['library_snapshot_ref']['sha256'])
    policy = _original(store, binding['qualification_policy_ref'], 'finite-e1-qualification-policy')
    _closed(policy, _POLICY_KEYS)
    _require(policy['schema'] == 'ai4r-finite-e1-qualification-policy:1'
             and policy['profile_ref'] == binding['profile_ref'] and policy['template_ref'] == binding['template_ref']
             and policy['plan_policy_ref'] == binding['policy_ref']
             and policy['stages'] in (['research.screening'], ['research.screening', 'research.hypothesis']))
    template = _original(store, binding['template_ref'], 'static-template', 'static-template')
    plan_policy = _original(store, binding['policy_ref'], 'plan-policy', 'plan-policy')
    _require([node['cc']['cc_name'] for node in template['nodes']] == policy['stages']
             and plan_policy['required_stages'] == policy['stages'])
    intake = _original(store, submission['intake_ref'], 'qualified-intake', 'qualified-intake')
    _require(intake['user_id'] == run['account_id'])
    return evaluation, binding


def _selection(store, run, envelope):
    value = _original(store, envelope['ref'], 'finite-e1-run-selection')
    _require(value == envelope['record'])
    _closed(value, _SELECTION_KEYS)
    expected = 'finite-selection:' + hashlib.sha256(json_bytes([run['id'], value['binding_ref'], run['submission']['intake_ref']])).hexdigest()
    _require(value['schema'] == 'ai4r-finite-e1-run-selection:1' and value['id'] == envelope['ref']['id'] == expected
             and value['run_id'] == run['id'] and value['account_id'] == run['account_id']
             and value['workspace_id'] == run['workspace_id'] and value['invalid_for_product'] is True
             and value['submission_sha256'] == hashlib.sha256(json_bytes(run['submission'])).hexdigest()
             and value['configuration_ref'] == run['submission']['configuration_ref']
             and value['intake_ref'] == run['submission']['intake_ref'])
    _context(store, run, value['binding_ref'], evaluation_ref=value['evaluation_binding_ref'])
    return value


def record_selection(store, run_id, protected):
    """Called only by fresh authenticated allocation, before scheduling work."""
    ref = protected.get('finite_e1_binding_ref')
    if ref is None:
        return None
    try:
        run = store.get_run(run_id)
        evaluation, _ = _context(store, run, ref)
        intake = store.read_record(run['submission']['intake_ref'], contract_id='qualified-intake')
        _require(protected.get('configuration_ref') == run['submission']['configuration_ref']
                 and protected.get('profile_id') == run['submission'].get('profile_id')
                 and all(protected.get(key) == intake[key] for key in ('profile_ref', 'workspace_ref', 'input_directory_ref')))
        value = {'schema': 'ai4r-finite-e1-run-selection:1',
            'id': 'finite-selection:' + hashlib.sha256(json_bytes([run_id, ref, run['submission']['intake_ref']])).hexdigest(),
            'run_id': run_id, 'account_id': run['account_id'], 'workspace_id': run['workspace_id'],
            'submission_sha256': hashlib.sha256(json_bytes(run['submission'])).hexdigest(),
            'binding_ref': ref, 'configuration_ref': run['submission']['configuration_ref'],
            'intake_ref': run['submission']['intake_ref'], 'evaluation_binding_ref': evaluation['ref'], 'invalid_for_product': True}
        prior = list(store.iter_records(run_id=run_id, kinds=('finite-e1-run-selection',)))
        if prior:
            _require(len(prior) == 1 and _selection(store, run, prior[0]) == value)
            return prior[0]['ref']
        captured = store.append_record('finite-e1-run-selection', value)
        store.mark_evaluation_material(run_id, captured)
        return captured
    except (ResearchError, ValueError, KeyError, TypeError, UnicodeError) as error:
        raise ResearchError('unavailable', 'Protected finite display selection could not be persisted') from error


def selected_for_status(store, run):
    """Read original provenance only; no eligibility, qualification or writes."""
    try:
        selections = list(store.iter_records(run_id=run['id'], kinds=('finite-e1-run-selection',)))
        qualifications = list(store.iter_records(run_id=run['id'], kinds=('finite-e1-fixture-qualification',)))
        _require(len(selections) <= 1 and len(qualifications) <= 1)
        selected = _selection(store, run, selections[0]) if selections else None
        if qualifications:
            envelope = qualifications[0]
            value = _original(store, envelope['ref'], 'finite-e1-fixture-qualification')
            _closed(value, _QUALIFICATION_KEYS)
            identity = 'finite-qualification:' + hashlib.sha256(json_bytes([run['id'], value['binding_ref'], run['submission']['intake_ref']])).hexdigest()
            _require(value == envelope['record'] and value['schema'] == 'ai4r-finite-e1-fixture-qualification:1'
                     and value['id'] == envelope['ref']['id'] == identity and value['run_id'] == run['id']
                     and value['intake_ref'] == run['submission']['intake_ref'] and value['invalid_for_product'] is True
                     and value['case_id'] == run['submission']['evaluation']['run_id'])
            _context(store, run, value['binding_ref'])
            if selected is not None:
                _require(value['binding_ref'] == selected['binding_ref'])
            from .finite_evaluation import QUALIFICATION_CHECKS
            checks = value['results']
            _require(type(checks) is list and [row['check_id'] for row in checks] == list(QUALIFICATION_CHECKS))
            for row in checks:
                _closed(row, {'check_id', 'outcome', 'reason', 'evidence_refs'})
                _require(row['outcome'] in {'PASS', 'FAIL', 'ENVIRONMENT_BLOCKED', 'INCONCLUSIVE'}
                         and isinstance(row['reason'], str) and row['reason'].strip() and type(row['evidence_refs']) is list)
                for ref in row['evidence_refs']: validate('Ref', ref)
            _require(value['status'] in {'qualified', 'rejected', 'blocked'})
            if value['status'] == 'qualified':
                _require(value['reason'] is None and all(row['outcome'] == 'PASS' for row in checks))
            else:
                _require(isinstance(value['reason'], str) and value['reason'].strip()
                         and any(row['outcome'] != 'PASS' for row in checks))
            return True
        if selected is None:
            _require(not list(store.iter_records(run_id=run['id'], kinds=('finite-e1-plan-binding',)))
                     and run.get('reason') != 'finite_selection_unavailable')
        return selected is not None
    except (ResearchError, ValueError, KeyError, TypeError, UnicodeError) as error:
        raise ResearchError('unavailable', 'Original finite status provenance is unavailable') from error
