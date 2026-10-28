"""Run C's existing integrity checks on the stored native JiuwenSwarm trap runs. No model calls, no docker.
Reads traps/ from AI4R_BENCH_DATA (never writes there); writes results.json and results-provenance.json under --out only.
Run: python -B -X utf8 run.py --out DIR   (product code from AI4R_CODE_ROOT, default: this repo)
Real check functions: jiuwenswarm.research.checks.integrity (pin_matches, baseline_consistent, units_consistent,
no_stale_duplicate, bound_feasible, split_disjoint) and checks.delivery_evidence.numbers_in. Everything else is glue
that turns native-run files into the arguments those functions take."""
import argparse
import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roots  # noqa: E402

PRODUCT = roots.code_root()
sys.path.insert(0, str(PRODUCT))
from jiuwenswarm.research.checks import integrity as I  # noqa: E402
from jiuwenswarm.research.checks.delivery_evidence import numbers_in  # noqa: E402

TRAPS = None   # set in main(): AI4R_BENCH_DATA/traps
SESS = None
# session prefix -> (planted-fault fixture, expected cause class or None for clean)
RUNS = [
    ('cb69e06d', 'baselinedef', 'baseline_definition_conflict'),
    ('f453cc3d', 'pinmismatch', 'environment_lock_pin_mismatch'),
    ('b4dbc372', 'stale', 'stale_or_duplicate_dataset'),
    ('154b9be6', 'units', 'metric_unit_conflict'),
    ('f473e481', 'units', 'metric_unit_conflict'),          # 2nd units attempt (run failed, no delivery)
    ('a02edd51', 'infeasible', 'infeasible_accuracy_bound'),
    ('0f7386e0', 'clean', None),
    ('7fb8e068', 'clean', None),
    ('cb8afcdb', 'clean', None),
    ('e6830418', 'conflicts', 'prose_requirement_conflict'),
    ('1fdc5eaf', 'overreach', 'unsupported_demands'),
]
CAUSE_OF_CHECK = {'pin': 'environment_lock_pin_mismatch', 'baseline': 'baseline_definition_conflict',
                  'units': 'metric_unit_conflict', 'stale': 'stale_or_duplicate_dataset',
                  'bound': 'infeasible_accuracy_bound', 'split': 'train_test_feature_overlap',
                  'claims': 'unsupported_numeric_claim'}
ORDER = ('pin', 'baseline', 'units', 'stale', 'bound', 'split', 'claims')


def sdir(prefix):
    return next(p for p in SESS.glob('trap-%s*' % prefix) if p.is_dir())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def final_text(s):
    out = ''
    f = s / 'native/run/events.jsonl'
    if not f.exists():
        return out
    for line in f.read_text(encoding='utf-8').splitlines():
        p = json.loads(line).get('payload')
        if isinstance(p, dict) and p.get('event_type') == 'chat.final' and p.get('content'):
            out += p['content']
    return out


def run_checks(s):
    inp = s / 'fixture/inputs'
    cases = json.loads((s / 'fixture/cases.json').read_text('utf-8'))['cases'][0]
    readme = (inp / 'README.md').read_text('utf-8')
    task_md = (inp / 'TASK.md').read_text('utf-8')
    text_all = readme + '\n' + task_md + '\n' + cases['task']
    pins = json.loads((inp / 'resource-pins.json').read_text('utf-8'))
    data = json.loads((inp / 'data.json').read_text('utf-8'))
    pm = s / 'private-measurement'
    scored = json.loads((pm / 'scored-response.json').read_text('utf-8')) if (pm / 'scored-response.json').exists() else None
    R = {}
    # 1 pin: environment lock bytes vs the host-record pin (the one pin that is a plain file-byte hash)
    R['pin'] = I.pin_matches((inp / 'environment-lock.json').read_bytes(),
                             pins['host_records']['environment_lock']['sha256'])
    # 1b naive variant: also pin baseline.zip / data.json bytes against the run_inputs pins (Store refs, not file hashes)
    R['pin_naive_extra'] = {k: I.pin_matches((inp / f).read_bytes(), pins['run_inputs'][k]['sha256'])
                            for k, f in (('baseline_resource', 'baseline.zip'), ('validation_resource', 'data.json'))}
    # 2 baseline definition vs replay (trusted-run baseline stdout); reference labels = training labels
    m = re.search(r'baseline, which predicts (\w+) for every test row', readme)
    definition = ('constant:' + m.group(1)) if m else ('majority_class' if 'majority-class baseline' in readme else None)
    base_out = pm / '01-baseline.stdout'
    if definition and base_out.exists():
        preds = [r['label'] for r in json.loads(base_out.read_text('utf-8'))['predictions']]
        R['baseline'] = I.baseline_consistent(definition, preds, [r['label'] for r in data['train']])
    else:
        R['baseline'] = {'ok': None, 'cause_class': 'not_assessable',
                         'evidence': [{'reason': 'no baseline replay output or definition'}]}
    # 3 units: declared unit of the accuracy metric, one entry per statement in the inputs
    acc = float(scored['metrics']['baseline'][0]) if scored else 0
    metrics = []
    if re.search(r'reported in percent', readme):
        metrics.append({'name': 'accuracy', 'unit': 'percent', 'value': acc, 'src': 'README'})
    if re.search(r'Metric accuracy \(fraction\)', cases['task']):
        metrics.append({'name': 'accuracy', 'unit': 'fraction', 'value': acc, 'src': 'task'})
    if re.search(r'Accuracy is the fraction', readme):
        metrics.append({'name': 'accuracy', 'unit': 'fraction', 'value': acc, 'src': 'README'})
    R['units'] = I.units_consistent([{k: v for k, v in x.items() if k != 'src'} for x in metrics])
    # 4 stale / duplicate dataset: manifest of files the run was given; role = dataset_id for dataset-shaped JSON
    entries = []
    for f in sorted(inp.iterdir()):
        role = f.name
        if f.suffix == '.json':
            try:
                j = json.loads(f.read_text('utf-8'))
                if isinstance(j, dict) and 'dataset_id' in j and 'train' in j:
                    role = 'dataset:' + j['dataset_id']
            except ValueError:
                pass
        entries.append({'path': f.name, 'sha256': sha(f), 'role': role, 'version': '1'})
    R['stale'] = I.no_stale_duplicate(entries)
    # 5 bound feasibility: absolute acceptance threshold stated as a fraction
    m = re.search(r'at least ([0-9]*\.?[0-9]+) as a fraction on the 0-1 scale', text_all)
    R['bound'] = I.bound_feasible((0, 1), m.group(1)) if m else {
        'ok': None, 'cause_class': 'not_applicable', 'evidence': [{'reason': 'no absolute threshold stated'}]}
    # 6 split overlap (train vs test features)
    R['split'] = I.split_disjoint(data['train'], data['test'], ['features'])
    # 7 numeric claims vs evidence: decimals in the final report must be measured accuracies, their differences,
    #   or numbers that appear in the inputs (heuristic extraction; hashes stripped first)
    txt = final_text(s)
    if scored and txt:
        b = [Decimal(str(x)) for x in scored['metrics']['baseline']]
        t = [Decimal(str(x)) for x in scored['metrics']['treatment']]
        allowed = set(b + t) | {x - y for x in t for y in b} | {v for _, v in numbers_in(text_all)}
        claims = [(mm.group(), v) for mm, v in numbers_in(re.sub(r'[0-9a-fA-F]{32,}', ' ', txt))
                  if '.' in mm.group() and not mm.group().startswith('.')]
        bad = [c for c, v in claims if v not in allowed]
        R['claims'] = {'ok': not bad, 'cause_class': 'unsupported_numeric_claim',
                       'evidence': [{'unsupported': bad, 'checked': len(claims)}]}
    else:
        R['claims'] = {'ok': None, 'cause_class': 'not_applicable',
                       'evidence': [{'reason': 'no delivered report or no scored response'}]}
    return R, txt, scored, {'definition': definition, 'unit_sources': metrics}


def main(argv=None):
    global TRAPS, SESS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='directory for results.json')
    out = parser.parse_args(argv).out
    TRAPS = roots.need_data('traps')
    SESS = TRAPS / 'sessions'
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for prefix, trap, cause in RUNS:
        s = sdir(prefix)
        R, txt, scored, glue = run_checks(s)
        stops = [k for k in ORDER if R[k]['ok'] is False]
        abst = [k for k in ORDER if R[k]['ok'] is None and R[k]['cause_class'] != 'not_applicable']
        naive = sorted(k for k, v in R['pin_naive_extra'].items() if v['ok'] is False)
        rows.append({'session': s.name, 'trap': trap, 'expected_cause': cause,
                     'native_delivered': bool(scored) and bool(txt),
                     'native_scientific_outcome': (scored or {}).get('scientific_outcome'),
                     'C_stop_checks': stops, 'C_stop_causes': [CAUSE_OF_CHECK[k] for k in stops],
                     'C_abstain_checks': abst, 'naive_extra_pin_failures': naive,
                     'detail': {k: v for k, v in R.items() if k != 'pin_naive_extra'}, 'glue': glue})
    (out / 'results.json').write_bytes(json.dumps(rows, indent=1, ensure_ascii=False, default=str).encode('utf-8'))
    # results.json is a list that other readers index, so the provenance of the replay goes in a sibling file.
    provenance = {'integrity_py': str(Path(I.__file__).resolve()), 'integrity_py_sha256': sha(I.__file__),
                  'delivery_evidence_py_sha256': sha(sys.modules[numbers_in.__module__].__file__),
                  'run_py_sha256': sha(__file__), 'product_commit': roots.product_commit()['commit'],
                  'product_dirty': roots.product_commit()['dirty'], 'results_json_sha256': sha(out / 'results.json')}
    (out / 'results-provenance.json').write_bytes(json.dumps(provenance, indent=1).encode('utf-8'))
    print('%-9s %-11s %-9s %-30s %-16s %s' % ('session', 'trap', 'delivered', 'expected', 'C stops', 'abstain | naive-extra-pin-fails'))
    for r in rows:
        print('%-9s %-11s %-9s %-30s %-16s %s | %s' % (
            r['session'][5:13], r['trap'], r['native_delivered'], r['expected_cause'],
            ','.join(r['C_stop_checks']) or '-', ','.join(r['C_abstain_checks']) or '-',
            ','.join(r['naive_extra_pin_failures']) or '-'))


if __name__ == '__main__':
    main()
