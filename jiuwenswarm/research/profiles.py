"""Protected finite evaluation profiles and actual E4 fault attribution.

Definitions are captured by the launcher. A client selects only an identity;
this module cannot publish a gate, accept an artifact or change library state.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import math
import re
import time
from collections.abc import Mapping

from .contracts import ResearchError, validate
from .state import json_bytes, utc_now


def _require(condition, message, code='evaluation_profile'):
    if not condition:
        raise ResearchError(code, message)


def _closed(value, keys):
    _require(isinstance(value, dict) and set(value) == set(keys), 'Invalid protected evaluation definition')


def _text(value):
    return isinstance(value, str) and bool(value) and len(value) <= 256


class EvaluationProfiles:
    """One startup-pinned source profile; no public definition registration."""

    def __init__(self, store, operator, *, fault_plan_ref=None, fixture_index_ref=None):
        self.store = store
        self._operator = operator.snapshot()
        self._profile_ref = copy.deepcopy(self._operator['cc']['evaluation_profile_ref'])
        self._fault_plan_ref = copy.deepcopy(fault_plan_ref)
        self._fixture_index_ref = copy.deepcopy(fixture_index_ref)
        self._faults, self._fixtures = {}, {}
        self._campaign = None
        self._profile = None
        if self._profile_ref is None:
            _require(fault_plan_ref is None and fixture_index_ref is None, 'Product mode has no evaluation definitions')
            return
        profile = self._read(self._profile_ref, 'evaluation-profile', contract='evaluation-profile')
        self._validate_profile(profile)
        self._profile = profile
        if fault_plan_ref is not None:
            _require('E4' in profile['allowed_entry_points'], 'Profile does not allow fault injection')
            plan = self._read(fault_plan_ref, 'evaluation-fault-plan')
            _closed(plan, {'schema', 'id', 'profile_ref', 'campaign_id', 'fault_plan'})
            _require(plan['schema'] == 'ai4r-evaluation-faults:1' and _text(plan['id'])
                     and plan['profile_ref'] == self._profile_ref and _text(plan['campaign_id']),
                     'Fault plan is not bound to this approved profile')
            _require(isinstance(plan['fault_plan'], list) and bool(plan['fault_plan']), 'Fault plan is empty')
            self._campaign = plan['campaign_id']
            for fault in plan['fault_plan']:
                self._validate_fault(fault)
                _require(fault['fault_id'] not in self._faults, 'Duplicate fault identity')
                self._faults[fault['fault_id']] = copy.deepcopy(fault)
        if fixture_index_ref is not None:
            _require(fault_plan_ref is not None, 'Fixture index needs its protected campaign fault plan')
            index = self._read(fixture_index_ref, 'evaluation-fixture-index')
            _closed(index, {'schema', 'id', 'profile_ref', 'campaign_id', 'entries'})
            _require(index['schema'] == 'ai4r-evaluation-fixtures:1' and _text(index['id'])
                     and index['profile_ref'] == self._profile_ref and index['campaign_id'] == self._campaign,
                     'Fixture index differs from the protected campaign')
            _require(isinstance(index['entries'], list), 'Invalid fixture inventory')
            for entry in index['entries']:
                _closed(entry, {'fixture_id', 'artifact_type', 'artifact_ref'})
                _require(_text(entry['fixture_id']) and _text(entry['artifact_type'])
                         and entry['fixture_id'] not in self._fixtures, 'Invalid or duplicate fixture identity')
                self.store.read_blob(entry['artifact_ref'])
                self._fixtures[entry['fixture_id']] = copy.deepcopy(entry)
        for fault in self._faults.values():
            if fault['kind'] == 'swap_artifact':
                fixture = self._fixtures.get(fault['parameters']['swap_fixture_id'])
                _require(fixture is not None and fixture['artifact_type'] == fault['target']['artifact_type'],
                         'Exact protected replacement fixture is unavailable')

    @property
    def profile_ref(self):
        return copy.deepcopy(self._profile_ref)

    @property
    def fault_plan_ref(self):
        return copy.deepcopy(self._fault_plan_ref)

    @property
    def fixture_index_ref(self):
        return copy.deepcopy(self._fixture_index_ref)

    @property
    def profile_id(self):
        return self._profile['profile_id'] if self._profile else None

    @property
    def invalid_for_product(self):
        return self._profile['invalid_for_product'] if self._profile else False

    @property
    def fault_injection(self):
        return bool(self._profile and 'E4' in self._profile['allowed_entry_points'] and self._faults)

    def _read(self, ref, kind, *, contract=None):
        _require(self.store.record_kind(ref) == kind, 'Protected definition has the wrong capture kind')
        return self.store.read_record(ref, contract_id=contract)

    def _validate_profile(self, profile):
        settings = self._operator['cc']
        _require(profile['plan_source'] == settings['plan_source']
                 and profile['router_enabled'] == settings['router']['enabled'], 'Profile differs from operator settings')
        _require((profile['router_version'] is None) == (profile['router_enabled'] is False), 'Invalid router version pin')
        _require(profile['router_enabled'] or profile['model_route'] == self._operator['codex']['route_id'],
                 'Fixed route differs from operator settings')
        points = profile['allowed_entry_points']
        pins = profile['candidate_pins']
        _require(len(points) == len(set(points)) and len(pins) == len({p['cc_name'] for p in pins}),
                 'Duplicate entry point or candidate pin')
        _require(profile['invalid_for_product'] or (set(points) <= {'E1'} and not pins),
                 'Evaluation-only output must be marked invalid for product')
        self.store.read_blob(profile['verifier_cc_ref'])

    def _validate_fault(self, fault):
        _closed(fault, {'fault_id', 'kind', 'target', 'parameters', 'expected_observation_sha256'})
        _require(_text(fault['fault_id']) and isinstance(fault['expected_observation_sha256'], str)
                 and re.fullmatch('[a-f0-9]{64}', fault['expected_observation_sha256']) is not None,
                 'Invalid protected fault identity')
        _closed(fault['target'], {'node_id', 'artifact_type'})
        parameters = fault['parameters']
        if fault['kind'] == 'delay_gate_persistence':
            _closed(parameters, {'node_id', 'delay_s'})
            delay = parameters['delay_s']
            _require(type(delay) in (int, float) and math.isfinite(delay) and 1 <= delay <= 600
                     and fault['target']['artifact_type'] is None, 'Invalid source gate delay')
        elif fault['kind'] == 'swap_artifact':
            _closed(parameters, {'node_id', 'swap_fixture_id'})
            _require(_text(parameters['swap_fixture_id']) and _text(fault['target']['artifact_type']),
                     'Invalid protected artifact swap')
        else:
            raise ResearchError('evaluation_profile', 'Unsupported source fault kind')
        _require(_text(parameters['node_id']) and fault['target']['node_id'] == parameters['node_id'],
                 'Fault target differs from its parameters')

    def validate_submission(self, submission, protected, *, principal):
        _require(self._profile is not None, 'Product mode has no evaluation profile')
        profile = self._read(self._profile_ref, 'evaluation-profile', contract='evaluation-profile')
        _require(profile == self._profile, 'Approved profile cannot change in place')
        self._definitions_intact()
        principal.require('submit', submission.get('workspace_id'))
        _require(submission.get('account_id') == principal.account_id, 'Evaluation account differs from authenticated account', 'auth')
        _require('E1' in profile['allowed_entry_points'] and submission.get('profile_id') == profile['profile_id']
                 and protected.get('profile_id') == profile['profile_id']
                 and submission.get('plan_source') == profile['plan_source']
                 and protected.get('plan_source') == profile['plan_source'], 'Submission differs from the frozen profile')
        evaluation = submission.get('evaluation')
        _closed(evaluation, {'campaign_id', 'run_id', 'inventory_id'})
        _require(all(_text(value) for value in evaluation.values()), 'Evaluation link is incomplete')
        _require(submission.get('configuration_ref') == protected.get('configuration_ref'), 'Configuration reference differs')
        configuration = self.store.read_record(protected['configuration_ref'])
        _require(configuration.get('operator', configuration) == self._operator, 'Configuration bytes differ from approved settings')
        snapshot_ref = protected.get('library_snapshot_ref')
        snapshot = self._read(snapshot_ref, 'library-snapshot', contract='library-snapshot')
        pins = protected.get('run_pins')
        validate('RunPins', pins)
        _require(snapshot_ref['sha256'] == profile['library_snapshot_sha256'] == pins['library_snapshot_sha256']
                 and pins['plan_policy_ref'] == self._operator['cc']['plan_policy_ref']
                 and pins['router_enabled'] == profile['router_enabled']
                 and pins['router_version'] == profile['router_version'], 'Run pins differ from the frozen profile')
        _require(protected.get('verifier_cc_ref') == profile['verifier_cc_ref']
                 and list(protected.get('candidate_pins', ())) == profile['candidate_pins'], 'Verifier or candidate pins differ')
        self.store.read_blob(profile['verifier_cc_ref'])
        entries = {(e['cc_name'], e['cc_version'], e['declaration_sha256']) for e in snapshot['entries']}
        for pin in profile['candidate_pins']:
            _require(tuple(pin[k] for k in ('cc_name', 'cc_version', 'declaration_sha256')) in entries,
                     'Candidate is not admitted in the exact snapshot')
        if submission.get('fault_id') is not None:
            principal.require('evaluation_profile', submission['workspace_id'])
            _require(self.fault_injection and submission['fault_id'] in self._faults
                     and evaluation['campaign_id'] == self._campaign, 'Fault is outside the protected campaign')

    def _definition_pin(self):
        # No traversal-capable private definition Ref enters public run records.
        return hashlib.sha256(json_bytes([self._fault_plan_ref, self._fixture_index_ref])).hexdigest()

    def _definitions_intact(self):
        for ref, kind in ((self._fault_plan_ref, 'evaluation-fault-plan'),
                          (self._fixture_index_ref, 'evaluation-fixture-index')):
            if ref is not None:
                self._read(ref, kind)

    def bind_run(self, run_id, submission, protected, *, principal):
        self.validate_submission(submission, protected, principal=principal)
        run = self.store.get_run(run_id, account_id=principal.account_id)
        _require(run['submission'] == submission and run['workspace_id'] == submission['workspace_id'],
                 'Evaluation binding must name the actual allocated submission')
        record = {'id': 'evaluation-binding:' + hashlib.sha256(run_id.encode()).hexdigest(), 'run_id': run_id,
                  'account_id': run['account_id'], 'workspace_id': run['workspace_id'], 'profile_ref': self._profile_ref,
                  'evaluation_profile_id': self.profile_id, 'evaluation': copy.deepcopy(submission['evaluation']),
                  'submission_sha256': hashlib.sha256(json_bytes(submission)).hexdigest(),
                  'configuration_ref': protected['configuration_ref'], 'library_snapshot_ref': protected['library_snapshot_ref'],
                  'verifier_cc_ref': protected['verifier_cc_ref'], 'candidate_pins': copy.deepcopy(self._profile['candidate_pins']),
                  'run_pins': copy.deepcopy(protected['run_pins']), 'fault_id': submission.get('fault_id'),
                  'fault_configuration_sha256': self._definition_pin(), 'invalid_for_product': self.invalid_for_product}
        return self.store.append_record('evaluation-run-binding', record)

    def _binding(self, run_id):
        run = self.store.get_run(run_id)
        if run['submission'].get('profile_id') is None:
            return None
        rows = list(self.store.iter_records(run_id=run_id, kinds=('evaluation-run-binding',)))
        _require(len(rows) == 1, 'Run has no unique protected evaluation binding')
        binding = rows[0]['record']
        _require(binding['profile_ref'] == self._profile_ref and binding['evaluation_profile_id'] == self.profile_id
                 and binding['fault_configuration_sha256'] == self._definition_pin()
                 and binding['account_id'] == run['account_id'] and binding['workspace_id'] == run['workspace_id']
                 and binding['evaluation'] == run['submission'].get('evaluation')
                 and binding['fault_id'] == run['submission'].get('fault_id')
                 and binding['submission_sha256'] == hashlib.sha256(json_bytes(run['submission'])).hexdigest(),
                 'Run differs from its protected evaluation binding')
        self._read(self._profile_ref, 'evaluation-profile', contract='evaluation-profile')
        self._definitions_intact()
        return binding

    def _target(self, context, kind, *, contract_kind):
        binding = self._binding(context['run_id'])
        if binding is None or binding['fault_id'] is None:
            return None
        fault = self._faults.get(binding['fault_id'])
        _require(fault is not None, 'Bound fault definition is unavailable')
        if fault['kind'] != kind:
            return None
        contract = self._read(context['contract_ref'], contract_kind, contract=contract_kind)
        _require(contract['run_id'] == context['run_id'], 'Fault context belongs to another run')
        if contract['node_id'] != fault['parameters']['node_id']:
            return None
        _require(not self.store.cancellation_requested(context['run_id']), 'Cancelled run cannot inject an effect', 'cancelled')
        return binding, fault, contract

    def _claim(self, binding, fault, context):
        identity = [binding['run_id'], self._profile_ref, fault['fault_id'], fault['parameters']['node_id']]
        key = 'evaluation-fault:' + hashlib.sha256(json_bytes(identity)).hexdigest()
        with self.store.transaction() as db:
            existing = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            _require(existing is None, 'Fault effect was already claimed; reconcile retained evidence', 'fault_already_claimed')
            db.execute('INSERT INTO metadata(key,value) VALUES(?,?)', (key, json_bytes(context).decode()))
        return key

    async def after_capture(self, context):
        _closed(context, {'run_id', 'contract_ref', 'output_refs'})
        _require(isinstance(context['output_refs'], Mapping), 'Captured outputs must be a port mapping')
        originals = copy.deepcopy(dict(context['output_refs']))
        for ref in originals.values():
            self.store.read_blob(ref)
        target = self._target(context, 'swap_artifact', contract_kind='subnode-execution-contract')
        if target is None:
            return {'output_refs': originals}
        binding, fault, contract = target
        ports = [port['name'] for port in contract['outputs'] if port['contract_id'] == fault['target']['artifact_type']
                 and port['name'] in originals]
        if not ports:
            return {'output_refs': originals}
        _require(len(ports) == 1, 'Fault target must identify one captured output port')
        fixture = self._fixtures[fault['parameters']['swap_fixture_id']]
        replacement = fixture['artifact_ref']
        self.store.read_blob(replacement)
        _require(replacement != originals[ports[0]], 'Fault must substitute a distinct captured artifact')
        claim = self._claim(binding, fault, context)
        selected = originals | {ports[0]: copy.deepcopy(replacement)}
        self.store.append_record('fault-injection', {'id': claim + ':injected', 'run_id': context['run_id'],
            'node_id': contract['node_id'], 'evaluation_profile_id': self.profile_id, 'fault_id': fault['fault_id'],
            'kind': fault['kind'], 'injected_at': utc_now(), 'contract_ref': context['contract_ref'],
            'original_refs': originals, 'replacement_refs': selected, 'invalid_for_product': True})
        return {'output_refs': selected}

    async def before_advance(self, context):
        _closed(context, {'run_id', 'node_id', 'contract_ref', 'decision_id', 'deadline_monotonic_s'})
        deadline = context['deadline_monotonic_s']
        _require(type(deadline) in (int, float) and math.isfinite(deadline)
                 and _text(context['decision_id']), 'A real protected deadline and decision identity are required')
        target = self._target(context, 'delay_gate_persistence', contract_kind='node-execution-contract')
        if target is None:
            return
        binding, fault, contract = target
        _require(context['node_id'] == contract['node_id'], 'Node delay context differs from its frozen contract')
        remaining = deadline - time.monotonic()
        _require(remaining > 0, 'Node deadline exhausted before gate persistence', 'budget_exhausted')
        claim = self._claim(binding, fault, context)
        self.store.append_record('fault-injection', {'id': claim + ':injected', 'run_id': context['run_id'],
            'node_id': contract['node_id'], 'evaluation_profile_id': self.profile_id, 'fault_id': fault['fault_id'],
            'kind': fault['kind'], 'injected_at': utc_now(), 'contract_ref': context['contract_ref'],
            'decision_id': context['decision_id'], 'delay_s': fault['parameters']['delay_s'], 'invalid_for_product': True})
        began = time.monotonic()
        outcome = 'failed'
        try:
            await asyncio.wait_for(asyncio.sleep(fault['parameters']['delay_s']), timeout=remaining)
            _require(time.monotonic() < deadline, 'Node deadline exhausted during gate delay', 'budget_exhausted')
            _require(not self.store.cancellation_requested(context['run_id']), 'Run cancelled during gate delay', 'cancelled')
            outcome = 'completed'
        except TimeoutError as error:
            outcome = 'budget_exhausted'
            raise ResearchError('budget_exhausted', 'Node deadline exhausted during gate delay') from error
        except asyncio.CancelledError:
            outcome = 'cancelled'
            raise
        except ResearchError as error:
            outcome = error.code
            raise
        finally:
            try:
                self.store.append_record('fault-injection-outcome', {'id': claim + ':outcome', 'run_id': context['run_id'],
                    'node_id': contract['node_id'], 'fault_id': fault['fault_id'], 'outcome': outcome,
                    'elapsed_s': time.monotonic() - began, 'recorded_at': utc_now(), 'invalid_for_product': True})
            except Exception:
                # Audit failure still prevents advancement; task cancellation
                # must reach the coordinator even when its last capture fails.
                if outcome == 'cancelled':
                    raise asyncio.CancelledError
                raise
