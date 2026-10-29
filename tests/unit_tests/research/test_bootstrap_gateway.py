from types import SimpleNamespace

import pytest

from jiuwenswarm.research.bootstrap_gateway import attach_native_research
from jiuwenswarm.research.contracts import ResearchError


@pytest.mark.asyncio
@pytest.mark.parametrize('configuration', ['missing', 'malformed', 'unsafe', 'symlink'])
async def test_missing_runtime_and_bindings_keep_authenticated_inspection_but_block_work(tmp_path,monkeypatch,configuration):
    import jiuwenswarm.research.bootstrap_gateway as gateway
    actual_store=gateway.SQLiteRunStore
    def isolated_store(root,**kwargs):
        assert kwargs['input_root']=='/workspace/input'
        return actual_store(root,**dict(kwargs,input_root=tmp_path/'input'))
    monkeypatch.setattr(gateway,'SQLiteRunStore',isolated_store)
    handoff=tmp_path/'ipc';handoff.mkdir(mode=0o700)
    monkeypatch.setattr(gateway,'BOOTSTRAP_HANDOFF',handoff/'browser-bootstrap.json')
    monkeypatch.setenv('JIUWENSWARM_M1_STATE',str(tmp_path/'state'))
    monkeypatch.setenv('JIUWENSWARM_M1_ACCOUNTS',str(tmp_path/'accounts'))
    config=tmp_path/'operator.yaml'
    if configuration=='malformed':config.write_text('secret-canary: [invalid',encoding='utf-8')
    elif configuration=='unsafe':config.write_text('secret-canary: invalid',encoding='utf-8');config.chmod(0o666)
    elif configuration=='symlink':
        target=tmp_path/'other';target.write_text('secret-canary: invalid',encoding='utf-8');config.symlink_to(target)
    monkeypatch.setenv('JIUWENSWARM_M1_CONFIG',str(config))
    monkeypatch.setenv('JIUWENSWARM_M1_ORIGIN','http://127.0.0.1:5173')
    monkeypatch.delenv('JIUWENSWARM_M1_BOOTSTRAP_BINDINGS',raising=False)
    channel=SimpleNamespace();result=await attach_native_research(channel)
    assert channel.research_profile and channel.research_service is result.service
    assert result.bootstrap_url.startswith('http://127.0.0.1:5173/#research_bootstrap=')
    token=(tmp_path/'accounts'/'sessions'/'session-token').read_text()
    actor=channel.research_authority.authenticate('Bearer '+token,'status')
    import json,os,stat
    from pathlib import Path
    defaults=Path(os.environ['JIUWENSWARM_M1_CLIENT_CONFIG'])
    assert defaults.parent==Path(os.environ['JIUWENSWARM_M1_TOKEN_FILE']).parent
    assert defaults.name=='client-defaults.json' and json.loads(defaults.read_text())['account_id']==actor.account_id
    if os.name=='posix':assert stat.S_IMODE(defaults.stat().st_mode)==0o600
    assert set(json.loads((handoff/'browser-bootstrap.json').read_text()))=={'url'}
    assert result.service.client_defaults(actor)['configuration_ref'] is None
    assert result.composition is None
    assert channel.research_refusal_reason=='operator_configuration_unavailable'
    assert 'secret-canary' not in str(result.diagnostics)
    with pytest.raises(ResearchError,match='unavailable'):
        await result.service.readiness(channel.research_authority.authenticate('Bearer '+token,'readiness'))
    with pytest.raises(ResearchError):await result.service.ingest(actor,'Attempt work')
    result.close()
