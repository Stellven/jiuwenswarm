import pytest

from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.contracts import Principal
from tests.unit_tests.research.controlled_assets import ControlledLibraryService as LibraryService
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.asyncio
async def test_frozen_research_assets_match_independent_associations_and_host_admission(tmp_path):
    store=SQLiteRunStore(tmp_path);library=LibraryService(store)
    actor=Principal('operator',operations=frozenset({'verifier_assets','library_admit'}))
    assets=build_research_assets(store)
    for stage,asset in assets.items():
        library.associate_checks(asset['declaration_ref'],asset['bundle_ref'],asset['profile_ref'],actor)
        ref=await library.admit(asset['declaration_ref'],asset['body_refs'],actor,memory_mb=32768)
        record=store.read_record(ref)
        assert record['status']=='admitted',(stage,record['reasons'])
        assert record['standing']=='inactive'
