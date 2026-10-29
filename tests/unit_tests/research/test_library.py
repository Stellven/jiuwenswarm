import asyncio
import copy
import json
from pathlib import Path

import pytest

from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.library import LibraryService
from jiuwenswarm.research.state import SQLiteRunStore


def test_author_guarantees_cannot_supply_independent_check_association(tmp_path):
    store = SQLiteRunStore(tmp_path)
    source = Path('tests/fixtures/research/compiler/capsule_declaration.json')
    declaration = json.loads(source.read_text('utf-8'))
    ref = store.put_blob(source.read_bytes())
    library = LibraryService(store)
    actor = Principal('owner', operations=frozenset({'library_admit'}))
    result = asyncio.run(library.admit(ref, {}, actor, memory_mb=256))
    record = store.read_record(result)
    assert record['status'] == 'blocked' and record['standing'] == 'inactive'
    assert any('association' in reason for reason in record['reasons'])
    assert library.entries() == []


def test_bootstrap_is_exact_bounded_and_never_general_fallback(tmp_path):
    store = SQLiteRunStore(tmp_path)
    library = LibraryService(store)
    actor = Principal('owner', operations=frozenset({'library_admit'}))
    with pytest.raises(ResearchError, match='bootstrap_not_allowed'):
        asyncio.run(library.bootstrap({'id':'x','sha256':'a'*64}, {}, actor, memory_mb=256))


def test_readable_declaration_view_is_exact_and_grants_no_standing(tmp_path):
    import json
    from jiuwenswarm.research.state import SQLiteRunStore
    from jiuwenswarm.research.library import LibraryService
    from jiuwenswarm.research.capsules.assets import build_research_assets
    store=SQLiteRunStore(tmp_path);library=LibraryService(store)
    ref=build_research_assets(store)['screening']['declaration_ref']
    view=library.render_declaration(ref)
    text=store.read_blob(view).decode('utf-8')
    assert ref['sha256'] in text and 'research.screening' in text
    for key in store.read_record(ref):assert '## '+key in text
    assert library.render_declaration(ref)==view
    assert not library.entries() and not list(store.iter_records(kinds=('activation-record','library-admission')))
