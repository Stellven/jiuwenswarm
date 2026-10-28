"""Run every ccbench self-test, one bench at a time, and print one line per bench.

Usage: python selftest.py [bench ...]        (default: all). Exit status is 0 only if every selected bench passes.
No model call, no docker call, no write beside the source: each suite runs with a temp directory as its working
directory (openjiuwen writes logs/ into the cwd) and its own folder on PYTHONPATH.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
# bench -> (working directory under ccbench, unittest module)
SUITES = {
    'admission': ('admission', 'test_admission'),
    'gatebench': ('gatebench', 'test_gatebench'),
    'planner': ('planner', 'test_planner_bench'),
    'planbench': ('planbench', 'test_planbench'),
    'nativeadmit': ('nativeadmit', 'test_score'),
    'nativetask': ('nativetask', 'test_run_native_task'),
    'cclib': ('.', 'cclib.test_harness'),
}


def main(argv):
    names = argv or list(SUITES)
    unknown = [n for n in names if n not in SUITES]
    if unknown:
        raise SystemExit('unknown bench: %s (known: %s)' % (', '.join(unknown), ', '.join(SUITES)))
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8')
    failed = []
    for name in names:
        folder, module = SUITES[name]
        path = os.pathsep.join([str((HERE / folder).resolve()), str(HERE)] + ([env['PYTHONPATH']] if env.get('PYTHONPATH') else []))
        with tempfile.TemporaryDirectory() as cwd:
            run = subprocess.run([sys.executable, '-B', '-m', 'unittest', module], cwd=cwd, env=dict(env, PYTHONPATH=path),
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        text = run.stdout.decode('utf-8', 'replace')
        ran = re.search(r'^Ran (\d+) tests?', text, re.M)
        verdict = re.search(r'^(OK|FAILED.*)$', text, re.M)
        print('%-12s %-4s %s tests  %s' % (name, 'PASS' if run.returncode == 0 else 'FAIL', ran.group(1) if ran else '?',
                                           verdict.group(1) if verdict else ''), flush=True)
        if run.returncode:
            failed.append(name)
            sys.stdout.write(text[-3000:])
    print('selftest: %s' % ('all passed' if not failed else 'FAILED: ' + ', '.join(failed)))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
