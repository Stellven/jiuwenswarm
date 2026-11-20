#!/usr/bin/env python3
"""Attach the frozen Granite WO3 scorer evidence to the original C2 report."""
import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess

from jiuwenswarm.factory.store import Store
from import_evidence import append_once
from report_p1 import json_bytes


ROOT = Path(__file__).resolve().parents[3]
REPO = ROOT / 'jiuwenswarm'
SCORER = ROOT / 'scorer-spark-v4-owner'
HOME = ROOT / 'factory-runs/star-weight_placement_planner'
TASK = 'spark-star-weight-placement-planner'
ITERATION = 'spark-c2-layer27-functional'
OBSERVATION = ITERATION + ':report-v2-granite-wo3'
PREFIX = ITERATION + '/granite-wo3-01/'
MANIFEST = ROOT / 'OPS/p3/granite-followup-launches.json'
MANIFEST_SHA = '526c98754f2257fb749b7135f76bef36fba7904e081ff52aa92c7f675693927b'
STAGES = ('S1', 'S2', 'S3', 'S4', 'S5', 'S5L', 'S6', 'S7')
APPLICABLE = ('S1', 'S2', 'S3', 'S4', 'S5', 'S6')
SCOPE_CONTROLS = {'memory.max': str(100 * 1024**3), 'memory.swap.max': '0', 'memory.oom.group': '1',
                  'cpu.max': '800000 100000', 'sched_affinity': list(range(8))}


def demand(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def preflight():
    demand(sha(MANIFEST) == MANIFEST_SHA, 'Granite follow-up manifest changed after freeze')
    plan = read(MANIFEST)
    arm = plan['arms']['C2']
    frozen = plan['scorer']
    source = arm['source']
    patch = Path(source['patch'])
    adapter = REPO / 'tools/spark_demo/scorer_adapter.py'
    platform = SCORER / 'platform-overrides.json'
    reference = SCORER / 'reference.json'
    receipt = SCORER / 'spark-stock-receipt.json'
    stock = ROOT / 'llama.cpp-stock'
    fixture = Path(plan['fixture']['path'])
    fixture_pin = ROOT / 'OPS/scorer-portability/granite-owner.sha256'
    pins = {patch: source['patch_sha256'], adapter: frozen['adapter_sha256'], platform: frozen['platform_overrides_sha256'],
            reference: frozen['reference_sha256'], receipt: frozen['stock_receipt_sha256'],
            Path(plan['stock_binary']['path']): plan['stock_binary']['sha256']}
    frozen_paths = {ROOT / 'inputs/ab' / path: digest for path, digest in frozen['frozen_sources'].items()}
    demand(all(sha(path) == digest for path, digest in (pins | frozen_paths).items()), 'Frozen scorer, patch or stock artifact digest changed')
    ref, platform_data, stock_receipt = read(reference), read(platform), read(receipt)
    fixture_sha = plan['fixture']['sha256']
    demand(fixture.stat().st_size == plan['fixture']['size'] and fixture_pin.read_text().strip() == fixture_sha ==
           ref['model_sha256'] == platform_data['fixture_expected_sha256'], 'Granite fixture receipt differs from the frozen model')
    demand(plan['stock_commit'] == source['base'] == ref['stock_commit'] == platform_data['stock_commit'] ==
           stock_receipt['source_commit'] and stock_receipt['source_verified'] and
           stock_receipt['binaries']['llama-server'] == plan['stock_binary'], 'Granite stock reference and binary provenance differ')
    head = subprocess.check_output(['git', '-C', str(stock), 'rev-parse', 'HEAD'], text=True).strip()
    demand(head == plan['stock_commit'] and not subprocess.check_output(
        ['git', '-C', str(stock), 'status', '--porcelain=v1', '--untracked-files=all', '--ignored']), 'Granite stock checkout is no longer pristine')
    subprocess.run(['git', '-C', str(stock), 'apply', '--check', '--', str(patch)], check=True)
    return plan, arm, fixture, ref, {p.name: p for p in (*pins.keys(), *frozen_paths.keys(), fixture_pin, MANIFEST) if p.name != 'llama-server'}


def cap_evidence(arm):
    scope = Path(arm['cap_scope'])
    start, result, controls = (read(scope / (name + '.json')) for name in ('start', 'result', 'scope'))
    command = arm['argv'][arm['argv'].index('--') + 1:]
    fields = ('arm', 'command', 'binary_sha256', 'unit', 'result_path', 'start', 'memory_max', 'cpus')
    demand(all(start[k] == result[k] for k in fields) and result['command'] == command and result['arm'] == scope.name and
           result['result_path'] == str(scope) and result['scope_verified'] and result['returncode'] == 0 and result['reason'] is None and
           not result['enforcement_test'] and not result['requires_review'] and result['min_mem_available_bytes'] >= 8 * 1024**3 and
           all(int(result['memory_events'].get(key, 0)) == 0 for key in ('oom', 'oom_kill', 'oom_group_kill')) and
           'Result=oom-kill' not in result['systemd_properties'] and (scope / 'monitor.ready').exists() and
           all(controls['actual'][key] == value for key, value in SCOPE_CONTROLS.items()), 'Granite WO3 requires the exact clean capped scorer command')
    return scope, result


def ledger_rows(runtime, fixture_sha, binary, cap):
    ledger = ROOT / 'OPS/LEDGER.jsonl'
    rows = []
    digest = sha(binary)
    for raw in ledger.read_bytes().splitlines():
        if str(runtime).encode() not in raw:
            continue
        item = json.loads(raw)
        path = Path(item['result_path'])
        if not path.is_relative_to(runtime):
            continue
        demand(item['model_sha256'] == fixture_sha and item['binary_sha256'] == digest and Path(item['command'][0]) == binary and
               datetime.fromisoformat(cap['start']) <= datetime.fromisoformat(item['utc']) <=
               datetime.fromisoformat(item.get('utc_stop', item['utc'])) <= datetime.fromisoformat(cap['stop']),
               'Granite runtime ledger does not bind the candidate scorer build and fixture')
        rows.append(item)
    pairs = {}
    for row in rows:
        pairs.setdefault(row['result_path'], []).append(row['event'])
    demand(all(events == ['start', 'stop'] for events in pairs.values()), 'Granite runtime ledger has incomplete process pairs')
    return digest, rows


def gather(plan, arm, fixture, ref, files):
    scope, cap = cap_evidence(arm)
    fixture_sha = plan['fixture']['sha256']
    demand(sha(fixture) == fixture_sha, 'Granite fixture bytes differ from the frozen owner digest')
    directory = Path(arm['score_dir'])
    score = read(directory / 'score.json')
    demand(score['wo'] == arm['work_order'] == 3 and score['scorer_version'] == 4 and
           score['stock_commit'] == plan['stock_commit'] and score['patch_sha256'] == arm['source']['patch_sha256'],
           'Score identity disagrees with the frozen Granite WO3 launch')
    stages = score['stages']
    score_log = directory / 'score.log'
    logged = {}
    for line in score_log.read_text().splitlines():
        stage, _, verdict = line.partition(' ')
        if stage in STAGES:
            logged[stage] = verdict.split(' ', 1)[0]
    demand(set(stages) == set(STAGES) and logged == {name: row['status'] for name, row in stages.items()} and
           all(stages[key]['status'] == 'skipped' for key in ('S5L', 'S7')) and
           score['done_claimable'] == all(stages[key]['status'] == 'pass' for key in STAGES[:5]),
           'Frozen stage verdict log differs from score.json')
    work = Path(score['work_dir']).resolve(strict=True)
    demand(work.is_relative_to(directory), 'Scorer attempt escaped its frozen output directory')
    runtime, binary_sha, ledger = None, None, []
    if score.get('runtime_dir'):
        runtime = Path(score['runtime_dir']).resolve(strict=True)
        build = Path(stages['S3']['build_dir']).resolve(strict=True)
        demand(runtime.is_relative_to(work) and build.is_relative_to(work) and
               score['reference_sha256'] == plan['scorer']['reference_sha256'],
               'Scorer runtime paths or loaded reference differ from their frozen provenance')
        binary_sha, ledger = ledger_rows(runtime, fixture_sha, build / 'bin/llama-server', cap)
    placement = stages['S6']
    if placement['status'] == 'pass':
        stock = ref['placement']
        actual_plan = Path(placement['plan'])
        demand(actual_plan == runtime / 'S6/plan.json' and read(actual_plan) == {'version': 1, 'overrides': [
            {'pattern': stock['pattern'], 'buft': 'CPU'}]} and placement['pattern'] == stock['pattern'] and
            placement['active_reached'] is True and placement['counters']['assigned'] == 24 and
            placement['tokens_sha256'] == placement['stock_ot_tokens_sha256'] == stock['tokens_sha256'] and
            placement['model_buffers'] == placement['stock_ot_model_buffers'] == stock['model_buffers'] and
            any(row['result_path'] == str(runtime / 'S6/candidate-plan') and row.get('outcome') == 'completed' for row in ledger),
            'S6 passed without the 24-tensor placement, stock token and buffer evidence')
    complete = all(stages[name]['status'] == 'pass' for name in APPLICABLE)
    files |= {'score.json': directory / 'score.json', 'score.log': score_log,
              **{f'cap/{name}': scope / name for name in ('start.json', 'scope.json', 'result.json', 'memory.jsonl', 'systemd-final.txt', 'stdout.log', 'stderr.log')}}
    if stages['S3'].get('build_log'):
        build_log = Path(stages['S3']['build_log']).resolve(strict=True)
        demand(build_log.is_relative_to(work), 'Frozen S3 build log escaped its work directory')
        files['build.log'] = build_log
    if runtime:
        for path in (runtime / 'S6').rglob('*'):
            if path.is_file() and path.suffix in ('.json', '.log', '.txt'):
                files['runtime/' + path.relative_to(runtime).as_posix()] = path
    outcome = 'pass' if complete else 'failed or incomplete'
    result = dict(schema='spark-c2-granite-wo3/1', source_commit=arm['source']['source_commit'], patch_sha256=score['patch_sha256'],
                  stock_commit=score['stock_commit'], stock_binary_sha256=plan['stock_binary']['sha256'], fixture_sha256=fixture_sha,
                  reference_sha256=plan['scorer']['reference_sha256'], runtime_reference_sha256=score.get('reference_sha256'),
                  candidate_scorer_binary_sha256=binary_sha, scorer_version=4, outcome=outcome,
                  done_claimable_s1_s5=score['done_claimable'], stages=stages, cap=cap)
    return result, files, ledger


def render(evidence):
    lines = ['## Independent Granite WO3 score', '', f'The frozen v4 scorer recorded **{evidence["outcome"]}** for '
             'the original C2 patch. The test used the owner-pinned Granite fixture and matched same-host stock reference.', '',
             '| Stage | Status | Frozen verdict |', '| --- | --- | --- |']
    stages = evidence['stages']
    lines.extend(f'| {key} | {stages[key]["status"]} | {stages[key]["reason"].replace("|", "&#124;")} |' for key in STAGES)
    lines.extend(['', 'S5 checks the generic gate with no placement plan. S6 supplies the actual fixture override.', ''])
    if stages['S6']['status'] == 'pass':
        lines.extend(['S6 assigned all 24 Granite down-expert tensors and reproduced the stock `-ot` greedy token hash '
                      'and buffer allocations.', ''])
    lines.append('The DeepSeek layer-27 functional result above used a separate model and placement policy.')
    return '\n'.join(lines).encode()


def publish(evidence, files, ledger):
    with Store(HOME) as store:
        old = store.read(TASK, ITERATION + ':report')
        envelope = old['values']
        original = envelope['report']
        demand(envelope['do']['source_commit'] == evidence['source_commit'] and
               store.read_artifact(TASK, envelope['do']['diff_artifact_id'])['sha256'] == evidence['patch_sha256'],
               'Original C2 factory task points at a different source patch')
        refs = {}

        def put(artifact, content, media):
            row = store.put_artifact(TASK, artifact, content, media, None)
            refs[artifact] = row['sha256']
            return dict(artifact_id=artifact, sha256=row['sha256'])

        for name, path in files.items():
            media = 'application/json' if path.suffix == '.json' else 'text/plain'
            put(PREFIX + name, path, media)
        put(PREFIX + 'runtime-ledger.json', json_bytes(ledger), 'application/json')
        evidence['artifact_sha256'] = dict(refs)
        sidecar = put(PREFIX + 'fixture-evidence.json', json_bytes(evidence), 'application/json')
        report = store.artifact_bytes(TASK, original['artifact_id']).rstrip() + b'\n\n' + render(evidence).rstrip() + b'\n'
        ref = put(ITERATION + '/report-v2-granite-wo3.md', report, 'text/markdown')
        envelope['lab']['independent_fixture'] = dict(sidecar, status=evidence['outcome'], work_order=3)
        envelope['lab']['result_artifact_ids'] += [item for item in refs if item != ref['artifact_id']]
        envelope['report'] = dict(original, **ref, revision=2, supersedes_artifact_id=original['artifact_id'],
                                  supersedes_observation_id=old['obs_id'], status='Granite WO3 ' + evidence['outcome'],
                                  summary=original['summary'] + f' Independent Granite WO3 outcome was {evidence["outcome"]}.')
        append_once(store, TASK, dict(obs_id=OBSERVATION, kind='factory_iteration_report_revision', values=envelope,
                                      source_artifacts=list(dict.fromkeys([*old['source_artifacts'], original['artifact_id'], *refs]))))
    out = ROOT / 'OPS/iterations' / ITERATION
    (out / 'report-v2-granite-wo3.md').write_bytes(report)
    (out / 'iteration-v2-granite-wo3.json').write_bytes(json_bytes(envelope))
    (out / 'granite-wo3-fixture-evidence.json').write_bytes(json_bytes(evidence))
    return dict(task=TASK, observation=OBSERVATION, report=ref, fixture_evidence=sidecar,
                relative_report=f'OPS/iterations/{ITERATION}/report-v2-granite-wo3.md', outcome=evidence['outcome'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check frozen static provenance without reading the full fixture or publishing')
    args = parser.parse_args()
    inputs = preflight()
    if args.check:
        print(f'Frozen WO3 manifest {MANIFEST_SHA} verified. No scorer or model started.')
    else:
        print(json_bytes(publish(*gather(*inputs))).decode(), end='')
