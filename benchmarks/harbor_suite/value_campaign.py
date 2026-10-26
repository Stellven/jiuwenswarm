"""Thin exploratory campaign tools around the existing Harbor suite.

Prepare existing tasks, retain original assessments and run explicit Harbor
jobs once. No new product protocol, acceptance rule or automatic retry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

from .contracts import EXTENDED, canonical, load_cases, read_json, regular
from .report import summarize
from .value_data import Dataset, public_record, utc_now, write_once

DEFAULT_CASES = ('cc01-transfer', 'cc02-binding', 'vf01-mechanical', 'vf02-semantic')
CHARTS = [
    {'id': 'outcomes', 'question': 'Which selected tasks deliver correct results, wrong results, expected halts or unavailable results?'},
    {'id': 'fault-detection', 'question': 'Which deterministic or semantic faults are caught, and which clean results are rejected?'},
    {'id': 'efficiency', 'question': 'What total observed calls, tokens and elapsed time buy a correct delivery?'},
    {'id': 'propagation', 'question': 'Which faulty artifacts reach successors and incur actual downstream work?'}]


def plan(destination, *, cases_root=None, case_ids=DEFAULT_CASES, repeats=1):
    if type(repeats) is not int or not 1 <= repeats <= 100:
        raise ValueError('repeats must be 1..100')
    cases = (load_cases(cases_root, case_ids=case_ids) if any(c in EXTENDED for c in case_ids)
             else load_cases(cases_root))
    if not case_ids or len(set(case_ids)) != len(case_ids) or set(case_ids) - {c['id'] for c in cases}:
        raise ValueError('select unique existing cases')
    selected = [c for c in cases if c['id'] in case_ids]
    result = {'schema': 'ai4r-value-plan:1', 'created_at': utc_now(), 'split': 'development',
              'purpose': 'Selected value demonstrations to guide continued development; not representative scientific evaluation.',
              'charts': CHARTS, 'cases': selected,
              'scheduled': [{'case_id': c['id'], 'variant_id': v['id'], 'repeat': repeat,
                             'expected_behavior': v['expected_behavior'], 'state': 'planned'}
                            for c in selected for v in c['variants'] for repeat in range(1, repeats + 1)],
              'selection_policy': 'Explore, tune and select useful wins; retain all outcomes and immutable earlier versions.',
              'baseline_identities': ['native_codex_tool_free', 'openjiuwen_react_diagnostic', 'jiuwenswarm_native'],
              'baseline_note': 'These are different systems. Only label an arm with the adapter actually executed.'}
    write_once(destination, result)
    return result


def import_job(dataset, bundle, job_results, *, arm='ai4r', revision=None, source_json=()):
    """Use existing strict task/model/single-job accounting before adoption."""
    data = Dataset(dataset)
    index = read_json(regular(Path(bundle) / 'task-index.json'))
    paths = sorted(Path(job_results).glob('*/verifier/assessment.json'))
    assessments = [read_json(regular(path)) for path in paths]
    # Reject foreign/duplicate observations before persisting any source.
    summary = summarize(index, assessments)
    public_record(summary)
    index_ref = data.artifact(Path(bundle) / 'task-index.json')
    identity = hashlib.sha256(canonical({'index': index_ref['sha256'],
        'job': str(Path(job_results).absolute()), 'arm': arm, 'revision': revision})).hexdigest()
    observed = {(r['case_id'], r['variant_id'], r['repeat']): (r, p) for r, p in zip(assessments, paths)}
    # Persist one import batch atomically as a single immutable record. An exact
    # re-import cannot inflate denominators; a new revision/job has its own ID.
    ident = 'job-' + identity
    if (data.root / 'records' / (ident + '.json')).exists():
        raise FileExistsError('job already imported; preserve original population')
    rows = []
    for task in index['tasks']:
        key = (task['case_id'], task['variant_id'], task['repeat'])
        result, path = observed.get(key, (None, None))
        row = {'case_id': key[0], 'variant_id': key[1], 'repeat': key[2],
               'task_sha256': hashlib.sha256(canonical(task)).hexdigest(),
               'arm': arm, 'revision': revision, 'mode': 'harbor_suite',
               'expected_behavior': task['variant']['expected_behavior'],
               'expected_model': task['expected_model'],
               'status': result['status'] if result else 'not_observed',
               'correct': result.get('case_correctness') if result else None,
               'available': result.get('execution_available') if result else None,
               'source': data.artifact(path) if path else None,
               'metrics': result.get('metrics', {}) if result else {},
               'checks': result.get('checks', []) if result else [],
               'critical_violations': result.get('critical_violations', []) if result else [],
               'missing_measurements': 'Usage, timings and resources require original exported telemetry; never infer zero.'}
        rows.append(row)
    retained = [data.artifact(p) for p in source_json]
    for name in ('bundle-manifest.json', 'job.json'):
        path = Path(bundle) / name
        if path.is_file():
            retained.append(data.artifact(path))
    return data.append('harbor_job', {'job_id': identity, 'index': index_ref,
        'summary': summary, 'rows': rows, 'retained_sources': retained,
        'evidence_scope': 'Assessment/index import plus explicit retained JSON sources; '
            'not a complete replayable product export or independent provider authentication.'}, record_id=ident)


def import_comparison(dataset, path, *, assignment=None, baseline=None, cc=None, criteria=None,
                      variant=None, quality_port=None):
    """Recompute from retained inputs, or retain summary-only without gain credit."""
    data = Dataset(dataset)
    result = read_json(regular(path))
    if result.get('schema') != 'native-codex-ai4r-paired-comparison:1':
        raise ValueError('expected original comparison.compare result')
    public_record(result)
    if (set(result.get('arms', {})) != {'native_codex_tool_free', 'ai4r_cc'}
            or result.get('sample_pairs') != 1
            or not isinstance(result.get('assignment_sha256'), str)
            or len(result['assignment_sha256']) != 64
            or any(c not in '0123456789abcdef' for c in result['assignment_sha256'])):
        raise ValueError('incomplete or invalid paired comparison summary')
    inputs = (assignment, baseline, cc, criteria, variant, quality_port)
    sources = []
    verified = all(item is not None for item in inputs)
    if any(item is not None for item in inputs) and not verified:
        raise ValueError('all frozen comparison inputs are required for recomputation')
    if verified:
        from .comparison import compare
        recomputed = compare(read_json(assignment), read_json(baseline), read_json(cc),
            variant=read_json(criteria)['variants'][variant], quality_port=quality_port)
        if canonical(recomputed) != canonical(result):
            raise ValueError('comparison summary differs from original inputs and shared oracle')
        sources = [data.artifact(p) for p in (assignment, baseline, cc, criteria)]
    source = data.artifact(path)
    return data.append('comparison' if verified else 'comparison_summary',
        {'source': source, 'result': result, 'retained_inputs': sources, 'recomputed': verified,
         'provenance': 'Offline recomputation only; original private provider/custody receipts remain separately required.'
                       if verified else 'Unvalidated summary, excluded from paired-gain analysis.'},
        record_id=('pair-' if verified else 'summary-') + source['sha256'])


def launch_once(dataset, job_config, *, harbor_executable='harbor', timeout_s=900, suite_config=None):
    """Launch one existing Harbor config; uncertain/failed jobs are never retried.

    The immutable claim is deliberately left in place for every outcome. Collect
    the original job or prepare a genuinely new scope; never remove the claim to
    bypass an interrupted dispatch. Harbor owns provider containment/recovery.
    """
    if type(timeout_s) not in (int, float) or not 1 <= timeout_s <= 86400:
        raise ValueError('finite positive timeout required')
    data = Dataset(dataset)
    config = regular(job_config)
    raw = config.read_bytes()
    job = read_json(config)
    if (job.get('n_attempts') != 1 or job.get('n_concurrent_trials') != 1
            or job.get('retry', {}).get('max_retries') != 0):
        raise ValueError('serial single-attempt zero-retry Harbor job required')
    digest = hashlib.sha256(raw).hexdigest()
    argv = [str(harbor_executable), 'run', '--config', str(config)]
    environment = os.environ.copy()
    if suite_config is not None:
        environment['AI4R_HARBOR_SUITE_CONFIG'] = str(regular(suite_config))
    claim = {'schema': 'ai4r-value-launch:1', 'job_sha256': digest,
             'created_at': utc_now(), 'argv': argv}
    public_record(claim)
    write_once(data.root / 'claims' / (digest + '.json'), claim)
    # Unknown/failed controller outcomes block other jobs in this shared dataset
    # as well. Existing Harbor/provider recovery still owns remote containment.
    active = data.root / 'claims' / 'active.json'
    write_once(active, claim)
    began = time.monotonic()
    data.append('launch_started', claim)
    try:
        # Inherit console rather than retain possibly sensitive host stdout.
        # Original trial artifacts remain in Harbor's own result directories.
        result = subprocess.run(argv, env=environment, timeout=timeout_s, check=False)
        status = 'controller_completed' if result.returncode == 0 else 'controller_failed'
        code = result.returncode
    except subprocess.TimeoutExpired:
        status, code = 'outcome_unknown', None
    except (KeyboardInterrupt, OSError):
        data.append('launch_finished', {**claim, 'status': 'outcome_unknown',
                    'elapsed_s': time.monotonic() - began, 'returncode': None})
        raise
    result = data.append('launch_finished', {**claim, 'status': status,
                         'elapsed_s': time.monotonic() - began, 'returncode': code})
    if status == 'controller_completed':
        # Keep the durable original claim. A successful controller lifecycle is
        # not a task-quality pass; the grader imports that independently.
        os.replace(active, data.root / 'claims' / ('closed-' + digest + '.json'))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('plan')
    prep.add_argument('--output', type=Path, required=True)
    prep.add_argument('--cases-root', type=Path)
    prep.add_argument('--case', action='append', dest='case_ids')
    prep.add_argument('--repeats', type=int, default=1)
    imp = commands.add_parser('import-job')
    for key in ('dataset', 'bundle', 'job-results'):
        imp.add_argument('--' + key, type=Path, required=True)
    imp.add_argument('--arm', default='ai4r')
    imp.add_argument('--revision')
    imp.add_argument('--source-json', type=Path, action='append', default=[])
    pair = commands.add_parser('import-comparison')
    pair.add_argument('--dataset', type=Path, required=True)
    pair.add_argument('--source', type=Path, required=True)
    for key in ('assignment', 'baseline', 'cc', 'criteria'):
        pair.add_argument('--' + key, type=Path)
    pair.add_argument('--variant')
    pair.add_argument('--quality-port')
    launch = commands.add_parser('launch')
    launch.add_argument('--dataset', type=Path, required=True)
    launch.add_argument('--job-config', type=Path, required=True)
    launch.add_argument('--suite-config', type=Path)
    launch.add_argument('--harbor-executable', default='harbor')
    launch.add_argument('--timeout-s', type=float, default=900)
    backup = commands.add_parser('backup')
    backup.add_argument('--dataset', type=Path, required=True)
    backup.add_argument('--destination', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        result = plan(args.output, cases_root=args.cases_root,
                      case_ids=args.case_ids or DEFAULT_CASES, repeats=args.repeats)
        print(json.dumps({'scheduled': len(result['scheduled']), 'output': str(args.output)}))
    elif args.command == 'import-job':
        result = import_job(args.dataset, args.bundle, args.job_results, arm=args.arm,
                            revision=args.revision, source_json=args.source_json)
        print(json.dumps({'record_id': result['id'], 'summary': result['value']['summary']}))
    elif args.command == 'import-comparison':
        result = import_comparison(args.dataset, args.source, assignment=args.assignment,
            baseline=args.baseline, cc=args.cc, criteria=args.criteria,
            variant=args.variant, quality_port=args.quality_port)
        print(json.dumps({'record_id': result['id']}))
    elif args.command == 'backup':
        print(json.dumps(Dataset(args.dataset).mirror(args.destination)))
    else:
        result = launch_once(args.dataset, args.job_config, harbor_executable=args.harbor_executable,
                             timeout_s=args.timeout_s, suite_config=args.suite_config)
        print(json.dumps({'record_id': result['id'], 'status': result['value']['status']}))
        return int(result['value']['status'] != 'controller_completed')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
