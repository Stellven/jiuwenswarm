"""Finite human operator mechanics; controlled assets are not qualification."""
import copy
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.contracts import Principal,ResearchError
from jiuwenswarm.research.state import json_bytes
from tests.unit_tests.research.test_isolated_evaluation import trial_fixture


def test_operator_entry_refuses_runtime_uid_before_state_access(monkeypatch):
    from jiuwenswarm.research import library_operator
    monkeypatch.setenv('JIUWENSWARM_M1_PROFILE','1')
    monkeypatch.setattr(library_operator.os,'geteuid',lambda:10001)
    with pytest.raises(ResearchError,match='operator_identity'):
        library_operator.operator_identity()


async def operator_fixture(root):
    from jiuwenswarm.research.library_operator import OperatorLibrary
    store,private,fixture,binding=await trial_fixture(root)
    library=private.resources.composition.library;installed=private.resources.composition.installed
    policy=store.put_record('plan-policy',{'schema_version':'1.0.0','id':'operator-unit-policy','max_nodes':12,
        'allowed_effect_classes':['pure','read'],'allow_network':False,'required_stages':[],
        'aggregate_limits':{'time_s':3000,'model_calls':60,'memory_mb':512},'max_attempts_per_node':1})
    settings={'cc':{'plan_policy_ref':policy}}
    config=store.put_blob(json_bytes(settings));actor=Principal('os:0:root',operations=frozenset({'library_admit','library_standing','verifier_assets'}))
    owner=OperatorLibrary(store,library,SimpleNamespace(snapshot=lambda:copy.deepcopy(settings)),{'configuration_ref':config},actor)
    return store,owner,library,installed


def screening_parent(store,library,installed):
    # The installed Screening release moves with the release table; resolve it, do not hard-code it.
    label=store.read_record(installed['screening']['declaration_ref'])['identity']['version_label']
    return library.get('research.screening',label)


@pytest.mark.asyncio
async def test_operator_admission_is_inactive_and_standing_is_an_independent_action(tmp_path):
    store,owner,library,installed=await operator_fixture(tmp_path)
    parent=screening_parent(store,library,installed);declaration=store.read_record(parent['declaration_ref'])
    unit=parent['version']+'.operator-unit';declaration['identity']['version_label']=unit;child=store.put_blob(json_bytes(declaration))
    association=library.association(parent['declaration_ref'])
    associate=store.put_blob(json_bytes({'schema':'ai4r-library-action:1','id':'associate-unit','declaration_ref':child,
        'bundle_ref':association['bundle_ref'],'profile_ref':association['profile_ref'],'evidence_refs':[]}))
    await owner.execute('associate-checks',associate)
    action=store.put_blob(json_bytes({'schema':'ai4r-library-action:1','id':'admit-unit','declaration_ref':child,
        'body_refs':parent['body_refs'],'memory_mb':512,'evidence_refs':[]}))
    before=[r['ref'] for r in store.iter_records(kinds=('activation-record',))]
    receipt=await owner.execute('admit',action)
    assert receipt['status']=='admitted' and receipt['admission_ref']
    assert library.get('research.screening',unit)['standing']=='inactive'
    assert [r['ref'] for r in store.iter_records(kinds=('activation-record',))]==before
    assert await owner.execute('admit',action)==receipt
    assert len([r for r in store.iter_records(kinds=('library-admission',)) if r['record']['candidate_ref']==child])==1
    move=store.put_blob(json_bytes({'schema':'ai4r-library-action:1','id':'standing-unit','name':'research.screening',
        'version':unit,'to_standing':'active','effect_scope':'rsi_sandbox','reason':'Explicit controlled operator action'}))
    moved=await owner.execute('standing',move)
    assert moved['status']=='completed' and library.get('research.screening',unit)['effect_scope']=='rsi_sandbox'


@pytest.mark.asyncio
@pytest.mark.parametrize('fault',['unknown_field','memory','configuration','permission'])
async def test_operator_request_cannot_widen_or_replace_protected_authority(tmp_path,fault):
    store,owner,library,installed=await operator_fixture(tmp_path)
    parent=screening_parent(store,library,installed)
    action={'schema':'ai4r-library-action:1','id':'negative','declaration_ref':parent['declaration_ref'],
        'body_refs':parent['body_refs'],'memory_mb':512,'evidence_refs':[]}
    if fault=='unknown_field':action['callback']='candidate.module'
    elif fault=='memory':action['memory_mb']=513
    elif fault=='configuration':owner.bindings['configuration_ref']=store.put_blob(b'{}')
    else:owner.actor=Principal('unprivileged')
    before=len(list(store.iter_records(kinds=('library-admission','activation-record'))))
    with pytest.raises(ResearchError):await owner.execute('admit',store.put_blob(json_bytes(action)))
    assert len(list(store.iter_records(kinds=('library-admission','activation-record'))))==before


@pytest.mark.asyncio
async def test_operator_cannot_turn_missing_check_qualification_into_admission(tmp_path):
    from jiuwenswarm.research.library import LibraryService
    store,owner,library,installed=await operator_fixture(tmp_path)
    parent=screening_parent(store,library,installed)
    owner.library=LibraryService(store)
    action=store.put_blob(json_bytes({'schema':'ai4r-library-action:1','id':'unqualified','declaration_ref':parent['declaration_ref'],
        'body_refs':parent['body_refs'],'memory_mb':512,'evidence_refs':[]}))
    before=[r['ref'] for r in store.iter_records(kinds=('activation-record',))]
    result=await owner.execute('admit',action)
    assert result['status']=='blocked' and store.read_record(result['admission_ref'])['standing']=='inactive'
    assert [r['ref'] for r in store.iter_records(kinds=('activation-record',))]==before
