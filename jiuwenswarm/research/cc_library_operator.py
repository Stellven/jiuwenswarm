"""Exact CC body-to-Library joins inside the permanently unprivileged child.

Preflight captures public inbox bytes and custody evidence only. Admission and
standing still run exclusively through OperatorLibrary and LibraryService.
"""
from __future__ import annotations

import hashlib
import json
import re

from .contracts import validate
from .library_operator import require
from .state import json_bytes


class CcLibraryAction:
    def __init__(self, owner):
        self.owner = owner

    def preflight(self, command, request_ref, digest, node_id):
        require(command in {'admit-rsi', 'standing'}, 'Only finite CC Library actions are supported')
        require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'Exact reviewed body hash required')
        owner = self.owner
        owner.actor.require('library_admit' if command == 'admit-rsi' else 'library_standing')
        validate('Ref', request_ref)
        request = owner.store.read_record(request_ref)
        require(isinstance(request, dict) and set(request) == owner.FIELDS[command] | {'schema', 'id'}
                and request['schema'] == 'ai4r-library-action:1'
                and isinstance(request['id'], str) and request['id'], 'Closed CC Library action required')
        configuration = owner.store.read_record(owner.bindings['configuration_ref'])
        require(configuration.get('operator', configuration) == owner.operator.snapshot(), 'Captured operator configuration changed')
        library = owner.library
        if command == 'admit-rsi':
            require(isinstance(request['package_path'], str), 'Protected inbox package path required')
            package_ref = library.capture_rsi_inbox(request['package_path'], owner.actor)
            package = owner.store.read_record(package_ref, contract_id='candidate-package')
        else:
            # This surface supports explicit sandbox activation only. Authored
            # future-plan promotion remains a separate finite operator action.
            require(request['to_standing'] == 'active' and request['effect_scope'] == 'rsi_sandbox'
                    and isinstance(request['reason'], str) and request['reason'].strip(), 'Explicit sandbox activation required')
            row = library.get(request['name'], request['version'])
            admission = owner.store.read_record(row['admission_ref'], contract_id='library-admission')
            require(admission['status'] == 'admitted' and admission['parent_ref'] is not None
                    and row['standing'] in {'inactive', 'suspended'}, 'An admitted inactive or suspended RSI child is required')
            authorization_ref = library._rsi_security_authorization(row['declaration_ref'], 'activate')
            authorization = owner.store.read_record(authorization_ref)
            package_ref = authorization['package_ref']
            package = owner.store.read_record(package_ref, contract_id='candidate-package')
            require(package['child_declaration_ref'] == row['declaration_ref'], 'Standing target differs from signed child')
        library._require_rsi_security('admit' if command == 'admit-rsi' else 'activate',
                                      package['session_ref'], package['child_declaration_ref'])
        parent = library.get(package['parent']['cc_name'], package['parent']['cc_version'])
        parent_admission = owner.store.read_record(parent['admission_ref'], contract_id='library-admission')
        require(parent['declaration_ref'] == package['parent_declaration_ref']
                and parent_admission['status'] == 'admitted', 'Exact admitted parent required')
        protected = set()
        for row in library.entries():
            declaration = owner.store.read_record(json.loads(row['declaration_ref']), contract_id='capsule-declaration')
            if declaration['evolution']['rsi'] == 'none':
                protected.update(body['sha256'] for body in declaration['identity']['body'])
        from .contracts.rsi import verify_package
        require(library._rsi_public_key is not None and library._rsi_key_id is not None, 'Pinned custodian verification key required')
        verified = verify_package(package, owner.store, public_key=library._rsi_public_key,
                                  key_id=library._rsi_key_id, protected_body_hashes=protected)
        require(verified['referee']['child_ref']['sha256'] == digest, 'Reviewed body differs from signed assessed finalist')
        require(node_id == 'candidate:' + verified['result']['final_attempt_ref']['sha256'],
                'Reviewed node differs from signed selected attempt')
        inherited = library.eligible_association(package['parent_declaration_ref'])
        library._validate_association(package['child_declaration_ref'], inherited['bundle_ref'], inherited['profile_ref'])
        from .contracts import ResearchError
        try:
            association = library.association(package['child_declaration_ref'])
        except ResearchError as error:
            if error.code != 'check_association_missing': raise
        else:
            require(all(association[key] == inherited[key] for key in ('bundle_ref', 'profile_ref')),
                    'Child checking pins differ from its exact parent')
        if command == 'admit-rsi':
            child = verified['child']
            by_hash = {ref['sha256']: ref for ref in verified['provenance']['implementation_refs']}
            bodies = {item['path']: by_hash[item['sha256']] for item in child['identity']['body']}
            for dependency in child['needs']['external']:
                for key in ('pin', 'lockfile'):
                    pin = dependency.get(key)
                    if pin:
                        inherited_ref = parent['body_refs'].get(pin['ref'])
                        require(inherited_ref is not None and inherited_ref['sha256'] == pin['sha256'],
                                'Exact inherited external dependency required')
                        owner.store.read_blob(inherited_ref); bodies[pin['ref']] = inherited_ref
            self._preflight_self_tests(package['child_declaration_ref'], child, bodies)
        owner.store.require_product_material([package['child_declaration_ref'], *verified['provenance']['implementation_refs']])
        return package, package_ref

    def _preflight_self_tests(self, declaration_ref, declaration, body_refs):
        tests = declaration['guarantees'].get('self_tests', [])
        if not tests: return
        owner = self.owner
        if owner.self_tests is not None:
            require(callable(owner.self_tests), 'Installed self-test runner required')
            return
        from .admission_executor import AdmissionTestProvider, ref_record
        provider = owner.library.self_test_provider
        require(isinstance(provider, AdmissionTestProvider), 'Required confined self-test provider is unavailable')
        require(provider.store is owner.store and provider.configuration_ref == owner.bindings['configuration_ref']
                and provider.profile_ref == owner.bindings.get('protected_options', {}).get('admission_execution_profile_ref'),
                'Self-test provider differs from protected configuration/profile pins')
        require(ref_record(owner.store, provider.profile_ref, 'admission-execution-profile') == provider.profile,
                'Captured self-test execution profile changed')
        require(callable(getattr(provider.rpc, 'run_admission_self_test', None)), 'Required self-test executor IPC is unavailable')
        # Existing subject checks validate exact carrier, body/test/dependency
        # closure and supported unprivileged adapter without issuing any job.
        for test in tests: provider._subject(test['id'], declaration_ref, body_refs)

    async def execute(self, command, request_ref, digest, node_id, *, preflight_only=False):
        package, package_ref = self.preflight(command, request_ref, digest, node_id)
        if preflight_only:
            return {'status': 'eligible', 'request_ref': request_ref, 'candidate_hash': digest}
        owner = self.owner
        result = await owner.execute(command, request_ref, expected_rsi_package_ref=package_ref if command == 'admit-rsi' else None)
        require(result['request_ref'] == request_ref and result['command'] == command, 'Library terminal identity differs')
        row = owner.library.get(package['child']['cc_name'], package['child']['cc_version'])
        require(row['declaration_ref'] == package['child_declaration_ref'], 'Library terminal child differs')
        admission = owner.store.read_record(row['admission_ref'], contract_id='library-admission')
        require(admission['status'] == 'admitted', 'Library admission did not succeed')
        if command == 'admit-rsi':
            require(result['status'] == 'admitted' and result['admission_ref'] == row['admission_ref']
                    and row['standing'] == 'inactive', 'Library did not admit this exact child inactive')
            status = 'admitted_inactive'
        else:
            standing = owner.store.read_record(result['standing_ref'], contract_id='activation-record')
            require(result['status'] == 'completed' and standing['admission_ref'] == row['admission_ref']
                    and standing['to_standing'] == row['standing'] == 'active'
                    and standing['effect_scope'] == row['effect_scope'] == 'rsi_sandbox', 'Exact sandbox activation receipt required')
            status = 'activated'
        # Return the actual immutable operator receipt, never a synthesized
        # success based on a subprocess exit status or a current standing alone.
        key = 'library-operator:' + hashlib.sha256(json_bytes([owner.actor.account_id, command,
            owner.store.read_record(request_ref)['id']])).hexdigest()
        captured = owner.store.connection.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        receipt_ref = json.loads(captured['value'])['receipt_ref']
        require(owner.store.read_record(receipt_ref) == result, 'Stored operator receipt differs')
        return {'status': status, 'request_ref': request_ref, 'candidate_hash': digest, 'operator_receipt_ref': receipt_ref}
