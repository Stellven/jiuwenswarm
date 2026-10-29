import pytest

from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.compiler import register_compiler_capsules
from jiuwenswarm.research.contracts import Principal
from tests.unit_tests.research.controlled_assets import ControlledLibraryService as LibraryService
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.asyncio
async def test_source_bound_installed_catalog_has_actual_carrier_and_independent_assets(tmp_path):
    store=SQLiteRunStore(tmp_path);registry=Registry();checks=CheckRegistry();library=LibraryService(store)
    operator=Principal('operator',operations=frozenset({'verifier_assets','library_admit','library_standing'}))
    installed=await register_compiler_capsules(registry,checks,library,store,operator,activate=True)
    assert set(installed)=={'intent','requirements','verifier','planner'}
    for stage,item in installed.items():
        assert store.read_record(item['admission_ref'])['status']=='admitted'
        for ref in item['body_refs'].values():assert store.read_blob(ref)
    snapshot=store.read_record(library.snapshot())
    assert len(snapshot['entries'])==4 and all(not e['selectable_by_planner'] for e in snapshot['entries'])
    first=library.snapshot();assert library.snapshot()==first
    before=[record['ref'] for record in store.iter_records(kinds=('library-admission','activation-record'))]
    # A second explicit command has a fresh in-process dispatch registry while
    # retaining the same protected admissions and standing in durable storage.
    repeated=await register_compiler_capsules(Registry(),CheckRegistry(),library,store,operator,activate=True)
    assert {key:value['admission_ref'] for key,value in repeated.items()}=={key:value['admission_ref'] for key,value in installed.items()}
    assert [record['ref'] for record in store.iter_records(kinds=('library-admission','activation-record'))]==before
    pins=library.current_pins();assert pins['library_snapshot_ref']==first
    target=installed['planner']['pin'];library.set_standing(target['cc_name'],target['cc_version'],'suspended',operator,reason='Controlled standing boundary test')
    changed=library.snapshot();assert changed!=first
    assert len(store.read_record(changed)['entries'])==3
    # An existing frozen capture retains the original exact four entries.
    assert len(store.read_record(first)['entries'])==4


@pytest.mark.asyncio
async def test_retired_optional_planner_remains_admitted_but_is_not_selectable(tmp_path):
    store=SQLiteRunStore(tmp_path);library=LibraryService(store);checks=CheckRegistry();registry=Registry()
    actor=Principal('operator',operations=frozenset({'verifier_assets','library_admit','library_standing'}))
    try:
        installed=await register_compiler_capsules(registry,checks,library,store,actor,activate=True)
        frozen=library.snapshot()
        frozen_value=store.read_record(frozen,contract_id='library-snapshot')

        # Reuse a fully qualified/admitted Planner release with a legacy optional
        # name to model a persisted Library row without carrying its retired worker.
        source=installed['planner']
        version=store.read_record(source['declaration_ref'])['identity']['version_label']
        declaration=store.read_record(source['declaration_ref'])
        declaration['identity']['name']='workflow.capability_planner'
        declaration_ref=store.put_record('capsule-declaration',declaration)
        bundle=store.read_record(source['bundle_ref']);bundle['bundle_id']='workflow.capability_planner.checks';bundle['target_cc_name']='workflow.capability_planner';bundle['target_cc_version_range']=version
        bundle_ref=store.put_record('check-bundle',bundle)
        profile=store.read_record(source['profile_ref']);profile['profile_id']='workflow.capability_planner.profile';profile['target_cc_name']='workflow.capability_planner';profile['target_cc_version_range']=version
        profile_ref=store.put_record('checking-profile',profile)

        library.associate_checks(declaration_ref,bundle_ref,profile_ref,actor)
        admission_ref=await library.admit(declaration_ref,source['body_refs'],actor,memory_mb=4096)
        admission=store.read_record(admission_ref)
        assert admission['status']=='admitted', admission['reasons']
        pin=admission['cc']
        library.set_standing(pin['cc_name'],pin['cc_version'],'active',actor,reason='Legacy compatibility fixture')

        current=library.snapshot()
        snapshot=store.read_record(current,contract_id='library-snapshot')
        legacy=next(entry for entry in snapshot['entries'] if entry['cc_name']=='workflow.capability_planner')

        assert legacy['selectable_by_planner'] is False
        assert library.get('workflow.capability_planner',pin['cc_version'])['standing']=='active'
        assert store.read_record(frozen,contract_id='library-snapshot')==frozen_value
    finally:
        store.close()
