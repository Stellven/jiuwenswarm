"""Model-free scoring of a run: parse -> execute -> compare with the referee -> classify -> aggregate.

  python -B planbench/run_arm.py score --label LABEL --out DIR   reads DIR/runs/LABEL, writes DIR/scores/LABEL.json and .md

Views: "cc" (the system as shipped: a plan counts as delivered only if the real gate advanced),
"cc_ungated" (the same CC plans, delivered whatever the checks said), "skill".
Item classes follow SCORING-RULES.md 3.1: correct, justified_halt, wrong_halt, flagged_wrong,
silent_wrong, unavailable. Utility weights: correct +1, justified_halt +1, wrong_halt 0, flagged_wrong -1,
silent_wrong -3, divided by the number of available items.
"""
import sys
sys.dont_write_bytecode = True
import json
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import executor
import normalize

CLASSES = ('correct', 'justified_halt', 'wrong_halt', 'flagged_wrong', 'silent_wrong', 'unavailable')
WEIGHTS = {'correct': 1, 'justified_halt': 1, 'wrong_halt': 0, 'flagged_wrong': -1, 'silent_wrong': -3}


def jload(p):
    return json.loads(Path(p).read_text('utf-8'))


def classify(g, plan, ev, delivered):
    """Return (class, detail) for one item in one view."""
    kind = plan['kind']
    if g['feasible']:
        if kind == 'infeasible':
            return 'wrong_halt', 'false_infeasible'
        if kind == 'unreadable':
            return 'wrong_halt', 'unreadable'
        if not delivered:
            return 'wrong_halt', 'gate_halt'
        if ev['final_correct']:
            return 'correct', ''
        return ('silent_wrong' if plan['complete_claim'] else 'flagged_wrong'), 'wrong_or_not_executable'
    if kind == 'infeasible':
        ok = re.search(g['reason_regex'], plan['reason'].lower()) is not None
        return ('justified_halt', '') if ok else ('wrong_halt', 'reason_mismatch')
    if kind == 'unreadable':
        return 'wrong_halt', 'unreadable'
    if not delivered:
        return 'wrong_halt', 'gate_halt'
    return ('silent_wrong' if plan['complete_claim'] else 'flagged_wrong'), 'planned_an_infeasible_task'


def score_item(arm, rec, task, g, lib):
    transport_failed = rec.get('status') == 'failed' or (arm == 'cc' and not rec.get('reply') and (rec.get('model_calls') or 0) > 0)
    plan = normalize.normalize(arm, rec.get('reply') or '', task, lib)
    res = executor.execute(plan, task, decoys=g['decoys'], checks=(lib or {}).get('checks')) if plan['kind'] == 'plan' else \
        {'executed': False, 'errors': [], 'outputs': {}, 'ran': [], 'final': None, 'criteria': {'total': 0, 'path_checkable': 0, 'check_id': 0, 'checkable': 0, 'steps_without': 0}}
    ev = executor.evaluate(plan, res, g) if plan['kind'] == 'plan' and g['feasible'] else \
        {'final_correct': False, 'deliverables': {d['id']: {'correct': False, 'traced': False, 'covered_by': []} for d in g['deliverables']}}
    views = {}
    for view, delivered in ((('cc', rec.get('delivered', False)), ('cc_ungated', True)) if arm == 'cc' else (('skill', True),)):
        if transport_failed:
            cls, detail = 'unavailable', rec.get('error', 'transport')
        else:
            cls, detail = classify(g, plan, ev, delivered)
        views[view] = {'class': cls, 'detail': detail}
    return plan, res, ev, views


def aggregate(items, view):
    rows = [i for i in items if view in i['views']]
    cnt = Counter(i['views'][view]['class'] for i in rows)
    avail = [i for i in rows if i['views'][view]['class'] != 'unavailable']
    solvable = [i for i in avail if i['feasible']]
    faults = [i for i in avail if not i['feasible']]
    delivered = cnt['correct'] + cnt['flagged_wrong'] + cnt['silent_wrong']
    plans = [i for i in avail if i['plan_kind'] == 'plan']
    errs, fab = Counter(), Counter()
    for i in plans:
        for e in i['errors']:
            errs[e['class']] += 1
        for e in i['errors']:
            if e['class'] in ('fabricated_capability', 'fabricated_input'):
                fab[e['class']] += 1
        for e in i['issues']:
            fab[e['class']] += 1
    crit = Counter()
    for i in plans:
        for k, v in i['criteria'].items():
            crit[k] += v
    dels_all = sum(len(i['deliverables']) for i in solvable)
    out = dict(
        items=len(rows), available=len(avail), classes={c: cnt[c] for c in CLASSES},
        solvable=len(solvable), fault_items=len(faults),
        executed_end_to_end=dict(n=sum(i['executed'] for i in avail), of_plans=len(plans), of_solvable=len(solvable),
                                 n_solvable=sum(i['executed'] for i in solvable)),
        final_answer_correct=dict(n=cnt['correct'], d=len(solvable)),
        delivered_precision=dict(n=cnt['correct'], d=delivered, value=(cnt['correct'] / delivered if delivered else None)),
        coverage=dict(n=cnt['correct'], d=len(solvable), value=(cnt['correct'] / len(solvable) if solvable else None)),
        silent_wrong=dict(n=cnt['silent_wrong'], d=delivered),
        justified_infeasible=dict(n=cnt['justified_halt'], d=len(faults)),
        false_infeasible=dict(n=sum(1 for i in solvable if i['views'][view]['detail'] == 'false_infeasible'), d=len(solvable)),
        gate_halts=sum(1 for i in avail if i['views'][view]['detail'] == 'gate_halt'),
        unreadable=sum(1 for i in avail if i['plan_kind'] == 'unreadable'),
        utility=(sum(WEIGHTS.get(i['views'][view]['class'], 0) for i in avail) / len(avail) if avail else None),
        binding_errors_by_class=dict(sorted(errs.items())),
        fabricated_references=dict(count=sum(fab.values()), by_class=dict(fab),
                                   plans_with_any=sum(1 for i in plans if any(e['class'] in ('fabricated_capability', 'fabricated_input') for e in i['errors']) or i['issues']),
                                   of_plans=len(plans)),
        traceability=dict(n=sum(1 for i in solvable for d in i['deliverables'].values() if d['traced']), d=dels_all),
        acceptance_criteria=dict(total=crit['total'], machine_checkable=crit['checkable'], by_output_path=crit['path_checkable'],
                                 by_installed_check_id=crit['check_id'], steps_without_any=crit['steps_without']),
        calls=sum(i['model_calls'] or 0 for i in rows), tokens=dict(total=sum(i['tokens'] or 0 for i in rows), items_with_tokens=sum(1 for i in rows if i['tokens'] is not None), of=len(rows)))
    return out


def main(label, out_dir):
    out_dir = Path(out_dir)
    gold = jload(HERE / 'referee' / 'gold.json')
    tasks = {t['id']: t for t in jload(HERE / 'tasks.json')}
    base = out_dir / 'runs' / label
    if not base.exists():
        raise SystemExit('no such run: %s' % base)
    lib = None
    items = []
    for arm in ('cc', 'skill'):
        for d in sorted((base / arm).glob('*/record.json')) if (base / arm).exists() else []:
            rec = jload(d)
            if arm == 'cc' and lib is None:
                sys.path.insert(0, str(HERE))
                import run_arm
                lib = run_arm.planner_library()
            plan, res, ev, views = score_item(arm, rec, tasks[rec['task']], gold[rec['task']], lib if arm == 'cc' else None)
            items.append(dict(arm=arm, task=rec['task'], feasible=gold[rec['task']]['feasible'], views=views, plan_kind=plan['kind'],
                              reason=plan.get('reason', ''), complete_claim=plan.get('complete_claim'), executed=res['executed'],
                              errors=res['errors'], issues=plan.get('issues', []), criteria=res['criteria'], deliverables=ev['deliverables'],
                              final_correct=ev['final_correct'], model_calls=rec.get('model_calls'), tokens=rec.get('tokens'),
                              run_label=rec.get('label'), parser=normalize.PARSER_VERSION))
    summary = {}
    for view, arm in (('cc', 'cc'), ('cc_ungated', 'cc'), ('skill', 'skill')):
        sel = [i for i in items if i['arm'] == arm]
        if sel:
            summary[view] = aggregate(sel, view)
    out = out_dir / 'scores'
    out.mkdir(parents=True, exist_ok=True)
    (out / (label + '.json')).write_bytes((json.dumps(dict(label=label, summary=summary, items=items), indent=1, ensure_ascii=False, default=str) + '\n').encode('utf-8'))
    (out / (label + '.md')).write_bytes(table(label, summary, items).encode('utf-8'))
    print(table(label, summary, items))


def frac(d):
    return '%d/%d' % (d['n'], d['d']) + ('' if not d['d'] else ' (%.0f%%)' % (100.0 * d['n'] / d['d']))


def table(label, summary, items):
    views = list(summary)
    L = ['# plan benchmark scores: %s' % label, '', '| metric | ' + ' | '.join(views) + ' |', '|---|' + '---|' * len(views)]
    def row(name, f):
        L.append('| %s | %s |' % (name, ' | '.join(f(summary[v]) for v in views)))
    row('classes (correct / justified_halt / wrong_halt / flagged / silent / unavailable)', lambda s: ' / '.join(str(s['classes'][c]) for c in CLASSES))
    row('executed end to end (solvable items)', lambda s: '%d/%d' % (s['executed_end_to_end']['n_solvable'], s['solvable']))
    row('final answer correct', lambda s: frac(s['final_answer_correct']))
    row('delivered precision', lambda s: frac(s['delivered_precision']))
    row('coverage', lambda s: frac(s['coverage']))
    row('silent_wrong / delivered', lambda s: frac(s['silent_wrong']))
    row('justified infeasible', lambda s: frac(s['justified_infeasible']))
    row('false infeasible', lambda s: frac(s['false_infeasible']))
    row('gate halts / unreadable', lambda s: '%d / %d' % (s['gate_halts'], s['unreadable']))
    row('utility', lambda s: '%.2f' % s['utility'] if s['utility'] is not None else 'n/a')
    row('binding errors by class', lambda s: ', '.join('%s %d' % kv for kv in s['binding_errors_by_class'].items()) or 'none')
    row('fabricated references', lambda s: '%d in %d/%d plans' % (s['fabricated_references']['count'], s['fabricated_references']['plans_with_any'], s['fabricated_references']['of_plans']))
    row('traceability (deliverable -> step)', lambda s: frac(s['traceability']))
    row('machine-checkable criteria', lambda s: '%d/%d (path %d, check id %d)' % (s['acceptance_criteria']['machine_checkable'], s['acceptance_criteria']['total'], s['acceptance_criteria']['by_output_path'], s['acceptance_criteria']['by_installed_check_id']))
    row('model calls', lambda s: str(s['calls']))
    row('tokens (items with a count)', lambda s: '%d (%d/%d)' % (s['tokens']['total'], s['tokens']['items_with_tokens'], s['tokens']['of']))
    L += ['', '## per item', '', '| task | arm | class | detail | plan | executed |', '|---|---|---|---|---|---|']
    for i in items:
        for v, x in i['views'].items():
            L.append('| %s | %s | %s | %s | %s | %s |' % (i['task'], v, x['class'], x['detail'], i['plan_kind'], i['executed']))
    return '\n'.join(L) + '\n'


if __name__ == '__main__':
    main(sys.argv[1])
