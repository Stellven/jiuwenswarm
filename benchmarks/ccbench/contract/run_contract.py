"""contract: a declared output contract (typed ports with unit, decimals, range) that is CHECKED, against the same contract as plain text.

  plan    [--case ID]...                         prompt digests, no model call
  freeze                                         write MANIFEST.sha256 for cases.json (once, before any run)
  run     --execute [--case ID]... [--arm A]... [--reps N] [--model M] --out DIR
  score   [--model M] --out DIR                  re-scores saved replies against the frozen gold; model-free

Every arm gets the identical task text: CSV data, question, notes and the declared contract (the typed ports as JSON).
Arms (model gpt-6.1-sol, tool-free codex, 10 data-analysis cases):
  plain     one call.
  verify    one call; the prompt adds "check each value against the data and the contract before you reply".
  cc        one call as plain; the bench validates the reply against the declared ports (exact keys, type, integer vs
            decimal, at most N decimals, min/max in the declared unit, string pattern). On any violation: ONE retry that
            carries the violation list. The validator never sees the gold. Final answer = the retry reply.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import modelbench as mb  # noqa: E402
import contract  # noqa: E402

ARMS = ('plain', 'verify', 'cc')
FROZEN = ('cases.json',)
HEAD = 'You are a data analyst. Answer using only the data below. Do not use any tools, read files or run code.'
TAIL = 'Reply with one JSON object whose keys are exactly the port names of the declared output contract, and nothing else.'
VERIFY = 'Before you reply, check each value in your answer against the data and against the output contract (type, unit, decimals, range) and fix any error.'


def load_cases(ids=None):
    cases = mb.read_json(HERE / 'cases.json')
    if ids:
        unknown = sorted(set(ids) - {c['id'] for c in cases})
        if unknown:
            raise SystemExit('unknown case id(s): %s; known: %s' % (', '.join(unknown), ', '.join(c['id'] for c in cases)))
        cases = [c for c in cases if c['id'] in set(ids)]
    return cases


def contract_text(case):
    return json.dumps({'ports': case['ports']}, indent=1, ensure_ascii=False)


def task_text(case):
    notes = ('Notes: ' + case['notes'] + '\n\n') if case['notes'] else ''
    return '%s\n\n<data format="csv">\n%s\n</data>\n\nQuestion: %s\n\n%sDeclared output contract:\n```json\n%s\n```\n' % (
        HEAD, case['data_csv'], case['question'], notes, contract_text(case))


def first_prompt(case, arm):
    if arm in ('plain', 'cc'):
        return task_text(case) + '\n' + TAIL + '\n'
    if arm == 'verify':
        return task_text(case) + '\n' + VERIFY + ' ' + TAIL + '\n'
    raise ValueError(arm)


def retry_prompt(case, previous_reply, violations):
    return (first_prompt(case, 'cc') + '\nYour previous reply:\n' + previous_reply.strip()[:3000] +
            '\n\nIt violates the declared output contract:\n' + '\n'.join('- ' + v for v in violations[:8]) +
            '\n\nReply again with one corrected JSON object and nothing else.\n')


def run_unit(case, arm, rep, model, unit_dir, call=None):
    call = call or (lambda prompt, d: mb.call_codex(prompt, d, model=model, meta=dict(case=case['id'], arm=arm, rep=rep)))
    unit_dir.mkdir(parents=True, exist_ok=True)
    calls = [call(first_prompt(case, arm), unit_dir / 'call-1')]
    reply1 = calls[0]['reply']
    final, retried, violations = reply1, False, []
    if arm == 'cc':
        violations, _ = contract.validate(reply1, case['ports'])
        if violations:
            retried = True
            calls.append(call(retry_prompt(case, reply1, violations), unit_dir / 'call-2'))
            final = calls[1]['reply']
    (unit_dir / 'reply1.txt').write_bytes(reply1.encode('utf-8'))
    (unit_dir / 'final.txt').write_bytes(final.encode('utf-8'))
    result = dict(case=case['id'], arm=arm, rep=rep, model=model, retried=retried, first_violations=violations[:8],
                  calls=[{k: c[k] for k in ('dir', 'tokens', 'elapsed_s', 'ok')} for c in calls], cost=mb.call_cost(calls),
                  final_sha256=hashlib.sha256(final.encode('utf-8')).hexdigest())
    mb.write_json(unit_dir / 'result.json', result)
    return result


def run(args):
    if not args.execute:
        raise SystemExit('Model calls need --execute. `plan` is the offline dry run.')
    problems = mb.verify_manifest(HERE)
    if problems:
        raise SystemExit('frozen gold check failed: ' + '; '.join(problems))
    mb.roots.require_codex()
    base = args.out / 'contract' / args.model
    for case in load_cases(args.case):
        for rep in range(1, args.reps + 1):
            for arm in mb.rotate(list(args.arm or ARMS), rep):
                unit = base / case['id'] / ('%s-r%d' % (arm, rep))
                if (unit / 'result.json').exists():
                    print('skip (done)', case['id'], arm, rep, flush=True)
                    continue
                if unit.exists():
                    raise SystemExit('%s exists without result.json (interrupted); move it away to redo that unit' % unit)
                res = run_unit(case, arm, rep, args.model, unit)
                print('%s %s r%d: retried=%s calls=%d wall=%.0fs' % (case['id'], arm, rep, res['retried'], res['cost']['calls'], res['cost']['wall_s']), flush=True)


def score_unit(case, unit):
    result = mb.read_json(unit / 'result.json')
    final = (unit / 'final.txt').read_bytes().decode('utf-8')
    first = (unit / 'reply1.txt').read_bytes().decode('utf-8')
    s = contract.score_reply(final, case['ports'], case['gold'])
    f = contract.score_reply(first, case['ports'], case['gold'])
    return dict(case=case['id'], arm=result['arm'], rep=result['rep'], retried=result['retried'], cost=result['cost'],
                fields=s['fields'], all_correct=s['all_correct'], compliant=s['compliant'], correct_and_compliant=s['correct_and_compliant'],
                first_correct_and_compliant=f['correct_and_compliant'], violations=s['violations'], final_sha256=result['final_sha256'])


def aggregate(rows, arms=ARMS):
    out = {}
    for arm in arms:
        g = [r for r in rows if r['arm'] == arm]
        if not g:
            continue
        n = len(g)
        nf = sum(len(r['fields']) for r in g)
        toks = [r['cost']['tokens'] for r in g if r['cost']['tokens'] is not None]
        by_case = {}
        for r in g:
            by_case.setdefault(r['case'], []).append(r['final_sha256'])
        multi = [v for v in by_case.values() if len(v) > 1]
        out[arm] = dict(units=n, correct_and_compliant=sum(r['correct_and_compliant'] for r in g) / n, all_correct=sum(r['all_correct'] for r in g) / n,
                        compliant=sum(r['compliant'] for r in g) / n, field_accuracy=sum(sum(r['fields'].values()) for r in g) / nf,
                        first_attempt_correct_and_compliant=sum(r['first_correct_and_compliant'] for r in g) / n,
                        retry_rate=sum(r['retried'] for r in g) / n, rescued=sum(r['correct_and_compliant'] and not r['first_correct_and_compliant'] for r in g),
                        broken_by_retry=sum(r['first_correct_and_compliant'] and not r['correct_and_compliant'] for r in g),
                        calls=sum(r['cost']['calls'] for r in g), tokens=sum(toks) if toks else None, units_missing_tokens=n - len(toks),
                        wall_s=round(sum(r['cost']['wall_s'] for r in g), 1),
                        identical_reply_across_reps=(sum(len(set(v)) == 1 for v in multi) / len(multi)) if multi else None)
    return out


def paired(rows):
    key = lambda r: (r['case'], r['rep'])
    ours = {key(r): r['correct_and_compliant'] for r in rows if r['arm'] == 'cc'}
    res = {}
    for arm in ARMS:
        if arm == 'cc':
            continue
        theirs = {key(r): r['correct_and_compliant'] for r in rows if r['arm'] == arm}
        common = ours.keys() & theirs.keys()
        res[arm] = dict(pairs=len(common), cc_only=sum(ours[k] and not theirs[k] for k in common), other_only=sum(theirs[k] and not ours[k] for k in common))
    return res


def score(model, out):
    base = Path(out) / 'contract' / model
    cases = {c['id']: c for c in load_cases()}
    rows = [score_unit(cases[p.parent.parent.name], p.parent) for p in sorted(base.glob('*/*/result.json'))]
    if not rows:
        raise SystemExit('no finished units under %s' % base)
    summary, pairs = aggregate(rows), paired(rows)
    scores = Path(out) / 'scores'
    mb.write_json(scores / ('contract-%s.json' % model), dict(model=model, units=rows, aggregate=summary, cc_vs_others=pairs))
    lines = ['| arm | units | correct+compliant | correct | compliant | field acc | first-attempt c+c | retry rate | rescued | broken | calls | tokens | wall s | identical reply across reps |', '|' + '---|' * 14]
    for arm, s in summary.items():
        lines.append('| %s | %d | %.3f | %.3f | %.3f | %.3f | %.3f | %.2f | %d | %d | %d | %s | %s | %s |' % (
            arm, s['units'], s['correct_and_compliant'], s['all_correct'], s['compliant'], s['field_accuracy'], s['first_attempt_correct_and_compliant'],
            s['retry_rate'], s['rescued'], s['broken_by_retry'], s['calls'], s['tokens'], s['wall_s'], s['identical_reply_across_reps']))
    lines.append('')
    for arm, p in pairs.items():
        lines.append('cc vs %s: pairs=%d cc_only=%d %s_only=%d' % (arm, p['pairs'], p['cc_only'], arm, p['other_only']))
    text = '\n'.join(lines) + '\n'
    (scores / ('contract-%s.md' % model)).write_bytes(text.encode('utf-8'))
    print(text)
    return summary


def plan(args):
    cases = load_cases(args.case)
    for case in cases:
        for arm in ARMS:
            raw = first_prompt(case, arm).encode('utf-8')
            print('%-10s %-7s %6d bytes  sha256 %s' % (case['id'], arm, len(raw), hashlib.sha256(raw).hexdigest()[:16]))
    n = len(cases)
    print('\nfull collection: %d cases x 2 reps: %d first calls + at most %d retries (cc) = at most %d model calls' % (n, 3 * n * 2, n * 2, 4 * n * 2))


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
