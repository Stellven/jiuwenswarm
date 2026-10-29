"""T2 input guard: the product's deterministic integrity checks, run on a fixture's input files BEFORE any agent starts.

Product code is read, never edited: jiuwenswarm/research/checks/integrity.py is loaded by file path from the code root
(`--code-root DIR`, else AI4R_CODE_ROOT, else this repo). That file imports only the standard library, so it runs without the
product store or the app. The glue below only turns fixture files into the arguments those functions take; it is the same
glue as trapcheck/run.py, minus what needs a run the guard has not seen.

What the guard can and cannot check from the input files alone:
  pin       environment-lock.json bytes against the host-record pin in resource-pins.json      checked
  units     declared unit of the accuracy metric in README.md / TASK.md / the task text          checked
  stale     the file manifest (a draft or duplicate dataset beside data.json)                    checked
  bound     an absolute acceptance threshold stated as a fraction on the 0-1 scale               checked
  split     train and test rows with equal features                                              checked
  baseline  needs the replayed baseline predictions, which only a run of baseline.zip produces  NOT checkable here (abstains)
  claims    needs a delivered report                                                              not applicable before the agent
Prose conflicts (conflicts-e6830418) and overreach (overreach-1fdc5eaf) have no check in integrity.py: the guard cannot halt
on them, and the baseline-definition fixture needs the replay. These are known misses, reported as they stand.

Decision: halt when any checked function returns ok=False. ok=None (not assessable) never halts.
"""
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import roots  # noqa: E402

CAUSE_OF_CHECK = {'pin': 'environment_lock_pin_mismatch', 'units': 'metric_unit_conflict', 'stale': 'stale_or_duplicate_dataset',
                  'bound': 'infeasible_accuracy_bound', 'split': 'train_test_feature_overlap'}
ORDER = ('pin', 'units', 'stale', 'bound', 'split')


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_integrity(code_root=None):
    root = Path(code_root) if code_root else roots.code_root()
    path = root / 'jiuwenswarm' / 'research' / 'checks' / 'integrity.py'
    if not path.is_file():
        raise SystemExit('integrity.py not found at %s. Set --code-root or AI4R_CODE_ROOT to a checkout of the product repo.' % path)
    spec = importlib.util.spec_from_file_location('ccbench_integrity_' + sha256_file(path)[:8], path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def _text(path):
    return Path(path).read_bytes().decode('utf-8-sig')


def run_checks(integrity, task_text, inputs):
    """{check: integrity result} for the checks that can run on the input files alone, plus baseline as an abstention."""
    inputs = Path(inputs)
    readme = _text(inputs / 'README.md')
    task_md = _text(inputs / 'TASK.md')
    text_all = readme + '\n' + task_md + '\n' + task_text
    pins = json.loads(_text(inputs / 'resource-pins.json'))
    data = json.loads(_text(inputs / 'data.json'))
    R = {}
    R['pin'] = integrity.pin_matches((inputs / 'environment-lock.json').read_bytes(), pins['host_records']['environment_lock']['sha256'])
    metrics = []
    if re.search(r'reported in percent', readme):
        metrics.append({'name': 'accuracy', 'unit': 'percent', 'value': 0})
    if re.search(r'Metric accuracy \(fraction\)', task_text):
        metrics.append({'name': 'accuracy', 'unit': 'fraction', 'value': 0})
    if re.search(r'Accuracy is the fraction', readme):
        metrics.append({'name': 'accuracy', 'unit': 'fraction', 'value': 0})
    R['units'] = integrity.units_consistent(metrics)    # value 0 is in range for both units: only the unit statements are tested
    entries = []
    for f in sorted(p for p in inputs.iterdir() if p.is_file()):
        role = f.name
        if f.suffix == '.json':
            try:
                j = json.loads(_text(f))
                if isinstance(j, dict) and 'dataset_id' in j and 'train' in j:
                    role = 'dataset:' + j['dataset_id']
            except ValueError:
                pass
        entries.append({'path': f.name, 'sha256': sha256_file(f), 'role': role, 'version': '1'})
    R['stale'] = integrity.no_stale_duplicate(entries)
    m = re.search(r'at least ([0-9]*\.?[0-9]+) as a fraction on the 0-1 scale', text_all)
    R['bound'] = integrity.bound_feasible((0, 1), m.group(1)) if m else {
        'ok': None, 'cause_class': 'not_applicable', 'evidence': [{'reason': 'no absolute threshold stated'}]}
    R['split'] = integrity.split_disjoint(data['train'], data['test'], ['features'])
    R['baseline'] = {'ok': None, 'cause_class': 'not_assessable',
                     'evidence': [{'reason': 'needs the replayed baseline predictions; the fixture has only baseline.zip'}]}
    return R


def decide(results):
    """Halt decision from check results: {halt, checks_failed, causes, reason_code, reason}."""
    failed = [k for k in ORDER if results[k]['ok'] is False]
    causes = [CAUSE_OF_CHECK[k] for k in failed]
    reason = '; '.join('%s: %s %s' % (k, results[k]['cause_class'], json.dumps(results[k]['evidence'], ensure_ascii=False)[:300]) for k in failed)
    return dict(halt=bool(failed), checks_failed=failed, causes=causes, reason_code=causes[0] if causes else None, reason=reason)


def guard(task_text, inputs, code_root=None):
    """Run the guard. Returns the decision plus the full per-check results and the provenance of integrity.py."""
    integrity, path = load_integrity(code_root)
    results = run_checks(integrity, task_text, inputs)
    out = decide(results)
    out['results'] = results
    out['abstained'] = [k for k, v in results.items() if v['ok'] is None and v['cause_class'] != 'not_applicable']
    out['integrity_py'] = str(path)
    out['integrity_py_sha256'] = sha256_file(path)
    return out
