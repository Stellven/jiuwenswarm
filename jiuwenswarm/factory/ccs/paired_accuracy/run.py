"""CC v2 native entry of eval.paired_accuracy: one JSON packet on stdin, one JSON result on stdout.

order   fix the question order of a paired accuracy run (every MMLU test question, one seeded shuffle) and
        report its digest, the planned checkpoints and the critical value.
verify  recompute a run from its per-question rows: order, pairing, identical canonical prompts, answer keys,
        planned checkpoints only, first-decision stop, and the paired interval of the accuracy loss against
        the pinned margin. Done needs runtime acceptance and a pass.
Reads files only; starts nothing.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paired  # noqa: E402

STATIC, NATIVE, RUNTIME = 'fixture', 'native CC execution', 'runtime acceptance'
ORDER = (STATIC, NATIVE, 'compile', RUNTIME)
FORMAT = 'muse-paired-accuracy/1'


def check(name, status, detail, stage):
    return dict(name=name, status=status, detail=detail, stage=stage)


def result(checks, need=None, **extra):
    failed = [c for c in checks if c['status'] == 'fail']
    reached = None
    for stage in ORDER:
        mine = [c for c in checks if c['stage'] == stage]
        if any(c['status'] in ('fail', 'skipped', 'inconclusive') for c in mine):
            break
        if any(c['status'] == 'pass' for c in mine):
            reached = stage
    why = [f"{c['name']}: {c['detail']}" for c in failed]
    why += [f"{c['name']} inconclusive: {c['detail']}" for c in checks if c['status'] == 'inconclusive']
    if need and (reached is None or ORDER.index(reached) < ORDER.index(need)):
        why.append(f'stage {need} not reached (reached {reached})')
    return dict(done=bool(checks) and not why, checks=checks, stage_reached=reached, not_done_because=why, **extra)


def _doc(value, name):
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value:
        raise ValueError(f'{name} is a document or a path to one')
    path = Path(value)
    return json.loads(path.read_text() if '\n' not in value and path.is_file() else value)


def _dataset(inputs):
    d = Path(inputs['dataset_dir'])
    if not d.is_dir() or not list(d.glob('*_test.csv')):
        raise ValueError(f'dataset_dir has no *_test.csv files: {d}')
    return d


def order(inputs):
    seed = int(inputs.get('seed', paired.SEED))
    qs = paired.mmlu_order(_dataset(inputs), seed)
    ids = [q['id'] for q in qs]
    doc = dict(count=len(ids), order_sha256=paired.sha(json.dumps(ids)), seed=seed, looks=list(paired.LOOKS), z=paired.Z_SEQ,
               first_ids=ids[:5])
    if inputs.get('order_out'):
        Path(inputs['order_out']).write_text(json.dumps(dict(doc, ids=ids), indent=1))
    ok = len(ids) >= paired.LOOKS[-1]
    return result([check('dataset', 'pass' if ok else 'fail', f'{len(ids)} questions in {len({q["subject"] for q in qs})} subjects', NATIVE)],
                  order=doc)


def _model_path(text):
    m = re.search(r'loaded meta data with \d+ key-value pairs and \d+ tensors from (\S+)', text)
    return m.group(1) if m else None


def verify(inputs):
    st = _doc(inputs['state'], 'state')
    margin = float(inputs['margin_pts'])
    min_mass = float(inputs.get('min_letter_mass', 0.5))
    qs = paired.mmlu_order(_dataset(inputs), int(st.get('seed', paired.SEED)))
    by_id = {q['id']: q for q in qs}
    ids = [q['id'] for q in qs]
    ref, cand = st.get('rows', {}).get('A', {}), st.get('rows', {}).get('B', {})
    checks = []

    checks.append(check('state_format', 'pass' if st.get('format') == FORMAT else 'fail', f"format {st.get('format')}", NATIVE))
    same_order = st.get('order_sha256') == paired.sha(json.dumps(ids))
    checks.append(check('order_fixed', 'pass' if same_order else 'fail',
                        f"order digest {'matches' if same_order else 'differs from'} the seeded order of the dataset ({len(ids)} questions)", NATIVE))
    planned = list(st.get('looks', [])) == list(paired.LOOKS) and abs(float(st.get('z', 0)) - paired.Z_SEQ) < 1e-9
    checks.append(check('planned_checkpoints', 'pass' if planned else 'fail',
                        f"looks {st.get('looks')} z {st.get('z')} (planned {list(paired.LOOKS)} z {paired.Z_SEQ})", NATIVE))
    pinned = abs(float(st.get('margin_pts', -1)) - margin) < 1e-9
    checks.append(check('margin_pinned', 'pass' if pinned else 'fail', f"run margin {st.get('margin_pts')} pts, contract {margin} pts", NATIVE))

    for arm, rows in (('A', ref), ('B', cand)):
        n = len(rows)
        prefix = set(rows) == set(ids[:n])
        checks.append(check(f'rows_prefix:{arm}', 'pass' if prefix and n else 'fail',
                            f'{n} rows' + ('' if prefix else ' are not the first rows of the fixed order (a gap or a reordering)'), NATIVE))
        bad_key = [i for i, r in rows.items() if i in by_id and (r.get('answer') != by_id[i]['answer']
                                                              or r.get('correct') != (r.get('pick') == r.get('answer') and r.get('letter_mass', 0) > 0))]
        checks.append(check(f'answer_keys:{arm}', 'fail' if bad_key else 'pass',
                            f'{len(bad_key)} rows disagree with the dataset key or their own pick' + (f' (first {bad_key[0]})' if bad_key else ''), NATIVE))
        bad_prompt = [i for i, r in rows.items() if i in by_id and r.get('prompt_sha256') != paired.sha(paired.prompt(by_id[i]))]
        checks.append(check(f'canonical_prompts:{arm}', 'fail' if bad_prompt else 'pass',
                            f'{len(bad_prompt)} rows were not scored on the canonical prompt' + (f' (first {bad_prompt[0]})' if bad_prompt else ''), NATIVE))

    both = [i for i in ids if i in ref and i in cand]
    checks.append(check('paired', 'pass' if len(both) >= paired.LOOKS[0] else 'fail',
                        f'{len(both)} questions answered by both arms (first checkpoint at {paired.LOOKS[0]})', NATIVE))

    looks = []
    if all(c['status'] == 'pass' for c in checks):
        looks = paired.sequential(ref, cand, ids, margin)
        claimed = [(r['n'], r['decision']) for r in st.get('looks_done', [])]
        recomputed = [(r['n'], r['decision']) for r in looks]
        checks.append(check('recomputed_checkpoints', 'pass' if claimed == recomputed else 'fail',
                            f'claimed {claimed}, recomputed {recomputed}', NATIVE))
        last = looks[-1] if looks else None
        checks.append(check('decision_claimed', 'pass' if (st.get('decision') or None) == (last['decision'] if last and last['decision'] != 'continue' else None) else 'fail',
                            f"state says {st.get('decision')}, rows give {last['decision'] if last else None}", NATIVE))

    # runtime acceptance: real loads, letters carry the probability, a pass
    for arm, rows in (('A', ref), ('B', cand)):
        if not rows:
            continue
        mass = sum(r.get('letter_mass', 0) for r in rows.values()) / len(rows)
        checks.append(check(f'letter_mass:{arm}', 'pass' if mass >= min_mass else 'inconclusive',
                            f'mean probability on A-D after "Answer:" {mass:.3f} (needs {min_mass}); below it the arm is not answering in the scored format', RUNTIME))
    arms = st.get('arms', {})
    loaded = all(arms.get(a, {}).get('load_seconds') for a in ('A', 'B'))
    checks.append(check('server_loads', 'pass' if loaded else 'fail',
                        'both arms record a server load' if loaded else f'missing a server load record: {sorted(arms)}', RUNTIME))
    logs = inputs.get('server_logs')
    if logs:
        paths = {a: _model_path(Path(p).read_text(errors='replace')) for a, p in logs.items()}
        distinct = paths.get('A') and paths.get('B') and paths['A'] != paths['B']
        checks.append(check('distinct_models', 'pass' if distinct else 'fail',
                            f"A {Path(paths.get('A') or '?').name}, B {Path(paths.get('B') or '?').name}", RUNTIME))
    last = looks[-1] if looks else None
    if last:
        verdict = last['decision']
        detail = (f"loss {last['loss_pts']:+.2f} pts, interval [{last['lo_pts']:+.2f}, {last['hi_pts']:+.2f}] at n={last['n']} "
                  f"(z {last['z']}), margin {margin} pts: {verdict}")
        checks.append(check('non_inferiority', 'pass' if verdict == 'pass' else 'fail' if verdict == 'fail' else 'inconclusive', detail, RUNTIME))
    return result(checks, RUNTIME, looks=looks)


def main():
    packet = json.load(sys.stdin)
    capability = packet.get('capability')
    if capability not in ('order', 'verify'):
        print(json.dumps({'outcome': 'error', 'error': {'code': 'INVALID_INPUT', 'message': 'Expected order or verify'}}))
        return
    try:
        outputs = (order if capability == 'order' else verify)(packet.get('inputs', {}))
    except (KeyError, OSError, TypeError, ValueError) as exc:
        outputs = result([check('input', 'fail', f'{type(exc).__name__}: {exc}', NATIVE)], RUNTIME if capability == 'verify' else None)
    print(json.dumps({'outcome': 'ok', 'outputs': outputs}))


if __name__ == '__main__':
    main()
