"""Root re-preparation of one durable capsule development slot revision.

A durable slot template (Root-owned, pinned by the broker configuration) names
only stable inputs: the registered capsule, its Root directory prefixes, the
shared isolated Core binding, the frozen runtime and the loop configuration.
Every per-revision value is derived here from the current files, never
hand-edited: the grant (``ai4r-rsi-whole-capsule-development-grant:3`` with
``max_executions = loop_execution_budget(...)``), the source closure pins, the
projection/launcher/runner pins, the preparation, run, launcher and
publication configurations. Preparation itself is the ordinary
``rsi_capsule_prepare`` path (new uploads, intake and ContractFactory work
contexts appended to the existing Core) and a model-free compose doctor, each
in its own finite container. Nothing is reset, rewritten or replayed: every
revision gets fresh directories, claims and journals; existing records stay.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

TEMPLATE = 'ai4r-rsi-capsule-durable-slot:1'
RUN_SCHEMA = 'ai4r-rsi-capsule-run-configuration:2'
PREPARE_SCHEMA = 'ai4r-rsi-capsule-prepare-configuration:1'
LAUNCHER_SCHEMA = 'ai4r-rsi-capsule-launcher:1'
PUBLICATION_SCHEMA = 'ai4r-capsule-completed-publication:1'
STEP_SCHEMA = 'ai4r-rsi-capsule-durable-step:1'
TEMPLATE_FIELDS = {'schema', 'target_id', 'slot_id', 'state_root', 'roots', 'composition', 'evaluator',
                   'grant', 'loop', 'prepare', 'run', 'launcher', 'publication', 'container'}
CONTROLLER = (12001, 12001)
SHARED_COMPOSITION = ('core_root', 'input_root', 'native_lease_root', 'account_root')


def need(value, reason):
    if not value: raise ValueError(reason)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf8')


def sha(raw): return hashlib.sha256(raw).hexdigest()


def absolute(path):
    path = Path(path)
    need(path.is_absolute() and '..' not in path.parts and ',' not in str(path), 'ABSOLUTE_ROOT_PATH_REQUIRED')
    return path


def custody(path, *, owner=0, directory=False):
    """Root custody of an existing input: no symlink, no group/other write."""
    path = absolute(path)
    for item in (path, *path.parents):
        meta = item.lstat()
        need(not stat.S_ISLNK(meta.st_mode) and not meta.st_mode & 0o022
             and meta.st_uid in ({0, owner} if item != path else {owner}), 'ROOT_INPUT_CUSTODY_DIFFERS: ' + str(item))
    meta = path.lstat()
    need(stat.S_ISDIR(meta.st_mode) if directory else stat.S_ISREG(meta.st_mode) and meta.st_nlink == 1,
         'ROOT_INPUT_KIND_DIFFERS: ' + str(path))
    return path


def file_pin(path):
    """Pin derived from the current Root-owned bytes."""
    path = custody(path)
    return {'path': str(path), 'sha256': sha(path.read_bytes())}


def source_pins(source_root):
    """Exact inventory the runner's ``load_sources`` requires: every file
    under ``<source_root>/jiuwenswarm`` with its current digest."""
    root = custody(source_root, directory=True)
    pins = {}
    for path in sorted((root / 'jiuwenswarm').rglob('*')):
        if path.is_symlink():
            raise ValueError('SOURCE_SYMLINK_REFUSED: ' + str(path))
        if path.is_file():
            pins[path.relative_to(root).as_posix()] = sha(path.read_bytes())
    need(pins, 'PINNED_SOURCE_CLOSURE_REQUIRED')
    return pins


def validate_template(value):
    need(isinstance(value, dict) and set(value) == TEMPLATE_FIELDS and value['schema'] == TEMPLATE,
         'CLOSED_DURABLE_SLOT_TEMPLATE_REQUIRED')
    need(isinstance(value['slot_id'], str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', value['slot_id']),
         'DURABLE_SLOT_IDENTITY_REQUIRED')
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
    need(registered_capsule(value['target_id']).public_evaluation_available, 'REGISTERED_EVALUATED_CAPSULE_REQUIRED')
    need(isinstance(value['roots'], dict) and set(value['roots']) == {'namespace', 'control', 'evidence'},
         'CLOSED_DURABLE_ROOTS_REQUIRED')
    for path in (value['state_root'], *value['roots'].values()): absolute(path)
    composition = value['composition']
    need(isinstance(composition, dict) and set(composition) == {*SHARED_COMPOSITION, 'principal', 'account_id',
         'exact_binding_refs', 'work_capsule_refs'}, 'CLOSED_SHARED_COMPOSITION_REQUIRED')
    for key in SHARED_COMPOSITION: absolute(composition[key])
    need(isinstance(value['evaluator'], dict) and set(value['evaluator']) == {
        'runtime_root', 'manifest_path', 'metadata', 'cgroup_root'}, 'CLOSED_DURABLE_EVALUATOR_REQUIRED')
    need(Path(value['evaluator']['cgroup_root']).is_relative_to('/sys/fs/cgroup/ai4r-rsi-host/jobs'),
         'EXACT_CAPSULE_CGROUP_REQUIRED')
    need(isinstance(value['evaluator']['metadata'], dict)
         and set(value['evaluator']['metadata']) == {'contract', 'environment', 'hardware'}, 'EXACT_WORKER_METADATA_REQUIRED')
    grant = value['grant']
    need(isinstance(grant, dict) and set(grant) == {'limits', 'iterations', 'horizon_s'}
         and type(grant['horizon_s']) is int and 0 < grant['horizon_s'] <= 400 * 24 * 3600, 'FINITE_DURABLE_GRANT_REQUIRED')
    need(isinstance(value['loop'], dict) and 'model_backend' in value['loop'] and 'contracts' not in value['loop'],
         'EXPLICIT_LOOP_CONFIGURATION_REQUIRED')
    need(isinstance(grant['limits'], dict) and type(grant['limits'].get('wall_s')) is int
         and grant['horizon_s'] > run_deadline_s(grant, value['loop']), 'DURABLE_HORIZON_BELOW_ONE_RUN')
    need(isinstance(value['prepare'], dict) and set(value['prepare']) == {
        'source_root', 'parent_declaration', 'request_text', 'observed_symptom'}, 'CLOSED_DURABLE_PREPARATION_REQUIRED')
    need(isinstance(value['run'], dict) and set(value['run']) == {'source_root', 'runner', 'composition_path'},
         'CLOSED_DURABLE_RUN_SOURCES_REQUIRED')
    need(Path(value['run']['runner']).parent == Path(value['run']['source_root']), 'RUNNER_SOURCE_ROOT_DIFFERS')
    need(isinstance(value['launcher'], dict) and set(value['launcher']) == {
        'launcher', 'restore', 'seccomp', 'publisher', 'projection'}, 'CLOSED_DURABLE_LAUNCHER_SOURCES_REQUIRED')
    publication = value['publication']
    need(isinstance(publication, dict) and set(publication) == {'meta', 'publication_directory'}
         and publication['meta'].get('target_id') == value['target_id'], 'CLOSED_DURABLE_PUBLICATION_REQUIRED')
    need(isinstance(value['container'], dict) and set(value['container']) == {'image', 'step_timeout_s'}
         and type(value['container']['step_timeout_s']) is int and 0 < value['container']['step_timeout_s'] <= 3600,
         'CLOSED_DURABLE_CONTAINER_STEPS_REQUIRED')
    return value


def load_template(pin):
    path = custody(pin['path'])
    raw = path.read_bytes()
    need(sha(raw) == pin['sha256'], 'DURABLE_SLOT_TEMPLATE_DIFFERS')
    return validate_template(json.loads(raw))


def revision_directories(template, run_id):
    roots = template['roots']
    namespace = Path(roots['namespace']) / run_id
    control = Path(roots['control']) / run_id
    return {'namespace': namespace, 'records': namespace / 'records', 'work': namespace / 'work',
            'prepare': namespace / 'prepare', 'control': control, 'claim': control / 'claim',
            'doctor': control / 'doctor-scratch', 'evidence': Path(roots['evidence']) / run_id}


def make_directories(dirs, *, chown=True):
    """Fresh per-revision directories; an existing one means a prior attempt
    and is never reused (a successor revision always has a new run id)."""
    owners = {'namespace': CONTROLLER, 'records': CONTROLLER, 'work': CONTROLLER, 'prepare': CONTROLLER,
              'control': (0, 0), 'claim': (0, 0), 'doctor': CONTROLLER, 'evidence': (0, 0)}
    modes = {'control': 0o700, 'claim': 0o700, 'evidence': 0o711}
    for key in ('namespace', 'records', 'work', 'prepare', 'control', 'claim', 'doctor', 'evidence'):
        path = dirs[key]
        need(not os.path.lexists(path), 'FRESH_REVISION_DIRECTORY_REQUIRED_NO_REUSE: ' + str(path))
        path.mkdir(mode=modes.get(key, 0o700))
        os.chmod(path, modes.get(key, 0o700))
        if chown: os.chown(path, *owners[key])


def write_exclusive(path, value, *, mode=0o444):
    raw = value if isinstance(value, bytes) else encoded(value)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw); stream.flush(); os.fchmod(stream.fileno(), mode); os.fsync(stream.fileno())
    directory = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(directory)
    finally: os.close(directory)
    return {'path': str(path), 'sha256': sha(raw)}


def loop_settings(loop):
    """Same documented defaults as ``rsi_capsule_prepare.loop_settings``."""
    defaults = {'max_iterations': 5, 'max_no_progress': 3, 'trials': 3}
    settings = {**defaults, **loop}
    for key in defaults:
        need(type(settings[key]) is int and 1 <= settings[key] <= 100, 'FINITE_LOOP_' + key.upper() + '_REQUIRED')
    return settings


def derive_grant(template, run_id, manifest, *, now):
    """Loop grant v3 bounded by its execution budget and a durable horizon."""
    from jiuwenswarm.research_rsi.records import encoded as canonical
    from jiuwenswarm.research_rsi.targets.capsule_executor import (LOOP_GRANT_SCHEMA, grant_fixtures,
        loop_execution_budget, validate_grant)
    from jiuwenswarm.research_rsi.targets.capsule_runtime import BOOTSTRAP_SCHEMA
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
    name = template['target_id']; target = registered_capsule(name)
    carrier = 'source/jiuwenswarm/' + target.carrier_path
    parent = next((row['sha256'] for row in manifest['files'] if row['path'] == carrier), None)
    need(parent is not None, 'EXACT_ORIGINAL_CAPSULE_PARENT_REQUIRED')
    loop = loop_settings(template['loop'])
    draft = {'schema': LOOP_GRANT_SCHEMA, 'capsule_name': name}
    fixtures = grant_fixtures(draft)
    metadata = template['evaluator']['metadata']
    grant = {'schema': LOOP_GRANT_SCHEMA, 'bootstrap_schema': BOOTSTRAP_SCHEMA, 'run_id': run_id,
        'capsule_name': name, 'runtime_manifest_sha256': sha(canonical(manifest)), 'parent_sha256': parent,
        'fixture_sha256': sha(canonical(fixtures)), 'fixture_count': len(fixtures), 'roles': ['parent', 'candidate'],
        'max_executions': loop_execution_budget(len(fixtures), max_iterations=loop['max_iterations'], trials=loop['trials']),
        'iterations': template['grant']['iterations'], 'limits': dict(template['grant']['limits']),
        'worker': {key + '_ref': {'id': sha(canonical(metadata[key])) + '.json', 'sha256': sha(canonical(metadata[key]))}
                   for key in ('contract', 'environment', 'hardware')},
        'expires_unix_s': int(now) + template['grant']['horizon_s'],
        'scope': 'public_m1_development_only', 'production_admission': 'UNKNOWN'}
    return validate_grant(grant, manifest)


def run_deadline_s(grant, loop):
    """Whole-run ceiling: the session hard timeout plus launcher slack
    (identical to ``rsi_capsule_launcher.run_deadline_s``)."""
    wall = min(grant['limits']['wall_s'], loop.get('wall_s', 3600))
    per_call = min(loop.get('per_call_s', 120), wall)
    return wall + 2 * per_call + 60 + 120


def visible_context(name):
    from jiuwenswarm.research_rsi.targets.capsules import public_fixtures, registered_capsule
    target = registered_capsule(name)
    return {'schema': 'ai4r-rsi-whole-capsule-public-context:1', 'capsule_name': name,
            'mutable_path': target.carrier_path, 'fixtures': public_fixtures(name),
            'metrics': list(target.metrics), 'labels': 'PUBLIC'}


def container_step(template, *, name, user, mounts, workdir, argv):
    """Finite no-network container command, same confinement as the worker."""
    image = template['container']['image']
    need(re.fullmatch(r'sha256:[0-9a-f]{64}', image), 'EXACT_STEP_IMAGE_REQUIRED')
    args = ['create', '--name', name, '--init', '--read-only', '--network', 'none', '--user', '%d:%d' % user,
            '--cap-drop', 'ALL']
    if user == (0, 0):
        for cap in ('SETUID', 'SETGID', 'CHOWN', 'FOWNER', 'DAC_OVERRIDE', 'KILL'): args += ['--cap-add', cap]
    args += ['--security-opt', 'no-new-privileges:true', '--security-opt', 'seccomp=' + template['launcher']['seccomp'],
             '--memory', '512m', '--memory-swap', '512m', '--pids-limit', '64', '--cpus', '2',
             '--tmpfs', '/tmp:rw,nosuid,nodev,size=64m', '--workdir', workdir, '--entrypoint', '/opt/venv/bin/python']
    for path, readonly in sorted(mounts.items()):
        absolute(path)
        args += ['--mount', f'type=bind,src={path},dst={path}' + (',readonly' if readonly else '')]
    return args + [image, *argv]


def prepare_step(template, dirs, configuration):
    comp = template['composition']
    mounts = {comp['core_root']: False, comp['input_root']: False, comp['native_lease_root']: False,
              comp['account_root']: True, str(dirs['records']): False, str(dirs['prepare']): False,
              template['prepare']['source_root']: True, configuration['path']: True}
    return container_step(template, name='ai4r-capsule-prepare-' + dirs['namespace'].name, user=CONTROLLER,
        mounts=mounts, workdir=template['prepare']['source_root'],
        argv=['-B', '-m', 'deploy.m1.rsi_capsule_prepare', '--configuration', configuration['path'],
              '--configuration-sha256', configuration['sha256']])


def doctor_step(template, dirs, configuration, run_cfg):
    comp = run_cfg['composition']
    mounts = {comp[key]: True for key in ('core_root', 'input_root', 'record_root', 'native_lease_root', 'account_root')}
    mounts.update({str(dirs['doctor']): False, run_cfg['source_root']: True,
                   run_cfg['evaluator']['runtime_root']: True, '/run/ai4r-rsi-host-codex': True, configuration['path']: True})
    return container_step(template, name='ai4r-capsule-doctor-' + dirs['namespace'].name, user=(0, 0),
        mounts=mounts, workdir='/',
        argv=['-I', '-B', template['run']['runner'], 'doctor', '--configuration', configuration['path'],
              '--configuration-sha256', configuration['sha256'], '--scratch-root', str(dirs['doctor'])])


def prepare_revision(template, sequence, run_id, *, run_step, now=None, chown=True):
    """Prepare one fresh durable revision; returns its pinned payload.

    ``run_step(name, argv, control)`` runs one finite container step to a
    known stop and raises unless it exited 0 (the Root implementation is
    ``ContainerSteps``). Every intermediate original is retained under the
    revision's control directory; a failure leaves them for inspection and a
    successor revision never reuses its directories or claims.
    """
    validate_template(template)
    now = int(time.time() if now is None else now)
    dirs = revision_directories(template, run_id)
    make_directories(dirs, chown=chown)
    evaluator = template['evaluator']
    manifest = json.loads(custody(evaluator['manifest_path']).read_bytes())
    grant = derive_grant(template, run_id, manifest, now=now)
    loop = loop_settings(template['loop'])
    deadline = run_deadline_s(grant, template['loop'])
    grant_pin = write_exclusive(dirs['control'] / 'grant.json', grant)
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
    target = registered_capsule(template['target_id'])
    parent = custody(Path(evaluator['runtime_root']) / 'source/jiuwenswarm' / target.carrier_path).read_bytes()
    need(sha(parent) == grant['parent_sha256'], 'FROZEN_PARENT_BYTES_DIFFER')
    comp = template['composition']
    prepare = write_exclusive(dirs['control'] / 'prepare-configuration.json', {
        'schema': PREPARE_SCHEMA, **{key: comp[key] for key in SHARED_COMPOSITION},
        'record_root': str(dirs['records']), 'account_id': comp['account_id'],
        'preparation_claim': str(dirs['prepare'] / 'preparation-claim.json'),
        'output_path': str(dirs['prepare'] / 'prepared.json'), 'exact_binding_refs': comp['exact_binding_refs'],
        'work_capsule_refs': comp['work_capsule_refs'], 'grant': grant, 'runtime_manifest': manifest,
        'parent_body': parent.decode('utf8'), 'parent_declaration': template['prepare']['parent_declaration'],
        'visible_context': visible_context(template['target_id']), 'request_text': template['prepare']['request_text'],
        'observed_symptom': template['prepare']['observed_symptom'], 'loop': dict(template['loop'])})
    run_step('prepare', prepare_step(template, dirs, prepare), dirs['control'])
    prepared_path = custody(dirs['prepare'] / 'prepared.json', owner=CONTROLLER[0])
    prepared_raw = prepared_path.read_bytes()
    prepared = json.loads(prepared_raw)
    need(prepared.get('schema') == 'ai4r-rsi-capsule-prepared:1' and prepared.get('model_calls') == 0
         and prepared['session']['id'] == run_id and prepared['session']['grant'] == grant,
         'EXACT_MODEL_FREE_PREPARATION_REQUIRED')
    run = template['run']
    run_cfg = {'schema': RUN_SCHEMA, 'session': prepared['session'],
        'composition': {**{key: comp[key] for key in SHARED_COMPOSITION}, 'record_root': str(dirs['records']),
            'work_root': str(dirs['work']), 'principal': comp['principal'],
            'exact_binding_refs': comp['exact_binding_refs'], 'work_capsule_refs': comp['work_capsule_refs'],
            'run_contexts': prepared['run_contexts']},
        'evaluator': {'root': str(dirs['evidence']), 'runtime_root': evaluator['runtime_root'], 'manifest': manifest,
            'metadata': evaluator['metadata'], 'grant_path': grant_pin['path'], 'grant_sha256': grant_pin['sha256'],
            'cgroup_root': evaluator['cgroup_root']},
        'claim_path': str(dirs['claim'] / 'session-claim.json'),
        'result_path': str(dirs['records'] / 'capsule-result.json'),
        'source_root': run['source_root'], 'source_pins': source_pins(run['source_root']),
        'composition_path': run['composition_path'], 'composition_sha256': file_pin(run['composition_path'])['sha256']}
    receipt_path = dirs['control'] / 'compose-doctor.json'
    # The doctor scope excludes ``compatibility``; the placeholder is replaced
    # by the actual receipt pin in the final, otherwise identical bytes.
    doctor_cfg = write_exclusive(dirs['control'] / 'doctor-configuration.json',
                                 dict(run_cfg, compatibility={'path': str(receipt_path), 'sha256': '0' * 64}))
    run_step('doctor', doctor_step(template, dirs, doctor_cfg, run_cfg), dirs['control'])
    receipt_raw = custody(dirs['doctor'] / 'doctor-result.json', owner=CONTROLLER[0]).read_bytes()
    receipt = json.loads(receipt_raw)
    need(receipt.get('status') == 'COMPATIBLE' and receipt.get('model_calls') == 0
         and receipt.get('execution_jobs') == 0, 'ACTUAL_MODEL_FREE_COMPOSE_DOCTOR_REQUIRED')
    compatibility = write_exclusive(receipt_path, receipt_raw)
    configuration = write_exclusive(dirs['control'] / 'run-configuration.json', dict(run_cfg, compatibility=compatibility))
    sources = template['launcher']
    publication = write_exclusive(dirs['control'] / 'publication-template.json', {
        'schema': PUBLICATION_SCHEMA, 'projection': file_pin(sources['projection']),
        'meta': template['publication']['meta'], 'configuration': configuration,
        'control_directory': str(dirs['control']), 'publication_directory': template['publication']['publication_directory']})
    launcher_pin = file_pin(sources['launcher'])
    launcher = write_exclusive(dirs['control'] / 'launcher-configuration.json', {
        'schema': LAUNCHER_SCHEMA, 'id': run_id, 'configuration': configuration, 'runner': file_pin(run['runner']),
        'restore': file_pin(sources['restore']), 'seccomp': file_pin(sources['seccomp']),
        'publisher': file_pin(sources['publisher']), 'publication_template': publication,
        'control_directory': str(dirs['control']), 'cgroup_root': evaluator['cgroup_root'],
        'launcher_sha256': launcher_pin['sha256']})
    return {'configuration': configuration, 'launcher_configuration': launcher, 'publication_template': publication,
            'grant_sha256': grant_pin['sha256'], 'expires_unix_s': grant['expires_unix_s'], 'wall_s': deadline,
            'max_executions': grant['max_executions'], 'max_iterations': loop['max_iterations'],
            'prepared_sha256': sha(prepared_raw), 'compose_doctor_sha256': compatibility['sha256'],
            'source_pins_sha256': sha(encoded(run_cfg['source_pins'])), 'model_calls': 0}


class ContainerSteps:
    """Run fixed preparation containers through the pinned Root docker client."""
    def __init__(self, template, control_root, docker, *, clock=time.monotonic, sleep=time.sleep):
        self.template, self.control_root, self.docker = template, Path(control_root), docker
        self.clock, self.sleep = clock, sleep

    def __call__(self, name, argv, control):
        need(name in ('prepare', 'doctor'), 'FIXED_PREPARATION_STEP_REQUIRED')
        control = custody(control, directory=True)
        need(control.parent == self.control_root, 'REVISION_CONTROL_DIRECTORY_DIFFERS')
        # The exclusive claim precedes the container: a step is never re-run.
        write_exclusive(control / (name + '-claim.json'), {'schema': STEP_SCHEMA, 'step': name, 'argv': argv}, mode=0o400)
        cid = self.docker(*argv).decode().strip()
        need(re.fullmatch('[0-9a-f]{64}', cid), 'EXACT_STEP_CID_REQUIRED')
        self.docker('start', cid)
        deadline = self.clock() + self.template['container']['step_timeout_s']
        while True:
            info = json.loads(self.docker('inspect', cid))[0]
            need(info['Id'] == cid and info['Image'] == self.template['container']['image'], 'STEP_IDENTITY_DIFFERS')
            if not info['State']['Running']: break
            need(self.clock() < deadline, 'STEP_DEADLINE_EXPIRED_RECONCILE_NO_REPLAY')
            self.sleep(2)
        need(info['State']['Pid'] == 0, 'STEP_TERMINATION_UNPROVEN')
        output = self.docker('logs', cid)
        write_exclusive(control / (name + '-exit.json'), {'schema': STEP_SCHEMA, 'step': name, 'cid': cid,
            'exit_code': info['State']['ExitCode'], 'stdout_sha256': sha(output)}, mode=0o400)
        write_exclusive(control / (name + '-stdout.log'), output[-65536:], mode=0o400)
        need(info['State']['ExitCode'] == 0, 'PREPARATION_STEP_FAILED_NO_REPLAY: ' + name)
