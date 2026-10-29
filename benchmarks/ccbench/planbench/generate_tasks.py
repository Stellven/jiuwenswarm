"""Regenerate tasks.json and referee/gold.json (fixed synthetic fixtures; no model, no network).

Gold numbers come from referee/oracle.py (independent stdlib arithmetic). Gold report files are the
text rendered by the real report body on the reference plan, frozen here by SHA-256; every numeric
deliverable is cross-checked against the oracle and every reference plan must execute and pass.

Run:  python -B planbench/generate_tasks.py
"""
import sys
sys.dont_write_bytecode = True
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'referee'))
import caps
import executor
import oracle

PLANNER = HERE.parent / 'planner'


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def packet(files=None, data=None):
    files = [dict(path=p, text=t, sha256=sha(t)) for p, t in (files or {}).items()]
    return dict(schema_version='1.0.0', data=data or {}, files=files, trust='provisional', provenance=[], limitations=[])


def paper_summary():
    r = lambda n: dict(id=n, sha256=sha(n))
    sec = lambda t: dict(status='supported', text=t, citation_ids=['C1'])
    return dict(schema_version='1.0.0', id='paper_summary', brief_ref=r('brief'), documents_ref=r('documents'),
                title='Linear classifier on a small benchmark',
                documents=[dict(document_id='P1', source_ref=r('paper-p1'), page_count=4)],
                sections=dict(problem=sec('Classify small tabular records.'), method=sec('A linear classifier trained on the supplied split.'),
                              results=sec('Accuracy 0.85 on the reported test set.'), contributions=sec('A simple baseline.'),
                              limitations=sec('No external validation was performed.')),
                citations=[dict(citation_id='C1', document_id='P1', page=1, start=0, end=40,
                                quote='A classifier achieved accuracy 0.85')])


def calc_req(col, ops, mode):
    return dict(columns=col, operations=ops, numeric_mode=mode)


def csv_req(file, cols, fmt='csv', delim=','):
    return dict(file=file, format=fmt, columns=cols, delimiter=delim)


def report_req(path, title, text, keys):
    return dict(path=path, title=title, sections=[dict(heading='Result', text=text)], data_keys=keys)


def build():
    lib_mod = _load('planner_library', PLANNER / 'library.py')
    ref = lib_mod.ref
    base = json.loads((lib_mod.REPO / 'tests/fixtures/research/planning/lifecycle_research_brief.json').read_text('utf-8'))
    T = []        # (task spec dicts)

    def step(i, cap, src, covers=(), final=False, criteria=()):
        return dict(id=i, capability=cap, inputs=[dict(param='packet', src=src)], outputs=['result'],
                    depends_on=[src['step']] if 'step' in src else [], covers=list(covers), criteria=list(criteria))

    ext = lambda k: {'external': k}
    stp = lambda s: {'step': s, 'output': 'result'}

    # ---- feasible --------------------------------------------------------------------------
    sales = 'region,revenue\nnorth,10.50\nsouth,20.25\neast,30.00\n'
    T.append(dict(id='sum_csv', feasible=True,
        paragraph='Using the supplied packet `sales`, read its CSV file sales.csv and compute the sum and the number of rows of the revenue column.',
        inputs={'sales': ('work_packet', 'packet with sales.csv and its parse/calculation settings',
                          packet({'sales.csv': sales}, dict(table_request=csv_req('sales.csv', ['region', 'revenue']),
                                                           calculation=calc_req(['revenue'], ['count', 'sum'], 'decimal_strings'))))},
        deliverables=[('D1', 'The sum of the revenue column', 'value', ['data', 'calculation_result', 'columns', 'revenue', 'sum'], None),
                      ('D2', 'The row count of the revenue column', 'value', ['data', 'calculation_result', 'columns', 'revenue', 'count'], None)],
        oracle=lambda c: {'D1': oracle.stats([r[1] for r in oracle.rows_from_csv(sales)[1]], ['sum'])['sum'],
                          'D2': oracle.stats([r[1] for r in oracle.rows_from_csv(sales)[1]], ['count'])['count']},
        reference=[step('s1', 'utility.table_normalize', ext('sales'), []), step('s2', 'utility.calculate', stp('s1'), ['D1', 'D2'])],
        decoys=[]))
    runs = 'run,accuracy\na,0.81\nb,0.87\nc,0.84\nd,0.90\n'
    T.append(dict(id='mean_report', feasible=True,
        paragraph='Using the supplied packet `runs`, compute the mean of the accuracy column of runs.csv and write a Markdown report file accuracy_report.md that includes that mean.',
        inputs={'runs': ('work_packet', 'packet with runs.csv, parse/calculation settings and report settings',
                         packet({'runs.csv': runs}, dict(table_request=csv_req('runs.csv', ['run', 'accuracy']),
                                                        calculation=calc_req(['accuracy'], ['mean'], 'decimal_strings'),
                                                        report=report_req('accuracy_report.md', 'Accuracy summary', 'Mean accuracy over four runs.', ['calculation_result']))))},
        deliverables=[('D1', 'The mean accuracy', 'value', ['data', 'calculation_result', 'columns', 'accuracy', 'mean'], None),
                      ('D2', 'The report file accuracy_report.md', 'file', None, 'accuracy_report.md')],
        oracle=lambda c: {'D1': oracle.stats([r[1] for r in oracle.rows_from_csv(runs)[1]], ['mean'])['mean']},
        reference=[step('s1', 'utility.table_normalize', ext('runs')), step('s2', 'utility.calculate', stp('s1'), ['D1']),
                   step('s3', 'utility.markdown_report', stp('s2'), ['D2'])], decoys=[]))
    lat = json.dumps([dict(service='a', ms=120), dict(service='b', ms=95), dict(service='c', ms=143), dict(service='d', ms=101)])
    T.append(dict(id='json_minmax', feasible=True,
        paragraph='Using the supplied packet `latency`, read its JSON file latency.json and report the smallest and the largest ms value.',
        inputs={'latency': ('work_packet', 'packet with latency.json and its parse/calculation settings',
                            packet({'latency.json': lat}, dict(table_request=csv_req('latency.json', ['service', 'ms'], 'json', None),
                                                              calculation=calc_req(['ms'], ['min', 'max'], 'json_numbers'))))},
        deliverables=[('D1', 'The smallest ms value', 'value', ['data', 'calculation_result', 'columns', 'ms', 'min'], None),
                      ('D2', 'The largest ms value', 'value', ['data', 'calculation_result', 'columns', 'ms', 'max'], None)],
        oracle=lambda c: {k: v for k, v in zip(('D1', 'D2'), [oracle.stats([r[1] for r in oracle.rows_from_json(lat, ['service', 'ms'])], [op])[op] for op in ('min', 'max')])},
        reference=[step('s1', 'utility.table_normalize', ext('latency')), step('s2', 'utility.calculate', stp('s1'), ['D1', 'D2'])], decoys=[]))
    q1 = 'month,units\njan,10\nfeb,20\nmar,30\n'
    q2 = 'month,units\napr,5\nmay,15\njun,25\njul,35\n'
    mk = lambda t: packet({'sales.csv': t}, dict(table_request=csv_req('sales.csv', ['month', 'units']), calculation=calc_req(['units'], ['sum'], 'decimal_strings')))
    T.append(dict(id='pick_q2', feasible=True,
        paragraph='Compute the total units sold in the second quarter, using the second-quarter packet. Each packet holds a CSV file sales.csv.',
        inputs={'q1_sales': ('work_packet', 'first-quarter packet with sales.csv and settings', mk(q1)),
                'q2_sales': ('work_packet', 'second-quarter packet with sales.csv and settings', mk(q2))},
        deliverables=[('D1', 'The sum of units in the second quarter', 'value', ['data', 'calculation_result', 'columns', 'units', 'sum'], None)],
        oracle=lambda c: {'D1': oracle.stats([r[1] for r in oracle.rows_from_csv(q2)[1]], ['sum'])['sum']},
        reference=[step('s1', 'utility.table_normalize', ext('q2_sales')), step('s2', 'utility.calculate', stp('s1'), ['D1'])], decoys=['q1_sales']))
    T.append(dict(id='summary_report', feasible=True,
        paragraph='Render the supplied paper summary as a Markdown report file.',
        inputs={'paper': ('paper_summary', 'structured paper summary', paper_summary())},
        deliverables=[('D1', 'The Markdown report file converted/paper-summary.md', 'file', None, 'converted/paper-summary.md')],
        oracle=lambda c: {},
        reference=[step('s1', 'utility.summary_to_packet', ext('paper')), step('s2', 'utility.packet_report', stp('s1'), ['D1'])], decoys=[]))
    T.append(dict(id='table_ready', feasible=True,
        paragraph='The supplied packet `metrics` already holds a parsed table. Compute the mean and the largest value of the score column and write the Markdown report file score_report.md.',
        inputs={'metrics': ('work_packet', 'packet with an already parsed table, calculation settings and report settings',
                            packet({}, dict(table=dict(columns=['run', 'score'], rows=[['a', 0.5], ['b', 0.75], ['c', 1.0]]),
                                            calculation=calc_req(['score'], ['mean', 'max'], 'json_numbers'),
                                            report=report_req('score_report.md', 'Scores', 'Mean and best score.', ['calculation_result']))))},
        deliverables=[('D1', 'The mean score', 'value', ['data', 'calculation_result', 'columns', 'score', 'mean'], None),
                      ('D2', 'The largest score', 'value', ['data', 'calculation_result', 'columns', 'score', 'max'], None),
                      ('D3', 'The report file score_report.md', 'file', None, 'score_report.md')],
        oracle=lambda c: {'D1': oracle.stats([0.5, 0.75, 1.0], ['mean'])['mean'], 'D2': oracle.stats([0.5, 0.75, 1.0], ['max'])['max']},
        reference=[step('s1', 'utility.calculate', ext('metrics')), step('s2', 'utility.markdown_report', stp('s1'), ['D1', 'D2', 'D3'])], decoys=[]))
    items = 'item,count\nbolt,10\nnut,25\nwasher,40\n'
    T.append(dict(id='normalize_report', feasible=True,
        paragraph='Parse items.csv from the supplied packet `inventory` into rows and write the Markdown report file items_report.md that shows the parsed table.',
        inputs={'inventory': ('work_packet', 'packet with items.csv, parse settings and report settings',
                              packet({'items.csv': items}, dict(table_request=csv_req('items.csv', ['item', 'count']),
                                                               report=report_req('items_report.md', 'Items', 'Parsed inventory rows.', ['table']))))},
        deliverables=[('D1', 'The parsed rows of items.csv', 'value', ['data', 'table'], None),
                      ('D2', 'The report file items_report.md', 'file', None, 'items_report.md')],
        oracle=lambda c: {'D1': dict(columns=oracle.rows_from_csv(items)[0], rows=oracle.rows_from_csv(items)[1])},
        reference=[step('s1', 'utility.table_normalize', ext('inventory'), ['D1']), step('s2', 'utility.packet_report', stp('s1'), ['D2'])], decoys=[]))
    tc = 'day,temp\nmon,18\ntue,25\nwed,21\n'
    tf = 'day,temp\nmon,64\ntue,77\nwed,70\n'
    mkt = lambda t: packet({'temps.csv': t}, dict(table_request=csv_req('temps.csv', ['day', 'temp']), calculation=calc_req(['temp'], ['max', 'min'], 'decimal_strings'),
                                                  report=report_req('temps_report.md', 'Temperatures', 'Highest and lowest reading.', ['calculation_result'])))
    T.append(dict(id='pick_fahrenheit', feasible=True,
        paragraph='Find the highest and the lowest Fahrenheit reading, using the Fahrenheit packet, and write the Markdown report file temps_report.md.',
        inputs={'temps_c': ('work_packet', 'Celsius readings: packet with temps.csv and settings', mkt(tc)),
                'temps_f': ('work_packet', 'Fahrenheit readings: packet with temps.csv and settings', mkt(tf))},
        deliverables=[('D1', 'The highest Fahrenheit reading', 'value', ['data', 'calculation_result', 'columns', 'temp', 'max'], None),
                      ('D2', 'The lowest Fahrenheit reading', 'value', ['data', 'calculation_result', 'columns', 'temp', 'min'], None),
                      ('D3', 'The report file temps_report.md', 'file', None, 'temps_report.md')],
        oracle=lambda c: {'D1': oracle.stats([r[1] for r in oracle.rows_from_csv(tf)[1]], ['max'])['max'],
                          'D2': oracle.stats([r[1] for r in oracle.rows_from_csv(tf)[1]], ['min'])['min']},
        reference=[step('s1', 'utility.table_normalize', ext('temps_f')), step('s2', 'utility.calculate', stp('s1'), ['D1', 'D2']),
                   step('s3', 'utility.markdown_report', stp('s2'), ['D3'])], decoys=['temps_c']))

    # ---- infeasible ------------------------------------------------------------------------
    scores = 'name,score\nann,3\nbob,9\ncy,4\n'
    T.append(dict(id='need_median', feasible=False, kind='missing_capability',
        paragraph='Using the supplied packet `scores`, read scores.csv and give the median of the score column.',
        inputs={'scores': ('work_packet', 'packet with scores.csv and settings',
                           packet({'scores.csv': scores}, dict(table_request=csv_req('scores.csv', ['name', 'score']), calculation=calc_req(['score'], ['mean'], 'decimal_strings'))))},
        deliverables=[('D1', 'The median of the score column', 'none', None, None)],
        reason_regex=r'median', missing='a median operation (only count, sum, mean, min, max exist)'))
    T.append(dict(id='need_chart', feasible=False, kind='missing_capability',
        paragraph='Using the supplied packet `sales`, produce a bar-chart image (PNG) of revenue by region.',
        inputs={'sales': ('work_packet', 'packet with sales.csv and its parse/calculation settings',
                          packet({'sales.csv': sales}, dict(table_request=csv_req('sales.csv', ['region', 'revenue']), calculation=calc_req(['revenue'], ['sum'], 'decimal_strings'))))},
        deliverables=[('D1', 'A PNG bar chart of revenue by region', 'none', None, None)],
        reason_regex=r'chart|plot|graph|image|png|draw|figure|visuali', missing='chart or image rendering'))
    T.append(dict(id='missing_final', feasible=False, kind='missing_input',
        paragraph='Compute the mean of the accuracy column in the packet `results_final`. Do not use the draft results.',
        inputs={'results_draft': ('work_packet', 'DRAFT results: packet with draft.csv and settings',
                                  packet({'draft.csv': 'run,accuracy\na,0.5\nb,0.6\n'}, dict(table_request=csv_req('draft.csv', ['run', 'accuracy']), calculation=calc_req(['accuracy'], ['mean'], 'decimal_strings'))))},
        deliverables=[('D1', 'The mean accuracy of the final results', 'none', None, None)],
        reason_regex=r'results_final|final (result|packet|file|data)', missing='the input results_final (only results_draft was supplied)'))
    T.append(dict(id='missing_pdf', feasible=False, kind='missing_input',
        paragraph='Summarize the PDF paper I attached, with exact page quotations, and give me a Markdown report. The notes packet below is not the paper.',
        inputs={'notes': ('work_packet', 'packet with unrelated meeting notes',
                          packet({'notes.txt': 'Agenda: budget review.\n'}, dict()))},
        deliverables=[('D1', 'A Markdown report of the paper summary with page quotations', 'none', None, None)],
        reason_regex=r'document|pdf|paper|buffer|attach|source text', missing='the paper document (no document input was supplied)'))

    tasks, gold = [], {}
    for sp in T:
        tid = sp['id']
        inputs = {k: dict(artifact_type=v[0], description=v[1], content=v[2]) for k, v in sp['inputs'].items()}
        dels = [dict(id=d[0], text=d[1]) for d in sp['deliverables']]
        lines = [sp['paragraph'], 'Plan only: do not run anything.', '', 'Supplied inputs (use these keys):']
        for k, v in inputs.items():
            lines.append('- `%s` (%s): %s' % (k, v['description'], json.dumps(v['content'], ensure_ascii=False, sort_keys=True)))
        lines += ['', 'Deliverables:'] + ['%s: %s' % (d['id'], d['text']) for d in dels]
        request_text = '\n'.join(lines) + '\n'
        # --- Brief v3 (CC arm structure; derived mechanically from the same request) -----------
        b = copy.deepcopy(base)
        b.update(schema_version='3.0.0', constraints=[], target_metrics=[], resource_refs=[], input_bindings=[], context_refs=[], assumptions=[], unresolved_items=[])
        b['objective'].update(id='objective:' + tid, text=request_text)
        b['in_scope'] = [dict(b['objective'], id='scope:' + tid)]
        b['mandatory_requirements'] = [dict(b['objective'], id='requirement:' + tid, text=sp['paragraph'])]
        b['deliverables'] = [dict(id='deliverable:%s:%s' % (tid, d['id'].lower()), name=d['id'].lower(), description=d['text'], artifact_type='work_packet') for d in dels]
        b['acceptance_expectations'] = [dict(id='acceptance:' + tid, requirement_ids=['requirement:' + tid], description='Named output fields or installed check IDs demonstrate the requested outcome.')]
        b['evidence_obligations'] = [dict(id='evidence:' + tid, requirement_ids=['requirement:' + tid], description='Preserve supplied source provenance and expose the checked result without claiming new unperformed research.')]
        inventory = dict(schema_version='1.0.0', id='inventory.' + tid,
                         resources=[dict(resource_key=k, kind='file', available=True, quantity=None, ref=ref(v['content'], k),
                                         artifact_type=v['artifact_type']) for k, v in inputs.items()])
        tasks.append(dict(id=tid, request=request_text, inputs=inputs, deliverables=dels, brief=b, resource_inventory=inventory))
        # --- gold -----------------------------------------------------------------------------
        g = dict(feasible=sp['feasible'], deliverables=[], decoys=sp.get('decoys', []))
        if not sp['feasible']:
            g.update(category=sp['kind'], reason_regex=sp['reason_regex'], missing=sp['missing'])
        else:
            ref_plan = dict(kind='plan', complete_claim=True, steps=sp['reference'], final=sp['reference'][-1]['id'], issues=[])
            task = tasks[-1]
            res = executor.execute(ref_plan, task, decoys=sp['decoys'])
            assert res['executed'] and not [e for e in res['errors'] if e['fatal']], (tid, res['errors'])
            final = res['outputs'][res['final']]
            want = sp['oracle'](None)
            for d in sp['deliverables']:
                if d[2] == 'value':
                    expected = want[d[0]]
                    found, got = executor._walk(final, d[3])
                    assert found and executor._canon(got) == executor._canon(expected), (tid, d[0], got, expected)
                    g['deliverables'].append(dict(id=d[0], kind='value', locator=d[3], expected=expected))
                else:
                    f = next(x for x in final['files'] if x['path'] == d[4])
                    # numbers appearing in the report are cross-checked against the oracle values
                    for v in want.values():
                        if isinstance(v, str):
                            assert v in f['text'], (tid, v)
                    g['deliverables'].append(dict(id=d[0], kind='file', path=d[4], sha256=sha(f['text']), size=len(f['text'].encode())))
            g['reference_plan'] = ref_plan
        gold[tid] = g
    return tasks, gold


def dump(path, value):
    path.write_bytes((json.dumps(value, indent=1, ensure_ascii=False, sort_keys=True) + '\n').encode('utf-8'))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True, help='writes DIR/tasks.json and DIR/referee/gold.json')
    out = ap.parse_args().out
    (out / 'referee').mkdir(parents=True, exist_ok=True)
    tasks, gold = build()
    dump(out / 'tasks.json', tasks)
    dump(out / 'referee' / 'gold.json', gold)
    print('tasks', len(tasks), 'feasible', sum(g['feasible'] for g in gold.values()))
