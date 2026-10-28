"""CC route: declaration-derived admission tests, then use the tool only if admitted.

Offline. No model, no docker. Runs derive.py tests exactly as admission/study.py does
(study.assess), against the item's public tool module, and writes <out>/cc/<id>.json.
Usage: python -B cc_route.py --out DIR [item_id ...]   (default: all items)
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADM = HERE.parent / 'admission'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ADM))
sys.path.insert(0, str(HERE))
import study  # noqa: E402  (assess / output_types; run() is guarded)
from derive import derive_tests  # noqa: E402
from oracle import expected  # noqa: E402
import jobs  # noqa: E402


def load_run(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.run


def route_item(item_id, decls, evidence_ref=None):
    item = HERE / 'items' / item_id
    job = json.loads((item / 'job.json').read_text(encoding='utf-8'))
    pub = item / 'public'
    tool = job['tool']
    tests = derive_tests(decls[tool])
    fn = load_run(pub / job['tool_file'], 'cc_' + item_id)
    admitted, evidence = study.assess(tool, fn, tests)
    failed = [e for e in evidence if not e['pass']]
    out = {
        'id': item_id, 'tool': tool, 'route': 'CC', 'admitted': admitted,
        'tests_run': len(evidence), 'failed_tests': len(failed),
        'failed_test_evidence': [
            {'test': e['test'], 'actual': e['actual'], 'oracle_expected': expected(tool, e['test']['input'])}
            for e in failed[:5]],
        'delivered_answer': None, 'halt_reason': None,
    }
    if admitted:
        ans = jobs.tool_answer(pub, job)
        if ans is None:
            out['halt_reason'] = 'tool returned an error on the job input after admission'
        else:
            out['delivered_answer'] = ans
    else:
        f = failed[0]
        out['halt_reason'] = ('admission failed: %d of %d derived tests failed; first failed test input=%s, tool returned %s, declared semantics require %s'
                              % (len(failed), len(evidence), json.dumps(f['test']['input'], ensure_ascii=False), json.dumps(f['actual'], ensure_ascii=False),
                                 json.dumps(expected(tool, f['test']['input']), ensure_ascii=False)))
    return out


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='directory; results go to <out>/cc/<id>.json')
    parser.add_argument('items', nargs='*')
    args = parser.parse_args(argv)
    decls = json.loads((ADM / 'declarations.json').read_text(encoding='utf-8'))
    ids = args.items or sorted(p.name for p in (HERE / 'items').iterdir() if p.is_dir())
    cc = args.out / 'cc'
    cc.mkdir(parents=True, exist_ok=True)
    rows = []
    for i in ids:
        r = route_item(i, decls)
        (cc / (i + '.json')).write_bytes((json.dumps(r, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
        rows.append(r)
        print('%-16s admitted=%-5s failed=%3d/%3d answer=%s' % (i, r['admitted'], r['failed_tests'], r['tests_run'], r['delivered_answer']))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
