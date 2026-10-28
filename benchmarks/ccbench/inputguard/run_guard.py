"""T2 CC arm, step 1: run the product input guard before any agent. No model, no docker.

  python -B run_guard.py --inputs DIR/inputs/cc --out DIR/cc [--code-root ROOT] [--only FIXTURE ...]

For each fixture folder under --inputs (task.txt + inputs/):
  * writes OUT/guard/<fixture>.json (the decision and every check result, with the sha256 of the integrity.py that ran);
  * if the guard halts: writes the CC session OUT/sessions/<fixture>-r1/ (guard.json, final-message.txt with the halt reason and
    the reason code) and the attempt marker OUT/attempts/<fixture>-r1.json, so collect.sh skips it. No agent runs.
  * if the guard passes: writes only the guard json. collect.sh then runs the same nativetask agent as the plain arm.
A fixture whose attempt marker already exists is skipped. The code under test is --code-root, else AI4R_CODE_ROOT, else this repo:
point it at a checkout with a changed integrity.py to run another arm (for example RSI) with no code change.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import guard as G  # noqa: E402
import roots  # noqa: E402


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((json.dumps(value, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))


def run_fixture(fx, out, code_root=None):
    attempt = out / 'attempts' / (fx.name + '-r1.json')
    if attempt.exists():
        return None
    decision = G.guard((fx / 'task.txt').read_bytes().decode('utf-8-sig'), fx / 'inputs', code_root)
    decision['code_root'] = str(Path(code_root) if code_root else roots.code_root())
    decision['product'] = roots.product_commit()
    dump(out / 'guard' / (fx.name + '.json'), decision)
    if decision['halt']:
        session = out / 'sessions' / (fx.name + '-r1')
        dump(session / 'guard.json', decision)
        message = 'HALT by the input guard before the agent started. Reason code: %s. %s\n' % (decision['reason_code'], decision['reason'])
        (session / 'final-message.txt').write_bytes(message.encode('utf-8'))
        dump(attempt, dict(action='guard_halt', attempt_id=fx.name + '-r1', model_calls=0, reason_code=decision['reason_code']))
    return decision


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--code-root', type=Path)
    ap.add_argument('--only', action='append')
    args = ap.parse_args(argv)
    for fx in sorted(p for p in args.inputs.iterdir() if p.is_dir()):
        if args.only and fx.name not in args.only:
            continue
        d = run_fixture(fx, args.out, args.code_root)
        print('%-22s %s' % (fx.name, 'skip (done)' if d is None else ('HALT ' + str(d['reason_code']) if d['halt'] else 'pass (agent will run)')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
