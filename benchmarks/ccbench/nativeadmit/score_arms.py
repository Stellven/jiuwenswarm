"""Score finished nativetask arms for luna T1 (nativeadmit) and report class counts plus cost. Model-free, no docker.

  score_arms.py --arm plain=DIR --arm careful=DIR --arm cc=DIR --out OUT

Each DIR is a nativetask --out folder (DIR/sessions/<item>-r<n>/). Every session is scored with score.py (the same rules
as the native scorer) and read with cost.session_usage for input / output tokens, model calls and wall time.
Writes OUT/score-arms.json and OUT/score-arms.md. Sessions that do not exist yet are not counted; a session folder with
no final message scores `unavailable`.
"""
import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import cost  # noqa: E402
import score  # noqa: E402

SESSION = re.compile(r'^(?P<item>.+)-r(?P<rep>\d+)$')


def score_arm(name, folder):
    folder = Path(folder)
    sessions = folder / 'sessions'
    if not sessions.is_dir():
        raise SystemExit('arm %s: %s has no sessions/ folder' % (name, folder))
    rows = []
    for s in sorted(p for p in sessions.iterdir() if p.is_dir()):
        m = SESSION.match(s.name)
        if not m or not (score.HERE / 'referee' / (m.group('item') + '.json')).is_file():
            continue
        res = score.score_native(m.group('item'), s)
        usage = cost.session_usage(s)
        rows.append(dict(arm=name, session=s.name, item=m.group('item'), rep=int(m.group('rep')), cls=res['class'], defect=res['defect'],
                         delivered=res.get('delivered'), gold=res.get('gold'), flagged_tool=res.get('flagged_tool'),
                         input_tokens=usage['input_tokens'], output_tokens=usage['output_tokens'], total_tokens=usage['total_tokens'],
                         calls=usage['calls'], wall_s=usage['wall_s']))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--arm', action='append', required=True, metavar='NAME=DIR')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(argv)
    runs = []
    for spec in args.arm:
        name, sep, folder = spec.partition('=')
        if not sep or not name or not folder:
            raise SystemExit('--arm needs NAME=DIR, got %r' % spec)
        runs.extend(score_arm(name, folder))
    table = cost.cost_table(runs)
    classes = {}
    for arm in table:
        classes[arm] = {c: sum(1 for r in runs if r['arm'] == arm and r['cls'] == c) for c in score.CLASSES}
    result = dict(test='T1 nativeadmit', class_counts=classes, cost=table, rows=runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'score-arms.json').write_bytes((json.dumps(result, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    head = '| arm | ' + ' | '.join(score.CLASSES) + ' |'
    lines = ['## T1 class counts', '', head, '|' + '---|' * (len(score.CLASSES) + 1)]
    for arm, counts in classes.items():
        lines.append('| %s | %s |' % (arm, ' | '.join(str(counts[c]) for c in score.CLASSES)))
    text = '\n'.join(lines) + '\n\n' + cost.markdown(table, '## T1 cost')
    (args.out / 'score-arms.md').write_bytes(text.encode('utf-8'))
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    sys.exit(main())
