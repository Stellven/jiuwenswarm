"""Repair tool for text lost to \\x01 markers.

  python marker_fix.py count [pages...]        markers per page
  python marker_fix.py list  <page>            numbered markers with context (marker shown as <<N>>)
  python marker_fix.py apply <page> <fills.json>   fills.json = JSON list of strings, one per marker in order

Every marker stood for the first use of a key term on that page. Fill with the missing word or words.
"""
import json
import sys
from pathlib import Path

V = Path(__file__).resolve().parent.parent
M = '\x01'


def read(p):
    return Path(p).read_bytes().decode('utf-8').replace('\r\n', '\n')


def main():
    cmd = sys.argv[1]
    if cmd == 'count':
        files = [Path(a) for a in sys.argv[2:]] or sorted(V.rglob('*.md'))
        tot = 0
        for p in files:
            if '.obsidian' in Path(p).parts:
                continue
            n = read(p).count(M)
            if n:
                print(n, Path(p).as_posix())
                tot += n
        print('total', tot)
        return 0
    page = Path(sys.argv[2])
    text = read(page)
    parts = text.split(M)
    if cmd == 'list':
        for i in range(len(parts) - 1):
            before = parts[i][-110:].replace('\n', ' / ')
            after = parts[i + 1][:70].replace('\n', ' / ')
            print(f'[{i}] ...{before}<<{i}>>{after}...')
        print(len(parts) - 1, 'markers')
        return 0
    if cmd == 'apply':
        fills = json.loads(Path(sys.argv[3]).read_text(encoding='utf-8'))
        if len(fills) != len(parts) - 1:
            print(f'need {len(parts) - 1} fills, got {len(fills)}')
            return 1
        out = parts[0]
        for f, rest in zip(fills, parts[1:]):
            out += f + rest
        page.write_bytes(out.encode('utf-8'))
        print('applied', len(fills), 'fills to', page.as_posix())
        return 0
    print(__doc__)
    return 1


if __name__ == '__main__':
    sys.exit(main())
