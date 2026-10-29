"""Disposable grants prove local authority controls, never an operational profile."""
import copy
import os
from pathlib import Path
import pytest
from jiuwenswarm.research.contracts import Principal, ResearchError
from jiuwenswarm.research.shell_auth import SessionAuthority


def pin(name):return {'id':name,'sha256':('a' if name=='config' else 'b')*64}


@pytest.fixture
def grants(tmp_path):
    authority=SessionAuthority(tmp_path/'sessions','http://testserver')
    main=Principal('owner',frozenset({'work'}),frozenset({'status','readiness','submit','reconcile','cancel','export','settings'}))
    authority.initialize(main)
    context={'account_id':'owner','workspace_id':'work','configuration_ref':pin('config'),'profile_ref':pin('profile'),'profile_id':'approved'}
    rows={'run:one':{'id':'run:one','account_id':'owner','workspace_id':'work','submission':{
        'profile_id':'approved','configuration_ref':pin('config'),'evaluation':{'campaign_id':'campaign-one'}}}}
    authority.configure_evaluation(context,run_lookup=lambda run:copy.deepcopy(rows[run]),
        run_reconcile=lambda account,request:[copy.deepcopy(row) for row in rows.values() if request==row['id']])
    yield authority,context,rows,tmp_path
    authority.close()


def issue(grants,campaign='campaign-one',name='evaluation-token'):
    authority,context,_,root=grants
    binding={'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':campaign}
    result=authority.issue_evaluation(binding,root/name)
    return result,'Bearer '+(root/name).read_text(encoding='ascii')


def test_separate_family_fixed_file_and_no_main_ws_or_operation_widening(grants):
    authority,_,_,root=grants
    main=authority.token_path.read_text(encoding='ascii')
    result,header=issue(grants)
    assert (root/'evaluation-token').stat().st_mode&0o777==0o600
    assert (root/'evaluation-token').stat().st_uid==11001
    assert authority.token_path.read_text(encoding='ascii')==main
    assert authority.authenticate(header,'evaluation_profile','work').account_id=='owner'
    with pytest.raises(ResearchError):authority.authenticate('Bearer '+main,'evaluation_profile','work')
    with pytest.raises(ResearchError):authority.authenticate(header,'settings')
    with pytest.raises(ResearchError):authority.authenticate_ws({'host':'testserver','authorization':header},'status')
    assert 'token' not in result and result['grant_id']
    authority.revoke_evaluation(result['grant_id'])
    with pytest.raises(ResearchError):authority.authenticate(header,'status')
    assert authority.authenticate('Bearer '+main,'status').account_id=='owner'


def test_each_token_is_bound_despite_same_account_and_reconcile_checks_run(grants):
    authority,_,rows,_=grants
    _,one=issue(grants)
    _,two=issue(grants,'campaign-two','other-token')
    authority.authorize_evaluation(one,'status',run_id='run:one')
    authority.authorize_evaluation(one,'reconcile',client_request_id='run:one')
    for operation in ('status','cancel','export'):
        with pytest.raises(ResearchError):authority.authorize_evaluation(two,operation,run_id='run:one')
    with pytest.raises(ResearchError):authority.authorize_evaluation(two,'reconcile',client_request_id='run:one')
    submission={'workspace_id':'work','profile_id':'approved','configuration_ref':pin('config'),'evaluation':{'campaign_id':'campaign-one'}}
    authority.authorize_evaluation(one,'submit',submission=submission)
    for key,value in [('workspace_id','foreign'),('profile_id','foreign'),('configuration_ref',pin('foreign')),('evaluation',{'campaign_id':'campaign-two'})]:
        with pytest.raises(ResearchError):authority.authorize_evaluation(one,'submit',submission=submission|{key:value})
    rows['run:one']['submission']['configuration_ref']=pin('foreign')
    with pytest.raises(ResearchError):authority.authorize_evaluation(one,'export',run_id='run:one')


def test_context_change_or_restart_revokes_grants(grants):
    authority,context,_,_=grants
    _,header=issue(grants)
    authority.configure_evaluation(context|{'profile_id':'next'},run_lookup=lambda _:None,run_reconcile=lambda *_:[])
    with pytest.raises(ResearchError):authority.authenticate(header,'status')
    authority.initialize(Principal('owner',frozenset({'work'}),frozenset({'status'})))
    with pytest.raises(ResearchError):authority.authenticate(header,'status')


def test_existing_file_symlink_and_unapproved_or_nonoperator_issuance_fail_closed(grants,monkeypatch):
    authority,context,_,root=grants
    output=root/'existing';output.write_bytes(b'preserved')
    with pytest.raises((ResearchError,FileExistsError)):issue(grants,name='existing')
    assert output.read_bytes()==b'preserved'
    link=root/'link';link.symlink_to(output)
    with pytest.raises((ResearchError,FileExistsError)):issue(grants,name='link')
    assert output.read_bytes()==b'preserved'
    monkeypatch.setattr(os,'geteuid',lambda:11001)
    with pytest.raises(ResearchError):issue(grants,name='denied')
    assert not (root/'denied').exists()


def test_no_startup_profile_means_no_issuer_authority(tmp_path):
    authority=SessionAuthority(tmp_path/'sessions','http://testserver')
    authority.initialize(Principal('owner',frozenset({'work'}),frozenset({'status'})))
    with pytest.raises(ResearchError):authority.issue_evaluation({'schema':'ai4r-evaluation-grant:1'},tmp_path/'token')
    assert not (tmp_path/'token').exists()
    authority.close()


def test_operator_binding_file_is_closed_private_and_never_reports_secret(grants,capsys):
    import json
    from jiuwenswarm.research.evaluation_grants import read_binding
    authority,context,_,root=grants
    path=root/'binding.json'
    binding={'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':'campaign-one'}
    path.write_text(json.dumps(binding),encoding='utf-8');path.chmod(0o600)
    assert read_binding(path)==binding
    path.chmod(0o644)
    with pytest.raises(ResearchError):read_binding(path)
    path.chmod(0o600)
    hard=root/'hard';os.link(path,hard)
    with pytest.raises(ResearchError):read_binding(path)
    hard.unlink()
    with pytest.raises(ResearchError):authority.issue_evaluation(binding|{'operations':['settings']},root/'extra')
    assert not (root/'extra').exists()
    assert capsys.readouterr().out==''


def test_exact_startup_campaign_refuses_other_issuance(grants):
    authority,context,_,root=grants
    authority.configure_evaluation(context,run_lookup=lambda _:None,run_reconcile=lambda *_:[],campaign_id='only')
    with pytest.raises(ResearchError):issue(grants,'other')
    assert not (root/'evaluation-token').exists()


def test_literal_operator_cli_opens_app_owned_database_without_changing_wal_custody(monkeypatch,capsys):
    import json,tempfile
    from jiuwenswarm.research import evaluation_grants
    with tempfile.TemporaryDirectory(prefix='ai4r-evaluation-issuer-') as directory:
        root=Path(directory);root.chmod(0o711)
        sessions=root/'sessions'
        authority=SessionAuthority(sessions,'http://testserver')
        authority.initialize(Principal('owner',frozenset({'work'}),frozenset({'status'})))
        context={'account_id':'owner','workspace_id':'work','configuration_ref':pin('config'),'profile_ref':pin('profile'),'profile_id':'approved'}
        authority.configure_evaluation(context,run_lookup=lambda _:None,run_reconcile=lambda *_:[])
        authority.close()
        for path in [sessions,*sessions.iterdir()]:os.chown(path,10001,10001)
        binding=root/'binding';binding.write_text(json.dumps({'schema':'ai4r-evaluation-grant:1',**{k:v for k,v in context.items() if k!='account_id'},'campaign_id':'one'}));binding.chmod(0o600)
        monkeypatch.setattr(evaluation_grants,'SESSION_ROOT',sessions)
        assert evaluation_grants.main(['issue','--binding-file',str(binding),'--output',str(root/'token')])==0
        reply=json.loads(capsys.readouterr().out)
        token=(root/'token').read_text(encoding='ascii')
        assert token not in json.dumps(reply) and (root/'token').stat().st_uid==11001
        assert all(path.stat().st_uid==10001 for path in sessions.iterdir())
        assert evaluation_grants.main(['revoke','--grant-id',reply['grant_id']])==0
        assert 'revoked' in capsys.readouterr().out


def test_evaluation_entry_checks_exact_actual_token_context_without_e1_body(grants):
    authority,context,_,_=grants
    _,header=issue(grants)
    fields={'profile_id':context['profile_id'],'workspace_id':context['workspace_id'],'campaign_id':'campaign-one','configuration_ref':context['configuration_ref']}
    authority.authorize_evaluation_entry(header,**fields)
    for key,value in [('profile_id','foreign'),('workspace_id','foreign'),('campaign_id','foreign'),('configuration_ref',pin('foreign'))]:
        with pytest.raises(ResearchError):authority.authorize_evaluation_entry(header,**(fields|{key:value}))
    main='Bearer '+authority.token_path.read_text(encoding='ascii')
    with pytest.raises(ResearchError):authority.authorize_evaluation_entry(main,**fields)
