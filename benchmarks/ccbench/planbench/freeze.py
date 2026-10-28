"""Write or verify SHA256SUMS for the files that must not change after the first real run.

  python -B planbench/freeze.py --out DIR   write DIR/SHA256SUMS
  python -B planbench/freeze.py --check     verify against the SHA256SUMS beside this file (exit 1 on any difference)
Frozen: tasks.json, referee/*, skillpack/** (the skill arm's tools and skills), prompts.py (request + answer format),
caps.py, executor.py, normalize.py, generate_*.py, stubs.py.
"""
import sys
sys.dont_write_bytecode = True
import hashlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
FILES = ['tasks.json', 'prompts.py', 'caps.py', 'executor.py', 'normalize.py', 'stubs.py', 'generate_tasks.py', 'generate_skillpack.py']


def files():
    out = [HERE / f for f in FILES]
    out += sorted(p for p in (HERE / 'referee').iterdir() if p.is_file())
    out += sorted(p for p in (HERE / 'skillpack').rglob('*') if p.is_file())
    return out


def digests():
    return {p.relative_to(HERE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files()}


def check():
    want = {}
    for line in (HERE / 'SHA256SUMS').read_text('utf-8').splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            want[name.lstrip('*')] = h
    have = digests()
    return sorted(set(want) ^ set(have)) + sorted(k for k in want if k in have and want[k] != have[k])


if __name__ == '__main__':
    if '--check' not in sys.argv and '--out' not in sys.argv:
        sys.exit('give --out DIR (or --check)')
    if '--check' in sys.argv:
        bad = check()
        print('OK' if not bad else 'CHANGED: %s' % bad)
        sys.exit(1 if bad else 0)
    out = Path(sys.argv[sys.argv.index('--out') + 1])
    out.mkdir(parents=True, exist_ok=True)
    (out / 'SHA256SUMS').write_bytes(''.join('%s  %s\n' % (h, n) for n, h in digests().items()).encode('utf-8'))
    print('wrote SHA256SUMS (%d files)' % len(digests()))
