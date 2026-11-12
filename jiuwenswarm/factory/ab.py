"""Host-owned A/B admission, spec generation and verified evidence ingestion."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import runpy
import sys
import time

from . import components, contract as contracts
from .config import LAB_TIMEOUT, SIMINFENG_ROOT
from .effective_config import ENV_KEYS
from .store import encoded


def environment(contract, requested):
    return components.environment(contract, requested)


def submit(manager, task_id, base_image, candidate_image, base_env, candidate_env,
           rounds, idem_key, component, contract_id=None):
    task = manager.store.get_task(task_id)
    contract_id = contract_id or task.get('contract_id')
    if task.get('contract_id') and contract_id != task['contract_id']:
        raise ValueError('A/B contract must match the task')
    contract = dict(contracts.load(contract_id))
    if not contracts.reference_info(contract).get('stdout_sha256'):
        raise ValueError('Operator must freeze the contract reference before A/B scoring')
    material = components.load(component)
    if type(rounds) is not int or not 1 <= rounds <= 100:
        raise ValueError('rounds must be an integer in 1..100')
    envs = [environment(contract, e) for e in (base_env, candidate_env)]
    if any(e.get('LLAMA_EXPERT_FILL_DIAG') == '1' for e in envs):
        raise ValueError('DIAG=1 is explain-only; use a lab run, then untraced ABBA for scoring')
    admissions = []
    for image in (base_image, candidate_image):
        if not isinstance(image, dict) or set(image) != {'tag', 'id', 'build_attempt_id'}:
            raise ValueError('Each A/B image requires tag, id and build_attempt_id')
        admissions.append(manager.admit(task_id, {k: image[k] for k in ('tag', 'id')}, image['build_attempt_id']))
    regexes = [c['regex'] for c in material['engagement_checks'] if c['source'] == 'stderr']
    spec = dict(id='ab', outdir_base=str(manager.spool_root / '{attempt_id}'), runner='om_run',
                tool=contract['workload']['tool'], argv=contract['workload']['argv'],
                order='ABBA', rounds=rounds, metric='eval_ms_per_token', direction='lower',
                threads=True, arms={
                    'base': dict(image=admissions[0]['image']['id'], env=envs[0], expect_switch=False),
                    'candidate': dict(image=admissions[1]['image']['id'], env=envs[1],
                                      expect_switch=bool(regexes), switch_regex=regexes)})
    # Env-only tuning can compare two enabled configurations. abrun's per-arm
    # config mode requires these assertions without treating base activation as leakage.
    primary = next(iter(material.get('enable_env', {})), None)
    base_enabled = primary and envs[0].get(primary) == material['enable_env'][primary]
    if base_enabled and regexes:
        spec['arms']['base'].update(switch_regex=regexes, switch_regex_is_config=True)
    # There is no activation switch/log in patch 09: its obligation is sampled threads.
    request = dict(mode='ab', contract=contract, component=component, component_material=material,
                   admissions=dict(zip(('base', 'candidate'), admissions)), spec=spec)
    digest = hashlib.sha256(encoded(request).encode()).hexdigest()
    config = manager.spool_root / 'configs' / (digest + '.json')
    if not config.exists():
        contracts.atomic_json(config, request)
    argv = [sys.executable, '-m', 'jiuwenswarm.factory.ab_runner', '--task', task_id,
            '--run', '{attempt_id}', '--config', str(config), '--spool', str(manager.spool_root)]
    env = dict(FACTORY_HOME=str(manager.store.home))
    for key in ('FACTORY_DOCKER', 'FACTORY_ABRUN', 'ABRUN_RUNNER', 'ABRUN_PREFLIGHT_RUNNER',
                'ABRUN_PREFLIGHT_CACHE_DIR', 'FACTORY_OM_RUN'):
        if key in os.environ:
            env[key] = os.environ[key]
    return manager.jobs.submit(task_id, 'lab', request, idem_key, 'gpu', argv,
                               LAB_TIMEOUT * 4 * rounds, env)


def gate_evaluate(grouped):
    # Execute the stdlib gate without importing the donor package or writing pycache.
    gate = runpy.run_path(str(SIMINFENG_ROOT / 'cc/abrun/gate.py'))
    return gate['evaluate'](grouped, metric='eval_ms_per_token', direction='lower')


def analyse(request, content):
    verdict = json.loads(content.get('ab/verdict.json', b'{}'))
    spec = request['spec']
    order = ['base', 'candidate', 'candidate', 'base'] * spec['rounds']
    grouped = {'base': [], 'candidate': []}
    problems = []
    if json.loads(content.get('worker.json', b'{}')).get('execution_outcome') != 'ok':
        problems.append('A/B worker did not complete successfully')
    if 'ab/REPORT.md' not in content:
        problems.append('A/B report missing')
    engagement = []
    candidate_checks = request['component_material']['engagement_checks']
    for index, arm in enumerate(order, 1):
        prefix = f'ab/{index:03d}-{arm}/'
        required = ['summary.json', 'stdout.txt', 'stderr.txt', 'result.json', 'telemetry.jsonl', 'watchdog.jsonl']
        if any(prefix + name not in content for name in required):
            problems.append(prefix + 'missing run evidence')
            continue
        summary = json.loads(content[prefix + 'summary.json'])
        stderr = content[prefix + 'stderr.txt'].decode(errors='replace')
        result = json.loads(content[prefix + 'result.json'])
        sha = hashlib.sha256(content[prefix + 'stdout.txt']).hexdigest()
        if summary.get('output_sha') not in {sha, sha[:12]}:
            problems.append(prefix + 'summary stdout hash differs from raw output')
        # Printed timing is the gate metric; summaries/verdict cannot override raw evidence.
        timings = re.findall(r'(?<!prompt )\beval time[^\n]*?\(\s*([\d.]+) ms per token', stderr)
        metric = float(timings[-1]) if timings else None
        failed = (result.get('status') != 'ok' or result.get('exit_code') != 0
                  or result.get('watchdog_trips') or result.get('oom_killed')
                  or b'watchdog_trip' in content[prefix + 'watchdog.jsonl'])
        if summary.get('contaminated') or summary.get('concurrent_jobs'):
            problems.append(prefix + 'contaminated run')
        if failed or summary.get('status') != 'ok':
            problems.append(prefix + 'unsuccessful run')
        for regex in spec['arms']['candidate']['switch_regex']:
            matched = re.search(regex, stderr) is not None
            expected = arm == 'candidate' or spec['arms']['base'].get('switch_regex_is_config', False)
            if expected != matched:
                problems.append(prefix + 'activation mismatch: ' + regex)
        if arm == 'candidate':
            for check_index, check in enumerate(candidate_checks):
                status = 'pass' if re.search(check['regex'], stderr) else 'fail'
                if check['source'] == 'threads':
                    capture = content.get(prefix + 'threads.summary.json')
                    threads = json.loads(capture).get('threads', {}) if capture else None
                    status = ('not_measured' if not threads or not any(t.get('samples', 0) > 0 for t in threads.values()) else 'pass' if any(
                        re.search(check['regex'], t.get('comm', '')) and t.get('samples', 0) > 0
                        for t in threads.values()) else 'fail')
                engagement.append(dict(run=prefix, id=check.get('id', str(check_index)),
                                       source=check['source'], status=status))
        # Preserve descriptive per-run summaries as artifacts; score only parsed evidence.
        grouped[arm].append(dict(summary, status='failed' if failed else summary.get('status'),
                                 output_sha=sha, eval_ms_per_token=metric))
    recomputed = gate_evaluate(grouped)
    if verdict.get('status') != 'completed' or verdict.get('invalid_reasons'):
        problems.append('abrun verdict is INVALID')
    if verdict.get('output', {}).get('class') != recomputed['output']['class']:
        problems.append('abrun output classification differs from raw evidence')
    reference = contracts.reference_info(request['contract']).get('stdout_sha256')
    base_hashes = recomputed['output']['hashes']['base']
    identical = (recomputed['output']['class'] == 'identical' and bool(reference)
                 and len(base_hashes) == 2 * spec['rounds']
                 and all(h == reference for h in base_hashes))
    comparison = recomputed['comparisons']['candidate']
    problems += recomputed['reasons']
    signal_problems = [c['run'] + ' engagement ' + c['status'] for c in engagement if c['status'] != 'pass']
    values = dict(engagement=engagement, gate=comparison['verdict'] if not problems else 'invalid', ratio=comparison['ratio'],
                  aa_gap=recomputed['aa_gap'], output_class=recomputed['output']['class'],
                  per_arm_ms=recomputed['means'], drift=recomputed['drift'],
                  threshold=recomputed['threshold'], component=request['component'],
                  measure=request['component_material']['measure'], problems=problems)
    if request['component_material']['measure'] == 'none' and values['gate'] != 'invalid':
        values['gate'] = 'not_measured'
    evaluation = dict(execution_outcome='candidate_failed' if not identical else
                      ('measurement_failed' if problems else 'ok'),
                      correctness='pass' if identical else 'fail',
                      evidence_completeness='partial' if problems else 'complete')
    values['acceptance'] = acceptance(request['component_material'], values, evaluation)
    evaluation['acceptance'] = values['acceptance']
    if signal_problems:
        values['problems'] += signal_problems
        if request['component_material'].get('acceptance', {}).get('type', 'performance') == 'performance':
            values['gate'] = 'invalid'
        evaluation.update(execution_outcome='measurement_failed' if identical else 'candidate_failed', evidence_completeness='partial')
    return values, evaluation, recomputed


def ingest(manager, task_id, run_id, root):
    from .manager import UploadConflict
    raw = (root / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    digest = hashlib.sha256(raw).hexdigest()
    if manifest['task_id'] != task_id or manifest['lab_run_id'] != run_id:
        raise ValueError('A/B upload identity differs')
    with manager.jobs.locked():
        attempt = manager.store._get('attempts', task_id, run_id)
        if attempt['kind'] != 'lab' or attempt['request'].get('mode') != 'ab':
            raise ValueError('A/B upload requires an A/B lab attempt')
        previous = manager.store._db.execute('SELECT sha256 FROM uploads WHERE task_id=? AND lab_run_id=?',
                                            (task_id, run_id)).fetchone()
        if previous and previous['sha256'] != digest:
            raise UploadConflict('A/B run already names different bytes')
        content = {}
        for name, sha in manifest['files'].items():
            path = (root / name).resolve()
            if (Path(name).is_absolute() or '..' in Path(name).parts or not path.is_relative_to(root)
                    or name in {'manifest.json', 'ack.json'} or not path.is_file()):
                raise ValueError('A/B manifest path escapes bundle or is missing')
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != sha:
                raise UploadConflict('A/B manifest SHA256 mismatch')
            content[name] = data
        request = attempt['request']
        if json.loads(content['config.json']) != dict(request, lab_run_id=run_id):
            raise ValueError('A/B configuration differs from submitted request')
        ack = dict(upload_id=run_id + ':upload', sha256=digest, ack_state='durable')
        if not previous:
            values, evaluation, recomputed = analyse(request, content)
            refs = []
            for name, data in {'manifest.json': raw, **content}.items():
                artifact = manager.store.put_artifact(task_id, run_id + ':' + name, data,
                    'application/json' if name.endswith('.json') else 'text/plain', run_id)
                refs.append(artifact['artifact_id'])
            with manager.store._transaction():
                now = time.time()
                obs_id, eval_id = run_id + ':observation', run_id + ':evaluation'
                manager.store._insert('observations', dict(obs_id=obs_id, task_id=task_id,
                    source_artifacts=refs.copy(), kind='ab_result', values=values, error={},
                    host_run=dict(attempt_id=run_id), confidence=None,
                    limitations=request['contract']['scope'], created=now))
                manager.store._insert('evaluations', dict(eval_id=eval_id, task_id=task_id,
                    contract_id=request['contract']['contract_id'], contract_version=str(request['contract']['version']),
                    contract=request['contract'], inputs=dict(acceptance=evaluation['acceptance'], ab_result=values, verdict=recomputed,
                        source_artifacts=refs.copy(), observation_id=obs_id), **{k: v for k, v in evaluation.items() if k != 'acceptance'}, created=now))
                refs += [obs_id, eval_id]
                current = manager.store._get('attempts', task_id, run_id)
                current['result_refs'] = refs
                manager.store._db.execute('UPDATE attempts SET result_refs=? WHERE task_id=? AND attempt_id=?',
                                         (encoded(refs), task_id, run_id))
                manager.store._event('attempts', current)
                manager.store._insert('uploads', dict(task_id=task_id, lab_run_id=run_id,
                    upload_id=ack['upload_id'], sha256=digest, ack_state='durable', created=now))
        contracts.atomic_json(root / 'ack.json', ack)
        return ack


def acceptance(material, values, evaluation):
    rule = material.get('acceptance', {'type': 'performance'})
    kind, reasons = rule['type'], []
    result = dict(type=kind, verdict='accept', reasons=reasons)
    checks = values.get('engagement', [])
    if (values['gate'] == 'invalid' or evaluation['execution_outcome'] != 'ok'
            or evaluation['evidence_completeness'] != 'complete'
            or any(c['status'] == 'not_measured' for c in checks)):
        result['verdict'] = 'invalid'
        reasons.append('Incomplete or invalid measurement; required signal may be not_measured')
    elif evaluation['correctness'] != 'pass':
        result['verdict'] = 'reject'
        reasons.append('Correctness did not pass')
    elif any(c['status'] != 'pass' for c in checks):
        result['verdict'] = 'reject'
        reasons.append('Candidate engagement checks did not all pass')
    elif kind == 'performance' and values['gate'] != 'improved':
        result['verdict'] = 'reject'
        reasons.append('Performance requires gate improved')
    elif kind == 'observability':
        ratio = values.get('ratio')
        if not checks or ratio is None or ratio <= 0:
            result['verdict'] = 'invalid'
            reasons.append('Signal or overhead was not measured')
        elif (1 / ratio - 1 > max(rule['overhead_bound'], values['threshold'])
              and not math.isclose(1 / ratio - 1, max(rule['overhead_bound'], values['threshold']), rel_tol=1e-12)):
            result['verdict'] = 'reject'
            reasons.append('Candidate overhead exceeds max(overhead_bound, gate threshold)')
    elif kind == 'prerequisite':
        result['verdict'] = 'reject'
        reasons.append('Use keep_dormant with source dependencies and runtime switch off')
    if result['verdict'] == 'accept':
        reasons.append('Correctness, engagement and module acceptance obligations passed')
    return result
