"""Controlled installation/transport wiring, never thirteen-case qualification."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import stat
import struct

import pytest

from jiuwenswarm.research.contracts import rsi_installation as installation
from jiuwenswarm.research.contracts.types import ResearchError
from jiuwenswarm.research_rsi.records import encoded


def fixture(tmp_path,monkeypatch):
    root=tmp_path/'root-installation';root.mkdir();originals=root/'originals';originals.mkdir()
    monkeypatch.setattr(installation,'ROOT',root)
    monkeypatch.setattr(installation,'INSTALLATION_FILE',root/'installation.json')
    monkeypatch.setattr(installation,'ORIGINALS_ROOT',originals)
    monkeypatch.setattr(installation,'RUNTIME_OBSERVATION_FILE',root/'runtime-observation.json')
    rows=[];objects={}
    def put(value,kind):
        raw=encoded(value) if not isinstance(value,bytes) else value
        digest=hashlib.sha256(raw).hexdigest();pin={'id':digest+'.json','sha256':digest}
        (originals/(digest+'.bytes')).write_bytes(raw)
        rows.append({'ref':pin,'kind':kind});objects[encoded(pin)]=raw
        return pin
    item=put({'controlled':'non-authoritative original'},'controlled-original')
    scope=put({'schema':'ai4r-rsi-security-scope:1','id':'controlled:scope','runtime_build_ref':item,
        'environment_ref':item,'worker_driver_ref':item,'executor_ref':item,'probe_ref':item,
        'kernel_release':'controlled-kernel','platform':'linux/amd64','worker_profile_refs':[item]},'rsi-security-scope')
    qualification=put({'schema':'ai4r-rsi-security-qualification:1','id':'controlled:incomplete-qualification',
        'scope_ref':scope,'verification_receipt_ref':item,'artifact_refs':[{'path':'unit.raw','ref':item}],
        'case_evidence_refs':{'RSIV-'+str(i):[item] for i in range(1,14)}},'rsi-security-qualification')
    assertions=put({'controlled':'independent assertions placeholder'},'security-assertion-manifest')
    attacks=put({'controlled':'attack pins placeholder'},'security-attack-pins')
    profile=put({'assertion_manifest_ref':assertions,'attack_pins_ref':attacks,'worker_profile_refs':[item]},'security-profile-pins')
    observation={'schema':'ai4r-rsi-runtime-observation:1','runtime_build_ref':item,'environment_ref':item,
        'worker_profile_refs':[item],'container_id':'a'*64,'image_id':'sha256:'+'b'*64,'image_digest':'sha256:'+'c'*64,
        'pid_namespace':'pid:[1]','mount_namespace':'mnt:[2]','boot_id':'12345678-1234-1234-1234-123456789abc',
        'kernel_release':'controlled-kernel','platform':'linux/amd64','init_start_ticks':10,'read_only_rootfs':True}
    observation_ref=put(observation,'rsi-runtime-observation')
    (root/'runtime-observation.json').write_bytes(encoded(observation))
    value={'schema':'ai4r-rsi-security-installation:1','qualification_ref':qualification,'scope_ref':scope,
        'validation_profile_ref':profile,'assertion_manifest_ref':assertions,'attack_pins_ref':attacks,
        'runtime_observation_ref':observation_ref,'custodian_key_id':'controlled:custodian',
        'custodian_public_key':base64.urlsafe_b64encode(b'x'*32).decode().rstrip('='),
        'rpc_session_id':'controlled:scope-rpc','rpc_capability':'A'*64,'originals':rows}
    (originals/'original-byte-index.json').write_bytes(encoded({'schema':'ai4r-original-bytes:1',
        'refs':{row['ref']['id']:row['ref']['sha256'] for row in rows}}))
    manifest=root/'installation.json';manifest.write_bytes(encoded(value))
    # Data/IPC tests do not claim real root:GID13000 publication. Production
    # custody has a separate fail-closed control below and no override API.
    def controlled_file(path,maximum):
        assert not Path(path).is_symlink()
        raw=Path(path).read_bytes();assert 0<len(raw)<=maximum
        return raw
    monkeypatch.setattr(installation,'_root_file',controlled_file)
    loaded=installation.SecurityInstallation(manifest.read_bytes())
    return dict(root=root,originals=originals,value=value,loaded=loaded,item=item,
        scope=loaded.scope,manifest=manifest,objects=objects)


def test_fixed_installation_absence_preserves_unavailable_authority(tmp_path,monkeypatch):
    monkeypatch.setattr(installation,'INSTALLATION_FILE',tmp_path/'absent.json')
    assert installation.load_installation() is None
    assert installation.installed_consumer_qualification() is None
    assert installation.installation_public_roots()==()


def test_closed_loader_reads_only_root_indexed_exact_originals(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);loaded=f['loaded']
    assert loaded.read(f['item'])==f['objects'][encoded(f['item'])]
    assert loaded.record_kind(f['item'])=='controlled-original'
    with pytest.raises(installation.InstallationUnavailable):loaded.read(dict(f['item'],id='../../unindexed'))
    invalid=dict(f['value'],factory='arbitrary.module:factory')
    f['manifest'].write_bytes(encoded(invalid))
    with pytest.raises((installation.InstallationUnavailable,ResearchError)):
        installation.SecurityInstallation(f['manifest'].read_bytes())


def test_changed_manifest_index_or_runtime_capture_cannot_silently_recompose(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);loaded=f['loaded'];original=f['manifest'].read_bytes()
    f['manifest'].write_bytes(encoded(dict(f['value'],rpc_capability='B'*64)))
    with pytest.raises(installation.InstallationUnavailable):loaded.assert_current()
    f['manifest'].write_bytes(original)
    index=f['originals']/'original-byte-index.json';raw=index.read_bytes();index.write_bytes(b'{}')
    with pytest.raises(installation.InstallationUnavailable):loaded.read(f['item'])
    index.write_bytes(raw)
    (f['root']/'runtime-observation.json').write_bytes(b'{"ready":true}')
    with pytest.raises(installation.InstallationUnavailable):loaded.current_runtime_observation()


def test_changed_original_and_caller_boolean_do_not_grant_authority(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    (f['originals']/(f['item']['sha256']+'.bytes')).write_bytes(b'{"qualified":true}')
    with pytest.raises(installation.InstallationUnavailable):f['loaded'].read(f['item'])
    with pytest.raises((installation.InstallationUnavailable,ResearchError)):
        installation.SecurityInstallation(b'{"ready":true,"qualified":true}')


def test_live_subject_overlay_cannot_shadow_root_typed_originals(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);calls=[];raw=b'controlled new candidate bytes'
    class Live:
        def read(self,pin):calls.append(pin);return raw
        def record_kind(self,pin):return 'controlled-live-subject'
    records=installation._QualificationRecords(f['loaded'],Live())
    assert records.record_kind(f['item'])=='controlled-original' and calls==[]
    changed=dict(f['item'],sha256=hashlib.sha256(raw).hexdigest())
    with pytest.raises(installation.InstallationUnavailable):records.read(changed)
    assert calls==[]
    current={'id':'controlled:new-live-body','sha256':hashlib.sha256(raw).hexdigest()}
    assert records.read(current)==raw and records.record_kind(current)=='controlled-live-subject'


def test_production_root_file_custody_rejects_world_writable_input(tmp_path):
    path=tmp_path/'not-installed.json';path.write_bytes(b'{"ready":true}');path.chmod(0o666)
    with pytest.raises(installation.InstallationUnavailable):installation._root_file(path,1024)


def connection(f,monkeypatch,*,peer=0,returned_scope=None):
    calls=[];scope=f['scope'] if returned_scope is None else returned_scope
    reply=encoded({'protocol':installation.SCOPE_PROTOCOL,'result':scope})
    class Socket:
        def __init__(self,*args):self.pending=struct.pack('!I',len(reply))+reply;calls.append(self);self.sent=None
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def settimeout(self,value):assert value==15
        def connect(self,path):assert path.replace('\\','/')=='/controlled/root-owned/scope.sock'
        def getsockopt(self,*args):return struct.pack('3i',777,peer,13000)
        def sendall(self,value):self.sent=value
        def recv(self,size):
            size=min(size,7);value=self.pending[:size];self.pending=self.pending[size:];return value
    monkeypatch.setattr(installation,'_scope_socket_path',lambda:Path('/controlled/root-owned/scope.sock'))
    monkeypatch.setattr(installation.socket,'SO_PEERCRED',17,raising=False)
    monkeypatch.setattr(installation.socket,'AF_UNIX',1,raising=False)
    monkeypatch.setattr(installation.socket,'socket',Socket)
    return calls


def test_consumer_observes_actual_producer_over_fresh_authenticated_connection_each_call(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch);calls=connection(f,monkeypatch)
    observer=installation.LiveProducerScopeObserver(f['loaded'])
    assert observer(f['scope'])==f['scope'] and observer(f['scope'])==f['scope']
    assert len(calls)==2
    for client in calls:
        length=struct.unpack('!I',client.sent[:4])[0]
        request=json.loads(client.sent[4:]);assert length==len(client.sent)-4
        assert request==f['loaded'].scope_request()
        assert request['operation']=='current_scope' and set(request['payload'])=={'scope_ref'}


@pytest.mark.parametrize('failure',['peer','scope'])
def test_consumer_rejects_foreign_root_peer_or_claimed_scope(tmp_path,monkeypatch,failure):
    f=fixture(tmp_path,monkeypatch)
    connection(f,monkeypatch,peer=12003 if failure=='peer' else 0,
        returned_scope=dict(f['scope'],kernel_release='stale') if failure=='scope' else None)
    with pytest.raises(installation.InstallationUnavailable):
        installation.LiveProducerScopeObserver(f['loaded'])(f['scope'])


def test_every_effect_recomputes_profile_and_constructs_full_independent_validator(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    from jiuwenswarm.research.contracts import rsi_security_cases
    profiles=[];authorities=[];cases=[]
    def current(self):profiles.append(True);return {'controlled_profile_revision':len(profiles)}
    monkeypatch.setattr(installation.InstalledQualification,'verification_profile',current)
    class Cases:
        def __init__(self,*args,**kwargs):cases.append(kwargs)
    class Authority:
        def __init__(self,read,pin,**kwargs):authorities.append(kwargs)
        def require(self,operation,**kwargs):return {'controlled_call':operation}
    monkeypatch.setattr(rsi_security_cases,'FiniteCaseObserver',Cases)
    monkeypatch.setattr(installation,'RSIQualification',Authority)
    guard=installation.InstalledQualification(f['loaded'],scope_observer=lambda _:pytest.fail('Controlled validator owns invocation'))
    for operation in ('session_start','proposal'):
        assert guard.require(operation,session_ref=f['item'])=={'controlled_call':operation}
    assert len(profiles)==len(authorities)==len(cases)==2
    assert [row['validation_profile']['controlled_profile_revision'] for row in authorities]==[1,2]
    assert all(row['public_key']==b'x'*32 and row['key_id']=='controlled:custodian' for row in authorities)
    # Altering an installed original still blocks before another owner runs.
    (f['root']/'runtime-observation.json').write_bytes(b'{"ready":true}')
    with pytest.raises(installation.InstallationUnavailable):guard.require('trial',session_ref=f['item'])


def test_incomplete_thirteen_case_data_cannot_become_real_qualification(tmp_path,monkeypatch):
    f=fixture(tmp_path,monkeypatch)
    guard=installation.InstalledQualification(f['loaded'],scope_observer=lambda scope:scope)
    with pytest.raises((ValueError,KeyError,ResearchError)):
        guard.require('session_start',session_ref=f['item'])


def test_side_current_scope_handler_calls_actual_observer_and_rejects_payload_expansion(tmp_path,monkeypatch):
    from jiuwenswarm.research_rsi import security_installation as side
    f=fixture(tmp_path,monkeypatch);calls=[]
    guard=side.WorkerInstalledQualification(f['loaded'],scope_observer=lambda scope:(calls.append(scope),copy.deepcopy(scope))[1])
    handler=side.current_scope_handler(guard)
    assert handler({'scope_ref':f['loaded'].scope_ref})==f['scope']
    assert calls==[f['scope']]
    with pytest.raises(installation.InstallationUnavailable):handler({'scope_ref':f['loaded'].scope_ref,'ready':True})
    with pytest.raises(installation.InstallationUnavailable):side.current_scope_handler(True)


def test_security_overlays_mount_only_qualification_data_and_scope_ipc_read_only_to_consumers():
    import yaml
    root=Path(__file__).resolve().parents[3]
    overlay=yaml.safe_load((root/'deploy/m1/compose.rsi.security.yaml').read_text())
    assert set(overlay['services'])=={'rsi-workbench','rsi-custodian','rsi-worker-broker'}
    for role,service in overlay['services'].items():
        for mount in service['volumes']:
            assert mount['target'] in {'/run/ai4r-rsi-security','/run/ai4r-rsi-security-ipc'}
            assert mount['bind']['create_host_path'] is False
            if role!='rsi-worker-broker' or mount['target']=='/run/ai4r-rsi-security':assert mount['read_only'] is True
    app=yaml.safe_load((root/'deploy/m1/compose.rsi.security-app.yaml').read_text())['services']['app']
    assert app['group_add']==['13000'] and all(row['read_only'] for row in app['volumes'])


def test_actual_root_original_reader_preserves_empty_artifact_without_accepting_empty_json(tmp_path):
    if os.name!='posix' or os.geteuid()!=0:return
    path=tmp_path/'empty.stderr';path.write_bytes(b'');os.chown(path,0,13000);path.chmod(0o640)
    assert installation._root_file(path,16)==b''
    with pytest.raises(ValueError):installation._json(installation._root_file(path,16))
