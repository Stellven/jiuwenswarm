"""Run explicit development check groups inside the existing verify image."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def unit(*names):
    return ['tests/unit_tests/research/test_' + name + '.py' for name in names]


GROUPS = {
    'capabilities': unit('generalist_capsule', 'table_normalize_capsule', 'calculate_capsule', 'markdown_report_capsule'),
    'replay': unit('evaluation_replay'),
    'status': unit('status_stage'),
    'planner': unit('planner_pipeline', 'typed_planner'),
    'builder': unit('builder', 'builder_agent_runtime', 'builder_agent_integration', 'builder_agent_host',
                    'builder_agent_service', 'agent_builder_custody', 'builder_action_rpc'),
    'benchmark': unit('science', 'execution_jobs', 'pi_protocol', 'pi_task', 'pi_execution_jobs', 'pi_benchmark', 'trusted_pi'),
    'completion': ['tests/integration/research/test_codex_completion_profile.py',
                   'tests/unit_tests/runtime/test_codex_subscription.py'],
    'executor': ['tests/integration/research/test_m1_process.py',
                 *unit('process_evidence')],
    'ml-readiness': [*unit('ml_pilot', 'pilot_budget', 'evaluation_pilot', 'capsule_composition',
                          'evaluation_pilot_cli', 'pilot_catalog', 'gate', 'check_asset_admission',
                          'runner', 'compiler_registration', 'bootstrap_gateway', 'evaluation_bootstrap',
                          'static_template_release', 'measurement'),
                     'tests/unit_tests/runtime/test_pilot_subscription_budget.py',
                     'tests/unit_tests/research_sidecar/test_native_diagnostic.py'],
}
SCOPES = ['jiuwenswarm/research', 'jiuwenswarm/research_assets', 'jiuwenswarm/research_contracts',
          'jiuwenswarm/server/runtime/codex_subscription', 'research_contracts', 'tests/unit_tests/research',
          'tests/unit_tests/runtime', 'tests/unit_tests/research_sidecar', 'jiuwenswarm/research_sidecar',
          'tests/integration/research', 'tests/fixtures/research', 'deploy/m1',
          'pyproject.toml', 'uv.lock', 'pytest.ini', '.gitattributes']


def capture_source(root):
    paths = set()
    for scope in SCOPES:
        path = root / scope
        paths.update([path] if path.is_file() else (p for p in path.rglob('*') if p.is_file()))
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if '__pycache__' not in p.parts and p.suffix != '.pyc'}


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group', choices=[*GROUPS, 'all'], required=True)
    parser.add_argument('--case', help='One node ID inside the selected group')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout-s', type=int, default=600)
    args = parser.parse_args(argv)
    if not 10 <= args.timeout_s <= 1200:
        parser.error('timeout must be between 10 and 1200 seconds')
    root = Path('/workspace')
    targets = sorted(set(p for group in GROUPS.values() for p in group)) if args.group == 'all' else GROUPS[args.group]
    if args.case:
        if args.case.split('::', 1)[0] not in targets:
            parser.error('case must belong to the selected group')
        targets = [args.case]
    args.output.mkdir(parents=True, exist_ok=True)
    if any((args.output / name).exists() for name in ('result.json', 'source-manifest.json', 'pytest.log', 'junit.xml')):
        parser.error('output already contains evidence; use a new directory')
    before = capture_source(root)
    write(args.output / 'source-manifest.json', before)
    source_hash = hashlib.sha256(json.dumps(before, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    command = [sys.executable, '-m', 'pytest', '-o', 'addopts=', '-o', 'log_cli=false', '-p', 'no:cacheprovider',
               '-W', 'ignore::SyntaxWarning', '-q', *targets, '--tb=short', '--junitxml=' + str(args.output / 'junit.xml')]
    result = {'schema': 'ai4r-development-checks:1', 'group': args.group, 'targets': targets, 'command': command,
              'python': sys.version, 'source_manifest_sha256': source_hash,
              'scope': 'Development mechanics; controlled model responses except completion profile inspection; no live model-quality claim',
              'timeout_s': args.timeout_s, 'status': 'running'}
    write(args.output / 'result.json', result)
    began = time.monotonic()
    with (args.output / 'pytest.log').open('xb') as log:
        process = subprocess.Popen(command, cwd=root, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            exit_code = process.wait(timeout=args.timeout_s)
            result['status'] = 'passed' if exit_code == 0 else 'failed'
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
            result['status'] = 'timeout' if isinstance(error, subprocess.TimeoutExpired) else 'interrupted'
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            exit_code = 124 if result['status'] == 'timeout' else 130
    result.update(exit_code=exit_code, elapsed_s=time.monotonic() - began)
    after = capture_source(root)
    changed = sorted(p for p in before.keys() | after.keys() if before.get(p) != after.get(p))
    result['source_changes'] = changed
    if changed:
        result['status'], exit_code = 'source_changed', 2
    junit = args.output / 'junit.xml'
    if junit.exists():
        suites = list(ET.parse(junit).getroot().iter('testsuite'))
        counts = {key: sum(int(s.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
        counts['passed'] = counts['tests'] - sum(counts[k] for k in ('failures', 'errors', 'skipped'))
        result['counts'] = counts
    result['exit_code'] = exit_code
    result['files'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in args.output.iterdir() if p.is_file() and p.name != 'result.json'}
    write(args.output / 'result.json', result)
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
