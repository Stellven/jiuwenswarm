"""Finite launch topology and real fresh assertion-key mechanics; no Docker."""
import base64
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).parents[3]
def load(name, file):
    spec = importlib.util.spec_from_file_location(name,ROOT/'deploy/m1'/file)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result); return result
launcher = load('unit_fixed_development_launcher','rsi_development_launcher.py')
installer = load('unit_fixed_development_install','rsi_development_install.py')


def topology():
    value = {'id':'unit-run','namespace_root':'/var/lib/fresh','evaluator_root':'/var/lib/evidence',
        'admin_directory':'/opt/frozen/deploy/m1','cgroup_root':'/sys/fs/cgroup/ai4r-rsi-host/jobs/development-unit-run',
        'approved_plan_sha256':'a'*64}
    for key in ('runner','authorization','seed_receipt','launch_guard_receipt'):
        value[key] = {'path':'/fixed/'+key,'sha256':'b'*64}
    value['seccomp'] = {'path':'/opt/frozen/deploy/m1/seccomp/executor.json','sha256':'c'*64}
    return value


@pytest.fixture
def private_claim_directory(monkeypatch):
    class Directory:
        def __str__(self): return '/fixed'
        def stat(self): return SimpleNamespace(st_mode=0o40700)
    monkeypatch.setattr(launcher, 'protected', lambda path, **kwargs: Directory())


def test_worker_topology_is_fixed_v18_no_hidden_auth_or_old_core_mounts(private_claim_directory):
    value = topology(); argv = launcher.worker_command(value,'run')
    assert launcher.IMAGE in argv and argv[-2:] == ['--approved-plan-sha256','a'*64]
    assert '--init' in argv and '--read-only' in argv and argv[argv.index('--network')+1] == 'none'
    assert argv[argv.index('--user')+1] == '0:0' and '--privileged' not in argv
    assert [argv[i+1] for i,item in enumerate(argv) if item == '--cap-add'] == ['SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL']
    assert argv[argv.index('--memory')+1] == argv[argv.index('--memory-swap')+1] == '512m'
    assert argv[argv.index('--pids-limit')+1] == '64'
    mounts = [argv[i+1] for i,item in enumerate(argv) if item == '--mount']
    assert len(mounts) == 9 and sum(',readonly' not in row for row in mounts) == 4
    assert mounts.index('type=bind,src=/fixed,dst=/fixed') < mounts.index('type=bind,src=/fixed/authorization,dst=/fixed/authorization,readonly')
    assert not any('operational-bootstrap' in row or 'custodian' in row or 'signing' in row for row in mounts)
    assert 'run' not in launcher.worker_command(value,'plan')[launcher.worker_command(value,'plan').index(launcher.IMAGE)+1:]
    with pytest.raises(ValueError): launcher.worker_command(value,'shell')


def test_mount_delimiters_cannot_add_another_mount_option(private_claim_directory):
    value = topology(); value['namespace_root'] += ',readonly=false'
    with pytest.raises(ValueError): launcher.worker_command(value,'run')


def test_claim_directory_must_remain_private_to_root(monkeypatch):
    monkeypatch.setattr(launcher, 'protected', lambda path, **kwargs: SimpleNamespace(stat=lambda: SimpleNamespace(st_mode=0o40750)))
    with pytest.raises(ValueError, match='PRIVATE_ROOT_AUTHORIZATION_CLAIM_DIRECTORY_REQUIRED'):
        launcher.worker_command(topology(), 'run')


def test_owned_host_client_uses_required_fixed_absolute_docker_command(monkeypatch):
    calls=[]
    def capture(command,**kwargs):calls.append(command);return SimpleNamespace(stdout=b'[]')
    monkeypatch.setattr(launcher.subprocess,'run',capture)
    assert launcher.docker({'restore':{'path':'/fixed/rsi_host_boot_restore.py'}},'ps','-q')==b'[]'
    assert calls==[['/usr/bin/python3','-B','/fixed/rsi_host_boot_restore.py','client','/usr/bin/docker','--host',launcher.SOCKET,'ps','-q']]


def test_real_gateway_key_generated_once_inplace_without_secret_in_output(tmp_path,monkeypatch):
    etc = tmp_path/'etc'; etc.mkdir(); module = tmp_path/'module'/'cc_rsi_development.py'
    registry = tmp_path/'registry'; registry.mkdir(); root = registry/'unit-run'
    source = tmp_path/'source.py'; source.write_bytes(b'# fixed public module\n')
    monkeypatch.setattr(installer,'ETC',etc); monkeypatch.setattr(installer,'MODULE',module)
    monkeypatch.setattr(installer,'REGISTRY',registry)
    monkeypatch.setattr(installer.launch,'protected',lambda path,**kwargs:Path(path))
    monkeypatch.setattr(installer.launch,'pinned',lambda value:Path(value['path']))
    monkeypatch.setattr(installer.os,'fchown',lambda *args:None,raising=False)
    monkeypatch.setattr(installer.os,'O_NOFOLLOW',0,raising=False)
    monkeypatch.setattr(installer.os,'O_DIRECTORY',0,raising=False)
    # Windows cannot open a directory with os.open; only the fsync helper is
    # replaced, while exclusive file writes and the real Ed25519 key are used.
    def write(path,raw,**kwargs):
        with open(path,'xb') as stream:stream.write(raw)
    monkeypatch.setattr(installer,'write',write)
    policy = {'schema':'ai4r-cc-rsi-development-policy:1','workspace_id':'local','origin':'http://127.0.0.1:5175',
        'actors':['unit:human'],'gateway_key_id':'unit:key','target_id':'unit:target','revision':'a'*64,'run_id':'unit-run'}
    value = {'schema':'ai4r-rsi-development-gateway-input:1','policy':policy,
        'module_source':{'path':str(source),'sha256':installer.launch.sha(source.read_bytes())}}
    facts = {'synthetic_source_plan':True}
    monkeypatch.setattr(installer,'gateway_plan',lambda path:(value,facts,root))
    completed = installer.gateway_apply(tmp_path/'input.json',installer.launch.sha(installer.launch.encoded(facts)))
    secret = (etc/'cc-rsi-development-gateway.key').read_bytes()
    assert len(secret) == 32 and secret not in installer.launch.encoded(completed)
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import Encoding,PublicFormat
    expected = base64.urlsafe_b64encode(Ed25519PrivateKey.from_private_bytes(secret).public_key().public_bytes(Encoding.Raw,PublicFormat.Raw)).decode().rstrip('=')
    assert completed['public_key'] == expected and completed['model_calls'] == 0 and completed['broker_started'] is False
    assert module.read_bytes() == source.read_bytes()
    before = (etc/'cc-rsi-development-gateway.key').read_bytes()
    with pytest.raises(FileExistsError): installer.gateway_apply(tmp_path/'input.json',installer.launch.sha(installer.launch.encoded(facts)))
    assert (etc/'cc-rsi-development-gateway.key').read_bytes() == before


@pytest.mark.parametrize('fault',['extra','no-actors','foreign-schema','unbounded-run'])
def test_installer_requires_explicit_closed_native_policy(fault):
    value = {'schema':'ai4r-cc-rsi-development-policy:1','workspace_id':'local','origin':'http://127.0.0.1:5175',
        'actors':['unit:human'],'gateway_key_id':'unit:key','target_id':'unit:target','revision':'a'*64,'run_id':'unit-run'}
    if fault == 'extra':value['command']='/bin/sh'
    elif fault == 'no-actors':value['actors']=[]
    elif fault == 'foreign-schema':value['schema']='other'
    else:value['run_id']='..'
    with pytest.raises(ValueError):installer.validate_policy(value)


def test_gateway_plan_pins_imported_launcher_and_mutation_blocks_before_key_write(tmp_path,monkeypatch):
    public = tmp_path/'public.py'; public.write_bytes(b'# unit public\n')
    policy = {'schema':'ai4r-cc-rsi-development-policy:1','workspace_id':'local','origin':'http://127.0.0.1:5175',
        'actors':['unit:human'],'gateway_key_id':'unit:key','target_id':'unit:target','revision':'a'*64,'run_id':'unit-run'}
    source = tmp_path/'input.json'; source.write_text(json.dumps({'schema':'ai4r-rsi-development-gateway-input:1',
        'policy':policy,'module_source':{'path':str(public),'sha256':installer.launch.sha(public.read_bytes())}}))
    dependency = tmp_path/'launcher.py'; dependency.write_bytes(b'# first helper\n')
    monkeypatch.setattr(installer.launch,'__file__',str(dependency))
    monkeypatch.setattr(installer.launch,'protected',lambda path,**kwargs:Path(path))
    monkeypatch.setattr(installer.launch,'pinned',lambda value:Path(value['path']))
    monkeypatch.setattr(installer,'os',SimpleNamespace(name='posix',geteuid=lambda:0,path=os.path))
    monkeypatch.setattr(installer,'MODULE',tmp_path/'not-yet-installed.py')
    monkeypatch.setattr(installer,'ETC',tmp_path/'not-yet-etc')
    monkeypatch.setattr(installer,'REGISTRY',tmp_path/'not-yet-registry')
    _,facts,_ = installer.gateway_plan(source)
    assert facts['launcher_sha256'] == installer.launch.sha(dependency.read_bytes())
    dependency.write_bytes(b'# changed helper\n')
    with pytest.raises(ValueError,match='PLAN_REVIEW'):
        installer.gateway_apply(source,installer.launch.sha(installer.launch.encoded(facts)))
    assert not installer.ETC.exists() and not installer.REGISTRY.exists()
