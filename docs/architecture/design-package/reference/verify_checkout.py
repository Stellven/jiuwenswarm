"""Optional exact-source checks; ordinary standalone validation needs neither checkout."""
import argparse
from pathlib import Path
import subprocess
from package_checks import source_issues

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('jiuwenswarm', type=Path)
parser.add_argument('openjiuwen', type=Path)
args = parser.parse_args()
repos = {'jiuwenswarm': args.jiuwenswarm.resolve(), 'openjiuwen': args.openjiuwen.resolve()}


def read_blob(repo, commit, path):
    return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=repos[repo])


errors = source_issues(Path(__file__).resolve().parents[1], read_blob)
if errors:
    raise SystemExit('\n'.join('FAIL: ' + e for e in errors))
print('PASS: recorded JiuwenSwarm/OpenJiuwen Git blobs, symbols and actual dependency pin')
print('LIMIT: source inspection only; runtime compatibility NOT_RUN')
