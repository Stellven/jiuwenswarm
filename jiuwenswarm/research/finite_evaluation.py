"""Protected finite E1 definitions; imported inputs never imply acceptance.

Only server composition can install this owner. Public profile names and marker
fields do not choose a graph, qualify an input or grant an execution capability.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

from .contracts import ResearchError, validate
from .state import json_bytes, utc_now


QUALIFICATION_CHECKS = (
    'finite_binding', 'owned_upload_custody', 'visible_ref_closure', 'typed_contracts',
    'source_relations', 'module_scope', 'admitted_body_pins', 'resource_environment',
    'qualifier_implementation',
)
FINITE_PLAN_CHECKS = (
    'template_structure', 'brief_coverage', 'library_membership', 'port_type_compatibility',
    'dependency_closure', 'acyclicity', 'finite_delivery_leaf_coverage_v1',
    'mandatory_check_bundle_present', 'effects_within_policy', 'resource_feasibility',
    'budget_ceilings', 'finite_fixture_qualification_v1',
)
_BINDING_KEYS = {'schema', 'id', 'profile_ref', 'configuration_ref', 'template_ref',
                 'policy_ref', 'qualification_policy_ref'}
_POLICY_KEYS = {'schema', 'id', 'profile_ref', 'template_ref', 'plan_policy_ref',
                'stages', 'terminal_ports', 'limits', 'cases'}
_LIMIT_KEYS = {'max_uploads', 'max_total_bytes', 'max_member_bytes', 'max_visible_refs',
               'max_archive_members', 'max_archive_uncompressed_bytes'}
_SCOPE_KEYS = {'mandatory_requirements', 'deliverables', 'acceptance_expectations',
               'evidence_obligations', 'target_metrics'}
_INPUT_CONTRACTS = {'brief': 'research-brief', 'candidate_set': 'candidate-set',
                    'baseline_resource': 'resource-snapshot',
                    'validation_resource': 'resource-snapshot'}
_VISIBLE_CONTRACTS = {'research-brief', 'candidate-set', 'resource-snapshot', 'search-scope',
                      'qualified-intake', 'intent-ir', 'default-policy', 'environment-lock'}


def _require(condition, message, code='finite_e1_binding'):
    if not condition:
        raise ResearchError(code, message)


def _closed(value, keys):
    _require(type(value) is dict and set(value) == set(keys), 'Finite definition has missing or unknown fields')


def _text(value):
    return isinstance(value, str) and bool(value.strip())


class FiniteE1:
    """Exact captured binding, independent of any client-selected graph or path."""

    def __init__(self, store, operator, *, binding_ref, configuration_ref, library):
        self.store = store
        self.library = library
        self._operator = copy.deepcopy(operator.snapshot())
        validate('Ref', configuration_ref)
        self._configuration_ref = copy.deepcopy(configuration_ref)
        captured = store.read_record(configuration_ref)
        _require(captured.get('operator', captured) == self._operator,
                 'Finite configuration differs from protected operator bytes')
        validate('Ref', binding_ref)
        binding = self._read(binding_ref, 'finite-e1-binding')
        _closed(binding, _BINDING_KEYS)
        _require(binding['schema'] == 'ai4r-finite-e1-binding:1' and _text(binding['id']),
                 'Unsupported finite binding identity')
        for key in _BINDING_KEYS - {'schema', 'id'}:
            validate('Ref', binding[key])
        settings = self._operator['cc']
        _require(binding['configuration_ref'] == configuration_ref
                 and binding['profile_ref'] == settings['evaluation_profile_ref']
                 and binding['template_ref'] == settings['static_template_ref']
                 and binding['policy_ref'] == settings['plan_policy_ref']
                 and settings['plan_source'] == 'static',
                 'Finite binding is not the exact approved static configuration')
        profile = self._read(binding['profile_ref'], 'evaluation-profile', 'evaluation-profile')
        _require(profile['invalid_for_product'] is True and 'E1' in profile['allowed_entry_points']
                 and profile['plan_source'] == 'static'
                 and profile['router_enabled'] == settings['router']['enabled'],
                 'Finite work requires its approved evaluation-only E1 profile')
        if not profile['router_enabled']:
            _require(profile['router_version'] is None and profile['model_route'] == self._operator['codex']['route_id'],
                     'Finite fixed model route differs from the approved configuration')
        template = self._read(binding['template_ref'], 'static-template', 'static-template')
        policy = self._read(binding['policy_ref'], 'plan-policy', 'plan-policy')
        qualification = self._read(binding['qualification_policy_ref'], 'finite-e1-qualification-policy')
        _closed(qualification, _POLICY_KEYS)
        _require(qualification['schema'] == 'ai4r-finite-e1-qualification-policy:1'
                 and _text(qualification['id'])
                 and qualification['profile_ref'] == binding['profile_ref']
                 and qualification['template_ref'] == binding['template_ref']
                 and qualification['plan_policy_ref'] == binding['policy_ref'],
                 'Fixture qualification policy differs from the protected binding')
        stages = qualification['stages']
        _require(stages in (['research.screening'], ['research.screening', 'research.hypothesis']),
                 'Unsupported finite stage inventory')
        _require([node['cc']['cc_name'] for node in template['nodes']] == stages
                 and policy['required_stages'] == stages,
                 'Finite template and policy must independently pin the exact stage inventory')
        if len(stages) == 1:
            _require(profile['profile_id'] == 'qa_capsule_screening_v1', 'Single Screening profile identity is not approved')
        else:
            _require(profile['profile_id'] != 'qa_capsule_screening_v1',
                     'A segment needs its own independently approved profile')
        _require(qualification['terminal_ports'] == [port['name'] for port in template['nodes'][-1]['outputs']]
                 and bool(qualification['terminal_ports']), 'Finite terminal output inventory differs')
        _closed(qualification['limits'], _LIMIT_KEYS)
        _require(all(type(value) is int and value > 0 for value in qualification['limits'].values()),
                 'Positive protected qualification bounds are required')
        _require(type(qualification['cases']) is list and bool(qualification['cases']),
                 'Finite qualification needs an independently preregistered case inventory')
        required_inputs = {'brief', 'candidate_set', 'original_request'}
        if len(stages) == 2:
            required_inputs |= {'baseline_resource', 'validation_resource'}
        cases = {}
        for case in qualification['cases']:
            self._validate_case(case, required_inputs, qualification, template)
            _require(case['case_id'] not in cases, 'Duplicate preregistered finite case correlation')
            cases[case['case_id']] = copy.deepcopy(case)
        _require(library is not None and getattr(library, 'store', None) is store,
                 'Finite Library owner is unavailable', 'unavailable')
        self._binding_ref = copy.deepcopy(binding_ref)
        self._binding = copy.deepcopy(binding)
        self._profile = copy.deepcopy(profile)
        self._template = copy.deepcopy(template)
        self._policy = copy.deepcopy(policy)
        self._qualification = copy.deepcopy(qualification)
        self._cases = cases
        self._context_token = object()
        # Keep exact original source bytes; object compatibility alone grants nothing.
        self._definitions = {json_bytes(ref): store.read_blob(ref) for ref in (
            binding_ref, configuration_ref, binding['profile_ref'], binding['template_ref'],
            binding['policy_ref'], binding['qualification_policy_ref'])}

    def _read(self, ref, kind, contract=None):
        validate('Ref', ref)
        _require(self.store.record_kind(ref) == kind, 'Finite definition has the wrong protected capture kind')
        return self.store.read_record(ref, contract_id=contract)

    @staticmethod
    def _validate_case(case, required_inputs, qualification, template):
        _closed(case, {'case_id', 'request_sha256', 'uploads', 'inputs', 'module_scope'})
        _require(_text(case['case_id']) and isinstance(case['request_sha256'], str)
                 and re.fullmatch('[0-9a-f]{64}', case['request_sha256']) is not None,
                 'Finite case correlation/request hash is incomplete')
        _closed(case['inputs'], required_inputs)
        _require(all(case['inputs'][name] == name for name in required_inputs),
                 'A typed finite input must name its own unique primary role')
        _closed(case['module_scope'], _SCOPE_KEYS)
        _require(all(type(value) is list for value in case['module_scope'].values()),
                 'Module Brief scope must be independently captured exact record arrays')
        types = {port['artifact_type'] for port in template['nodes'][-1]['outputs']}
        _require(bool(case['module_scope']['deliverables']) and all(
            type(value) is dict and value.get('artifact_type') in types
            for value in case['module_scope']['deliverables']),
            'Finite outputs cannot fulfill the promised Brief deliverables')
        slots = case['uploads']
        _require(type(slots) is list and bool(slots), 'Finite case visible upload inventory is absent')
        uploaded_roles = required_inputs - {'original_request'}
        identities, refs, roles, uploads = set(), {}, {}, set()
        for slot in slots:
            _closed(slot, {'filename', 'kind', 'role', 'contract_id', 'artifact_ref', 'source'})
            _require(isinstance(slot['filename'], str)
                     and re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', slot['filename']) is not None
                     and slot['kind'] in {'docs', 'repo', 'datasets'}
                     and slot['source'] in {'original', 'extracted'}
                     and (slot['source'] != 'extracted' or slot['kind'] == 'docs'),
                     'Finite slot differs from the existing safe upload transport')
            validate('Ref', slot['artifact_ref'])
            _require(slot['role'] in uploaded_roles | {'visible_support'}, 'Unknown finite input role')
            expected = _INPUT_CONTRACTS.get(slot['role'])
            _require(slot['contract_id'] == expected if expected else slot['contract_id'] in _VISIBLE_CONTRACTS | {None},
                     'Finite slot contract is unsupported or differs from its typed role')
            identity = (slot['filename'], slot['kind'], slot['source'])
            _require(identity not in identities, 'Ambiguous duplicate visible upload slot')
            identities.add(identity)
            uploads.add((slot['filename'], slot['kind']))
            ref = slot['artifact_ref']
            _require(ref['id'] not in refs or refs[ref['id']] == ref['sha256'],
                     'An immutable visible Ref ID cannot name different bytes')
            refs[ref['id']] = ref['sha256']
            roles[slot['role']] = roles.get(slot['role'], 0) + 1
        _require(all(roles.get(name) == 1 for name in uploaded_roles), 'Finite primary input role is missing or ambiguous')
        _require(len(uploads) <= qualification['limits']['max_uploads']
                 and len(refs) + 1 <= qualification['limits']['max_visible_refs'],
                 'Preregistered visible inventory exceeds its own protected bounds')

    @property
    def binding_ref(self):
        return copy.deepcopy(self._binding_ref)

    def _intact(self):
        for encoded, expected in self._definitions.items():
            _require(self.store.read_blob(json.loads(encoded)) == expected,
                     'Captured finite definition changed in place')

    @staticmethod
    def _json(raw):
        def members(rows):
            value = {}
            for key, item in rows:
                _require(key not in value, 'Duplicate JSON member in visible fixture', 'finite_fixture')
                value[key] = item
            return value
        try:
            value = json.loads(raw.decode('utf-8', errors='strict'), object_pairs_hook=members,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
        except (ValueError, UnicodeError) as error:
            raise ResearchError('finite_fixture', 'Visible typed fixture is not strict finite UTF-8 JSON') from error
        _require(type(value) is dict, 'Visible typed fixture must be one object', 'finite_fixture')
        return value

    @staticmethod
    def _refs(value):
        if isinstance(value, dict):
            if set(value) == {'id', 'sha256'}:
                validate('Ref', value)
                yield value
            else:
                for item in value.values():
                    yield from FiniteE1._refs(item)
        elif isinstance(value, list):
            for item in value:
                yield from FiniteE1._refs(item)

    def _run(self, run_id, protected):
        self._intact()
        run = self.store.get_run(run_id)
        submission = run['submission']
        _require(protected.get('finite_e1_binding_ref') == self._binding_ref
                 and protected.get('configuration_ref') == submission.get('configuration_ref') == self._configuration_ref
                 and protected.get('profile_id') == submission.get('profile_id') == self._profile['profile_id']
                 and submission.get('plan_source') == 'static', 'Run differs from protected finite definitions')
        binding = self.store.evaluation_binding(run_id)
        _require(binding is not None, 'Finite run has no actual protected evaluation binding')
        actual = binding['record']
        _require(actual['profile_ref'] == self._binding['profile_ref'] and actual['configuration_ref'] == self._configuration_ref
                 and actual['account_id'] == run['account_id'] and actual['workspace_id'] == run['workspace_id']
                 and actual['invalid_for_product'] is True
                 and actual['submission_sha256'] == hashlib.sha256(json_bytes(submission)).hexdigest(),
                 'Finite run ownership/profile binding differs')
        intake = self.store.read_record(submission['intake_ref'], contract_id='qualified-intake')
        _require(intake['user_id'] == run['account_id'], 'Finite intake belongs to another account', 'auth')
        for key in ('profile_ref', 'workspace_ref', 'input_directory_ref'):
            _require(protected.get(key) == intake[key], 'Finite intake differs from its protected workspace', 'auth')
        evaluation = submission.get('evaluation')
        _require(type(evaluation) is dict and _text(evaluation.get('run_id')), 'Finite case correlation is absent')
        return run, intake, evaluation['run_id']

    def implementation_refs(self):
        from .checks import research
        from . import finite_archive
        return [self.store.put_blob(path.read_bytes(), media_type='text/x-python')
                for path in (Path(__file__), Path(research.__file__), Path(finite_archive.__file__))]

    def qualify(self, run_id, protected):
        """Read exact live owned uploads; capture a result without dispatching."""
        run, intake, case_id = self._run(run_id, protected)
        intake_ref = run['submission']['intake_ref']
        identity = 'finite-qualification:' + hashlib.sha256(json_bytes([run_id, self._binding_ref, intake_ref])).hexdigest()
        prior = list(self.store.iter_records(run_id=run_id, kinds=('finite-e1-fixture-qualification',)))
        if prior:
            _require(len(prior) == 1 and prior[0]['record']['id'] == identity
                     and prior[0]['record']['binding_ref'] == self._binding_ref
                     and prior[0]['record']['intake_ref'] == intake_ref,
                     'Finite qualification identity cannot be replaced')
            return prior[0]['ref']
        implementation_ref = self.store.put_blob(Path(__file__).read_bytes(), media_type='text/x-python')
        rows = []
        inputs, visible, bodies, typed = {}, {}, {}, {}
        case = self._cases.get(case_id)
        status, reason = 'qualified', None

        def passed(check, evidence):
            rows.append({'check_id': check, 'outcome': 'PASS', 'reason': 'Exact protected invariant satisfied',
                         'evidence_refs': copy.deepcopy(evidence)})

        try:
            _require(case is not None, 'Actual finite case is not preregistered', 'finite_fixture')
            request_ref = intake['request_ref']
            request_raw = self.store.read_blob(request_ref)
            request_raw.decode('utf-8', errors='strict')
            _require(request_ref['sha256'] == case['request_sha256'], 'Original request differs from the frozen case', 'finite_fixture')
            inputs['original_request'] = request_ref
            visible[request_ref['id']] = request_ref
            passed('finite_binding', [self._binding_ref, self._binding['qualification_policy_ref'], intake_ref])

            limits = self._qualification['limits']
            actual_uploads = {}
            total_bytes = 0
            archive_members, archive_uncompressed = 0, 0
            expected_uploads = {(slot['filename'], slot['kind']) for slot in case['uploads']}
            _require(len(intake['upload_refs']) <= limits['max_uploads'], 'Too many visible uploads', 'finite_fixture')
            raw_sources = {}
            for offered in intake['upload_refs']:
                captured = self.store.read_record(offered, contract_id='client-upload')
                record = self.store.get_upload(captured['id'], run['account_id'])
                _require(record == captured and record['scope_id'] == run['workspace_id'] and record['status'] == 'uploaded',
                         'Upload is not the original live account/workspace member', 'finite_fixture')
                key = (record['filename'], record['kind'])
                _require(key in expected_uploads and key not in actual_uploads, 'Unexpected or ambiguous upload member', 'finite_fixture')
                _require(record['size_bytes'] <= limits['max_member_bytes'], 'Visible original exceeds member bound', 'finite_fixture')
                original = self.store.read_upload(record['id'], run['account_id'])
                _require(len(original) == record['size_bytes'] and hashlib.sha256(original).hexdigest() == record['content_sha256'],
                         'Original upload bytes differ from custody receipt', 'finite_fixture')
                if (record['kind'] == 'repo' or record['filename'].casefold().endswith('.zip')
                        or zipfile.is_zipfile(io.BytesIO(original))):
                    from .finite_archive import validate_opaque_zip
                    slots = [slot for slot in case['uploads'] if (slot['filename'], slot['kind']) == key]
                    _require(record['kind'] in {'repo', 'datasets'} and all(
                        slot['source'] == 'original' and slot['role'] == 'visible_support'
                        and slot['contract_id'] is None
                        and slot['artifact_ref']['sha256'] == record['content_sha256'] for slot in slots),
                        'Policy v1 supports only exact original opaque archive support', 'finite_fixture')
                    _require(total_bytes + len(original) <= limits['max_total_bytes'],
                             'Visible archive original exceeds remaining case byte bound', 'finite_fixture')
                    count, size = validate_opaque_zip(original,
                        max_members=limits['max_archive_members'] - archive_members,
                        max_member_bytes=limits['max_member_bytes'],
                        max_uncompressed_bytes=limits['max_archive_uncompressed_bytes'] - archive_uncompressed,
                        max_total_bytes=limits['max_total_bytes'] - total_bytes - len(original))
                    archive_members += count
                    archive_uncompressed += size
                    total_bytes += size
                raw_sources[(*key, 'original')] = original
                total_bytes += len(original)
                if any((slot['filename'], slot['kind'], slot['source']) == (*key, 'extracted') for slot in case['uploads']):
                    extracted = self.store.read_upload(record['id'], run['account_id'], extracted=True)
                    _require(len(extracted) <= limits['max_member_bytes'], 'Visible extraction exceeds member bound', 'finite_fixture')
                    raw_sources[(*key, 'extracted')] = extracted
                    total_bytes += len(extracted)
                _require(total_bytes <= limits['max_total_bytes'], 'Visible upload closure exceeds byte bound', 'finite_fixture')
                actual_uploads[key] = record
            _require(set(actual_uploads) == expected_uploads, 'Required visible upload member is missing', 'finite_fixture')
            passed('owned_upload_custody', intake['upload_refs'])

            for slot in case['uploads']:
                raw = raw_sources[(slot['filename'], slot['kind'], slot['source'])]
                ref = slot['artifact_ref']
                _require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'Visible slot bytes differ from approved original', 'finite_fixture')
                _require(ref['id'] not in visible or visible[ref['id']] == ref, 'Visible Ref identity collides', 'finite_fixture')
                # This immutable alias preserves uploaded payload bytes. It does
                # not register a fictitious canonical record producer.
                actual_ref = self.store.put_blob(raw, record_id=ref['id'])
                _require(actual_ref == ref, 'Visible original alias differs', 'finite_fixture')
                visible[ref['id']] = ref
                if slot['contract_id'] is not None:
                    value = self._json(raw)
                    validate(slot['contract_id'], value)
                    typed[ref['id']] = value
                if slot['role'] != 'visible_support':
                    inputs[slot['role']] = ref
            _require(len(visible) <= limits['max_visible_refs'], 'Visible Ref closure exceeds count bound', 'finite_fixture')
            for value in typed.values():
                for ref in self._refs(value):
                    _require(visible.get(ref['id']) == ref, 'A nested Ref is outside original visible upload/request closure', 'finite_fixture')
            passed('visible_ref_closure', list(visible.values()))
            passed('typed_contracts', [ref for key, ref in visible.items() if key in typed])

            brief = typed[inputs['brief']['id']]
            candidate = typed[inputs['candidate_set']['id']]
            _require(candidate['brief_ref'] == inputs['brief'], 'Candidate belongs to another Brief', 'finite_fixture')
            scope = typed[candidate['scope_ref']['id']]
            validate('search-scope', scope)
            _require(scope['brief_ref'] == inputs['brief'], 'Original Search scope belongs to another Brief', 'finite_fixture')
            from .checks.research import validate_search
            validate_search(scope, candidate, lambda ref: self.store.read_blob(visible[ref['id']]) if visible.get(ref['id']) == ref else
                            (_ for _ in ()).throw(ResearchError('finite_fixture', 'Source Ref outside allowed closure')))
            original_intake = typed[brief['intake_ref']['id']]
            intent = typed[brief['intent_ref']['id']]
            validate('qualified-intake', original_intake)
            validate('intent-ir', intent)
            _require(original_intake['request_ref'] == intent['request_ref'] == request_ref,
                     'Imported Brief/Intent/intake request provenance differs', 'finite_fixture')
            passed('source_relations', [inputs['brief'], inputs['candidate_set'], candidate['scope_ref'], brief['intake_ref'], brief['intent_ref'], request_ref])

            _require(all(brief[key] == case['module_scope'][key] for key in _SCOPE_KEYS),
                     'Original Brief promises differ from approved module scope', 'finite_fixture')
            passed('module_scope', [inputs['brief'], self._binding['qualification_policy_ref']])

            snapshot_ref = protected['library_snapshot_ref']
            _require(snapshot_ref['sha256'] == self._profile['library_snapshot_sha256']
                     and protected['verifier_cc_ref'] == self._profile['verifier_cc_ref']
                     and protected['candidate_pins'] == self._profile['candidate_pins'],
                     'Actual run library/verifier/candidate pins differ')
            snapshot = self.store.read_record(snapshot_ref, contract_id='library-snapshot')
            self.library.snapshot_budget_binding(snapshot_ref)
            for node in self._template['nodes']:
                pin = node['cc']
                entries = [value for value in snapshot['entries'] if all(value[key] == pin[key] for key in ('cc_name', 'cc_version', 'declaration_sha256'))]
                _require(len(entries) == 1, 'Finite work pin is absent from the frozen Library snapshot')
                entry = self.library.get(pin['cc_name'], pin['cc_version'])
                admission = self.store.read_record(entry['admission_ref'], contract_id='library-admission')
                _require(entry['standing'] == 'active' and admission['status'] == 'admitted' and admission['cc'] == pin
                         and entry['declaration_ref']['sha256'] == pin['declaration_sha256'], 'Finite work is not the admitted exact active version')
                association = self.library.eligible_association(entry['declaration_ref'])
                _require(association['bundle_ref']['sha256'] == entries[0]['check_pins']['check_bundle_sha256']
                         and association['profile_ref']['sha256'] == entries[0]['check_pins']['checking_profile_sha256'],
                         'Finite independent checking pins differ')
                if pin['cc_name'] == 'research.screening':
                    declaration = self.store.read_record(entry['declaration_ref'], contract_id='capsule-declaration')
                    declared = {value['path']: value['sha256'] for value in declaration['identity']['body']}
                    for filename in ('screening_rubric.json', 'screening_prompt.txt', 'ranking_parent.txt'):
                        ref = entry['body_refs'][filename]
                        _require(declared.get(filename) == ref['sha256'], 'Screening body pin differs')
                        self.store.read_blob(ref)
                        bodies[filename] = ref
                    validate('screening-rubric', self._json(self.store.read_blob(bodies['screening_rubric.json'])))
                    supplied = protected.get('host_records', {}).get('screening_rubric')
                    _require(supplied is None or supplied == bodies['screening_rubric.json'], 'Host rubric cannot replace the admitted body')
            passed('admitted_body_pins', [snapshot_ref, *bodies.values()])

            inventory_ref = protected['resource_inventory_ref']
            inventory = self.store.read_record(inventory_ref, contract_id='resource-inventory')
            resources = {value['resource_key']: value for value in inventory['resources']}
            _require(len(resources) == len(inventory['resources']), 'Ambiguous protected resource inventory')
            for key in ('original_request', 'baseline_resource', 'validation_resource'):
                if key in inputs:
                    _require(key in resources and resources[key]['available'] is True and resources[key]['ref'] == inputs[key],
                             'Protected inventory would replace a qualified input: ' + key, 'finite_fixture')
            if 'baseline_resource' in inputs:
                baseline = typed[inputs['baseline_resource']['id']]
                validation = typed[inputs['validation_resource']['id']]
                environment = resources.get('environment_lock', {}).get('ref')
                _require(environment is not None and baseline['environment_ref'] == validation['environment_ref'] == environment,
                         'Segment resources do not share the approved exact environment lock', 'finite_fixture')
                _require(visible.get(environment['id']) == environment, 'Segment environment is outside visible closure', 'finite_fixture')
                validate('environment-lock', typed[environment['id']])
            passed('resource_environment', [inventory_ref, *inputs.values()])
            passed('qualifier_implementation', self.implementation_refs())
        except (ResearchError, ValueError, UnicodeError, KeyError, TypeError) as error:
            code = error.code if isinstance(error, ResearchError) else 'finite_fixture_invalid'
            status = 'blocked' if code in {'unavailable', 'runtime_unavailable', 'schema_unavailable'} else 'rejected'
            reason = code
            failed = len(rows)
            for check in QUALIFICATION_CHECKS[failed:]:
                rows.append({'check_id': check, 'outcome': 'ENVIRONMENT_BLOCKED' if status == 'blocked' else 'FAIL',
                    'reason': code if check == QUALIFICATION_CHECKS[failed] else 'Not run after required qualification failure',
                    'evidence_refs': [implementation_ref, intake_ref]})
        _require([row['check_id'] for row in rows] == list(QUALIFICATION_CHECKS), 'Qualifier omitted a mandatory check')
        result = {'schema': 'ai4r-finite-e1-fixture-qualification:1', 'id': identity, 'run_id': run_id,
            'binding_ref': self._binding_ref, 'intake_ref': intake_ref, 'case_id': case_id,
            'upload_refs': intake['upload_refs'], 'input_refs': inputs, 'visible_refs': list(visible.values()),
            'body_refs': bodies, 'results': rows, 'status': status, 'reason': reason, 'invalid_for_product': True}
        ref = self.store.append_record('finite-e1-fixture-qualification', result)
        self.store.mark_evaluation_material(run_id, ref)
        return ref

    def _qualified(self, run_id, protected, qualification_ref=None):
        run, intake, case_id = self._run(run_id, protected)
        _require(run['state'] in {'pending', 'running'} and not self.store.cancellation_requested(run_id),
                 'Stopped finite run cannot prepare new work', 'cancelled')
        matches = list(self.store.iter_records(run_id=run_id, kinds=('finite-e1-fixture-qualification',)))
        _require(len(matches) == 1 and (qualification_ref is None or matches[0]['ref'] == qualification_ref),
                 'Finite work has no unique original qualification')
        envelope = matches[0]
        result = envelope['record']
        _closed(result, {'schema', 'id', 'run_id', 'binding_ref', 'intake_ref', 'case_id', 'upload_refs',
                         'input_refs', 'visible_refs', 'body_refs', 'results', 'status', 'reason', 'invalid_for_product'})
        _require(result['schema'] == 'ai4r-finite-e1-fixture-qualification:1'
                 and result['run_id'] == run_id and result['binding_ref'] == self._binding_ref
                 and result['intake_ref'] == run['submission']['intake_ref'] and result['case_id'] == case_id
                 and result['upload_refs'] == intake['upload_refs'] and result['invalid_for_product'] is True
                 and result['status'] == 'qualified' and result['reason'] is None,
                 'Finite qualification is not the actual qualified run/input record', 'finite_fixture')
        checks = result['results']
        _require([row['check_id'] for row in checks] == list(QUALIFICATION_CHECKS)
                 and all(row['outcome'] == 'PASS' for row in checks)
                 and checks[-1]['evidence_refs'] == self.implementation_refs(),
                 'Finite qualification/checker implementation is missing, stale or incomplete', 'finite_fixture')
        _require(protected['library_snapshot_ref'] in checks[6]['evidence_refs']
                 and protected['resource_inventory_ref'] in checks[7]['evidence_refs'],
                 'Current Library/inventory differs from original qualification', 'finite_fixture')
        case = self._cases[case_id]
        seen = set()
        for offered in intake['upload_refs']:
            original = self.store.read_record(offered, contract_id='client-upload')
            current = self.store.get_upload(original['id'], run['account_id'])
            _require(current == original and current['status'] == 'uploaded'
                     and current['scope_id'] == run['workspace_id'],
                     'Original finite input upload is no longer live and owned', 'finite_fixture')
            for slot in case['uploads']:
                if (slot['filename'], slot['kind']) != (current['filename'], current['kind']):
                    continue
                raw = self.store.read_upload(current['id'], run['account_id'], extracted=slot['source'] == 'extracted')
                _require(hashlib.sha256(raw).hexdigest() == slot['artifact_ref']['sha256'],
                         'Original finite upload bytes changed after qualification', 'finite_fixture')
                seen.add((slot['filename'], slot['kind'], slot['source']))
        _require(seen == {(slot['filename'], slot['kind'], slot['source']) for slot in case['uploads']},
                 'Original finite upload membership changed', 'finite_fixture')
        for ref in result['visible_refs']:
            self.store.read_blob(ref)
        return envelope

    def plan_context(self, run_id, protected):
        qualified = self._qualified(run_id, protected)
        keys = ('finite_e1_binding_ref', 'configuration_ref', 'profile_id', 'library_snapshot_ref', 'resource_inventory_ref',
                'verifier_cc_ref', 'candidate_pins', 'profile_ref', 'workspace_ref', 'input_directory_ref')
        pins = {key: copy.deepcopy(protected[key]) for key in keys}
        return _FinitePlanContext(self, self._context_token, run_id, qualified['ref'], pins)

    def validate_context(self, context):
        _require(type(context) is _FinitePlanContext and context.owner is self
                 and context.token is self._context_token, 'Unknown or forged finite plan context')
        return self._qualified(context.run_id, context.protected, context.qualification_ref)

    def validate_plan_inputs(self, context, *, source_ref, brief_ref, snapshot_ref, resources_ref,
                             policy_ref, configuration_ref, plan_source):
        result = self.validate_context(context)['record']
        _require(plan_source == 'static' and source_ref == self._binding['template_ref']
                 and brief_ref == result['input_refs']['brief']
                 and snapshot_ref == context.protected['library_snapshot_ref']
                 and resources_ref == context.protected['resource_inventory_ref']
                 and policy_ref == self._binding['policy_ref'] and configuration_ref == self._configuration_ref,
                 'Finite plan is outside its exact qualified source/pins', 'finite_fixture')
        return result

    def prior_plan(self, context):
        self.validate_context(context)
        rows = list(self.store.iter_records(run_id=context.run_id, kinds=('finite-e1-plan-binding',)))
        if not rows:
            return None
        _require(len(rows) == 1 and rows[0]['record']['binding_ref'] == self._binding_ref
                 and rows[0]['record']['qualification_ref'] == context.qualification_ref,
                 'Frozen finite plan cannot be replaced')
        return rows[0]['record']['plan_ref']

    def _freeze_key(self, context):
        return 'finite-plan-once:' + hashlib.sha256(json_bytes([
            context.run_id, self._binding_ref, context.qualification_ref])).hexdigest()

    def claim_plan(self, context):
        self.validate_context(context)
        key = self._freeze_key(context)
        prior = None
        with self.store.transaction() as db:
            row = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            if row:
                value = json.loads(row['value'])
                _require(type(value) is dict and value.get('qualification_ref') == context.qualification_ref
                         and value.get('binding_ref') == self._binding_ref,
                         'Finite freeze claim belongs to another protected scope')
                _require(value.get('state') == 'frozen',
                         'Finite freeze already started; reconcile without replay', 'finite_freeze_unknown')
                prior = value['plan_ref']
            else:
                value = {'state': 'claimed', 'binding_ref': self._binding_ref, 'qualification_ref': context.qualification_ref}
                db.execute('INSERT INTO metadata(key,value) VALUES(?,?)', (key, json_bytes(value).decode()))
        if prior is not None:
            _require(self.prior_plan(context) == prior, 'Frozen finite claim lacks the exact original binding')
        return prior

    def publish_plan(self, context, plan):
        """Publish the Binder's genuine plan, private join and taint atomically."""
        self.validate_context(context)
        _require(self.prior_plan(context) is None, 'Finite plan is already frozen')
        validate('run-plan', plan)
        self.validate_plan_inputs(context, source_ref=plan['source_ref'], brief_ref=plan['brief_ref'],
            snapshot_ref=plan['library_snapshot_ref'], resources_ref=plan['resource_inventory_ref'],
            policy_ref=plan['policy_ref'], configuration_ref=plan['configuration_ref'], plan_source=plan['plan_source'])
        plan_raw = json_bytes(plan)
        plan_ref = {'id': plan['id'], 'sha256': self.store.blobs.put(plan_raw)}
        identity = 'finite-plan-binding:' + hashlib.sha256(json_bytes([
            context.run_id, self._binding_ref, context.qualification_ref])).hexdigest()
        value = {'schema': 'ai4r-finite-e1-plan-binding:1', 'id': identity, 'run_id': context.run_id,
            'binding_ref': self._binding_ref, 'qualification_ref': context.qualification_ref, 'plan_ref': plan_ref,
            'implementation_refs': self.implementation_refs(), 'invalid_for_product': True}
        raw = json_bytes(value)
        binding_ref = {'id': identity, 'sha256': self.store.blobs.put(raw)}
        captures = [('run-plan', plan_ref, plan_raw, None), ('finite-e1-plan-binding', binding_ref, raw, context.run_id)]
        evaluation = self.store.evaluation_binding(context.run_id)
        _require(evaluation is not None and evaluation['record']['invalid_for_product'] is True,
                 'Finite publication lost its original evaluation ownership')
        for artifact_ref in (plan_ref, binding_ref):
            origin = {'id': 'evaluation-material:' + hashlib.sha256(json_bytes([context.run_id, artifact_ref])).hexdigest(),
                'run_id': context.run_id, 'artifact_ref': artifact_ref, 'binding_ref': evaluation['ref'], 'invalid_for_product': True}
            original = json_bytes(origin)
            captures.append(('evaluation-material', {'id': origin['id'], 'sha256': self.store.blobs.put(original)}, original, context.run_id))
        stamp = utc_now()
        with self.store.transaction() as db:
            row = db.execute('SELECT value FROM metadata WHERE key=?', (self._freeze_key(context),)).fetchone()
            claimed = json.loads(row['value']) if row else None
            _require(claimed == {'state': 'claimed', 'binding_ref': self._binding_ref, 'qualification_ref': context.qualification_ref},
                     'Finite publication has no exact durable once-claim', 'finite_freeze_unknown')
            for kind, ref, captured, run_id in captures:
                existing = db.execute('SELECT sha256 FROM artifacts WHERE id=?', (ref['id'],)).fetchone()
                _require(existing is None or existing['sha256'] == ref['sha256'], 'Immutable finite publication identity collides')
                indexed = db.execute('SELECT kind FROM records WHERE id=?', (ref['id'],)).fetchone()
                _require(indexed is None or indexed['kind'] == kind, 'Finite publication has another producer kind')
                db.execute('INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?)', (ref['id'], ref['sha256'], 'application/json', None, stamp))
                db.execute('INSERT OR IGNORE INTO records VALUES(?,?,?,?,?,?)', (ref['id'], kind, run_id, None, None, stamp))
            frozen = {'state': 'frozen', 'binding_ref': self._binding_ref, 'qualification_ref': context.qualification_ref,
                      'plan_ref': plan_ref, 'plan_binding_ref': binding_ref}
            db.execute('UPDATE metadata SET value=? WHERE key=?', (json_bytes(frozen).decode(), self._freeze_key(context)))
        return plan_ref

    def validate_dispatch(self, run_id, plan, protected):
        self._run(run_id, protected)
        context = self.context_for_plan(plan)
        _require(context.run_id == run_id, 'Finite plan belongs to another run')
        qualified = self.validate_context(context)
        _require(context.protected == self.plan_context(run_id, protected).protected,
                 'Finite dispatch differs from its exact qualified pins')
        return qualified

    def _execution_key(self, run_id):
        return 'finite-execute-once:' + hashlib.sha256(json_bytes([run_id, self._binding_ref])).hexdigest()

    async def execute(self, run_id, protected, *, scheduler):
        """Qualify and freeze once, then use the ordinary native execution path."""
        from .scheduler import Scheduler
        _require(type(scheduler) is Scheduler and scheduler.store is self.store
                 and scheduler.library is self.library and scheduler.binder.finite_e1 is self,
                 'Finite execution needs the actual bound Scheduler/Library owner', 'unavailable')
        run, _, _ = self._run(run_id, protected)
        keys = ('configuration_ref', 'model_selection_profile_ref', 'deployment_ref', 'router', 'run_limits',
                'authority_ceiling', 'host_records', 'resource_inventory_ref', 'library_snapshot_ref')
        _require(all(key in protected for key in keys), 'Finite protected runtime binding is incomplete', 'unavailable')
        _require(protected['router'] == self._operator['cc']['router']
                 and protected['run_limits'] == self._policy['aggregate_limits'],
                 'Finite runtime route or aggregate limits differ from approved policy')
        for key in ('model_selection_profile_ref', 'deployment_ref'):
            self.store.read_blob(protected[key])
        digest = hashlib.sha256(json_bytes({key: protected[key] for key in keys})).hexdigest()
        key = self._execution_key(run_id)
        with self.store._lock:
            row = self.store.connection.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        if row:
            value = json.loads(row['value'])
            _require(type(value) is dict and value.get('binding_ref') == self._binding_ref
                     and value.get('context_sha256') == digest, 'Finite execution has another runtime scope')
            _require(value.get('state') == 'completed',
                     'Finite execution was already issued; reconcile original evidence without replay', 'finite_execution_unknown')
            result = value.get('result')
            _require(type(result) is dict and set(result) == {'status', 'plan_ref', 'node_states'}
                     and result['status'] == run['state'] and result['status'] in {'completed', 'partial'}
                     and self.store.read_record(result['plan_ref'], contract_id='run-plan')['configuration_ref'] == self._configuration_ref,
                     'Terminal finite receipt does not join the original run/plan')
            original = self.prior_plan_for_history(run_id)
            _require(original == result['plan_ref'] and value.get('plan_ref') == original,
                     'Terminal finite receipt names another frozen plan')
            return copy.deepcopy(result)
        qualification_ref = self.qualify(run_id, protected)
        qualification = self.store.read_record(qualification_ref)
        if qualification['status'] != 'qualified':
            self.store.set_run_state(run_id, 'halted', reason=qualification['reason'])
            return {'status': 'halted', 'qualification_ref': qualification_ref, 'reason': qualification['reason']}
        context = self.plan_context(run_id, protected)
        inputs = context.input_refs()
        plan_ref = scheduler.binder.freeze(self._binding['template_ref'], inputs['brief'],
            protected['library_snapshot_ref'], protected['resource_inventory_ref'], self._binding['policy_ref'],
            self._configuration_ref, plan_source='static', finite_context=context)
        scheduler.runner.configure_run(run_id,
            **{name: protected[name] for name in ('model_selection_profile_ref', 'deployment_ref', 'router', 'configuration_ref', 'run_limits')},
            routing_context=protected.get('routing_context'))
        issued = {'state': 'issued', 'binding_ref': self._binding_ref, 'context_sha256': digest,
                  'qualification_ref': qualification_ref, 'plan_ref': plan_ref}
        with self.store.transaction() as db:
            _require(db.execute('SELECT 1 FROM metadata WHERE key=?', (key,)).fetchone() is None,
                     'Finite execution already started; do not replay', 'finite_execution_unknown')
            db.execute('INSERT INTO metadata(key,value) VALUES(?,?)', (key, json_bytes(issued).decode()))
        result = await scheduler.execute_plan(run_id, plan_ref, protected)
        with self.store.transaction() as db:
            current = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
            _require(current is not None and json.loads(current['value']) == issued,
                     'Finite execution once-claim changed during actual work', 'finite_execution_unknown')
            terminal = dict(issued, state='completed', result=result)
            db.execute('UPDATE metadata SET value=? WHERE key=?', (json_bytes(terminal).decode(), key))
        return result

    def prior_plan_for_history(self, run_id):
        """Read original terminal linkage without granting a new work capability."""
        rows = list(self.store.iter_records(run_id=run_id, kinds=('finite-e1-plan-binding',)))
        _require(len(rows) == 1 and rows[0]['record']['binding_ref'] == self._binding_ref,
                 'Finite history lacks its exact original plan binding')
        value = rows[0]['record']
        self.store.read_blob(value['qualification_ref'])
        self.store.read_blob(value['plan_ref'])
        return value['plan_ref']

    def context_for_plan(self, plan):
        plan_ref = {'id': plan['id'], 'sha256': hashlib.sha256(json_bytes(plan)).hexdigest()}
        _require(self.store.read_record(plan_ref, contract_id='run-plan') == plan, 'Finite plan bytes are not captured')
        rows = [row for row in self.store.iter_records(kinds=('finite-e1-plan-binding',))
                if row['record'].get('plan_ref') == plan_ref]
        _require(len(rows) == 1, 'Finite plan has no unique protected run/qualification binding')
        value = rows[0]['record']
        _closed(value, {'schema', 'id', 'run_id', 'binding_ref', 'qualification_ref', 'plan_ref', 'implementation_refs', 'invalid_for_product'})
        _require(value['schema'] == 'ai4r-finite-e1-plan-binding:1' and value['binding_ref'] == self._binding_ref
                 and value['invalid_for_product'] is True and value['implementation_refs'] == self.implementation_refs(),
                 'Finite plan binding is foreign or stale')
        run = self.store.get_run(value['run_id'])
        intake = self.store.read_record(run['submission']['intake_ref'], contract_id='qualified-intake')
        protected = {'finite_e1_binding_ref': self._binding_ref, 'configuration_ref': plan['configuration_ref'],
            'profile_id': self._profile['profile_id'], 'library_snapshot_ref': plan['library_snapshot_ref'],
            'resource_inventory_ref': plan['resource_inventory_ref'], 'verifier_cc_ref': self._profile['verifier_cc_ref'],
            'candidate_pins': self._profile['candidate_pins'],
            **{key: intake[key] for key in ('profile_ref', 'workspace_ref', 'input_directory_ref')}}
        return _FinitePlanContext(self, self._context_token, value['run_id'], value['qualification_ref'], protected)


def finite_evidence_refs(store, run_id):
    """Validate original owned joins for inspection; never grant work or recurse policy."""
    rows = list(store.iter_records(run_id=run_id, kinds=('finite-e1-fixture-qualification',)))
    plans = list(store.iter_records(run_id=run_id, kinds=('finite-e1-plan-binding',)))
    if not rows:
        _require(not plans, 'Finite plan evidence lost its original qualification', 'finite_evidence')
        return None
    _require(len(rows) == 1 and len(plans) <= 1, 'Ambiguous finite original evidence', 'finite_evidence')
    envelope = rows[0]
    result = envelope['record']
    _closed(result, {'schema', 'id', 'run_id', 'binding_ref', 'intake_ref', 'case_id', 'upload_refs',
                     'input_refs', 'visible_refs', 'body_refs', 'results', 'status', 'reason', 'invalid_for_product'})
    run = store.get_run(run_id)
    submission = run['submission']
    evaluation = store.evaluation_binding(run_id)
    _require(result['schema'] == 'ai4r-finite-e1-fixture-qualification:1' and result['run_id'] == run_id
             and result['intake_ref'] == submission['intake_ref'] and result['invalid_for_product'] is True
             and evaluation is not None, 'Finite evidence has another original run', 'finite_evidence')
    actual = evaluation['record']
    _require(actual['run_id'] == run_id and actual['account_id'] == run['account_id']
             and actual['workspace_id'] == run['workspace_id'] and actual['invalid_for_product'] is True
             and actual['configuration_ref'] == submission['configuration_ref']
             and actual['submission_sha256'] == hashlib.sha256(json_bytes(submission)).hexdigest(),
             'Finite evidence belongs to another account/workspace/submission', 'finite_evidence')
    def original(ref, kind=None, contract=None):
        validate('Ref', ref)
        if kind is not None:
            _require(store.record_kind(ref) == kind, 'Finite evidence has another producer kind', 'finite_evidence')
        return store.read_record(ref, contract_id=contract) if kind or contract else store.read_blob(ref)
    binding = original(result['binding_ref'], 'finite-e1-binding')
    _closed(binding, _BINDING_KEYS)
    _require(binding['schema'] == 'ai4r-finite-e1-binding:1' and binding['configuration_ref'] == submission['configuration_ref']
             and binding['profile_ref'] == actual['profile_ref'], 'Finite evidence binding differs', 'finite_evidence')
    policy = original(binding['qualification_policy_ref'], 'finite-e1-qualification-policy')
    _require(policy['schema'] == 'ai4r-finite-e1-qualification-policy:1' and policy['profile_ref'] == binding['profile_ref']
             and policy['template_ref'] == binding['template_ref'] and policy['plan_policy_ref'] == binding['policy_ref'],
             'Finite evidence qualification policy differs', 'finite_evidence')
    cases = [case for case in policy['cases'] if case['case_id'] == result['case_id']]
    _require(len(cases) == 1 and result['case_id'] == submission['evaluation']['run_id'],
             'Finite original case correlation differs', 'finite_evidence')
    intake = original(result['intake_ref'], 'qualified-intake', 'qualified-intake')
    _require(intake['user_id'] == run['account_id'] and intake['upload_refs'] == result['upload_refs'],
             'Finite original intake/upload ownership differs', 'finite_evidence')
    _require(result['status'] != 'qualified'
             or intake['request_ref']['sha256'] == cases[0]['request_sha256'],
             'Finite qualified request differs from the frozen case', 'finite_evidence')
    allowed = {(ref['id'], ref['sha256']) for ref in [intake['request_ref'], *[slot['artifact_ref'] for slot in cases[0]['uploads']]]}
    _require(all((ref['id'], ref['sha256']) in allowed for ref in [*result['visible_refs'], *result['input_refs'].values()]),
             'Finite evidence would disclose an unrelated input', 'finite_evidence')
    for ref in result['upload_refs']:
        upload = original(ref, 'client-upload', 'client-upload')
        _require(upload['user_id'] == run['account_id'] and upload['scope_id'] == run['workspace_id'],
                 'Finite evidence upload belongs to another owner', 'finite_evidence')
    checks = result['results']
    _require([row['check_id'] for row in checks] == list(QUALIFICATION_CHECKS)
             and result['status'] in {'qualified', 'rejected', 'blocked'}
             and (result['status'] != 'qualified' or result['reason'] is None and all(row['outcome'] == 'PASS' for row in checks)),
             'Finite original qualification is incomplete', 'finite_evidence')
    refs = [envelope['ref'], result['binding_ref'], result['intake_ref'], intake['request_ref'],
            *result['upload_refs'], *result['visible_refs'], *result['input_refs'].values()]
    for row in checks:
        refs.extend(ref for ref in row['evidence_refs'] if ref in result['visible_refs'])
    # Keep exact installed qualifier/checker source proof, not the whole case policy.
    refs.extend(checks[-1]['evidence_refs'] if result['status'] == 'qualified' else [])
    stages = policy['stages']
    if plans:
        value = plans[0]['record']
        _closed(value, {'schema', 'id', 'run_id', 'binding_ref', 'qualification_ref', 'plan_ref', 'implementation_refs', 'invalid_for_product'})
        _require(value['schema'] == 'ai4r-finite-e1-plan-binding:1' and value['run_id'] == run_id
                 and value['binding_ref'] == result['binding_ref'] and value['qualification_ref'] == envelope['ref']
                 and value['invalid_for_product'] is True and result['status'] == 'qualified',
                 'Finite plan evidence has another original qualification', 'finite_evidence')
        plan = original(value['plan_ref'], 'run-plan', 'run-plan')
        _require(plan['configuration_ref'] == binding['configuration_ref'] and plan['source_ref'] == binding['template_ref']
                 and plan['policy_ref'] == binding['policy_ref'] and plan['brief_ref'] == result['input_refs']['brief']
                 and plan['library_snapshot_ref'] == actual['library_snapshot_ref']
                 and [node['cc']['cc_name'] for node in plan['nodes']] == stages,
                 'Finite original plan pins/stages differ', 'finite_evidence')
        proof = original(plan['acceptance_ref'], 'deterministic-check-result', 'deterministic-check-result')
        _require([row['check_id'] for row in proof['results']] == list(FINITE_PLAN_CHECKS)
                 and all(row['outcome'] == 'PASS' for row in proof['results']),
                 'Finite original plan proof is incomplete', 'finite_evidence')
        check_plan = original(proof['check_plan_ref'], 'bound-check-plan', 'bound-check-plan')
        refs.extend([plans[0]['ref'], value['plan_ref'], plan['acceptance_ref'], proof['check_plan_ref'],
                     binding['template_ref'], binding['policy_ref'], *value['implementation_refs'], *check_plan['runner_refs']])
    unique = list({(ref['id'], ref['sha256']): ref for ref in refs}.values())
    for ref in unique:
        store.read_blob(ref)
    return {'artifact_refs': unique, 'stages': stages, 'qualification_ref': envelope['ref'],
            'plan_binding_ref': plans[0]['ref'] if plans else None}


@dataclass(frozen=True)
class _FinitePlanContext:
    owner: FiniteE1
    token: object
    run_id: str
    qualification_ref: dict
    protected: dict

    def input_refs(self):
        return copy.deepcopy(self.owner.validate_context(self)['record']['input_refs'])

    def validate_payloads(self, source, brief, snapshot, resources, policy):
        qualified = self.owner.validate_context(self)['record']
        _require(source == self.owner._template and policy == self.owner._policy
                 and brief == self.owner.store.read_record(qualified['input_refs']['brief'], contract_id='research-brief')
                 and snapshot == self.owner.store.read_record(self.protected['library_snapshot_ref'], contract_id='library-snapshot')
                 and resources == self.owner.store.read_record(self.protected['resource_inventory_ref'], contract_id='resource-inventory'),
                 'Finite plan payload differs from exact protected bytes')

    def terminal_result(self, bound, brief):
        self.owner.validate_context(self)
        nodes = bound['nodes']
        names = [node['cc']['cc_name'] for node in nodes]
        referenced = {key for node in nodes for key in node['predecessors']}
        leaves = [node for node in nodes if node['node_id'] not in referenced]
        ok = (names == self.owner._qualification['stages'] and len(leaves) == 1
              and leaves[0]['node_id'] == nodes[-1]['node_id']
              and [port['name'] for port in leaves[0]['outputs']] == self.owner._qualification['terminal_ports']
              and {item['id'] for item in brief['deliverables']} <= set(leaves[0]['deliverable_ids']))
        coverage = {(item.get('item_kind'), item.get('item_id')): set(item['node_ids']) for item in bound['coverage']}
        for obligation in brief['evidence_obligations']:
            expected = set().union(*(coverage.get(('requirement', key), set()) for key in obligation['requirement_ids']))
            ok = ok and bool(expected) and coverage.get(('evidence_obligation', obligation['id'])) == expected
        if len(nodes) == 2:
            port = next((item for item in nodes[1]['inputs'] if item['name'] == 'opportunity'), None)
            ok = (ok and nodes[1]['predecessors'] == [nodes[0]['node_id']] and port is not None
                  and port['source_kind'] == 'future_output' and port['future']['producer_node'] == nodes[0]['node_id']
                  and port['future']['port'] == 'opportunity_card')
        return {'check_id': 'finite_delivery_leaf_coverage_v1', 'outcome': 'PASS' if ok else 'FAIL',
            'reason': 'Exact approved finite stages, terminal outputs and complete module coverage' if ok else 'Finite stage/terminal/module coverage differs',
            'evidence_refs': [self.owner.binding_ref, self.qualification_ref]}
