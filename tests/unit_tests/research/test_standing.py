import pytest

from jiuwenswarm.research.checks import CheckRegistry
from jiuwenswarm.research.compiler import register_compiler_capsules
from jiuwenswarm.research.contracts import Principal,ResearchError
from tests.unit_tests.research.controlled_assets import ControlledLibraryService as LibraryService
from jiuwenswarm.research.runner import Registry
from jiuwenswarm.research.state import SQLiteRunStore


@pytest.mark.asyncio
async def test_exact_standing_moves_and_terminal_revocation(tmp_path):
    store=SQLiteRunStore(tmp_path);library=LibraryService(store)
    actor=Principal('operator',operations=frozenset({'verifier_assets','library_admit','library_standing'}))
    installed=await register_compiler_capsules(Registry(),CheckRegistry(),library,store,actor)
    pin=installed['planner']['pin'];name,version=pin['cc_name'],pin['cc_version']
    with pytest.raises(ResearchError,match='standing_transition'):library.set_standing(name,version,'suspended',actor,reason='invalid from inactive')
    library.set_standing(name,version,'active',actor,reason='explicit activation')
    with pytest.raises(ResearchError,match='standing_transition'):library.set_standing(name,version,'active',actor,reason='invalid unchanged standing')
    library.set_standing(name,version,'suspended',actor,reason='hold future starts')
    library.set_standing(name,version,'active',actor,reason='rollback to this admitted version')
    library.set_standing(name,version,'revoked',actor,reason='terminal revoke')
    with pytest.raises(ResearchError,match='standing_transition'):library.set_standing(name,version,'active',actor,reason='forbidden resurrection')
