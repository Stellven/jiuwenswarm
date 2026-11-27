"""Host authority for the AQBC expert-seeding experiment. No gate starts a model."""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
import tempfile
import time

from .config import expand_sources
from .contract import load_for_task
from .store import NotFound

PREMISE_SCHEMA = 'factory.muse-seeding-premise/1'
PROFILE_SCHEMA = 'factory.muse-expert-seed-profile/1'
PROFILE_INPUTS = {'trace': ('seeding_trace', 'trace.mct'), 'manifest': ('seeding_trace_manifest', 'manifest.json')}
EVIDENCE_FILES = ('load-receipts.json', 'warmup-receipts.json', 'startup-fill-receipts.json', 'request-receipts.json')
REQUEST_METRICS = {'client_ttft_ms', 'decode_tokens_per_second', 'request_total_ms', 'cache_hit_rate'}
FIXTURE = Path(__file__).with_name('fixtures') / 'muse_r11_seed_profile.cpp'
MAX_TRACE_BYTES = 64 << 20


def digest(data):
    return hashlib.sha256(data).hexdigest()


def profile_bytes(profile):
    return json.dumps(profile, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def policy(task):
    contract = load_for_task(task, task['contract_id'])
    return expand_sources(contract['extensions']['muse.r11-seeding'])


def read_pin(pin, limit=MAX_TRACE_BYTES):
    path = Path(pin['path'])
    if path.stat().st_size > limit:
        raise ValueError(f'Pinned input exceeds its byte limit: {path.name}')
    raw = path.read_bytes()
    if len(raw) > limit or digest(raw) != pin['sha256']:
        raise ValueError(f'Pinned input changed: {path.name}')
    return raw


def validate_parent(task):
    protocol = policy(task)
    pin = protocol['parent_reference']
    parent = json.loads(read_pin(pin))
    if any(parent.get(key) != value for key, value in protocol['baseline'].items()):
        raise ValueError('Released AQBC identity differs from the contract')
    root = Path(pin['path']).resolve().parent.parent
    for evidence in parent['evidence'].values():
        path = (root / evidence['path']).resolve(strict=True)
        if not path.is_relative_to(root):
            raise ValueError('AQBC parent evidence points outside the demo root')
        read_pin(dict(path=path, sha256=evidence['sha256']))
    source = parent['engine_source']
    tree = git(protocol['source_root'], 'rev-parse', source['commit'] + '^{tree}').decode().strip()
    if tree != source['tree']:
        raise ValueError('AQBC parent source tree changed')
    return parent


def graph(host, task_id):
    from .taskgraph import plan_get

    return {node['node_id']: node for node in plan_get(host, task_id)['nodes']}


def check_for(host, task_id, nodes, node_id, name):
    from .node_check import accepted_output

    if node_id not in nodes:
        raise ValueError(f'The seeding plan is missing {node_id}')
    return accepted_output(host, task_id, nodes[node_id], name)


def cited_ids(refs):
    refs = refs or {}
    ids = refs.get('evidence_ids')
    if not isinstance(ids, list) or not ids or any(not isinstance(value, str) for value in ids):
        raise ValueError('Cite the required native evidence IDs')
    return set(ids)


def operator_input(host, task_id, key, path, refs):
    matches = []
    for evidence_id in cited_ids(refs):
        record = host.read(task_id, evidence_id)
        values = record.get('values') or {}
        if record.get('kind') == 'operator_input' and values.get('key') == key:
            matches.append((record, values))
    if len(matches) != 1:
        raise ValueError(f'Cite the operator-imported {key} input exactly once')
    record, values = matches[0]
    if Path(values.get('path', '')).resolve() != Path(path).resolve():
        raise ValueError(f'Seeding input {key} does not match the contract path')
    artifact = values.get('artifact_id')
    if not artifact or artifact not in record.get('source_artifacts', []):
        raise ValueError(f'The {key} input has no immutable raw attachment')
    pin = dict(path=str(path), sha256=values['sha256'])
    raw = read_pin(pin)
    if host.artifact_bytes(task_id, artifact) != raw:
        raise ValueError(f'Raw attachment for {key} differs from the operator pin')
    return pin, artifact


def pin_inputs(host, task, refs):
    task_id = task['task_id']
    pin = policy(task)['parent_reference']
    cited, artifact = operator_input(host, task_id, 'aqbc_parent', pin['path'], refs)
    if cited != pin:
        raise ValueError('Cited AQBC parent digest differs from the frozen contract')
    parent = validate_parent(task)
    return dict(image_id=parent['image_id'], evidence_ids=sorted(cited_ids(refs)), artifacts=[artifact])


def calibration_requests(contract):
    """Resolve and render the calibration file pinned by the admitted contract."""
    from jinja2 import Environment
    repo = Path(__file__).resolve().parents[2]
    spec = contract['inputs']['calibration_prompts']
    path = (repo / spec['repo_path']).resolve(strict=True)
    if not path.is_relative_to(repo):
        raise ValueError('Calibration input outside the checked repository')
    raw = read_pin({'path': path, 'sha256': spec['sha256']}, 1 << 20)
    if len(raw) != spec['size']:
        raise ValueError('Recorded calibration input size differs from the contract')
    prescribed = [json.loads(line) for line in raw.splitlines() if line.strip()]
    folder = repo / 'ops/spark/prompts/muse'
    template = (folder/'chat_template.jinja').read_bytes()
    if digest(template) != json.loads((folder/'MANIFEST.json').read_bytes())['files']['chat_template.jinja']:
        raise ValueError('Calibration rendering template differs from recorded manifest')
    env = Environment(trim_blocks=True, lstrip_blocks=True)
    render = env.from_string(re.sub(r'\{%-?\s*(end)?generation\s*-?%\}', '', template.decode()))
    rows = []
    for expected in prescribed:
        prompt = expected.get('rendered_prompt')
        if prompt is None:
            prompt = render.render(messages=[{'role':'user', 'content':expected['prompt']}],
                                   add_generation_prompt=True, reasoning_effort='low', current_date='2026-11-30')
        rows.append({**expected, 'rendered_prompt': prompt})
    if not rows or len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Calibration input requires unique request IDs')
    return rows


def verify_calibration_binding(contract, manifest):
    prescribed = calibration_requests(contract)
    observed = [r for r in manifest['requests'] if r.get('cohort') == 'calibration']
    if not prescribed or len(prescribed) != len(observed):
        raise ValueError(f'Calibration input mismatch: contract specifies {len(prescribed)} requests, trace contains {len(observed)}')
    for expected, actual in zip(prescribed, observed, strict=True):
        fields = (expected['id'], digest(expected['rendered_prompt'].encode()), expected['n_predict'], False)
        if fields != (actual['id'], actual['prompt_sha256'], actual['generated_n'], actual['cache_prompt']):
            raise ValueError(f'Calibration request differs from contract: {expected["id"]}')
        if 'token_ids_sha256' in expected and expected['token_ids_sha256'] != actual.get('token_ids_sha256'):
            raise ValueError('Calibration token identities differ from contract')
    return contract['inputs']['calibration_prompts']['sha256']


def premise_inputs(host, task, refs):
    task_id = task['task_id']
    protocol = policy(task)
    parent_check = check_for(host, task_id, graph(host, task_id), 'pin_inputs', 'pinned_inputs')
    if parent_check['obs_id'] not in cited_ids(refs):
        raise ValueError('Cite the accepted AQBC pin check')
    request = {'parent': protocol['parent_reference']}
    for name, (key, filename) in PROFILE_INPUTS.items():
        pin, _ = operator_input(host, task_id, key, Path(protocol['profile_directory']) / filename, refs)
        request[name] = pin
    contract = load_for_task(task, task_id)
    verify_calibration_binding(contract, json.loads(read_pin(request['manifest'])))
    return {'request': request}


def import_profile(host, task):
    """Seal the acquired inputs after admission. Do not invent or acquire a trace."""
    protocol = policy(task)
    task_id = task['task_id']
    directory = Path(protocol['profile_directory']).resolve()
    for key, name in PROFILE_INPUTS.values():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_TRACE_BYTES:
            raise ValueError(f'Expected bounded acquisition file {path}')
    observations = []
    for key, name in PROFILE_INPUTS.values():
        path = directory / name
        data = path.read_bytes()
        if not data or len(data) > MAX_TRACE_BYTES:
            raise ValueError(f'Missing or oversized acquisition evidence: {name}')
        sha256 = digest(data)
        artifact = f'operator-{key}-{sha256[:24]}'
        obs_id = f'operator:{key}:{sha256[:24]}'
        try:
            prior = host.read(task_id, obs_id)
        except NotFound:
            host.put_artifact(task_id, artifact, data, 'application/json' if name.endswith('.json')
                              else 'application/octet-stream', None)
            prior = host.append_observation(task_id, dict(
                obs_id=obs_id, kind='operator_input', source_artifacts=[artifact],
                values=dict(key=key, path=str(path), bytes=len(data), sha256=sha256, artifact_id=artifact,
                            how='Operator-acquired AQBC profile evidence, sealed without changing any bytes.'),
                host_run=dict(by='operator', module=__name__),
                limitations='Acquisition source only. The capsule independently checks coverage, identity and premise.'))
        observations.append(prior['obs_id'])
    return observations


def premise(host, task_id, checkpoint, nodes):
    check = check_for(host, task_id, nodes, checkpoint['premise_node'], 'premise')
    verifier = check.get('verifier') or {}
    artifact = verifier.get('sealed_artifact')
    if not artifact or artifact not in check['source_artifacts']:
        raise ValueError('The accepted premise has no sealed result')
    result = json.loads(host.artifact_bytes(task_id, artifact))
    if (not isinstance(result, dict) or result.get('format') != PREMISE_SCHEMA
            or type(result.get('may_build')) is not bool or not str(result.get('reason') or '').strip()):
        raise ValueError('The sealed premise result is invalid')
    if result['may_build']:
        profile = result.get('profile')
        if (not isinstance(profile, dict) or profile.get('format') != PROFILE_SCHEMA
                or digest(profile_bytes(profile)) != result.get('profile_sha256')):
            raise ValueError('The positive premise has no digest-bound seed profile')
    return check, result


def require_eligible(host, task_id, checkpoint, nodes):
    _, result = premise(host, task_id, checkpoint, nodes)
    if not result['may_build']:
        raise ValueError('Seeding premise refused candidate work: ' + result['reason'])
    task = host.get_task(task_id)
    manifest = Path(policy(task)['profile_directory']) / 'manifest.json'
    raw = read_pin(dict(path=manifest, sha256=result['manifest_sha256']))
    verify_calibration_binding(load_for_task(task, task_id), json.loads(raw))
    return result


def guard_node(host, task_id, checkpoint, nodes, node_id):
    if node_id in {checkpoint[key] for key in ('patch_node', 'fixture_node', 'build_node', 'delivery_node')}:
        require_eligible(host, task_id, checkpoint, nodes)


def git(source, *args):
    try:
        return subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
            '-C', str(source), *args], check=True, stdin=subprocess.DEVNULL, capture_output=True,
            timeout=30).stdout
    except subprocess.CalledProcessError as exc:
        raise ValueError('Cannot verify candidate Git identity: ' + exc.stderr.decode(errors='replace')[:300]) from exc


def checkout(host, task):
    return (host.home / 'agent-workspace' / task['source']['subpath']).resolve()


def guard_source(host, task, operation, inputs):
    from .node_check import working_diff
    from .scheduler import effective_contract
    from .node_contract import for_task
    from .taskgraph import dispatch_precondition

    checkpoint = task['constraints']['seeding_checkpoint']
    task_id, node_id = task['task_id'], checkpoint['patch_node']
    dispatch_precondition(host, task_id, node_id)
    nodes = graph(host, task_id)
    if effective_contract(host, task_id, nodes[node_id], for_task(task))[1]:
        raise ValueError('The scheduler must finalize the candidate source node before editing')
    if operation == 'localcommit':
        patch = check_for(host, task_id, nodes, node_id, 'candidate_patch')
        base = policy(task)['baseline']['engine_source']['commit']
        source = checkout(host, task)
        if (inputs.get('expected_head') != base or git(source, 'rev-parse', 'HEAD').decode().strip() != base
                or digest(working_diff(source)) != patch.get('diff_sha256')):
            raise ValueError('Commit only the accepted candidate working diff against the pinned AQBC source')


def checked_patch(host, task, checkpoint, nodes):
    task_id = task['task_id']
    patch = check_for(host, task_id, nodes, checkpoint['patch_node'], 'candidate_patch')
    base = policy(task)['baseline']['engine_source']['commit']
    source = checkout(host, task)
    if git(source, 'status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Verify the clean committed task-owned candidate')
    parent = git(source, 'rev-list', '--parents', '-n', '1', 'HEAD').decode().split()
    if len(parent) != 2 or parent[1] != base or patch.get('head') != base:
        raise ValueError('Candidate must be a single local commit on pinned AQBC')
    diff = git(source, 'diff', '--binary', '--full-index', '--no-renames', base, 'HEAD')
    if not diff or digest(diff) != patch.get('diff_sha256'):
        raise ValueError('Committed candidate diff differs from the accepted patch')
    return patch, dict(commit=parent[0], tree=git(source, 'rev-parse', 'HEAD^{tree}').decode().strip())


def check_fixture(host, task, refs):
    task_id = task['task_id']
    checkpoint = task['constraints']['seeding_checkpoint']
    nodes = graph(host, task_id)
    result = require_eligible(host, task_id, checkpoint, nodes)
    patch, identity = checked_patch(host, task, checkpoint, nodes)
    if patch['obs_id'] not in cited_ids(refs):
        raise ValueError('Cite the accepted candidate patch check')
    profile = profile_bytes(result['profile'])
    source = checkout(host, task) / 'src'
    fixture_source = FIXTURE.read_bytes()
    env = dict(PATH=os.defpath, LANG='C', CUDA_VISIBLE_DEVICES='')
    with tempfile.TemporaryDirectory(prefix='muse-r11-fixture-') as work:
        root = Path(work)
        (root / 'profile.json').write_bytes(profile)
        malformed = dict(result['profile'], format='invalid-profile-schema')
        (root / 'malformed.json').write_bytes(profile_bytes(malformed))
        duplicate = json.loads(profile)
        entries = [entry for group in duplicate['groups'] for entry in group['entries']]
        if not entries:
            raise ValueError('The positive premise must contain at least one seed entry')
        next(group['entries'] for group in duplicate['groups'] if group['entries']).append(entries[0])
        (root / 'duplicate.json').write_bytes(profile_bytes(duplicate))
        # Memory and CPU limits also apply to any subprocess of the CPU fixture.
        cap = ['/usr/bin/prlimit', '--as=1073741824', '--cpu=60', '--']
        compiler = ['/usr/bin/c++', '-std=c++17', '-Wall', '-Wextra', '-I', str(source), str(FIXTURE),
                    str(source / 'llama-expert-cache-profile.cpp'), '-o', str(root / 'fixture')]
        commands = [compiler, [str(root / 'fixture'), str(len(entries))]]
        log = []
        for command in commands:
            try:
                ran = subprocess.run([*cap, *command], cwd=root, env=env, stdin=subprocess.DEVNULL,
                                     capture_output=True, timeout=90)
            except subprocess.TimeoutExpired as exc:
                raise ValueError('The model-free seeding fixture did not finish') from exc
            output = (ran.stdout + ran.stderr).decode(errors='replace')[-12000:]
            if ran.returncode:
                raise ValueError('The model-free seeding fixture failed: ' + output[-4000:])
            log.append(output)
    profile_id = 'r11-seeding-profile-' + result['profile_sha256'][:24]
    log_id = 'r11-seeding-fixture-' + digest((identity['commit'] + result['profile_sha256']).encode())[:24]
    host.put_artifact(task_id, profile_id, profile, 'application/json', None)
    host.put_artifact(task_id, log_id, '\n'.join(log).encode(), 'text/plain', None)
    return dict(source=identity, candidate_patch=patch['obs_id'], diff_sha256=patch['diff_sha256'],
                fixture_sha256=digest(fixture_source), profile_sha256=result['profile_sha256'],
                seeding_profile_artifact=profile_id, artifacts=[profile_id, log_id])


def verify_build_request(host, task, checkpoint, request, node_id):
    if node_id != checkpoint['build_node']:
        raise ValueError('Build only on the contracted AQBCE build node')
    task_id = task['task_id']
    nodes = graph(host, task_id)
    require_eligible(host, task_id, checkpoint, nodes)
    patch, identity = checked_patch(host, task, checkpoint, nodes)
    fixture = check_for(host, task_id, nodes, checkpoint['fixture_node'], 'fixture_evidence')['found']
    if fixture.get('source') != identity or fixture.get('candidate_patch') != patch['obs_id']:
        raise ValueError('The candidate no longer matches the host-checked fixture')
    expected = dict(path=str(checkout(host, task)), commit=identity['commit'])
    if (request.get('source') != expected or request.get('dependency') != expected
            or request.get('target') != 'spark-gb10' or request.get('build_target') != 'llama-server'
            or request.get('delivery', 'image') != 'image' or request.get('verify_image') is not True
            or request.get('env') or request.get('patch') or request.get('config_image')):
        raise ValueError('Build the fixture-checked source and embedded dependency with the frozen Spark image settings')


def verify_image(host, task, refs):
    checkpoint = task['constraints']['seeding_checkpoint']
    task_id = task['task_id']
    nodes = graph(host, task_id)
    attempt, image = refs['build_attempt_id'], refs['image_id']
    build = host._get('attempts', task_id, attempt)
    fixture = check_for(host, task_id, nodes, checkpoint['fixture_node'], 'fixture_evidence')['found']
    request = build['request']
    check = json.loads(host.artifact_bytes(task_id, attempt + ':image-check'))
    parent = policy(task)['baseline']
    actual = {key: request.get('source', {}).get(key) for key in ('commit', 'tree')}
    if (request.get('node_id') != checkpoint['build_node'] or actual != fixture['source']
            or request.get('verify_image') is not True or check.get('status') != 'passed'
            or check.get('image_id') != image or check.get('source_commit') != actual['commit']
            or not re.fullmatch(r'[0-9a-f]{64}', check.get('executable_sha256') or '')
            or image == parent['image_id']):
        raise ValueError('The new Spark image must verify the executable digest and the exact fixture-checked source')
    return attempt + ':image-check'


def verify_lab_task(host, task, checkpoint, node_id, lab_task):
    task_id = task['task_id']
    if node_id != checkpoint['delivery_node']:
        raise ValueError('Only the contracted delivery node composes the seeding laboratory task')
    nodes = graph(host, task_id)
    image = check_for(host, task_id, nodes, checkpoint['build_node'], 'image')['found']
    fixture = check_for(host, task_id, nodes, checkpoint['fixture_node'], 'fixture_evidence')['found']
    subjects, arms = lab_task['subjects'], lab_task['arms']
    if set(arms) != {'AQBC', 'AQBCE'} or arms['AQBC']['subject'] != arms['AQBCE']['subject']:
        raise ValueError('The E comparison must use one exact image for AQBC switch-off and AQBCE switch-on')
    engine = arms['AQBC']['subject']
    if engine == 'seeding_profile' or set(subjects) != {engine, 'seeding_profile'}:
        raise ValueError('Deliver the exact image and seeding profile as the two laboratory subjects')
    subject = subjects[engine]
    if (subject['kind'] != 'container_image' or subject.get('build_attempt_id') != image['build_attempt_id']
            or subject['identity'].get('id') != image['image_id']):
        raise ValueError('The lab subject must match the accepted image build')
    if (arms['AQBC'].get('env') or arms['AQBCE'].get('env') != policy(task)['profile_env']
            or any(arm.get('args') for arm in arms.values())):
        raise ValueError('Neither laboratory arm may differ outside the pinned opt-in and profile')
    item = subjects.get('seeding_profile') or {}
    if (item.get('kind') != 'artifact' or item.get('transfer') != 'attach'
            or item.get('identity', {}).get('artifact_id') != fixture['seeding_profile_artifact']
            or digest(host.artifact_bytes(task_id, fixture['seeding_profile_artifact'])) != fixture['profile_sha256']):
        raise ValueError('Attach the exact fixture-checked seed profile under seeding_profile')
    deliver = lab_task.get('deliverables') or {}
    files = {item['name'] for item in deliver.get('files', [])}
    if deliver.get('raw_samples') is not True or not set(EVIDENCE_FILES) <= files:
        raise ValueError('Require raw load, warm-up, startup-fill and request receipts in the lab package')
    contract = load_for_task(task, task['contract_id'])
    checks = {(item['check'], arm) for item in lab_task['tests'] if item.get('check') for arm in item['arms']}
    if checks != required_checks(contract):
        raise ValueError('The laboratory must check every required arm and correctness pair')
    coverage = {(metric, arm, request) for item in lab_task['tests'] for metric in item.get('measure', [])
                for arm in item['arms'] for request in item.get('requests', [None])}
    if coverage != required_measurements(contract):
        raise ValueError('Measure each request-level metric for both arms on every fixed request, plus the startup and load metrics per arm')


def required_measurements(contract):
    requests = [item['id'] for item in contract['workload']['requests']]
    return {(metric, arm['id'], request) for metric in contract['measurement']['metrics'] for arm in contract['arms']
            for request in (requests if metric in REQUEST_METRICS else [None])}


def required_checks(contract):
    return {(item['id'], arm) for item in contract['correctness']['checks'] for arm in item['applies_to']}


def external_wait(host, task, checkpoint):
    """Wait for real operator evidence without spending native scheduler turns."""
    from .lab_manager import LabManager

    task_id = task['task_id']
    nodes = graph(host, task_id)
    protocol = policy(task)
    if time.time() >= datetime.fromisoformat(protocol['target_deadline']).timestamp():
        return 'Run 4 deadline reached before independent acceptance', True
    if nodes['pin_inputs']['state'] == 'done' and nodes[checkpoint['premise_node']]['state'] not in {'done', 'failed'}:
        rows = host._db.execute('SELECT "values" FROM observations WHERE task_id=? AND kind=?',
                                (task_id, 'operator_input'))
        keys = {json.loads(row[0]).get('key') for row in rows}
        if any(key not in keys for key, _ in PROFILE_INPUTS.values()):
            return 'Awaiting operator-imported AQBC cache trace and manifest', False
    if nodes[checkpoint['delivery_node']]['state'] == 'done':
        delivery = check_for(host, task_id, nodes, checkpoint['delivery_node'], 'lab_package')
        status = LabManager(host, route='mailbox').status(task_id, delivery['found']['request_id'])['state']
        if status in {'requested', 'accepted', 'running', 'cancel_requested'}:
            return 'Awaiting the independent target lab verdict', False
    return None


def validate_terminal(host, task, checkpoint, decision):
    from .node_check import current_checks

    action = decision.get('action') or {}
    kind = action.get('type')
    if kind not in {'accept', 'reject', 'report_inconclusive', 'stop_missing_prerequisite'}:
        return
    task_id = task['task_id']
    nodes = graph(host, task_id)
    ids = set(decision.get('evidence_ids', []))
    if kind == 'stop_missing_prerequisite':
        try:
            check, result = premise(host, task_id, checkpoint, nodes)
        except ValueError:
            checks = current_checks(host, task_id, nodes[checkpoint['premise_node']], 'premise')
            if checks and checks[-1].get('passed') is False and checks[-1].get('state') == 'finished'                     and checks[-1]['obs_id'] in ids and str(action.get('reason') or '').strip():
                return
            raise ValueError('A premise refusal must cite its genuine completed check') from None
        if result['may_build'] or check['obs_id'] not in ids or not str(action.get('reason') or '').strip():
            raise ValueError('Stop at the premise only on a cited sealed result that disallows building')
        return
    if kind == 'report_inconclusive':
        if not ids or not str(action.get('reason') or '').strip():
            raise ValueError('Report inconclusive with the stated limitation and cited native evidence')
        for key in ids:
            row = host.read(task_id, key)
            values = row.get('values') or {}
            if (row.get('kind') == 'node_check' and values.get('state') == 'finished' and values.get('passed') is False
                    or row.get('kind') == 'lab_report' and (values.get('valid') is False or values.get('outcome') != 'completed')
                    or row.get('kind') == 'build_result' and bool(row.get('error'))
                    or row.get('kind') == 'operator_intervention'):
                break
        else:
            raise ValueError('The inconclusive decision must cite a recorded host refusal, incomplete lab result or operator intervention')
        return
    require_eligible(host, task_id, checkpoint, nodes)
    delivery = check_for(host, task_id, nodes, checkpoint['delivery_node'], 'lab_package')
    request = delivery['found']['request_id']
    report_id = request + ':report'
    if not {delivery['obs_id'], report_id} <= ids or nodes[checkpoint['delivery_node']]['state'] != 'done':
        raise ValueError('The decision needs the completed delivery and its exact independently imported lab report')
    report = host.read(task_id, report_id)
    values = report.get('values') or {}
    if (report.get('kind') != 'lab_report' or values.get('valid') is not True
            or values.get('request_id') != request or values.get('package_id') != delivery['found']['package_id']
            or values.get('contract_sha256') != task['constraints']['contract_sha256']):
        raise ValueError('Invalid or unrelated laboratory report')
    verdict = next((row.get('verdict') for row in values['checks'] if row.get('check') == 'independent_acceptance'
                    and row.get('arm') == 'AQBCE'), None)
    if kind == 'reject' and verdict == 'fail':
        return
    deadline = datetime.fromisoformat(policy(task)['target_deadline']).timestamp()
    if (kind != 'accept' or verdict != 'pass' or values.get('outcome') != 'completed' or values.get('not_run')
            or any(row['verdict'] != 'pass' for row in values['checks']) or report['created'] > deadline):
        raise ValueError('AQBCE needs an on-time passing independent acceptance and every required check')
    contract = load_for_task(task, task['contract_id'])
    checks = [(row['check'], row.get('arm')) for row in values['checks']]
    if len(checks) != len(set(checks)) or set(checks) != required_checks(contract):
        raise ValueError('The laboratory report must answer every per-arm correctness check exactly once')
    reported = [(row['metric'], row['arm'], row.get('request')) for row in values['results']]
    if len(reported) != len(set(reported)) or set(reported) != required_measurements(contract):
        raise ValueError('The laboratory report must contain every comparison and per-arm load metric exactly once')
    for row in values['results']:
        if row.get('request') not in {None, 'first_after_start'} and len(row.get('samples', [])) != 3:
            raise ValueError('The warm and follow-up comparison needs three measured samples per cell')
