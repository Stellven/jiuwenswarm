"""Independent calibration producer; catalog preparation grants no eligibility.

The private profile pins cases and exact expected outcome maps before effects.
It adds no public contract fields, default labels or numerical pass threshold.
Only an installed, byte-pinned protected measurement adapter can run cases.
Candidate bytes and arbitrary PASS-shaped records have no admission authority.
"""

from __future__ import annotations

import inspect
import json
import uuid
import copy

from ..contracts import ResearchError, validate
from ..state import json_bytes, utc_now


CHALLENGES = frozenset({'instruction_injection', 'omissions', 'unsupported_claims', 'ambiguity', 'scope_escape'})
OUTCOMES = frozenset({'PASS', 'FAIL', 'ENVIRONMENT_BLOCKED', 'INCONCLUSIVE'})
EVIDENCE_REVIEW_MODE = 'task_sources_tier1_v1'
EVIDENCE_REVIEW_PROFILE_VERSION = '2.0.0'
MAX_REVIEW_EVIDENCE_BYTES = 131072


def prepare_evidence_aware_release(store, asset, *, version_label, evidence_criterion_ids,
                                   evidence_input_names, reviewer_instructions,
                                   max_evidence_bytes=65536):
    """Create a new immutable CC/checking release with bounded source-aware review.

    The original refs and profile remain untouched. The returned asset has a
    distinct declaration identity and exact v2 bundle/profile pins so callers
    can admit it only in an explicitly prepared pilot catalog.
    """
    def require(condition, message):
        if not condition:
            raise ResearchError('evidence_review_profile', message)
    require(isinstance(asset, dict) and all(key in asset for key in
        ('declaration_ref', 'bundle_ref', 'profile_ref')), 'A complete admitted source asset is required')
    require(isinstance(version_label, str) and version_label and len(version_label) <= 64,
            'A distinct target CC release label is required')
    require(isinstance(reviewer_instructions, str) and reviewer_instructions.strip(),
            'The new release needs complete fixed reviewer instructions')
    require(1 <= max_evidence_bytes <= MAX_REVIEW_EVIDENCE_BYTES,
            'Evidence disclosure limit exceeds the fixed host ceiling')
    declaration = copy.deepcopy(store.read_record(asset['declaration_ref'], contract_id='capsule-declaration'))
    prior_label = declaration['identity']['version_label']
    require(version_label != prior_label, 'Evidence-aware review must use a new immutable CC identity')
    bundle = copy.deepcopy(store.read_record(asset['bundle_ref'], contract_id='check-bundle'))
    profile = copy.deepcopy(store.read_record(asset['profile_ref'], contract_id='checking-profile'))
    known = {row['criterion_id'] for row in profile['criteria']}
    require(isinstance(evidence_criterion_ids, (list, tuple)) and
            isinstance(evidence_input_names, (list, tuple)), 'Evidence criteria and input ports must be explicit lists')
    selected = list(evidence_criterion_ids)
    input_names = list(evidence_input_names)
    require(selected and len(selected) == len(set(selected)) and set(selected) <= known,
            'Evidence criteria must be unique members of the exact existing profile')
    require(input_names and len(input_names) == len(set(input_names)) and
            all(isinstance(name, str) and name for name in input_names),
            'Evidence input ports must be a nonempty unique list')
    forbidden = ('gold', 'expected', 'answer_key', 'reference_answer', 'solution', 'private', 'worker', 'conversation')
    require(not any(any(word in name.lower() for word in forbidden) for name in input_names),
            'Evidence input selection includes a private-answer or worker-conversation port')
    generic = {'declared_output_conformance', 'internal_consistency', 'limitations_consistency'}
    require(not (set(selected) & generic), 'Generic structural criteria remain output-only')
    for criterion in profile['criteria']:
        if criterion['criterion_id'] in selected:
            criterion['answerable_from'] = 'selected_task_sources_and_tier1'
    declaration['identity']['version_label'] = version_label
    declaration['identity']['summary'] = declaration['identity']['summary'].rstrip() + \
        ' Uses a separately pinned bounded task-source and Tier 1 semantic review profile.'
    bundle.update(id=bundle['bundle_id'] + ':' + version_label,
                  version=EVIDENCE_REVIEW_PROFILE_VERSION,
                  target_cc_version_range=version_label)
    profile.update(id=profile['profile_id'] + ':' + version_label,
                   version=EVIDENCE_REVIEW_PROFILE_VERSION, target_cc_version_range=version_label,
                   instruction_ref=store.put_blob(store.read_blob(profile['instruction_ref']).rstrip(b'\n') + b'\n\n' +
                                                  reviewer_instructions.encode('utf-8'), media_type='text/plain'),
                   review_mode=EVIDENCE_REVIEW_MODE, review_evidence_max_bytes=max_evidence_bytes,
                   review_evidence_input_names=input_names, evidence_criterion_ids=selected)
    validate('capsule-declaration', declaration)
    validate('check-bundle', bundle)
    validate('checking-profile', profile)
    result = copy.deepcopy(asset)
    result.update(declaration_ref=store.put_record('capsule-declaration', declaration),
                  bundle_ref=store.put_record('check-bundle', bundle),
                  profile_ref=store.put_record('checking-profile', profile))
    return result


class CheckAssetAdmissions:
    def __init__(self, store):
        self.store = store
        self._runners = {}
        self._validated_profiles = {}
        self._development_authorizations = {}
        with store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS calibration_profiles (
                profile_sha TEXT PRIMARY KEY, profile_ref TEXT NOT NULL, registration_ref TEXT NOT NULL,
                closure TEXT NOT NULL, actor TEXT NOT NULL)''')
            db.execute('''CREATE TABLE IF NOT EXISTS calibration_attempts (
                profile_sha TEXT NOT NULL, case_id TEXT NOT NULL, state TEXT NOT NULL,
                receipt_ref TEXT, PRIMARY KEY(profile_sha,case_id))''')
            db.execute('''CREATE TABLE IF NOT EXISTS checking_asset_admissions (
                closure_sha TEXT NOT NULL, asset_kind TEXT NOT NULL, profile_sha TEXT NOT NULL,
                receipt_ref TEXT NOT NULL, PRIMARY KEY(closure_sha,asset_kind,profile_sha))''')

    def closure(self, bundle_ref, profile_ref):
        bundle = self.store.read_record(bundle_ref, contract_id='check-bundle')
        profile = self.store.read_record(profile_ref, contract_id='checking-profile')
        runners = {check['runner_ref']['sha256']: check['runner_ref'] for check in bundle['checks']}
        for ref in (*runners.values(), profile['instruction_ref']):
            self.store.read_blob(ref)
        return {'bundle_ref': dict(bundle_ref), 'profile_ref': dict(profile_ref),
                'runner_refs': [runners[key] for key in sorted(runners)],
                'instruction_ref': dict(profile['instruction_ref'])}

    def authorize_development_builtin(self, bundle_ref, profile_ref, authorization_ref):
        """Select shipped guards locally without claiming independent calibration."""
        authorization=self.store.read_record(authorization_ref)
        closure=self.closure(bundle_ref,profile_ref)
        if (self.store.record_kind(authorization_ref)!='development-builtin-authorization'
                or authorization.get('qualification_status')!='not_run'
                or authorization.get('authorization_basis')!='user_C022'
                or authorization.get('checking_closure')!=closure):
            raise ResearchError('development_builtin_binding','Development authorization differs from shipped guards')
        self._development_authorizations[json_bytes([bundle_ref,profile_ref])]=(closure,authorization_ref)

    def register_runner(self, implementation_ref, evaluate):
        """Protected composition seam, analogous to the installed CC registry.

        Neither operator YAML nor any client/candidate supplies a callable.
        An adapter executes measurements; it never supplies a pass decision.
        """
        validate('Ref', implementation_ref)
        self.store.read_blob(implementation_ref)
        if not callable(evaluate):
            raise ResearchError('calibration_runner', 'Installed calibration adapter must be callable')
        if implementation_ref['sha256'] in self._runners:
            raise ResearchError('calibration_runner', 'Calibration adapter is already registered')
        self._runners[implementation_ref['sha256']] = (dict(implementation_ref), evaluate)

    def _profile(self, ref):
        cache_key=json_bytes(ref)
        cached=self._validated_profiles.get(cache_key)
        if cached is not None:
            # These facts derive solely from immutable exact-byte Refs. Verify
            # current custody/hash for every distinct dependency, then reuse
            # the already validated schema/coverage calculation. Registrations,
            # issued claims, request state and deadlines are never cached.
            value,closure,dependencies=cached
            for dependency in dependencies:self.store.read_blob(dependency)
            return copy.deepcopy(value),copy.deepcopy(closure)
        value = self.store.read_record(ref)
        fields = {'schema', 'id', 'bundle_ref', 'profile_ref', 'measurement_runner_ref', 'cases'}
        if (not isinstance(value, dict) or set(value) != fields or value['schema'] != 'ai4r-check-calibration:1'
                or not isinstance(value['id'], str) or not value['id'] or not isinstance(value['cases'], list) or not value['cases']):
            raise ResearchError('calibration_profile', 'An exact protected calibration profile is required')
        closure = self.closure(value['bundle_ref'], value['profile_ref'])
        validate('Ref', value['measurement_runner_ref'])
        self.store.read_blob(value['measurement_runner_ref'])
        bundle = self.store.read_record(value['bundle_ref'], contract_id='check-bundle')
        profile = self.store.read_record(value['profile_ref'], contract_id='checking-profile')
        known = {'bundle': {r['check_id'] for r in bundle['checks']},
                 'criteria': {r['criterion_id'] for r in profile['criteria']}}
        mandatory = {'bundle': {r['check_id'] for r in bundle['checks'] if r['blocking']},
                     'criteria': {r['criterion_id'] for r in profile['criteria'] if r['blocking']}}
        coverage = {kind: set() for kind in known}; challenges = {kind: set() for kind in known}; ids = set()
        for case in value['cases']:
            if (not isinstance(case, dict) or set(case) != {'case_id', 'asset_kind', 'challenge_class', 'declaration_ref', 'subject_ref', 'expected_ref', 'output_port'}
                    or not isinstance(case['case_id'], str) or not case['case_id'] or case['case_id'] in ids
                    or case['asset_kind'] not in known or case['challenge_class'] not in CHALLENGES):
                raise ResearchError('calibration_profile', 'Calibration case identity or source challenge class is invalid')
            ids.add(case['case_id'])
            for key in ('declaration_ref', 'subject_ref', 'expected_ref'):
                validate('Ref', case[key]); self.store.read_blob(case[key])
            declaration = self.store.read_record(case['declaration_ref'], contract_id='capsule-declaration')
            if declaration['identity']['name'] != bundle['target_cc_name'] or declaration['identity']['name'] != profile['target_cc_name']:
                raise ResearchError('calibration_profile', 'Calibration subject does not match the pinned asset target')
            if case['output_port'] not in {port['name'] for port in declaration['ports']['outputs']}:
                raise ResearchError('calibration_profile', 'Calibration output port is not declared')
            expected = self.store.read_record(case['expected_ref'])
            kind = case['asset_kind']
            if (not isinstance(expected, dict) or not expected or set(expected) - known[kind]
                    or any(outcome not in OUTCOMES for outcome in expected.values())):
                raise ResearchError('calibration_profile', 'Expected outcomes must be fixed exact known check or criterion labels')
            coverage[kind].update(expected); challenges[kind].add(case['challenge_class'])
        if any(not mandatory[kind].issubset(coverage[kind]) or challenges[kind] != CHALLENGES for kind in known):
            raise ResearchError('calibration_profile', 'Both independent assets need all five source challenge classes and mandatory ID coverage')
        dependencies=[ref,value['bundle_ref'],value['profile_ref'],value['measurement_runner_ref'],
            closure['instruction_ref'],*closure['runner_refs']]
        dependencies.extend(case[key] for case in value['cases'] for key in ('declaration_ref','subject_ref','expected_ref'))
        dependencies=list({json_bytes(dependency):copy.deepcopy(dependency) for dependency in dependencies}.values())
        self._validated_profiles[cache_key]=(copy.deepcopy(value),copy.deepcopy(closure),dependencies)
        return value, closure

    def register_profile(self, profile_ref, actor):
        actor.require('verifier_assets')
        _, closure = self._profile(profile_ref)
        with self.store._lock:
            prior = self.store.connection.execute('SELECT * FROM calibration_profiles WHERE profile_sha=?', (profile_ref['sha256'],)).fetchone()
        if prior:
            if json.loads(prior['profile_ref']) != profile_ref:
                raise ResearchError('calibration_profile', 'Calibration identity is ambiguous')
            return json.loads(prior['registration_ref'])
        receipt = self.store.append_record('calibration-profile-registration', {'id': 'calibration-profile:' + uuid.uuid4().hex,
            'profile_ref': profile_ref, 'closure': closure, 'actor': actor.account_id, 'registered_at': utc_now()})
        with self.store.transaction() as db:
            db.execute('INSERT INTO calibration_profiles VALUES(?,?,?,?,?)', (profile_ref['sha256'], json_bytes(profile_ref).decode(),
                json_bytes(receipt).decode(), json_bytes(closure).decode(), actor.account_id))
        return receipt

    def _registered(self, profile_ref):
        profile, closure = self._profile(profile_ref)
        with self.store._lock:
            row = self.store.connection.execute('SELECT * FROM calibration_profiles WHERE profile_sha=?', (profile_ref['sha256'],)).fetchone()
        if not row or json.loads(row['profile_ref']) != profile_ref or json.loads(row['closure']) != closure:
            raise ResearchError('calibration_unregistered', 'Exact profile and asset closure must be preregistered before measurement')
        receipt = json.loads(row['registration_ref'])
        if self.store.read_record(receipt)['profile_ref'] != profile_ref:
            raise ResearchError('calibration_unregistered', 'Protected preregistration receipt is inconsistent')
        return profile, closure, receipt

    def _indexed_after(self, ref, registration_ref, kind):
        self.store.read_blob(ref)
        with self.store._lock:
            observed = self.store.connection.execute('SELECT rowid,kind FROM records WHERE id=?', (ref['id'],)).fetchone()
            registered = self.store.connection.execute('SELECT rowid FROM records WHERE id=?', (registration_ref['id'],)).fetchone()
        if not observed or not registered or observed['kind'] != kind or observed['rowid'] <= registered['rowid']:
            raise ResearchError('calibration_attribution', 'Measurement must be an exact protected record produced after preregistration')

    def _outcomes(self, profile, case, result, registration_ref):
        if not isinstance(result, dict) or set(result) != {'result_ref', 'model_call_refs'} or not isinstance(result['model_call_refs'], list):
            raise ResearchError('calibration_attribution', 'Calibration adapters return captured record Refs, never pass booleans')
        kind = case['asset_kind']; ref = result['result_ref']
        contract = 'deterministic-check-result' if kind == 'bundle' else 'verifier-assessment'
        self._indexed_after(ref, registration_ref, contract)
        record = self.store.read_record(ref, contract_id=contract)
        measured_subject=case['subject_ref'];subject_bytes=self.store.read_blob(case['subject_ref'])
        if kind=='criteria':
            declaration=self.store.read_record(case['declaration_ref'],contract_id='capsule-declaration')
            schema=next(port['schema_ref'] for port in declaration['ports']['outputs'] if port['name']==case['output_port'])
            from .verifier import contract_is
            if contract_is(schema,'poc-artifact-bundle'):
                from ..gate import zip_projection
                subject_bytes=zip_projection(subject_bytes)
                measured_subject=self.store.put_blob(subject_bytes,media_type='text/plain;charset=utf-8')
        if measured_subject not in record.get('subject_refs', [record['subject_ref']]):
            raise ResearchError('calibration_attribution', 'Measured subject differs from its fixed case')
        if kind == 'bundle':
            if result['model_call_refs']:
                raise ResearchError('calibration_attribution', 'Deterministic calibration cannot certify itself with a model')
            plan = self._measurement_plan(record['check_plan_ref'],profile,case)
            if profile['bundle_ref'] not in plan['runner_refs'] or plan['profile_ref'] != profile['profile_ref']:
                raise ResearchError('calibration_attribution', 'Measured checks differ from the pinned asset closure')
            items = record['results']; key = 'check_id'
        else:
            review = self.store.read_record(record['review_context_ref'], contract_id='review-context')
            plan = self._measurement_plan(review['check_plan_ref'],profile,case)
            if plan['profile_ref'] != profile['profile_ref'] or review['subject_ref'] != case['subject_ref']:
                raise ResearchError('calibration_attribution', 'Measured review differs from its fixed profile and case')
            if len(result['model_call_refs']) != 1:
                raise ResearchError('calibration_attribution', 'Semantic calibration requires its actual single governed model call')
            call_ref = result['model_call_refs'][0]
            self._indexed_after(call_ref, registration_ref, 'model-call')
            call = self.store.read_record(call_ref, contract_id='model-call')
            if call['outcome'] != 'completed' or call['call_function'] != 'verifier' or call['observed_runtime'] is not True:
                raise ResearchError('calibration_attribution', 'Semantic calibration has no completed attributable real governed call')
            with self.store._lock:
                claim = self.store.connection.execute('SELECT claim_ref FROM model_calls WHERE call_id=? AND invocation_id=?',
                    (call['id'], call['invocation_id'])).fetchone()
            private_claim=None
            if not claim:private_claim=self._private_call_claim(profile,case,plan,call,registration_ref)
            if not claim and private_claim is None:
                raise ResearchError('calibration_attribution', 'Semantic calibration has no completed attributable real governed call')
            claim_ref=json.loads(claim['claim_ref']) if claim else private_claim
            self._indexed_after(claim_ref,registration_ref,'model-call-claim' if claim else 'calibration-call-claim')
            claimed=self.store.read_record(claim_ref)
            if claimed['call_id']!=call['id'] or any(claimed[key]!=call[key] for key in ('invocation_id','execution_id')):
                raise ResearchError('calibration_attribution','Model call does not match its protected durable claim')
            starts=[row for row in self.store.iter_records(kinds=('model-call-start',)) if row['record'].get('call_id')==call['id']]
            if len(starts)!=1 or starts[0]['record'].get('call_claim_ref')!=claim_ref:
                raise ResearchError('calibration_attribution','Actual model start does not match its protected claim')
            self._indexed_after(starts[0]['ref'],registration_ref,'model-call-start')
            outputs = [self.store.read_record(e) for e in call['evidence_refs'] if self.store.record_kind(e) == 'model-call-output']
            if len(outputs) != 1 or outputs[0].get('call_id') != call['id'] or outputs[0].get('invocation_id') != call['invocation_id']:
                raise ResearchError('calibration_attribution', 'Actual model output is unavailable or belongs to another call')
            subject_profile = self.store.read_record(profile['profile_ref'], contract_id='checking-profile')
            criteria=[item for item in subject_profile['criteria'] if item['target_port'] in (None,case['output_port'])]
            instructions=self.store.read_blob(subject_profile['instruction_ref']).decode('utf-8')
            instructions+='\nCriteria for this output:\n'+json.dumps(criteria,ensure_ascii=False)
            payload=json.dumps({'subject_declaration':self.store.read_blob(case['declaration_ref']).decode('utf-8'),
                'subject_output':subject_bytes.decode('utf-8')},ensure_ascii=False)
            expected_prompt=instructions+'\n\n<subject_payload>\n'+payload+'\n</subject_payload>'
            if private_claim:
                import hashlib
                if claimed.get('expected_prompt_sha256')!=hashlib.sha256(expected_prompt.encode()).hexdigest():
                    raise ResearchError('calibration_attribution','Private prompt grant differs from exact subject projection')
            inputs=[self.store.read_record(e) for e in call['evidence_refs'] if self.store.record_kind(e)=='model-call-input']
            if len(inputs)!=1 or inputs[0].get('prompt')!=expected_prompt or inputs[0].get('call_id')!=call['id']:
                raise ResearchError('calibration_attribution','Actual verifier payload differs from fixed declaration/output/instructions')
            from ..gate import assemble_assessment
            recomputed = assemble_assessment(json.loads(outputs[0]['text']), criteria, case['declaration_ref'],
                measured_subject, record['review_context_ref'])
            if recomputed != record:
                raise ResearchError('calibration_attribution', 'Assessment is not the actual captured model output')
            items = record['findings']; key = 'criterion_id'
        if len({item[key] for item in items}) != len(items):
            raise ResearchError('calibration_attribution', 'Duplicate measured check or criterion')
        observed = {item[key]: item['outcome'] for item in items}
        expected = self.store.read_record(case['expected_ref'])
        return all(observed.get(key) == outcome for key, outcome in expected.items())

    def _measurement_plan(self,ref,profile,case):
        if self.store.record_kind(ref)!='calibration-check-plan':return self.store.read_record(ref,contract_id='bound-check-plan')
        value=self.store.read_record(ref)
        required={'schema','id','contract_ref','node_contract_ref','input_refs','profile_ref','policy_ref','mandatory_deterministic',
            'mandatory_semantic','runner_refs','subnode_id','request_ref','calibration_profile_ref','case_id'}
        if (not isinstance(value,dict) or set(value)!=required or value['schema']!='ai4r-calibration-check-plan:1'
                or value['case_id']!=case['case_id'] or value['profile_ref']!=profile['profile_ref']):
            raise ResearchError('calibration_attribution','Private measurement check plan differs from the fixed case')
        request=self.store.read_record(value['request_ref']);validate('urn:ai4r:private:check-calibration-request:1',request)
        if request['calibration_profile_ref']!=value['calibration_profile_ref'] or self.store.read_record(value['calibration_profile_ref'])!=profile:
            raise ResearchError('calibration_attribution','Private measurement plan names another preregistered profile')
        return value

    def _private_call_claim(self,profile,case,plan,call,registration_ref):
        with self.store._lock:
            if self.store.connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='private_calibration_calls'").fetchone() is None:return None
            row=self.store.connection.execute('SELECT * FROM private_calibration_calls WHERE call_id=? AND execution_id=?',
                (call['id'],call['execution_id'])).fetchone()
        if row is None:return None
        claim_ref=json.loads(row['claim_ref']);claimed=self.store.read_record(claim_ref)
        grant_ref=claimed.get('grant_ref');grant=self.store.read_record(grant_ref);validate('urn:ai4r:private:calibration-case-grant:1',grant)
        request=self.store.read_record(grant['request_ref']);validate('urn:ai4r:private:check-calibration-request:1',request)
        runtime=self.store.read_record(request['runtime_ref']);validate('urn:ai4r:private:calibration-runtime:1',runtime)
        with self.store._lock:
            started=self.store.connection.execute('SELECT * FROM private_calibration_requests WHERE id=?',(request['id'],)).fetchone()
            issued=self.store.connection.execute('SELECT * FROM private_calibration_grants WHERE execution_id=?',(call['execution_id'],)).fetchone()
        exact={'request_ref':plan.get('request_ref'),'calibration_profile_ref':plan.get('calibration_profile_ref'),'case_id':case['case_id'],
            'subject_declaration_ref':case['declaration_ref'],'subject_ref':case['subject_ref'],'checking_profile_ref':profile['profile_ref'],
            'instruction_ref':self.store.read_record(profile['profile_ref'])['instruction_ref']}
        if (not started or not issued or self.store.record_kind(grant_ref)!='calibration-case-grant'
                or self.store.record_kind(grant['request_ref'])!='check-calibration-request' or self.store.record_kind(request['runtime_ref'])!='calibration-runtime'
                or json.loads(issued['grant_ref'])!=grant_ref or json.loads(started['request_ref'])!=grant['request_ref']
                or any(grant.get(k)!=v for k,v in exact.items()) or request['id']!=row['request_id'] or row['case_id']!=case['case_id'] or row['ordinal']!=1
                or call['invocation_id']!=grant['invocation_id'] or call['model_selection_profile_ref']!=grant['model_selection_profile_ref']
                or call['deployment_ref']!=grant['deployment_ref'] or request['calibration_profile_ref'] not in runtime['approved_profile_refs']
                or request['actor_id']!=self.store.read_record(registration_ref)['actor']
                or grant['context_ref']!=runtime['case_context_refs'][request['calibration_profile_ref']['sha256']][case['case_id']]
                or claimed.get('contract_ref')!=grant_ref or claimed.get('request_ref')!=grant['request_ref'] or claimed.get('ordinal')!=1
                or claimed.get('expected_prompt_sha256')!=grant['expected_prompt_sha256']):
            raise ResearchError('calibration_attribution','Private measurement call does not join its exact registered request/grant/ledger')
        # Independently reconstruct the original runtime/policy and high-resolution
        # private chronology. A producer's matching grant/claim is insufficient.
        import math
        from ..calibration_authority import epoch
        configuration=self.store.read_record(runtime['configuration_ref'])
        policy_ref=configuration.get('operator',configuration)['cc']['plan_policy_ref']
        policy=self.store.read_record(policy_ref,contract_id='plan-policy')
        selection=self.store.read_record(runtime['model_selection_profile_ref'],contract_id='model-selection-profile')
        verifier=self.store.read_record(runtime['verifier_declaration_ref'],contract_id='capsule-declaration')
        checking=self.store.read_record(profile['profile_ref'],contract_id='checking-profile')
        starts=[e for e in self.store.iter_records(kinds=('calibration-request-start',)) if e['record'].get('request_ref')==grant['request_ref']]
        returns=[e for e in self.store.iter_records(kinds=('calibration-call-return',)) if e['record'].get('call_id')==call['id']]
        with self.store._lock:
            counts=self.store.connection.execute('SELECT COUNT(*) AS total FROM private_calibration_calls WHERE request_id=?',(request['id'],)).fetchone()['total']
        if len(starts)!=1 or len(returns)!=1:
            raise ResearchError('calibration_attribution','Private measurement needs one original request-start and actual call-return capture')
        original=starts[0]['record'];returned=returns[0]['record']
        finite=lambda n:type(n) in (int,float) and math.isfinite(n)
        times=(original.get('started_epoch'),original.get('deadline_epoch'),issued['started_epoch'],issued['deadline_epoch'],claimed.get('claimed_epoch'),returned.get('returned_epoch'))
        expected_deadline=min(original['started_epoch']+runtime['limits']['time_s'],epoch(request['expires_at'])) if all(finite(n) for n in times) else None
        if (not all(finite(n) for n in times) or original['started_epoch']!=started['started_epoch']
                or original['deadline_epoch']!=started['deadline_epoch'] or original['deadline_epoch']!=expected_deadline
                or not epoch(request['created_at'])<=original['started_epoch']<epoch(request['created_at'])+1
                or not original['started_epoch']<=issued['started_epoch']<=claimed['claimed_epoch']<=returned['returned_epoch']<=min(original['deadline_epoch'],issued['deadline_epoch'])
                or not epoch(grant['created_at'])<=issued['started_epoch']<epoch(grant['created_at'])+1
                or issued['deadline_epoch']!=min(original['deadline_epoch'],issued['started_epoch']+grant['limits']['time_s'])
                or returned.get('request_ref')!=grant['request_ref'] or returned.get('grant_ref')!=grant_ref
                or returned.get('call_ref')!=self.store.record_ref(call['id']) or returned.get('execution_id')!=call['execution_id']
                or returned.get('invocation_id')!=call['invocation_id']
                or any(grant[k]!=runtime[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref'))
                or any(claimed.get(k)!=runtime[k] for k in ('configuration_ref','model_selection_profile_ref','deployment_ref'))
                or selection['policy_mode']!='fixed_baseline' or selection['approved_model_ids']!=['codex-cli-default'] or selection['policy_ref']!=policy_ref
                or any(runtime['limits'][k]>policy['aggregate_limits'][k] for k in ('time_s','model_calls','memory_mb'))
                or counts!=started['calls'] or counts>runtime['limits']['model_calls'] or counts<1
                or grant['limits']['model_calls']!=1 or claimed['limits']['model_calls']!=1
                or grant['limits']['memory_mb']>runtime['limits']['memory_mb']
                or claimed['limits']['memory_mb']>grant['limits']['memory_mb']
                or grant['limits']['time_s']>min(checking['time_s'],verifier['budget']['per_call']['wall_s'],runtime['limits']['time_s'])
                or claimed['limits']['time_s']>grant['limits']['time_s']
                or claimed.get('cc_name')!=verifier['identity']['name'] or claimed.get('cc_version')!=verifier['identity']['version_label']):
            raise ResearchError('calibration_attribution','Private measurement runtime/policy/deadline/counter provenance is inconsistent')
        self._indexed_after(returns[0]['ref'],claim_ref,'calibration-call-return')
        self._indexed_after(returns[0]['ref'],self.store.record_ref(call['id']),'calibration-call-return')
        call_starts=[e for e in self.store.iter_records(kinds=('model-call-start',)) if e['record'].get('call_id')==call['id']]
        if len(call_starts)!=1 or not epoch(claimed['claimed_at'])<=epoch(call['started_at'])<=epoch(call['ended_at'])<=math.floor(returned['returned_epoch']):
            raise ResearchError('calibration_attribution','Original private call-start/completion chronology is inconsistent')
        self._indexed_after(call_starts[0]['ref'],claim_ref,'model-call-start')
        return claim_ref

    async def measure(self, profile_ref, actor, *, stop_on_failure=False):
        actor.require('verifier_assets')
        profile, closure, registration_ref = self._registered(profile_ref)
        installed = self._runners.get(profile['measurement_runner_ref']['sha256'])
        if installed is None or installed[0] != profile['measurement_runner_ref']:
            raise ResearchError('calibration_runner_unavailable', 'The exact protected calibration measurement adapter is unavailable')
        receipts = []
        for case in profile['cases']:
            with self.store.transaction() as db:
                old = db.execute('SELECT * FROM calibration_attempts WHERE profile_sha=? AND case_id=?', (profile_ref['sha256'], case['case_id'])).fetchone()
                if old:
                    if old['receipt_ref'] is None:
                        raise ResearchError('calibration_uncertain', 'An issued calibration attempt is never implicitly replayed')
                    prior=json.loads(old['receipt_ref']);receipts.append(prior)
                    if stop_on_failure and self.store.read_record(prior)['status']!='matched':break
                    continue
                db.execute('INSERT INTO calibration_attempts VALUES(?,?,?,NULL)', (profile_ref['sha256'], case['case_id'], 'issued'))
            result = None; status = 'blocked'; reason = None
            try:
                result = installed[1](dict(case), dict(closure), profile_ref)
                if inspect.isawaitable(result): result = await result
                status = 'matched' if self._outcomes(profile, case, result, registration_ref) else 'mismatched'
            except Exception as error:
                reason = getattr(error, 'code', 'calibration_measurement_failed')
            receipt = self.store.append_record('calibration-measurement', {'id': 'calibration-case:' + uuid.uuid4().hex,
                'profile_ref': profile_ref, 'registration_ref': registration_ref, 'case_id': case['case_id'],
                'asset_kind': case['asset_kind'], 'result': result if isinstance(result, dict) and set(result) == {'result_ref', 'model_call_refs'} else None,
                'status': status, 'reason_code': reason, 'recorded_at': utc_now()})
            with self.store.transaction() as db:
                db.execute('UPDATE calibration_attempts SET state=?,receipt_ref=? WHERE profile_sha=? AND case_id=?',
                    (status, json_bytes(receipt).decode(), profile_ref['sha256'], case['case_id']))
            receipts.append(receipt)
            if stop_on_failure and status!='matched':break
        return receipts

    def admit(self, profile_ref, actor, *, publish=True, guard=None):
        actor.require('verifier_assets')
        profile, closure, registration_ref = self._registered(profile_ref)
        import hashlib
        closure_sha = hashlib.sha256(json_bytes(closure)).hexdigest(); admissions = {}
        for kind in ('bundle', 'criteria'):
            if guard:guard()
            measured = []; failures = []
            for case in (item for item in profile['cases'] if item['asset_kind'] == kind):
                with self.store._lock:
                    row = self.store.connection.execute('SELECT * FROM calibration_attempts WHERE profile_sha=? AND case_id=?', (profile_ref['sha256'], case['case_id'])).fetchone()
                if not row or row['receipt_ref'] is None:
                    failures.append('measurement_missing'); continue
                ref = json.loads(row['receipt_ref']); receipt = self.store.read_record(ref); measured.append(ref)
                if receipt['profile_ref'] != profile_ref or receipt['registration_ref'] != registration_ref or receipt['case_id'] != case['case_id']:
                    raise ResearchError('calibration_attribution', 'Stored calibration receipt was substituted')
                if receipt['status'] != 'matched' or not self._outcomes(profile, case, receipt['result'], registration_ref):
                    failures.append(receipt['reason_code'] or 'challenge_mismatch')
            asset_ref = profile['bundle_ref' if kind == 'bundle' else 'profile_ref']
            record = {'id': 'checking-admission:' + uuid.uuid4().hex, 'asset_kind': kind, 'asset_ref': asset_ref,
                'calibration_profile_ref': profile_ref, 'registration_ref': registration_ref, 'closure': closure,
                'measurement_refs': measured, 'status': 'blocked' if failures else 'admitted',
                'reasons': failures, 'actor': actor.account_id, 'recorded_at': utc_now()}
            ref = self.store.append_record('checking-asset-admission', record); admissions[kind] = ref
            if not failures and publish:
                with self.store.transaction() as db:
                    if guard:guard()
                    db.execute('INSERT OR IGNORE INTO checking_asset_admissions VALUES(?,?,?,?)',
                        (closure_sha, kind, profile_ref['sha256'], json_bytes(ref).decode()))
        return admissions

    def publish_admissions(self, admissions, *, guard, commit):
        """Publish measured eligibility after the private final receipt is durable."""
        import hashlib
        rows=[]
        for kind,ref in admissions.items():
            record=self.store.read_record(ref)
            if self.store.record_kind(ref)!='checking-asset-admission' or record['asset_kind']!=kind:
                raise ResearchError('calibration_attribution','Staged asset admission identity is invalid')
            profile,closure,registration=self._registered(record['calibration_profile_ref'])
            if record['closure']!=closure or record['registration_ref']!=registration:
                raise ResearchError('calibration_attribution','Staged admission differs from preregistration')
            if record['status']!='admitted':continue
            expected={case['case_id'] for case in profile['cases'] if case['asset_kind']==kind}
            originals=[self.store.read_record(ref) for ref in record['measurement_refs']]
            if ({value['case_id'] for value in originals}!=expected or len(originals)!=len(expected)
                    or record['asset_ref']!=profile['bundle_ref' if kind=='bundle' else 'profile_ref']):
                raise ResearchError('calibration_attribution','Staged admission omits or duplicates original required challenge measurements')
            for measured_ref in record['measurement_refs']:
                measured=self.store.read_record(measured_ref)
                with self.store._lock:
                    actual=self.store.connection.execute('SELECT receipt_ref FROM calibration_attempts WHERE profile_sha=? AND case_id=?',
                        (record['calibration_profile_ref']['sha256'],measured['case_id'])).fetchone()
                if (not actual or json.loads(actual['receipt_ref'])!=measured_ref or measured['profile_ref']!=record['calibration_profile_ref']
                        or measured['registration_ref']!=registration or measured['asset_kind']!=kind):
                    raise ResearchError('calibration_attribution','Staged measurement is not the original protected case receipt')
                case=next(c for c in profile['cases'] if c['case_id']==measured['case_id'])
                if measured['status']!='matched' or not self._outcomes(profile,case,measured['result'],registration):
                    raise ResearchError('calibration_attribution','Staged measurement no longer validates')
            rows.append((hashlib.sha256(json_bytes(closure)).hexdigest(),kind,record['calibration_profile_ref']['sha256'],json_bytes(ref).decode()))
        with self.store.transaction() as db:
            guard()
            for row in rows:db.execute('INSERT OR IGNORE INTO checking_asset_admissions VALUES(?,?,?,?)',row)
            commit(db)

    def require(self, bundle_ref, profile_ref):
        development=self._development_authorizations.get(json_bytes([bundle_ref,profile_ref]))
        if development is not None:
            closure,authorization_ref=development
            authorization=self.store.read_record(authorization_ref)
            if (self.closure(bundle_ref,profile_ref)!=closure
                    or authorization.get('checking_closure')!=closure
                    or authorization.get('qualification_status')!='not_run'):
                raise ResearchError('development_builtin_binding','Selected development checking bytes changed')
            return (authorization_ref,)
        import hashlib
        closure = self.closure(bundle_ref, profile_ref); closure_sha = hashlib.sha256(json_bytes(closure)).hexdigest()
        with self.store._lock:
            rows = self.store.connection.execute('SELECT * FROM checking_asset_admissions WHERE closure_sha=?', (closure_sha,)).fetchall()
        if len(rows) != 2 or {row['asset_kind'] for row in rows} != {'bundle', 'criteria'} or len({row['profile_sha'] for row in rows}) != 1:
            raise ResearchError('check_asset_unqualified', 'Independent calibration qualification is missing or ambiguous for the exact checking assets')
        for row in rows:
            receipt = self.store.read_record(json.loads(row['receipt_ref']))
            if receipt['status'] != 'admitted' or receipt['closure'] != closure or receipt['asset_kind'] != row['asset_kind']:
                raise ResearchError('check_asset_unqualified', 'Independent calibration admission does not match the exact checking closure')
            self._registered(receipt['calibration_profile_ref'])
        return tuple(json.loads(row['receipt_ref']) for row in rows)
