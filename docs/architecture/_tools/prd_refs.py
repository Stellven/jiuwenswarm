"""Check that pages cite PRD clause numbers, and that the numbers exist.

Convention (every page except generated, verbatim and index files):
  front matter:   prd: [3.2, 4.7.1]            clause numbers from docs/product/prd-m1-full-2026-10-02.txt
                  prd: []                      allowed only with `prd_note: <reason>` (design with no PRD clause)
  visible line:   `PRD: 3.2, 4.7.1` directly under the first H1, so a reader sees the link
Usage: python prd_refs.py [--list]     (--list prints the clause numbers found in the PRD)
Also writes exports/prd-clauses.json (clause number -> heading) so tools and agents can look clauses up.
"""
import json
import re
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
PRD = V.parent / 'product' / 'prd-m1-full-2026-10-02.txt'
SKIP = ('.obsidian', 'exports', '_tools', 'contracts/fixtures', 'data-foundation')
SKIP_FILES = {'model_router_design_en.md'}
HEAD = re.compile(r'^#{2,5} (\d+(?:\.\d+)*)[ .]+(.+?)\s*$')


def clauses():
    out = {}
    for line in PRD.read_text(encoding='utf-8', errors='replace').split('\n'):
        m = HEAD.match(line)
        if m:
            out[m.group(1).rstrip('.')] = m.group(2)
    return out


def front(text):
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    return m.group(1) if m else ''


def main():
    cl = clauses()
    if '--list' in sys.argv:
        print(len(cl), 'clauses')
        return 0
    (V / 'exports').mkdir(exist_ok=True)
    (V / 'exports' / 'prd-clauses.json').write_text(
        json.dumps({'source': 'docs/product/prd-m1-full-2026-10-02.txt', 'clauses': cl}, indent=1) + '\n', encoding='utf-8', newline='\n')
    problems = []
    for p in sorted(V.rglob('*.md')):
        rel = p.relative_to(V).as_posix()
        if any(rel.startswith(s) for s in SKIP) or p.name in SKIP_FILES or rel.startswith('contracts/index-'):
            continue
        text = p.read_bytes().decode('utf-8').replace('\r\n', '\n')
        fm = front(text)
        m = re.search(r'^prd: \[(.*?)\]\s*$', fm, re.M)
        if not m:
            problems.append(f'{rel}: front matter has no `prd:` list')
            continue
        refs = [x.strip() for x in m.group(1).split(',') if x.strip()]
        if not refs and 'prd_note:' not in fm:
            problems.append(f'{rel}: empty `prd:` needs a `prd_note:` reason')
        for r in refs:
            if r not in cl:
                problems.append(f'{rel}: PRD clause {r} does not exist in the PRD')
        if refs:
            body = text[len(re.match(r'---\n.*?\n---\n', text, re.S).group(0)):]
            h1 = re.search(r'^# .+$', body, re.M)
            vis = re.search(r'^PRD: (.+)$', body[h1.end():h1.end() + 400] if h1 else '', re.M)
            if not vis:
                problems.append(f'{rel}: no visible `PRD: ...` line under the first heading')
            else:
                shown = [x.strip() for x in re.split(r'[,;]', re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', vis.group(1))) if x.strip()]
                if [s for s in shown if re.fullmatch(r'\d+(\.\d+)*', s)] != refs:
                    problems.append(f'{rel}: visible PRD line does not match front matter `prd:`')
    if problems:
        print('\n'.join(problems))
        print(f'{len(problems)} PRD reference problem(s)')
        return 1
    print(f'PRD references ok; {len(cl)} clauses in the PRD')
    return 0


if __name__ == '__main__':
    sys.exit(main())
