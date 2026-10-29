"""Run unittest in a child interpreter and preserve exact, unformatted output.

Usage: python verify.py --out DIR   (writes DIR/tests-output.txt)
"""
import argparse
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--out', type=Path, required=True)
args = parser.parse_args()
args.out.mkdir(parents=True, exist_ok=True)
env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
completed = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', '.',
                            '-p', 'test_gatebench.py', '-v'], cwd=ROOT,
                           env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
(args.out / 'tests-output.txt').write_bytes(completed.stdout)
sys.stdout.buffer.write(completed.stdout)
sys.exit(completed.returncode)
