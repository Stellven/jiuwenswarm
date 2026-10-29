"""Immutable admission history, independent check associations and human standing."""

from __future__ import annotations

import hashlib
import inspect
import json
import os
import re
import stat
import uuid
from pathlib import Path
from datetime import datetime, timezone

from .checks.admission import declaration_checks,verify_self_test,rubric_checks
from .checks.assets import CheckAssetAdmissions
from .contracts import Principal, Ref, ResearchError, validate
from .state import json_bytes, utc_now


def version_matches(version: str, supported: str) -> bool:
    if version==supported:return True
    if not supported.endswith('.x'):return False
    prefix=supported[:-2]
    return version==prefix or version.startswith(prefix+'.') and len(version)>len(prefix)+1


class LibraryService:
    def render_declaration(self,declaration_ref):
        declaration=self.store.read_record(declaration_ref,contract_id='capsule-declaration')
        sections=['# Capsule declaration: '+declaration['identity']['name'],
            'Exact declaration SHA-256: `'+declaration_ref['sha256']+'`.',
            'This view preserves author declarations. Separate protected admission and gate records determine eligibility.']
        for key,value in declaration.items():
            sections.extend(['## '+key,'```json',json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False),'```'])
        raw=('\n\n'.join(sections)+'\n').encode('utf-8')
        ref=self.store.capture_record_file('capsules/'+declaration_ref['sha256']+'/make_capsule.md',raw,media_type='text/markdown')
        self.store.append_record('declaration-view',{'id':'declaration-view:'+declaration_ref['sha256'],'declaration_ref':declaration_ref,'view_ref':ref})
        return ref

    def __init__(self, store, *, executor=None, bootstrap_pins=(),rsi_public_key=None,rsi_key_id=None,rsi_inbox=None,rsi_custodian_uid=None,check_assets=None,self_test_provider=None,rsi_security_guard=None):
        self.store, self.executor = store, executor
        self.self_test_provider=self_test_provider
        self.rsi_security_guard=rsi_security_guard
        self.bootstrap_pins = frozenset(bootstrap_pins)
        self._rsi_public_key,self._rsi_key_id=rsi_public_key,rsi_key_id
        self._rsi_inbox=Path(rsi_inbox) if rsi_inbox is not None else None
        if self._rsi_inbox is not None and not self._rsi_inbox.is_absolute():
            raise ResearchError('rsi_custody','The protected inbox must be an absolute path')
        self._rsi_custodian_uid=rsi_custodian_uid
        self._custody_receipts={}
        self._snapshot_cache=None
        self._inspection_cache=None
        self._verifier_pin=None
        self._development_entries={}
        self._development_associations={}
        self.development_mode=False
        # Protected composition only; never populated from submit/config data.
        self.check_assets=CheckAssetAdmissions(store) if check_assets is None else check_assets
        with store.transaction() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS library_versions (
                name TEXT NOT NULL, version TEXT NOT NULL, declaration_ref TEXT NOT NULL,
                admission_ref TEXT NOT NULL, standing TEXT NOT NULL, effect_scope TEXT NOT NULL,
                body_refs TEXT NOT NULL, origin TEXT NOT NULL, PRIMARY KEY(name,version))''')
            db.execute('''CREATE TABLE IF NOT EXISTS check_associations (
                declaration_sha256 TEXT PRIMARY KEY, bundle_ref TEXT NOT NULL,
                profile_ref TEXT NOT NULL, evidence_refs TEXT NOT NULL, actor TEXT NOT NULL)''')

    def _validate_association(self,declaration_ref: Ref,bundle_ref: Ref,profile_ref: Ref)->None:
        declaration = self.store.read_record(declaration_ref, contract_id='capsule-declaration')
        bundle = self.store.read_record(bundle_ref, contract_id='check-bundle')
        profile = self.store.read_record(profile_ref, contract_id='checking-profile')
        name, version = declaration['identity']['name'], declaration['identity']['version_label']
        for asset in (bundle, profile):
            if asset['owner_role'] != 'verifier_owner' or asset['target_cc_name'] != name or not version_matches(version, asset['target_cc_version_range']):
                raise ResearchError('check_compatibility', 'Independent check assets do not cover this exact CC version')
        if bundle['bundle_id'] != name + '.checks' or profile['profile_id'] != name + '.profile':
            raise ResearchError('check_compatibility', 'Check asset IDs must match the selected CC')
        ids = [c['check_id'] for c in bundle['checks']]
        criteria = [c['criterion_id'] for c in profile['criteria']]
        generic = {'declared_output_conformance', 'internal_consistency', 'limitations_consistency'}
        if len(set(ids)) != len(ids) or len(set(criteria)) != len(criteria) or not generic.issubset(criteria):
            raise ResearchError('check_compatibility', 'Duplicate or missing mandatory check criteria')
        review_mode = profile.get('review_mode')
        evidence_ids = profile.get('evidence_criterion_ids', [])
        if review_mode is None:
            if any(key in profile for key in ('review_evidence_max_bytes', 'review_evidence_input_names', 'evidence_criterion_ids')):
                raise ResearchError('verifier_boundary', 'Evidence settings require an explicitly versioned review mode')
            if any(c['answerable_from'] != 'declaration_and_output' or
                   any(word in c['criterion_id'] for word in ('fidelity', 'preservation', 'faithfulness', 'source_support'))
                   for c in profile['criteria']):
                raise ResearchError('verifier_boundary', 'Legacy semantic criteria may use declaration and output only')
        else:
            inputs = profile.get('review_evidence_input_names')
            maximum = profile.get('review_evidence_max_bytes')
            selected = [c['criterion_id'] for c in profile['criteria']
                        if c['answerable_from'] == 'selected_task_sources_and_tier1']
            if (review_mode != 'task_sources_tier1_v1' or profile['version'] != '2.0.0'
                    or not isinstance(inputs, list) or not inputs or len(inputs) != len(set(inputs))
                    or any(not isinstance(name, str) or not name for name in inputs)
                    or type(maximum) is not int or not 1 <= maximum <= 131072
                    or not isinstance(evidence_ids, list) or not evidence_ids
                    or len(evidence_ids) != len(set(evidence_ids)) or set(evidence_ids) != set(selected)
                    or set(evidence_ids) & generic
                    or any(c['answerable_from'] not in {'declaration_and_output', 'selected_task_sources_and_tier1'}
                           for c in profile['criteria'])):
                raise ResearchError('verifier_boundary', 'Evidence-aware review needs an exact bounded v2 evidence policy')
        for criterion in profile['criteria']:
            if review_mode is None and any(word in criterion['criterion_id'] for word in ('fidelity','preservation','faithfulness','source_support')):
                raise ResearchError('verifier_boundary', 'Legacy semantic criteria may not claim source review')
            if criterion['criterion_id'] in generic and not criterion['blocking']:
                raise ResearchError('check_compatibility', 'Generic criteria are blocking')
        for port in declaration['ports']['outputs']:
            if not any(c['check_id'] == port['name'] + '_schema' and c['target_port'] == port['name'] and c['blocking'] and c['reads'] == ['output'] for c in bundle['checks']):
                raise ResearchError('check_compatibility', 'Every output needs its independent blocking schema check')
        for check in bundle['checks']:
            self.store.read_blob(check['runner_ref'])
        self.store.read_blob(profile['instruction_ref'])

    def _record_association(self,declaration_ref,bundle_ref,profile_ref,actor_id,*,evidence_refs=()):
        for ref in evidence_refs:
            self.store.read_blob(ref)
        with self.store.transaction() as db:
            prior = db.execute('SELECT * FROM check_associations WHERE declaration_sha256=?', (declaration_ref['sha256'],)).fetchone()
            if prior:
                if json.loads(prior['bundle_ref']) != bundle_ref or json.loads(prior['profile_ref']) != profile_ref:
                    raise ResearchError('identity_conflict', 'An exact CC version already has another immutable association')
                return
            db.execute('INSERT INTO check_associations VALUES(?,?,?,?,?)',
                       (declaration_ref['sha256'], json_bytes(bundle_ref).decode(), json_bytes(profile_ref).decode(), json_bytes(list(evidence_refs)).decode(), actor_id))
        self.store.append_record('check-association', {'id': 'association:' + uuid.uuid4().hex, 'declaration_ref': declaration_ref,
            'bundle_ref': bundle_ref, 'profile_ref': profile_ref, 'evidence_refs': list(evidence_refs), 'actor': actor_id, 'recorded_at': utc_now()})

    def associate_checks(self,declaration_ref: Ref,bundle_ref: Ref,profile_ref: Ref,actor: Principal,*,evidence_refs=())->None:
        actor.require('verifier_assets')
        self._validate_association(declaration_ref,bundle_ref,profile_ref)
        self._record_association(declaration_ref,bundle_ref,profile_ref,actor.account_id,evidence_refs=evidence_refs)

    def association(self, declaration_ref: Ref) -> dict:
        development=self._development_associations.get(declaration_ref['sha256'])
        if development is not None:return json.loads(json_bytes(development))
        with self.store._lock:
            row = self.store.connection.execute('SELECT * FROM check_associations WHERE declaration_sha256=?', (declaration_ref['sha256'],)).fetchone()
        if not row:
            raise ResearchError('check_association_missing', 'No independently approved compatible check association')
        return {key: json.loads(row[key]) for key in ('bundle_ref','profile_ref','evidence_refs')}

    def eligible_association(self, declaration_ref: Ref) -> dict:
        association=self.association(declaration_ref)
        self._validate_association(declaration_ref,association['bundle_ref'],association['profile_ref'])
        self.check_assets.require(association['bundle_ref'],association['profile_ref'])
        return association

    async def bootstrap(self, declaration_ref, body_refs, actor, **kwargs):
        if declaration_ref['sha256'] not in self.bootstrap_pins:
            raise ResearchError('bootstrap_not_allowed', 'Bootstrap is restricted to the explicit frozen initial catalog')
        return await self.admit(declaration_ref, body_refs, actor, _bootstrap=True, **kwargs)

    def select_development_builtins(self, assets, *, memory_mb):
        """Record local execution permission, explicitly without qualification.

        The overlay never changes strict Library or checking admission tables.
        Per-request checks, independent reviewers and gates remain required.
        """
        if not isinstance(memory_mb,int) or isinstance(memory_mb,bool) or memory_mb<1:
            raise ResearchError('development_builtin_binding','Positive local memory ceiling required')
        for asset in assets:
            declaration_ref=asset['declaration_ref'];body_refs=asset['body_refs']
            if declaration_ref['sha256'] not in self.bootstrap_pins:
                raise ResearchError('development_builtin_binding','Only exact installed built-ins can be selected')
            declaration=self.store.read_record(declaration_ref,contract_id='capsule-declaration')
            self._validate_association(declaration_ref,asset['bundle_ref'],asset['profile_ref'])
            identity=declaration['identity']
            for body in [*identity['body'],identity['carrier']]:
                path=body.get('path',body.get('ref'))
                if path not in body_refs or body_refs[path]['sha256']!=body['sha256']:
                    raise ResearchError('development_builtin_binding','Built-in body differs from declaration')
            for ref in body_refs.values():self.store.read_blob(ref)
            closure=self.check_assets.closure(asset['bundle_ref'],asset['profile_ref'])
            key=hashlib.sha256(json_bytes([declaration_ref,body_refs,closure,memory_mb])).hexdigest()
            authorization=self.store.append_record('development-builtin-authorization',{
                'schema':'ai4r-development-builtin-authorization:1','id':'development-builtin:'+key,
                'authorization_basis':'user_C022','qualification_status':'not_run',
                'declaration_ref':declaration_ref,'body_refs':body_refs,'checking_closure':closure,
                'scope':'explicit_local_research_only',
                'limitations':['Independent calibration and pre-admission self-tests NOT_RUN.',
                    'Per-request deterministic checks, Capsule verifiers and gates remain required.']})
            self.check_assets.authorize_development_builtin(asset['bundle_ref'],asset['profile_ref'],authorization)
            self._development_associations[declaration_ref['sha256']]={
                'bundle_ref':asset['bundle_ref'],'profile_ref':asset['profile_ref'],'evidence_refs':[authorization]}
            bundle=self.store.read_record(asset['bundle_ref'],contract_id='check-bundle')
            profile=self.store.read_record(asset['profile_ref'],contract_id='checking-profile')
            pins={'check_bundle_id':bundle['bundle_id'],'check_bundle_version':bundle['version'],
                'check_bundle_sha256':asset['bundle_ref']['sha256'],'checking_profile_id':profile['profile_id'],
                'checking_profile_version':profile['version'],'checking_profile_sha256':asset['profile_ref']['sha256']}
            cc={'cc_name':identity['name'],'cc_version':identity['version_label'],'declaration_sha256':declaration_ref['sha256']}
            admission=self.store.put_record('library-admission',{
                'schema_version':'1.0.0','id':'dev-admission:'+key[:40],'candidate_ref':declaration_ref,
                'cc':cc,'parent_ref':None,'parent_admission_ref':None,'evidence_refs':[authorization],
                'check_pins':pins,'memory_mb':memory_mb,'status':'admitted','standing':'active',
                'reasons':['User C022 authorizes local built-ins; independent qualification NOT_RUN.']})
            self._development_entries[(identity['name'],identity['version_label'])]={
                'name':identity['name'],'version':identity['version_label'],
                'declaration_ref':json_bytes(declaration_ref).decode(),'admission_ref':json_bytes(admission).decode(),
                'standing':'active','effect_scope':'live_plans','body_refs':json_bytes(body_refs).decode(),
                'origin':'development_builtin'}
        self.development_mode=True

    def capture_rsi_inbox(self,path,actor: Principal,*,read_external=None)->Ref:
        """Import an exact custodian-owned package closure through a read port.

        read_external is protected composition code for immutable side records;
        it supplies bytes only and cannot supply admission verdicts or keys.
        """
        actor.require('library_admit')
        if self._rsi_inbox is None or self._rsi_custodian_uid is None or not hasattr(os,'geteuid'):
            raise ResearchError('rsi_custody_unavailable','Linux custodian-only inbox is not configured')
        if read_external is None:
            from .contracts.inbox import SignedInboxReader
            read_external=SignedInboxReader(self._rsi_inbox,custodian_uid=self._rsi_custodian_uid).read
        root=self._rsi_inbox;supplied=Path(path)
        if supplied.is_symlink():raise ResearchError('rsi_custody','Inbox candidate is a symbolic link')
        resolved=supplied.resolve()
        if root not in resolved.parents:raise ResearchError('rsi_custody','Candidate is outside the protected inbox')
        for entry in (root,*resolved.relative_to(root).parents):
            current=entry if entry==root else root/entry
            if current.is_symlink():raise ResearchError('rsi_custody','Inbox ancestry is a symbolic link')
            metadata=current.stat()
            if metadata.st_uid!=self._rsi_custodian_uid or metadata.st_mode & (stat.S_IWGRP|stat.S_IWOTH):
                raise ResearchError('rsi_custody','Inbox custody permits a non-custodian writer')
        descriptor=os.open(resolved,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(descriptor,'rb') as handle:
            metadata=os.fstat(handle.fileno())
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_uid!=self._rsi_custodian_uid or metadata.st_mode & (stat.S_IWGRP|stat.S_IWOTH):
                raise ResearchError('rsi_custody','Candidate custody is invalid')
            if metadata.st_nlink!=1 or metadata.st_size>4*1024*1024:raise ResearchError('rsi_custody','Candidate custody or transport size is invalid')
            raw=handle.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:raise ResearchError('rsi_custody','Candidate exceeds the private inbox transport size')
        try:package=json.loads(raw.decode('utf-8'));validate('candidate-package',package)
        except (ValueError,UnicodeError,ResearchError) as exc:raise ResearchError('rsi_package_structure','Inbox package is malformed') from exc
        seen=set()
        def capture(value):
            if isinstance(value,dict):
                if set(value)=={'id','sha256'}:
                    validate('Ref',value);key=(value['id'],value['sha256'])
                    if key in seen:return
                    seen.add(key)
                    try:data=self.store.read_blob(value)
                    except ResearchError:
                        data=read_external(value)
                        if not isinstance(data,bytes) or hashlib.sha256(data).hexdigest()!=value['sha256']:
                            raise ResearchError('rsi_refs','External original-byte reference failed integrity')
                        self.store.put_blob(data,record_id=value['id'],provenance={'rsi_inbox_sha256':hashlib.sha256(raw).hexdigest()})
                    try:nested=json.loads(data.decode('utf-8'))
                    except (ValueError,UnicodeError):return
                    capture(nested)
                else:
                    for child in value.values():capture(child)
            elif isinstance(value,list):
                for child in value:capture(child)
        capture(package)
        package_ref=self.store.put_blob(raw,record_id=package['id'],media_type='application/json')
        receipt=self.store.append_record('rsi-custody',{'id':'rsi-custody:'+uuid.uuid4().hex,'package_ref':package_ref,
            'custodian_uid':self._rsi_custodian_uid,'captured_at':utc_now(),'closure_refs':[{'id':i,'sha256':h} for i,h in sorted(seen)]})
        self._custody_receipts[(package_ref['id'],package_ref['sha256'])]=receipt
        return package_ref

    def _require_rsi_security(self,operation,session_ref,candidate_ref):
        try:
            if self.rsi_security_guard is None or not callable(getattr(self.rsi_security_guard,'require',None)):
                raise ValueError('RSI security qualification unavailable')
            proof=self.rsi_security_guard.require(operation,session_ref=session_ref,candidate_ref=candidate_ref)
            if not isinstance(proof,dict) or set(proof)!={'qualification_ref','scope_ref'}:
                raise ValueError('RSI security qualification returned no exact proof')
            for ref in proof.values():
                if not isinstance(ref,dict) or set(ref)!={'id','sha256'} or not ref['id'] or not re.fullmatch('[0-9a-f]{64}',ref['sha256']):
                    raise ValueError('RSI security qualification proof identity invalid')
            return proof
        except (ValueError,KeyError,TypeError,OSError,ResearchError):
            if not self.store.connection.in_transaction:
                self.store.append_record('rsi-security-blocked',{'id':'rsi-security-blocked:'+uuid.uuid4().hex,'operation':operation,
                    'candidate_ref':candidate_ref,'session_ref':session_ref,'reason':'Current independent full13-case RSI security qualification is unavailable','recorded_at':utc_now()})
            raise ResearchError('rsi_security_qualification','Current independent RSI security qualification is unavailable') from None

    def _rsi_security_authorization(self,candidate_ref,operation):
        matches=[]
        for row in self.store.iter_records(kinds=('rsi-security-authorization',)):
            value=row['record']
            if value.get('candidate_ref')!=candidate_ref:continue
            proof=self._require_rsi_security(operation,value['session_ref'],candidate_ref)
            if all(value.get(key)==proof[key] for key in proof):matches.append((row['ref'],value))
        if not matches or len({json_bytes(value['package_ref']) for _,value in matches})!=1:
            raise ResearchError('rsi_security_qualification','RSI lineage has no unambiguous independently qualified package authorization')
        return matches[0][0]

    async def admit_rsi(self,package_ref: Ref,actor: Principal,*,self_test_runner=None)->Ref:
        actor.require('library_admit')
        if self.rsi_security_guard is None:
            self._require_rsi_security('admit',None,package_ref)
        package=self.store.read_record(package_ref,contract_id='candidate-package')
        security=self._require_rsi_security('admit',package['session_ref'],package['child_declaration_ref'])
        parent_row=self.get(package['parent']['cc_name'],package['parent']['cc_version'])
        parent_admission=self.store.read_record(parent_row['admission_ref'],contract_id='library-admission')
        evidence=[package_ref];reason=None
        try:
            receipt=self._custody_receipts.get((package_ref['id'],package_ref['sha256']))
            if receipt is None:raise ResearchError('rsi_custody','Candidate did not arrive through the protected custodian inbox')
            evidence.append(receipt)
            if self._rsi_public_key is None or self._rsi_key_id is None:raise ResearchError('rsi_signature','Pinned custodian public key is unavailable')
            if parent_row['declaration_ref']!=package['parent_declaration_ref'] or parent_admission['status']!='admitted':
                raise ResearchError('rsi_identity','Package parent is not the exact admitted library version')
            protected=set()
            for row in self.entries():
                declaration=self.store.read_record(json.loads(row['declaration_ref']),contract_id='capsule-declaration')
                if declaration['evolution']['rsi']=='none':protected.update(body['sha256'] for body in declaration['identity']['body'])
            from .contracts.rsi import verify_package
            verified=verify_package(package,self.store,public_key=self._rsi_public_key,key_id=self._rsi_key_id,protected_body_hashes=protected)
            child=verified['child']
            authorization=self.store.append_record('rsi-security-authorization',{'id':'rsi-security-authorization:'+uuid.uuid4().hex,
                'candidate_ref':package['child_declaration_ref'],'package_ref':package_ref,'session_ref':package['session_ref'],
                **security,'recorded_at':utc_now()})
            evidence.append(authorization)
            # The candidate cannot pick or revise checking assets. Only the
            # already owner-approved exact parent assets may be inherited,
            # after complete package verification and family compatibility.
            inherited=self.association(package['parent_declaration_ref'])
            self._validate_association(package['child_declaration_ref'],inherited['bundle_ref'],inherited['profile_ref'])
            try:association=self.association(package['child_declaration_ref'])
            except ResearchError as exc:
                if exc.code!='check_association_missing':raise
                inherited_receipt=self.store.append_record('rsi-check-inheritance',{'id':'rsi-check-inheritance:'+uuid.uuid4().hex,
                    'package_ref':package_ref,'parent_declaration_ref':package['parent_declaration_ref'],
                    'child_declaration_ref':package['child_declaration_ref'],'parent_admission_ref':parent_row['admission_ref'],
                    'bundle_ref':inherited['bundle_ref'],'profile_ref':inherited['profile_ref'],'actor':actor.account_id,
                    'reason':'Independent signed package and allowed diff verified; exact owner-approved parent checking family covers this child',
                    'recorded_at':utc_now()})
                self._record_association(package['child_declaration_ref'],inherited['bundle_ref'],inherited['profile_ref'],actor.account_id,
                    evidence_refs=[*inherited['evidence_refs'],inherited_receipt])
                association=self.association(package['child_declaration_ref']);evidence.append(inherited_receipt)
            if any(association[key]!=inherited[key] for key in ('bundle_ref','profile_ref')):
                raise ResearchError('rsi_check_pins',"Child does not inherit the parent's independent exact check pins")
            refs=verified['provenance']['implementation_refs'];by_hash={ref['sha256']:ref for ref in refs}
            body_refs={body['path']:by_hash[body['sha256']] for body in child['identity']['body']}
            for dependency in child['needs']['external']:
                for key in ('pin','lockfile'):
                    pin=dependency.get(key)
                    if pin:
                        inherited_ref=parent_row['body_refs'].get(pin['ref'])
                        if inherited_ref is None or inherited_ref['sha256']!=pin['sha256']:
                            raise ResearchError('rsi_refs','Inherited external dependency is not the exact admitted parent pin')
                        self.store.read_blob(inherited_ref);body_refs[pin['ref']]=inherited_ref
            return await self.admit(package['child_declaration_ref'],body_refs,actor,memory_mb=parent_admission['memory_mb'],
                parent_ref=package['parent_declaration_ref'],parent_admission_ref=parent_row['admission_ref'],evidence_refs=evidence,
                self_test_runner=self_test_runner)
        except (ResearchError,KeyError) as exc:
            code=exc.code if isinstance(exc,ResearchError) else 'rsi_refs'
            blocked=code in {'rsi_custody','rsi_signature','rsi_chain','rsi_refs','evidence_unavailable','check_association_missing','rsi_check_pins'}
            if code=='rsi_security_halt':self.store.append_record('rsi-security-halt',{'id':'rsi-security:'+uuid.uuid4().hex,'package_ref':package_ref,'session_ref':package['session_ref'],'reason_code':code})
            record={'schema_version':'1.0.0','id':'admission:'+uuid.uuid4().hex,'candidate_ref':package['child_declaration_ref'],
                'cc':package['child'],'parent_ref':package['parent_declaration_ref'],'parent_admission_ref':parent_row['admission_ref'],
                'evidence_refs':evidence,'check_pins':parent_admission['check_pins'],'memory_mb':parent_admission['memory_mb'],
                'status':'blocked' if blocked else 'rejected','standing':'inactive','reasons':[code]}
            return self.store.put_record('library-admission',record)

    async def admit(self, declaration_ref: Ref, body_refs: dict[str, Ref], actor: Principal, *,
                    memory_mb: int, self_test_runner=None, _bootstrap=False,
                    parent_ref: Ref | None = None, parent_admission_ref: Ref | None = None,
                    evidence_refs=()) -> Ref:
        actor.require('library_admit')
        try:candidate=json.loads(self.store.read_blob(declaration_ref))
        except (ValueError,UnicodeError):candidate={}
        identity=candidate.get('identity',{}) if isinstance(candidate,dict) else {}
        lineage=identity.get('lineage') if isinstance(identity,dict) else None
        if parent_ref is not None or isinstance(lineage,dict) and lineage.get('builder')=='rsi_workbench':
            self._rsi_security_authorization(declaration_ref,'admit')
        self.store.require_product_material([declaration_ref,*body_refs.values()])
        if not isinstance(memory_mb, int) or isinstance(memory_mb, bool) or memory_mb < 1:
            raise ResearchError('validation', 'Admission requires a protected positive memory ceiling')
        raw = self.store.read_blob(declaration_ref)
        try:
            declaration = json.loads(raw.decode('utf-8'))
            validate('capsule-declaration', declaration)
        except (ValueError, UnicodeError, ResearchError):
            raise ResearchError('declaration_invalid', 'Candidate is not a valid exact declaration')
        if self_test_runner is None and self.self_test_provider is not None:
            self_test_runner=self.self_test_provider.for_admission(actor,memory_mb)
        identity = declaration['identity']
        cc = {'cc_name': identity['name'], 'cc_version': identity['version_label'], 'declaration_sha256': declaration_ref['sha256']}
        reasons, evidence = [], [*evidence_refs,self.render_declaration(declaration_ref)]
        status, pins = 'admitted', None
        try:
            association = self.eligible_association(declaration_ref)
            bundle = self.store.read_record(association['bundle_ref'], contract_id='check-bundle')
            profile = self.store.read_record(association['profile_ref'], contract_id='checking-profile')
            pins = {'check_bundle_id': bundle['bundle_id'], 'check_bundle_version': bundle['version'],
                    'check_bundle_sha256': association['bundle_ref']['sha256'], 'checking_profile_id': profile['profile_id'],
                    'checking_profile_version': profile['version'], 'checking_profile_sha256': association['profile_ref']['sha256']}
        except ResearchError as exc:
            status, reasons = 'blocked', [exc.message]
        try:
            bodies = {path: self.store.read_blob(ref) for path, ref in body_refs.items()}
            required = {p['path'] for p in identity['body']} | {identity['carrier']['ref']}
            for dependency in declaration['needs']['external']:
                for key in ('pin','lockfile'):
                    if dependency.get(key):
                        required.add(dependency[key]['ref'])
            if not required.issubset(bodies):
                status = 'blocked'
                reasons.append('Required exact implementation/dependency bytes are unavailable')
            checks = declaration_checks(declaration, bodies)
            if identity['name']=='research.screening' and 'screening_rubric.json' in bodies:
                checks.extend(rubric_checks(bodies['screening_rubric.json']))
            check_ref = self.store.append_record('admission-host-checks', {'id':'admission-checks:' + uuid.uuid4().hex,
                'candidate_ref':declaration_ref,'results':checks})
            evidence.append(check_ref)
            failures = [r['check_id'] for r in checks if r['outcome'] != 'PASS']
            if failures and status != 'blocked':
                status = 'rejected'
            reasons.extend(failures)
            for test in declaration['guarantees'].get('self_tests', []):
                pin = test['ref']
                if pin['ref'] not in bodies or hashlib.sha256(bodies[pin['ref']]).hexdigest() != pin['sha256']:
                    status = 'blocked' if pin['ref'] not in bodies else 'rejected'
                    reasons.append('self_test_pin:' + test['id'])
                    continue
                if self_test_runner is None:
                    status = 'blocked'
                    reasons.append('Confined self-test executor unavailable:' + test['id'])
                    continue
                try:
                    observed = self_test_runner(test, declaration_ref, body_refs)
                    if inspect.isawaitable(observed):
                        observed = await observed
                    proof=verify_self_test(self.store,test,declaration_ref,body_refs,observed,memory_mb=memory_mb,actor=actor,
                        configuration_ref=getattr(self.self_test_provider,'configuration_ref',None),
                        execution_profile_ref=getattr(self.self_test_provider,'profile_ref',None))
                    evidence.extend([observed,self.store.append_record('admission-self-test', {'id':'self-test:' + uuid.uuid4().hex,
                        'test_id':test['id'],'expected':test['expects'],'observed_ref':observed,'end_state':proof['end_state']})])
                except ResearchError as error:
                    status='blocked' if error.code in {'self_test_unavailable','self_test_adapter_unbuilt','evidence_unavailable','ENVIRONMENT_BLOCKED'} else 'rejected'
                    reasons.append(error.code+':'+test['id'])
        except ResearchError as exc:
            status = 'blocked' if exc.code == 'evidence_unavailable' else 'rejected'
            reasons.append(exc.code)
        if identity.get('load_mode', 'invoked') != 'invoked':
            status = 'rejected'
            reasons.append('m1_kind_admitted')
        if parent_ref is not None:
            lineage = identity.get('lineage', {})
            if lineage.get('parent') != parent_ref or lineage.get('relation') != 'supersedes' or lineage.get('builder') != 'rsi_workbench':
                status = 'rejected'
                reasons.append('rsi_child_has_lineage')
        record = {'schema_version':'1.0.0','id':'admission:' + uuid.uuid4().hex,'candidate_ref':declaration_ref,
                  'cc':cc,'parent_ref':parent_ref,'parent_admission_ref':parent_admission_ref,'evidence_refs':evidence,
                  'check_pins':pins,'memory_mb':memory_mb,'status':status,'standing':'inactive',
                  'reasons':reasons or ['provisional bootstrap; not capsule quality evidence' if _bootstrap else 'Protected host admission checks passed']}
        ref = self.store.put_record('library-admission', record)
        if status == 'admitted':
            with self.store.transaction() as db:
                prior = db.execute('SELECT declaration_ref FROM library_versions WHERE name=? AND version=?', (cc['cc_name'],cc['cc_version'])).fetchone()
                if prior and json.loads(prior['declaration_ref']) != declaration_ref:
                    raise ResearchError('identity_conflict', 'CC name/version already names different exact bytes')
                db.execute('INSERT OR IGNORE INTO library_versions VALUES(?,?,?,?,?,?,?,?)',
                    (cc['cc_name'],cc['cc_version'],json_bytes(declaration_ref).decode(),json_bytes(ref).decode(),
                     'active' if _bootstrap else 'inactive','live_plans',json_bytes(body_refs).decode(),'bootstrap' if _bootstrap else 'governed'))
        return ref

    def set_standing(self, name: str, version: str, to_standing: str, actor: Principal, *, reason: str, effect_scope='live_plans') -> Ref:
        actor.require('library_standing')
        if to_standing not in {'active','suspended','revoked'} or effect_scope not in {'live_plans','rsi_sandbox'} or not reason.strip():
            raise ResearchError('validation', 'Standing change needs a valid target, scope and reason')
        if to_standing=='active':
            current=self.store.connection.execute('SELECT admission_ref,declaration_ref FROM library_versions WHERE name=? AND version=?',(name,version)).fetchone()
            if current:
                admission=self.store.read_record(json.loads(current['admission_ref']))
                declaration_ref=json.loads(current['declaration_ref'])
                declaration=self.store.read_record(declaration_ref,contract_id='capsule-declaration')
                if admission['parent_ref'] is not None or declaration.get('identity',{}).get('lineage',{}).get('builder')=='rsi_workbench':
                    self._rsi_security_authorization(declaration_ref,'activate')
        with self.store.transaction() as db:
            row = db.execute('SELECT * FROM library_versions WHERE name=? AND version=?', (name,version)).fetchone()
            if not row or row['standing'] == 'revoked':
                raise ResearchError('standing_transition', 'Unknown or terminally revoked version')
            admission = self.store.read_record(json.loads(row['admission_ref']))
            if to_standing=='active':
                declaration_ref=json.loads(row['declaration_ref'])
                declaration=self.store.read_record(declaration_ref,contract_id='capsule-declaration')
                if admission['parent_ref'] is not None or declaration.get('identity',{}).get('lineage',{}).get('builder')=='rsi_workbench':
                    self._rsi_security_authorization(declaration_ref,'activate')
                self.store.require_product_material([json.loads(row['declaration_ref']),*json.loads(row['body_refs']).values()])
            allowed={'inactive':{'active','revoked'},'active':{'suspended','revoked'},'suspended':{'active','revoked'}}
            if to_standing not in allowed.get(row['standing'],set()):
                if not (row['standing']==to_standing=='active' and admission['parent_ref'] is not None and effect_scope!=row['effect_scope']):
                    raise ResearchError('standing_transition','Standing move is not in the source transition table')
            if admission['parent_ref'] is not None and to_standing=='active' and effect_scope=='live_plans' and row['standing']!='active':
                raise ResearchError('standing_transition','RSI child must first be active in its sandbox before live promotion')
            record = {'schema_version':'1.0.0','id':'activation:' + uuid.uuid4().hex,'actor':actor.account_id,'recorded_at':utc_now(),
                      'cc':admission['cc'],'admission_ref':json.loads(row['admission_ref']),'from_standing':row['standing'],
                      'to_standing':to_standing,'reason':reason,'effect_scope':effect_scope}
            # Blob first; metadata+standing publishes in this one transaction.
            validate('activation-record',record)
            raw = json_bytes(record); digest = self.store.blobs.put(raw); ref={'id':record['id'],'sha256':digest}
            db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)',(ref['id'],digest,'application/json',None,utc_now()))
            db.execute('INSERT INTO records VALUES(?,?,?,?,?,?)',(ref['id'],'activation-record',None,None,None,utc_now()))
            db.execute('UPDATE library_versions SET standing=?,effect_scope=? WHERE name=? AND version=?', (to_standing,effect_scope,name,version))
        return ref

    def entries(self) -> list[dict]:
        if self.development_mode:
            return [dict(self._development_entries[key]) for key in sorted(self._development_entries)]
        with self.store._lock:
            return [dict(r) for r in self.store.connection.execute('SELECT * FROM library_versions ORDER BY name,version')]

    def get(self, name: str, version: str) -> dict:
        rows = [r for r in self.entries() if (r['name'],r['version']) == (name,version)]
        if len(rows) != 1:
            raise ResearchError('library_membership','Unknown exact CC version')
        row = rows[0]
        for key in ('declaration_ref','admission_ref','body_refs'):
            row[key] = json.loads(row[key])
        return row

    def configure_verifier(self, pin: dict) -> None:
        """Bind the independently admitted checker explicitly, never by latest."""
        row=self.get(pin['cc_name'],pin['cc_version'])
        admission=self.store.read_record(row['admission_ref'],contract_id='library-admission')
        declaration=self.store.read_record(row['declaration_ref'],contract_id='capsule-declaration')
        if admission['status']!='admitted' or admission['cc']!=pin or pin['cc_name']!='research.verifier':
            raise ResearchError('verifier_binding','Verifier pin differs from its exact protected admission')
        per=declaration['budget']['per_call']
        if per['invocations']!=1 or not any(i['service_key']=='audited_model_bridge' for i in declaration['needs']['injects']):
            raise ResearchError('verifier_binding','M1 independently budgeted review requires one audited model call')
        self.eligible_association(row['declaration_ref'])
        self._verifier_pin=dict(pin)

    def _snapshot_verifier(self):
        if self._verifier_pin is None:
            raise ResearchError('verifier_binding','No exact independently admitted verifier pin was configured')
        row=self.get(self._verifier_pin['cc_name'],self._verifier_pin['cc_version'])
        admission=self.store.read_record(row['admission_ref'],contract_id='library-admission')
        if admission['status']!='admitted' or admission['cc']!=self._verifier_pin or row['standing']!='active' or row['effect_scope']!='live_plans':
            raise ResearchError('verifier_binding','Current selection requires the exact active protected verifier')
        declaration=self.store.read_record(row['declaration_ref'],contract_id='capsule-declaration')
        self.eligible_association(row['declaration_ref'])
        return row,admission,declaration

    def snapshot_budget_binding(self,snapshot_ref: Ref)->Ref:
        self.store.read_record(snapshot_ref,contract_id='library-snapshot')
        matches=[entry['ref'] for entry in self.store.iter_records(kinds=('library-budget-binding',))
                 if entry['record']['library_snapshot_ref']==snapshot_ref]
        if len(matches)!=1:raise ResearchError('verifier_binding','Snapshot has no unique protected aggregate-budget binding')
        return matches[0]

    def snapshot(self, *, candidate_pins=()) -> Ref:
        candidates = {(c['cc_name'],c['cc_version'],c['declaration_sha256']) for c in candidate_pins}
        entries = [];admission_refs=[];budget_entries=[]
        selected=[r for r in self.entries() if r['standing']=='active' and r['effect_scope']=='live_plans' or any(r['name']==c[0] and r['version']==c[1] for c in candidates)]
        verifier=self._snapshot_verifier() if selected else None
        fixed = {'intent.compiler','requirements.compiler','research.verifier','research.planner','workflow.paper_planner',
                 'workflow.capability_planner'}
        for raw in self.entries():
            row = self.get(raw['name'],raw['version'])
            admission = self.store.read_record(row['admission_ref'],contract_id='library-admission')
            cc=admission['cc']
            if row['standing']=='revoked' or not ((row['standing']=='active' and row['effect_scope']=='live_plans') or tuple(cc[k] for k in ('cc_name','cc_version','declaration_sha256')) in candidates):
                continue
            declaration=self.store.read_record(row['declaration_ref'],contract_id='capsule-declaration')
            admission_refs.append(row['admission_ref'])
            limits=declaration['budget']['per_call']; injects=declaration['needs']['injects']
            worker={'time_s':limits['wall_s'],'model_calls':limits['invocations'] if any(i['service_key']=='audited_model_bridge' for i in injects) else 0,'memory_mb':admission['memory_mb']}
            profile_ref=self.eligible_association(row['declaration_ref'])['profile_ref']
            profile=self.store.read_record(profile_ref,contract_id='checking-profile')
            output_count=0 if cc['cc_name']=='research.verifier' else len(declaration['ports']['outputs'])
            review={'time_s':min(verifier[2]['budget']['per_call']['wall_s'],profile['time_s']),'model_calls':1,'memory_mb':verifier[1]['memory_mb']}
            if profile['model_call_limit']!=1:raise ResearchError('verifier_binding','Subject profile must preserve exactly one review call per output')
            aggregate={'time_s':worker['time_s']+output_count*review['time_s'],
                       'model_calls':worker['model_calls']+output_count,
                       'memory_mb':max(worker['memory_mb'],review['memory_mb']) if output_count else worker['memory_mb']}
            budget_entries.append({'cc':cc,'worker_limits':worker,'verifier_limits':review,'output_ports':[p['name'] for p in declaration['ports']['outputs']] if output_count else [],
                                   'aggregate_limits':aggregate,'checking_profile_ref':profile_ref})
            entries.append(dict(cc,selectable_by_planner=cc['cc_name'] not in fixed,
                input_ports=[{k:p[k] for k in ('name','artifact_type','schema_ref','required')} for p in declaration['ports']['inputs']],
                output_ports=[{k:p[k] for k in ('name','artifact_type','schema_ref','required')} for p in declaration['ports']['outputs']],
                effect_class=declaration['changes']['effect_class'],network_mode=declaration['needs']['network']['mode'],
                resource_needs=[{'resource_key':r['resource_key'],'mode':r['mode'],'min_quantity':r.get('min_quantity')} for r in declaration['needs']['resources']],
                max_limits=aggregate,check_pins=admission['check_pins']))
        verifier_binding=None if verifier is None else {'cc':self._verifier_pin,'declaration_ref':verifier[0]['declaration_ref'],'admission_ref':verifier[0]['admission_ref']}
        key=hashlib.sha256(json_bytes({'entries':entries,'admission_refs':admission_refs,'candidate_pins':sorted(candidates),'verifier':verifier_binding,'budget_entries':budget_entries})).hexdigest()
        if self._snapshot_cache is not None and self._snapshot_cache[0]==key:
            self.store.read_blob(self._snapshot_cache[1]);return dict(self._snapshot_cache[1])
        record={'schema_version':'1.0.0','id':'library_' + uuid.uuid4().hex,'captured_at':datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),'entries':entries}
        ref=self.store.put_record('library-snapshot',record)
        self.store.append_record('library-budget-binding',{'id':'library-budget:'+uuid.uuid4().hex,'interface_revision':'M1-IF-002@r2',
            'library_snapshot_ref':ref,'verifier':verifier_binding,'entries':budget_entries,'captured_at':utc_now()})
        self._snapshot_cache=(key,ref)
        return dict(ref)

    def current_pins(self,*,candidate_pins=())->dict:
        ref=self.snapshot(candidate_pins=candidate_pins);snapshot=self.store.read_record(ref,contract_id='library-snapshot')
        pins=sorted({entry['check_pins']['check_bundle_sha256'] for entry in snapshot['entries'] if entry['check_pins'] is not None})
        return {'library_snapshot_ref':ref,'library_snapshot_sha256':ref['sha256'],
                'check_bundle_set_sha256':hashlib.sha256(''.join(digest+'\n' for digest in pins).encode('utf-8')).hexdigest()}

    def inspection_pins(self,*,candidate_pins=())->dict:
        """Observe current eligibility without granting missing prerequisites.

        A missing protected verifier/budget binding makes no work selectable.
        The explicit empty capture names that actual blocked state; it never
        changes admission, standing, a frozen snapshot or an accepted output.
        """
        try:return self.current_pins(candidate_pins=candidate_pins)
        except ResearchError as exc:
            rows=self.entries()
            reason=exc.code if rows else 'no_eligible_capsule'
            key=hashlib.sha256(json_bytes({'rows':rows,'candidate_pins':candidate_pins,'verifier_pin':self._verifier_pin,'reason':reason})).hexdigest()
            if self._inspection_cache is not None and self._inspection_cache[0]==key:return dict(self._inspection_cache[1])
            # The selectable LibrarySnapshot contract requires at least one
            # entry. An empty inspection state is an internal observation,
            # never a fabricated schema-valid selectable library snapshot.
            record={'id':'blocked-library:'+uuid.uuid4().hex,'interface_revision':'M1-IF-002@r2',
                'captured_at':utc_now(),'entries':[],'reason_code':reason,'membership_sha256':key}
            ref=self.store.append_record('library-eligibility-observation',record)
            pins={'library_snapshot_ref':ref,'library_snapshot_sha256':ref['sha256'],
                  'check_bundle_set_sha256':hashlib.sha256(json_bytes([])).hexdigest(),'unavailable_reason':reason}
            self._inspection_cache=(key,pins)
            return dict(pins)
