"""Controlled scope composition; never a real thirteen-case qualification.

Kernel/Docker identities and prerequisite availability are controlled fixtures.
Linux still exercises actual file custody and full inventory hashing. Windows
emulates only the root-file reads; production has no such platform override.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from jiuwenswarm.research_rsi import security_scope as scopes
from jiuwenswarm.research_rsi.records import encoded
from jiuwenswarm.research_rsi.worker import PublicBytes, WorkerBroker
from jiuwenswarm.research.executor import RestrictedExecutor

REAL_PREREQUISITES=RestrictedExecutor.prerequisites


def test_installed_inventory_accepts_bounded_native_asset_larger_than_a_capture(tmp_path):
    if os.name!='posix':return
    package=tmp_path/'package';package.mkdir()
    asset=package/'native-component.node';asset.write_bytes(b'x'*(5*1024*1024));asset.chmod(0o600)
    assert scopes._inventory(package)['files'][0]['bytes']==5*1024*1024


def test_runtime_capture_parent_cannot_be_renamed_by_another_role(tmp_path):
    if os.name!='posix':return
    parent=tmp_path/'writable';parent.mkdir();parent.chmod(0o777)
    with pytest.raises(scopes.ScopeUnavailable):scopes._capture_ancestry(parent/'capture.json')


def test_capture_ancestry_is_rechecked_after_observer_construction(tmp_path,monkeypatch):
    if os.name!='posix':return
    f=fixture(tmp_path,monkeypatch)
    assert f['observer'](f['scope'])==f['scope']
    f['capture_file'].parent.chmod(0o777)
    try:
        with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])
    finally:f['capture_file'].parent.chmod(0o700)


def fixture(tmp_path,monkeypatch):
    from tests.unit_tests.research_rsi.fixture_package import make_unit_package
    f=make_unit_package(tmp_path/'unit-source')
    table={}
    def retain(pin,raw):table[encoded(pin)]=raw;return pin
    def put(raw):
        digest=hashlib.sha256(raw).hexdigest()
        return retain({'id':digest+'.json','sha256':digest},raw)
    def record(value):return put(encoded(value))
    def original(pin):return retain(pin,f['store'].read_blob(pin))
    package=tmp_path/'selected-package';package.mkdir()
    for name,raw in {'worker.py':b'controlled worker source','executor.py':b'controlled executor source',
                     '_executor_probe.py':b'controlled probe source','adapter.py':b'full closure beyond entrypoints',
                     '__init__.py':b''}.items():
        (package/name).write_bytes(raw);(package/name).chmod(0o600)
    installed=tmp_path/'installed-package';shutil.copytree(package,installed)
    tui=tmp_path/'tui';tui.mkdir();(tui/'ui.py').write_bytes(b'controlled component');(tui/'ui.py').chmod(0o600)
    if os.name!='posix':
        monkeypatch.setattr(scopes,'_root_bytes',lambda p,maximum=scopes.MAX_BYTES:Path(p).read_bytes())
        monkeypatch.setattr(scopes.os,'geteuid',lambda:0,raising=False)
    monkeypatch.setattr(scopes,'_installed_roots',lambda:(package,installed,tui))
    monkeypatch.setattr(scopes,'_source_files',lambda:{'worker_driver_ref':package/'worker.py',
        'executor_ref':package/'executor.py','probe_ref':package/'_executor_probe.py'})
    monkeypatch.setattr(scopes,'_dependencies',lambda:[{'name':'controlled-dependency','version':'1'}])
    manifest={'schema':'ai4r-installed-build:2',**scopes._inventory(package),
        'dependencies':scopes._dependencies(),'components':{'jiuwenswarm_tui':scopes._inventory(tui)},
        'uv_lock_sha256':'a'*64,'pyproject_sha256':'b'*64}
    manifest['build_id']=hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    installed_ref=record(manifest)
    build_ref=record({'candidate_id':'controlled-candidate','installed_build_ref':installed_ref})
    image_id='sha256:'+'d'*64;digest='sha256:'+'e'*64
    environment_ref=record({'image_id':image_id,'image_digest':digest,'platform':'linux/amd64'})
    session=copy.deepcopy(f['session']);session['pass_count_repeats']=1
    session_ref=record(session);target_ref=session['target_profile_ref']
    target=f['store'].read_record(target_ref)
    unit=f['attempt']['configuration_ref']
    for pin in (target_ref,target['parent_declaration_ref'],target['parent_ref'],unit):original(pin)
    profile={'schema':'ai4r-rsi-worker-profile:3','process_policy':'single_process_seccomp_v1','target_kind':'ranking-v1','session_ref':session_ref,
        'target_ref':target_ref,'parent_ref':target['parent_ref'],'contract_ref':unit,
        'environment_ref':environment_ref,'hardware_ref':unit,'memory_mb':64,'pids_max':32,'timeout_s':1}
    profile_ref=record(profile)
    source_refs={key:put(path.read_bytes()) for key,path in scopes._source_files().items()}
    scope={'schema':'ai4r-rsi-security-scope:1','id':'controlled:scope','runtime_build_ref':build_ref,
        'environment_ref':environment_ref,**source_refs,'kernel_release':'controlled-kernel','platform':'linux/amd64',
        'worker_profile_refs':[profile_ref]}
    identity={'container_id':'c'*64,'pid_namespace':'pid:[123]','mount_namespace':'mnt:[456]',
        'boot_id':'12345678-1234-1234-1234-123456789abc','kernel_release':'controlled-kernel',
        'platform':'linux/amd64','init_start_ticks':100}
    captured={'schema':'ai4r-rsi-runtime-observation:1',**identity,'image_id':image_id,'image_digest':digest,
        'read_only_rootfs':True,**{k:scope[k] for k in ('runtime_build_ref','environment_ref','worker_profile_refs')}}
    capture_file=tmp_path/'root-runtime.json';capture_file.write_bytes(encoded(captured));capture_file.chmod(0o600)
    public=PublicBytes([tmp_path])
    reads=[]
    def read(self,pin):reads.append(pin);return table[encoded(pin)]
    monkeypatch.setattr(PublicBytes,'read',read)
    owner=object.__new__(WorkerBroker);owner.public=public;owner.profiles={encoded(profile_ref):copy.deepcopy(profile)}
    owner.executor=RestrictedExecutor(workspace_root=tmp_path/'work',cgroup_root=tmp_path/'cgroup',
        authorize_job=None,capture=None,executor_uid=12003,executor_gid=12003)
    checks=[]
    def prerequisites(self):checks.append(self);return []
    monkeypatch.setattr(RestrictedExecutor,'prerequisites',prerequisites)
    monkeypatch.setattr(scopes,'_mount_for',lambda p:(Path('/'),{'ro'},'cgroup2' if p==owner.executor.cgroup_root else 'overlay'))
    monkeypatch.setattr(scopes,'_identity',lambda *args,**kwargs:copy.deepcopy(identity))
    observer=scopes.RuntimeScopeObserver(worker_owner=owner,approved_scope=scope,runtime_capture_file=capture_file)
    f['store'].close()
    return dict(observer=observer,scope=scope,captured=captured,capture_file=capture_file,owner=owner,
        table=table,reads=reads,checks=checks,profile=profile,profile_ref=profile_ref,package=package,
        installed=installed,public=public,image_id=image_id,digest=digest,identity=identity)


def test_controlled_current_measurements_match_exact_scope_and_revalidate_every_call(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    assert f['observer'](f['scope'])==f['scope']
    count=len(f['reads'])
    observed=f['observer'](copy.deepcopy(f['scope']))
    assert len(f['checks'])==2 and len(f['reads'])>count
    observed['id']='mutated returned copy'
    assert f['observer'](f['scope'])['id']=='controlled:scope'


def test_caller_scope_or_boolean_cannot_select_current_truth(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    for claimed in (True,dict(f['scope'],kernel_release='caller-claimed-kernel')):
        with pytest.raises(scopes.ScopeUnavailable):f['observer'](claimed)
    with pytest.raises(scopes.ScopeUnavailable):
        scopes.RuntimeScopeObserver(worker_owner=type('Attestation',(),{'ready':True})(),
            approved_scope=f['scope'],runtime_capture_file=f['capture_file'])


def test_actual_core_prerequisites_are_called_unbound_and_cannot_be_replaced_by_owner_ready(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f['owner'].executor.prerequisites=lambda:['this override must not be used']
    assert f['observer'](f['scope'])==f['scope']
    assert len(f['checks'])==1
    monkeypatch.setattr(RestrictedExecutor,'prerequisites',lambda self:['ACTUAL_CORE_PREREQUISITE_UNAVAILABLE'])
    f['owner'].executor.prerequisites=lambda:[]
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])


def test_real_missing_cgroup_prerequisite_blocks_despite_a_matching_root_capture(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(RestrictedExecutor,'prerequisites',REAL_PREREQUISITES)
    f['owner'].executor.cgroup_root=None
    # Actual installed prerequisites run here; no injected positive measurement
    # can replace the mandatory delegated-cgroup condition.
    expected='DELEGATED_CGROUP_UNAVAILABLE' if os.name=='posix' else 'LINUX_REQUIRED'
    assert expected in REAL_PREREQUISITES(f['owner'].executor)
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])


@pytest.mark.parametrize('field,value',[('container_id','f'*64),('pid_namespace','pid:[999]'),
    ('init_start_ticks',101),('image_digest','sha256:'+'f'*64),('image_id','sha256:'+'f'*64)])
def test_stale_or_foreign_root_observation_is_not_current_scope(tmp_path,monkeypatch,field,value):
    f=fixture(tmp_path,monkeypatch)
    f['capture_file'].write_bytes(encoded(dict(f['captured'],**{field:value})))
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])


@pytest.mark.parametrize('tree',['package','installed'])
def test_changed_closure_beyond_three_entrypoints_or_shadow_install_blocks(tmp_path,monkeypatch,tree):
    f=fixture(tmp_path,monkeypatch)
    (f[tree]/'adapter.py').write_bytes(b'changed source outside entrypoints')
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])


def test_profile_original_bytes_and_active_registry_are_revalidated(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    original=f['table'][encoded(f['profile_ref'])]
    f['table'][encoded(f['profile_ref'])]=encoded(dict(f['profile'],memory_mb=65))
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])
    f['table'][encoded(f['profile_ref'])]=original
    f['owner'].profiles[encoded(f['profile_ref'])]['timeout_s']=2
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])


def test_missing_actual_capture_or_complete_inventory_never_uses_a_ready_receipt(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    f['capture_file'].write_bytes(b'{"ready":true,"outcome":"PASS"}')
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])
    f['capture_file'].write_bytes(encoded(f['captured']))
    f['capture_file'].unlink()
    with pytest.raises(scopes.ScopeUnavailable):f['observer'](f['scope'])


def test_root_file_custody_is_required_without_a_test_override(tmp_path):
    path=tmp_path/'not-protected.json';path.write_bytes(b'{"claimed":"current"}');path.chmod(0o666)
    with pytest.raises(scopes.ScopeUnavailable):scopes._root_bytes(path)


def docker_rows(f):
    return {'Id':f['identity']['container_id'],'Image':f['image_id'],'State':{'Running':True,'Pid':777},
        'HostConfig':{'ReadonlyRootfs':True},'Mounts':[{'Destination':'/var/lib/ai4r-rsi-worker'}],
        'Config':{'Env':['PYTHONPATH=/opt/ai4r']}}, {
        'Id':f['image_id'],'RepoDigests':['controlled@'+f['digest']],'Os':'linux','Architecture':'amd64'}


def test_host_builder_uses_actual_inspection_identity_and_returns_data_only(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);container,image=docker_rows(f);calls=[]
    def inspect(arguments):
        calls.append(arguments);return container if arguments[0]=='container' else image
    monkeypatch.setattr(scopes,'_docker_json',inspect)
    before=f['capture_file'].read_bytes()
    value=scopes.build_runtime_observation(container_id=f['identity']['container_id'],approved_scope=f['scope'],public_reader=f['public'])
    assert value==f['captured'] and f['capture_file'].read_bytes()==before
    assert calls==[['container','inspect',f['identity']['container_id']],['image','inspect',f['image_id']]]


@pytest.mark.parametrize('change',['image','namespace','source_mount','python_path'])
def test_host_builder_rejects_unobserved_image_namespace_or_source_overlay(tmp_path,monkeypatch,change):
    f=fixture(tmp_path,monkeypatch);container,image=docker_rows(f)
    if change=='image':image['RepoDigests']=[]
    elif change=='namespace':
        monkeypatch.setattr(scopes,'_identity',lambda *a,**k:dict(f['identity'],container_id='9'*64))
    elif change=='source_mount':container['Mounts']=[{'Destination':'/opt/ai4r/jiuwenswarm'}]
    else:container['Config']['Env']=['PYTHONPATH=/var/lib/foreign-code']
    monkeypatch.setattr(scopes,'_docker_json',lambda args:container if args[0]=='container' else image)
    with pytest.raises(scopes.ScopeUnavailable):
        scopes.build_runtime_observation(container_id=f['identity']['container_id'],approved_scope=f['scope'],public_reader=f['public'])


def test_docker_command_is_finite_and_provider_stderr_never_escapes(monkeypatch):
    calls=[]
    def run(command,**kwargs):
        calls.append((command,kwargs))
        return subprocess.CompletedProcess(command,1,stdout=b'PRIVATE-DIAGNOSTIC',stderr=b'PRIVATE-CREDENTIAL')
    monkeypatch.setattr(scopes.subprocess,'run',run)
    with pytest.raises(scopes.ScopeUnavailable) as error:scopes._docker_json(['container','inspect','a'*64])
    assert 'PRIVATE' not in str(error.value)
    assert calls[0][0][:3]==['/usr/bin/docker','--host','unix:///var/run/docker.sock']
    assert set(calls[0][1]['env'])=={'PATH','LANG'}
