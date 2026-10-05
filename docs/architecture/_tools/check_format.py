"""Check pages against standards.md. Prints problems by page. Exit 1 if any problem.

Usage: python check_format.py [--summary]
Checked: front matter keys, H1 first, `PRD:` line and `> Answers:` line under H1, required H2 sections per `type`,
line endings, people names, 'owner' wording, Mermaid style (ASCII, no ';').
"""
import re
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
REQUIRED = {
    'capability': ['What it does', 'Where it sits', 'Declaration', 'Checks', 'Tests', 'Acceptance seeds'],
    'gate-profile': ['Criteria', 'Acceptance seeds'],
    'module': ['What it does', 'Interface', 'Tests', 'Acceptance seeds'],
    'module-spec': ['Purpose', 'Interface', 'Behavior', 'Failure', 'Tests'],
}
PRESENT_TYPES = {'home', 'design', 'plan', 'ledger', 'stories', 'glossary'}
SKIP_DIRS = ('.obsidian', 'exports', '_tools', 'data-foundation', 'contracts/fixtures')
SKIP_FILES = {'model_router_design_en.md'}
NAMES = re.compile(r'\b(Muk|Saurav|Ramika|Xiaoyang|Suraj|Xiaoyang)\b')
KEYS = ['id', 'type', 'level', 'status', 'provides', 'depends_on']


def fm_of(text):
    m = re.match(r'---\n(.*?)\n---\n', text, re.S)
    return (m.group(1), text[m.end():]) if m else ('', text)


def keyval(fm, key):
    m = re.search(rf'^{key}: (.*)$', fm, re.M)
    return m.group(1).strip() if m else None


def main():
    problems = {}
    for p in sorted(V.rglob('*.md')):
        rel = p.relative_to(V).as_posix()
        if any(rel.startswith(s) for s in SKIP_DIRS) or p.name in SKIP_FILES:
            continue
        raw = p.read_bytes().decode('utf-8')
        out = problems.setdefault(rel, [])
        if '\r\n' in raw:
            out.append('CRLF line endings')
        text = raw.replace('\r\n', '\n')
        fm, body = fm_of(text)
        typ = keyval(fm, 'type')
        exempt = typ in ('index', 'generated', 'standard', 'payload-type', 'schema', 'record', 'reference', 'type') \
            or rel.startswith(('types/', 'schemas/')) or rel.startswith('contracts/index-')
        for k in KEYS:
            if keyval(fm, k) is None and not (exempt and k in ('status', 'provides', 'depends_on')):
                out.append(f'front matter lacks `{k}`')
        if not exempt:
            h1 = re.search(r'^# .+$', body, re.M)
            if not h1:
                out.append('no H1')
            else:
                after = body[h1.end():].lstrip('\n').split('\n')
                lines = [l for l in after[:6] if l.strip()]
                prd = keyval(fm, 'prd')
                if prd and prd != '[]' and not (lines and lines[0].startswith('PRD:')):
                    out.append('line under H1 must be `PRD: ...`')
                ans = [l for l in lines[:3] if l.startswith('> Answers:')]
                if not ans:
                    out.append('missing `> Answers: ...` line under H1')
            if typ in REQUIRED:
                heads = [h.strip().strip('`') for h in re.findall(r'^## (.+)$', body, re.M)]
                low = [h.lower() for h in heads]
                last = -1
                for need in REQUIRED[typ]:
                    idx = next((i for i, h in enumerate(low) if h.startswith(need.lower())), None)
                    if idx is None:
                        out.append(f'missing section `{need}`')
                    elif idx < last:
                        out.append(f'section `{need}` is out of order')
                    else:
                        last = idx
            if typ in PRESENT_TYPES and rel.count('/') == 0 and body.count('\n') > 220 and rel not in ('README.md', 'stories.md', 'flow.md', 'terms.md'):
                out.append('present page over about 220 lines')
        if NAMES.search(text):
            out.append('names a person')
        if re.search(r'\bowner\b|\bowns\b', text, re.I) and not rel.startswith(('standards', 'contracts/principles', 'schemas/', 'types/')):
            out.append('uses "owner"/"owns" wording')
        for blk in re.findall(r'```mermaid\n(.*?)```', text, re.S):
            if re.search(r'[^\x00-\x7f]', blk):
                out.append('non-ASCII in Mermaid')
            if re.search(r'\[[^\]]*;[^\]]*\]|\|[^|]*;[^|]*\|', blk):
                out.append('semicolon in a Mermaid label')
    problems = {k: v for k, v in problems.items() if v}
    if '--summary' in sys.argv:
        from collections import Counter
        c = Counter(x.split('`')[0].strip() if x.startswith('missing section') else x for v in problems.values() for x in v)
        for k, n in c.most_common():
            print(f'{n:4d}  {k}')
        print(len(problems), 'pages with problems')
    else:
        for k, v in problems.items():
            print(k)
            for x in v:
                print('   ', x)
        print(len(problems), 'pages with problems')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
