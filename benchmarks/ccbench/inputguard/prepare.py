"""T2 prepare: build the per-arm input folders and a sha256 manifest. No model, no docker.

  python -B prepare.py --out DIR [--fixtures DIR]

Reads <fixtures>/<fixture>/{task.txt, inputs/, fault.json} (default AI4R_T2_FIXTURES, else the B-theirs reconstruction) and, when
<fixtures>/MANIFEST.sha256 exists, refuses to run if any fixture file differs from it. Writes
  DIR/inputs/<arm>/<fixture>/{task.txt, inputs/...}      arm in plain, careful, cc
  DIR/inputs/MANIFEST.sha256                             sha256 of every file written, relative to DIR/inputs
Arms differ only in the task text:
  plain    the fixture task, byte for byte.
  careful  the task, a blank line, then CAREFUL (one sentence telling the agent to check the inputs).
  cc       the same bytes as plain. The CC arm differs by the guard that runs before the agent (run_guard.py), not by its inputs.
"""
import argparse
import hashlib
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE.parent))
import roots  # noqa: E402

ARMS = ('plain', 'careful', 'cc')
CAREFUL = ('Before you start, check that the input files are consistent with each other and with any stated pins, '
           'and stop with the reason if they are not.')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixtures_in(root):
    root = Path(root)
    if not root.is_dir():
        raise SystemExit('fixtures folder not found: %s. Set AI4R_T2_FIXTURES or pass --fixtures.' % root)
    found = sorted(p for p in root.iterdir() if p.is_dir() and (p / 'task.txt').is_file() and (p / 'inputs').is_dir())
    if not found:
        raise SystemExit('no fixtures (task.txt + inputs/) under %s' % root)
    return found


def verify_fixtures(root):
    """Problems against <root>/MANIFEST.sha256 (lines `<sha256>  <path relative to root>`); [] when it matches or is absent."""
    manifest = Path(root) / 'MANIFEST.sha256'
    if not manifest.is_file():
        return []
    problems = []
    for line in manifest.read_bytes().decode('utf-8').splitlines():
        if not line.strip():
            continue
        digest, name = line.split('  ', 1)
        target = Path(root) / name
        if not target.is_file():
            problems.append('%s is missing' % name)
        elif sha(target) != digest:
            problems.append('%s differs from the manifest' % name)
    return problems


def careful_task(raw):
    sep = b'\n' if raw.endswith(b'\n') else b'\n\n'
    return raw + sep + CAREFUL.encode('utf-8') + b'\n'


def prepare(fixtures, out):
    problems = verify_fixtures(fixtures)
    if problems:
        raise SystemExit('fixtures differ from their manifest: ' + '; '.join(problems[:5]))
    base = Path(out) / 'inputs'
    if base.exists():
        raise SystemExit('%s exists; move it away to prepare again (it is part of the frozen record)' % base)
    names = []
    for fx in fixtures_in(fixtures):
        raw = (fx / 'task.txt').read_bytes()
        for arm in ARMS:
            dest = base / arm / fx.name
            shutil.copytree(fx / 'inputs', dest / 'inputs')
            (dest / 'task.txt').write_bytes(careful_task(raw) if arm == 'careful' else raw)
        names.append(fx.name)
    lines = ['%s  %s' % (sha(p), p.relative_to(base).as_posix()) for p in sorted(base.rglob('*')) if p.is_file()]
    (base / 'MANIFEST.sha256').write_bytes(('\n'.join(lines) + '\n').encode('utf-8'))
    return names


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--fixtures', type=Path, default=None)
    args = ap.parse_args(argv)
    names = prepare(args.fixtures or roots.t2_fixtures(), args.out)
    print('prepared %d fixtures x %d arms under %s' % (len(names), len(ARMS), args.out / 'inputs'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
