"""Print lines that look like words were deleted (double space inside a sentence, space before punctuation, empty bold).

Usage: python damage_scan.py [pages...]   (default: every page). Exit 1 if any suspicious line is found.
Field-table rows are skipped when they are only empty-Unlocks cells.
"""
import re
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
PATS = [r'(?<=[\w.,)\]])  +(?=[\w(\[`*])', r'(?<=\w) [,.;:](?=\s|$)', r'\( ', r'\*\*\*\*', r'\*\*:\*\*', r'\*\*\s+\*\*', r'\bsuch as ,', r'(?<=\w) \)']
SKIP = ('.obsidian', '_tools', 'exports', 'data-foundation', 'contracts/fixtures', 'contracts/index-')


def scan(p):
    rel = p.relative_to(V).as_posix()
    text = p.read_bytes().decode('utf-8').replace('\r\n', '\n')
    lines = text.split('\n')
    start = 0
    if lines and lines[0] == '---':
        start = lines[1:].index('---') + 2
    out, code = [], False
    for i, line in enumerate(lines):
        if i < start:
            continue
        if line.startswith('```'):
            code = not code
            continue
        if code:
            continue
        if line.lstrip().startswith('|') and re.search(r'\|\s{2}\|', line):
            line = re.sub(r'\|\s{2}\|', '| - |', line)
        for pat in PATS:
            if re.search(pat, line):
                out.append((i + 1, line.strip()[:160]))
                break
    return rel, out


def main():
    args = [Path(a).resolve() for a in sys.argv[1:]]
    paths = args or [p for p in sorted(V.rglob('*.md'))]
    bad = 0
    for p in paths:
        rel = p.relative_to(V).as_posix()
        if any(rel.startswith(s) for s in SKIP) or p.name == 'model_router_design_en.md':
            continue
        rel, hits = scan(p)
        for n, l in hits:
            print(f'{rel}:{n}: {l}')
            bad += 1
    print(bad, 'suspicious line(s)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
