"""Halt-plus-admitted-fallback for the CC route (offline, no model, no docker).

When cc_route rejects an item's tool, run the ADMITTED reference tool of the same family
(calc_reference/calc_tool.py or table_reference/table_tool.py) on the same item data with the
same invocation recorded in the item's job.json (jobs.tool_answer), then score the delivered
answer against referee gold with score.same. If the reference tool errors, the route still halts.
Usage: python -B cc_fallback.py --out DIR   (reads <out>/cc/*.json from cc_route.py; prints a table and writes <out>/cc_fallback.json)
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
import jobs  # noqa: E402
import score  # noqa: E402

REF = {'calculate': 'calc_reference', 'table_normalize': 'table_reference'}


def run(item, cc_dir):
    job = json.loads((HERE / 'items' / item / 'job.json').read_text(encoding='utf-8'))
    cc = json.loads((Path(cc_dir) / (item + '.json')).read_text(encoding='utf-8'))
    ref = score.load_ref(item)
    if cc['admitted']:
        return {'item': item, 'route': 'admitted tool', 'delivered': cc['delivered_answer'], 'class': score.score_cc(item, cc_dir)['class'], 'gold': ref['answer']}
    refjob = json.loads((HERE / 'items' / REF[job['tool']] / 'job.json').read_text(encoding='utf-8'))
    pub = HERE / 'items' / item / 'public'
    tool = HERE / 'items' / REF[job['tool']] / 'public' / refjob['tool_file']
    j = dict(job)
    j['tool_file'] = str(tool)  # absolute path; cwd stays the item's public dir (its data file)
    ans = jobs.tool_answer(pub, j)
    if ans is None:
        cls = 'justified_halt'  # reference tool also refuses; halt with the failed-test evidence
    elif score.same(ref.get('answer_kind'), ans, ref['answer']):
        cls = 'correct'
    else:
        cls = 'silent_wrong'
    return {'item': item, 'route': 'rejected, fallback to admitted reference', 'delivered': ans, 'class': cls, 'gold': ref['answer']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args().out
    rows = [run(p.name, out / 'cc') for p in sorted((HERE / 'items').iterdir()) if p.is_dir()]
    for r in rows:
        print('%-16s %-12s delivered=%-20s gold=%s' % (r['item'], r['class'], r['delivered'], r['gold']))
    print(json.dumps(score.metrics([r['class'] for r in rows]), indent=1))
    (out / 'cc_fallback.json').write_bytes((json.dumps(rows, indent=1) + '\n').encode('utf-8'))
