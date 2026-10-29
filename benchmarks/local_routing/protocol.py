"""Freeze public assignments separately from the independent reviewer material."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from benchmarks.harbor_suite.contracts import canonical, pin, read_json, regular, validate_case

PROTOCOL = 'ai4r-local-routing-development:1'
ROOT = Path(__file__).resolve().parents[2]
CODE = ('benchmarks/local_routing/protocol.py', 'benchmarks/local_routing/runtime.py',
        'benchmarks/local_routing/score.py', 'jiuwenswarm/research/automatic_routing.py',
        'jiuwenswarm/research/bridge.py', 'jiuwenswarm/research/model_settings.py',
        'jiuwenswarm/research/providers.py', 'jiuwenswarm/research/local_pool_registry.py',
        'jiuwenswarm/research/routing_component.py',
        'jiuwenswarm/research/state.py')


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical(value))


def code_pins():
    return {name: pin(ROOT / name) for name in CODE}


def prepare(cases_root, models, workspace, *, mode='smoke', case_ids=(), variant_ids=()):
    from jiuwenswarm.research.local_pool_registry import LocalModelRegistry
    workspace = Path(workspace).absolute()
    reviewer = workspace.with_name(workspace.name+'-reviewer')
    if workspace.exists() or reviewer.exists() or any(p.is_symlink() for p in (workspace, *workspace.parents)):
        raise ValueError('Use a new workspace; retained attempts must not be overwritten')
    revision, entries = LocalModelRegistry(Path(models).absolute()).configuration()
    if not revision or {e['id'] for e in entries if e['enabled']} != {'e4b', 'qwen', 'bolt'}:
        raise ValueError('Configure all three real local services before freezing this protocol')
    if mode not in {'smoke', 'campaign'}:
        raise ValueError('Unknown measurement mode')
    cases_root = Path(cases_root).absolute()
    if workspace.is_relative_to(cases_root) or cases_root.is_relative_to(workspace):
        raise ValueError('Keep the retained campaign separate from source cases')
    if set(case_ids) - {'mr01-quality', 'mr02-compatibility'}:
        raise ValueError('Only the two MR cases belong to this protocol')
    selected = []
    source_pins = {}
    for ident in ('mr01-quality', 'mr02-compatibility'):
        if case_ids and ident not in case_ids:
            continue
        folder = cases_root / ident
        case = validate_case(read_json(folder / 'case.json'), folder)
        source_pins[ident] = {n: pin(folder / n) for n in ('case.json', 'README.md', 'oracle.py', 'referee/criteria.json')}
        for variant in case['variants']:
            if variant_ids and variant['id'] not in variant_ids:
                continue
            inputs = []
            for item in variant['inputs']:
                raw = regular(folder / item['path']).read_bytes()
                fixture = json.loads(raw)
                inputs.append({'path': item['path'], 'sha256': hashlib.sha256(raw).hexdigest(), 'value': fixture})
            needs = {'modalities': ['text']}
            if ident == 'mr02-compatibility':
                needs.update({'context-window': {'min_context': 32768},
                    'unsupported-tool': {'tool_calling': True},
                    'unsupported-schema': {'native_structured_output': True}}.get(variant['id'], {}))
            declaration = {'identity': {'name': 'benchmark.bounded-json', 'version_label': 'local-1',
                'summary': 'Answer a bounded technical assignment as one JSON object, using only supplied facts.'},
                'needs': {'model': needs}, 'guarantees': {'acceptance':
                    ['One finite JSON object', 'No external sources or tools', 'Preserve the declared task and output rule']}}
            selected.append({'case_id': ident, 'variant_id': variant['id'], 'task': variant['task'],
                'inputs': inputs, 'declaration': declaration, 'budget': case['budgets'],
                'fault': variant['id'] if ident == 'mr02-compatibility' else None})
    if not selected or set(variant_ids) - {v['variant_id'] for v in selected}:
        raise ValueError('Select existing variants of the selected MR cases')
    try:
        commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.SubprocessError):
        source = ROOT / 'source-identity.json'
        commit = read_json(source).get('base_commit') if source.is_file() else None
    plan = {'schema': PROTOCOL, 'mode': mode, 'repeats': 1 if mode == 'smoke' else 3,
        'scope': 'isolated routing component; not admitted-CC, frontend, full-pipeline or original-MR acceptance',
        'baseline': 'qwen', 'selector': 'e4b', 'verifier': 'qwen', 'executor_pool': ['e4b', 'qwen', 'bolt'],
        'model_configuration': {'path': str(Path(models).absolute()), 'pin': pin(models), 'revision': revision},
        'models': entries, 'commit': commit, 'source_status': 'exact code hashes; base commit is not a clean-build claim',
        'code_pins': code_pins(), 'source_pins': source_pins,
        'reviewer_directory': str(reviewer),
        'limits': {'worker_time_s': 90, 'verifier_time_s': 60, 'output_tokens': 1024, 'concurrency': 1},
        'cost_policy': 'unknown self-hosted compute price; cost, savings and monetary regret remain null',
        'cases': selected}
    # Reviewer material stays in a sibling tree, never in the public run plan.
    reviewer_pins = {}
    for ident in source_pins:
        write_new(reviewer / (ident+'.json'), read_json(cases_root / ident / 'referee/criteria.json'))
        reviewer_pins[ident] = pin(reviewer / (ident+'.json'))
    plan['reviewer_pins'] = reviewer_pins
    write_new(workspace / 'plan.json', plan)
    write_new(workspace / 'plan-pin.json', pin(workspace / 'plan.json'))
    return plan


def load_plan(workspace):
    workspace = Path(workspace).absolute()
    if pin(workspace / 'plan.json') != read_json(workspace / 'plan-pin.json'):
        raise ValueError('Frozen plan changed')
    plan = read_json(workspace / 'plan.json')
    if plan['schema'] != PROTOCOL or plan['code_pins'] != code_pins():
        raise ValueError('Controller/production code changed; prepare a new campaign')
    if pin(plan['model_configuration']['path']) != plan['model_configuration']['pin']:
        raise ValueError('Model endpoints changed; prepare a new campaign')
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--cases-root', type=Path, required=True)
    p.add_argument('--models', type=Path, required=True)
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--mode', choices=['smoke', 'campaign'], default='smoke')
    p.add_argument('--case', dest='case_ids', action='append', default=[])
    p.add_argument('--variant', dest='variant_ids', action='append', default=[])
    for name in ('doctor', 'run', 'score'):
        p = sub.add_parser(name); p.add_argument('--workspace', type=Path, required=True)
    args = vars(parser.parse_args(argv)); command = args.pop('command')
    if command == 'prepare':
        plan = prepare(**args)
        result = {'schema': plan['schema'], 'mode': plan['mode'], 'variants': len(plan['cases']), 'workspace': str(args['workspace'])}
    elif command == 'score':
        from .score import score
        result = score(args['workspace'])
    else:
        import asyncio
        from .runtime import doctor, run
        result = asyncio.run((doctor if command == 'doctor' else run)(args['workspace']))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
