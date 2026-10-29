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
    need(isinstance(grant['limits'], dict) and type(grant['limits'].get('wall_s')) is int, 'FINITE_DURABLE_GRANT_REQUIRED')
    need(isinstance(value['prepare'], dict) and set(value['prepare']) == {
        'source_root', 'parent_declaration', 'request_text', 'observed_symptom'}, 'CLOSED_DURABLE_PREPARATION_REQUIRED')
    need(isinstance(value['run'], dict) and set(value['run']) == {'source_root', 'runner', 'composition_path'},
         'CLOSED_DURABLE_RUN_SOURCES_REQUIRED')
    need(Path(value['run']['runner']).parent == Path(value['run']['source_root']), 'RUNNER_SOURCE_ROOT_DIFFERS')
    # The doctor and worker containers mount only ``source_root``: a frozen
    # composition elsewhere would surface only as a container FileNotFoundError.
    source_root, composition_path = absolute(value['run']['source_root']), absolute(value['run']['composition_path'])
    need(composition_path != source_root and composition_path.is_relative_to(source_root),
         'COMPOSITION_OUTSIDE_SOURCE_ROOT: ' + str(composition_path) + ' is not under ' + str(source_root))
    sources = value['launcher']
    need(isinstance(sources, dict) and set(sources) - {'timeouts'} == {
        'launcher', 'restore', 'seccomp', 'publisher', 'projection'}, 'CLOSED_DURABLE_LAUNCHER_SOURCES_REQUIRED')
    if 'timeouts' in sources:  # Optional launcher bounds; absent keeps the launcher defaults.
        need(isinstance(sources['timeouts'], dict) and set(sources['timeouts']) <= {'runner_preflight_s', 'docker_s'}
             and all(type(v) is int and 1 <= v <= 3600 for v in sources['timeouts'].values()),
             'CLOSED_LAUNCHER_TIMEOUTS_REQUIRED')
    publication = value['publication']
    need(isinstance(publication, dict) and set(publication) == {'meta', 'publication_directory'}
         and publication['meta'].get('target_id') == value['target_id'], 'CLOSED_DURABLE_PUBLICATION_REQUIRED')
    need(isinstance(value['container'], dict) and set(value['container']) == {'image', 'step_timeout_s'}
         and type(value['container']['step_timeout_s']) is int and 0 < value['container']['step_timeout_s'] <= 3600,
         'CLOSED_DURABLE_CONTAINER_STEPS_REQUIRED')
    # The horizon must cover one whole run, benchmark included.
    need(grant['horizon_s'] > run_deadline_s(grant, revision_loop(value)), 'DURABLE_HORIZON_BELOW_ONE_RUN')
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


# Paired batched benchmark (Interface E) sizing. Configurable per template in
# ``loop.benchmark``; ``workloads`` defaults to the capsule's data-driven
# ``fixtures/benchmark.json`` in the pinned run source. The other defaults are
# Codex's frozen protocol (11 AB/BA pairs, 2 warmups) and a per-job wall
# budget sized from its measured protected batch jobs (see the runbook).
BENCHMARK_FIELDS = {'workloads', 'repetitions', 'warmups', 'per_job_s', 'wall_s'}
BENCHMARK_DEFAULTS = {'repetitions': 11, 'warmups': 2, 'per_job_s': 6}
BENCHMARK_CEILINGS = {'workloads': 64, 'repetitions': 100, 'warmups': 20, 'per_job_s': 300, 'wall_s': 14 * 24 * 3600}


def benchmark_workload_count(template):
    """Workloads from the registered fixture adapter in the pinned source.

    A selected release may delegate to an older fixture adapter; its mutable
    carrier directory does not determine where the benchmark spec lives.
    """
    extensions = Path(template['run']['source_root']) / 'jiuwenswarm/research/capsule_extensions'
    manifests = [path for path in sorted(extensions.glob('*/fixtures/manifest.json'))
                 if json.loads(custody(path).read_bytes()).get('capsule_name') == template['target_id']]
    need(len(manifests) <= 1, 'UNIQUE_CAPSULE_FIXTURE_MANIFEST_REQUIRED')
    if not manifests:
        return None
    path = manifests[0].parent / 'benchmark.json'
    if not path.exists():
        return None
    value = json.loads(custody(path).read_bytes())
    need(isinstance(value, dict), 'DATA_DRIVEN_BENCHMARK_WORKLOADS_REQUIRED: ' + str(path))
    # The timed workloads, as ``capsule_benchmark`` reads the spec: its
    # ``workloads`` index when present, else every ``timed`` row of every split.
    rows = value.get('workloads')
    if rows is None and isinstance(value.get('splits'), dict):
        rows = [row for split in value['splits'].values() if isinstance(split, list)
                for row in split if isinstance(row, dict) and row.get('timed') is True]
    need(isinstance(rows, (list, dict)) and rows, 'DATA_DRIVEN_BENCHMARK_WORKLOADS_REQUIRED: ' + str(path))
    return len(rows)


def benchmark_settings(template):
    """Closed benchmark sizing for one revision, or None when the capsule has
    no benchmark (the loop then keeps the single-job floor and the historical
    budget and deadline exactly)."""
    loop = template['loop']
    given = loop.get('benchmark')
    need(given is None or isinstance(given, dict) and set(given) <= BENCHMARK_FIELDS, 'CLOSED_LOOP_BENCHMARK_REQUIRED')
    given = dict(given or {})
    if 'workloads' not in given:
        counted = benchmark_workload_count(template)
        if counted is None:
            need(not given, 'BENCHMARK_WORKLOAD_COUNT_REQUIRED')
            return None
        given['workloads'] = counted
    settings = {**BENCHMARK_DEFAULTS, **given}
    for key, ceiling in BENCHMARK_CEILINGS.items():
        if key in settings:
            low = 0 if key == 'warmups' else 1
            need(type(settings[key]) is int and low <= settings[key] <= ceiling, 'FINITE_BENCHMARK_' + key.upper() + '_REQUIRED')
    if 'wall_s' not in settings:
        settings['wall_s'] = benchmark_wall_s(settings, loop_settings(loop)['max_iterations'], template['target_id'])
    return settings


def benchmark_wall_s(settings, max_iterations, capsule_name):
    """Default benchmark wall: one A/A baseline plus one candidate benchmark
    per iteration, each exactly the owner's ``benchmark_job_count`` jobs (timed
    workloads x repetitions x 2 sides, warmups run inside each timed job, plus
    the untimed and semantic-edge jobs) at ``per_job_s`` seconds per job."""
    from jiuwenswarm.research_rsi.targets.capsule_executor import benchmark_jobs_for_sizing
    jobs = benchmark_jobs_for_sizing({key: settings[key] for key in ('workloads', 'repetitions', 'warmups')},
                                     capsule_name=capsule_name)
    return (max_iterations + 1) * jobs * settings['per_job_s']


def revision_loop(template):
    """The loop configuration a revision is prepared with: the template's own,
    plus the materialized ``benchmark`` sizing when the capsule has one (so the
    session, the runner and the launcher read one value)."""
    loop = dict(template['loop'])
    settings = benchmark_settings(template)
    if settings is not None:
        loop['benchmark'] = settings
    return loop


def execution_budget(fixtures, loop, capsule_name):
    """``loop_execution_budget`` of the target owner, with the loop config.

    The benchmark jobs are counted by the owner's (extended) function, never
    re-derived here; a loop without a benchmark keeps the historical call.
    """
    from jiuwenswarm.research_rsi.targets.capsule_executor import loop_execution_budget
    settings = loop_settings(loop)
    kwargs = {'max_iterations': settings['max_iterations'], 'trials': settings['trials']}
    if isinstance(loop.get('benchmark'), dict):
        # Exact per-capsule job count (never the cross-capsule upper bound).
        kwargs.update(benchmark=loop['benchmark'], capsule_name=capsule_name)
    return loop_execution_budget(len(fixtures), **kwargs)



def revision_metadata(template, run_id, manifest, *, loop=None):
    """Rebind public worker facts to this revision, keeping hardware limits.

    Durable templates may originate in an older installed run. Its contract
    identity/job count and runtime identity are facts to derive, not stable
    installation authority that may be copied into a successor.
    """
    import copy
    metadata = copy.deepcopy(template['evaluator']['metadata'])
    contract, environment = metadata['contract'], metadata['environment']
    if contract.get('schema') == 'ai4r-public-whole-capsule-development-contract:1':
        from jiuwenswarm.research_rsi.targets.capsule_executor import grant_fixtures, LOOP_GRANT_SCHEMA
        loop = revision_loop(template) if loop is None else loop
        fixtures = grant_fixtures({'schema': LOOP_GRANT_SCHEMA, 'capsule_name': template['target_id']})
        contract.update(id=run_id, run_id=run_id, target=template['target_id'],
                        max_jobs=execution_budget(fixtures, loop, template['target_id']),
                        roles=['parent', 'candidate'])
    if environment.get('schema') == 'ai4r-public-whole-capsule-runtime-environment:1':
        environment.update(manifest_sha256=sha(encoded(manifest)), python=copy.deepcopy(manifest['python']),
                           image=template['container']['image'])
    return metadata


def derive_grant(template, run_id, manifest, *, now, loop=None):
    """Loop grant v3 bounded by its execution budget and a durable horizon."""
    from jiuwenswarm.research_rsi.records import encoded as canonical
    from jiuwenswarm.research_rsi.targets.capsule_executor import LOOP_GRANT_SCHEMA, grant_fixtures, validate_grant
    from jiuwenswarm.research_rsi.targets.capsule_runtime import BOOTSTRAP_SCHEMA
    from jiuwenswarm.research_rsi.targets.capsules import registered_capsule
    name = template['target_id']; target = registered_capsule(name)
    carrier = 'source/jiuwenswarm/' + target.carrier_path
    parent = next((row['sha256'] for row in manifest['files'] if row['path'] == carrier), None)
    need(parent is not None, 'EXACT_ORIGINAL_CAPSULE_PARENT_REQUIRED')
    loop = revision_loop(template) if loop is None else loop
    draft = {'schema': LOOP_GRANT_SCHEMA, 'capsule_name': name}
    fixtures = grant_fixtures(draft)
    metadata = revision_metadata(template, run_id, manifest, loop=loop)
    grant = {'schema': LOOP_GRANT_SCHEMA, 'bootstrap_schema': BOOTSTRAP_SCHEMA, 'run_id': run_id,
        'capsule_name': name, 'runtime_manifest_sha256': sha(canonical(manifest)), 'parent_sha256': parent,
        'fixture_sha256': sha(canonical(fixtures)), 'fixture_count': len(fixtures), 'roles': ['parent', 'candidate'],
        'max_executions': execution_budget(fixtures, loop, name),
        'iterations': template['grant']['iterations'], 'limits': grant_limits(template, loop),
        'worker': {key + '_ref': {'id': sha(canonical(metadata[key])) + '.json', 'sha256': sha(canonical(metadata[key]))}
                   for key in ('contract', 'environment', 'hardware')},
        'expires_unix_s': int(now) + template['grant']['horizon_s'],
        'scope': 'public_m1_development_only', 'production_admission': 'UNKNOWN'}
    return validate_grant(grant, manifest)


def grant_limits(template, loop):
    """The template's job limits plus, with a materialized benchmark, its wall
    as ``limits.benchmark_wall_s`` (Root's dispatcher deadline adds it)."""
    limits = {key: item for key, item in template['grant']['limits'].items() if key != 'benchmark_wall_s'}
    if isinstance(loop.get('benchmark'), dict):
        limits['benchmark_wall_s'] = loop['benchmark']['wall_s']
    return limits


def run_deadline_s(grant, loop):
    """Whole-run ceiling: the session hard timeout plus the materialized
    benchmark wall plus launcher slack (identical to
    ``rsi_capsule_launcher.run_deadline_s``)."""
    wall = min(grant['limits']['wall_s'], loop.get('wall_s', 3600))
    per_call = min(loop.get('per_call_s', 120), wall)
    benchmark = loop.get('benchmark')
    bench = 0
    if benchmark is not None:
        need(isinstance(benchmark, dict) and type(benchmark.get('wall_s')) is int and benchmark['wall_s'] > 0,
             'MATERIALIZED_BENCHMARK_WALL_REQUIRED')
        bench = benchmark['wall_s']
    return wall + bench + 2 * per_call + 60 + 120


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
    from jiuwenswarm.research_rsi.targets.capsule_executor import v18_kernel_sources
    mounts.update({str(path): True for path in v18_kernel_sources()})
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
    from deploy.m1.rsi_capsule_prepare import validate_iteration_run_ids
    revision = revision_loop(template)
    validate_iteration_run_ids(run_id, loop_settings(revision)['max_iterations'])
    now = int(time.time() if now is None else now)
    dirs = revision_directories(template, run_id)
    make_directories(dirs, chown=chown)
    evaluator = template['evaluator']
    manifest = json.loads(custody(evaluator['manifest_path']).read_bytes())
    grant = derive_grant(template, run_id, manifest, now=now, loop=revision)
    loop = loop_settings(revision)
    deadline = run_deadline_s(grant, revision)
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
        'observed_symptom': template['prepare']['observed_symptom'], 'loop': revision})
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
            'metadata': revision_metadata(template, run_id, manifest, loop=revision), 'grant_path': grant_pin['path'], 'grant_sha256': grant_pin['sha256'],
            'cgroup_root': evaluator['cgroup_root']},
        'claim_path': str(dirs['claim'] / 'session-claim.json'),
        'result_path': str(dirs['records'] / 'capsule-result.json'),
        'source_root': run['source_root'], 'source_pins': source_pins(run['source_root']),
        'composition_path': run['composition_path'], 'composition_sha256': file_pin(run['composition_path'])['sha256']}
    # Walk the package closure once, here in Root preparation (off any request
    # path); the doctor, launcher and runner preflights reuse the proof.
    warm_source_closure(run_cfg, run['runner'])
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
    launcher_value = {
        'schema': LAUNCHER_SCHEMA, 'id': run_id, 'configuration': configuration, 'runner': file_pin(run['runner']),
        'restore': file_pin(sources['restore']), 'seccomp': file_pin(sources['seccomp']),
        'publisher': file_pin(sources['publisher']), 'publication_template': publication,
        'control_directory': str(dirs['control']), 'cgroup_root': evaluator['cgroup_root'],
        'launcher_sha256': launcher_pin['sha256']}
    if 'timeouts' in sources:
        launcher_value['timeouts'] = dict(sources['timeouts'])
    launcher = write_exclusive(dirs['control'] / 'launcher-configuration.json', launcher_value)
    return {'configuration': configuration, 'launcher_configuration': launcher, 'publication_template': publication,
            'grant_sha256': grant_pin['sha256'], 'expires_unix_s': grant['expires_unix_s'], 'wall_s': deadline,
            'max_executions': grant['max_executions'], 'max_iterations': loop['max_iterations'],
            'prepared_sha256': sha(prepared_raw), 'compose_doctor_sha256': compatibility['sha256'],
            'source_pins_sha256': sha(encoded(run_cfg['source_pins'])), 'model_calls': 0,
            **({'benchmark_wall_s': revision['benchmark']['wall_s']} if 'benchmark' in revision else {})}


DOCTOR_SOURCE = 'jiuwenswarm/research_rsi/capsule_doctor.py'


def warm_source_closure(run_cfg, runner):
    """Persist the package's closure proofs for both entry sets in use: the
    doctor/controller (frozen composition) and the launcher (runner plus
    composition). Uses the configuration's own pinned walker stand-alone; a
    package without it is left to the later preflights, which refuse it."""
    root, pins = Path(run_cfg['source_root']), run_cfg['source_pins']
    if DOCTOR_SOURCE not in pins:
        return None
    raw = custody(root / DOCTOR_SOURCE).read_bytes()
    need(sha(raw) == pins[DOCTOR_SOURCE], 'SOURCE_PIN_DIFFERS: ' + DOCTOR_SOURCE)
    import importlib.util
    module = importlib.util.module_from_spec(importlib.util.spec_from_loader('capsule_slot_pinned_doctor', loader=None))
    module.__file__ = str(root / DOCTOR_SOURCE)
    exec(compile(raw, str(root / DOCTOR_SOURCE), 'exec'), module.__dict__)
    module.create_proof_directory(root)
    composition = run_cfg['composition_path']
    return [module.proven_source_closure(root, pins, entry_files=entries)['modules_sha256']
            for entries in ([composition], [runner, composition])]


def _absent(error):
    """A docker refusal that proves the named container does not exist."""
    stderr = getattr(error, 'stderr', None) or b''
    text = stderr.decode('utf8', 'replace') if isinstance(stderr, bytes) else str(stderr)
    return 'No such container' in text or 'No such object' in text


class ContainerSteps:
    """Run fixed preparation containers through the pinned Root docker client.

    Every step container is recorded (``<step>-container.json``) before it
    starts and is proven stopped before its step is reported failed: an
    overdue step is stopped by its recorded id and waited for. After a broker
    restart ``reconcile`` finds a claimed step's container by its recorded id
    (or fixed name), waits while it is inside its own deadline, stops it when
    overdue, and adopts its terminal state; only then may a successor start.
    """
    STEPS = ('prepare', 'doctor')

    def __init__(self, template, control_root, docker, *, clock=time.monotonic, sleep=time.sleep, wall=time.time,
                 stop_grace_s=10, stop_wait_s=60):
        self.template, self.control_root, self.docker = template, Path(control_root), docker
        self.clock, self.sleep, self.wall = clock, sleep, wall
        self.stop_grace_s, self.stop_wait_s = stop_grace_s, stop_wait_s

    def inspect(self, ident, *, cid=None, name=None):
        info = json.loads(self.docker('inspect', ident))[0]
        need(info['Image'] == self.template['container']['image'] and (cid is None or info['Id'] == cid)
             and (name is None or info.get('Name') in (name, '/' + name)), 'STEP_IDENTITY_DIFFERS')
        return info

    def stop(self, cid):
        """Stop a step container by id and wait for its exit; raises unless proven."""
        try:
            self.docker('stop', '--time', str(self.stop_grace_s), cid)
        except Exception:
            pass  # Proven below by inspection, never assumed.
        deadline, killed = self.clock() + self.stop_wait_s, False
        while True:
            info = self.inspect(cid, cid=cid)
            if not info['State']['Running'] and info['State']['Pid'] == 0:
                return info
            if self.clock() >= deadline:
                need(not killed, 'STEP_TERMINATION_UNPROVEN_RECONCILE_NO_REPLAY: ' + cid)
                try:
                    self.docker('kill', cid)
                except Exception:
                    pass
                killed, deadline = True, self.clock() + self.stop_wait_s
            self.sleep(1)

    def record_exit(self, control, name, cid, info, **extra):
        output = self.docker('logs', cid) if info is not None else b''
        write_exclusive(control / (name + '-exit.json'), {'schema': STEP_SCHEMA, 'step': name, 'cid': cid,
            'exit_code': None if info is None else info['State']['ExitCode'], 'stdout_sha256': sha(output), **extra},
            mode=0o400)
        write_exclusive(control / (name + '-stdout.log'), output[-65536:], mode=0o400)

    def __call__(self, name, argv, control):
        need(name in self.STEPS, 'FIXED_PREPARATION_STEP_REQUIRED')
        control = custody(control, directory=True)
        need(control.parent == self.control_root, 'REVISION_CONTROL_DIRECTORY_DIFFERS')
        # The exclusive claim precedes the container: a step is never re-run.
        write_exclusive(control / (name + '-claim.json'), {'schema': STEP_SCHEMA, 'step': name, 'argv': argv}, mode=0o400)
        cid = self.docker(*argv).decode().strip()
        need(re.fullmatch('[0-9a-f]{64}', cid), 'EXACT_STEP_CID_REQUIRED')
        timeout = self.template['container']['step_timeout_s']
        write_exclusive(control / (name + '-container.json'), {'schema': STEP_SCHEMA, 'step': name, 'cid': cid,
            'name': argv[argv.index('--name') + 1], 'started_unix_s': int(self.wall()), 'timeout_s': timeout}, mode=0o400)
        self.docker('start', cid)
        deadline = self.clock() + timeout
        while True:
            info = self.inspect(cid, cid=cid)
            if not info['State']['Running']: break
            if self.clock() >= deadline:
                info = self.stop(cid)  # Proven stopped before the step is reported failed.
                self.record_exit(control, name, cid, info, stopped='STEP_DEADLINE_EXPIRED')
                raise ValueError('STEP_DEADLINE_EXPIRED_STOPPED_NO_REPLAY: ' + name)
            self.sleep(2)
        need(info['State']['Pid'] == 0, 'STEP_TERMINATION_UNPROVEN')
        self.record_exit(control, name, cid, info)
        need(info['State']['ExitCode'] == 0, 'PREPARATION_STEP_FAILED_NO_REPLAY: ' + name)

    def reconcile(self, control):
        """None once every claimed step of a revision is known stopped (its exit
        recorded or adopted); otherwise why one still runs (the caller waits)."""
        control = Path(control)
        if not control.is_dir():
            return None  # Interrupted before its directories: no step was claimed.
        control = custody(control, directory=True)
        for name in self.STEPS:
            claim_path = control / (name + '-claim.json')
            if not claim_path.exists() or (control / (name + '-exit.json')).exists():
                continue
            claim = json.loads(custody(claim_path).read_bytes())
            record_path = control / (name + '-container.json')
            record = json.loads(custody(record_path).read_bytes()) if record_path.exists() else None
            container = record['name'] if record else claim['argv'][claim['argv'].index('--name') + 1]
            try:
                info = self.inspect(record['cid'] if record else container,
                                    cid=record['cid'] if record else None, name=container)
            except Exception as error:
                if not _absent(error):
                    raise
                if record is not None:
                    self.record_exit(control, name, record['cid'], None, adopted='STEP_CONTAINER_ABSENT')
                continue  # Without a record it was claimed but never created: nothing ran.
            if info['State']['Running']:
                started = record['started_unix_s'] if record else int(claim_path.stat().st_mtime)
                if self.wall() < started + self.template['container']['step_timeout_s']:
                    return 'PREPARATION_STEP_STILL_RUNNING: ' + name
                info = self.stop(info['Id'])
            need(info['State']['Pid'] == 0, 'STEP_TERMINATION_UNPROVEN')
            self.record_exit(control, name, info['Id'], info, adopted='AFTER_INTERRUPTION')
        return None
