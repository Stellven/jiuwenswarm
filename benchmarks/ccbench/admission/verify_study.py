"""Offline rerun/hash verification and exact unittest stdout/stderr capture.

Usage: python verify_study.py --out DIR [--reps N]
Runs study.py twice into DIR/run-1 and DIR/run-2, compares artifact hashes, writes DIR/reproducibility.json
and DIR/test-output.txt. Nothing is written beside the source.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
ARTIFACTS = ['frozen_manifest.json','derived_tests.json','admission_evidence.json',
    'usage_streams.json','cc_trials.json','cc_thin_trials.json','skill_trials.json',
    'results.json','RESULTS.md','run-output.txt']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reps', type=int, default=100)
    args = parser.parse_args(argv)
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    runs = []
    for index in [1,2]:
        run_dir = out/f'run-{index}'
        run = subprocess.run([sys.executable,str(ROOT/'study.py'),'--out',str(run_dir),'--reps',str(args.reps)],
            cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/f'run-{index}.txt').write_bytes(run.stdout)
        if run.returncode:
            sys.stdout.buffer.write(run.stdout)
            return run.returncode
        runs.append({name:hashlib.sha256((run_dir/name).read_bytes()).hexdigest() for name in ARTIFACTS})
    equal = runs[0] == runs[1]
    (out/'reproducibility.json').write_bytes((json.dumps({'identical':equal,'first_run':runs[0],'second_run':runs[1]},indent=2)+'\n').encode('utf-8'))
    if not equal: raise AssertionError('Reproducibility hashes differ')
    print('Reproducibility: 10/10 artifacts byte-identical across two runs.',flush=True)
    test = subprocess.run([sys.executable,'-m','unittest','-v','test_admission'],cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'test-output.txt').write_bytes(test.stdout)
    sys.stdout.buffer.write(test.stdout)
    return test.returncode


if __name__ == '__main__': sys.exit(main())
