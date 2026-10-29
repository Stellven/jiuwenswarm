"""Literal conditional Screening text job assembly; no arbitrary factories."""
from __future__ import annotations
import copy,hashlib,json,time,uuid
from pathlib import Path
from .records import encoded
from .fixed_resources import closed,owned_directory
from .text_evaluation import child_subject


async def assemble_text_job(job,*,resources,store,binding,custody,custody_requests,native_lease,publication,trial_runtime,principal,recovery=False,qualification=None):
    from jiuwenswarm.research.contracts import validate
    from jiuwenswarm.research.admitted_measurement import AdmittedMeasurementResources
    from .profiles import Limits,freeze_profile
    from .opportunity import decide
    from .assessment import GuardedAssessment
    from .proposer import GuardedProposer
    from .fixed_resources import CoreProposer
    from .controller import Controller
    from .custodian_client import CustodianClient
    from .mutation import child_declaration
    from .text_checks import TextParentTests
    if not recovery:
        from .qualification import require_qualification
        require_qualification(qualification,'session_start',session_ref=job['session_ref'],worker_profile_ref=job['worker_profile_ref'])
    if trial_runtime is None or not getattr(trial_runtime,'parent_bindings',None):raise ValueError('Actual child and original-parent private ports are unavailable')
    session=store.get(job['session_ref']);validate('rsi-session',session);limits=Limits.from_mapping(session['limits'])
    if session['started_by']!=principal.account_id or session['pass_count_repeats']!=3:raise ValueError('Frozen text actor/repeat differs')
    if len(job['proposer_contract_refs'])!=limits.max_attempts:raise ValueError('Exact bounded proposer contract list is absent')
    target=store.get(session['target_profile_ref']);parent=store.get(session['parent_declaration_ref']);freeze_profile(target,parent,validate)
    if parent['identity']['name']!='research.screening':raise ValueError('Unknown installed finite text carrier')
    profile=store.get(job['worker_profile_ref'])
    required={'session_ref','target_ref','parent_admission_ref','parent_contract_ref','parent_check_plan_ref',
        'model_selection_profile_ref','deployment_ref','check_bundle_ref','checking_profile_ref','limits'}
    version=2 if profile.get('schema')=='ai4r-rsi-screening-text-profile:2' else 1
    closed(profile,required,'ai4r-rsi-screening-text-profile:'+str(version))
    if target['mutable_paths'][0] not in {'screening_prompt.txt','screening_rubric.json'} or version==1 and target['mutable_paths'][0]!='screening_prompt.txt':
        raise ValueError('Frozen text target/version does not authorize this body')
    if profile['session_ref']!=job['session_ref'] or profile['target_ref']!=session['target_profile_ref']:raise ValueError('Text resource profile differs')
    matches=[p for p in trial_runtime.parent_bindings if p['session_ref']==job['session_ref']]
    if len(matches)!=1 or any(profile[k]!=matches[0][k] for k in ('parent_contract_ref','parent_check_plan_ref')):raise ValueError('Original-parent binding is not protected')
    original=AdmittedMeasurementResources(resources)._validate(profile['parent_contract_ref'],profile['parent_check_plan_ref'])[0]
    if original['bindings'][0]['declaration_ref']!=session['parent_declaration_ref'] or original['bindings'][0]['admission_ref']!=profile['parent_admission_ref']:
        raise ValueError('Actual admitted immutable original parent differs')
    if any(profile['limits'][k]>target['limits'][k] for k in profile['limits']):raise ValueError('Text limits widen the target')
    entry=resources.composition.library.get(session['parent']['cc_name'],session['parent']['cc_version'])
    if entry['declaration_ref']!=session['parent_declaration_ref']:raise ValueError('Selected parent version differs')
    opportunity=store.get(job['opportunity_ref']);closed(opportunity,{'attribution','symptom_reproduced','mandatory_passed','headroom','headroom_minimum','diagnosis','resource_ready','evidence_refs','parent_visible_time_s'},'ai4r-rsi-opportunity:1')
    if not opportunity['evidence_refs']:raise ValueError('No measured implementation opportunity')
    for ref in opportunity['evidence_refs']:store.read(ref)
    decision=decide(**{k:opportunity[k] for k in ('attribution','symptom_reproduced','mandatory_passed','headroom','headroom_minimum','diagnosis','resource_ready')})
    if decision['decision']!='START':raise ValueError('The actual text target has no qualified measured headroom')
    decision['parent_visible_time_s']=opportunity['parent_visible_time_s']
    visible=store.get(job['visible_context_ref'])
    if set(visible)!={'context','mandatory_fixtures','required_test_refs'} or visible['required_test_refs']!=target['required_test_refs']:
        raise ValueError('Frozen visible tests differ')
    parent_directory=owned_directory(binding['parent_directory'],12001)
    expected={p:ref['sha256'] for p,ref in entry['body_refs'].items()}
    actual={p.relative_to(parent_directory).as_posix():p for p in parent_directory.rglob('*') if p.is_file() or p.is_symlink()}
    if set(actual)!=set(expected) or any(p.is_symlink() or p.stat().st_nlink!=1 or hashlib.sha256(p.read_bytes()).hexdigest()!=expected[name] for name,p in actual.items()):
        raise ValueError('Text parent sandbox closure differs')
    for ref in [job['session_ref'],session['target_profile_ref'],session['parent_declaration_ref'],session['chain_root_ref'],session['hash_profile_ref'],
            profile['parent_contract_ref'],profile['parent_check_plan_ref'],profile['parent_admission_ref'],*entry['body_refs'].values(),*target['required_test_refs']]:
        publication.put_ref(ref,store.read(ref))
    context={'session_ref':job['session_ref'],'target_ref':session['target_profile_ref'],'configuration_ref':session['configuration_ref']}
    subjects={}
    async def declaration(snapshot,child,diff):
        hashes={p['path']:p['sha256'] for p in parent['identity']['body']};hashes[target['mutable_paths'][0]]=child['sha256']
        starts=store.proposer_starts(session['session_id'])
        value=child_declaration(parent,body_hashes=hashes,version_label=parent['identity']['version_label']+'.'+uuid.uuid4().hex[:8],
            carrier=parent['identity']['carrier'],lineage={'parent':session['parent_declaration_ref'],'co_parents':[],'relation':'supersedes',
            'builder':'rsi_workbench','build_trigger':session['session_id'],'context_capsules':[],'diagnosis_inputs':opportunity['evidence_refs'],
            'builder_ref':starts[-1],'provenance':{'generating_model':None,'prompt_ref':session['improver_ref'],'trajectory_ref':starts[-1]}},validate=validate)
        return value,{'cc_name':value['identity']['name'],'cc_version':value['identity']['version_label'],'declaration_sha256':store.put(value)['sha256']}
    async def mandatory(snapshot,declaration):
        started=time.monotonic();body_refs={row['path']:entry['body_refs'][row['path']] for row in parent['identity']['body']}
        body_refs[target['mutable_paths'][0]]=store.put_bytes((Path(snapshot['path'])/target['mutable_paths'][0]).read_bytes())
        child_ref=store.put(declaration)
        for ref in [child_ref,*body_refs.values()]:resources.store.put_blob(store.read(ref),record_id=ref['id'])
        test_binding=resources.store.append_record('isolated-text-test-subject',{'id':'visible-text:'+uuid.uuid4().hex,
            'parent_declaration_ref':session['parent_declaration_ref'],'child_declaration_ref':child_ref,
            'child_body_refs':body_refs,'configuration_ref':session['configuration_ref']})
        receipts=await TextParentTests(resources.store).run(test_binding,target['required_test_refs'])
        passed=bool(receipts) and all(resources.store.read_record(ref)['outcome']=='PASS' for ref in receipts)
        if passed:
            subject=child_subject(store,parent,declaration,target,context,parent_declaration_ref=session['parent_declaration_ref'],
                child_declaration_ref=child_ref,body_refs=body_refs,dependency_refs=original['bindings'][0]['dependency_refs'])
            subjects[encoded(subject['candidate_ref'])]=subject;store.put(subject)
        for ref in receipts:
            publication.put_ref(ref,resources.store.read_blob(ref))
        return {'passed':passed,'evidence_refs':receipts,'visible_selection_time_s':time.monotonic()-started}
    client=CustodianClient(custody_requests,socket_path=custody['socket_path'],peer_uid=custody['peer_uid'],session_id=session['session_id'],timeout=limits.wall_s)
    proposer=GuardedProposer(CoreProposer(resources,job['proposer_contract_refs'],store,native_lease=native_lease,session_id=session['session_id'],qualification=qualification,session_ref=job['session_ref']),
        configuration_ref=session['configuration_ref'],improver_ref=session['improver_ref'],limits=limits,store=store)
    assess=GuardedAssessment(parent_directory=parent_directory,target=target,store=store,work_root=binding['work_root'],run_mandatory=mandatory,make_declaration=declaration)
    async def contain(sid):
        if sid!=session['session_id']:raise ValueError('Containment session differs')
        try:await client.halt(sid)
        finally:
            owner=getattr(trial_runtime,'contain_session',None)
            if owner is None:raise ValueError('Actual text containment owner is unavailable')
            proof=await owner(sid)
        return proof
    controller=Controller(store=store,ledger=client,oracle=client,proposer=proposer,assess=assess,signer=client,validate=validate,recovery_containment=contain,qualification=qualification)
    async def final(best):
        value=store.get(best['child_declaration_ref']);value['identity']['lineage']['builder_ref']=best['attempt_ref'];value['identity']['lineage']['provenance']['trajectory_ref']=best['attempt_ref']
        validate('capsule-declaration',value);best['child_declaration_ref']=store.put(value);best['child']={**best['child'],'declaration_sha256':best['child_declaration_ref']['sha256']}
        subject=dict(subjects[encoded(best['child_ref'])],id='text-subject:'+uuid.uuid4().hex,child_declaration_ref=best['child_declaration_ref'],attempt_ref=best['attempt_ref']);store.put(subject)
        decision,ref=await client.final({'attempt_ref':best['attempt_ref'],'target_ref':session['target_profile_ref'],'parent_ref':target['parent_ref'],
            'child_ref':best['child_ref'],'configuration_ref':session['configuration_ref'],'repeats':session['pass_count_repeats'],
            'qualification':session['qualification'],'mandatory_passed':True,'integrity_passed':True})
        if store.put(custody_requests.get(ref))!=ref:raise ValueError('Signed final aggregate transfer differs')
        return decision,ref
    return controller,{'session':session,'session_ref':job['session_ref'],'opportunity':decision,'fixture_identity':job['fixture_identity'],
        'visible_context':visible['context'],'parent_body_ref':target['parent_ref'],'finalize':final}


def resolve_text_subject(public,candidate,session_ref,target_ref,target,comparison=None):
    """Scan only the bounded controller-public publication, never hidden roots."""
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    matches=[]
    for root in public.roots:
        if not (root/'original-byte-index.json').exists():continue
        index=OriginalBytes(root).index()
        for ident,digest in index.items():
            ref={'id':ident,'sha256':digest}
            try:value=json.loads(public.read(ref))
            except (ValueError,UnicodeError):continue
            if not isinstance(value,dict) or value.get('schema')!='ai4r-rsi-text-subject:1':continue
            fields={'schema','id','session_ref','target_ref','configuration_ref','parent_declaration_ref','child_declaration_ref','candidate_ref','child_body_refs','dependency_refs','attempt_ref'}
            if set(value)!=fields:raise ValueError('Unknown published text subject')
            if value['session_ref']!=session_ref or value['candidate_ref']!=candidate:continue
            if comparison is None and value['attempt_ref'] is not None:continue
            if comparison is not None and value['attempt_ref']!=comparison['attempt_ref']:continue
            if value['target_ref']!=target_ref or value['parent_declaration_ref']!=target['parent_declaration_ref'] or value['configuration_ref']!=target['configuration_ref']:
                raise ValueError('Published child subject differs from the frozen target')
            if encoded(value) not in {encoded(v) for v in matches}:matches.append(value)
    if len(matches)!=1:raise ValueError('One exact published changed child subject is required')
    return matches[0]


def assemble_text_custody(*,profile_ref,session_ref,session,target,manifest,store,public,ledger,signer,input_root,custody_root):
    from .fixed_resources import shared_directory
    from .trial_port import TrialReservationIssuer
    from .text_trial import TextTrialClient,ParentMeasurementClient
    from .text_evaluation import TextFixtureEvaluator
    from jiuwenswarm.research_records.original_bytes import OriginalBytes
    if input_root!='/var/lib/ai4r-rsi-trial-inputs':raise ValueError('Unknown private legitimate-input publication')
    shared=OriginalBytes(shared_directory(input_root,12002),writable=True)
    capture_root=Path(custody_root)/'text-captures';capture_root.mkdir(mode=0o700,exist_ok=True)
    capture=OriginalBytes(capture_root,writable=True)
    profile=store.get(profile_ref)
    if profile['session_ref']!=session_ref or profile['target_ref']!=manifest['target_ref']:raise ValueError('Frozen text custody profile differs')
    # Only exact frozen development inputs authorize uncharged visible checks.
    development=[]
    version=2 if profile.get('schema')=='ai4r-rsi-screening-text-profile:2' else 1
    for row in manifest['partitions']['development']:
        value=store.get(row['input_ref'])
        if set(value)!={'schema','inputs'} or value['schema']!='ai4r-rsi-legitimate-inputs:'+str(version):raise ValueError('Unknown explicit visible input version')
        development.append(hashlib.sha256(encoded(value['inputs'])).hexdigest())
    issuer=TrialReservationIssuer(ledger,store,signer,approved_sessions=[session_ref],development_input_hashes=development)
    child=TextTrialClient(store,allowed_session_refs=[session_ref],capture=capture)
    parent=ParentMeasurementClient(store,allowed_session_refs=[session_ref],capture=capture)
    def subjects(candidate,comparison):return resolve_text_subject(public,candidate,session_ref,manifest['target_ref'],target,comparison)
    evaluator=TextFixtureEvaluator(manifest=manifest,store=store,session_ref=session_ref,target=target,repeats=session['pass_count_repeats'],
        profile=profile,child_client=child,parent_client=parent,issuer=issuer,publication=shared,subjects=subjects,ledger=ledger)
    # Only public original context and implementation bytes are initially shared;
    # legitimate fixture bytes are added per already charged measurement.
    for pin in [session_ref,manifest['target_ref'],target['parent_declaration_ref'],profile['parent_admission_ref'],profile['parent_contract_ref'],profile['parent_check_plan_ref'],
            session['configuration_ref'],profile['model_selection_profile_ref'],profile['deployment_ref'],profile['check_bundle_ref'],profile['checking_profile_ref']]:
        shared.put_ref(pin,store.read(pin))
    return evaluator
