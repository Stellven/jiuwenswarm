"""Fail-closed checking eligibility; these fixtures are not calibration evidence."""

import pytest

from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.checks.assets import prepare_evidence_aware_release
from jiuwenswarm.research.state import SQLiteRunStore


def prepared(tmp_path, *, evidence=()):
    store = SQLiteRunStore(tmp_path)
    library = LibraryService(store)
    actor = Principal('independent-test-owner', operations=frozenset({'verifier_assets', 'library_admit'}))
    asset = build_research_assets(store)['screening']
    library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor,
                             evidence_refs=evidence)
    return store, library, actor, asset


@pytest.mark.asyncio
async def test_unknown_verifier_call_is_refused_before_private_completion_chronology(tmp_path,monkeypatch):
    """Untrusted assessment cannot turn an actual unknown call into calibration."""
    from jiuwenswarm.research.bridge import BridgeError,GovernedBridge
    from jiuwenswarm.research.gate import assemble_assessment
    from jiuwenswarm.research.state import json_bytes
    from tests.unit_tests.research.test_bridge import authorized_context

    store,library,actor,asset=prepared(tmp_path)
    profile,_=fixed_unit_profile(store,asset)
    profile_ref=store.put_blob(json_bytes(profile))
    registration=library.check_assets.register_profile(profile_ref,actor)
    case=next(case for case in profile['cases'] if case['asset_kind']=='criteria')
    pin=case['subject_ref'];checking=store.read_record(asset['profile_ref'])
    criteria=[row for row in checking['criteria'] if row['target_port'] in (None,case['output_port'])]
    plan=store.put_record('bound-check-plan',{'schema_version':'2.0.0','id':'plan:unknown-negative',
        'contract_ref':pin,'input_refs':[pin],'profile_ref':asset['profile_ref'],'policy_ref':pin,
        'mandatory_deterministic':['controlled_predicate'],'mandatory_semantic':[r['criterion_id'] for r in criteria],
        'runner_refs':[asset['bundle_ref']],'node_contract_ref':pin,'subnode_id':'reviewer'})
    review=store.put_record('review-context',{'schema_version':'2.0.0','id':'review:unknown-negative',
        'subject_ref':pin,'contract_ref':pin,'check_plan_ref':plan,'input_refs':[pin],'deterministic_result_ref':pin,
        'criteria':[r['criterion_id'] for r in criteria],'observations':[],'evidence_classes':[],
        'node_contract_ref':pin,'subnode_id':'reviewer'})
    # This deliberately supplied assessment is not an actual successful review
    # and must never be enough to overcome the failed runtime prerequisite.
    assessment=assemble_assessment({'findings':[{'criterion_id':r['criterion_id'],'outcome':'FAIL',
        'reason':'Controlled negative assessment'} for r in criteria],'uncertainties':[],'limitations':[],
        'required_correction':'Controlled incomplete subject'},criteria,case['declaration_ref'],pin,review)
    assessment_ref=store.append_record('verifier-assessment',assessment)
    context=authorized_context();context['call_function']='verifier'
    class LostReply:
        async def invoke_governed(self,*args,**kwargs):raise TimeoutError('controlled lost completion')
    bridge=GovernedBridge(persist=store.append_record,authorize=lambda _:context,revalidate=lambda _:context,
                          subscription_service=LostReply())
    try:
        with pytest.raises(BridgeError,match='timeout'):await bridge.call({},'controlled verifier input')
        calls=list(store.iter_records(kinds=('model-call',)))
        assert len(calls)==1 and calls[0]['record']['outcome']=='outcome_unknown' and calls[0]['record']['ended_at'] is None
        def forbidden_completion_lookup(*args):
            raise AssertionError('Unknown completion must be refused before private completed-call chronology')
        monkeypatch.setattr(library.check_assets,'_private_call_claim',forbidden_completion_lookup)
        with pytest.raises(ResearchError,match='calibration_attribution.*completed'):
            library.check_assets._outcomes(profile,case,{'result_ref':assessment_ref,'model_call_refs':[calls[0]['ref']]},registration)
        assert not list(store.iter_records(kinds=('check-asset-admission','library-admission','activation-record')))
    finally:store.close()


def test_catalog_preparation_needs_no_model_and_grants_no_eligibility(tmp_path):
    store = SQLiteRunStore(tmp_path)
    assets = build_research_assets(store)
    assert len(assets) == 7
    assert all(store.read_blob(asset['bundle_ref']) and store.read_blob(asset['profile_ref'])
               for asset in assets.values())
    assert LibraryService(store).entries() == []
    assert list(store.iter_records(kinds=('library-admission', 'model-call'))) == []


def test_evidence_aware_asset_is_a_distinct_opt_in_release(tmp_path):
    store = SQLiteRunStore(tmp_path)
    library = LibraryService(store)
    base = build_research_assets(store)['screening']
    profile = store.read_record(base['profile_ref'], contract_id='checking-profile')
    selected = next(row['criterion_id'] for row in profile['criteria']
                    if row['criterion_id'] not in {'declared_output_conformance','internal_consistency','limitations_consistency'})
    evidence = prepare_evidence_aware_release(store, base, version_label='example-2',
        evidence_criterion_ids=[selected], evidence_input_names=['brief'],
        reviewer_instructions='Use the selected original task source and Tier 1 scores only for the named criterion.',
        max_evidence_bytes=32768)
    assert evidence['declaration_ref'] != base['declaration_ref']
    assert evidence['profile_ref'] != base['profile_ref']
    assert evidence['bundle_ref'] != base['bundle_ref']
    old_label = store.read_record(base['declaration_ref'])['identity']['version_label']
    assert old_label != 'example-2'
    new_declaration = store.read_record(evidence['declaration_ref'], contract_id='capsule-declaration')
    new_profile = store.read_record(evidence['profile_ref'], contract_id='checking-profile')
    assert new_declaration['identity']['version_label'] == 'example-2'
    assert new_profile['version'] == '2.0.0' and new_profile['review_mode'] == 'task_sources_tier1_v1'
    assert new_profile['evidence_criterion_ids'] == [selected]
    assert new_profile['review_evidence_input_names'] == ['brief']
    # Legacy and evidence-aware pairs are independently admissible and exact.
    library._validate_association(base['declaration_ref'], base['bundle_ref'], base['profile_ref'])
    library._validate_association(evidence['declaration_ref'], evidence['bundle_ref'], evidence['profile_ref'])
    store.close()


@pytest.mark.asyncio
async def test_new_evidence_verifier_release_does_not_rewrite_frozen_release(tmp_path):
    from jiuwenswarm.research.compiler import register_compiler_capsules
    from jiuwenswarm.research.evidence_review import prepare_evidence_aware_verifier_release
    from tests.unit_tests.research.controlled_assets import ControlledLibraryService
    from jiuwenswarm.research.checks import CheckRegistry
    from jiuwenswarm.research.runner import Registry

    store = SQLiteRunStore(tmp_path)
    actor = Principal('operator', operations=frozenset({'verifier_assets','library_admit','library_standing'}))
    library = ControlledLibraryService(store)
    installed = await register_compiler_capsules(Registry(), CheckRegistry(), library, store, actor, activate=True)
    base = installed['verifier']
    new = prepare_evidence_aware_verifier_release(store, base, version_label='m1-3')
    old_decl = store.read_record(base['declaration_ref'], contract_id='capsule-declaration')
    new_decl = store.read_record(new['declaration_ref'], contract_id='capsule-declaration')
    assert old_decl['identity']['version_label'] == 'm1-2'
    assert new_decl['identity']['version_label'] == 'm1-3'
    assert base['body_refs'] != new['body_refs']
    assert new['body_refs']['research/evidence_review.py']['sha256'] == new_decl['identity']['carrier']['sha256']
    assert new['declaration'] == new_decl
    assert new['implementation_refs'] == tuple(new['body_refs'][body['path']]
                                                for body in new_decl['identity']['body'])
    assert store.read_record(base['profile_ref'])['target_cc_version_range'] == 'm1-2'
    assert store.read_record(new['profile_ref'])['target_cc_version_range'] == 'm1-3'
    library.associate_checks(new['declaration_ref'], new['bundle_ref'], new['profile_ref'], actor)
    admission_ref = await library.admit(new['declaration_ref'], new['body_refs'], actor, memory_mb=256)
    admission = store.read_record(admission_ref)
    assert admission['status'] == 'admitted', admission['reasons']
    pin = admission['cc']
    library.set_standing(pin['cc_name'], pin['cc_version'], 'active', actor,
                          reason='Explicit opt-in bounded evidence-aware verifier release')
    prepared = await register_compiler_capsules(None, None, None, store, None, prepare_only=True)
    prepared_verifier = dict(prepared['verifier'])
    prepared_verifier.update(new)
    prepared['verifier'] = [prepared['verifier'], prepared_verifier]
    installed_v3 = await register_compiler_capsules(Registry(), CheckRegistry(), library, store, actor,
        activate=True, prepared_assets=prepared)
    assert installed_v3['verifier']['pin'] == pin
    library.configure_verifier(pin)
    assert library.get('research.verifier', 'm1-3')['declaration_ref'] == new['declaration_ref']
    assert library.get('research.verifier', 'm1-2')['declaration_ref'] == base['declaration_ref']
    registry = Registry()
    store.close()


@pytest.mark.asyncio
async def test_prepared_exact_association_without_calibration_blocks_admission(tmp_path):
    store, library, actor, asset = prepared(tmp_path)
    association = library.association(asset['declaration_ref'])
    assert association['bundle_ref'] == asset['bundle_ref']
    assert association['profile_ref'] == asset['profile_ref']
    admission_ref = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=512)
    admission = store.read_record(admission_ref, contract_id='library-admission')
    assert admission['status'] == 'blocked'
    assert admission['standing'] == 'inactive'
    assert any('calibrat' in reason.lower() for reason in admission['reasons'])
    assert library.entries() == []
    assert list(store.iter_records(kinds=('model-call',))) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['check-asset-admission', 'calibration-results', 'model-call'])
async def test_caller_supplied_pass_record_is_not_protected_calibration(tmp_path, kind):
    store, library, actor, asset = prepared(tmp_path)
    forged = store.append_record(kind, {'id': 'forged:' + kind, 'outcome': 'PASS',
        'bundle_ref': asset['bundle_ref'], 'profile_ref': asset['profile_ref'],
        'challenge_classes': ['instruction_injection', 'omissions', 'unsupported_claims', 'ambiguity', 'scope_escape']})
    # The ordinary exact association may retain evidence, but its contents do
    # not manufacture a protected premeasurement profile or measured result.
    library.associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], actor,
                             evidence_refs=[forged])
    admission_ref = await library.admit(asset['declaration_ref'], asset['body_refs'], actor, memory_mb=512,
                                      evidence_refs=[forged])
    admission = store.read_record(admission_ref, contract_id='library-admission')
    assert admission['status'] == 'blocked'
    assert any('calibrat' in reason.lower() for reason in admission['reasons'])
    assert library.entries() == []


def test_capsule_author_cannot_prepare_independent_check_assets(tmp_path):
    store = SQLiteRunStore(tmp_path)
    asset = build_research_assets(store)['screening']
    author = Principal('capsule-author', operations=frozenset({'library_admit'}))
    with pytest.raises(ResearchError):
        LibraryService(store).associate_checks(asset['declaration_ref'], asset['bundle_ref'], asset['profile_ref'], author)


def fixed_unit_profile(store, asset):
    """Explicit negative-test labels, never an approved product calibration."""
    from jiuwenswarm.research.checks.assets import CHALLENGES
    runner = store.put_blob(b'controlled negative measurement adapter; no model authority')
    subject = store.put_blob(b'{"negative_unit_subject":true}')
    bundle = store.read_record(asset['bundle_ref'])
    profile = store.read_record(asset['profile_ref'])
    cases = []
    for kind, ids in [('bundle', [item['check_id'] for item in bundle['checks']]),
                      ('criteria', [item['criterion_id'] for item in profile['criteria']])]:
        expected = store.put_blob(__import__('json').dumps({key: 'FAIL' for key in ids}).encode())
        for challenge in sorted(CHALLENGES):
            cases.append({'case_id': kind + ':' + challenge, 'asset_kind': kind, 'challenge_class': challenge,
                'declaration_ref': asset['declaration_ref'], 'subject_ref': subject, 'expected_ref': expected,
                'output_port': 'screening_result'})
    value = {'schema': 'ai4r-check-calibration:1', 'id': 'unit-negative-profile', 'bundle_ref': asset['bundle_ref'],
        'profile_ref': asset['profile_ref'], 'measurement_runner_ref': runner, 'cases': cases}
    return value, runner


@pytest.mark.asyncio
async def test_measurement_producer_requires_preregistration_and_exact_installed_runner(tmp_path):
    from jiuwenswarm.research.state import json_bytes
    store, library, actor, asset = prepared(tmp_path)
    value, runner = fixed_unit_profile(store, asset)
    profile_ref = store.put_blob(json_bytes(value))
    with pytest.raises(ResearchError, match='calibration_unregistered'):
        await library.check_assets.measure(profile_ref, actor)
    registration = library.check_assets.register_profile(profile_ref, actor)
    assert library.check_assets.register_profile(profile_ref, actor) == registration
    with pytest.raises(ResearchError, match='calibration_runner_unavailable'):
        await library.check_assets.measure(profile_ref, actor)
    reports = library.check_assets.admit(profile_ref, actor)
    assert {store.read_record(ref)['status'] for ref in reports.values()} == {'blocked'}
    assert store.read_record(reports['bundle'])['asset_ref'] == asset['bundle_ref']
    assert store.read_record(reports['criteria'])['asset_ref'] == asset['profile_ref']
    with pytest.raises(ResearchError, match='check_asset_unqualified'):
        library.eligible_association(asset['declaration_ref'])
    changed = dict(value, id='changed-after-registration')
    with pytest.raises(ResearchError, match='calibration_unregistered'):
        await library.check_assets.measure(store.put_blob(json_bytes(changed)), actor)


@pytest.mark.asyncio
async def test_measurement_producer_rejects_booleans_retains_failures_and_does_not_replay(tmp_path):
    from jiuwenswarm.research.state import json_bytes
    store, library, actor, asset = prepared(tmp_path)
    value, runner = fixed_unit_profile(store, asset)
    profile_ref = store.put_blob(json_bytes(value))
    calls = []
    async def dishonest_adapter(case, closure, exact_profile):
        calls.append(case['case_id'])
        return {'passed': True}
    library.check_assets.register_runner(runner, dishonest_adapter)
    library.check_assets.register_profile(profile_ref, actor)
    first = await library.check_assets.measure(profile_ref, actor)
    assert len(first) == len(value['cases'])
    assert all(store.read_record(ref)['status'] == 'blocked' for ref in first)
    assert all(store.read_record(ref)['reason_code'] == 'calibration_attribution' for ref in first)
    assert await library.check_assets.measure(profile_ref, actor) == first
    assert len(calls) == len(value['cases'])
    admissions = library.check_assets.admit(profile_ref, actor)
    assert all(store.read_record(ref)['status'] == 'blocked' for ref in admissions.values())
    assert not list(store.iter_records(kinds=('model-call',)))
    with pytest.raises(ResearchError, match='check_asset_unqualified'):
        library.eligible_association(asset['declaration_ref'])


@pytest.mark.parametrize('fault', ['missing_class', 'foreign_criterion', 'duplicate_case'])
def test_fixed_profile_requires_independent_source_challenges_and_exact_labels(tmp_path, fault):
    from jiuwenswarm.research.state import json_bytes
    store, library, actor, asset = prepared(tmp_path)
    value, _ = fixed_unit_profile(store, asset)
    if fault == 'missing_class': value['cases'].pop()
    elif fault == 'duplicate_case': value['cases'].append(value['cases'][0])
    else: value['cases'][0]['expected_ref'] = store.put_blob(json_bytes({'candidate_chosen_check': 'PASS'}))
    with pytest.raises(ResearchError, match='calibration_profile'):
        library.check_assets.register_profile(store.put_blob(json_bytes(value)), actor)
