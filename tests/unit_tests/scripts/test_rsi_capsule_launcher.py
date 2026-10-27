"""Finite Docker carrier topology; never starts a container or inference."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import pytest

spec=importlib.util.spec_from_file_location('capsule_launcher',Path(__file__).parents[3]/'deploy/m1/rsi_capsule_launcher.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)


def test_worker_topology_is_closed_no_network_or_auth_and_exact_source(tmp_path,monkeypatch):
    monkeypatch.setattr(launcher,'protected',lambda p,**kw:Path(p))
    comp={key:str(tmp_path/key) for key in ('core_root','input_root','record_root','native_lease_root','account_root','work_root')}
    for path in comp.values():Path(path).mkdir()
    cfg={'composition':comp,'evaluator':{'root':str(tmp_path),'runtime_root':'/opt/runtime','grant_path':'/opt/admin/grant.json'},
        'source_root':'/opt/admin','claim_path':str(tmp_path/'claim.json'),'result_path':str(tmp_path/'result.json')}
    value={'id':'unit-capsule','seccomp':{'path':'/opt/admin/seccomp.json'},'runner':{'path':'/opt/admin/rsi_capsule_run.py'},
        'configuration':{'path':'/opt/admin/config.json','sha256':'a'*64},'cgroup_root':'/sys/fs/cgroup/ai4r-rsi-host/jobs/unit'}
    argv=launcher.worker_command(value,cfg)
    assert argv[argv.index('--network')+1]=='none' and '--read-only' in argv
    assert [argv[i+1] for i,a in enumerate(argv) if a=='--cap-add']==['SETUID','SETGID','CHOWN','FOWNER','DAC_OVERRIDE','KILL']
    assert argv[-9:]==[launcher.IMAGE,'-I','-B','/opt/admin/rsi_capsule_run.py','run','--configuration','/opt/admin/config.json','--configuration-sha256','a'*64]
    mounts=[argv[i+1] for i,a in enumerate(argv) if a=='--mount']
    assert 'type=bind,src=/opt/runtime,dst=/opt/runtime,readonly' in mounts
    assert not any('auth.json' in row or '/var/run/docker.sock' in row for row in mounts)
    assert any('dst=/sys/fs/cgroup/ai4r-rsi-host/jobs/unit' in row for row in mounts)
    proof={'path':'/opt/separate-doctors/actual-compose.json','sha256':'d'*64}
    observed=[]
    monkeypatch.setattr(launcher,'pinned',lambda value:observed.append(value) or Path(value['path']))
    cfg['compatibility']=proof
    verified=launcher.worker_command(value,cfg)
    assert observed==[proof]
    assert 'type=bind,src=/opt/separate-doctors/actual-compose.json,dst=/opt/separate-doctors/actual-compose.json,readonly' in verified


@pytest.mark.parametrize('version',[1,2,3])
def test_launcher_accepts_reviewed_original_and_compatibility_config_schemas_only(tmp_path,monkeypatch,version):
    monkeypatch.setattr(launcher,'os',SimpleNamespace(name='posix',geteuid=lambda:0))
    monkeypatch.setattr(launcher,'protected',lambda path,**kwargs:Path(path))
    monkeypatch.setattr(launcher,'pinned',lambda value:Path(value['path']))
    admin=tmp_path/'admin';admin.mkdir()
    group='/sys/fs/cgroup/ai4r-rsi-host/jobs/unit'
    cfg={'schema':'ai4r-rsi-capsule-run-configuration:'+str(version),'session':{'id':'unit'},
        'source_root':str(admin),'evaluator':{'cgroup_root':group}}
    cfg_path=tmp_path/'run.json';cfg_path.write_text(json.dumps(cfg))
    value={'schema':'ai4r-rsi-capsule-launcher:1','id':'unit','configuration':{'path':str(cfg_path),'sha256':'a'*64},
        'runner':{'path':str(admin/'runner.py'),'sha256':'b'*64},'control_directory':str(tmp_path),'cgroup_root':group,
        'launcher_sha256':launcher.sha(Path(launcher.__file__).read_bytes())}
    for key in ('restore','seccomp','publisher','publication_template'):value[key]={'path':str(admin/key),'sha256':'c'*64}
    path=tmp_path/'launcher.json';path.write_text(json.dumps(value))
    if version==3:
        with pytest.raises(ValueError,match='EXACT_SESSION_CONFIGURATION_REQUIRED'):
            launcher.load(path,launcher.sha(path.read_bytes()))
    else:
        assert launcher.load(path,launcher.sha(path.read_bytes()))[1]==cfg


def package_pins(root):
    import hashlib
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (root / 'jiuwenswarm').rglob('*')
            if p.is_file() and '__pycache__' not in p.parts and 'node_modules' not in p.parts}


def test_package_preflight_derives_closure_and_worker_traversal_before_any_claim(tmp_path, monkeypatch):
    import os, shutil, tempfile
    root = Path(__file__).parents[3]
    monkeypatch.setattr(launcher, 'protected', lambda path, **kw: Path(path))
    base = Path(tempfile.mkdtemp(prefix='launcher-preflight-'))
    try:
        base.chmod(0o711)
        evaluator = base / 'slot/evaluator'; evaluator.mkdir(parents=True); (base / 'slot').chmod(0o711)
        evaluator.chmod(0o700)  # Root-owned evidence root: correctable by the evaluator.
        runtime = base / 'runtime'; (runtime / 'source').mkdir(parents=True)
        (runtime / 'source/m.py').write_text('x'); runtime.chmod(0o755); (runtime / 'source').chmod(0o755)
        cfg = {'source_root': str(root), 'source_pins': package_pins(root),
               'composition_path': str(root / 'deploy/m1/rsi_development_run.py'),
               'evaluator': {'root': str(evaluator), 'runtime_root': str(runtime)}}
        value = {'runner': {'path': str(root / 'deploy/m1/rsi_capsule_run.py')}}
        ready = launcher.package_preflight(value, cfg)
        assert ready['source_closure']['complete'] and ready['source_closure']['module_count'] > 100
        assert ready['dispatcher'] == 'v18-bwrap'
        assert ready['worker_traversal'] == ('simulated' if os.geteuid() == 0 else 'static')
        # R1 shape: an incomplete package names the exact missing source.
        broken = dict(cfg, source_pins={k: v for k, v in cfg['source_pins'].items()
                                        if k != 'jiuwenswarm/research/local_model_codex.py'})
        with pytest.raises(ValueError, match='SOURCE_CLOSURE_INCOMPLETE: missing jiuwenswarm/research/local_model_codex.py'):
            launcher.package_preflight(value, broken)
        # R2 shape: an untraversable ancestor of the evidence root is reported.
        (base / 'slot').chmod(0o700)
        with pytest.raises(ValueError, match='WORKER_TRAVERSAL_BLOCKED: .*' + str(base / 'slot')):
            launcher.package_preflight(value, cfg)
        (base / 'slot').chmod(0o711); (runtime / 'source').chmod(0o711)
        with pytest.raises(ValueError, match='not_listable'):
            launcher.package_preflight(value, cfg)
    finally:
        shutil.rmtree(base)
