"""heldout: held-out check plus one retry carrying the failure reason (CC) against a model alone and two controls.

  plan    [--case ID]...                                   prompt digests, no model call
  freeze                                                   write MANIFEST.sha256 for cases.json (do this once, before any run)
  run     --execute [--case ID]... [--arm A]... [--reps N] [--model M] --out DIR
  score   [--model M] --out DIR                            re-executes the saved final code on the never-shown score suite

Arms (same task text, same model, tool-free codex, 10 cases):
  plain     one call, "write the function".
  verify    one call, plus the plain instruction "check your function against edge cases and fix it before answering".
  selftest  the model writes the function AND its own tests in one call; the bench runs the model's tests; if they fail,
            ONE retry carrying the model's own failure text. (Control for "any checker", not only an independent one.)
  cc        one call as plain; the bench runs the held-out gate suite (written before the run, by someone else than the
            worker, never the same tests as the score suite); if any gate check fails, ONE retry carrying the failing
            inputs, expected and actual values.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import modelbench as mb  # noqa: E402
import checker  # noqa: E402

ARMS = ('plain', 'verify', 'selftest', 'cc')
FROZEN = ('cases.json',)
RULES = 'Use Python 3 and the standard library only. Do not use any tools, read files, run commands or access a network.'
ONE_BLOCK = 'Reply with exactly one ```python block holding the complete function (and any helpers) and nothing else.'
TWO_BLOCKS = ('Reply with exactly two ```python blocks and nothing else. Block 1: the complete function (and any helpers). '
              'Block 2: a test script of plain assert statements that calls your function on the edge cases you think matter; it will be executed against your function.')
VERIFY = 'Before you answer, check your function against the spec and the edge cases it implies, and fix any error you find.'


def load_cases(ids=None):
    cases = mb.read_json(HERE / 'cases.json')
    if ids:
        unknown = sorted(set(ids) - {c['id'] for c in cases})
        if unknown:
            raise SystemExit('unknown case id(s): %s; known: %s' % (', '.join(unknown), ', '.join(c['id'] for c in cases)))
        cases = [c for c in cases if c['id'] in set(ids)]
    return cases


def task_text(case):
    examples = '\n'.join('  ' + e for e in case['examples'])
    return 'Write a Python function.\n\nSpec: %s\n\nExamples:\n%s\n\n%s' % (case['spec'], examples, RULES)


def first_prompt(case, arm):
    base = task_text(case)
    if arm in ('plain', 'cc'):
        return base + '\n\n' + ONE_BLOCK + '\n'
    if arm == 'verify':
        return base + '\n\n' + VERIFY + ' ' + ONE_BLOCK + '\n'
    if arm == 'selftest':
        return base + '\n\n' + TWO_BLOCKS + '\n'
    raise ValueError(arm)


def retry_prompt(case, arm, previous_code, reason_text):
    base = first_prompt(case, arm)
    if arm == 'cc':
        why = 'Your previous answer failed independent checks that were written separately from this task:\n' + reason_text
    else:
        why = 'Your own test script failed when it was run against your function:\n' + reason_text
    return (base + '\n\nYour previous function:\n```python\n' + (previous_code or '') + '\n```\n' + why +
            '\n\nReturn a corrected complete function in exactly one ```python block and nothing else. Do not change the spec.\n')


def split_reply(reply, arm):
    """(code, tests) from the reply. selftest: block 1 is code, block 2 is tests. Others: first block (or the whole reply if it has no fence)."""
    blocks = [b for b in mb.extract_blocks(reply, 'python')] or mb.extract_blocks(reply)
    if not blocks:
        return (reply if reply.strip().startswith(('def ', 'import ', 'from ')) else None), None
    return blocks[0], (blocks[1] if arm == 'selftest' and len(blocks) > 1 else None)


def gate_reasons(case, code):
    out = checker.run_tests(code, case['function'], case['gate'])
    failed = [(t, r) for t, r in zip(case['gate'], out['results']) if not r['ok']]
    return out, failed


def fmt_reasons(failed, limit=3):
    lines = ['- ' + r['detail'] for _, r in failed[:limit]]
    if len(failed) > limit:
        lines.append('- (%d more checks failed)' % (len(failed) - limit))
    return '\n'.join(lines)


def run_unit(case, arm, rep, model, unit_dir, call=None):
    """One case x arm x repeat. `call(prompt, dir)` is injectable for tests. Returns the result dict (also written)."""
    call = call or (lambda prompt, d: mb.call_codex(prompt, d, model=model, meta=dict(case=case['id'], arm=arm, rep=rep)))
    unit_dir.mkdir(parents=True, exist_ok=True)
    calls = []
    first = call(first_prompt(case, arm), unit_dir / 'call-1')
    calls.append(first)
    code1, tests1 = split_reply(first['reply'], arm)
    (unit_dir / 'attempt1.py').write_bytes((code1 or '').encode('utf-8'))
    final, retried, trigger, check_status = code1, False, '', 'not_run'
    if arm == 'cc' and code1 is not None:
        gate, failed = gate_reasons(case, code1)
        check_status = 'fail' if failed else 'pass'
        if failed:
            trigger = fmt_reasons(failed)
    elif arm == 'cc':
        check_status, trigger = 'fail', '- no function could be extracted from your reply'
    elif arm == 'selftest':
        check_status, trigger = checker.run_selftest(code1 or '', tests1)
        if code1 is None:
            check_status, trigger = 'fail', 'no function could be extracted from your reply'
    if check_status == 'fail':
        retried = True
        second = call(retry_prompt(case, arm, code1, trigger), unit_dir / 'call-2')
        calls.append(second)
        code2, _ = split_reply(second['reply'], arm)
        final = code2
    (unit_dir / 'final.py').write_bytes((final or '').encode('utf-8'))
    result = dict(case=case['id'], arm=arm, rep=rep, model=model, check_status=check_status, retried=retried,
                  trigger=trigger[:1500], calls=[{k: c[k] for k in ('dir', 'tokens', 'elapsed_s', 'ok')} for c in calls],
                  cost=mb.call_cost(calls), final_sha256=hashlib.sha256((final or '').encode('utf-8')).hexdigest(), has_code=bool(final))
    mb.write_json(unit_dir / 'result.json', result)
    return result


def run(args):
    if not args.execute:
        raise SystemExit('Model calls need --execute. `plan` is the offline dry run.')
    problems = mb.verify_manifest(HERE)
    if problems:
        raise SystemExit('frozen gold check failed: ' + '; '.join(problems))
    mb.roots.require_codex()
    cases = load_cases(args.case)
    arms = args.arm or list(ARMS)
    base = args.out / 'heldout' / args.model
    for case in cases:
        for rep in range(1, args.reps + 1):
            for arm in mb.rotate(list(arms), rep):
                unit = base / case['id'] / ('%s-r%d' % (arm, rep))
                if (unit / 'result.json').exists():
                    print('skip (done)', case['id'], arm, rep, flush=True)
                    continue
                if unit.exists():
                    raise SystemExit('%s exists without result.json (interrupted); move it away to redo that unit' % unit)
                res = run_unit(case, arm, rep, args.model, unit)
                print('%s %s r%d: check=%s retried=%s calls=%d wall=%.0fs' % (case['id'], arm, rep, res['check_status'], res['retried'],
                      res['cost']['calls'], res['cost']['wall_s']), flush=True)


def score_unit(case, unit):
    result = mb.read_json(unit / 'result.json')
    final = (unit / 'final.py').read_bytes().decode('utf-8')
    first = (unit / 'attempt1.py').read_bytes().decode('utf-8')
    out = checker.run_tests(final, case['function'], case['score'])
    ok = [r['ok'] for r in out['results']]
    first_ok = ok if not result['retried'] else [r['ok'] for r in checker.run_tests(first, case['function'], case['score'])['results']]
    return dict(case=case['id'], arm=result['arm'], rep=result['rep'], passes=ok, passed_all=all(ok) and bool(ok),
                first_passed_all=all(first_ok) and bool(first_ok), retried=result['retried'], check_status=result['check_status'],
                cost=result['cost'], details=[r['detail'] for r in out['results'] if not r['ok']][:3])


def aggregate(rows, arms=ARMS):
    summary = {}
    for arm in arms:
        g = [r for r in rows if r['arm'] == arm]
        if not g:
            continue
        n = len(g)
        tests = sum(len(r['passes']) for r in g)
        calls = sum(r['cost']['calls'] for r in g)
        toks = [r['cost']['tokens'] for r in g if r['cost']['tokens'] is not None]
        by_case = {}
        for r in g:
            by_case.setdefault(r['case'], []).append(tuple(r['passes']))
        multi = [v for v in by_case.values() if len(v) > 1]
        retried = [r for r in g if r['retried']]
        summary[arm] = dict(units=n, case_pass_rate=sum(r['passed_all'] for r in g) / n,
                            test_pass_rate=sum(sum(r['passes']) for r in g) / tests if tests else None,
                            first_attempt_pass_rate=sum(r['first_passed_all'] for r in g) / n,
                            retry_rate=len(retried) / n, rescued=sum(r['passed_all'] and not r['first_passed_all'] for r in g),
                            broken_by_retry=sum(r['first_passed_all'] and not r['passed_all'] for r in g),
                            calls=calls, tokens=sum(toks) if toks else None, units_missing_tokens=n - len(toks),
                            wall_s=round(sum(r['cost']['wall_s'] for r in g), 1),
                            same_outcome_across_reps=(sum(len(set(v)) == 1 for v in multi) / len(multi)) if multi else None)
    return summary


def paired(rows, a='cc'):
    """Paired comparison on (case, rep): cc passes / other fails and the reverse."""
    key = lambda r: (r['case'], r['rep'])
    ours = {key(r): r['passed_all'] for r in rows if r['arm'] == a}
    out = {}
    for arm in ARMS:
        if arm == a:
            continue
        theirs = {key(r): r['passed_all'] for r in rows if r['arm'] == arm}
        common = ours.keys() & theirs.keys()
        out[arm] = dict(pairs=len(common), cc_only=sum(ours[k] and not theirs[k] for k in common), other_only=sum(theirs[k] and not ours[k] for k in common))
    return out


def score(model, out):
    base = Path(out) / 'heldout' / model
    cases = {c['id']: c for c in load_cases()}
    rows = []
    for result in sorted(base.glob('*/*/result.json')):
        rows.append(score_unit(cases[result.parent.parent.name], result.parent))
    if not rows:
        raise SystemExit('no finished units under %s' % base)
    summary, pairs = aggregate(rows), paired(rows)
    scores = Path(out) / 'scores'
    mb.write_json(scores / ('heldout-%s.json' % model), dict(model=model, units=rows, aggregate=summary, cc_vs_others=pairs))
    lines = ['| arm | units | case pass | test pass | first-attempt pass | retry rate | rescued | broken | calls | tokens | wall s | same outcome across reps |', '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for arm, s in summary.items():
        lines.append('| %s | %d | %.3f | %s | %.3f | %.2f | %d | %d | %d | %s | %s | %s |' % (
            arm, s['units'], s['case_pass_rate'], '%.3f' % s['test_pass_rate'] if s['test_pass_rate'] is not None else '-', s['first_attempt_pass_rate'],
            s['retry_rate'], s['rescued'], s['broken_by_retry'], s['calls'], s['tokens'], s['wall_s'], s['same_outcome_across_reps']))
    lines.append('')
    for arm, p in pairs.items():
        lines.append('cc vs %s: pairs=%d cc_only_pass=%d %s_only_pass=%d' % (arm, p['pairs'], p['cc_only'], arm, p['other_only']))
    text = '\n'.join(lines) + '\n'
    (scores / ('heldout-%s.md' % model)).write_bytes(text.encode('utf-8'))
    print(text)
    return summary


def plan(args):
    for case in load_cases(args.case):
        for arm in ARMS:
            raw = first_prompt(case, arm).encode('utf-8')
            print('%-18s %-9s %6d bytes  sha256 %s' % (case['id'], arm, len(raw), hashlib.sha256(raw).hexdigest()[:16]))
    n = len(load_cases(args.case))
    print('\nfull collection: %d cases x 2 reps: model calls = %d first calls + at most %d retries (cc, selftest) = at most %d' % (n, 4 * n * 2, 2 * n * 2, 6 * n * 2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan'); p.add_argument('--case', action='append'); p.add_argument('--out', type=Path)
    sub.add_parser('freeze').add_argument('--out', type=Path)
    r = sub.add_parser('run')
    r.add_argument('--model', default=mb.MODEL); r.add_argument('--reps', type=int, default=2)
    r.add_argument('--case', action='append'); r.add_argument('--arm', action='append', choices=ARMS)
    r.add_argument('--out', type=Path, required=True); r.add_argument('--execute', action='store_true')
    s = sub.add_parser('score'); s.add_argument('--model', default=mb.MODEL); s.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == 'plan':
        plan(args)
    elif args.command == 'freeze':
        print('\n'.join(mb.write_manifest(HERE, FROZEN)))
    elif args.command == 'run':
        run(args)
    else:
        score(args.model, args.out)


if __name__ == '__main__':
    main()
