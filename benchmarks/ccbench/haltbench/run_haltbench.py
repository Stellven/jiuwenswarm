"""haltbench: an honest, named stop on requests that should not be answered, against answering anyway.

  plan    [--case ID]...                         prompt digests, no model call
  freeze                                         write MANIFEST.sha256 for cases.json (once, before any run)
  run     --execute [--case ID]... [--arm A]... [--reps N] [--model M] --out DIR
  score   [--model M] --out DIR                  re-scores saved replies against the frozen gold; model-free

10 cases: 5 answerable (controls for false stops) and 5 not answerable (missing column, missing period, contradictory
format, missing exchange rates, empty target). Every arm gets the same task text AND the same stop option: the reply is
{"status":"ok","value":...} or {"status":"cannot_answer","reason":"..."}, and all arms are told not to guess.
Arms:
  plain     one call.
  verify    one call; adds "before replying, check that every requirement is satisfiable from the data; stop if not".
  cc        TWO stages. Stage 1 (fresh call, sees the request and data): list the request's obligations and mark each
            satisfiable or not, with evidence. The bench's gate halts on any unsatisfiable obligation with the named
            obligation as the reason, and does not call stage 2. If all pass (or stage 1 is unparsable) stage 2 is the
            plain call. This is the requirement-check-before-work shape of the product's requirements capsule and the
            planner's INFEASIBLE reply; the obligation list and gate here are bench-side.
"""
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
import re
from decimal import Decimal as D, InvalidOperation
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import modelbench as mb  # noqa: E402

ARMS = ('plain', 'verify', 'cc')
FROZEN = ('cases.json',)
HEAD = 'You are a data analyst. Answer using only the data below. Do not use any tools, read files or run code.'
PROTOCOL = ('Reply with one JSON object and nothing else. Either {"status": "ok", "value": <the answer: a number, or a string>} '
            'or {"status": "cannot_answer", "reason": "<one sentence naming the specific missing or conflicting item>"}. '
            'If the request cannot be answered correctly from the data and instructions given, use cannot_answer. Do not guess.')
VERIFY = ('Before you reply, check that every requirement of the request (each column, period, unit, constraint and format) can actually be satisfied '
          'from the data and instructions given. If one cannot, reply with cannot_answer.')
STAGE1 = ('You are checking a request before any work is done. Do not compute the answer. List every requirement the request places on the answer '
          '(each column, period, unit, constraint and output format it relies on) as obligations, and for each say whether the data and instructions '
          'given satisfy it. Reply with one JSON object and nothing else: {"obligations": [{"id": "R1", "text": "...", "satisfiable": true or false, "evidence": "..."}]}.')


def load_cases(ids=None):
    cases = mb.read_json(HERE / 'cases.json')
    if ids:
        unknown = sorted(set(ids) - {c['id'] for c in cases})
        if unknown:
            raise SystemExit('unknown case id(s): %s; known: %s' % (', '.join(unknown), ', '.join(c['id'] for c in cases)))
        cases = [c for c in cases if c['id'] in set(ids)]
    return cases


def task_text(case):
    notes = ('Notes: ' + case['notes'] + '\n\n') if case['notes'] else ''
    return '%s\n\n<data format="csv">\n%s\n</data>\n\nRequest: %s\n\n%s' % (HEAD, case['data_csv'], case['question'], notes)


def first_prompt(case, arm):
    if arm in ('plain', 'cc'):
        return task_text(case) + PROTOCOL + '\n'
    if arm == 'verify':
        return task_text(case) + VERIFY + ' ' + PROTOCOL + '\n'
    raise ValueError(arm)


def stage1_prompt(case):
    return task_text(case) + STAGE1 + '\n'


def parse_json(text):
    if not text or not text.strip():
        return None
    body = text.strip()
    fence = re.search(r'```(?:json)?\s*\n(.*?)```', body, flags=re.S)
    if fence:
        body = fence.group(1).strip()
    a, b = body.find('{'), body.rfind('}')
    if a < 0 or b <= a:
        return None
    try:
        obj = json.loads(body[a:b + 1])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def gate(stage1_reply):
    """Deterministic gate over the stage-1 obligations. Returns (halt, reason, obligations). Unparsable = no halt (fail open)."""
    obj = parse_json(stage1_reply)
    obligations = obj.get('obligations') if obj else None
    if not isinstance(obligations, list) or not obligations:
        return False, '', None
    for o in obligations:
        if isinstance(o, dict) and o.get('satisfiable') is False:
            return True, '%s: %s (%s)' % (o.get('id', '?'), o.get('text', ''), o.get('evidence', '')), obligations
    return False, '', obligations


def run_unit(case, arm, rep, model, unit_dir, call=None):
    call = call or (lambda prompt, d: mb.call_codex(prompt, d, model=model, meta=dict(case=case['id'], arm=arm, rep=rep)))
    unit_dir.mkdir(parents=True, exist_ok=True)
    calls, halted_by_gate, gate_reason, gate_parsed = [], False, '', None
    if arm == 'cc':
        calls.append(call(stage1_prompt(case), unit_dir / 'call-1-requirements'))
        halted_by_gate, gate_reason, obligations = gate(calls[0]['reply'])
        gate_parsed = obligations is not None
    if halted_by_gate:
        final = json.dumps({'status': 'cannot_answer', 'reason': gate_reason})
    else:
        calls.append(call(first_prompt(case, arm), unit_dir / ('call-%d-answer' % (len(calls) + 1))))
        final = calls[-1]['reply']
    (unit_dir / 'final.txt').write_bytes(final.encode('utf-8'))
    result = dict(case=case['id'], arm=arm, rep=rep, model=model, halted_by_gate=halted_by_gate, gate_reason=gate_reason[:500], gate_parsed=gate_parsed,
                  calls=[{k: c.get(k) for k in ('dir', 'tokens', 'input_tokens', 'output_tokens', 'elapsed_s', 'ok')} for c in calls], cost=mb.call_cost(calls),
                  final_sha256=hashlib.sha256(final.encode('utf-8')).hexdigest())
    mb.write_json(unit_dir / 'result.json', result)
    return result


def classify(case, text):
    """One of: correct, wrong_value, false_stop, unparseable (answerable); correct_stop, wrong_reason_stop, fabricated, unparseable (not answerable)."""
    obj = parse_json(text)
    if not obj or obj.get('status') not in ('ok', 'cannot_answer'):
        return 'unparseable'
    stopped = obj['status'] == 'cannot_answer'
    if case['feasible']:
        if stopped:
            return 'false_stop'
        try:
            v = obj.get('value')
            if isinstance(v, bool):
                return 'wrong_value'
            return 'correct' if abs(D(str(v)) - D(case['gold'])) <= D('0.0051') else 'wrong_value'
        except (InvalidOperation, ValueError, TypeError):
            return 'wrong_value'
    if not stopped:
        return 'fabricated'
    return 'correct_stop' if re.search(case['blocker_regex'], str(obj.get('reason', '')), flags=re.I) else 'wrong_reason_stop'


GOOD = ('correct', 'correct_stop')


def score_unit(case, unit):
    result = mb.read_json(unit / 'result.json')
    final = (unit / 'final.txt').read_bytes().decode('utf-8')
    obj = parse_json(final) or {}
    label = classify(case, final)
    return dict(case=case['id'], feasible=case['feasible'], arm=result['arm'], rep=result['rep'], label=label, good=label in GOOD,
                halted_by_gate=result['halted_by_gate'], cost=result['cost'], final_sha256=result['final_sha256'],
                status=obj.get('status'), reason=str(obj.get('reason', ''))[:300])


def aggregate(rows, arms=ARMS):
    out = {}
    for arm in arms:
        g = [r for r in rows if r['arm'] == arm]
        if not g:
            continue
        n = len(g)
        un, an = [r for r in g if not r['feasible']], [r for r in g if r['feasible']]
        toks = [r['cost']['tokens'] for r in g if r['cost']['tokens'] is not None]
        by_case = {}
        for r in g:
            by_case.setdefault(r['case'], []).append(r['label'])
        multi = [v for v in by_case.values() if len(v) > 1]
        out[arm] = dict(units=n, good=sum(r['good'] for r in g) / n,
                        not_answerable_good=(sum(r['good'] for r in un) / len(un)) if un else None,
                        answerable_good=(sum(r['good'] for r in an) / len(an)) if an else None,
                        labels={k: sum(1 for r in g if r['label'] == k) for k in sorted({r['label'] for r in g})},
                        fabricated=sum(r['label'] == 'fabricated' for r in g), false_stops=sum(r['label'] == 'false_stop' for r in g),
                        gate_halts=sum(r['halted_by_gate'] for r in g), calls=sum(r['cost']['calls'] for r in g),
                        tokens=sum(toks) if toks else None, units_missing_tokens=n - len(toks), wall_s=round(sum(r['cost']['wall_s'] for r in g), 1),
                        same_label_across_reps=(sum(len(set(v)) == 1 for v in multi) / len(multi)) if multi else None)
    return out


def paired(rows):
    key = lambda r: (r['case'], r['rep'])
    ours = {key(r): r['good'] for r in rows if r['arm'] == 'cc'}
    res = {}
    for arm in ARMS:
        if arm == 'cc':
            continue
        theirs = {key(r): r['good'] for r in rows if r['arm'] == arm}
        common = ours.keys() & theirs.keys()
        res[arm] = dict(pairs=len(common), cc_only=sum(ours[k] and not theirs[k] for k in common), other_only=sum(theirs[k] and not ours[k] for k in common))
    return res


def run(args):
    if not args.execute:
        raise SystemExit('Model calls need --execute. `plan` is the offline dry run.')
    problems = mb.verify_manifest(HERE)
    if problems:
        raise SystemExit('frozen gold check failed: ' + '; '.join(problems))
    mb.roots.require_codex()
    base = args.out / 'haltbench' / args.model
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
                print('%s %s r%d: gate_halt=%s calls=%d wall=%.0fs' % (case['id'], arm, rep, res['halted_by_gate'], res['cost']['calls'], res['cost']['wall_s']), flush=True)


def score(model, out):
    base = Path(out) / 'haltbench' / model
    cases = {c['id']: c for c in load_cases()}
    rows = [score_unit(cases[p.parent.parent.name], p.parent) for p in sorted(base.glob('*/*/result.json'))]
    if not rows:
        raise SystemExit('no finished units under %s' % base)
    summary, pairs = aggregate(rows), paired(rows)
    scores = Path(out) / 'scores'
    mb.write_json(scores / ('haltbench-%s.json' % model), dict(model=model, units=rows, aggregate=summary, cc_vs_others=pairs))
    lines = ['| arm | units | good | not-answerable good | answerable good | fabricated | false stops | gate halts | calls | tokens | wall s | same label across reps |', '|' + '---|' * 12]
    for arm, s in summary.items():
        f = lambda x: '-' if x is None else '%.3f' % x
        lines.append('| %s | %d | %.3f | %s | %s | %d | %d | %d | %d | %s | %s | %s |' % (arm, s['units'], s['good'], f(s['not_answerable_good']), f(s['answerable_good']),
                     s['fabricated'], s['false_stops'], s['gate_halts'], s['calls'], s['tokens'], s['wall_s'], s['same_label_across_reps']))
    lines.append('')
    for arm, p in pairs.items():
        lines.append('cc vs %s: pairs=%d cc_only=%d %s_only=%d' % (arm, p['pairs'], p['cc_only'], arm, p['other_only']))
    lines.append('stop reasons are saved in the json for human adjudication of the keyword match')
    text = '\n'.join(lines) + '\n'
    (scores / ('haltbench-%s.md' % model)).write_bytes(text.encode('utf-8'))
    print(text)
    return summary


def plan(args):
    cases = load_cases(args.case)
    for case in cases:
        for arm in ARMS:
            raw = first_prompt(case, arm).encode('utf-8')
            print('%-22s %-7s %6d bytes  sha256 %s' % (case['id'], arm, len(raw), hashlib.sha256(raw).hexdigest()[:16]))
    n = len(cases)
    print('\nfull collection per model: %d cases x 2 reps: plain %d + verify %d + cc %d to %d (stage 1 always, stage 2 unless halted) = at most %d model calls' % (
        n, n * 2, n * 2, n * 2, 2 * n * 2, 4 * n * 2))


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
