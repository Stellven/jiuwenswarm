"""Reproduce offline validation; writes only beneath --out.

Usage (from benchmarks/ccbench): python cclib/verify.py --out DIR
Needs the product repo (AI4R_CODE_ROOT) importable and, for the prompt comparison, the stored trap export under
AI4R_BENCH_DATA (traps/sessions/trap-9c7ea96b.../collection/cc/runs/poc-feasible-r1/artifacts/readable).
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
import roots  # noqa: E402

EXPORT = ('traps', 'sessions', 'trap-9c7ea96ba45949d580884df69efcd46f', 'collection', 'cc', 'runs', 'poc-feasible-r1', 'artifacts', 'readable')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    repo = str(roots.code_root())
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([repo, str(ROOT.parent)]), PYTHONIOENCODING='utf-8',
               PYTHONDONTWRITEBYTECODE='1', AI4R_BENCH_SCRATCH=str(args.out / '.scratch'))
    result = subprocess.run([sys.executable, '-B', '-m', 'unittest', 'cclib.test_harness', '-v'],
                            cwd=ROOT.parent, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    (args.out / 'test-output.txt').write_bytes(result.stdout)
    sys.stdout.write(result.stdout.decode('utf-8'))
    if result.returncode:
        return result.returncode
    # Import only after setting path/environment; no model calls.
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(ROOT.parent), repo]
    from cclib import harness
    from cclib.compare_prompts import compare_export
    harness.SCRATCH_ROOT = args.out / '.scratch'
    export = roots.need_data(*EXPORT)
    comparison = asyncio.run(compare_export(export))
    (args.out / 'prompt-comparison.json').write_bytes((json.dumps(comparison, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    print('Prompt equality: ' + str(sum(p['equal'] for p in comparison['prompts'])) + '/' + str(len(comparison['prompts'])))
    print('All gate decisions equal: ' + str(comparison['all_gates_equal']))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
