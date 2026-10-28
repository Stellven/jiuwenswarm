"""Offline admission study. No network, app, model, credentials or subprocesses."""
import argparse
import copy
import hashlib
import importlib
import json
from pathlib import Path
import random
import statistics

from derive import derive_tests
from oracle import matches
from usage import typical_use

ROOT = Path(__file__).resolve().parent
REPETITIONS = 100
N = 20
SEED = 361027
BOOTSTRAPS = 2000


def load_declarations():
    return json.loads((ROOT/'declarations.json').read_text(encoding='utf-8'))


def thin(declaration):
    result = copy.deepcopy(declaration)
    result['invariants'] = {}
    result['edge_cases'] = []
    result['description'] = 'Typed ports only; no semantic guarantees.'
    return result


def invoke(fn, p):
    try: return fn(copy.deepcopy(p))
    except Exception as e: return {'status':'crash','exception':type(e).__name__}


def output_types(tool, p, result):
    if type(result) is not dict: return False
    if result == {'status':'error'}: return True
    if result.get('status') != 'ok': return False
    if tool == 'calculate':
        return set(result) == {'status','value'} and type(result['value']) is (int if p['operation'] == 'count' else str)
    return (set(result) == {'status','columns','rows'} and type(result['columns']) is list
        and all(type(c) is str for c in result['columns']) and type(result['rows']) is list
        and all(type(r) is list and all(type(v) in (str,int,float,bool,type(None)) for v in r) for r in result['rows']))


def assess(tool, fn, tests):
    evidence = []
    for t in tests:
        p = t['input']; result = invoke(fn, p)
        ok = output_types(tool, p, result)
        if 'declared_semantics' in t['assertions']: ok = ok and matches(tool, p, result)
        evidence.append({'test':t,'actual':result,'pass':ok})
    return all(t['pass'] for t in evidence), evidence


def bootstrap(values):
    rng = random.Random(SEED + 999)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAPS))
    return {'mean':statistics.mean(values), 'bootstrap_95_ci':[means[49],means[1949]]}


def summarize(rows, reps=REPETITIONS):
    names = ['defects_admitted','defects_rejected','false_rejections','failures_delivered_through_detection','failures_strictly_before_detection','restricted_lag_20']
    by_repeat = []
    for rep in range(reps):
        group = [r for r in rows if r['repeat'] == rep]
        defective = [r for r in group if r['defective']]
        by_repeat.append({
            'defects_admitted':sum(r['admitted'] for r in defective),
            'defects_rejected':sum(not r['admitted'] for r in defective),
            'false_rejections':sum(not r['admitted'] for r in group if not r['defective']),
            'failures_delivered_through_detection':sum(r['failures_delivered_through_detection'] for r in group),
            'failures_strictly_before_detection':sum(r['failures_strictly_before_detection'] for r in group),
            'restricted_lag_20':statistics.mean(r['restricted_lag_20'] for r in defective),
        })
    result = {k:bootstrap([r[k] for r in by_repeat]) for k in names}
    observed = [r['first_failure_use'] for r in rows if r['first_failure_use'] is not None]
    result['conditional_observed_lag_mean'] = statistics.mean(observed) if observed else None
    result['detected_during_use_candidate_repeats'] = len(observed)
    result['per_repeat'] = by_repeat
    return result


def run(out, reps=REPETITIONS):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    declarations = load_declarations()
    labels = json.loads((ROOT/'ground_truth.json').read_text(encoding='utf-8'))
    functions = {r['candidate']:importlib.import_module('candidates.'+r['candidate']).run for r in labels}
    # Freeze all implementation/contracts/scoring sources BEFORE evaluation.
    paths = sorted([*ROOT.glob('*.py'), *ROOT.glob('candidates/*.py'), ROOT/'declarations.json', ROOT/'ground_truth.json', ROOT/'SKILLS.md'])
    hashes = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    write(out, 'frozen_manifest.json', {'seed':SEED,'N':N,'repetitions':reps,'bootstrap_resamples':BOOTSTRAPS,'files':hashes})
    admission = {}
    tests = {}
    for route in ['CC','CC_THIN']:
        tests[route] = {tool:derive_tests(d if route == 'CC' else thin(d)) for tool,d in declarations.items()}
        admission[route] = {}
        for label in labels:
            name,tool = label['candidate'],label['tool']
            ok,evidence = assess(tool,functions[name],tests[route][tool])
            admission[route][name] = {'admitted':ok,'tests_run':len(evidence),'failed_tests':sum(not t['pass'] for t in evidence),'evidence':evidence}
    write(out, 'admission_evidence.json', admission)
    write(out, 'derived_tests.json', tests)
    # Identical draws for all candidates and all routes within a tool/repeat.
    streams = {}
    for tool_index,tool in enumerate(declarations):
        for rep in range(reps):
            rng = random.Random(SEED + 10000*tool_index + rep)
            streams[(tool,rep)] = [typical_use(tool,rng) for _ in range(N)]
    write(out, 'usage_streams.json', [{'tool':t,'repeat':r,'uses':uses} for (t,r),uses in streams.items()])
    rows = {route:[] for route in ['CC','CC_THIN','SKILL']}
    for route in rows:
        for label in labels:
            name,tool = label['candidate'],label['tool']
            pre_admitted = route == 'SKILL' or admission[route][name]['admitted']
            for rep in range(reps):
                history = []
                first = None
                if pre_admitted:
                    for number,p in enumerate(streams[(tool,rep)],1):
                        actual = invoke(functions[name],p)
                        ok = matches(tool,p,actual)
                        history.append({'use':number,'input':p,'actual':actual,'correct':ok})
                        if not ok:
                            first = number
                            break
                # Skill admission decision follows its 20-use probation.
                admitted = pre_admitted and (first is None if route == 'SKILL' else True)
                rows[route].append({'candidate':name,'tool':tool,'defective':label['defective'],'repeat':rep,
                    'admitted':admitted,'pre_admitted':pre_admitted,'first_failure_use':first,
                    'right_censored':bool(pre_admitted and first is None),
                    'restricted_lag_20':0 if not pre_admitted else first if first else N,
                    'failures_delivered_through_detection':int(first is not None),
                    # Immediate oracle: detection is the first wrong response, so this is 0 by construction;
                    # counted from the history so a non-immediate oracle would show up here.
                    'failures_strictly_before_detection':sum(not h['correct'] for h in history if first is not None and h['use'] < first),
                    'history':history})
    for route,data in rows.items(): write(out, route.lower()+'_trials.json',data)
    summary = {route:summarize(data, reps) for route,data in rows.items()}
    summary['paired_skill_minus_cc_defects_admitted'] = bootstrap([
        a['defects_admitted']-b['defects_admitted'] for a,b in zip(summary['SKILL']['per_repeat'],summary['CC']['per_repeat'])])
    write(out, 'results.json',summary)
    render_results(out,summary,rows,admission,reps)
    lines = []
    for route,s in summary.items():
        if 'per_repeat' not in s: continue
        lines.append(f"{route}: defects admitted {s['defects_admitted']['mean']:.2f}/14; rejected {s['defects_rejected']['mean']:.2f}/14; false rejections {s['false_rejections']['mean']:.2f}/2; consumer failures {s['failures_delivered_through_detection']['mean']:.2f}")
    report = '\n'.join(lines)+'\n'
    (out/'run-output.txt').write_bytes(report.encode('utf-8'))
    print(report,end='')


def write(out, name, value):
    (Path(out)/name).write_bytes((json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8'))


def render_results(out,summary,rows,admission,reps=REPETITIONS):
    lines = ['# Deterministic admission results', '',
        'Means per repetition; brackets are percentile bootstrap 95% CIs over ' + str(reps) + ' paired repetitions (2,000 resamples). Fixed 14 defective and 2 correct candidates.', '',
        '| Route | Defects admitted /14 | Defects rejected /14 | False rejections /2 | Consumer failures through detection | Restricted lag, uses |',
        '|---|---:|---:|---:|---:|---:|']
    for route in rows:
        s = summary[route]
        fields = []
        for k in ['defects_admitted','defects_rejected','false_rejections','failures_delivered_through_detection','restricted_lag_20']:
            v = s[k]; lo,hi = v['bootstrap_95_ci']
            fields.append(f"{v['mean']:.2f} [{lo:.2f}, {hi:.2f}]")
        lines.append('| '+route+' | '+' | '.join(fields)+' |')
    lines.extend(['', 'Restricted lag = min(first failure use, 20); undetected is censored at 20; pre-admission rejection has zero consumer exposure. CC lag zero is containment/exposure accounting, not an observed failure time. Conditional observed skill lag = '+f"{summary['SKILL']['conditional_observed_lag_mean']:.2f}"+' uses; it excludes censored candidates and is selection-biased. All routes have zero failures strictly before detection under the immediate oracle assumption. The triggering wrong response counts as one delivered failure.', '',
        '| Candidate | CC failing tests / run | Thin failing tests / run | Skill detected /' + str(reps) + ' | Mean first failure (detected only) | Mean capped lag |',
        '|---|---:|---:|---:|---:|---:|'])
    for name in admission['CC']:
        trials = [r for r in rows['SKILL'] if r['candidate']==name]
        lags = [r['first_failure_use'] for r in trials if r['first_failure_use'] is not None]
        a,b = admission['CC'][name],admission['CC_THIN'][name]
        mean = f'{statistics.mean(lags):.2f}' if lags else 'censored'
        lines.append(f"| {name} | {a['failed_tests']}/{a['tests_run']} | {b['failed_tests']}/{b['tests_run']} | {len(lags)} | {mean} | {statistics.mean(r['restricted_lag_20'] for r in trials):.2f} |")
    lines.extend(['', 'CC and thin decisions occur before consumer use. Skill admission means no observed failure during its probation. Thin post-admission observation uses the same streams and has the same failure exposure as the skill route, but does not retroactively change its pre-admission decision.', ''])
    (Path(out)/'RESULTS.md').write_bytes('\n'.join(lines).encode('utf-8'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='directory for every output file')
    parser.add_argument('--reps', type=int, default=REPETITIONS, help='paired repetitions (default %d, the full study)' % REPETITIONS)
    args = parser.parse_args(argv)
    if args.reps < 1:
        parser.error('--reps must be positive')
    run(args.out, args.reps)


if __name__ == '__main__': main()
