"""Materialize sixteen plain Python modules and separate witness labels.

Reproduces the identical sources. Usage: python build_candidates.py --out DIR (writes DIR/candidates and DIR/ground_truth.json).
Neither derive.py nor the usage sampler imports this file or ground_truth.json.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SOURCES = {
    'calculate_reference': 'return calculate(p)',
    'calculate_absolute': "p['values'] = [abs(v) if type(v) in (int, float) else v.lstrip('-') if type(v) is str else v for v in p['values']]\nreturn calculate(p)",
    'calculate_float': "r = calculate(p)\nif r['status'] == 'ok' and p['operation'] != 'count': r['value'] = str(float(r['value']))\nreturn r",
    'calculate_boolean': "if p['mode'] == 'json_numbers': p['values'] = [int(v) if type(v) is bool else v for v in p['values']]\nreturn calculate(p)",
    'calculate_unicode': "if p['mode'] == 'decimal_strings': p['values'] = [''.join(str(unicodedata.digit(c)) if c.isdecimal() else c for c in v) if type(v) is str else v for v in p['values']]\nreturn calculate(p)",
    'calculate_comma': "if p['mode'] == 'decimal_strings': p['values'] = [v.replace(',', '.') if type(v) is str else v for v in p['values']]\nreturn calculate(p)",
    'calculate_empty': "if not p['values']: return {'status': 'error'}\nreturn calculate(p)",
    'calculate_truncate': "r = calculate(p)\nif r['status'] == 'ok' and p['operation'] == 'mean': r['value'] = str(int(Decimal(r['value'])))\nreturn r",
    'table_normalize_reference': 'return table_normalize(p)',
    'table_normalize_numeric': "r = table_normalize(p)\nif r['status'] == 'ok' and p['format'] == 'csv': r['rows'] = [[int(v) if v.isascii() and v.isdigit() else v for v in row] for row in r['rows']]\nreturn r",
    'table_normalize_sorted': "r = table_normalize(p)\nif r['status'] == 'ok': r['rows'].sort(key=repr)\nreturn r",
    'table_normalize_boolean': "r = table_normalize(p)\nif r['status'] == 'ok': r['rows'] = [[int(v) if type(v) is bool else v for v in row] for row in r['rows']]\nreturn r",
    'table_normalize_float': "r = table_normalize(p)\nif r['status'] == 'ok': r['rows'] = [[int(float(v)) if type(v) is int else v for v in row] for row in r['rows']]\nreturn r",
    'table_normalize_pad': "if p['format'] == 'csv':\n    rows = list(csv.reader(io.StringIO(p['text']), delimiter=p['delimiter']))\n    rows = [rows[0]] + [r + [''] * max(0, len(p['columns'])-len(r)) for r in rows[1:]] if rows else []\n    s = io.StringIO(); csv.writer(s, delimiter=p['delimiter']).writerows(rows); p['text'] = s.getvalue()\nreturn table_normalize(p)",
    'table_normalize_empty': "r = table_normalize(p)\nif r['status'] == 'ok' and not r['rows']: return {'status': 'error'}\nreturn r",
    'table_normalize_strip': "r = table_normalize(p)\nif r['status'] == 'ok': r['rows'] = [[v.strip() if type(v) is str else v for v in row] for row in r['rows']]\nreturn r",
}

# Handwritten counterexamples and expected outcomes, independent of generated
# tests and typical-use distribution. Never consulted by admission decisions.
TRUTH = [
 ('calculate_reference', None, None, 'correct'),
 ('calculate_absolute', {'values': [-7, 2], 'mode': 'json_numbers', 'operation': 'sum'}, {'status':'ok','value':'-5'}, 'broad: signs discarded'),
 ('calculate_float', {'values': [9007199254740993], 'mode':'json_numbers','operation':'sum'}, {'status':'ok','value':'9007199254740993'}, 'subtle: binary float precision'),
 ('calculate_boolean', {'values':[True,2],'mode':'json_numbers','operation':'sum'}, {'status':'error'}, 'medium: boolean coercion'),
 ('calculate_unicode', {'values':['٣','2'],'mode':'decimal_strings','operation':'sum'}, {'status':'error'}, 'rare: Unicode grammar acceptance'),
 ('calculate_comma', {'values':['2,5','2'],'mode':'decimal_strings','operation':'sum'}, {'status':'error'}, 'rare: locale coercion'),
 ('calculate_empty', {'values':[],'mode':'json_numbers','operation':'sum'}, {'status':'ok','value':'0'}, 'edge: empty rejection'),
 ('calculate_truncate', {'values':[2,3],'mode':'json_numbers','operation':'mean'}, {'status':'ok','value':'2.5'}, 'broad: fractional means truncated'),
 ('table_normalize_reference', None, None, 'correct'),
 ('table_normalize_numeric', {'text':'id\n007\n','format':'csv','columns':['id'],'delimiter':','}, {'status':'ok','columns':['id'],'rows':[['007']]}, 'broad: CSV numeric coercion'),
 ('table_normalize_sorted', {'text':'x\nz\na\n','format':'csv','columns':['x'],'delimiter':','}, {'status':'ok','columns':['x'],'rows':[['z'],['a']]}, 'medium: row reordering'),
 ('table_normalize_boolean', {'text':'[{"x":true}]','format':'json','columns':['x'],'delimiter':None}, {'status':'ok','columns':['x'],'rows':[[True]]}, 'medium: JSON boolean coercion'),
 ('table_normalize_float', {'text':'[{"x":9007199254740993}]','format':'json','columns':['x'],'delimiter':None}, {'status':'ok','columns':['x'],'rows':[[9007199254740993]]}, 'subtle: large integer precision'),
 ('table_normalize_pad', {'text':'x,y\na\n','format':'csv','columns':['x','y'],'delimiter':','}, {'status':'error'}, 'rare: ragged rows silently padded'),
 ('table_normalize_empty', {'text':'[]','format':'json','columns':['x'],'delimiter':None}, {'status':'ok','columns':['x'],'rows':[]}, 'edge: empty rejection'),
 ('table_normalize_strip', {'text':'x\n a \n','format':'csv','columns':['x'],'delimiter':','}, {'status':'ok','columns':['x'],'rows':[[' a ']]}, 'subtle: whitespace loss'),
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    out = parser.parse_args(argv).out
    dest = out / 'candidates'
    dest.mkdir(parents=True, exist_ok=True)
    for name, body in SOURCES.items():
        text = '"""Seeded study candidate; deterministic, no I/O."""\nimport copy\nimport csv\nimport io\nimport unicodedata\nfrom decimal import Decimal\nfrom reference import calculate, table_normalize\n\ndef run(payload):\n    p = copy.deepcopy(payload)\n' + '\n'.join('    '+line for line in body.splitlines()) + '\n'
        (dest / (name+'.py')).write_bytes(text.encode('utf-8'))
    truth = [{'candidate':n, 'tool':'calculate' if n.startswith('calculate_') else 'table_normalize', 'defective':p is not None, 'witness':p, 'expected':e, 'defect':d} for n,p,e,d in TRUTH]
    (out/'ground_truth.json').write_bytes((json.dumps(truth, ensure_ascii=False, indent=2)+'\n').encode('utf-8'))
    print('Built 16 candidate modules and 16 ground-truth labels.')


if __name__ == '__main__': main()
