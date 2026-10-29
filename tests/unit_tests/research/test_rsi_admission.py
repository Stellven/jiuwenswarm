from tests.unit_tests.research_rsi.qualification_fixtures import ControlledQualification
import base64
import json

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat

from jiuwenswarm.research.contracts.rsi import verify_signature,verify_package
from jiuwenswarm.research.contracts import ResearchError


def test_independent_signature_covers_key_id_and_every_original_semantic_field():
    private=Ed25519PrivateKey.generate();public=private.public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)
    record={'signer_key_id':'custodian:test','value':1}
    raw=json.dumps(record,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
    record['signature']=base64.urlsafe_b64encode(private.sign(raw)).decode().rstrip('=')
    verify_signature(record,public,'custodian:test')
    with pytest.raises(ResearchError):verify_signature(record|{'value':2},public,'custodian:test')
    with pytest.raises(ResearchError):verify_signature(record,public,'custodian:other')


def verify_unit(fixture,package=None):
    return verify_package(package or fixture['package'],fixture['store'],
        public_key=fixture['signer'].public_bytes(),key_id=fixture['signer'].key_id)


def test_v2_mean_package_keeps_earlier_finalist_and_later_rejected_attempt(tmp_path):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path)
    verified=verify_unit(fixture)
    assert verified['result']['statistics']['parent_passed']==20/3
    assert verified['result']['final_attempt_ref']!=verified['result']['attempt_refs'][-1]


@pytest.mark.parametrize('change', ['gain_direction','fraction_grid','rejected_final','genesis_revision','signature'])
def test_current_admission_independently_rejects_signed_v2_semantic_tampering(tmp_path,change):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    import copy
    fixture=make_unit_package(tmp_path);package=copy.deepcopy(fixture['package'])
    if change=='signature':
        result=copy.deepcopy(fixture['result']);result['queries_used']+=1
        package['session_result_ref']=fixture['put'](result)
    elif change=='genesis_revision':
        session=copy.deepcopy(fixture['session']);genesis=fixture['store'].read_record(session['chain_root_ref'])
        genesis['interface_revision']='M1-IF-009@r1';session['chain_root_ref']=fixture['put'](genesis)
        package['session_ref']=fixture['put'](session)
        result=copy.deepcopy(fixture['result']);result['session_ref']=package['session_ref']
        package['session_result_ref']=fixture['put'](fixture['signer'].sign(result))
    else:
        result=copy.deepcopy(fixture['result']);referee=copy.deepcopy(fixture['referee'])
        if change=='gain_direction':
            result['statistics']['gain_units']=9
        elif change=='fraction_grid':
            result['statistics']['parent_passed']=6.7;referee['pairs'][0]['parent_passed']=6.7
        else:
            result['final_attempt_ref']=result['attempt_refs'][-1]
            referee['attempt_ref']=result['final_attempt_ref']
        package['referee_evidence_ref']=fixture['put'](fixture['signer'].sign(referee))
        result['referee_evidence_ref']=package['referee_evidence_ref']
        package['session_result_ref']=fixture['put'](fixture['signer'].sign(result))
    expected={'signature':'rsi_signature','genesis_revision':'rsi_chain'}.get(change,'rsi_not_qualified')
    with pytest.raises(ResearchError,match=expected):verify_unit(fixture,package)


@pytest.mark.parametrize('version,expected',[('m1-1',True),('m1-1.child1',True),('m1-1.child2.more',True),('m1-1.',False),('m1-10',False),('m1-10.child',False),('foreign.child',False)])
def test_authored_screening_check_family_has_a_narrow_prefix(version,expected):
    from jiuwenswarm.research.library import version_matches
    assert version_matches(version,'m1-1.x') is expected


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',[None,'unrelated_version','changed_check_pins'])
async def test_independent_rsi_admission_inherits_exact_parent_checks_and_external_bytes_but_stays_inactive(tmp_path,fault):
    import copy
    import os
    from jiuwenswarm.research.capsules.assets import build_research_assets
    from jiuwenswarm.research.contracts import Principal
    from tests.unit_tests.research.controlled_assets import ControlledLibraryService as LibraryService
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path/'store');store=fixture['store'];inbox=tmp_path/'inbox';inbox.mkdir(mode=0o700)
    library=LibraryService(store,rsi_security_guard=ControlledQualification(),rsi_public_key=fixture['signer'].public_bytes(),rsi_key_id=fixture['signer'].key_id,
        rsi_inbox=inbox,rsi_custodian_uid=os.geteuid())
    asset=build_research_assets(store)['screening']
    owner=Principal('independent-owner',operations=frozenset({'verifier_assets','library_admit'}))
    library.associate_checks(asset['declaration_ref'],asset['bundle_ref'],asset['profile_ref'],owner)
    parent_ref=await library.admit(asset['declaration_ref'],asset['body_refs'],owner,memory_mb=512)
    assert store.read_record(parent_ref)['status']=='admitted'
    if fault=='unrelated_version':
        package=fixture['package'];child=store.read_record(package['child_declaration_ref'])
        child['identity']['version_label']='foreign.child';child_ref=fixture['put'](child)
        package['child_declaration_ref']=child_ref
        package['child']={'cc_name':child['identity']['name'],'cc_version':'foreign.child','declaration_sha256':child_ref['sha256']}
        provenance=store.read_record(package['provenance_ref']);provenance['declaration_ref']=child_ref
        package['provenance_ref']=fixture['put'](provenance)
        result=copy.deepcopy(fixture['result']);result['child']=package['child'];result['child_declaration_ref']=child_ref
        package['session_result_ref']=fixture['put'](fixture['signer'].sign(result))
    elif fault=='changed_check_pins':
        alternate=store.read_record(asset['bundle_ref']);alternate['version']='1.0.1'
        alternate_ref=fixture['put'](alternate)
        library.associate_checks(fixture['package']['child_declaration_ref'],alternate_ref,asset['profile_ref'],owner)
    package_path=inbox/'candidate.json';package_path.write_text(json.dumps(fixture['package']));package_path.chmod(0o600)
    operator=Principal('operator',operations=frozenset({'library_admit'}))
    captured=library.capture_rsi_inbox(package_path,operator,read_external=lambda ref:pytest.fail('All original unit refs are already captured'))
    admitted=await library.admit_rsi(captured,operator)
    result=store.read_record(admitted)
    if fault is not None:
        assert result['status'] in {'blocked','rejected'} and result['standing']=='inactive'
        assert ('check_compatibility' if fault=='unrelated_version' else 'rsi_check_pins') in result['reasons']
        assert not list(store.iter_records(kinds=('rsi-check-inheritance','activation-record')))
        with pytest.raises(ResearchError):library.get(fixture['package']['child']['cc_name'],fixture['package']['child']['cc_version'])
        return
    assert result['status']=='admitted',result['reasons']
    assert result['standing']=='inactive' and result['memory_mb']==512
    assert result['check_pins']==store.read_record(parent_ref)['check_pins']
    assert library.association(fixture['package']['child_declaration_ref'])['bundle_ref']==asset['bundle_ref']
    assert len(list(store.iter_records(kinds=('rsi-check-inheritance',))))==1
    assert not list(store.iter_records(kinds=('activation-record',)))


@pytest.mark.parametrize("parent_time,child_time,noise,qualified", [(10,9,0,True),(10,7,0.1,False)])
def test_independent_timing_qualification_uses_exact_decimal_boundaries(tmp_path,parent_time,child_time,noise,qualified):
    """Arithmetic controls, never measured RSI timing or calibration proof."""
    import copy
    from fractions import Fraction
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    fixture=make_unit_package(tmp_path);package=copy.deepcopy(fixture['package'])
    target=fixture['store'].read_record(package['target_profile_ref']);target['scoring']['calibrated_relative_noise']=noise
    package['target_profile_ref']=fixture['put'](target)
    session=copy.deepcopy(fixture['session']);session['target_profile_ref']=package['target_profile_ref']
    genesis=fixture['store'].read_record(session['chain_root_ref']);genesis['target_ref']=package['target_profile_ref'];session['chain_root_ref']=fixture['put'](genesis)
    package['session_ref']=fixture['put'](session)
    result=copy.deepcopy(fixture['result']);referee=copy.deepcopy(fixture['referee']);previous=None;attempts=[]
    for ref in result['attempt_refs']:
        attempt=fixture['store'].read_record(ref);attempt.update(target_ref=package['target_profile_ref'],chain_root_ref=session['chain_root_ref'],previous_ref=previous)
        current=fixture['put'](attempt)
        if ref==result['final_attempt_ref']:result['final_attempt_ref']=current
        previous=current;attempts.append(current)
    result.update(attempt_refs=attempts,session_ref=package['session_ref'],qualified_by='timing_tiebreak')
    referee.update(target_ref=package['target_profile_ref'],attempt_ref=result['final_attempt_ref'])
    # Retarget exact finalist provenance, including the child's signed lineage.
    child=fixture['store'].read_record(package['child_declaration_ref']);child['identity']['lineage']['builder_ref']=result['final_attempt_ref']
    package['child_declaration_ref']=fixture['put'](child);package['child']['declaration_sha256']=package['child_declaration_ref']['sha256']
    result.update(child=package['child'],child_declaration_ref=package['child_declaration_ref'])
    provenance=fixture['store'].read_record(package['provenance_ref']);provenance.update(builder_ref=result['final_attempt_ref'],declaration_ref=package['child_declaration_ref']);package['provenance_ref']=fixture['put'](provenance)
    for pair in referee['pairs']:
        pair.update(parent_passed=10,child_passed=10,gain_units=0,loss_units=0,parent_time_s=[parent_time]*7,child_time_s=[child_time]*7)
    relative=float(1-Fraction(str(child_time))/Fraction(str(parent_time)))
    result['statistics'].update(parent_passed=10,child_passed=10,gain_units=0,loss_units=0,pass_rate_gain=0,p_value=None,
        timing={'warmup_batches':5,'paired_rounds':7,'parent_median_s':parent_time,'child_median_s':child_time,'relative_gain':relative,
            'noise_multiplier':session['qualification']['noise_multiplier'],'calibrated_relative_noise':noise,'min_relative_gain':session['qualification']['min_timing_gain']})
    package['referee_evidence_ref']=fixture['put'](fixture['signer'].sign(referee));result['referee_evidence_ref']=package['referee_evidence_ref']
    package['session_result_ref']=fixture['put'](fixture['signer'].sign(result))
    if qualified:verify_unit(fixture,package)
    else:
        with pytest.raises(ResearchError,match='rsi_not_qualified'):verify_unit(fixture,package)
