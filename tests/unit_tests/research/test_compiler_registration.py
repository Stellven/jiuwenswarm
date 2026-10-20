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
