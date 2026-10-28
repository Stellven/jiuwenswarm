"""Native installation/auth mechanics only; no runtime keys or Library effects."""
import asyncio
import ast
import base64
import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from jiuwenswarm.research.cc_ui_runtime import module

installation=module('cc_rsi_installation')
operator=module('cc_rsi_operator')
ROOT=Path(__file__).parents[3]
spec=importlib.util.spec_from_file_location('unit_ui_operator',ROOT/'deploy/m1/rsi_ui_operator.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)


def policy():
    return {'schema':'ai4r-cc-rsi-root-operator-policy:2','revision':'unit','origin':'http://127.0.0.1:5175',
        'workspace_id':'unit-workspace','gateway_key_id':'unit:key','operators':{'unit:human':['admit']},
        'candidates':{'a'*64:{'node_id':'unit-node','admit_request_ref':{'id':'unit-request','sha256':'b'*64},'activate_request_ref':None}}}


@pytest.fixture
def gateway(tmp_path):
    from jiuwenswarm.research.shell_auth import SessionAuthority
    from jiuwenswarm.research.contracts import Principal
    from jiuwenswarm.research_rsi.signing import Signer
    authority=SessionAuthority(tmp_path/'synthetic-native-session','http://127.0.0.1:5175')
    bootstrap=authority.initialize(Principal('unit:human',frozenset({'unit-workspace'}),frozenset({'status'})))
    grant=authority.bootstrap(bootstrap.split('research_bootstrap=')[1],origin=authority.origin,host=authority.host)
    headers={'origin':authority.origin,'host':authority.host,'cookie':grant['set_cookie'].split(';')[0]}
    signer=Signer.generate('unit:key');calls=[]
    class Client:
        def execute(self,*args):calls.append(args);return {'unit':'synthetic client, no Library dispatch'}
    class Projection:
        def snapshot(self,params):
            return {'targets':[{'run':{'allowed':False,'blocker':'uninstalled run authority'}}],
                'nodes':[{'id':'unit-node','hash':'a'*64,'admit':{'allowed':False,'blocker':'installation'},
                          'activate':{'allowed':False,'blocker':'installation'}}]}
    value=installation.InstalledNativeGateway(authority,signer,Client(),policy(),projection=Projection())
    try:yield value,headers,calls
    finally:authority.close()


def test_native_snapshot_gates_exact_account_workspace_node_and_action(gateway):
    value,headers,calls=gateway
    view=value.snapshot(headers,{})
    assert view['nodes'][0]['admit']=={'allowed':True,'blocker':None}
    assert view['nodes'][0]['activate']['allowed'] is False
    assert view['targets'][0]['run']['allowed'] is False and calls==[]
    value.policy['workspace_id']='another-workspace'
    assert value.snapshot(headers,{})['nodes'][0]['admit']['allowed'] is False
    value.policy['workspace_id']='unit-workspace';value.policy['operators']={}
    assert value.snapshot(headers,{})['nodes'][0]['admit']['allowed'] is False


def test_action_proof_contains_current_native_identity_and_root_workspace(gateway):
    from jiuwenswarm.research.contracts import ResearchError
    value,headers,calls=gateway
    params={'action':'admit','node_id':'unit-node','candidate_hash':'a'*64}
    assert asyncio.run(value.execute(headers,params))=={'unit':'synthetic client, no Library dispatch'}
    authorization=calls[0][-1]
    assertion=json.loads(base64.urlsafe_b64decode(authorization.proof))
    assert assertion['actor']=='unit:human' and assertion['workspace_id']=='unit-workspace'
    with pytest.raises(ResearchError):asyncio.run(value.execute(dict(headers,origin='http://other.invalid'),params))
    with pytest.raises(ResearchError):asyncio.run(value.execute(headers,dict(params,actor='root')))
    value.adapter.workspace_id='another-workspace'
    with pytest.raises(ResearchError):asyncio.run(value.execute(headers,params))
    assert len(calls)==1


def test_root_rechecks_signed_workspace_before_any_library_preflight(gateway):
    value,headers,calls=gateway
    asyncio.run(value.execute(headers,{'action':'admit','node_id':'unit-node','candidate_hash':'a'*64}))
    authorization=calls[0][-1]
    changed=policy();changed['workspace_id']='another-workspace'
    def forbidden(*args):pytest.fail('Workspace mismatch must not touch Library or journal')
    engine=operator.RootOperatorEngine(changed,value.adapter.signer.public_bytes(),SimpleNamespace(lookup=forbidden),forbidden,forbidden)
    request={'protocol':'ai4r-cc-rsi-human-operator:1','action':'admit','node_id':'unit-node','candidate_hash':'a'*64,
        'authorization':{'actor':authorization.actor,'action_id':authorization.action_id,'proof':authorization.proof}}
    with pytest.raises(installation.ProjectionError):engine.handle(request)


def test_installed_native_route_returns_authenticated_per_human_snapshot(gateway):
    from jiuwenswarm.research.contracts import ResearchError
    value,headers,calls=gateway
    tree=ast.parse((ROOT/'jiuwenswarm/gateway/channel_manager/web/research_http.py').read_text(encoding='utf8'))
    functions=[node for node in tree.body if isinstance(node,ast.AsyncFunctionDef) and node.name in {'_result','native_research_message'}]
    namespace={'asyncio':asyncio,'ResearchError':ResearchError,'inspect':__import__('inspect'),'os':__import__('os')}
    exec(compile(ast.Module(body=functions,type_ignores=[]),'native-cc-route','exec'),namespace)
    channel=SimpleNamespace(research_authority=value.authority,research_service=object(),research_cc_operator=value)
    handled,view=asyncio.run(namespace['native_research_message'](channel,SimpleNamespace(request_headers=headers),'rsi.cc.snapshot',{}))
    assert handled and view['nodes'][0]['admit']['allowed'] and calls==[]
    value.authority.revoke(value.authority.token_path.read_text())
    with pytest.raises(ResearchError):asyncio.run(value.execute(headers,{'action':'admit','node_id':'unit-node','candidate_hash':'a'*64}))


def test_absent_installation_remains_uninstalled_and_invalid_file_is_refused(tmp_path,monkeypatch):
    path=tmp_path/'missing-installation.json'
    monkeypatch.setattr(installation,'GATEWAY_CONFIG',path)
    assert installation.load_native_gateway(SimpleNamespace()) is None
    path.write_text('{}')
    def rejected(*args,**kwargs):raise installation.ProjectionError('unit custody rejection')
    monkeypatch.setattr(installation,'protected_bytes',rejected)
    with pytest.raises(installation.ProjectionError):installation.load_native_gateway(SimpleNamespace())


def grant():
    return {'schema':'ai4r-cc-rsi-installation-input:1','revision':'unit','origin':'http://127.0.0.1:5175',
        'workspace_id':'unit-workspace','operators':{},'candidates':{},'gateway_uid':10001,'gateway_gid':10001,'socket_gid':10001,
        'library':{'python':'/opt/venv/bin/python-cc-operator','bindings_path':'/etc/ai4r/bootstrap-bindings.json',
            'config_path':'/etc/ai4r/config.yaml','state_root':'/var/lib/ai4r','timeout':3600}}


def test_bundle_configuration_pair_has_no_default_human_or_candidate_grants():
    value=grant();selected=installer.policy_for(value)
    gateway,root=installer.configurations(value,selected,b'x'*32,'f'*64)
    assert gateway['policy']==root['policy']==selected
    assert selected['operators']==selected['candidates']=={}
    assert root['library']==dict(value['library'],python_sha256='f'*64)
    assert set(gateway)=={'schema','policy','gateway_uid','gateway_public_key'}


@pytest.mark.parametrize('fault',['callback','port','workspace','candidate','uid','gateway_gid','socket_gid'])
def test_installer_input_cannot_select_callbacks_or_implicit_authority(fault):
    value=grant()
    if fault=='callback':value['callback']='untrusted.module'
    elif fault=='port':value['origin']='http://127.0.0.1:5176'
    elif fault=='workspace':value['workspace_id']=''
    elif fault=='candidate':value['candidates']={'a'*64:{'node_id':'unit','admit_request_ref':{'path':'browser'},'activate_request_ref':None}}
    elif fault in ('gateway_gid','socket_gid'):value[fault]=13000
    else:value['gateway_uid']=True
    with pytest.raises(ValueError):installer.policy_for(value)


@pytest.mark.parametrize('fault', [None, 'config', 'build', 'completion', 'effect'])
def test_completion_binds_exact_config_installed_build_and_preparation_only(fault, monkeypatch):
    import hashlib
    import jiuwenswarm.research.native_ports as native_ports
    raw = b'unit protected config'
    done = {'schema':'ai4r-cc-rsi-installation-complete:1','plan_sha256':'a'*64,
        'source_build_id':'unit-build','entrypoint_sha256':'b'*64,
        'gateway_config_sha256':hashlib.sha256(raw).hexdigest(),'operator_config_sha256':'c'*64,
        'app_deployed':False,'broker_started':False,'admission_performed':False,'activation_performed':False}
    if fault == 'completion': done.pop('plan_sha256')
    if fault == 'effect': done['admission_performed'] = True
    monkeypatch.setattr(installation,'protected_bytes',lambda *args,**kwargs: json.dumps(done).encode())
    monkeypatch.setattr(native_ports,'verify_installed_build',lambda: 'other-build' if fault=='build' else 'unit-build')
    if fault is None:
        assert installation.completed_installation('gateway_config_sha256',raw)==done
    else:
        with pytest.raises(installation.ProjectionError):
            installation.completed_installation('gateway_config_sha256',b'changed' if fault=='config' else raw)


def test_broker_composition_requires_existing_native_library_input_mount():
    import yaml
    class Loader(yaml.SafeLoader): pass
    Loader.add_constructor('!override', lambda loader,node: loader.construct_sequence(node))
    compose = yaml.load((ROOT/'deploy/m1/compose.rsi.ui.operator.yaml').read_text(), Loader=Loader)
    broker = compose['services']['cc-human-operator']
    assert broker['read_only'] is True
    assert 'group_add' not in compose['services']['app']
    mounts = [row for row in broker['volumes'] if row['target']=='/workspace/input']
    assert len(mounts)==1
    assert mounts[0]=={'type':'bind','source':'${AI4R_CC_LIBRARY_INPUT:?explicit verified native Library input root required}',
        'target':'/workspace/input','bind':{'create_host_path':False}}


def test_library_composition_rejects_uninstalled_native_input_before_child(monkeypatch):
    library = module('cc_rsi_library')
    monkeypatch.setattr(library,'os',SimpleNamespace(name='posix',geteuid=lambda:0))
    checks=[]
    def paths(path, **options):
        checks.append((path,options))
        if path=='/workspace/input': raise installation.ProjectionError('unit native input custody failure')
        return path
    monkeypatch.setattr(library,'_root_path',paths)
    with pytest.raises(installation.ProjectionError):
        library.ProtectedLibraryComposition(policy(),**grant()['library'])
    assert checks[-1]==('/workspace/input',{'directory':True,'leaf_uid':10001})


def test_installer_identity_matches_existing_native_permanent_primary_group():
    tree = ast.parse((ROOT/'jiuwenswarm/research/bootstrap.py').read_text())
    identity = next(row for row in tree.body if isinstance(row,ast.Assign)
        and {target.id for target in row.targets if isinstance(target,ast.Name)}=={'APP_UID','APP_GID'})
    assert ast.literal_eval(identity.value)==10001
    selected = grant()
    assert all(selected[key]==10001 for key in ('gateway_uid','gateway_gid','socket_gid'))
    installer.policy_for(selected)
