"""Actual native-session catalog reads: no carrier execution or grants."""
import ast
import asyncio
import hashlib
import inspect
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.shell_auth import SessionAuthority
from jiuwenswarm.research_rsi.targets import capsules


@pytest.fixture
def endpoint(tmp_path, monkeypatch):
    source = Path(__file__).parents[3]/'jiuwenswarm/gateway/channel_manager/web/research_http.py'
    functions = [n for n in ast.parse(source.read_text(encoding='utf8')).body
                 if isinstance(n, ast.AsyncFunctionDef) and n.name in ('_result','native_research_message')]
    ns = {'ResearchError': ResearchError, 'inspect': inspect, 'os': os}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), ns)
    monkeypatch.delenv('JIUWENSWARM_CC_RSI_PUBLICATION', raising=False)
    authority = SessionAuthority(tmp_path/'native', 'http://127.0.0.1:5175')
    bootstrap = authority.initialize(Principal('unit:catalog-human', frozenset({'local'}), frozenset({'status'})))
    grant = authority.bootstrap(bootstrap.split('research_bootstrap=')[1], origin=authority.origin, host=authority.host)
    headers = {'origin': authority.origin, 'host': authority.host, 'cookie': grant['set_cookie'].split(';')[0]}
    channel = SimpleNamespace(research_authority=authority, research_service=None, research_cc_workspace='local')
    def call(params=None, supplied_headers=None):
        return asyncio.run(ns['native_research_message'](channel, SimpleNamespace(request_headers=headers if supplied_headers is None else supplied_headers), 'rsi.cc.targets.list', {} if params is None else params))
    yield call, channel
    authority.close()


def test_actual_registry_metadata_no_evaluation_or_runtime_authority(endpoint, monkeypatch):
    monkeypatch.setattr(capsules, '_carrier', lambda *a: pytest.fail('Catalog must not import/execute carrier'))
    handled, result = endpoint[0]()
    assert handled and result['workspace_id'] == 'local'
    assert [r['capsule_name'] for r in result['targets']] == ['utility.calculate','utility.table_normalize','research.builder']
    root = Path(capsules.__file__).resolve().parents[2]
    for row in result['targets']:
        assert row['development_grant_status'] == 'NOT_ESTABLISHED'
        assert row['library_admission'] == 'UNKNOWN' and row['measured_results'] is None
        assert row['operational_rsi_available'] is False
        assert row['parent_code_sha256'] == hashlib.sha256((root/row['carrier_path']).read_bytes()).hexdigest()
    assert [r['public_fixture_count'] for r in result['targets']] == [4,5,0]
    assert result['targets'][2]['public_evaluation_available'] is False


def test_catalog_rejects_auth_workspace_and_browser_selected_inputs(endpoint):
    call, channel = endpoint
    with pytest.raises(ResearchError): call(supplied_headers={})
    for params in ({'path':'/private'}, {'target_id':'utility.calculate'}, {'execute':True}):
        with pytest.raises(ResearchError): call(params)
    channel.research_cc_workspace = 'foreign'
    with pytest.raises(ResearchError): call()
    channel.research_cc_workspace = None
    with pytest.raises(ResearchError): call()


def test_catalog_rejects_publication_startup_environment_mismatch(endpoint, monkeypatch):
    monkeypatch.setenv('JIUWENSWARM_CC_RSI_PUBLICATION', '/run/ai4r-rsi-ui/publication.json')
    monkeypatch.setenv('JIUWENSWARM_CC_RSI_WORKSPACE', 'foreign')
    with pytest.raises(ResearchError): endpoint[0]()
