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


# --------------------------------------------------------------------------
# Durable slots: grant horizon, terminal publication, revision preparation.
# --------------------------------------------------------------------------
slot_spec = importlib.util.spec_from_file_location('capsule_slot', Path(__file__).parents[3]/'deploy/m1/rsi_capsule_slot.py')
slot = importlib.util.module_from_spec(slot_spec); slot_spec.loader.exec_module(slot)
LOOP_GRANT = 'ai4r-rsi-whole-capsule-development-grant:3'


def loop_cfg(expires, *, schema=LOOP_GRANT, loop=None):
    session = {'grant': {'schema': schema, 'expires_unix_s': expires, 'limits': {'wall_s': 1200}}}
    if loop is not None: session['loop'] = loop
    return {'session': session}


def test_loop_grant_must_cover_whole_run_while_finite_v2_grant_is_unchanged():
    now = 1_000_000
    legacy = loop_cfg(now + 60, schema='ai4r-rsi-whole-capsule-development-grant:2')
    launcher.grant_ready(legacy['session']['grant'], legacy, now)  # Historical single check.
    assert launcher.run_deadline_s(legacy) == launcher.LEGACY_WAIT_S == 3700
    cfg = loop_cfg(now + 60, loop={'model_backend': {'kind': 'fake'}, 'per_call_s': 200})
    deadline = launcher.run_deadline_s(cfg)
    assert deadline == 1200 + 2 * 200 + 60 + 120
    assert deadline == slot.run_deadline_s(cfg['session']['grant'], cfg['session']['loop'])
    with pytest.raises(ValueError, match='CAPSULE_GRANT_HORIZON_BELOW_ONE_RUN'):
        launcher.grant_ready(cfg['session']['grant'], cfg, now)
    covered = loop_cfg(now + deadline, loop=cfg['session']['loop'])
    launcher.grant_ready(covered['session']['grant'], covered, now)
    with pytest.raises(ValueError, match='CAPSULE_GRANT_EXPIRED'):
        launcher.grant_ready(covered['session']['grant'], covered, now + deadline)


@pytest.mark.parametrize('case', ['result', 'resultless', 'failure'])
def test_every_known_stopped_worker_is_published_from_retained_evidence(tmp_path, monkeypatch, case):
    monkeypatch.setattr(launcher, 'pinned', lambda value: Path(value['path']))
    result = tmp_path / 'capsule-result.json'
    if case != 'resultless': result.write_text('{}')
    calls = []
    class Publisher:
        def publish_completed(self, template):
            calls.append(('completed', template))
            if case == 'failure': raise ValueError('ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS')
            return {'publication_sha256': 'a'*64, 'model_calls': 0}
        def publish_worker_terminal(self, template):
            calls.append(('worker', template)); return {'publication_sha256': 'b'*64, 'model_calls': 0}
    value = {'id': 'unit', 'publication_template': {'path': str(tmp_path / 'template.json'), 'sha256': 'c'*64}}
    failed = launcher.publish_terminal(value, {'result_path': str(result)}, tmp_path, load_publisher=lambda v, c: Publisher())
    assert calls == [('worker' if case == 'resultless' else 'completed', tmp_path / 'template.json')]
    assert failed is (case == 'failure')
    if failed:
        record = json.loads((tmp_path / 'publication-failure.json').read_text())
        assert record['reexecuted'] is False and record['message'] == 'ROOT_TERMINAL_EXECUTION_COUNT_DIFFERS'
        assert not (tmp_path / 'publication-receipt.json').exists()
    else:
        assert json.loads((tmp_path / 'publication-receipt.json').read_text())['model_calls'] == 0


PREPARE_FIELDS = {'schema', 'core_root', 'input_root', 'record_root', 'native_lease_root', 'account_root', 'account_id',
    'preparation_claim', 'output_path', 'exact_binding_refs', 'work_capsule_refs', 'grant', 'runtime_manifest',
    'parent_body', 'parent_declaration', 'visible_context', 'request_text', 'observed_symptom', 'loop'}


@pytest.fixture
def template(tmp_path, monkeypatch):
    import hashlib
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
    monkeypatch.setattr(slot, 'custody', lambda path, owner=0, directory=False: Path(path) if Path(path).exists() else
                        (_ for _ in ()).throw(ValueError('ROOT_INPUT_KIND_DIFFERS: ' + str(path))))
    name = 'utility.calculate'; target = registered_capsule(name)
    runtime = tmp_path / 'runtime'; carrier = runtime / 'source/jiuwenswarm' / target.carrier_path
    carrier.parent.mkdir(parents=True); parent = b'# synthetic parent, never executed\n'; carrier.write_bytes(parent)
    manifest = {'files': [{'path': 'source/jiuwenswarm/' + target.carrier_path, 'sha256': hashlib.sha256(parent).hexdigest()}],
                'python': {'version': [3, 13, 0], 'executable_sha256': 'e'*64}}
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    source = tmp_path / 'src'; (source / 'jiuwenswarm/research').mkdir(parents=True)
    (source / 'jiuwenswarm/__init__.py').write_text(''); (source / 'jiuwenswarm/research/mod.py').write_text('x = 1\n')
    for name_ in ('runner.py', 'composition.py'): (source / name_).write_text('# ' + name_)
    admin = tmp_path / 'admin'; admin.mkdir()
    for name_ in ('launcher.py', 'restore.py', 'seccomp.json', 'publisher.py', 'projection.py'): (admin / name_).write_text(name_)
    for key in ('namespace', 'control', 'evidence'): (tmp_path / key).mkdir()
    value = {'schema': slot.TEMPLATE, 'target_id': name, 'slot_id': 'unit-calculate-dev', 'state_root': str(tmp_path / 'state'),
        'roots': {key: str(tmp_path / key) for key in ('namespace', 'control', 'evidence')},
        'composition': {'core_root': '/srv/core', 'input_root': '/srv/input', 'native_lease_root': '/srv/leases',
            'account_root': '/srv/account', 'principal': {'account_id': 'unit:human'}, 'account_id': 'unit:human',
            'exact_binding_refs': {'configuration_ref': {'id': 'c.json', 'sha256': 'c'*64}}, 'work_capsule_refs': {'intent': 'i'}},
        'evaluator': {'runtime_root': str(runtime), 'manifest_path': str(tmp_path / 'manifest.json'),
            'metadata': {'contract': {'unit': 'contract'}, 'environment': {'unit': 'env'}, 'hardware': {'unit': 'hw'}},
            'cgroup_root': '/sys/fs/cgroup/ai4r-rsi-host/jobs/unit-calculate-dev'},
        'grant': {'limits': {'timeout_s': 20, 'memory_mb': 256, 'pids_max': 64, 'wall_s': 1200}, 'iterations': 1,
                  'horizon_s': 7 * 24 * 3600},
        'loop': {'model_backend': {'kind': 'fake'}, 'max_iterations': 3, 'trials': 2},
        'prepare': {'source_root': str(source), 'parent_declaration': {'identity': {'name': name}},
                    'request_text': 'Improve the capsule.', 'observed_symptom': 'Public baseline only.'},
        'run': {'source_root': str(source), 'runner': str(source / 'runner.py'), 'composition_path': str(source / 'composition.py')},
        'launcher': {key: str(admin / file) for key, file in (('launcher', 'launcher.py'), ('restore', 'restore.py'),
            ('seccomp', 'seccomp.json'), ('publisher', 'publisher.py'), ('projection', 'projection.py'))},
        'publication': {'meta': {'target_id': name, 'workspace_id': 'local'}, 'publication_directory': str(tmp_path / 'public')},
        'container': {'image': 'sha256:' + '1'*64, 'step_timeout_s': 600}}
    steps = []
    def run_step(step, argv, control):
        steps.append((step, argv, control))
        configuration = json.loads(Path(argv[argv.index('--configuration') + 1]).read_text())
        if step == 'prepare':
            session = {'id': configuration['grant']['run_id'], 'grant': configuration['grant'],
                       'loop': dict(configuration['loop'], contracts=[])}
            Path(configuration['output_path']).write_text(json.dumps({'schema': 'ai4r-rsi-capsule-prepared:1',
                'session': session, 'run_contexts': {'rsi-development:' + session['id'] + ':diagnosis': {}}, 'model_calls': 0}))
        else:
            scratch = Path(argv[argv.index('--scratch-root') + 1])
            (scratch / 'doctor-result.json').write_text(json.dumps({'status': 'COMPATIBLE', 'model_calls': 0, 'execution_jobs': 0}))
    return {'value': value, 'run_step': run_step, 'steps': steps, 'tmp': tmp_path, 'source': source, 'admin': admin}


def test_durable_revision_derives_loop_grant_and_pins_from_current_files(template):
    import hashlib
    from jiuwenswarm.research_rsi.targets.capsule_executor import loop_execution_budget, grant_fixtures
    t = template; now = 1_800_000_000
    payload = slot.prepare_revision(t['value'], 1, 'unit-calculate-dev-r1', run_step=t['run_step'], now=now, chown=False)
    control = t['tmp'] / 'control/unit-calculate-dev-r1'
    grant = json.loads((control / 'grant.json').read_text())
    cases = len(grant_fixtures(grant))
    assert grant['schema'] == LOOP_GRANT and grant['run_id'] == 'unit-calculate-dev-r1'
    assert grant['max_executions'] == loop_execution_budget(cases, max_iterations=3, trials=2) == cases * (3 + 2 * 3)
    assert grant['expires_unix_s'] == now + 7 * 24 * 3600 and payload['expires_unix_s'] == grant['expires_unix_s']
    prepare = json.loads((control / 'prepare-configuration.json').read_text())
    assert set(prepare) == PREPARE_FIELDS and prepare['grant'] == grant and prepare['loop'] == t['value']['loop']
    assert prepare['record_root'] == str(t['tmp'] / 'namespace/unit-calculate-dev-r1/records')
    run = json.loads((control / 'run-configuration.json').read_text())
    def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    assert run['source_pins'] == {'jiuwenswarm/__init__.py': digest(t['source'] / 'jiuwenswarm/__init__.py'),
                                  'jiuwenswarm/research/mod.py': digest(t['source'] / 'jiuwenswarm/research/mod.py')}
    assert run['composition_sha256'] == digest(t['source'] / 'composition.py')
    assert run['compatibility'] == {'path': str(control / 'compose-doctor.json'), 'sha256': digest(control / 'compose-doctor.json')}
    from deploy.m1.rsi_capsule_run import compose_doctor_scope
    doctor = json.loads((control / 'doctor-configuration.json').read_text())
    assert compose_doctor_scope(doctor) == compose_doctor_scope(run) and doctor['compatibility']['sha256'] == '0'*64
    assert run['evaluator']['grant_sha256'] == digest(control / 'grant.json') == payload['grant_sha256']
    assert run['claim_path'] == str(control / 'claim/session-claim.json') and run['evaluator']['root'].endswith('unit-calculate-dev-r1')
    launch = json.loads((control / 'launcher-configuration.json').read_text())
    assert set(launch) == launcher.FIELDS and launch['schema'] == 'ai4r-rsi-capsule-launcher:1'
    assert launch['launcher_sha256'] == digest(t['admin'] / 'launcher.py')
    assert launch['configuration'] == payload['configuration'] == {'path': str(control / 'run-configuration.json'),
                                                                    'sha256': digest(control / 'run-configuration.json')}
    publication = json.loads((control / 'publication-template.json').read_text())
    assert publication['projection'] == {'path': str(t['admin'] / 'projection.py'), 'sha256': digest(t['admin'] / 'projection.py')}
    assert payload['wall_s'] == launcher.run_deadline_s(run) and payload['model_calls'] == 0
    (prepare_name, prepare_argv, _), (doctor_name, doctor_argv, _) = t['steps']
    assert prepare_name == 'prepare' and prepare_argv[prepare_argv.index('--user') + 1] == '12001:12001'
    assert prepare_argv[prepare_argv.index('--network') + 1] == 'none' and '--cap-add' not in prepare_argv
    mounts = [prepare_argv[i + 1] for i, a in enumerate(prepare_argv) if a == '--mount']
    assert f"type=bind,src={t['source']},dst={t['source']},readonly" in mounts
    doctor_mounts = [doctor_argv[i + 1] for i, a in enumerate(doctor_argv) if a == '--mount']
    for key in ('core_root', 'input_root', 'native_lease_root', 'account_root'):
        path = t['value']['composition'][key]
        assert f'type=bind,src={path},dst={path},readonly' in doctor_mounts  # Doctor originals stay read-only.
    # A revision never reuses directories; a successor derives fresh pins.
    with pytest.raises(ValueError, match='FRESH_REVISION_DIRECTORY_REQUIRED_NO_REUSE'):
        slot.prepare_revision(t['value'], 1, 'unit-calculate-dev-r1', run_step=t['run_step'], now=now, chown=False)
    (t['source'] / 'jiuwenswarm/research/mod.py').write_text('x = 2\n')
    second = slot.prepare_revision(t['value'], 2, 'unit-calculate-dev-r2', run_step=t['run_step'], now=now + 10, chown=False)
    assert second['source_pins_sha256'] != payload['source_pins_sha256'] and second['configuration'] != payload['configuration']


@pytest.mark.parametrize('change', ['builder', 'local-cgroup', 'runner-outside', 'horizon'])
def test_durable_template_is_closed_and_general(template, change):
    t = template; value = json.loads(json.dumps(t['value']))
    if change == 'builder': value['target_id'] = 'research.builder'
    if change == 'local-cgroup': value['evaluator']['cgroup_root'] = '/sys/fs/cgroup/other'
    if change == 'runner-outside': value['run']['runner'] = str(t['admin'] / 'launcher.py')
    if change == 'horizon': value['grant']['horizon_s'] = 600
    with pytest.raises(Exception):
        slot.prepare_revision(value, 1, 'unit-calculate-dev-r1', run_step=t['run_step'], now=1, chown=False)
    assert t['steps'] == [] and not (t['tmp'] / 'control/unit-calculate-dev-r1').exists()


@pytest.mark.parametrize('outside', ['sibling', 'admin', 'source-root-itself'])
def test_frozen_composition_must_lie_inside_the_only_mounted_source_root(template, outside):
    t = template; value = json.loads(json.dumps(t['value']))
    composition = {'sibling': t['tmp'] / 'composition.py', 'admin': t['admin'] / 'publisher.py',
                   'source-root-itself': t['source']}[outside]
    if outside == 'sibling': composition.write_text('# outside the mounted source root')
    value['run']['composition_path'] = str(composition)
    with pytest.raises(ValueError, match='COMPOSITION_OUTSIDE_SOURCE_ROOT: ' + str(composition)):
        slot.validate_template(value)
    with pytest.raises(ValueError, match='COMPOSITION_OUTSIDE_SOURCE_ROOT'):
        slot.prepare_revision(value, 1, 'unit-calculate-dev-r1', run_step=t['run_step'], now=1, chown=False)
    assert t['steps'] == [] and not (t['tmp'] / 'control/unit-calculate-dev-r1').exists()
    nested = dict(value, run=dict(value['run'], composition_path=str(t['source'] / 'deploy/m1/x.py')))
    assert slot.validate_template(nested) == nested  # Anywhere under source_root is mounted.


def test_preparation_persists_closure_proofs_and_template_launcher_timeouts(template):
    import shutil
    t = template; value = json.loads(json.dumps(t['value']))
    doctor_path = t['source'] / slot.DOCTOR_SOURCE; doctor_path.parent.mkdir(parents=True)
    shutil.copyfile(Path(__file__).parents[3] / slot.DOCTOR_SOURCE, doctor_path)
    (t['source'] / 'jiuwenswarm/research_rsi/__init__.py').write_text('')
    (t['source'] / 'jiuwenswarm/research_rsi/host_codex_backend.py').write_text('descriptor = None\n')
    (t['source'] / 'jiuwenswarm/research/__init__.py').write_text('from . import mod\n')
    value['launcher']['timeouts'] = {'runner_preflight_s': 60}
    slot.prepare_revision(value, 1, 'unit-calculate-dev-r1', run_step=t['run_step'], now=1_800_000_000, chown=False)
    proofs = sorted((t['source'] / '.ai4r-source-closure').glob('*.json'))
    assert len(proofs) == 2  # Controller/doctor entry set and launcher (runner + composition) entry set.
    control = t['tmp'] / 'control/unit-calculate-dev-r1'
    launch = json.loads((control / 'launcher-configuration.json').read_text())
    assert set(launch) == launcher.FIELDS | {'timeouts'} and launcher.timeouts(launch) == {'runner_preflight_s': 60, 'docker_s': 45}
    assert launcher.timeouts({}) == {'runner_preflight_s': 30, 'docker_s': 45}  # Historical defaults.
    with pytest.raises(ValueError, match='CLOSED_LAUNCHER_TIMEOUTS_REQUIRED'):
        launcher.timeouts({'timeouts': {'runner_preflight_s': 0}})
    value['launcher']['timeouts'] = {'unknown_s': 5}
    with pytest.raises(ValueError, match='CLOSED_LAUNCHER_TIMEOUTS_REQUIRED'):
        slot.validate_template(value)
    # The runner's controller preflight reuses the persisted proof.
    run = json.loads((control / 'run-configuration.json').read_text())
    from jiuwenswarm.research_rsi import capsule_doctor
    key = capsule_doctor.closure_proof_key(run['source_pins'], entry_files=[run['composition_path']])
    assert capsule_doctor.read_closure_proof(t['source'], run['source_pins'], key)['complete'] is True


class FakeDocker:
    """Fake Root docker client: containers run until stopped (or never)."""
    def __init__(self, image, *, exits_on_stop=True, finishes=False):
        import subprocess
        self.subprocess, self.image, self.calls, self.containers = subprocess, image, [], {}
        self.exits_on_stop, self.finishes = exits_on_stop, finishes

    def __call__(self, *args):
        self.calls.append(args)
        verb = args[0]
        if verb == 'create':
            cid = '%064x' % (len(self.containers) + 1)
            self.containers[cid] = {'name': '/' + args[args.index('--name') + 1], 'running': False, 'code': None}
            return cid.encode()
        ident = args[-1]
        cid = next((key for key, row in self.containers.items() if ident in (key, row['name'][1:])), None)
        if cid is None:
            raise self.subprocess.CalledProcessError(1, args, b'', b'Error: No such container: ' + ident.encode())
        row = self.containers[cid]
        if verb == 'start': row['running'] = not self.finishes; row['code'] = 0 if self.finishes else None
        if verb in ('stop', 'kill') and self.exits_on_stop: row['running'] = False; row['code'] = 137
        if verb == 'logs': return b'step output'
        if verb == 'inspect':
            return json.dumps([{'Id': cid, 'Image': self.image, 'Name': row['name'], 'State': {
                'Running': row['running'], 'Pid': 4242 if row['running'] else 0, 'ExitCode': row['code'] or 0}}]).encode()
        return b''


def container_steps(tmp_path, monkeypatch, docker, *, timeout=600, wall=None):
    monkeypatch.setattr(slot, 'custody', lambda path, owner=0, directory=False: Path(path))
    now = [0.0]
    def sleep(seconds): now[0] += seconds
    template = {'container': {'image': 'sha256:' + '1'*64, 'step_timeout_s': timeout}}
    control = tmp_path / 'control/unit-r1'; control.mkdir(parents=True)
    steps = slot.ContainerSteps(template, tmp_path / 'control', docker, clock=lambda: now[0], sleep=sleep,
                                wall=wall or (lambda: 1_000_000 + now[0]))
    argv = ['create', '--name', 'ai4r-capsule-prepare-unit-r1', 'sha256:' + '1'*64, '-B', '-m', 'deploy.m1.rsi_capsule_prepare']
    return steps, control, argv, now


def test_overdue_preparation_step_is_stopped_by_recorded_id_before_it_is_failed(tmp_path, monkeypatch):
    docker = FakeDocker('sha256:' + '1'*64)
    steps, control, argv, now = container_steps(tmp_path, monkeypatch, docker, timeout=30)
    with pytest.raises(ValueError, match='STEP_DEADLINE_EXPIRED_STOPPED_NO_REPLAY: prepare'):
        steps('prepare', argv, control)
    record = json.loads((control / 'prepare-container.json').read_text())
    cid = record['cid']
    assert record['name'] == 'ai4r-capsule-prepare-unit-r1' and record['timeout_s'] == 30
    verbs = [call[0] for call in docker.calls]
    assert verbs.index('stop') < len(verbs) - 1 and docker.calls[verbs.index('stop')][-1] == cid
    assert not docker.containers[cid]['running']  # Proven stopped before the failure is reported.
    exit_ = json.loads((control / 'prepare-exit.json').read_text())
    assert exit_['stopped'] == 'STEP_DEADLINE_EXPIRED' and exit_['cid'] == cid and exit_['exit_code'] == 137
    assert steps.reconcile(control) is None  # Nothing left running for a successor to race.


def test_unstoppable_step_is_never_reported_stopped(tmp_path, monkeypatch):
    docker = FakeDocker('sha256:' + '1'*64, exits_on_stop=False)
    steps, control, argv, now = container_steps(tmp_path, monkeypatch, docker, timeout=30)
    with pytest.raises(ValueError, match='STEP_TERMINATION_UNPROVEN_RECONCILE_NO_REPLAY'):
        steps('prepare', argv, control)
    assert [call[0] for call in docker.calls].count('kill') == 1 and not (control / 'prepare-exit.json').exists()
    # After a restart the slot keeps waiting on it: the container is still running.
    with pytest.raises(ValueError, match='STEP_TERMINATION_UNPROVEN_RECONCILE_NO_REPLAY'):
        steps.reconcile(control)


def test_restart_reconcile_waits_for_running_step_then_adopts_its_terminal_state(tmp_path, monkeypatch):
    docker = FakeDocker('sha256:' + '1'*64)
    wall = [1_000_000]
    steps, control, argv, now = container_steps(tmp_path, monkeypatch, docker, timeout=600, wall=lambda: wall[0])
    # A broker died mid-step: claim and container record exist, no exit.
    slot.write_exclusive(control / 'prepare-claim.json', {'schema': slot.STEP_SCHEMA, 'step': 'prepare', 'argv': argv})
    cid = docker(*argv).decode(); docker('start', cid)
    slot.write_exclusive(control / 'prepare-container.json', {'schema': slot.STEP_SCHEMA, 'step': 'prepare', 'cid': cid,
        'name': 'ai4r-capsule-prepare-unit-r1', 'started_unix_s': wall[0], 'timeout_s': 600})
    assert steps.reconcile(control) == 'PREPARATION_STEP_STILL_RUNNING: prepare'
    assert docker.containers[cid]['running'] and 'stop' not in [c[0] for c in docker.calls]  # Within its deadline: wait.
    docker.containers[cid].update(running=False, code=3)  # It finished on its own.
    assert steps.reconcile(control) is None
    adopted = json.loads((control / 'prepare-exit.json').read_text())
    assert adopted['adopted'] == 'AFTER_INTERRUPTION' and adopted['exit_code'] == 3 and adopted['cid'] == cid
    # Overdue after a restart: stopped by its recorded id, then adopted.
    doctor_argv = ['create', '--name', 'ai4r-capsule-doctor-unit-r1', 'sha256:' + '1'*64]
    slot.write_exclusive(control / 'doctor-claim.json', {'schema': slot.STEP_SCHEMA, 'step': 'doctor', 'argv': doctor_argv})
    second = docker(*doctor_argv).decode(); docker('start', second)  # Created, its record never written.
    wall[0] += 601 + int((control / 'doctor-claim.json').stat().st_mtime) - 1_000_000
    assert steps.reconcile(control) is None
    assert ('stop', '--time', '10', second) in docker.calls and not docker.containers[second]['running']
    assert json.loads((control / 'doctor-exit.json').read_text())['adopted'] == 'AFTER_INTERRUPTION'
    # Claimed but never created (died before docker create): nothing ran.
    other = tmp_path / 'control/unit-r2'; other.mkdir()
    slot.write_exclusive(other / 'prepare-claim.json', {'schema': slot.STEP_SCHEMA, 'step': 'prepare',
        'argv': ['create', '--name', 'ai4r-capsule-prepare-unit-r2']})
    assert steps.reconcile(other) is None and not (other / 'prepare-exit.json').exists()
    assert steps.reconcile(tmp_path / 'control/never-made') is None
