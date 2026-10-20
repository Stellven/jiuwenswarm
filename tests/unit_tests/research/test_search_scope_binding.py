"""Binder scope construction from explicit protected bounds; no live retrieval."""
import copy
from types import SimpleNamespace
import pytest
from jiuwenswarm.research.binding import Binder
from jiuwenswarm.research.capsules.assets import build_research_assets
from jiuwenswarm.research.state import SQLiteRunStore
from jiuwenswarm.research.contracts import ResearchError


def scope_fixture(tmp_path,**bounds):
    store=SQLiteRunStore(tmp_path);asset=build_research_assets(store)['search'];decl=store.read_record(asset['declaration_ref'])
    pin={'cc_name':decl['identity']['name'],'cc_version':decl['identity']['version_label'],'declaration_sha256':asset['declaration_ref']['sha256']}
    # Explicit test-only catalog lookup, not admission/qualification evidence.
    library=SimpleNamespace(get=lambda name,version:{'declaration_ref':asset['declaration_ref']})
    policy={'schema':'ai4r-search-bounds:1','id':'configured-bounds','connectors':['local_documents'],'max_queries':2,'max_hits_per_query':3}|bounds
    bound=store.append_record('search-bounds',policy)
    binder=Binder(store,library,None,search_bounds_ref=bound)
    source={'nodes':[{'cc':pin}],'topic_hints':['valid planned hint']}
    document=store.put_blob(b'exact extracted local document',media_type='text/plain')
    resources={'resources':[{'resource_key':'local_document_buffer','kind':'file','available':True,'quantity':None,'ref':document}]}
    brief=store.put_blob(b'accepted brief component identity')
    authority={'network':'none','network_allowlist':[],'resource_reads':[document],'write_roots':[],'tools':['deepsearch']}
    return store,binder,source,brief,resources,authority,document


def test_scope_is_new_brief_bound_and_static_has_no_queries_or_planner_hints(tmp_path):
    store,binder,source,brief,resources,authority,doc=scope_fixture(tmp_path)
    first=binder.build_search_scope(source,brief,resources,authority,plan_source='static')
    value=store.read_record(first,contract_id='search-scope')
    assert value['brief_ref']==brief and value['topic_hints']==[] and value['local_document_refs']==[doc]
    assert 'queries' not in value
    other=store.put_blob(b'another accepted brief')
    second=binder.build_search_scope(source,other,resources,authority,plan_source='planned')
    assert second!=first and store.read_record(second)['topic_hints']==source['topic_hints']
    assert store.read_record(first)['brief_ref']==brief


@pytest.mark.parametrize('fault',['missing_bounds','missing_local','duplicate_connector','unknown_connector','queries_zero','queries_nine','hits_six','tool_budget','external_denied','bad_hint'])
def test_bounds_resource_authority_and_hint_failures_block_before_search(tmp_path,fault):
    bounds={}
    if fault=='duplicate_connector':bounds['connectors']=['local_documents','local_documents']
    if fault=='unknown_connector':bounds['connectors']=['invented']
    if fault=='queries_zero':bounds['max_queries']=0
    if fault=='queries_nine':bounds['max_queries']=9
    if fault=='hits_six':bounds['max_hits_per_query']=6
    if fault=='tool_budget':bounds.update(connectors=['local_documents','arxiv','semantic_scholar'],max_queries=8)
    if fault=='external_denied':bounds['connectors']=['arxiv']
    store,binder,source,brief,resources,authority,_=scope_fixture(tmp_path,**bounds)
    if fault=='missing_bounds':binder.search_bounds_ref=None
    if fault=='missing_local':resources['resources'][0]['available']=False
    if fault=='bad_hint':source['topic_hints']=['x']
    if fault=='tool_budget':authority.update(network='allowlist',network_allowlist=['export.arxiv.org','api.semanticscholar.org'])
    with pytest.raises(ResearchError):binder.build_search_scope(source,brief,resources,authority,plan_source='planned')
    assert not list(store.iter_records(kinds=('model-call','search-scope')))
